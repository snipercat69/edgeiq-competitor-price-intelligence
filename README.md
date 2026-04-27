# EdgeIQ Competitor Price Intelligence

Monitor public competitor product pages and generate simple price-change reports.

## What it does

- Fetch one or more public product URLs
- Extract title, price, currency, and availability when detectable
- Store prior snapshots in a local JSON state file
- Detect price, availability, and major title/listing changes
- Output console text, JSON, and HTML reports
- Send concise alerts through Telegram Bot API and Twilio WhatsApp if configured

## Guardrails

Use this only for:

- Publicly accessible pages, or
- Pages you are explicitly authorized to monitor

Do **not** use it to bypass logins, CAPTCHAs, paywalls, or anti-bot controls.

## Quick start

```bash
cd /home/guy/.openclaw/workspace/apps/edgeiq-competitor-price-intelligence
cp .env.example .env
python3 scripts/price_monitor.py \
  "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html" \
  --state-file ./state/demo-state.json \
  --json-out ./out/report.json \
  --html-out ./out/report.html \
  --text-out ./out/report.txt
```

## Watchlist formats

### Plain text

One URL per line:

```txt
https://example.com/product/sku-1
https://example.com/product/sku-2
```

### JSON

```json
{
  "targets": [
    {"url": "https://example.com/product/sku-1", "label": "Competitor A"},
    {"url": "https://example.com/product/sku-2", "label": "Competitor B"}
  ]
}
```

### JSONL

```jsonl
{"url":"https://example.com/product/sku-1","label":"Competitor A"}
{"url":"https://example.com/product/sku-2","label":"Competitor B"}
```

### CSV

```csv
url,label
https://example.com/product/sku-1,Competitor A
https://example.com/product/sku-2,Competitor B
```

## CLI usage

```bash
python3 scripts/price_monitor.py [URL ...] [options]
```

Options:

- `--watchlist PATH` - load URLs from `.json`, `.jsonl`, `.csv`, `.tsv`, or text file
- `--state-file PATH` - snapshot state store (default `./state/price-monitor-state.json`)
- `--json-out PATH` - write machine-readable report
- `--html-out PATH` - write HTML report
- `--text-out PATH` - write plain-text report
- `--env-file PATH` - optional env file to load (default `.env`)
- `--dry-run` - fetch and compare without persisting state or sending alerts
- `--no-alerts` - suppress Telegram and WhatsApp delivery
- `--fail-on-fetch-error` - exit non-zero if any target fetch fails
- `--timeout SECONDS` - override HTTP timeout
- `--user-agent STRING` - override request user-agent

## Example cron-friendly run

```bash
cd /home/guy/.openclaw/workspace/apps/edgeiq-competitor-price-intelligence && \
python3 scripts/price_monitor.py \
  --watchlist ./watchlists/sample-watchlist.json \
  --state-file ./state/prod.json \
  --json-out ./out/latest.json \
  --html-out ./out/latest.html \
  --text-out ./out/latest.txt
```

## Alerts

When credentials are configured, alerts include:

- Product name
- Old price
- New price
- Percent change
- Availability
- Source URL

Telegram uses the Bot API.
WhatsApp uses Twilio-style messaging credentials.

## Notes on extraction

The monitor tries multiple public-page patterns:

- JSON-LD / schema.org product data
- OpenGraph and other meta tags
- Common inline JSON fields
- Common HTML price class/id patterns
- Generic text fallback for visible currency amounts

It is intentionally lightweight and stdlib-first, so results will vary across heavily scripted storefronts.

## Sample output

```text
EdgeIQ competitor price intelligence report (1 target(s))
- A Light in the Attic
  URL: https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html
  Price: GBP 51.77
  Availability: In Stock
  Change: first observation
```
