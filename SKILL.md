---
name: edgeiq-competitor-price-intelligence
description: Monitor public competitor product pages and ecommerce listings for price, availability, and listing changes. Use when tracking retailer or marketplace product URLs, generating scheduled pricing visibility reports, comparing snapshots across runs, or sending concise Telegram/WhatsApp alerts from public or explicitly authorized sources.
---

# EdgeIQ Competitor Price Intelligence

Version: 1.0.0

Category: Market Intelligence / Ecommerce Monitoring

Build a lightweight pricing-monitoring workflow for public or authorized product pages.

## Tiers

- Free
  - 1 watch target
  - Console/text output only
- **Pro ($19/mo)** — Multiple watch targets, Telegram alerts, WhatsApp alerts, JSON reports, HTML reports
- **Lifetime ($39)** — [buy lifetime](https://buy.stripe.com/3cI14p0Lxbxr8Ec8AE7wA00) — your tool forever

## Features

- Accept one or more product URLs directly
- Accept watchlists from JSON, JSONL, CSV, TSV, or plain text
- Fetch public product pages with stdlib HTTP tooling
- Extract title, price, currency, and availability using layered fallback logic
- Detect price changes, availability changes, and major title/listing changes
- Store previous snapshots in a local JSON state file
- Generate readable text, JSON, and HTML reports
- Run safely in one-shot cron-style mode
- Send concise change alerts through Telegram Bot API and Twilio-style WhatsApp when configured

## Files

- Main app: `scripts/price_monitor.py`
- Environment template: `.env.example`
- User guide and watchlist examples: `README.md`

## Usage examples

Run against a single URL:

```bash
python3 scripts/price_monitor.py "https://example.com/product/sku-123"
```

Run against a watchlist and save reports:

```bash
python3 scripts/price_monitor.py \
  --watchlist ./watchlists/sample-watchlist.json \
  --state-file ./state/price-monitor-state.json \
  --json-out ./out/latest.json \
  --html-out ./out/latest.html \
  --text-out ./out/latest.txt
```

Run a dry test without updating state or sending alerts:

```bash
python3 scripts/price_monitor.py \
  --watchlist ./watchlists/sample-watchlist.json \
  --dry-run --no-alerts
```

## Operating guidance

- Use only public pages or pages the customer is explicitly authorized to monitor.
- Do not attempt to bypass logins, CAPTCHAs, or anti-bot protections.
- Prefer scheduled one-shot runs over aggressive polling.
- Review extraction quality on each new retailer before relying on automated alerts.

## Legal notice

Use this skill only for lawful market-intelligence monitoring of public webpages or sources you are authorized to access. Do not use it to evade access controls, scrape private data, bypass authentication, defeat anti-bot systems, or violate marketplace/site terms. The operator is responsible for confirming authorization, compliance obligations, and acceptable monitoring frequency.


---

## 🔗 More from EdgeIQ Labs

**edgeiqlabs.com** — Security tools, OSINT utilities, and micro-SaaS products for developers and security professionals.

- 🛠️ **Subdomain Hunter** — Passive subdomain enumeration via Certificate Transparency
- 📸 **Screenshot API** — URL-to-screenshot API for developers
- 🔔 **uptime.check** — URL uptime monitoring with alerts
- 🛡️ **headers.check** — HTTP security headers analyzer

👉 [Visit edgeiqlabs.com →](https://edgeiqlabs.com)
