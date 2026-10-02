"""Ежедневное обновление цен в витрине на главной alexpekk.com (облачная версия).

Запускается GitHub Actions по расписанию (.github/workflows/prices.yml), мак не нужен.
Ключ технического аккаунта Google лежит в секрете репозитория GOOGLE_KEY_JSON.

Берёт стартовую цену за метр из листа «Наличие» таблицы застройщиков
(его в 10:10 пересобирает build_svod.py), ставит сегодняшнюю дату,
сортирует дома от дешёвого к дорогому и выкладывает сайт в репозиторий.
Год сдачи задан здесь руками: Alex правил его сам, таблица может отставать.
Запуск по расписанию системы: ~/Library/LaunchAgents/com.alexpekk.site-prices.plist
"""

import datetime
import json
import os
import re
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

PAGE = "index.html"
SHEET_ID = "1DrM2IdEVVYdRssufiH1jJ-_96r26bVrS_b7_fMA8OKc"

# (район, название на сайте, строки листа «Наличие», год сдачи, показывать диапазон)
LOTS = [
    ("Батуми", "Status House", ["Status House"], 2028, False),
    ("Гонио", "HOME", ["HOME"], 2026, False),
    ("Батуми", "The Parallel", ["The Parallel (блок A)", "The Parallel (блок B)"], 2028, False),
    ("Батуми", "Strada", ["Strada"], 2030, False),
    ("Батуми", "Cube", ["Cube"], 2028, False),
    ("Тбилиси", "VR Vake Sky Tower", ["VR Vake Sky Tower"], 2031, True),
]
# цена за метр: каркас, если нет - с ремонтом, если нет - под ключ
PRICE_COLS = ["Каркас, $/м2", "С ремонтом, $/м2", "Под ключ, $/м2"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]


def log(msg):
    print(f"{datetime.datetime.now():%Y-%m-%d %H:%M} {msg}", flush=True)


def money(v):
    s = f"{v:,}".replace(",", " ")
    return s


def read_sheet():
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_KEY_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    sid = SHEET_ID
    rows = build("sheets", "v4", credentials=creds).spreadsheets().values().get(
        spreadsheetId=sid, range="Наличие").execute()["values"]
    head = rows[0]
    return {r[1]: dict(zip(head, r + [""] * len(head))) for r in rows[1:] if len(r) > 1}


def prices(row):
    for col in PRICE_COLS:
        nums = [int(n) for n in re.findall(r"\d+", row.get(col, "").replace(" ", ""))]
        if nums:
            return min(nums), max(nums)
    return None


def main():
    sheet = read_sheet()
    lots = []
    for area, name, keys, year, show_range in LOTS:
        found = [p for p in (prices(sheet[k]) for k in keys if k in sheet) if p]
        if not found:
            log(f"нет цены для {name} - витрину не трогаю")
            return 1
        lo, hi = min(p[0] for p in found), max(p[1] for p in found)
        label = f"${money(lo)} - {money(hi)}" if show_range and hi > lo else f"${money(lo)}"
        lots.append((lo, area, name, label, year))
    lots.sort()
    html = "".join(
        f'      <div class="lot"><span class="area">{a}</span><span class="name">{n}</span>'
        f'<span class="price">{l} <small>за м²</small></span><span class="terms">сдача {y}</span></div>\n'
        for _, a, n, l, y in lots)

    s = open(PAGE, encoding="utf-8").read()
    start = s.index('    <div class="lots">\n') + len('    <div class="lots">\n')
    end = s.index("    </div>", start)
    s = s[:start] + html + s[end:]
    today = datetime.date.today()
    s, n = re.subn(r"Цены на \d{1,2} [а-я]+ \d{4}",
                   f"Цены на {today.day} {MONTHS[today.month - 1]} {today.year}", s)
    if n != 1:
        log("не нашёл строку с датой - витрину не трогаю")
        return 1
    open(PAGE, "w", encoding="utf-8").write(s)

    log("витрина обновлена: " + ", ".join(f"{n} {l}" for _, _, n, l, _ in lots))
    return 0


if __name__ == "__main__":
    sys.exit(main())
