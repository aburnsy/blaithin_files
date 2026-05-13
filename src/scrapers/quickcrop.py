"""QuickCrop Ireland scraper — BigCommerce Stencil, no JS rendering needed.

QuickCrop is a BigCommerce store. For products with size/variant options the
price update on the product page is driven by an XHR call to BigCommerce's
public storefront endpoint::

    POST /remote/v1/product-attributes/<product_id>
    body: action=add&product_id=<id>&attribute[<attr_id>]=<value_id>

We call that endpoint directly with httpx — one short request per option —
instead of driving Selenium through the dropdown. Single-price products
parse straight from the product page HTML.

Category discovery is sitemap-driven (``/xmlsitemap.php?type=categories``)
for full catalog coverage. The legacy ``config/quickcrop.py`` hand-picked
seed list missed most of the catalog.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.bigcommerce_sitemap import bc_category_urls
from src.scrapers.http import RetryExhausted

_BASE = "https://www.quickcrop.ie"

_MULTIBUY_PATTERNS = (
    re.compile(r"(\d+) x \w+", re.IGNORECASE),
    re.compile(r"(\d+) Tree", re.IGNORECASE),
    re.compile(r"(\d+) Pack", re.IGNORECASE),
    re.compile(r"(\d+) Plant", re.IGNORECASE),
)


class QuickcropScraper(BaseScraper):
    source = "quickcrop"
    rate_limit_seconds = 0.5
    # Subclasses (mr_middleton) override _site_base; default is quickcrop.ie.
    _site_base: str = _BASE

    def discover_categories(self) -> list[tuple[str, str]]:
        """Walk every category in the BigCommerce sitemap, paginating each
        with ``?page=N`` until the grid is empty.
        """
        leaves: list[tuple[str, str]] = []
        for base_url in bc_category_urls(self._site_base, log=self.log):
            category_name = _slug_to_label(base_url)
            page = 1
            while True:
                url = base_url if page == 1 else f"{base_url}?page={page}"
                html = self._safe_fetch(url)
                if not html or not self._listing_has_grid(html):
                    break
                leaves.append((url, category_name))
                page += 1
        return leaves

    def _safe_fetch(self, url: str) -> str:
        try:
            return self.fetch(url)
        except RetryExhausted as e:
            self.log.warning("listing_fetch_failed", url=url, error=str(e))
            return ""

    @staticmethod
    def _listing_has_grid(html: str) -> bool:
        # Look for actual product cards (`.card-title` anchors). The grid
        # itself often renders subcategory tiles on parent-category pages
        # and on out-of-range ``?page=N`` URLs that wrap back to the
        # landing tile view, so checking for ``li`` alone false-positives.
        soup = BeautifulSoup(html, "html.parser")
        grid = soup.find("ul", class_="productGrid")
        if grid is None:
            return False
        return bool(grid.select_one("li .card-title a"))

    def parse_listing(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        grid = soup.find("ul", class_="productGrid")
        if grid is None:
            return []
        out: list[str] = []
        seen: set[str] = set()
        for li in grid.find_all("li"):
            card_title = li.find(class_="card-title")
            if card_title is None or card_title.a is None:
                continue
            href = _as_str(card_title.a.get("href"))
            if not href:
                continue
            url = re.sub(r"^https?://(?:www\.)?quickcrop\.ie", _BASE, href).split("?", 1)[0]
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | list[dict] | None:
        soup = BeautifulSoup(html, "html.parser")

        product_name = self._extract_product_name(soup)
        if not product_name:
            return None
        description = self._extract_description(soup)
        img_url = self._extract_image(soup)

        # Try variant path: find a <select> with attribute[N] name + product_id.
        variant_rows = self._maybe_extract_variants(
            soup,
            product_url=product_url,
            source_url=source_url,
            category=category,
            product_name=product_name,
            description=description,
            img_url=img_url,
        )
        if variant_rows is not None:
            return variant_rows

        # Simple product — single price/stock from the product page.
        price = self._extract_page_price(soup)
        stock = self._extract_page_stock(soup)
        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": category,
            "product_name": product_name,
            "img_url": img_url,
            "description": description,
            "price": price,
            "size": None,
            "stock": stock,
            "quantity": _extract_quantity(product_name),
        }

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_product_name(soup: BeautifulSoup) -> str | None:
        el = soup.find("h1", class_="productView-title")
        if not el:
            return None
        raw = el.get_text(strip=True)
        return raw.split(" - ", 1)[0] if raw else None

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        desc_base = soup.find("div", id="custom-product-short-description")
        if not desc_base:
            return None
        items = desc_base.find_all("li")
        if items:
            return "\n".join(li.get_text(strip=True) for li in items)
        p = desc_base.find("p")
        if p:
            return p.get_text(strip=True) or None
        text = desc_base.get_text(strip=True)
        return text or None

    @staticmethod
    def _extract_image(soup: BeautifulSoup) -> str | None:
        container = soup.find("div", class_="productView-img-container")
        if not container:
            return None
        img = container.find("img")
        if not img:
            return None
        return _as_str(img.get("src")) or _as_str(img.get("data-src"))

    @staticmethod
    def _extract_page_price(soup: BeautifulSoup) -> float | None:
        # Some products display "€12.95 - €49.50" price ranges on the PDP.
        # ``_price_from_text`` strips separators and would parse that as
        # 129549.50 — take the first price token instead.
        span = soup.find("span", class_="price price--withTax")
        if not span:
            return None
        raw = span.get_text(strip=True)
        m = re.search(r"(\d+(?:[.,]\d+)?)", raw)
        return _price_from_text(m.group(1)) if m else None

    @staticmethod
    def _extract_page_stock(soup: BeautifulSoup) -> int | None:
        span = soup.find("span", attrs={"data-product-stock": ""})
        if not span:
            return None
        text = span.get_text(strip=True)
        try:
            return int(text)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # BigCommerce variant resolution
    # ------------------------------------------------------------------

    def _maybe_extract_variants(
        self,
        soup: BeautifulSoup,
        *,
        product_url: str,
        source_url: str,
        category: str,
        product_name: str,
        description: str | None,
        img_url: str | None,
    ) -> list[dict] | None:
        """Return one row per variant, or None if this isn't a variant product."""
        select = soup.find("select", class_=re.compile(r"\bform-select\b"))
        if select is None:
            return None
        name_attr = _as_str(select.get("name")) or ""
        attr_match = re.search(r"attribute\[(\d+)\]", name_attr)
        if not attr_match:
            return None
        attribute_id = attr_match.group(1)

        product_id = self._extract_product_id(soup)
        if product_id is None:
            self.log.warning("variant_product_id_missing", url=product_url)
            return None

        options: list[tuple[str, str]] = []
        for opt in select.find_all("option"):
            value = _as_str(opt.get("value")) or ""
            label = opt.get_text(strip=True)
            if not value or label.lower() in ("", "see options", "choose options"):
                continue
            options.append((value, label))
        if not options:
            return None

        rows: list[dict] = []
        for value, label in options:
            price, stock = self._fetch_variant_attrs(
                product_id=product_id,
                attribute_id=attribute_id,
                value_id=value,
                product_url=product_url,
            )
            rows.append(
                {
                    "source": self.source,
                    "source_url": source_url,
                    "product_url": product_url,
                    "category": category,
                    "product_name": product_name,
                    "img_url": img_url,
                    "description": description,
                    "price": price,
                    "size": label,
                    "stock": stock,
                    "quantity": _extract_quantity(label),
                }
            )
        return rows

    @staticmethod
    def _extract_product_id(soup: BeautifulSoup) -> str | None:
        # Hidden input on the add-to-cart form is the most reliable source.
        hidden = soup.find("input", attrs={"name": "product_id"})
        if hidden is not None:
            val = _as_str(hidden.get("value"))
            if val and val.isdigit():
                return val
        # Form action sometimes encodes it: /cart.php?action=add&product_id=123
        form = soup.find("form", attrs={"data-cart-item-add": True})
        if form is not None:
            action = _as_str(form.get("action")) or ""
            m = re.search(r"product_id=(\d+)", action)
            if m:
                return m.group(1)
        # Last resort — JSON-LD productID.
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            graph = data.get("@graph", [data])
            for item in graph:
                pid = item.get("productID") or item.get("sku")
                if isinstance(pid, str) and pid.isdigit():
                    return pid
        return None

    def _fetch_variant_attrs(
        self,
        *,
        product_id: str,
        attribute_id: str,
        value_id: str,
        product_url: str,
    ) -> tuple[float | None, int | None]:
        """Call BigCommerce's product-attributes endpoint for one variant."""
        if self._client is None:
            raise RuntimeError("Scraper used outside of `with` block")

        origin = f"{urlparse(product_url).scheme}://{urlparse(product_url).netloc}"
        endpoint = f"{origin}/remote/v1/product-attributes/{product_id}"
        body = {
            "action": "add",
            "product_id": product_id,
            f"attribute[{attribute_id}]": value_id,
        }
        try:
            response = self._client.post(
                endpoint,
                data=body,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": product_url,
                },
            )
            response.raise_for_status()
        except Exception as e:  # noqa: BLE001
            self.log.warning(
                "variant_attrs_fetch_failed",
                product_id=product_id,
                value_id=value_id,
                error=str(e),
            )
            return None, None

        try:
            payload = response.json()
        except json.JSONDecodeError:
            self.log.warning(
                "variant_attrs_bad_json", product_id=product_id, value_id=value_id
            )
            return None, None

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return None, None

        price = None
        price_block = data.get("price")
        if isinstance(price_block, dict):
            with_tax = price_block.get("with_tax")
            if isinstance(with_tax, dict):
                raw = with_tax.get("value")
                if isinstance(raw, (int, float)):
                    price = float(raw)
                elif isinstance(raw, str):
                    price = _price_from_text(raw)

        stock: int | None = None
        raw_stock = data.get("stock")
        if isinstance(raw_stock, (int, float)):
            stock = int(raw_stock)
        else:
            instock = data.get("instock")
            if instock is True:
                stock = 100  # BC default — quickcrop hides exact counts
            elif instock is False:
                stock = 0

        return price, stock


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _as_str(v) -> str | None:
    """BeautifulSoup attribute getters return list|str|None — normalise."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v:
        first = v[0]
        return first if isinstance(first, str) else None
    return None


def _price_from_text(text: str) -> float | None:
    cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    parts = cleaned.rsplit(".", 1)
    if len(parts) == 2 and len(parts[1]) <= 2:
        cleaned = parts[0].replace(".", "") + "." + parts[1]
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _extract_quantity(text: str) -> int:
    """Detect multibuy phrases like '3 x Trees', '5 Pack', '6 Plant'."""
    for pat in _MULTIBUY_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                pass
    return 1


# ---------------------------------------------------------------------------
# Backward-compat shim — load_bronze_data.py calls get_product_data()
# ---------------------------------------------------------------------------


def _slug_to_label(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    return slug.replace("-", " ").title() if slug else ""


def get_product_data() -> list[dict]:
    with QuickcropScraper() as scraper:
        return scraper.run()
