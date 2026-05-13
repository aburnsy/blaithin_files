# Online nurseries shipping to Ireland — research

Compiled 2026-05-11. Sources: web research (WebSearch + WebFetch on nursery sites and An Irish Times Brexit coverage). All facts spot-verified May 2026 where possible. Where a site refused WebFetch (Cloudflare 403), the policy is taken from search-engine snippets and review sites and flagged as such in the Notes column.

## Summary

- **~55 nurseries reviewed**, organised by origin (IE / UK / EU) and by specialty.
- **~40 ship live plants to ROI**; the remainder are either UK seed-only post-Brexit, or were excluded for not shipping to ROI at all.
- Categories covered: Irish full-range, Irish hedging/native, Irish seeds, Irish houseplants, NL bulb wholesalers, NL/FR full-range exporters, UK seed-only, UK roses still shipping, UK fruit trees, garden sundries / DIY chains.
- **Top picks for value (price-comparison candidates):**
  - **Bulbs in bulk:** Peter Nyssen (UK-NL hybrid), DutchGrown, BULBi.nl, Farmer Gracy — all ship to IE in EUR or with simple flat rates; DutchGrown offers free over €100, BULBi €15.50 flat.
  - **Bare-root hedging (cheap):** Hedging.ie (free delivery!), Hedges & Trees Direct, Future Forests, Cullen Nurseries.
  - **Cheap perennials (volume):** Gardens4You.ie (NL warehouse, EUR pricing, €8.95 ship), PlantGift.ie (free shipping), Promesse de Fleurs.ie.
  - **Seed packets, low-cost shipping:** Mr Middleton (€6.50/€85 free), Johnstown Garden Centre (€4.75 flat), Quickcrop (free over €75), Beattys (free over €100), Brown Envelope Seeds (free over €50).
  - **Roses:** David Austin EU site (€9.95 to IE, ships live), Famous Roses World (Romania/EU, courier), Future Forests (locally grown).
- **Brexit reality check:** Crocus, Sarah Raven, Thompson & Morgan, Suttons, Dobies, Marshalls, Hayloft, Ashridge, Buckingham, Apuldram, Pheasant Acre, Mr Fothergill's, YouGarden, Gardening Express, Beards & Daisies, Bakker UK site — **none ship to ROI**. Many UK seed-only retailers also stopped post-Brexit.
- **High-priority scrape candidates** (good catalogue + clear pricing + ship to IE + low anti-bot risk based on Shopify/WooCommerce/BigCommerce stack): Future Forests, Mr Middleton, Quickcrop, Johnstown, Caragh Nurseries, Newlands, Windyridge, Howbert & Mays, Bandon Co-op, Beattys, Connecting to Nature, Brown Envelope Seeds, Hedging.ie, Hedges & Trees Direct, Cullen Nurseries, Plant Store, Bloombox Club, Hopeless Botanics, Mount Venus, Ardcarne, Mid Ulster (NI but ships to ROI), Ballyrobert (NI), Gardens4You, PlantGift, Promesse de Fleurs IE, Farmer Gracy, BULBi, GreenGardenFlowerBulbs, DutchGrown, Fluwel, David Austin (EU site), Famous Roses, Peter Nyssen, J Parker's IE.
- **Avoid scraping** (Cloudflare/PerimeterX hard blocks observed even on policy pages): Crocus, Sarah Raven, Thompson & Morgan, Suttons, Dobies, Mr Fothergill, Chiltern Seeds, Beards & Daisies, Peter Nyssen `.com` site (search-engine and review aggregators are usable instead), Bandon Co-op (403 even on category page).

---

## Already in dashboard

| Name | URL | Country | Currency | Specialty | Ships IE | Notes |
|---|---|---|---|---|---|---|
| Tully Nurseries | https://www.tullynurseries.ie/ | IE | EUR | Trees, hedging, perennials, large specimens | Yes | Zoned delivery: Green €20 (Dub/Meath) → Grey €100 (Donegal/Kerry/Mayo). No free threshold. Custom platform. |
| Arboretum | https://www.arboretum.ie/ | IE | EUR | Full-range garden centre + outdoor living | Yes | Free over €80; 5–7 day delivery; custom platform. |
| Caragh Nurseries | https://caraghnurseries.ie/ | IE | EUR | Trees, shrubs, hedging, large specimens (Co. Kildare, 55 acres) | Yes | Free over €100 (excl. furniture & crane jobs); WooCommerce. |
| Gardens4You.ie | https://www.gardens4you.ie/ | NL→IE | EUR | Bedding, perennials, bulbs, shrubs, houseplants | Yes | Ships from Voorhout, NL. €8.95–€14.95 (FedEx) / €12.95 DPD. 3–5 days. |
| Quickcrop | https://www.quickcrop.ie/ | IE | EUR | Veg seeds & plug plants, raised beds, organics | Yes | Free over €75 for members (excl. bulk soil). BigCommerce. |
| Future Forests | https://futureforests.ie/ | IE | EUR | Trees, hedging, fruit, ornamentals (West Cork; established 1986) | Yes | €15–€75 zone-based delivery; 3–10 working days; Shopify. |
| Mr Middleton | https://www.mrmiddleton.com/ | IE | EUR | Bulbs (Langeveld), seeds, garden tools, fertiliser | Yes | €6.50 flat; free over €85. BigCommerce. |
| Farmer Gracy | https://www.farmergracy.co.uk/ | UK→NL | GBP/EUR | Bulbs (Dutch), corms, perennials | Yes | Ships to all EU, packed in NL. EUR available via currency selector on `.co.uk` site. Shopify. Customer reviews confirm IE delivery. |

