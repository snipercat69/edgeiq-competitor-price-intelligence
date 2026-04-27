#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import html
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 EdgeIQLabsPriceMonitor/1.0"
)
DEFAULT_TIMEOUT = 20
PRICE_RE = re.compile(
    r"(?P<currency>[$€£₹]|USD|EUR|GBP|CAD|AUD|JPY|INR)?\s*"
    r"(?P<amount>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+(?:[.,]\d{2}))"
)
CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
}
AVAILABILITY_PATTERNS = [
    (re.compile(r"\bin stock\b", re.I), "In Stock"),
    (re.compile(r"\bout of stock\b", re.I), "Out of Stock"),
    (re.compile(r"\bout[- ]?of[- ]?stock\b", re.I), "Out of Stock"),
    (re.compile(r"\bcurrently unavailable\b", re.I), "Unavailable"),
    (re.compile(r"\bsold out\b", re.I), "Sold Out"),
    (re.compile(r"\bavailable now\b", re.I), "Available"),
    (re.compile(r"\bpre-?order\b", re.I), "Preorder"),
]
TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
META_RE_TEMPLATE = r'<meta[^>]+(?:property|name)=["\']{name}["\'][^>]+content=["\'](.*?)["\']'
JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
SCRIPT_JSON_RE = re.compile(r"\{.*?\}", re.S)
PRICE_KEYS = {
    "price",
    "lowprice",
    "highprice",
    "saleprice",
    "currentprice",
    "pricevalue",
    "listprice",
    "offerprice",
}
TITLE_KEYS = {"name", "title", "productname"}
AVAILABILITY_KEYS = {"availability", "stockstatus", "availabilitystatus"}


@dataclass
class ProductSnapshot:
    url: str
    fetched_at: str
    title: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    availability: Optional[str]
    source_host: str
    raw_price_text: Optional[str] = None


class ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._attrs: Dict[str, str] = {}
        self.scripts: List[Tuple[Dict[str, str], str]] = []
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "script":
            self._capture = True
            self._attrs = {k.lower(): v or "" for k, v in attrs}
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capture:
            self.scripts.append((self._attrs, "".join(self._chunks)))
            self._capture = False
            self._attrs = {}
            self._chunks = []


def load_env_file(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT, user_agent: str = DEFAULT_USER_AGENT) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        data = response.read()
        return data.decode(content_type, errors="replace")


