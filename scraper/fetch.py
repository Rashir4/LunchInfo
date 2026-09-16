"""Polite HTTP layer: browser-like UA, pooling, timeouts, retries, size cap.

Retry policy: connection errors and 5xx responses are transient and retried
with exponential backoff; 4xx responses are permanent and fail immediately.
"""

from __future__ import annotations

import io
import time

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
    "(lunchmeny-aggregator; personal use)"
)

TIMEOUT = 20  # seconds
RETRIES = 3
BACKOFF = 2.0  # seconds, doubled per retry
MAX_BYTES = 10 * 1024 * 1024  # refuse to buffer more than 10 MB

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "sv,en;q=0.8"})
for _scheme in ("http://", "https://"):
    _session.mount(_scheme, requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16))


class FetchError(Exception):
    """A URL could not be fetched (after retries, where retrying makes sense)."""


def _read_capped(resp: requests.Response) -> bytes:
    """Read a streamed body, refusing anything over the cap.

    Always closes the response when rejecting: an unclosed streamed response is
    never returned to the pool, so each rejection would cost a fresh connection.
    """
    declared = resp.headers.get("Content-Length", "")
    # A duplicated header arrives joined ("15, 15"), so parse defensively.
    if declared.strip().isdigit() and int(declared) > MAX_BYTES:
        resp.close()
        raise FetchError(f"response too large: {declared} bytes")
    body = b""
    try:
        for chunk in resp.iter_content(chunk_size=65536):
            body += chunk
            if len(body) > MAX_BYTES:
                raise FetchError("response exceeded size cap while streaming")
    except FetchError:
        resp.close()
        raise
    return body


def _request(method: str, url: str, **kwargs) -> requests.Response:
    last_err: Exception | None = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(BACKOFF * (2 ** (attempt - 1)))
        try:
            resp = _session.request(method, url, timeout=TIMEOUT, stream=True, **kwargs)
        except requests.RequestException as exc:
            last_err = exc
            continue
        if resp.status_code >= 500:
            last_err = FetchError(f"HTTP {resp.status_code}")
            resp.close()
            continue
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code} for {url}")
        resp._content = _read_capped(resp)  # make .text/.content work after streaming
        return resp
    raise FetchError(f"failed to fetch {url} after {RETRIES} attempts: {last_err}")


def fetch_html(url: str) -> str:
    """Fetch a page and return its decoded text.

    An explicit charset in the Content-Type header is trusted; when the header
    omits one, requests would default to latin-1, so we sniff instead (modern
    Swedish sites are UTF-8).
    """
    resp = _request("GET", url)
    if "charset=" not in resp.headers.get("Content-Type", "").lower():
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def fetch_bytes(url: str) -> bytes:
    """Fetch a binary resource (e.g. a PDF menu)."""
    return _request("GET", url).content


def post_json(url: str, payload: dict) -> str:
    """POST a JSON body (e.g. a GraphQL query) and return the response text."""
    return _request("POST", url, json=payload).text


def fetch_pdf_text(url: str) -> str:
    """Fetch a PDF and return its extracted text, page texts joined by newlines."""
    import pdfplumber  # slow import, only needed by PDF-based parsers

    with pdfplumber.open(io.BytesIO(fetch_bytes(url))) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    if not text.strip():
        raise FetchError(f"no extractable text in PDF at {url}")
    return text