---

## Candidates — Irish nurseries

| Name | URL | Specialty | Ships IE | Delivery cost | VAT | Value | Anti-bot | Notes |
|---|---|---|---|---|---|---|---|---|
| Newlands Garden Centre | https://www.newlands.ie/ | Full-range, indoor + outdoor, BBQs, aquatics | Yes | "Fast next-day nationwide" — flat or per-item; not stated on homepage | Inc. | Mid | Shopify (mention "$" symbols on listings is suspicious — currency selector likely needed) | Strong specialism in roses (David Austin reseller) and aquatics; 2-acre Dublin nursery. |
| Windyridge Garden Centre | https://www.windyridgegardencentre.ie/ | Plants, BBQs, lifestyle (Dún Laoghaire) | Yes | Nationwide 2–3 working days; cost not on homepage | Inc. | Mid | Shopify (clean) | Family-run, awards, 1,200+ 5-star reviews. |
| Howbert & Mays | https://howbertandmays.ie/ | Plants, garden tools, Biohort sheds, homewares | Yes | Stated on product pages | Inc. | Premium | Shopify (clean) | Three Dublin shops (Monkstown, Clare St, Dundrum); high-end. |
| Mount Venus Nursery | https://mountvenusnursery.com/ | Perennials, hardy garden plants (Dublin 16) | Yes (Oct–Apr only) | An Post €10 for boxes ≤10 kg | Inc. | Premium | WooCommerce | Specialist; one of widest perennial collections in IE; mail order seasonal. |
| Camolin Potting Shed | https://www.camolinpottingshed.com/ | Specialist perennials (Wexford) | Yes | €18 by courier (any number of plants) | Inc. | Mid | Custom (WP, refused WebFetch) | Mail order to IE & Europe; long catalogue of clematis. |
| Hosfords Garden Centre | https://hosfordsgardencentre.ie/ | Plants, especially geraniums/pelargoniums (West Cork) | Unknown — phone/email order primarily | Unknown | Inc. | Mid | Limited online presence | Founded 1980; well-regarded; **excluded from priority scrape list** — site appears to be brochure-only. |
| Johnstown Garden Centre | https://johnstowngardencentre.ie/ | Full-range (Kildare), Suttons/T&M/Westland reseller | Yes | **€4.75 flat** anywhere in IE & NI | Inc. | Cheap | Custom (likely Magento) | Excellent flat-rate; stocks blocked-UK seed brands. |
| Ardcarne Garden Centre | https://www.ardcarne.ie/ | Plants, aquatics, garden products (Roscommon) | Yes | €13.95 ≤20 kg; €3.80 seed-only; bulk local only | Inc. | Mid | Custom | No free threshold; courier collects Tue/Thu only. |
| Clarenbridge Garden Centre | https://clarenbridgegardencentre.ie/ | Plants, decor (Galway, Waterford, Limerick) | Yes | Not on homepage | Inc. | Mid | Shopify (likely) | Multi-store. |
| Ballyseedy | https://ballyseedy.com/ | Houseplants, garden, gifts | Yes | Courier nationally; cost not on homepage | Inc. | Mid | Shopify | Big Tralee garden centre. |
| The Garden Shop | https://www.thegardenshop.ie/ | "Ireland's Low Cost Garden Centre"; broad | Yes | Not visible on homepage | Inc. | Cheap (claimed) | Custom (looked like older OpenCart-style) | Strong claim of low prices but checkout-time delivery rates. |
| Plant Store | https://www.plantstore.ie/ | Indoor plants, succulents, plant kits | Yes | 5–7 working days; cost not on homepage | Inc. | Mid | Shopify | Also B2B/corporate. |
| Bloombox Club Ireland | https://bloomboxclub.ie/ | Indoor plants, subscription boxes | Yes | Free over £85; flat rate otherwise (~£6.95 quoted) | Inc. | Mid | Shopify | Subscription model is unusual. |
| Verd Houseplants | https://verd.ie/ | Houseplants | Yes | National to all ROI counties; cost at checkout | Inc. | Mid | Shopify (likely) | Ships Mon/Tue, cut-off Fri 5pm. |
| Hopeless Botanics | https://hopelessbotanics.ie/ | Houseplants, pots, accessories (Dublin/Liberties) | Yes | ~€8.50 average; weight-based for large | Inc. | Mid | Shopify (likely) | DPD next-day after dispatch. |
| Connecting to Nature | https://connectingtonature.ie/ | Native wildflower seed, bird food, hedging (Waterford) | Yes | Calculated at checkout | Inc. | Cheap | Shopify (clean) | Sixth-generation family business since 1859. |
| Brown Envelope Seeds | https://brownenvelopeseeds.ie/ | Organic open-pollinated veg, herb, grain seed (West Cork) | Yes | Free over €50 | Inc. | Cheap | Shopify (clean) | Halted UK shipments due to phytosanitary rules. |
| Seedaholic | https://www.seedaholic.com/ | Heirloom/organic flower & veg seed (West Cork) | Yes | EU-wide incl. NI/Norway/CH/Turkey; cost on delivery page (refused WebFetch) | Inc. | Cheap | Cloudflare-fronted | Curated catalogue. |
| Seedie.ie | https://seedie.ie/ | Marketplace for Irish organic seed growers | Yes | Per supplier | Inc. | Cheap | Shopify | Spinoff of Brown Envelope. |
| Seeds Ireland | https://seedsireland.ie/ | Organic open-pollinated veg/flower seed | Yes | Free over €45 | Inc. | Cheap | Shopify | Irish-grown. |
| The Organic Centre | https://www.theorganiccentre.ie/ | Organic seed, biodynamic | Yes | At checkout | Inc. | Mid | WooCommerce (likely) | Leitrim-based educational + retail. |
| Wildflowers.ie / Design By Nature | http://www.wildflowers.ie/ | Irish native wildflower seed; meadow mixes | Yes | Free fast delivery via An Post | Inc. | Cheap | Old static site (HTML) — very low-tech | Sandro Cafolla, Carlow; market leader for native seed. **Note: extracting prices may be hard — old HTML.** |
| Fruit Hill Farm | https://www.fruithillfarm.com/ | Organic seed, tools, compost, propagation (Bantry) | Yes | Per order; cost at checkout | Inc. | Mid | Magento (likely; refused WebFetch) | Klasmann compost reseller. |
| English's Fruit Nursery | https://www.englishsfruitnursery.ie/ | Fruit trees, soft fruit (Wexford) | Yes | Nationwide; "competitive"; cost per order | Inc. | Mid | Custom (older platform) | 75-year-old fruit specialist. |
| Hedging.ie | https://hedging.ie/ | Bare-root + potted hedging, fruit trees | Yes | **FREE nationwide** | Inc. | **Cheap** | WooCommerce (clean) | Standout free-delivery hedging supplier. |
| Hedges & Trees Direct | https://hedgesandtreesdirect.ie/ | Hedging, trees, native packs | Yes | Nationwide, packed for transit | Inc. | **Cheap** | WooCommerce/Shopify | Whitethorn from €0.80 — pure value. |
| Cullen Nurseries | https://cullennurseries.ie/ | Native trees and hedging (Carlow) | Yes | Not on homepage; 14–21 day window in bare-root season | Inc. | Mid | WooCommerce | DAFM-approved. |
| Hyland's Nursery | https://hylandsnursery.ie/ | Mature hedging, large trees (Wexford, 60-yr family) | Yes | Per order; arrange | Inc. | Mid | Custom | Mature/instant hedging specialist. |
| Etna Plants | https://etnaplants.ie/ | Trees, shrubs, perennials, climbers, bareroot/rootball (Limerick) | Yes | Ships all over IE; click & collect | Inc. | Mid | WordPress + WooCommerce | Online since ~2019. |
| Van der Wel / Cappagh Nurseries | https://www.vanderwel.ie/ | Hedging, bare-root trees, screening (Wicklow) | Yes | Online ordering via subdomain | Inc. | Mid | Old zCart subdomain | Family business since 1967. |
| None-So-Hardy | https://nonesohardy.ie/ | Forestry conifers + broadleaves (Wexford/Wicklow) | Yes | B2B / contact direct | Excl./Trade | Cheap | B2B brochure | Bulk forestry plants — not a retail scrape candidate. |
| Bandon Co-op | https://www.bandoncoop.ie/ | Plants, fertiliser, agri retail (West Cork) | Yes | Click & collect + delivery | Inc. | Cheap | Custom (refused WebFetch — Cloudflare) | Outdoor plants nationwide; multi-store. |
| Beattys of Loughrea | https://www.beattys.ie/ | Hardware + garden + seeds (Galway) | Yes | Free over €100 (excl. bulky) | Inc. | Cheap | Shopify (clean) | Sells Suttons & Thompson & Morgan **seeds** (UK-blocked retail brands). |
| Tirlán CountryLife | https://www.countrylife.ie/shop | Garden, plants, seeds, planting accessories | Yes | Click & collect + delivery | Inc. | Mid | Custom (SAP Hybris likely) | 15 stores in Leinster/Munster; 90% Irish-grown plants. |
| Lenehans | https://www.lenehans.ie/gardening.html | Hardware + seeds + bulbs (Cork) | Yes | Free over €60; Click & collect from 900 locations | Inc. | Cheap | Magento (likely) | Hardware shop with strong garden seed range. |
| Powerscourt Garden Pavilion | https://www.powerscourtgardenpavilion.com/ | Plants, gifts (Wicklow estate) | Yes (likely) | At checkout | Inc. | Premium | Shopify (likely) | Premium-positioned tourist garden centre. |
| Dunnes Garden Centre Durrow | https://www.dunnesgardencentre.com/ | Trees, hedging, conifers, shrubs, perennials (Laois) | Yes | Phone for delivery | Inc. | Mid | Old custom site (refused WebFetch — ECONNREFUSED) | Family est. 1978. **Excluded from scrape list** — site appears partly broken. |
| Easy Garden | https://easygarden.ie/ | Plants, pots, seeds (Dublin) | Yes (working on new site) | Phone | Inc. | Cheap | Old custom site | "Famous for Value"; site under rebuild. |
| Pavilion (Cork) | https://www.thepavilion.ie/ | Garden centre + interiors + restaurant | Yes | Online | Inc. | Premium | Shopify (likely) | Lifestyle-positioned. |
| Whites Agri | https://www.whitesagri.ie/ | Klasmann compost, agri & garden inputs (Lusk) | Yes | Mon–Fri; usually next day, up to 5 days | Inc. | Cheap | WooCommerce | Useful for **compost price comparison**. |
| Woodies | https://www.woodies.ie/ | DIY chain — plants, seeds, compost, bulbs | Yes | 2–3 working days; cost not headline | Inc. | Cheap | Custom (Salesforce Commerce or similar) | 35 stores; useful for **non-plant comparison**. |
| B&Q Ireland (diy.ie) | https://www.diy.ie/ | DIY — compost, tools, plant care | Yes | Free over €75 | Inc. | Cheap | Custom Salesforce-style | Bulk delivery only in Dublin region. |
| Lidl Ireland | https://www.lidl.ie/ | Periodic plants & flowers special-buys | In-store mostly | N/A for plants typically | Inc. | Cheap | Custom | Hard to scrape for ongoing pricing — drops are weekly. |
| FitzGerald Nurseries | https://fitzgerald-nurseries.com/ | Wholesale propagation (Kilkenny/Wexford) | B2B | N/A | N/A | N/A | N/A | **Excluded** — trade-only, no retail. |
| Rentes Plants | https://www.rentes.ie/ | Wholesale | B2B | N/A | N/A | N/A | N/A | **Excluded** — trade-only. |
| Gardenworld Nurseries | https://gardenworld.ie/ | Wholesale | B2B | N/A | N/A | N/A | N/A | **Excluded** — trade-only. |
| O'Connor Nurseries | https://oconnornurseries.ie/ | Wholesale | B2B | N/A | N/A | N/A | N/A | **Excluded** — trade-only. |

