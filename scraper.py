"""
Alko opening-hours scraper using Playwright.

Sources:
  - Store page (normal weekly hours, rolling 7-day view):
      https://www.alko.fi/fi/myymalat-palvelut/2464
  - Exceptions / holidays page:
      https://www.alko.fi/fi/palvelut/asiointi-myymalassa/aukioloajat

Logic:
  1. Scrape the store page for its 7-day timetable.
     The timetable contains entries for the next ~7 days so we can read
     the actual hours for any day that falls inside that window.
  2. If the target date is outside the 7-day window, fall back to the
     regular weekday pattern inferred from what we scraped.
  3. Scrape the exceptions page for holiday overrides.
  4. Exceptions always trump the store timetable.
"""

import re
import logging
from datetime import date, timedelta
from typing import Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

STORE_URL      = "https://www.alko.fi/fi/myymalat-palvelut/2464"
EXCEPTION_URL  = "https://www.alko.fi/fi/palvelut/asiointi-myymalassa/aukioloajat"

WEEKDAY_NAMES_FI = [
    "maanantai",   # 0  ma
    "tiistai",     # 1  ti
    "keskiviikko", # 2  ke
    "torstai",     # 3  to
    "perjantai",   # 4  pe
    "lauantai",    # 5  la
    "sunnuntai",   # 6  su
]

# Short 2-letter prefixes used on the page (totorstai, peperjantai, …)
WEEKDAY_SHORT = ["ma", "ti", "ke", "to", "pe", "la", "su"]

CLOSED_KEYWORDS = ["suljettu", "kiinni", "closed", "ei auki"]

# Time patterns: "9–18", "9:00–18:00", "9.00–18.00", "klo 9–18"
TIME_RE       = re.compile(r"\b(\d{1,2})[:\.](\d{2})\b")
BARE_RANGE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[–\-]\s*(\d{1,2})(?!\d)")

# Date pattern: "2.4." or "02.04." or "2.4.2026"
DATE_IN_TEXT_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})?")

# Exception "like-another-day" pattern
OPEN_LIKE_RE = re.compile(
    r"(maanantai|tiistai|keskiviikko|torstai|perjantai|lauantai|sunnuntai)"
    r".{0,50}(aukioloaiko|mukaisesti|tavoin)",
    re.IGNORECASE,
)


def parse_time_range(text: str) -> Optional[tuple[str, str]]:
    times = TIME_RE.findall(text)
    if len(times) >= 2:
        return f"{int(times[0][0]):02d}:{times[0][1]}", f"{int(times[1][0]):02d}:{times[1][1]}"
    m = BARE_RANGE_RE.search(text)
    if m:
        return f"{int(m.group(1)):02d}:00", f"{int(m.group(2)):02d}:00"
    return None


def is_closed(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in CLOSED_KEYWORDS)


