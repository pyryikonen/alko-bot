# 🍷 Alko Telegram Bot

Telegram-botti joka hakee Alkon aukioloajat suoraan alko.fi-sivustolta Playwrightia käyttäen.

## Komennot

| Komento | Kuvaus |
|---|---|
| `/start` tai `/help` | Näyttää ohjeet |
| `/auki` | Tänään voimassa olevat aukioloajat |
| `/auki 24.12.2025` | Aukioloajat valittuna päivänä (muoto pp.kk.vvvv) |
| `/viikko` | Tämän viikon aukioloajat |
| `/huomenna` | Huomisen aukioloajat |

## Asennus

### 1. Hanki Telegram Bot Token

1. Avaa Telegram ja etsi **@BotFather**
2. Lähetä `/newbot` ja seuraa ohjeita
3. Kopioi saamasi token talteen

### 2. Asenna riippuvuudet

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Aseta ympäristömuuttuja

**Linux / macOS:**
```bash
export TELEGRAM_BOT_TOKEN="sinun-token-tähän"
```

**Windows (PowerShell):**
```powershell
$env:TELEGRAM_BOT_TOKEN = "sinun-token-tähän"
```

Tai luo `.env`-tiedosto projektin juureen:
```
TELEGRAM_BOT_TOKEN=sinun-token-tähän
```

Jos käytät `.env`-tiedostoa, asenna `python-dotenv` ja lisää tämä `bot.py`:n alkuun:
```python
from dotenv import load_dotenv
load_dotenv()
```

### 4. Käynnistä botti

```bash
python bot.py
```

## Tiedostorakenne

```
alko-bot/
├── bot.py          # Telegram-botti (komennot ja käsittelijät)
├── scraper.py      # Playwright-scraper Alkon sivulle
├── requirements.txt
└── README.md
```

## Miten scraper toimii

1. Playwright avaa oikean Chromium-selaimen (headless) ja lataa Alkon aukioloajat-sivun
2. Skripti etsii ensin **poikkeusajat** – juhlapyhät, erikoisaukioloajat – tälle päivälle
3. Jos poikkeusta ei löydy, haetaan **normaali viikoittainen aukioloaika** kyseiselle viikonpäivälle
4. Viimeinen varasuunnitelma on sisäänrakennettu taulukko normaaleista aukioloajoista

## Ajastaminen palvelimella (systemd)

Luo tiedosto `/etc/systemd/system/alko-bot.service`:

```ini
[Unit]
Description=Alko Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/alko-bot
Environment=TELEGRAM_BOT_TOKEN=sinun-token-tähän
ExecStart=/usr/bin/python3 /path/to/alko-bot/bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable alko-bot
sudo systemctl start alko-bot
sudo systemctl status alko-bot
```