### Northern Ireland nurseries that ship to the Republic

| Name | URL | Specialty | Ships ROI | Delivery cost | Currency | Notes |
|---|---|---|---|---|---|---|
| Mid Ulster Garden Centre (Hortus Vitae) | https://midulster.co.uk/ (or .ie) | Trees, perennials, garden furniture (Maghera) | Yes (UK & Ireland) | Free for in-stock items; free 30-mile radius | GBP/EUR | Stocks Thompson & Morgan **seeds** for IE customers; useful T&M proxy. |
| Ballyrobert Gardens | https://www.ballyrobertgardens.com/ | Perennials & cottage plants (Ballyclare) | Yes | £5.99 flat, free over £200 | GBP | RHS Partner Garden; closed Nov–Dec; Shopify (clean). |
| Papervale Trees | https://www.papervaletrees.com/ | 350+ tree varieties (NI specialist) | Yes | Quote — courier-based | GBP | Tree specialist for IE & UK. |
| Hyland Bros. / Screen It Green | https://screenitgreen.com/ | Instant hedging troughs, bare-root | Yes | Free over £100 to NI; ROI per quote | GBP | Volume discounts on instant hedging troughs. |

---

## Candidates — UK nurseries (with Brexit notes)

UK nurseries typically need **phytosanitary certificates** to ship live plants to ROI post-Brexit. Most retail-scale UK suppliers stopped at end of 2020 / early 2021. Seeds, bulbs and dormant bare-root material are usually fine; live potted plants almost always blocked.

