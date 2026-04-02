"""
Alko Opening Hours Telegram Bot
Scrapes https://www.alko.fi/fi/palvelut/asiointi-myymalassa/aukioloajat
using Playwright to get opening/closing times for any date.
"""

import os
import logging
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

from scraper import AlkoScraper

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


# In-memory cache, valid for the current day only.
_CACHE_DAY = date.today()
_HOURS_CACHE: dict[date, dict] = {}
_WEEK_CACHE: list[dict] | None = None


def _ensure_cache_day() -> None:
    global _CACHE_DAY, _HOURS_CACHE, _WEEK_CACHE
    today = date.today()
    if _CACHE_DAY != today:
        _CACHE_DAY = today
        _HOURS_CACHE = {}
        _WEEK_CACHE = None
        logger.info("Cache reset for new day: %s", today.isoformat())


# ── helpers ───────────────────────────────────────────────────────────────────

def format_hours_message(info: dict, target_date: date) -> str:
    weekdays_fi = [
        "Maanantai", "Tiistai", "Keskiviikko",
        "Torstai", "Perjantai", "Lauantai", "Sunnuntai",
    ]
    day_name = weekdays_fi[target_date.weekday()]
    date_str = target_date.strftime("%d.%m.%Y")

    if info.get("closed"):
        note = info.get("note", "")
        msg = (
            f"🏪 *Alko Tampere Sokos – Aukioloaika*\n"
            f"📅 {day_name} {date_str}\n\n"
            f"❌ *Myymälä suljettu*"
        )
        if note:
            msg += f"\n\n_{note}_"
        return msg

    open_time  = info.get("open",  "?")
    close_time = info.get("close", "?")
    note       = info.get("note",  "")

    lines = [
        "🏪 *Alko Tampere Sokos – Aukioloaika*",
        f"📅 {day_name} {date_str}",
        "",
        f"🟢 Avataan: *{open_time}*",
        f"🔴 Suljetaan: *{close_time}*",
    ]
    if note:
        lines += ["", f"_{note}_"]

    return "\n".join(lines)


def format_week_message(hours_list: list[dict]) -> str:
    """Format the current week of opening hours."""
    weekdays_fi = [
        "Maanantai", "Tiistai", "Keskiviikko",
        "Torstai", "Perjantai", "Lauantai", "Sunnuntai",
    ]

    lines = ["🏪 *Alko Tampere Sokos – Aukioloajat*"]

    for info in hours_list:
        target_date = info["date"]
        day_name = weekdays_fi[target_date.weekday()]
        date_str = target_date.strftime("%d.%m.")

        lines.append("")
        lines.append(f"*{day_name} {date_str}*")

        if info.get("closed"):
            lines.append("❌ SULJETTU")
        else:
            open_time = info.get("open", "?")
            close_time = info.get("close", "?")
            lines.append(f"🟢 {open_time}–{close_time}")

        note = info.get("note", "")
        if note:
            lines.append(f"_{note}_")

    return "\n".join(lines)


# ── command handlers ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 Hei! Olen *Alko-botti* 🍷\n\n"
        "Kerron Alko Tampere Sokoksen aukioloajat haluamallesi päivälle.\n\n"
        "*Komennot:*\n"
        "  /auki - tänään\n"
        "  /auki 24.12.2025 - valittuna päivänä\n"
        "  /viikko - tämän viikon aukioloajat\n"
        "  /huomenna - huomisen ajat\n\n"
        "Tiedot haetaan suoraan alko.fi-sivustolta."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def auki(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        raw = context.args[0].strip()
        try:
            target = datetime.strptime(raw, "%d.%m.%Y").date()
        except ValueError:
            await update.message.reply_text(
                "Virheellinen paivamaara. Kayta muotoa pp.kk.vvvv, esim. /auki 24.12.2025"
            )
            return
    else:
        target = date.today()

    _ensure_cache_day()
    cached = _HOURS_CACHE.get(target)
    if cached is not None:
        logger.info("Cache hit for date %s", target.isoformat())
        text = format_hours_message(cached, target)
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    msg = await update.message.reply_text("Haetaan tietoja alko.fi:sta...")

    try:
        async with AlkoScraper() as scraper:
            info = await scraper.get_hours(target)
        _HOURS_CACHE[target] = info
        text = format_hours_message(info, target)
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Scraper error")
        await msg.edit_text(
            "Tietojen haku epaonnistui.\n\n"
            "Tarkista aukioloajat osoitteesta:\n"
            "https://www.alko.fi/fi/myymalat-palvelut/2464"
        )


async def huomenna(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.args = [(date.today() + timedelta(days=1)).strftime("%d.%m.%Y")]
    await auki(update, context)

async def tanaan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.args = [date.today().strftime("%d.%m.%Y")]
    await auki(update, context)

async def viikko(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the current week's opening hours from the scraper."""
    global _WEEK_CACHE

    _ensure_cache_day()
    if _WEEK_CACHE is not None:
        logger.info("Week cache hit for day %s", _CACHE_DAY.isoformat())
        text = format_week_message(_WEEK_CACHE)
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    msg = await update.message.reply_text("Haetaan viikon aukioloajat alko.fi:sta...")

    try:
        async with AlkoScraper() as scraper:
            hours_list = await scraper.get_week_hours()
        _WEEK_CACHE = hours_list

        text = format_week_message(hours_list)
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Scraper error")
        await msg.edit_text(
            "Tietojen haku epaonnistui.\n\n"
            "Tarkista aukioloajat osoitteesta:\n"
            "https://www.alko.fi/fi/myymalat-palvelut/2464"
        )


# ── startup: register commands with Telegram ──────────────────────────────────

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("auki",     "Aukioloaika tänään (tai /auki pp.kk.vvvv)"),
        BotCommand("tanaan",   "Aukioloaika tänään"),
        BotCommand("huomenna", "Huomisen aukioloaika"),
        BotCommand("viikko",   "Viikon aukioloajat"),
        BotCommand("start",    "Ohjeet"),
        BotCommand("help",     "Ohjeet"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered with Telegram")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN ei ole asetettu! "
            "Lisaa se .env-tiedostoon tai ymparistomuuttujiin."
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("help",     start))
    app.add_handler(CommandHandler("auki",     auki))
    app.add_handler(CommandHandler("tanaan",   tanaan))
    app.add_handler(CommandHandler("huomenna", huomenna))
    app.add_handler(CommandHandler("viikko",   viikko))

    logger.info("Alko-botti kaynnistyy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()