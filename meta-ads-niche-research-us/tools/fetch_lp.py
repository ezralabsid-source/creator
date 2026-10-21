"""Ambil landing page (LP) dari halaman Meta Ad Library secara otomatis.

Membaca lp_todo.csv, membuka tiap ad_url dengan Chromium headless (beberapa tab paralel),
lalu mengambil URL tujuan tombol CTA dari link l.facebook.com/l.php?u=... atau dari
field "link_url" di data halaman. Hasil ditulis ke lp_found.csv.

Jalankan di komputer yang bisa membuka facebook.com:
    pip install playwright
    python -m playwright install chromium
    python tools/fetch_lp.py lp_todo.csv lp_found.csv
(Opsional: CHROME_PATH=/path/ke/chrome untuk memakai Chrome yang sudah terpasang.)
"""
import asyncio
import csv
import json
import os
import re
import sys
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

CONCURRENCY = 4
SKIP_HOSTS = ("facebook.com", "fb.com", "fbcdn.net", "instagram.com", "messenger.com", "whatsapp.com", "fb.me")
LINK_URL_RE = re.compile(r'"link_url":"((?:[^"\\]|\\.)*)"')


def usable(url):
    if not url or not url.startswith("http"):
        return False
    host = urlparse(url).netloc.lower()
    return not any(host == h or host.endswith("." + h) for h in SKIP_HOSTS)


def unwrap(href):
    """l.facebook.com/l.php?u=<target> -> <target>"""
    parsed = urlparse(href)
    if parsed.netloc.endswith("facebook.com") and parsed.path.startswith("/l.php"):
        return parse_qs(parsed.query).get("u", [""])[0]
    return href


async def fetch_one(context, row):
    page = await context.new_page()
    found = []
    try:
        await page.goto(row["ad_url"], wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)
        for href in await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"):
            url = unwrap(href)
            if usable(url):
                found.append(url)
        for raw in LINK_URL_RE.findall(await page.content()):
            url = json.loads(f'"{raw}"')
            if usable(url):
                found.append(url)
    except Exception as exc:  # timeout, login wall, etc.
        return {**row, "lp_url": "", "fetch_status": f"error: {type(exc).__name__}"}
    finally:
        await page.close()
    # paling sering muncul = tujuan tombol CTA
    best = max(set(found), key=found.count) if found else ""
    return {**row, "lp_url": best, "fetch_status": "ok" if best else "no_link"}


async def main(src, dst):
    rows = list(csv.DictReader(open(src, newline="")))
    sem = asyncio.Semaphore(CONCURRENCY)
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=os.environ.get("CHROME_PATH") or None)
        context = await browser.new_context(
            locale="en-US",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        )

        async def run(row):
            async with sem:
                res = await fetch_one(context, row)
                results.append(res)
                print(f'[{len(results)}/{len(rows)}] {res["page_name"]}: {res["lp_url"] or res["fetch_status"]}')

        await asyncio.gather(*(run(r) for r in rows))
        await browser.close()

    fields = list(rows[0].keys()) + ["fetch_status"]
    with open(dst, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(results)
    ok = sum(1 for r in results if r["lp_url"])
    print(f"Selesai: {ok}/{len(rows)} LP ditemukan -> {dst}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
