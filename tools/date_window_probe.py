# -*- coding: utf-8 -*-
"""권혁찬 v5.0 검색식의 기간 제한이 잘라낸 크기를 건수로만 진단한다.
인출·선별·채점을 하지 않는다."""
import io
import json
import re
import time
import urllib.parse
import urllib.request

QDEF = r"C:\dev\otc-nutrient-safety-engine\research_v3\otc\literature\v5\query_definitions.json"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
TOOL = "otc-nutrient-safety-engine-date-window-probe"
EMAIL = "wellnessbox.tips@gmail.com"
DATE = re.compile(r'"(\d{4}/\d{2}/\d{2})"\[Date - Publication\]')


def count(term):
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": term, "rettype": "count",
        "retmode": "json", "tool": TOOL, "email": EMAIL,
    })
    req = urllib.request.Request(EUTILS, data=params.encode("utf-8"),
                                 headers={"User-Agent": TOOL})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(json.loads(r.read().decode("utf-8"))["esearchresult"]["count"])


raw = json.load(io.open(QDEF, encoding="utf-8"))
qs = raw["questions"] if isinstance(raw, dict) and "questions" in raw else raw
print("항목 수", len(qs), "· 키", list(qs[0].keys())[:12])

rows = []
for q in qs:
    qid = q.get("question_id") or q.get("id")
    term = q.get("query") or q.get("final_query") or ""
    ds = DATE.findall(term)
    if not ds:
        print(f"  {qid}: 날짜 제한 없음 — 건너뜀")
        continue
    start = ds[0]
    wide = term.replace(f'"{start}"[Date - Publication]',
                        '"1900/01/01"[Date - Publication]', 1)
    n_o = count(term)
    time.sleep(0.5)
    n_w = count(wide)
    time.sleep(0.5)
    rows.append((qid, start, n_o, n_w))
    print(f"  {qid:6s} 시작 {start}  현재 {n_o:>7,}  해제 {n_w:>8,}  배수 {n_w / n_o:.2f}")

t_o = sum(r[2] for r in rows)
t_w = sum(r[3] for r in rows)
print(f"\n  합계   현재 {t_o:>7,}  해제 {t_w:>8,}  배수 {t_w / t_o:.2f}")
print(f"  창 밖 {t_w - t_o:,}건 · 전체의 {(t_w - t_o) / t_w * 100:.1f}%")

io.open("kwon_date_window_probe.json", "w", encoding="utf-8").write(json.dumps({
    "purpose": "기간 제한이 잘라낸 크기를 건수로만 진단. 인출·선별·채점 없음.",
    "start_probe": "1900/01/01",
    "per_question": [
        {"question_id": r[0], "start_original": r[1], "hit_current": r[2],
         "hit_without_start_limit": r[3], "ratio": round(r[3] / r[2], 4)}
        for r in rows
    ],
    "total": {"current": t_o, "without_start_limit": t_w,
              "ratio": round(t_w / t_o, 4), "outside_window": t_w - t_o},
}, ensure_ascii=False, indent=2))
print("\nkwon_date_window_probe.json 저장")