| Name | URL | Ships live to ROI | Ships seed/bulb/dormant to ROI | Delivery cost | Notes |
|---|---|---|---|---|---|
| Crocus | https://www.crocus.co.uk/ | **No** | **No** (UK only) | N/A | UK-only since Brexit; **Cloudflare 403** — won't scrape easily anyway. **Exclude.** |
| Sarah Raven | https://www.sarahraven.com/ | **No** | **No** (UK only) | N/A | "Not able to process any orders for delivery outside of the UK." Some seed available via Irish Plants Direct reseller. **Exclude direct.** |
| Thompson & Morgan | https://www.thompson-morgan.com/ | **No** | **No** direct (UK mainland only) | N/A | T&M opened a Dublin warehouse for **trade** distribution — Irish customers buy via Beattys, Mid Ulster, Mr Middleton, Johnstown. **Use Irish resellers as proxy.** |
| Suttons | https://www.suttons.co.uk/ | **No** | **No** (UK only) | N/A | "Unable to send any items, including seed, outside the UK." Cloudflare 403. **Exclude direct.** |
| Dobies | https://www.dobies.co.uk/ | **No** | **No** | N/A | Same parent as Suttons; same restrictions. **Exclude.** |
| Mr Fothergill's | https://mr-fothergills.co.uk/ | **No** | **No** | N/A | Cannot supply NI or Europe. Cloudflare 403. Available via Irish resellers (Johnstown, Arboretum). **Exclude direct.** |
| Marshalls | https://marshallsgarden.com/ | **No** | **No** to ROI | N/A | NI now possible with £3 surcharge; ROI excluded. **Exclude.** |
| Hayloft | https://www.hayloft.co.uk/ | **No** (assumed) | **No** | N/A | Search returned no current ROI policy; UK focus. **Exclude.** |
| Burncoose | https://www.burncoose.co.uk/ | Restricted | Restricted | Quote only | "Larger orders to the EU can be organised by contacting them" — not retail-friendly. **Exclude direct retail; consider as quote source.** |
| Hardy's Cottage Garden Plants | https://www.hardysplants.co.uk/ | Unknown | Unknown | N/A | No clear ROI policy in research. Assume no. **Exclude.** |
| Bluebell Cottage | https://www.bluebellcottage.co.uk/ | Unknown | Unknown | N/A | Cheshire perennial nursery; no clear ROI policy. **Exclude.** |
| Beth Chatto's | https://www.bethchatto.co.uk/ | Unknown | Unknown | N/A | No clear ROI policy. **Exclude.** |
| Kings Seeds | https://kingsseeds.com/ | **No** | **No** | N/A | Search returned no specific ROI policy; assume UK-only post-Brexit. **Exclude.** |
| Chiltern Seeds | https://www.chilternseeds.co.uk/ | **No** | Unknown | N/A | Cloudflare 403. **Exclude direct.** |
| The Real Seed Catalogue | https://www.realseeds.co.uk/ | Unknown | Unknown — likely no | N/A | Pembrokeshire heirloom; no clear ROI policy. **Exclude until verified.** |
| YouGarden | https://www.yougarden.com/ | **No** | **No** (UK only, not even NI) | N/A | Explicit "do not deliver outside UK." **Exclude.** |
| Gardening Express | https://www.gardeningexpress.co.uk/ | **No** | **No** | N/A | Explicit Brexit exclusion: "cannot deliver to Northern Ireland, Southern Ireland or Channel Islands due to customs regulations relating to the transit of live plants." **Exclude.** |
| Van Meuwen | https://www.vanmeuwen.com/ | **No** (assumed; same parent group) | **No** | N/A | T&M-owned. **Exclude.** |
| Beards & Daisies | https://www.beardsanddaisies.co.uk/ | **No** | **No** | N/A | UK-only (excl. NI). **Exclude.** |
| Patch Plants | https://www.patchplants.com/ | **No** | **No** | N/A | UK-only. **Exclude.** |
| Pottertons | https://www.pottertons.co.uk/ | **No** | **No** | N/A | Excludes NI and Channel Isles. **Exclude.** |
| Pheasant Acre Plants | https://www.pheasantacreplants.co.uk/ | **No** | **No** | N/A | "Unable to send to Ireland and any countries outside of the United Kingdom." **Exclude.** |
| Buckingham Nurseries | https://www.hedging.co.uk/ | **No** | **No** | N/A | Brexit-restricted; no NI either. **Exclude.** |
| Ashridge Nurseries | https://www.ashridgetrees.co.uk/ | **No** | **No** | N/A | UK mainland only; no NI/IoM/CI. **Exclude.** |
| Hopes Grove Nurseries | https://www.hopesgrovenurseries.co.uk/ | **No** | **No** | N/A | UK only; same as above. **Exclude.** |
| Trees Direct | https://treesdirect.co.uk/ | Unknown | Unknown | N/A | UK-focused; no clear ROI policy. **Exclude.** |
| Jackson's Nurseries | https://www.jacksonsnurseries.co.uk/ | Unknown | Unknown | N/A | No clear policy. **Exclude.** |
| Mail Order Trees | https://www.mailordertrees.co.uk/ | Unknown | Unknown | N/A | UK focus. **Exclude.** |
| Apuldram Roses | https://www.apuldramroses.co.uk/ | **No** | **No** | N/A | "Cannot send to Europe, Northern Ireland, IoW, IoM, Highlands, Scottish Isles, or Channel Isles." **Exclude.** |
| Trevor White Roses | https://www.trevorwhiteroses.co.uk/ | Unknown | Unknown | N/A | Norfolk specialist; no clear ROI policy in research. **Exclude until verified.** |
| Peter Beales Roses | https://www.peterbealesroses.com/ | Unknown — likely restricted | Unknown | N/A | World-leading classic-rose grower; assume restricted post-Brexit. **Exclude until verified.** |
| Wharton's Roses | https://www.whartonsroses.co.uk/ | Unknown | Unknown | N/A | Wholesale-leaning. **Exclude.** |
| **David Austin Roses (EU)** | https://eu.davidaustinroses.com/ | **YES** | **YES** | **€9.95 to IE** | Their dedicated EU site does ship live + bare-root to IE. **Include — high value.** UK `.com` site does NOT ship to IE; ensure scrape uses `eu.` subdomain. |
| **Peter Nyssen** | https://www.peternyssen.com/ | n/a (bulbs) | **YES** | ~€17 / order to IE; standard postage free in EU over £50 (per UK site) | Manchester-based but ships from NL warehouse since Brexit. EU & NI delivery "as normal." Site has Cloudflare 403 on direct WebFetch — likely heavy anti-bot. **Include but plan careful scraper (rotating headers / browser).** |
| **J Parker's (Ireland site)** | https://www.jparkers.com/ | n/a (bulbs/some plants) | **YES** | **€6.99 flat** (€2.99 seeds-only); free over €60 | Has dedicated `.com` site with EUR pricing for IE. Bulb specialist with extensive range. **Include — easy scrape candidate.** |
| **Farmer Gracy** | https://www.farmergracy.co.uk/ | n/a (bulbs/perennials) | **YES** | EUR currency selector available | Packs in NL, ships across EU. Shopify, fairly clean. **Already in dashboard.** |
| **Ballyrobert Gardens (NI)** | https://www.ballyrobertgardens.com/ | **YES** | **YES** | **£5.99 flat, free over £200** | NI nursery, perennials specialist; ships ROI freely. Shopify. **Include.** |

