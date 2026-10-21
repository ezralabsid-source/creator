"""Build HTML / Markdown / CSV report from niche JSON files."""
import csv
import html
import json
import sys
from pathlib import Path

DATA = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

ORDER = ["mrr-plr", "ai-side-hustle", "ecommerce", "trading-investing", "personal-finance",
         "real-estate", "fitness", "diet-nutrition", "mental-health", "spirituality", "christian",
         "parenting-kids", "survival", "natural-remedies", "crafts-diy", "templates-planners",
         "dating-relationships", "creative-skills", "pet-training", "career-business"]
# broad keywords the research agents flagged as dominated by unrelated ads (drama apps, novels, brokers)
NOISE = {"get your ex back", "save your marriage", "pulled away", '"ex back"', "learn to draw",
         "devotional for women", "sleep training", "dog training", "law of attraction",
         "job interview", "Amish", "coaching business", "remote job"}
STATUS_RANK = {"WINNING": 0, "POTENSIAL": 1, "BARU": 2}

niches = []
for slug in ORDER:
    p = DATA / f"{slug}.json"
    if not p.exists():
        print("MISSING", slug)
        continue
    n = json.loads(p.read_text())
    n["slug"] = slug
    advs = n.get("advertisers", [])
    for a in advs:
        a["status"] = (a.get("status") or "BARU").upper()
        a["active_ads"] = a.get("active_ads") or 0
        a["max_days_running"] = a.get("max_days_running") or 0
    advs.sort(key=lambda a: (STATUS_RANK.get(a["status"], 3), -a["max_days_running"], -a["active_ads"]))
    n["advertisers"] = advs
    kw = n.get("keywords", [])
    for k in kw:
        k["noise"] = "(noise" in k["term"].lower() or k["term"] in NOISE
    clean = [k for k in kw if not k["noise"]]
    n["volume"] = max([k.get("active_ads_id") or 0 for k in clean] or [0])
    n["volume_raw"] = max([k.get("active_ads_id") or 0 for k in kw] or [0])
    n["volume_sum"] = sum(k.get("active_ads_id") or 0 for k in kw)
    n["n_win"] = sum(a["status"] == "WINNING" for a in advs)
    n["n_pot"] = sum(a["status"] == "POTENSIAL" for a in advs)
    n["total_active"] = sum(a["active_ads"] for a in advs)
    n["max_days"] = max([a["max_days_running"] for a in advs] or [0])
    niches.append(n)

# advertisers that appear in more than one niche
seen = {}
for n in niches:
    for a in n["advertisers"]:
        seen.setdefault(str(a.get("page_id")), []).append(n["niche"])

# rank niches: winning advertisers first, then summed keyword volume
ranked = sorted(niches, key=lambda n: (-n["total_active"], -n["n_win"]))
for i, n in enumerate(ranked, 1):
    n["rank"] = i

e = html.escape


def lp_cell(a):
    url = a.get("lp_url")
    src = a.get("lp_source") or "not_found"
    labels = {"verified": "terverifikasi", "search": "dari pencarian web", "domain_hint": "petunjuk domain", "not_found": "belum ditemukan"}
    if url and src == "domain_hint":
        hint = url.replace("https://", "").replace("http://", "").rstrip("/")
        return f'<span class="hint">{e(hint)}</span><span class="src src-domain_hint">petunjuk, belum dicek</span>'
    if url:
        short = url.replace("https://", "").replace("http://", "")
        if len(short) > 38:
            short = short[:36] + "…"
        return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(short)}</a><span class="src src-{e(src)}">{labels.get(src, src)}</span>'
    return f'<span class="muted">—</span><span class="src src-not_found">{labels.get(src, src)}</span>'


def ads_cell(a):
    out = []
    for ad in (a.get("winning_ads") or [])[:3]:
        url = ad.get("ad_url") or f"https://www.facebook.com/ads/library/?id={ad.get('ad_id')}"
        title = ad.get("link_title") or ""
        if len(title) > 70:
            title = title[:68] + "…"
        out.append(f'<li><a href="{e(url)}" target="_blank" rel="noopener">{e(str(ad.get("ad_id")))}</a> '
                   f'<span class="days">{ad.get("days", "?")} hr</span>'
                   f'{"<br><span class=t>" + e(title) + "</span>" if title else ""}</li>')
    return f'<ul class="ads">{"".join(out)}</ul>' if out else '<span class="muted">—</span>'