class AlkoScraper:
    def __init__(self):
        self._playwright = None
        self._browser    = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        return self

    async def __aexit__(self, *_):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ── public ────────────────────────────────────────────────────────────────

    async def get_hours(self, target: date) -> dict:
        ctx = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fi-FI",
            timezone_id="Europe/Helsinki",
        )
        try:
            # ── 1. Scrape store timetable ──────────────────────────────────
            store_hours = await self._scrape_store(ctx, target)
            logger.info("Store timetable result: %s", store_hours)

            # ── 2. Scrape exceptions ───────────────────────────────────────
            exception = await self._scrape_exception(ctx, target, store_hours)
            logger.info("Exception result: %s", exception)

            if exception is not None:
                return exception
            if store_hours is not None:
                return store_hours

            # ── 3. Absolute fallback ───────────────────────────────────────
            return self._weekday_fallback(target.weekday())

        finally:
            await ctx.close()

    async def get_week_hours(self) -> list[dict]:
        """Scrape the current week's opening hours from the store timetable."""
        ctx = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fi-FI",
            timezone_id="Europe/Helsinki",
        )
        try:
            page = await ctx.new_page()
            try:
                try:
                    await page.goto(STORE_URL, wait_until="commit", timeout=15_000)
                except PlaywrightTimeoutError:
                    logger.warning("Week store navigation timed out; continuing with partial load")
                try:
                    await page.wait_for_selector("main, .store, table, li", timeout=10_000)
                except Exception:
                    pass
                await page.wait_for_timeout(3500)

                texts = await page.eval_on_selector_all(
                    "*",
                    "els => els.map(e => e.innerText ? e.innerText.trim() : '').filter(t => t.length > 0)"
                )
                logger.info("Week page sample: %s", texts[:20])

                timetable = self._parse_timetable(texts)
                logger.info("Week timetable parsed: %s", timetable)

                return self._week_hours_from_timetable(timetable)
            finally:
                await page.close()
        finally:
            await ctx.close()

    # ── store page ────────────────────────────────────────────────────────────

    async def _scrape_store(self, ctx, target: date) -> Optional[dict]:
        page = await ctx.new_page()
        try:
            try:
                await page.goto(STORE_URL, wait_until="commit", timeout=15_000)
            except PlaywrightTimeoutError:
                logger.warning("Store navigation timed out; continuing with partial load")
            try:
                await page.wait_for_selector("main, .store, table, li", timeout=10_000)
            except Exception:
                pass
            await page.wait_for_timeout(3500)

            # Grab all text nodes
            texts = await page.eval_on_selector_all(
                "*",
                "els => els.map(e => e.innerText ? e.innerText.trim() : '').filter(t => t.length > 0)"
            )
            logger.info("Store page raw sample: %s", texts[:60])

            # Parse the 7-day timetable entries.
            # Format seen in search results: "totorstai02.04.9–18" or separate nodes
            timetable = self._parse_timetable(texts)
            logger.info("Parsed timetable: %s", timetable)

            return timetable.get(target)
        finally:
            await page.close()

    def _parse_timetable(self, texts: list[str]) -> dict[date, dict]:
        """
        Parse the rolling 7-day timetable from the store page.
        Returns a dict mapping date -> hours dict.

        The page renders each day as a text node containing:
          - short weekday prefix (to, pe, la, …)
          - date like 02.04. or 2.4.
          - hours like 9–18 or SULJETTU

        These may come as one concatenated string or several adjacent nodes.
        We look for any text chunk containing a date pattern and extract info
        from it and its immediate neighbours.
        """
        result: dict[date, dict] = {}
        today = date.today()

        for text in texts:
            if len(text) > 200:
                continue

            normalized = re.sub(r"\s+", " ", text).strip()
            matches = list(DATE_IN_TEXT_RE.finditer(normalized))
            if len(matches) != 1:
                continue

            m = matches[0]
            day_n = int(m.group(1))
            month_n = int(m.group(2))
            year_n = int(m.group(3)) if m.group(3) else today.year

            try:
                d = date(year_n, month_n, day_n)
            except ValueError:
                continue

            if abs((d - today).days) > 14:
                continue

            ctx_text = normalized
            cleaned_text = DATE_IN_TEXT_RE.sub(" ", normalized)
            logger.info("Timetable snippet for %s: %r", d.isoformat(), ctx_text)

            if is_closed(cleaned_text):
                result[d] = {"closed": True, "note": "", "source": ctx_text}
            else:
                times = parse_time_range(cleaned_text)
                if times:
                    result[d] = {"open": times[0], "close": times[1], "note": "", "source": ctx_text}

        return result

    # ── exceptions page ───────────────────────────────────────────────────────

    async def _scrape_exception(self, ctx, target: date, store_hours: Optional[dict]) -> Optional[dict]:
        page = await ctx.new_page()
        try:
            await page.goto(EXCEPTION_URL, wait_until="domcontentloaded", timeout=30_000)
            try:
                await page.wait_for_selector("main, article, li, p", timeout=10_000)
            except Exception:
                pass
            await page.wait_for_timeout(2000)

            texts = await page.eval_on_selector_all(
                "p, li, td, span",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 2)"
            )
            logger.info("Exception page sample: %s", texts[:40])

            return self._find_exception(texts, target, store_hours)
        finally:
            await page.close()

    def _find_exception(self, texts: list[str], target: date, store_hours: Optional[dict]) -> Optional[dict]:
        """
        Look for a line on the exceptions page that mentions the target date.
        Exception always wins over the store timetable.
        """
        day_pats = [
            rf"(?<!\d){target.day}\.{target.month:02d}\.{target.year}(?!\d)",
            rf"(?<!\d){target.day}\.{target.month}\.{target.year}(?!\d)",
            rf"(?<!\d){target.day}\.{target.month:02d}\.(?!\d)",
            rf"(?<!\d){target.day}\.{target.month}\.(?!\d)",
        ]

        for text in texts:
            if not any(re.search(p, text) for p in day_pats):
                continue

            logger.info("Exception line matched: %r", text)
            lower = text.lower()

            # "open like <weekday>" → look up that weekday from store hours or fallback
            like = OPEN_LIKE_RE.search(lower)
            if like:
                ref_name = like.group(1).lower()
                ref_weekday = next(
                    (i for i, n in enumerate(WEEKDAY_NAMES_FI) if n == ref_name), None
                )
                note = text[:160]
                if ref_weekday is not None:
                    # Try to get that weekday's hours from the timetable we already scraped
                    ref_date = self._nearest_weekday(ref_weekday)
                    if store_hours is None:
                        pass  # will fall through to fallback
                    # We don't have a timetable dict here — use fallback
                    fb = self._weekday_fallback(ref_weekday)
                    fb["note"] = note
                    return fb
                # Unknown weekday reference — try to parse explicit time
                times = parse_time_range(text)
                if times:
                    return {"open": times[0], "close": times[1], "note": note}

            # Explicit closed
            # Only match "suljettu" in the same clause as the date
            clause = self._date_clause(text, target)
            if is_closed(clause):
                return {"closed": True, "note": clause[:160]}

            # Explicit time range
            times = parse_time_range(text)
            if times:
                return {"open": times[0], "close": times[1], "note": text[:160]}

        return None

    # ── helpers ───────────────────────────────────────────────────────────────

    def _date_clause(self, text: str, target: date) -> str:
        """Return the sentence/clause that actually contains the date."""
        parts = re.split(r"[·•\n]|(?<=\.)\s+(?=[A-ZÄÖÅ])", text)
        pats  = [
            rf"(?<!\d){target.day}\.{target.month:02d}\.(?!\d)",
            rf"(?<!\d){target.day}\.{target.month}\.(?!\d)",
        ]
        for part in parts:
            if any(re.search(p, part) for p in pats):
                return part.strip()
        return text

    def _nearest_weekday(self, weekday: int) -> date:
        today = date.today()
        delta = (weekday - today.weekday()) % 7
        return today + timedelta(days=delta)

    def _weekday_fallback(self, weekday: int) -> dict:
        fallback = {
            0: ("09:00", "21:00"),
            1: ("09:00", "21:00"),
            2: ("09:00", "21:00"),
            3: ("09:00", "21:00"),
            4: ("09:00", "21:00"),
            5: ("09:00", "18:00"),
            6: None,
        }
        hours = fallback.get(weekday)
        if not hours:
            return {"closed": True, "note": "Suljettu (oletustieto – tarkista alko.fi)."}
        return {
            "open":  hours[0],
            "close": hours[1],
            "note":  "⚠️ Oletustieto – tarkista poikkeukset alko.fi:stä.",
        }

    def _fallback_week_hours(self, start: date) -> list[dict]:
        """Build a 7-day fallback list from the weekday defaults."""
        result: list[dict] = []
        for offset in range(7):
            item_date = start + timedelta(days=offset)
            fallback = self._weekday_fallback(item_date.weekday()).copy()
            fallback["date"] = item_date
            result.append(fallback)
        return result

    def _week_hours_from_timetable(self, timetable: dict[date, dict]) -> list[dict]:
        """Build a 7-day week view from the parsed store timetable."""
        result: list[dict] = []
        start = date.today()

        for offset in range(7):
            item_date = start + timedelta(days=offset)
            info = timetable.get(item_date)
            if info is None:
                info = self._weekday_fallback(item_date.weekday()).copy()
            else:
                info = info.copy()
                source = info.get("source")
                if source:
                    logger.info("Week entry %s uses timetable snippet: %r", item_date.isoformat(), source)
            info["date"] = item_date
            result.append(info)

        return result