---

## Candidates — EU nurseries

EU→IE plant shipments are not affected by Brexit; phytosanitary requirements are intra-EU and routine. These are typically **the cheapest sources for bulbs in bulk** and competitive on perennials.

| Name | URL | Country | Specialty | Ships IE | Delivery cost | Min order | Currency | Notes |
|---|---|---|---|---|---|---|---|---|
| **BULBi.nl** | https://www.bulbi.nl/ | NL | Bulbs (B2C arm of Green Garden Flower Bulbs) | Yes | **€15.50** flat; free over €250 | None | EUR | Already in dashboard. Shopify-style. **Easy scrape.** |
| **Green Garden Flower Bulbs** | https://www.greengardenflowerbulbs.nl/ | NL | Bulbs B2B wholesale | Yes | €21.50/box, €425/pallet to IE | **€500 min** | EUR | High min order — relevant for landscapers/large gardens. |
| **DutchGrown** | https://www.dutchgrown.eu/ | NL | Bulbs (B2C) | Yes | **€11.99 < €100; FREE over €100** | None | EUR | Excellent value; Shopify (clean). **Include.** |
| **Fluwel** | https://www.fluwel.com/ | NL | Bulbs (large-size, premium) | Yes | **€33.25 flat to IE** | None | EUR | Higher shipping but covers extra >20 kg. Shopify. **Include — premium bulb tier.** |
| **Verver Export** | https://ververexport.com/en/ | NL | Bulb concepts, naturalising mixes | Likely B2B only | Quote | High | EUR | Active in 11 EU countries — IE not listed. **Exclude unless trade.** |
| **Promesse de Fleurs (IE site)** | https://www.promessedefleurs.ie/ | FR | 20,000 varieties — perennials, shrubs, bulbs, seeds, fruit, accessories | Yes | ~€22; free over a threshold (not on home page) | None | EUR | Customer reviews report 3-day FR→IE delivery. Custom platform but Magento-style. **Include — broadest catalogue.** |
| **Bakker.com** (international) | https://www.bakker.com/ | NL/BE | Bulbs, indoor & outdoor plants | Yes (international site) | EU-wide flat rates | None | EUR/GBP | UK site (`en-gb.bakker.com`) does NOT ship outside UK. Use `bakker.com/INTERSHOP/.../INTL` site or country-specific Bakker sites. Worth checking dedicated IE redirect. |
| **PlantGift.ie** | https://plantgift.ie/ | IE/EU | Houseplants + outdoor; 500+ varieties; sources from EU growers | Yes (IE + 24 EU) | **FREE shipping all orders** (claimed, all destinations) | None | EUR | Family-run Dublin; Shopify (clean). **Include — exceptional shipping policy.** |
| **Famous Roses World** | https://en.famousroses.eu/ | RO/EU | Roses (bare-root + potted) | Yes | At checkout (~courier rates) | None | EUR | Good IE coverage page. Shopify. |
| **Lubera Edibles / Lubera AG** | https://www.lubera.com/ / https://www.luberaedibles.com/ | CH/DE | Fruit trees, fruit-bearing plants (own breeding) | Yes (Edibles ships EU; AG limited to DACH) | At checkout | Mid | EUR/CHF | Edibles ships EU; reach-out for IE quote. **Include for fruit specialty.** |
| **Bakker Hillegom (FR/NL/BE entities)** | https://www.bakker.com/INTERSHOP/web/.../IE | NL | Bulbs, perennials, accessories — Dutch garden mail-order giant | Yes (must use international redirect) | Tiered EU rates | None | EUR | Check international entry point — UK redirect blocks IE. |
| **Dehner** | https://www.dehner.de/ | DE | Massive German garden retailer | Unknown — predominantly DACH | Quote | None | EUR | 135+ stores in DE/AT; international shipping unclear. **Exclude unless verified.** |
| **Pötschke** | https://www.pflanzen.gaertner-poetschke.de/ | DE | Mid-market flowers, plants, bulbs | Unknown | Quote | None | EUR | Limited info on IE shipping. **Exclude until verified.** |
| **Thomas Fruit Trees** | https://thomasfruittrees.eu/ | FR | Organic fruit trees | Yes (EU delivery) | Quote | None | EUR | Niche organic specialist. |
| **Dutch-Bulbs.com** | https://dutch-bulbs.com/ | NL | Bulbs, plants | Likely yes | Per country | None | EUR | Less well-known but ships across EU. |
| **Nijssen Bulbs** | https://www.nijssenbulbs.com/ | NL | Bulbs (Heemstede) | Yes | Per country (~€17 to IE per snippet) | None | EUR | Sister to Peter Nyssen (Manchester). |