rank_rows = []
max_vol = max([n["total_active"] for n in ranked] or [1]) or 1
for n in ranked:
    w = round(100 * n["total_active"] / max_vol, 1)
    rank_rows.append(f'''<tr>
<td class="num">{n["rank"]}</td>
<td><a href="#{n["slug"]}">{e(n["niche"])}</a></td>
<td class="bar-cell"><div class="bar-line"><div class="bar"><span style="width:{w}%"></span></div><span class="num">{n["total_active"]:,}</span></div></td>
<td class="num">{n["volume"]:,}</td>
<td class="num">{len(n["advertisers"])}</td>
<td class="num"><b>{n["n_win"]}</b></td>
<td class="num">{n["max_days"]}</td>
</tr>''')

sections = []
for n in ranked:
    ins = n.get("insights", {}) or {}
    kw = ", ".join(f'<span class="{"muted" if k["noise"] else ""}">{e(k["term"])} <span class="num muted">({k.get("active_ads_id") or 0:,}{" · noise" if k["noise"] else ""})</span></span>' for k in n.get("keywords", []))
    angles = "".join(f"<li>{e(x)}</li>" for x in ins.get("angles", []) or [])
    formats = ", ".join(e(x) for x in ins.get("formats", []) or [])
    rows = []
    for i, a in enumerate(n["advertisers"], 1):
        pid = a.get("page_id")
        lib = a.get("ad_library_page_url") or f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&view_all_page_id={pid}"
        price = a.get("price_seen")
        rows.append(f'''<tr data-status="{a["status"]}">
<td class="num">{i}</td>
<td><a class="adv" href="{e(lib)}" target="_blank" rel="noopener">{e(a.get("page_name") or "")}</a><span class="pid">ID {e(str(pid))}</span></td>
<td>{e(a.get("product") or "")}<span class="meta">{e(a.get("format") or "")}{" · " + e(price) if price else ""}</span>{'<span class="note">' + e(a["notes"]) + '</span>' if a.get("notes") else ''}{'<span class="meta">Juga tercantum di: ' + e(", ".join(x for x in seen[str(pid)] if x != n["niche"])) + '</span>' if len(seen.get(str(pid), [])) > 1 else ''}</td>
<td class="num">{a["active_ads"]}</td>
<td class="num">{a["max_days_running"]}<span class="meta">sejak {e(a.get("oldest_active_start") or "?")}</span></td>
<td><span class="pill pill-{a["status"].lower()}">{a["status"]}</span></td>
<td>{ads_cell(a)}</td>
<td class="lp">{lp_cell(a)}</td>
</tr>''')
    sections.append(f'''<section class="niche" id="{n["slug"]}">
<header class="niche-head">
<span class="eyebrow">Peringkat {n["rank"]} dari {len(ranked)}</span>
<h2>{e(n["niche"])}</h2>
<div class="stats"><span><b>{n["total_active"]:,}</b> iklan aktif dari pengiklan di bawah</span><span><b>{n["volume"]:,}</b> iklan aktif di keyword teratas</span><span><b>{len(n["advertisers"])}</b> pengiklan</span><span><b>{n["n_win"]}</b> WINNING</span><span><b>{n["n_pot"]}</b> POTENSIAL</span></div>
</header>
<div class="insight">
<p>{e(ins.get("summary") or "")}</p>
<dl>
<div><dt>Kisaran harga</dt><dd>{e(ins.get("price_range") or "-")}</dd></div>
<div><dt>Format dominan</dt><dd>{formats or "-"}</dd></div>
<div><dt>Keyword dicek</dt><dd>{kw}</dd></div>
</dl>
{"<h3>Angle / hook yang sering dipakai</h3><ul class=angles>" + angles + "</ul>" if angles else ""}
</div>
<div class="table-wrap"><table class="adv-table">
<thead><tr><th>#</th><th>Pengiklan</th><th>Produk</th><th>Iklan aktif</th><th>Hari jalan (maks)</th><th>Status</th><th>Iklan winning (link)</th><th>Landing page</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
</section>''')

total_adv = sum(len(n["advertisers"]) for n in niches)
total_win = sum(n["n_win"] for n in niches)
total_lp = sum(1 for n in niches for a in n["advertisers"] if a.get("lp_url") and a.get("lp_source") in ("search", "verified"))

