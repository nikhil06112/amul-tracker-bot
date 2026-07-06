# Amul Protein Lassi Stock Notifier

Monitors **Amul High Protein Plain Lassi** and **Amul High Protein Rose Lassi** on [shop.amul.com](https://shop.amul.com) for pincode **560103** (Karnataka) and sends a Telegram message when either product comes back in stock.

You only need to provide your Telegram credentials.

## How it works

shop.amul.com uses a StoreHippo REST API (not Shopify/GraphQL). The bot:

1. Opens a browser-like session and loads cookies from the protein browse page
2. Resolves pincode `560103` → substore `karnataka`
3. Calls `/api/1/entity/ms.products` with inventory fields (`available`, `inventory_quantity`)
4. Watches for **Plain** and **Rose** protein lassi variants
5. Sends **one Telegram alert per product** when stock changes from unavailable → available

Stock state is saved in `.stock_state.json` so you are not spammed on every poll.

## Quick start

### 1. Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Create a Telegram bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** into `.env` as `BOT_TOKEN`

### 3. Get your Chat ID

1. Start a chat with your new bot (send any message)
2. Visit (replace `<TOKEN>`):

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

3. Find `"chat":{"id": ...}` in the JSON
4. Copy that number into `.env` as `CHAT_ID`

### 4. Run locally

```bash
python app.py
```

The bot checks every **300 seconds** (5 minutes) by default.

### 5. Run a one-off check

```bash
python app.py --once
```

### 6. Smoke test

Without Telegram credentials (API only):

```bash
python test_connection.py --skip-telegram
```

With Telegram credentials:

```bash
python test_connection.py
```

## Configuration

`.env` only needs:

```env
BOT_TOKEN=your_bot_token
CHAT_ID=your_chat_id
```

Optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL` | `300` | Seconds between checks when running continuously |
| `PINCODE` | `560103` | Delivery pincode (preconfigured for your area) |

## Watched products

| Variant | SKU |
|---------|-----|
| Plain Protein Lassi (200 mL × 30) | `LASCP61_30` |
| Rose Protein Lassi (200 mL × 30) | `LASCP40_30` |

A product is considered **in stock** when `available` is true and `inventory_quantity > 0`.

## Project structure

```
├── app.py                 # Main loop (--once for CI)
├── amul_client.py         # Amul API session client
├── stock_checker.py       # Product filtering and state tracking
├── notifier.py            # Telegram alerts
├── config.py              # Settings and watched products
├── test_connection.py     # Smoke tests
├── requirements.txt
├── .env.example
└── .github/workflows/check-stock.yml
```

## Running continuously

### systemd (Linux / Raspberry Pi)

Create `/etc/systemd/system/amul-stock-bot.service`:

```ini
[Unit]
Description=Amul Protein Lassi Stock Notifier
After=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/telegram_bot
EnvironmentFile=/home/pi/telegram_bot/.env
ExecStart=/home/pi/telegram_bot/.venv/bin/python app.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now amul-stock-bot
sudo systemctl status amul-stock-bot
```

### Raspberry Pi tips

- Use Python 3.12+ (`sudo apt install python3.12 python3.12-venv`)
- Clone the repo, create a venv, add `.env`, enable the systemd service above
- Logs: `journalctl -u amul-stock-bot -f`

## GitHub Actions

The included workflow runs every 5 minutes.

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Add repository secrets:
   - `BOT_TOKEN`
   - `CHAT_ID`
4. Enable Actions on the repo

The workflow caches `.stock_state.json` between runs so notifications are not repeated.

## Deploy on Railway

1. Create a new project from this GitHub repo
2. Set environment variables: `BOT_TOKEN`, `CHAT_ID`
3. Set start command: `python app.py`
4. Deploy

Railway will keep the process running and restart it if it crashes. The stock state file persists on the container filesystem between restarts.

## Deploy on Render

1. Create a **Background Worker** service
2. Connect this repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python app.py`
5. Add environment variables: `BOT_TOKEN`, `CHAT_ID`

## API notes

Discovered endpoints (for pincode 560103):

| Step | Endpoint | Purpose |
|------|----------|---------|
| Session | `GET /en/browse/protein` | Obtain cookies |
| Session | `GET /user/info.js` | Obtain session `tid` |
| Pincode | `GET /entity/pincode?filters...560103` | Resolve substore |
| Store | `PUT /entity/ms.settings/_/setPreferences` | Set delivery region |
| Products | `GET /api/1/entity/ms.products?...&substore=<id>` | Inventory data |

Requests require a computed `tid` header (SHA-256 of store ID, timestamp, random value, and session tid). Plain unauthenticated calls to the products API return HTTP 401.

## Extending to more products

Edit `WATCHED_PRODUCTS` in `config.py`:

```python
WATCHED_PRODUCTS = (
    {"match": "plain-lassi", "label": "Plain Protein Lassi"},
    {"match": "rose-lassi", "label": "Rose Protein Lassi"},
    {"match": "another-product-alias-part", "label": "Another Product"},
)
```

## License

Personal/educational use. Respect shop.amul.com terms of service and avoid aggressive polling.