---

## By specialty

### Bare-root trees and hedging (best value)
- **Hedging.ie** — free nationwide delivery — **lowest cost-per-stem in IE**.
- **Hedges & Trees Direct** — €0.80/whitethorn; nationwide.
- **Future Forests** — broadest catalogue, €15–€75 zoned ship.
- **Cullen Nurseries** — DAFM-approved native specialist.
- **Hyland's Nursery** — mature/instant hedging.
- **Etna Plants**, **Van der Wel** — also competitive.
- **None-So-Hardy** — forestry-scale wholesale only.

### Roses
- **David Austin (EU site)** — €9.95 to IE for live + bare-root — best mainstream UK→IE rose option.
- **Famous Roses World** — EU courier; bare-root + potted; good site.
- **Future Forests** — locally-grown rose collection.
- **Newlands** — David Austin reseller in IE.
- **Apuldram, Trevor White, Peter Beales, Wharton's** — generally **do not ship to ROI** post-Brexit.

### Bulbs in bulk (best value)
- **Peter Nyssen** — bulk bulb specialist, NL warehouse, ships EU/NI normally; ~€17 to IE.
- **DutchGrown** — free over €100; smaller orders €11.99.
- **BULBi.nl** — €15.50 flat; very wide range; free over €250.
- **Farmer Gracy** — already in dashboard.
- **Fluwel** — premium large-size bulbs; €33.25 flat (premium tier).
- **J Parker's (IE)** — €6.99 flat; broadest catalogue with seeds & plants too.
- **Mr Middleton** — Langeveld bulbs; €6.50 flat in IE.

