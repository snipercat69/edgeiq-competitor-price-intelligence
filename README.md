# 💰 EdgeIQ Competitor Price Intelligence

**Monitor competitor pricing and market positioning automatically.**

Track competitor pricing changes across multiple domains, get alerted to price shifts, and maintain competitive intelligence — all automated on a schedule you define.

[![Project Stage](https://img.shields.io/badge/Stage-Beta-blue)](https://edgeiqlabs.com)
[![Python](https://img.shields.io/badge/Python-3.8+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-orange)](LICENSE)

---

## What It Does

Scrapes competitor pricing pages at configurable intervals, records price history, and alerts you when prices change. Designed for e-commerce operators, SaaS pricing analysts, and business intelligence teams.

---

## Key Features

- **Multi-domain price tracking** — monitor any number of competitor domains
- **Scheduled scraping** — run on cron or manual trigger
- **Price change alerts** — Slack/Telegram notification when prices shift
- **Price history** — SQLite-backed historical record
- **Product matching** — map competitor products to your catalog
- **JSON/CSV export** — structured data for BI tools

---

## Prerequisites

- Python 3.8+
- `requests`, `beautifulsoup4`, `lxml`

---

## Installation

```bash
git clone https://github.com/snipercat69/edgeiq-competitor-price-intelligence.git
cd edgeiq-competitor-price-intelligence
pip install -r requirements.txt
cp config.json.example config.json
```

---

## Quick Start

```bash
# Run a price check
python3 scripts/price_check.py

# Check specific domain
python3 scripts/price_check.py --domain competitor.com

# Export price history
python3 scripts/export_prices.py --format csv --output price_history.csv
```

---

## Pricing

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | 3 domains, daily checks |
| **Pro** | $20/mo | Unlimited domains, hourly checks, CSV export |
| **Lifetime** | $100 one-time | All Pro features, forever |

---

## Support

Open an issue at: https://github.com/snipercat69/edgeiq-competitor-price-intelligence/issues

---

*Part of EdgeIQ Labs — [edgeiqlabs.com](https://edgeiqlabs.com)*
