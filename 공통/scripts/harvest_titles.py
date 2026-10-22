# -*- coding: utf-8 -*-
"""검색 때 받아 둔 법제처·LBOX 수확 목록에서 사안 고유어가 제목에 든 줄을 다시 뽑아, 대조표·원고·검색기록에 올라 있는지 본다.

`/검토의견` 4-2단계(마지막 자체 검토)의 '수확 목록 제목 다시 훑기'에 쓴다. 유사 사례 표는 작성 세션이 고른 것만 담으므로,
받아 두고도 표에 올리지 않은 판결·회시가 마지막 검토에서도 빠진다(2026. 10. 22. HPS 업종 분류 검토의견서에서 법제처 수확에
있던 산업안전과-2077·산재예방지원과-829 가 처음 작성과 4-2단계에서 모두 빠졌다가 재검토에서 들어갔다).
LBOX 에는 요청을 보내지 않는다. 사건 폴더 안의 파일만 읽는다.

    python -B 공통/scripts/harvest_titles.py scan "{사건 폴더}" --낱말 발전소 정비 위탁 [--lbox "{파일}" …] [--out "{사건 폴더}/작업/수확목록_재확인.md"]
    python -B 공통/scripts/harvest_titles.py lbox-save "{결과 파일}" [… ] --out "{사건 폴더}/작업/LBOX_목록.tsv"

scan
  - 법제처: 사건 폴더 아래 모든 `법제처_목록.json`(lawgo.py harvest 가 쓴 것)의 줄. 제목(사건명·안건명)에서 찾는다.
  - LBOX: 사건 폴더 아래 `LBOX_목록.tsv`(lbox-save 가 쓴 것)와 --lbox 로 준 파일. --lbox 에는 lbox-save 의 결과 파일이나
    `lboxLines` 출력이 남은 세션 결과 파일(tool-results 의 .txt, 세션 기록 .jsonl)을 줄 수 있다. 사건명과 스니펫에서 찾는다.
  - 낱말은 공백과 가운뎃점을 무시하고 찾는다('유지보수'로 '유지·보수'도 걸린다). '발전+정비'처럼 + 로 이으면 둘 다 든 줄만
    걸린다. '정비'·'위탁'처럼 다른 분야 제목(도시정비, 민간위탁)에도 흔한 낱말은 홀로 쓰지 말고 + 로 묶는다.
  - 기록: 사건 폴더의 .md(법제처 수확 폴더·지침발췌·인용판결_PDF 아래는 뺀다)에 그 줄의 사건번호·문서번호가 있는지.
  - 본문: 법제처 줄은 `법제처_본문_*.md`·`법제처/본문/*.md` 머리에 그 번호가 있는지. LBOX 줄은 알 수 없어 '—'.
  결과는 기록에 없는 줄부터 표로 낸다. 종료 코드는 늘 0 이다(판정은 사람이 한다).

lbox-save
  조종 탭에서 `lboxRowsDump(모은rows)`(lbox-검색 3항 블록)를 부른 결과가 길면 도구가 세션의 tool-results 폴더에 저장한다.
  그 파일에서 'LBOXROWS\t{건수}' ~ 'LBOXROWS-END' 묶음을 찾아 TSV 로 옮기고 건수를 맞춘다. 여러 묶음은 사건번호로 합친다.
  결과가 짧아 대화에 그대로 들어왔으면 그 글을 파일로 저장해 넘긴다.
"""
import argparse
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
SQUEEZE = re.compile(r"[\s·ㆍ•]+")
LINES = re.compile(r"(?:^|\s)(\d{1,5}) \| ([^|\n]{1,40}) \| (\d{2}-\d{2}-\d{2}) \| ([^|\s]{3,80}) \| ([^|\n]{1,300}?)(?= \| |\n|$)")
HEAD = "id\t법원\t선고일\t사건\t출처\t스니펫"
SKIP_DIRS = ("법제처", "지침발췌", "인용판결_PDF", "전환작업", "빌드")


def sq(t):
    return SQUEEZE.sub("", t or "")