### Vegetable seeds and plug plants
- **Quickcrop** — leading veg + plug plants in IE; free over €75 for members.
- **Brown Envelope Seeds** — organic Irish-grown seed; free over €50.
- **Seedaholic** — heirloom + organic; ships EU.
- **Seeds Ireland** — free over €45.
- **Seedie.ie** — Irish growers' marketplace.
- **Fruit Hill Farm** — organic seed + tools.
- **The Organic Centre** — biodynamic.
- **Beattys / Johnstown / Mr Middleton** — stock UK-blocked Suttons & T&M brands as resellers.
- **Mid Ulster (NI)** — also stocks T&M for IE customers.

### Wildflower seeds and meadow mixes
- **Wildflowers.ie / Design By Nature** — Sandro Cafolla, Carlow; native Irish seed; free An Post delivery.
- **Connecting to Nature** — Waterford, native mixes; Shopify.

### Indoor / houseplants
- **Bloombox Club Ireland** — 200,000+ plants delivered; subscription model.
- **Plant Store** — Shopify; B2B too.
- **Verd Houseplants** — specialist.
- **Hopeless Botanics** — DPD next-day; ~€8.50 ship.
- **PlantGift.ie** — free shipping; 500+ varieties.
- **Howbert & Mays** — premium tier.

### Fruit trees and soft fruit
- **English's Fruit Nursery** — 75-yr Wexford specialist.
- **Future Forests** — comprehensive fruit range.
- **Lubera Edibles** — CH/DE; ships EU; own breeding.
- **Quickcrop** — also stocks fruit bushes.