def normalize_whitespace(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_currency(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip().upper()
    return CURRENCY_SYMBOLS.get(value, value)


def parse_amount(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\xa0", " ")
    match = PRICE_RE.search(text)
    if match:
        text = match.group("amount")
    if text.count(",") and text.count("."):
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def extract_meta(html_text: str, names: List[str]) -> Optional[str]:
    for name in names:
        pattern = re.compile(META_RE_TEMPLATE.format(name=re.escape(name)), re.I | re.S)
        match = pattern.search(html_text)
        if match:
            return normalize_whitespace(match.group(1))
    return None


def extract_title(html_text: str, parsed_json: List[Any]) -> Optional[str]:
    for item in parsed_json:
        title = find_first_value(item, TITLE_KEYS)
        if title:
            clean = normalize_whitespace(str(title))
            if clean and len(clean) > 3:
                return clean
    meta_title = extract_meta(html_text, ["og:title", "twitter:title", "title"])
    if meta_title:
        return meta_title
    match = TITLE_TAG_RE.search(html_text)
    if match:
        return normalize_whitespace(match.group(1))
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.I | re.S)
    if h1_match:
        return normalize_whitespace(h1_match.group(1))
    return None


def parse_json_ld_blocks(html_text: str) -> List[Any]:
    parsed: List[Any] = []
    collector = ScriptCollector()
    collector.feed(html_text)
    for attrs, content in collector.scripts:
        script_type = attrs.get("type", "").lower()
        if "ld+json" in script_type:
            candidate = content.strip()
            if not candidate:
                continue
            try:
                parsed.append(json.loads(candidate))
            except json.JSONDecodeError:
                repaired = candidate.replace("\t", " ").replace("\n", " ")
                try:
                    parsed.append(json.loads(repaired))
                except json.JSONDecodeError:
                    continue
        elif any(key in content.lower() for key in ["price", "availability", "product"]):
            for fragment in SCRIPT_JSON_RE.findall(content):
                try:
                    parsed.append(json.loads(fragment))
                except Exception:
                    continue
    return parsed


def find_first_value(obj: Any, target_keys: set) -> Optional[Any]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in target_keys and value not in (None, ""):
                return value
        for value in obj.values():
            found = find_first_value(value, target_keys)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_first_value(item, target_keys)
            if found not in (None, ""):
                return found
    return None


def normalize_availability(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = normalize_whitespace(str(value)) or ""
    text = re.sub(r"https?://schema.org/", "", text, flags=re.I)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ").strip()
    for pattern, label in AVAILABILITY_PATTERNS:
        if pattern.search(text):
            return label
    return text.title() if text else None


def extract_price_from_json(parsed_json: List[Any]) -> Tuple[Optional[float], Optional[str], Optional[str], Optional[str]]:
    best_price = None
    best_currency = None
    raw_price = None
    availability = None
    for item in parsed_json:
        price = find_first_value(item, PRICE_KEYS)
        currency = find_first_value(item, {"pricecurrency", "currency", "currencycode"})
        avail = find_first_value(item, AVAILABILITY_KEYS)
        amount = parse_amount(price)
        if amount is not None:
            best_price = amount
            best_currency = normalize_currency(str(currency) if currency else None)
            raw_price = str(price)
            availability = normalize_availability(str(avail) if avail else None)
            break
    return best_price, best_currency, raw_price, availability


def extract_price_from_meta(html_text: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    price_text = extract_meta(
        html_text,
        [
            "product:price:amount",
            "og:price:amount",
            "twitter:data1",
            "price",
            "twitter:label1",
        ],
    )
    currency = extract_meta(
        html_text,
        ["product:price:currency", "og:price:currency", "price:currency", "currency"],
    )
    amount = parse_amount(price_text) if price_text else None
    return amount, normalize_currency(currency), price_text


def extract_price_fallback(html_text: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    fallback_patterns = [
        r'"price"\s*[:=]\s*"?([^",}<]+)',
        r'data-(?:price|product-price)=["\']([^"\']+)',
        r'class=["\'][^"\']*(?:price|sale-price|product-price)[^"\']*["\'][^>]*>(.*?)<',
        r'id=["\'][^"\']*(?:price|sale-price|product-price)[^"\']*["\'][^>]*>(.*?)<',
        r'aria-label=["\']([^"\']{0,60}(?:\$|€|£)\s*\d[^"\']*)["\']',
    ]
    for pattern in fallback_patterns:
        match = re.search(pattern, html_text, re.I | re.S)
        if not match:
            continue
        candidate = normalize_whitespace(match.group(1))
        amount = parse_amount(candidate)
        if amount is not None:
            currency_match = PRICE_RE.search(candidate or "")
            currency = normalize_currency(currency_match.group("currency")) if currency_match and currency_match.group("currency") else None
            return amount, currency, candidate
    text_window = normalize_whitespace(html_text[:200000]) or ""
    for match in PRICE_RE.finditer(text_window):
        amount = parse_amount(match.group(0))
        if amount is not None and amount > 0:
            currency = normalize_currency(match.group("currency")) if match.group("currency") else None
            return amount, currency, match.group(0)
    return None, None, None


def extract_availability(html_text: str, parsed_json: List[Any]) -> Optional[str]:
    for item in parsed_json:
        avail = find_first_value(item, AVAILABILITY_KEYS)
        if avail:
            normalized = normalize_availability(str(avail))
            if normalized:
                return normalized
    meta_avail = extract_meta(html_text, ["product:availability", "availability"])
    if meta_avail:
        return normalize_availability(meta_avail)
    body_slice = normalize_whitespace(html_text[:200000]) or ""
    for pattern, label in AVAILABILITY_PATTERNS:
        if pattern.search(body_slice):
            return label
    return None


def extract_snapshot(url: str, html_text: str) -> ProductSnapshot:
    parsed_json = parse_json_ld_blocks(html_text)
    title = extract_title(html_text, parsed_json)
    price, currency, raw_price, availability = extract_price_from_json(parsed_json)
    if price is None:
        price, currency_meta, raw_meta = extract_price_from_meta(html_text)
        currency = currency or currency_meta
        raw_price = raw_price or raw_meta
    if price is None:
        price, currency_fallback, raw_fallback = extract_price_fallback(html_text)
        currency = currency or currency_fallback
        raw_price = raw_price or raw_fallback
    if not availability:
        availability = extract_availability(html_text, parsed_json)
    host = urllib.parse.urlparse(url).netloc
    return ProductSnapshot(
        url=url,
        fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        title=title,
        price=price,
        currency=currency,
        availability=availability,
        source_host=host,
        raw_price_text=raw_price,
    )


def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"items": {}}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(path: str, state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def compute_change(previous: Optional[Dict[str, Any]], current: ProductSnapshot) -> Dict[str, Any]:
    change = {
        "first_seen": previous is None,
        "price_changed": False,
        "availability_changed": False,
        "title_changed": False,
        "old_price": previous.get("price") if previous else None,
        "new_price": current.price,
        "old_availability": previous.get("availability") if previous else None,
        "new_availability": current.availability,
        "old_title": previous.get("title") if previous else None,
        "new_title": current.title,
        "percent_change": None,
    }
    if previous:
        old_price = previous.get("price")
        if old_price is not None and current.price is not None and not math.isclose(float(old_price), float(current.price), rel_tol=1e-9):
            change["price_changed"] = True
            if float(old_price) != 0:
                change["percent_change"] = round(((float(current.price) - float(old_price)) / float(old_price)) * 100, 2)
        elif old_price is None and current.price is not None:
            change["price_changed"] = True
        if (previous.get("availability") or "") != (current.availability or ""):
            change["availability_changed"] = True
        if significant_title_change(previous.get("title"), current.title):
            change["title_changed"] = True
    return change


def significant_title_change(old: Optional[str], new: Optional[str]) -> bool:
    if not old or not new:
        return False
    norm_old = re.sub(r"\W+", " ", old.lower()).strip()
    norm_new = re.sub(r"\W+", " ", new.lower()).strip()
    if norm_old == norm_new:
        return False
    old_tokens = set(norm_old.split())
    new_tokens = set(norm_new.split())
    if not old_tokens or not new_tokens:
        return False
    overlap = len(old_tokens & new_tokens) / max(len(old_tokens | new_tokens), 1)
    return overlap < 0.6


def format_price(price: Optional[float], currency: Optional[str]) -> str:
    if price is None:
        return "n/a"
    return f"{currency + ' ' if currency else ''}{price:.2f}"


def load_watch_targets(path: str) -> List[Dict[str, Any]]:
    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8") as handle:
        if ext == ".json":
            data = json.load(handle)
            if isinstance(data, list):
                return [normalize_target(item) for item in data]
            if isinstance(data, dict) and "targets" in data:
                return [normalize_target(item) for item in data["targets"]]
        elif ext == ".jsonl":
            return [normalize_target(json.loads(line)) for line in handle if line.strip()]
        elif ext in {".csv", ".tsv"}:
            delimiter = "\t" if ext == ".tsv" else ","
            reader = csv.DictReader(handle, delimiter=delimiter)
            return [normalize_target(row) for row in reader]
        else:
            return [normalize_target({"url": line.strip()}) for line in handle if line.strip() and not line.lstrip().startswith("#")]
    raise ValueError(f"Unsupported watchlist format: {path}")


def normalize_target(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return {"url": item}
    if not isinstance(item, dict) or not item.get("url"):
        raise ValueError(f"Invalid target entry: {item!r}")
    return {"url": item["url"], "label": item.get("label")}


def build_text_report(results: List[Dict[str, Any]]) -> str:
    lines = [f"EdgeIQ competitor price intelligence report ({len(results)} target(s))"]
    for item in results:
        snapshot = item["snapshot"]
        change = item["change"]
        lines.append(f"- {snapshot['title'] or snapshot['url']}")
        lines.append(f"  URL: {snapshot['url']}")
        lines.append(f"  Price: {format_price(snapshot['price'], snapshot['currency'])}")
        lines.append(f"  Availability: {snapshot.get('availability') or 'Unknown'}")
        if change["first_seen"]:
            lines.append("  Change: first observation")
        else:
            flags = []
            if change["price_changed"]:
                delta = (
                    f" ({change['percent_change']:+.2f}%)" if change["percent_change"] is not None else ""
                )
                flags.append(
                    f"price {format_price(change['old_price'], snapshot['currency'])} -> {format_price(change['new_price'], snapshot['currency'])}{delta}"
                )
            if change["availability_changed"]:
                flags.append(f"availability {change['old_availability'] or 'Unknown'} -> {change['new_availability'] or 'Unknown'}")
            if change["title_changed"]:
                flags.append("title/listing changed")
            lines.append(f"  Change: {'; '.join(flags) if flags else 'no change'}")
    return "\n".join(lines)


def build_html_report(results: List[Dict[str, Any]]) -> str:
    rows = []
    for item in results:
        s = item["snapshot"]
        c = item["change"]
        changes = []
        if c["first_seen"]:
            changes.append("first observation")
        if c["price_changed"]:
            pct = f" ({c['percent_change']:+.2f}%)" if c["percent_change"] is not None else ""
            changes.append(f"Price {html.escape(format_price(c['old_price'], s['currency']))} → {html.escape(format_price(c['new_price'], s['currency']))}{pct}")
        if c["availability_changed"]:
            changes.append(f"Availability {html.escape(c['old_availability'] or 'Unknown')} → {html.escape(c['new_availability'] or 'Unknown')}")
        if c["title_changed"]:
            changes.append("Title/listing changed")
        rows.append(
            "<tr>"
            f"<td><a href=\"{html.escape(s['url'])}\">{html.escape(s['title'] or s['url'])}</a></td>"
            f"<td>{html.escape(format_price(s['price'], s['currency']))}</td>"
            f"<td>{html.escape(s.get('availability') or 'Unknown')}</td>"
            f"<td>{'<br>'.join(changes) if changes else 'No change'}</td>"
            "</tr>"
        )
    timestamp = html.escape(dt.datetime.now(dt.timezone.utc).isoformat())
    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\">
  <title>EdgeIQ competitor price intelligence</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    a {{ color: #0a58ca; text-decoration: none; }}
  </style>
</head>
<body>
  <h1>EdgeIQ competitor price intelligence</h1>
  <p>Generated at {timestamp}</p>
  <table>
    <thead><tr><th>Product</th><th>Price</th><th>Availability</th><th>Detected changes</th></tr></thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>"""


def send_telegram_alert(message_text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message_text})
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20):
        return


def send_whatsapp_alert(message_text: str) -> None:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")
    to_number = os.getenv("TWILIO_WHATSAPP_TO")
    if not all([sid, token, from_number, to_number]):
        return
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = urllib.parse.urlencode({"From": from_number, "To": to_number, "Body": message_text}).encode("utf-8")
    request = urllib.request.Request(endpoint, data=payload, method="POST")
    auth = urllib.request.HTTPBasicAuthHandler()
    auth.add_password(realm=None, uri=endpoint, user=sid, passwd=token)
    opener = urllib.request.build_opener(auth)
    opener.open(request, timeout=20).read()


def build_alert_message(snapshot: Dict[str, Any], change: Dict[str, Any]) -> str:
    title = snapshot.get("title") or snapshot["url"]
    old_price = format_price(change.get("old_price"), snapshot.get("currency"))
    new_price = format_price(change.get("new_price"), snapshot.get("currency"))
    pct = f" ({change['percent_change']:+.2f}%)" if change.get("percent_change") is not None else ""
    availability = snapshot.get("availability") or "Unknown"
    return (
        f"Price alert: {title}\n"
        f"{old_price} -> {new_price}{pct}\n"
        f"Availability: {availability}\n"
        f"{snapshot['url']}"
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor public competitor product pages for price changes.")
    parser.add_argument("urls", nargs="*", help="One or more public product URLs to monitor")
    parser.add_argument("--watchlist", help="Path to watchlist file (.json, .jsonl, .csv, .tsv, or .txt)")
    parser.add_argument("--state-file", default="./state/price-monitor-state.json", help="Path to JSON state file")
    parser.add_argument("--json-out", help="Write full report JSON to this path")
    parser.add_argument("--html-out", help="Write full report HTML to this path")
    parser.add_argument("--text-out", help="Write text report to this path")
    parser.add_argument("--env-file", default=".env", help="Optional .env file path")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP User-Agent string")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist state or send alerts")
    parser.add_argument("--no-alerts", action="store_true", help="Suppress Telegram/WhatsApp alerts")
    parser.add_argument("--fail-on-fetch-error", action="store_true", help="Exit non-zero if a target cannot be fetched")
    return parser.parse_args(argv)


def ensure_parent(path: str) -> None:
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    load_env_file(args.env_file)

    targets: List[Dict[str, Any]] = []
    if args.watchlist:
        targets.extend(load_watch_targets(args.watchlist))
    targets.extend({"url": url} for url in args.urls)

    deduped = []
    seen = set()
    for item in targets:
        url = item["url"].strip()
        if url and url not in seen:
            deduped.append({"url": url, "label": item.get("label")})
            seen.add(url)
    targets = deduped

    if not targets:
        print("No URLs supplied. Pass URLs and/or --watchlist.", file=sys.stderr)
        return 2

    state = load_state(args.state_file)
    previous_items = state.get("items", {})
    new_state = {"items": dict(previous_items)}
    results: List[Dict[str, Any]] = []
    fetch_errors: List[str] = []

    for target in targets:
        url = target["url"]
        try:
            html_text = fetch_url(url, timeout=args.timeout, user_agent=args.user_agent)
            snapshot = extract_snapshot(url, html_text)
            previous = previous_items.get(url)
            change = compute_change(previous, snapshot)
            snapshot_dict = asdict(snapshot)
            results.append({"snapshot": snapshot_dict, "change": change})
            new_state["items"][url] = snapshot_dict
        except Exception as exc:
            fetch_errors.append(f"{url}: {exc}")
            results.append({
                "snapshot": {
                    "url": url,
                    "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "title": None,
                    "price": None,
                    "currency": None,
                    "availability": None,
                    "source_host": urllib.parse.urlparse(url).netloc,
                    "raw_price_text": None,
                },
                "change": {"error": str(exc), "first_seen": False, "price_changed": False, "availability_changed": False, "title_changed": False},
            })

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "target_count": len(targets),
        "results": results,
        "fetch_errors": fetch_errors,
    }
    text_report = build_text_report(results)
    print(text_report)
    if fetch_errors:
        print("\nFetch errors:", file=sys.stderr)
        for error in fetch_errors:
            print(f"- {error}", file=sys.stderr)

    if args.json_out:
        ensure_parent(args.json_out)
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    if args.html_out:
        ensure_parent(args.html_out)
        with open(args.html_out, "w", encoding="utf-8") as handle:
            handle.write(build_html_report(results))
    if args.text_out:
        ensure_parent(args.text_out)
        with open(args.text_out, "w", encoding="utf-8") as handle:
            handle.write(text_report + "\n")

    if not args.dry_run:
        save_state(args.state_file, new_state)

    if not args.dry_run and not args.no_alerts:
        for item in results:
            change = item["change"]
            snapshot = item["snapshot"]
            if change.get("price_changed") or change.get("availability_changed") or change.get("title_changed"):
                message_text = build_alert_message(snapshot, change)
                try:
                    send_telegram_alert(message_text)
                except Exception:
                    pass
                try:
                    send_whatsapp_alert(message_text)
                except Exception:
                    pass

    if fetch_errors and args.fail_on_fetch_error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