def read_any(path):
    """세션 결과 파일(JSON 배열·JSON 줄·글)의 글을 잇는다."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    if path.endswith(".jsonl"):
        out = []
        for ln in raw.splitlines():
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            for x in (d.get("message") or {}).get("content") or [] if isinstance((d.get("message") or {}).get("content"), list) else []:
                if isinstance(x, dict) and x.get("type") == "tool_result":
                    c = x.get("content")
                    out.append(c if isinstance(c, str) else " ".join(y.get("text", "") for y in (c or []) if isinstance(y, dict)))
        return "\n".join(out)
    try:
        arr = json.loads(raw)
    except ValueError:
        return raw
    if isinstance(arr, list):
        return "".join(x.get("text", "") for x in arr if isinstance(x, dict))
    if isinstance(arr, str):
        return arr
    return raw


def dump_blocks(text):
    """lboxRowsDump 묶음을 찾아 (적힌 건수, 줄 목록)으로 돌려준다.
    스크립트 실행 도구는 돌려준 글을 JSON 문자열로 적으므로(탭·줄바꿈이 \\t·\\n 두 글자), 그 꼴도 풀어 읽는다."""
    out = []
    found = [(m.group(1), m.group(2)) for m in re.finditer(r"LBOXROWS\t(\d+)\n(.*?)\nLBOXROWS-END", text, flags=re.S)]
    if not found:
        for m in re.finditer(r"LBOXROWS\\t(\d+)\\n(.*?)\\nLBOXROWS-END", text, flags=re.S):
            found.append((m.group(1), json.loads('"' + m.group(2) + '"')))
    for n, body in found:
        rows = [ln.split("\t") for ln in body.split("\n") if ln.strip()]
        out.append((int(n), rows))
    return out


def load_lbox_file(path):
    """LBOX 목록 줄: TSV(lbox-save), 덤프 묶음, lboxLines 출력 가운데 있는 것을 읽는다."""
    rows = []
    if path.endswith(".tsv"):
        for ln in open(path, encoding="utf-8").read().splitlines()[1:]:
            c = (ln.split("\t") + [""] * 6)[:6]
            rows.append({"src": "LBOX", "id": c[0], "org": c[1], "date": c[2], "title": c[3], "extra": c[5], "q": c[4]})
        return rows
    text = read_any(path)
    for n, block in dump_blocks(text):
        for c in block:
            c = (c + [""] * 6)[:6]
            rows.append({"src": "LBOX", "id": c[0], "org": c[1], "date": c[2], "title": c[3], "extra": c[5], "q": c[4]})
    if not rows:                                   # lboxLines 출력(순번 | 법원 | 선고일 | id | 사건 | …)
        for m in LINES.finditer(text):
            rows.append({"src": "LBOX", "id": m.group(4).strip(), "org": m.group(2).strip(), "date": m.group(3),
                         "title": m.group(5).strip(), "extra": "", "q": ""})
    return rows


def load_lawgo(case):
    rows = []
    files = glob.glob(os.path.join(case, "**", "법제처_목록.json"), recursive=True)
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        for kind, v in d.items():
            for r in (v.get("rows", []) if isinstance(v, dict) else []):
                rows.append({"src": "법제처-" + (r.get("종류") or kind), "id": r.get("사건번호") or r.get("id") or "",
                             "org": r.get("기관") or "", "date": r.get("일자") or "", "title": r.get("제목") or "",
                             "extra": "", "q": r.get("검색어") or "", "lawgo_id": str(r.get("id") or "")})
    return files, rows


NUMBER = re.compile(r"\d{2,4}[가-힣]{1,4}\d+|[가-힣]+과-\d+")


def number_key(r):
    """기록에서 찾을 번호. LBOX id('대법원-2011두12856', '조세심판원-심판결정례-조심2018지0635')는 사건번호·문서번호만,
    가려진 번호(…OOO, ?)는 쓰지 않는다."""
    n = r["id"]
    if r["src"] == "LBOX":
        m = NUMBER.search(n)
        n = m.group(0) if m else n.rsplit("-", 1)[-1]
    k = sq(n)
    if not k or "?" in k or "OOO" in k or not re.search(r"\d", k) or len(k) < 4:
        return ""
    return k


def record_text(case):
    parts = []
    for f in glob.glob(os.path.join(case, "**", "*.md"), recursive=True):
        rel = os.path.relpath(f, case).replace("\\", "/")
        if any(seg in SKIP_DIRS for seg in rel.split("/")[:-1]) or os.path.basename(f).startswith("수확목록_재확인"):
            continue
        parts.append(open(f, encoding="utf-8", errors="replace").read())
    return sq("\n".join(parts))


def body_heads(case):
    heads = []
    for f in glob.glob(os.path.join(case, "**", "법제처_본문_*.md"), recursive=True) + glob.glob(os.path.join(case, "**", "법제처", "본문", "*.md"), recursive=True):
        for ln in open(f, encoding="utf-8", errors="replace"):
            if ln.startswith("## "):
                heads.append(sq(ln))
    return "\n".join(heads)


def cell(t, n=None):
    t = re.sub(r"\s+", " ", str(t or "")).replace("|", "/").strip()
    return t if n is None or len(t) <= n else t[:n] + "…"


def scan(a):
    case = a.case.rstrip("/\\")
    words = [w for w in a.낱말 if sq(w)]
    files, law = load_lawgo(case)
    lbox_files = glob.glob(os.path.join(case, "**", "LBOX_목록.tsv"), recursive=True) + (a.lbox or [])
    lbox = []
    for f in lbox_files:
        lbox += load_lbox_file(f)
    seen, rows = set(), []
    for r in law + lbox:                           # 같은 줄이 여러 수확·파일에 있으면 하나로
        key = (r["src"].split("-")[0], sq(r["id"]) or sq(r["title"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(r)
    recs, heads = record_text(case), body_heads(case)
    hits = []
    for r in rows:
        hay = sq(r["title"] + " " + r.get("extra", ""))
        got = [w for w in words if all(sq(p) in hay for p in w.split("+") if sq(p))]   # '발전+정비'는 둘 다 든 줄
        if not got:
            continue
        k = number_key(r)
        r["낱말"] = ", ".join(got)
        r["기록"] = ("있음" if k in recs else "없음") if k else "번호 없음"
        r["본문"] = ("받음" if k and k in heads else "안 받음") if r["src"].startswith("법제처") else "—"
        hits.append(r)
    order = {"없음": 0, "번호 없음": 1, "있음": 2}
    hits.sort(key=lambda r: (order[r["기록"]], r["src"], r["date"]), reverse=False)
    miss = [r for r in hits if r["기록"] != "있음"]
    out = ["# 수확 목록 제목 다시 훑기 — %s" % os.path.basename(case), "",
           "낱말: %s" % ", ".join(words),
           "법제처 목록 %d개 파일 · %d줄 / LBOX 목록 %d개 파일 · %d줄(같은 줄 합친 뒤 %d줄)" % (len(files), len(law), len(lbox_files), len(lbox), len(rows)),
           "걸린 줄 %d건 — 기록에 있음 %d건, 없음 %d건(그 가운데 법제처 본문을 받은 것 %d건), 번호가 없어 가리지 못한 것 %d건"
           % (len(hits), len(hits) - len(miss), sum(1 for r in miss if r["기록"] == "없음"),
              sum(1 for r in miss if r["기록"] == "없음" and r["본문"] == "받음"), sum(1 for r in miss if r["기록"] == "번호 없음")),
           ""]
    if not lbox_files:
        out += ["LBOX 목록 파일이 없다. 조종 탭에 모은 목록이 남아 있으면 `lboxUnread`로, 없으면 검색기록의 검색어로 다시 수확해 본다(`/검토의견` 4-2단계).", ""]
    for title, part in (("기록에 없는 줄(본문을 읽고 반영하거나 유사 사례 표에 미반영 이유를 적는다)", miss),
                        ("기록에 있는 줄", [r for r in hits if r["기록"] == "있음"])):
        out += ["## %s" % title, "", "| 출처 | 사건번호·문서번호 | 일자 | 기관·법원 | 제목 | 걸린 낱말 | 기록 | 본문 |", "|---|---|---|---|---|---|---|---|"]
        out += ["| %s | %s | %s | %s | %s | %s | %s | %s |" % (cell(r["src"]), cell(r["id"]), cell(r["date"]), cell(r["org"], 20),
                                                              cell(r["title"], 90), cell(r["낱말"]), r["기록"], r["본문"]) for r in part]
        out.append("")
    text = "\n".join(out)
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(text)
        print("씀:", a.out)
    print(text if not a.out else "\n".join(out[:6]))


def lbox_save(a):
    merged, bad = {}, 0
    for f in a.results:
        blocks = dump_blocks(read_any(f))
        if not blocks:
            print("묶음 없음:", f)
            bad += 1
        for n, rows in blocks:
            if n != len(rows):
                print("건수 다름: 적힌 %d · 읽은 %d (%s)" % (n, len(rows), f))
                bad += 1
            for c in rows:
                c = (c + [""] * 6)[:6]
                merged.setdefault(c[0], c)
    if not merged:
        sys.exit(1)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as w:
        w.write(HEAD + "\n" + "\n".join("\t".join(c) for c in merged.values()) + "\n")
    print("씀: %s · %d줄%s" % (a.out, len(merged), " · 확인할 것 %d" % bad if bad else ""))
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("case", help="사건 폴더")
    s.add_argument("--낱말", nargs="+", required=True, help="사안 고유어(목록 대부분에 걸리는 쟁점 낱말은 넣지 않는다)")
    s.add_argument("--lbox", nargs="*", help="LBOX 목록이 든 파일(TSV, lboxRowsDump 결과, lboxLines 출력이 남은 세션 결과)")
    s.add_argument("--out", help="결과를 쓸 파일(.md)")
    s2 = sub.add_parser("lbox-save")
    s2.add_argument("results", nargs="+", help="lboxRowsDump 결과가 저장된 파일")
    s2.add_argument("--out", required=True, help="{사건 폴더}/작업/LBOX_목록.tsv")
    a = ap.parse_args()
    scan(a) if a.cmd == "scan" else lbox_save(a)


if __name__ == "__main__":
    main()
