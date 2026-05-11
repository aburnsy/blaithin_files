"""Tests for the retry-aware HTTP client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.scrapers.http import RetryExhausted, build_client, fetch_html


def test_build_client_returns_httpx_client():
    client = build_client(rate_limit_seconds=0)
    assert isinstance(client, httpx.Client)
    client.close()


@patch("src.scrapers.http.httpx.Client.get")
def test_fetch_html_succeeds_first_try(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text="<html>ok</html>", raise_for_status=lambda: None)
    client = build_client(rate_limit_seconds=0)
    html = fetch_html(client, "https://example.com")
    assert html == "<html>ok</html>"
    client.close()


@patch("src.scrapers.http.httpx.Client.get")
def test_fetch_html_retries_on_500(mock_get):
    # 500, 500, 200 — should succeed on third attempt
    err_resp = MagicMock(status_code=500)
    err_resp.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=err_resp)
    ok_resp = MagicMock(status_code=200, text="<html>ok</html>", raise_for_status=lambda: None)
    mock_get.side_effect = [err_resp, err_resp, ok_resp]

    client = build_client(rate_limit_seconds=0)
    html = fetch_html(client, "https://example.com", max_attempts=3)
    assert html == "<html>ok</html>"
    assert mock_get.call_count == 3
    client.close()


@patch("src.scrapers.http.httpx.Client.get")
def test_fetch_html_gives_up_after_max(mock_get):
    err_resp = MagicMock(status_code=503)
    err_resp.raise_for_status.side_effect = httpx.HTTPStatusError("503", request=MagicMock(), response=err_resp)
    mock_get.return_value = err_resp

    client = build_client(rate_limit_seconds=0)
    with pytest.raises(RetryExhausted):
        fetch_html(client, "https://example.com", max_attempts=2)
    client.close()