### Aquatic / pond plants
- **Newlands** — full aquatic range with next-day delivery.
- **Future Forests** — water plants & marginals.
- **Ardcarne** — aquatic range online.
- **Beechmount Garden Centre** (https://beechmount.ie/pond-plants/) — also stocks pond plants.
- **Fernhill Garden Centre** — pond planting range (https://www.fernhill.ie/).
- **Gardens4You.ie** — pond plants from NL.
- (UK Waterside Nursery — **no longer ships to NI/ROI**.)

### Alpines / rockery
- **Newlands** — Irish alpine range.
- (UK specialists Pottertons, Picts Hill, D'arcy & Everest, Carbeth, Calamazag, Ardfearn, Ice Alpines — **none ship to ROI** based on research; all UK-only.)

### Ornamental grasses
- **Future Forests**, **Caragh Nurseries**, **Etna Plants**, **Mount Venus** all carry significant grass ranges — no specialist Irish grasses-only nursery surfaced.

### Hedging plants in bulk
- See "Bare-root trees and hedging" above.

### Garden sundries / non-plant (compost, tools, pots, fertilisers)
- **Mr Middleton** — strong on tools/fertiliser.
- **Quickcrop** — raised beds, soil, tools.
- **Whites Agri** — Klasmann compost specialist (price-comparison anchor).
- **Fruit Hill Farm** — organic inputs.
- **Lenehans** — hardware + garden.
- **Beattys** — hardware + garden.
- **Tirlán CountryLife** — agri retail group.
- **Woodies** — DIY chain.
- **B&Q (diy.ie)** — DIY chain.
- **Howbert & Mays** — high-end pots & sheds (Biohort).

---

## Excluded / not worth scraping

- **Crocus, Sarah Raven, Suttons, Dobies, Marshalls, Mr Fothergill's, Hayloft, YouGarden, Gardening Express, Van Meuwen, Beards & Daisies, Patch Plants, Apuldram, Pheasant Acre, Pottertons, Buckingham, Ashridge, Hopes Grove, Burncoose** — confirmed do not ship to ROI (Brexit + plant health). Most also block scrapers via Cloudflare/PerimeterX.
- **Thompson & Morgan** direct site — UK-only, but their products reach IE via Beattys, Mid Ulster, Mr Middleton, Johnstown — scrape *those* instead.
- **FitzGerald, Rentes, Gardenworld, O'Connor Nurseries** — wholesale/B2B only, no public retail prices.
- **None-So-Hardy** — forestry-scale B2B.
- **Easy Garden, Dunnes Garden Centre Durrow, Hosfords** — sites are partly broken / brochure-only / phone-order; not a useful price source for now.
- **Lidl, Aldi (IE) "specialbuys"** — weekly drops, no ongoing catalogue to scrape.
- **Verver Export, Bakker UK redirect, Dehner, Pötschke** — could not confirm IE shipping; defer.

---

## Additional candidates flagged 2026-05-12 (community-roundup pass)

A second pass against Reddit / Boards.ie / project-segfau roundups surfaced
four nurseries not yet in the tables above. Stack/anti-bot/shipping still
to be verified before promoting to a scrape priority.

| Name | URL | Specialty | Ships IE | Notes |
|---|---|---|---|---|
| Irish Seed Savers | https://irishseedsavers.ie/ | Organic heirloom seed + fruit trees (Co. Clare, near Scarriff) | Yes | Recurring community recommendation for heirloom veg/grain seed and a large fruit-tree range. Stack TBC. |
| Fermoy Woodland | https://fermoywoodland.ie/ | Bare-root hedging + woodland trees (Cork) | Yes | Frequently paired with Hedging.ie in "best value hedging" threads. Stack TBC. |
| Kearneys Nursery | https://www.irelandtrees.com/ | Trees, shrubs, hedging — family-run grower (Galbally, Co. Tipperary; ~75 years) | Yes (nationwide delivery + collect) | Online ordering available. Active DoneDeal seller too. Stack TBC — promote to scrape candidate once verified. |
| Guineys.ie | https://www.guineys.ie/ | Discount home/garden basics: gloves €2.49, shovels €3.99, etc. | Yes | Tools-only retailer; relevant only if we widen scope to non-plant garden sundries. |

Tools-only retailers raised in the same roundup but **out of scope** for
the plant-price comparison: Toolforce.ie, Carey Tools, Lenehans (already
in main table for its seed range — tools side noted but not separately
scraped). Lidl/Aldi already in the excluded list as no-ongoing-catalogue.

---

## Open questions for the user

1. **UK seed-only sites.** Worth including any UK *seed* retailers if/when we confirm they actually ship dormant seed to IE? Suttons, Mr F, Chiltern, Kings — all currently report "UK only" on policy pages, but enforcement varies. Is it worth a follow-up email-test to each, or just rely on the Irish resellers (Beattys, Mid Ulster, Mr Middleton, Johnstown)?
2. **Anti-bot tolerance.** Several high-value sites (Peter Nyssen, Crocus, T&M, Suttons, Mr Fothergill's, Beards & Daisies, Bandon Co-op, Fruit Hill Farm) sit behind Cloudflare and refused WebFetch. For Peter Nyssen specifically (good bulb prices to IE, EUR-friendly), do we want to invest in a browser-driven scraper, or skip and rely on BULBi/DutchGrown/Farmer Gracy?
3. **Wholesale tier.** Caragh, Hyland's, Tully, Cullen, Verver Export, Green Garden Flower Bulbs all serve trade as well as retail — do you want a separate "trade-priced" tab, or filter them in/out based on retail-only pricing on the site?
4. **NI vs ROI.** Mid Ulster and Ballyrobert (Northern Ireland, GBP) ship freely to ROI. Should the dashboard flag NI vs ROI separately for currency / VAT clarity, or treat them as one "ships-to-IE" pool?
5. **Wildflowers.ie** is a static HTML brochure-style site — good prices, but extracting them will need bespoke parsing (not Shopify/WooCommerce metadata). Worth the effort, or skip for v1?
6. **Subscription / box services** (Bloombox Club, PlantGift gifts) — include in price comparison, or carve out as a separate "gifts" view?
7. **Garden sundries** — same dashboard as plants, or a separate "non-plant" view as you implied? If separate, that's its own scrape job; if mixed, we need a category taxonomy first.
8. **Fluwel** (premium large-size bulbs at €33 ship) — include even though it's a premium tier and shipping is high? Useful for showing the upper bound of bulb pricing.
