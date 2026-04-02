# Alko Telegram Bot

A Telegram bot that fetches Alko opening hours directly from alko.fi using Playwright.

## Commands

| Command | Description |
|---|---|
| `/help` | Show help |
| `/auki` | Opening hours for today |
| `/auki 24.12.2025` | Opening hours for a specific date (format: dd.mm.yyyy) |
| `/tanaan` | Opening hours for today |
| `/huomenna` | Opening hours for tomorrow |
| `/viikko` | Opening hours for the current week |

## Installation

### 1. Create a Telegram bot token

1. Open Telegram and find **@BotFather**.
2. Send `/newbot` and follow the instructions.
3. Copy the token.

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure environment variables

Linux / macOS:

```bash
export TELEGRAM_BOT_TOKEN="your-token-here"
```

Windows (PowerShell):

```powershell
$env:TELEGRAM_BOT_TOKEN = "your-token-here"
```

Or create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=your-token-here
```

Security notes:
- `.env` is excluded by `.gitignore`.
- Never commit a real bot token.
- If a token has leaked or has been committed, rotate it immediately in BotFather.

### 4. Start the bot

```bash
python bot.py
```

The weekly cache is warmed at startup and refreshed automatically every day at 04:00 (Europe/Helsinki).

## Project structure

```text
alko-bot/
├── bot.py
├── scraper.py
├── requirements.txt
└── README.md
```

## How scraping works

1. Playwright launches headless Chromium and opens Alko pages.
2. The scraper checks exception/holiday opening hours first.
3. If no exception is found, it uses the regular weekly opening hours.
4. Command responses are built from the scraped result and cache.

The `/auki`, `/tanaan`, and `/huomenna` commands use in-memory cache when possible. If the date is not in cache, the bot fetches it directly.

## Run as a service (Ubuntu + systemd)

Use `alko-bot.service` and update these values:
- `User=youruser`
- `WorkingDirectory=/home/youruser/Github/alko-bot`
- `EnvironmentFile=/etc/alko-bot/secrets.env`
- `ExecStart=/home/youruser/Github/alko-bot/.venv/bin/python /home/youruser/Github/alko-bot/bot.py`

Create a secret file:

```bash
sudo mkdir -p /etc/alko-bot
sudo sh -c 'printf "TELEGRAM_BOT_TOKEN=your-token-here\n" > /etc/alko-bot/secrets.env'
sudo chmod 600 /etc/alko-bot/secrets.env
```

Enable and start service:

```bash
sudo cp alko-bot.service /etc/systemd/system/alko-bot.service
sudo systemctl daemon-reload
sudo systemctl enable alko-bot
sudo systemctl start alko-bot
sudo systemctl status alko-bot
```

### Proxy environment (optional)

If the server is behind a corporate proxy, add proxy variables to the same `EnvironmentFile`:

```env
TELEGRAM_BOT_TOKEN=your-token-here
HTTPS_PROXY=http://proxy.example.local:8080
HTTP_PROXY=http://proxy.example.local:8080
```

### Service management and logs (Linux)

```bash
# Start / stop / restart
sudo systemctl start alko-bot
sudo systemctl stop alko-bot
sudo systemctl restart alko-bot

# Enable/disable on boot
sudo systemctl enable alko-bot
sudo systemctl disable alko-bot

# Status
sudo systemctl status alko-bot
sudo systemctl show -p MainPID,SubState,ActiveState alko-bot

# Logs
sudo journalctl -u alko-bot -f
sudo journalctl -u alko-bot -n 200 --no-pager
sudo journalctl -u alko-bot -b
```