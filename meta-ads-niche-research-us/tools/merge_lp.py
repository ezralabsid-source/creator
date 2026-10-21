"""Masukkan hasil fetch_lp.py (lp_found.csv) ke data/*.json.

    python tools/merge_lp.py lp_found.csv data
    python build_report.py data out
"""
import csv
import glob
import json
import sys
from pathlib import Path

found = {r["page_id"]: r["lp_url"] for r in csv.DictReader(open(sys.argv[1], newline="")) if r.get("lp_url")}
n = 0
for f in sorted(glob.glob(str(Path(sys.argv[2]) / "*.json"))):
    d = json.load(open(f))
    for a in d["advertisers"]:
        url = found.get(str(a["page_id"]))
        if url:
            a["lp_url"] = url
            a["lp_source"] = "verified"
            n += 1
    Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=2))
print(f"{n} LP dimasukkan")