template = (Path(__file__).parent / "template_us.html").read_text()
page = (template
        .replace("{{RANK_ROWS}}", "\n".join(rank_rows))
        .replace("{{SECTIONS}}", "\n".join(sections))
        .replace("{{N_NICHE}}", str(len(niches)))
        .replace("{{TOTAL_ADV}}", str(total_adv))
        .replace("{{TOTAL_WIN}}", str(total_win))
        .replace("{{TOTAL_LP}}", str(total_lp))
        .replace("{{NAV}}", "".join(f'<a href="#{n["slug"]}">{n["rank"]}. {e(n["niche"])}</a>' for n in ranked)))
(OUT / "report.html").write_text(page)

# CSV
with open(OUT / "advertisers.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["peringkat_niche", "niche", "pengiklan", "page_id", "ad_library_page", "produk", "format", "harga",
                "iklan_aktif", "hari_jalan_maks", "mulai_tertua", "status", "iklan_winning_1", "iklan_winning_2",
                "iklan_winning_3", "lp_url", "lp_sumber", "catatan"])
    for n in ranked:
        for a in n["advertisers"]:
            ads = [x.get("ad_url") or f"https://www.facebook.com/ads/library/?id={x.get('ad_id')}" for x in (a.get("winning_ads") or [])[:3]]
            ads += [""] * (3 - len(ads))
            w.writerow([n["rank"], n["niche"], a.get("page_name"), a.get("page_id"), a.get("ad_library_page_url"),
                        a.get("product"), a.get("format"), a.get("price_seen"), a["active_ads"], a["max_days_running"],
                        a.get("oldest_active_start"), a["status"], *ads, a.get("lp_url") or "", a.get("lp_source"), a.get("notes") or ""])

# Markdown
md = [f"# Riset Niche Produk Digital — Meta Ad Library Amerika Serikat (US)\n",
      f"Data diambil 21 Oktober 2026 dari Meta Ad Library (negara: US, status: aktif). {len(niches)} niche, {total_adv} pengiklan, {total_win} berstatus WINNING (punya iklan aktif ≥30 hari).\n",
      "## Peringkat niche\n", "| # | Niche | Iklan aktif pengiklan terdaftar | Iklan aktif keyword teratas | Pengiklan | WINNING | Hari jalan terlama |", "|---|---|---|---|---|---|---|"]
for n in ranked:
    md.append(f'| {n["rank"]} | {n["niche"]} | {n["total_active"]:,} | {n["volume"]:,} | {len(n["advertisers"])} | {n["n_win"]} | {n["max_days"]} |')
for n in ranked:
    ins = n.get("insights", {}) or {}
    md += [f'\n## {n["rank"]}. {n["niche"]}\n', ins.get("summary") or "", "",
           f'- Kisaran harga: {ins.get("price_range") or "-"}',
           f'- Format dominan: {", ".join(ins.get("formats") or [])}',
           f'- Keyword: {", ".join(f"{k["term"]} ({k.get("active_ads_id") or 0})" for k in n.get("keywords", []))}']
    if ins.get("angles"):
        md.append("- Angle: " + "; ".join(ins["angles"]))
    md += ["", "| # | Pengiklan | Produk | Harga | Iklan aktif | Hari jalan | Status | Iklan winning | LP |", "|---|---|---|---|---|---|---|---|---|"]
    for i, a in enumerate(n["advertisers"], 1):
        ads = " ".join(f'[{x.get("days","?")}hr]({x.get("ad_url") or "https://www.facebook.com/ads/library/?id=" + str(x.get("ad_id"))})' for x in (a.get("winning_ads") or [])[:3])
        lp = (f'{a["lp_url"]} (petunjuk)' if a.get("lp_source") == "domain_hint" else f'[link]({a["lp_url"]})') if a.get("lp_url") else "—"
        name = (a.get("page_name") or "").replace("|", "/")
        prod = (a.get("product") or "").replace("|", "/")
        md.append(f'| {i} | [{name}]({a.get("ad_library_page_url")}) | {prod} | {a.get("price_seen") or "-"} | {a["active_ads"]} | {a["max_days_running"]} | {a["status"]} | {ads} | {lp} |')
(OUT / "REPORT.md").write_text("\n".join(md) + "\n")
print(f"niches={len(niches)} adv={total_adv} win={total_win} lp={total_lp}")
