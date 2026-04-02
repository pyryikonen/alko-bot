# 🍷 Alko Telegram Bot

Telegram-botti joka hakee Alkon aukioloajat suoraan alko.fi-sivustolta Playwrightia käyttäen.

## Komennot

| Komento | Kuvaus |
|---|---|
| `/help` | Näyttää ohjeet |
| `/auki` | Tänään voimassa olevat aukioloajat |
| `/auki 24.12.2025` | Aukioloajat valittuna päivänä (muoto pp.kk.vvvv) |
| `/viikko` | Tämän viikon aukioloajat |
| `/huomenna` | Huomisen aukioloajat |
| `/top` | Parhaat drinkit hinnan ja etanolilitran mukaan |
| `/cheap` | Halvimmat drinkit |
| `/strong` | Vahvimmat drinkit |
| `/random` | Drink of the day |

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

## Ajastaminen palvelimella (Ubuntu + systemd)

Projektissa on valmis palvelutiedosto [alko-bot.service](alko-bot.service).

1. Päivitä tiedostoon oma käyttäjä ja polut:
	- `User=youruser`
	- `WorkingDirectory=/home/youruser/Github/alko-bot`
	- `EnvironmentFile=/home/youruser/Github/alko-bot/.env`
	- `ExecStart=/home/youruser/Github/alko-bot/.venv/bin/python /home/youruser/Github/alko-bot/bot.py`

2. Luo `.env` projektin juureen:

```env
TELEGRAM_BOT_TOKEN=sinun-token-tähän
```

3. Ota palvelu käyttöön Ubuntussa:

```bash
sudo cp alko-bot.service /etc/systemd/system/alko-bot.service
sudo systemctl daemon-reload
sudo systemctl enable alko-bot
sudo systemctl start alko-bot
sudo systemctl status alko-bot
```

### Palvelun hallinta ja lokit (Linux)

```bash
# Käynnistä / pysäytä / uudelleenkäynnistä
sudo systemctl start alko-bot
sudo systemctl stop alko-bot
sudo systemctl restart alko-bot

# Käynnistyykö automaattisesti bootissa
sudo systemctl enable alko-bot
sudo systemctl disable alko-bot

# Tila ja prosessi
sudo systemctl status alko-bot
sudo systemctl show -p MainPID,SubState,ActiveState alko-bot

# Lokit
sudo journalctl -u alko-bot -f                 # live-loki
sudo journalctl -u alko-bot -n 200 --no-pager # viimeiset 200 riviä
sudo journalctl -u alko-bot -b                # nykyinen boot
```

### Vaikuttaako koodimuutos heti käynnissä olevaan bottiin?

Ei yleensä. Käynnissä oleva prosessi käyttää käynnistyshetkellä ladattua koodia.

- Muutit `bot.py` / `scraper.py` -> aja `sudo systemctl restart alko-bot`
- Muutit `.env` -> aja `sudo systemctl restart alko-bot`
- Muutit `alko-bot.service` -> aja ensin:

```bash
sudo systemctl daemon-reload
sudo systemctl restart alko-bot
```
