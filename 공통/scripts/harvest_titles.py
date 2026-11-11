# -*- coding: utf-8 -*-
"""검색 때 받아 둔 법제처·LBOX 수확 목록에서 사안 고유어가 제목에 든 줄을 다시 뽑아, 대조표·원고·검색기록에 올라 있는지 본다.

`/검토의견` 4-2단계(마지막 자체 검토)와 `/서면` 8-1단계 ⑧(적정성 점검)의 '수확 목록 제목 다시 훑기'에 쓴다. 유사 사례 표는
작성 세션이 고른 것만 담으므로, 받아 두고도 표에 올리지 않은 판결·회시가 마지막 검토에서도 빠진다(2026. 10. 22. HPS 업종 분류
검토의견서에서 법제처 수확에 있던 산업안전과-2077·산재예방지원과-829 가 처음 작성과 4-2단계에서 모두 빠졌다가 재검토에서 들어갔다).
LBOX 에는 요청을 보내지 않는다. 넘긴 폴더 안의 파일만 읽는다.

    python -B 공통/scripts/harvest_titles.py scan "{폴더}" --낱말 발전소 "발전+정비" [--lbox "{파일}" …] [--out "{폴더}/작업/수확목록_재확인.md"] [--잇기 "{앞 보고서}" …]
    python -B 공통/scripts/harvest_titles.py lbox-save "{결과 파일}" [… ] --out "{폴더}/작업/LBOX_목록.tsv"

  {폴더}는 검토의견이면 사건 폴더(`1_검토의견/사건/{의뢰인}_{검토내용}`), 서면이면 그 라운드 폴더(`4_서면작성/사건/{사건명}/라운드N`)이다.

scan
  - 법제처: 폴더 아래 모든 `법제처_목록.json`(lawgo.py harvest 가 쓴 것. `법제처_양정` 처럼 나눈 수확 폴더도)의 줄.
    제목(사건명·안건명)에서 찾는다.
  - 법원 누리집: 폴더 아래 모든 `법원_목록.json`(scourt.py harvest 가 쓴 것. 같은 칸이다)의 줄. 게시물 제목(공보는 사건명)에서 찾는다.
    게시물을 열지 않은 줄은 사건번호가 없어 '번호 없음'으로 나온다(2026. 11. 11. LBOX 를 멈추며 넣었다).
  - LBOX: 폴더 아래 `LBOX_목록*.tsv`(lbox-save 가 쓴 것. `LBOX_목록_2차.tsv` 처럼 나눈 목록도)와 --lbox 로 준 파일. --lbox 에는 lbox-save 의 결과 파일이나
    `lboxLines` 출력이 남은 세션 결과 파일(tool-results 의 .txt, 세션 기록 .jsonl)을 줄 수 있다. 사건명과 스니펫에서 찾는다.
  - 낱말은 공백과 가운뎃점을 무시하고 찾는다('유지보수'로 '유지·보수'도 걸린다). '발전+정비'처럼 + 로 이으면 둘 다 든 줄만
    걸린다. '정비'·'위탁'처럼 다른 분야 제목(도시정비, 민간위탁)에도 흔한 낱말은 홀로 쓰지 말고 + 로 묶는다.
  - 좁은 검색어(목록에 걸린 줄이 3줄 이하인 검색어, NARROW)의 줄은 낱말에 걸리지 않아도 함께 뽑는다('걸린 낱말' 칸에 '좁은 검색어 …').
    규정 문언 그대로 같은 꼭 맞춘 검색어의 결과를 목록에서 버리면 그 까닭이 줄마다 남아야 한다(2026. 11. 11.).
  - 기록: 폴더의 .md·.docx(원고·서면초안·대조표·검색기록·사건상태·제출본 등. 이름이 '법제처'로 시작하는 수확 폴더·파일과
    지침발췌·인용판결_PDF·전환작업·빌드 아래는 뺀다)에 그 줄의 사건번호·문서번호가 있는지.
  - 본문: 법제처 줄은 '법제처'로 시작하는 수확 폴더 안 .md(법제처_본문_*.md, 따로 받은 본문/) 머리에 그 번호가 있는지.
    LBOX 줄은 알 수 없어 '—'.
  결과는 기록에 없는 줄부터 표로 낸다. 종료 코드는 늘 0 이다(판정은 사람이 한다).
  - 처리: 기록에 없는 줄과 번호가 없는 줄은 표의 '처리' 칸에 줄마다 무엇을 하였는지 적는다(본문 반영, 하단 ② 반영, 유사 사례 표 미반영,
    '사안 다름: {다른 점}'). 사안이 전혀 다른 줄도 한 문장으로 묶어 가리지 않는다. 같은 --out 으로 다시 돌리면 적어 둔 처리를 이어 적고,
    --잇기 로 준 보고서의 처리도 잇는다. '같음'·'상동'·'—'만 적은 칸은 빈 칸으로 본다. 칸 안에는 세로줄(|)을 쓰지 않는다.
    2026. 11. 3. 점검: '나머지는 사안이 다름' 한 문장으로 기록에 없는 줄 161건이 최종 관문을 지나갔다.

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
from urllib.parse import unquote

sys.stdout.reconfigure(encoding="utf-8")
EMPTY = {"", "-", "—", "–", "?", "…", "같음", "위와 같음", "위와같음", "상동", "〃", '"', "동일", "반복"}      # 이 말만 적은 처리 칸은 빈 칸이다
SQUEEZE = re.compile(r"[\s·ㆍ•]+")
LINES = re.compile(r"(?:^|\s)(\d{1,5}) \| ([^|\n]{1,40}) \| (\d{2}-\d{2}-\d{2}) \| ([^|\s]{3,80}) \| ([^|\n]{1,300}?)(?= \| |\n|$)")
HEAD = "id\t법원\t선고일\t사건\t출처\t스니펫"
SKIP_DIRS = ("지침발췌", "인용판결_PDF", "전환작업", "빌드")
# 결정례 스니펫에 폼피드(0x0c) 같은 글자가 섞여 온다. 파이썬 splitlines 는 이것도 줄바꿈으로 보아 TSV 줄을 쪼개므로
# 저장할 때 칸에서 공백으로 바꾸고, 읽을 때는 \n 으로만 나눈다(2026. 10. 22. 이승민 휴직 1차 목록 10줄)
BREAKS = re.compile(r"[\x0b\x0c\x1c\x1d\x1e\x85  ]")


def harvest_dir(seg):
    """lawgo.py harvest 가 쓴 수확 폴더('법제처', '법제처_양정', '법제처_재검증' 등)와 scourt.py harvest 가 쓴 폴더('법원', '법원_양정').
    '법원 제출본'처럼 사건 기록이 든 폴더를 빼지 않도록 법원은 이름이 '법원' 이거나 '법원_' 으로 시작할 때만 수확 폴더로 본다."""
    return seg.startswith("법제처") or seg == "법원" or seg.startswith("법원_")


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
        for ln in open(path, encoding="utf-8").read().split("\n")[1:]:
            if not ln.strip():
                continue
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


def load_court(case):
    """scourt.py harvest 가 쓴 법원_목록.json. 게시물을 열지 않은 줄은 사건번호가 비어 '번호 없음'으로 가린다."""
    rows = []
    files = glob.glob(os.path.join(case, "**", "법원_목록.json"), recursive=True)
    for f in files:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for kind, v in d.items():
            for r in (v.get("rows", []) if isinstance(v, dict) else []):
                no = (r.get("사건번호") or "").split(",")[0].strip()
                rows.append({"src": "법원-" + (r.get("종류") or kind), "id": no, "org": r.get("기관") or "",
                             "date": r.get("일자") or r.get("게시일") or "", "title": r.get("제목") or "", "extra": "",
                             "q": r.get("검색어") or "", "court_id": str(r.get("id") or "")})
    return files, rows


# 좁은 검색어: 받아 둔 목록에 걸린 줄이 이만큼 이하인 검색어. 규정 문언 그대로 같은 꼭 맞춘 검색어여서 줄마다 가린다.
# 2026. 11. 11. `/하자보완`: 최문희 강등 사건 11. 6. 첫 검색에서 규정 문언 그대로 넣은 검색어(3줄)에 걸린, 쟁점에 불리한 확정 판결을
# 스니펫에 그 판단이 있는데도 목록에서 버렸다. 낱말에 걸리지 않아 다시 훑기와 관문을 지났고, 담당 노무사 "케이스가 없다는게 뭔가
# 좀 이상해서"로 11. 10. 세 번째 검색에서야 찾았다. 그때 사건 보고서 27개를 같은 낱말로 다시 훑으니 처리를 적을 줄이 286줄(보고서마다
# 10줄 안팎) 늘었다.
NARROW = 3


def queries(q):
    """목록 줄의 '출처'(LBOX 는 그 줄을 건 검색어들을 ' / ' 로 잇는다, 법제처는 '검색어')."""
    return [x.strip() for x in (q or "").split(" / ") if x.strip()]


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


def row_key(r):
    """처리를 이을 때 줄을 알아보는 열쇠. 번호가 있으면 번호, 없거나 가려졌으면 id 와 제목 앞부분."""
    return number_key(r) or "#%s|%s" % (sq(r["id"]), sq(r["title"])[:40])


def old_handling(paths):
    """앞서 쓴 재확인 보고서의 '기록에 없는 줄' 표에서 줄마다 적은 처리. {열쇠: 처리}. 앞의 파일이 먼저이다."""
    got = {}
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        text = open(p, encoding="utf-8", errors="replace").read()
        k = text.find("\n## 기록에 없는 줄")
        if k < 0:
            continue
        part = text[k + 1:]
        m = re.search(r"\n## ", part)
        head = None
        for ln in (part[:m.start()] if m else part).splitlines():
            s = ln.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if head is None:
                head = cells
                if "처리" not in head:
                    break
                continue
            if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
                continue
            row = dict(zip(head, cells + [""] * (len(head) - len(cells))))
            h = row.get("처리", "").strip()
            if h in EMPTY:
                continue
            key = row_key({"src": row.get("출처", ""), "id": unquote(row.get("사건번호·문서번호", "")), "title": row.get("제목", "")})
            got.setdefault(key, h)
    return got


def docx_text(path):
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            xml = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist()
                          if n in ("word/document.xml", "word/footnotes.xml"))
    except (zipfile.BadZipFile, OSError, KeyError):
        return ""
    return re.sub(r"<[^>]+>", "", xml)


def record_text(case):
    parts = []
    for f in glob.glob(os.path.join(case, "**", "*.md"), recursive=True) + glob.glob(os.path.join(case, "**", "*.docx"), recursive=True):
        rel = os.path.relpath(f, case).replace("\\", "/")
        dirs, base = rel.split("/")[:-1], os.path.basename(f)
        if any(seg in SKIP_DIRS or harvest_dir(seg) for seg in dirs) or base.startswith(("수확목록_재확인", "법제처_", "법원_본문_",
                                                                                          "법원_게시물_", "~$")):
            continue
        if not os.path.isfile(f):      # 이름이 .md 로 끝나는 폴더(2026. 11. 10. comwel.py --out '…_심급.md')를 열면 Windows 가 '권한 없음'을 낸다
            continue
        parts.append(docx_text(f) if f.endswith(".docx") else open(f, encoding="utf-8", errors="replace").read())
    return sq("\n".join(parts))


def body_heads(case):
    heads = []
    for f in glob.glob(os.path.join(case, "**", "*.md"), recursive=True):
        rel = os.path.relpath(f, case).replace("\\", "/")
        if not any(harvest_dir(seg) for seg in rel.split("/")[:-1]) or not os.path.isfile(f):
            continue
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
    court_files, court = load_court(case)
    lbox_files = glob.glob(os.path.join(case, "**", "LBOX_목록*.tsv"), recursive=True) + (a.lbox or [])
    lbox = []
    for f in lbox_files:
        lbox += load_lbox_file(f)
    for r in lbox:                                 # 주소 그대로 저장된 id('%EA%B5%AD…')는 번호를 찾을 수 없으므로 글자로 푼다
        r["id"] = unquote(r["id"])
    seen, rows, 검색어들, 줄_검색어 = set(), [], {}, {}
    # 법고을(법원 누리집 목록의 '법고을')은 법제처와 같은 법원도서관 판례 자료이다. 법제처 줄과 사건번호가 같은 법원 줄은 한 줄로 둔다
    법제처_번호 = {number_key(r) for r in law} - {""}
    for r in law + court + lbox:                   # 같은 줄이 여러 수확·파일에 있으면 하나로
        key = (r["src"].split("-")[0], sq(r["id"]) or sq(r["title"]))
        for q in queries(r.get("q")):
            검색어들.setdefault((key[0], q), set()).add(key[1])
            줄_검색어.setdefault(key, []).append(q)
        if key in seen or (key[0] == "법원" and number_key(r) in 법제처_번호):
            continue
        seen.add(key)
        rows.append(r)
    좁은 = {sq_ for sq_, ids in 검색어들.items() if len(ids) <= NARROW}      # (출처, 검색어). 같은 글의 검색어도 법제처와 LBOX 는 따로 센다
    recs, heads = record_text(case), body_heads(case)
    hits = []
    for r in rows:
        hay = sq(r["title"] + " " + r.get("extra", ""))
        got = [w for w in words if all(sq(p) in hay for p in w.split("+") if sq(p))]   # '발전+정비'는 둘 다 든 줄
        key = (r["src"].split("-")[0], sq(r["id"]) or sq(r["title"]))
        got += ["좁은 검색어 " + q for q in dict.fromkeys(줄_검색어.get(key, [])) if (key[0], q) in 좁은]
        if not got:
            continue
        k = number_key(r)
        r["낱말"] = ", ".join(got)
        r["기록"] = ("있음" if k in recs else "없음") if k else "번호 없음"
        r["본문"] = ("받음" if k and k in heads else "안 받음") if r["src"].startswith(("법제처", "법원")) else "—"
        hits.append(r)
    order = {"없음": 0, "번호 없음": 1, "있음": 2}
    hits.sort(key=lambda r: (order[r["기록"]], r["src"], r["date"]), reverse=False)
    miss = [r for r in hits if r["기록"] != "있음"]
    done = old_handling([a.out] + list(a.잇기 or []))      # 다시 돌려도 줄마다 적어 둔 처리는 남긴다
    for r in miss:
        r["처리"] = cell(done.get(row_key(r), ""))
    out = ["# 수확 목록 제목 다시 훑기 — %s" % os.path.basename(case), "",
           "낱말: %s" % ", ".join(words),
           "좁은 검색어(목록에 걸린 줄이 %d줄 이하인 검색어) %d개 — 그 줄은 낱말과 관계없이 함께 가린다" % (NARROW, len(좁은)),
           "법제처 목록 %d개 파일 · %d줄 / 법원 누리집 목록 %d개 파일 · %d줄 / LBOX 목록 %d개 파일 · %d줄(같은 줄 합친 뒤 %d줄)"
           % (len(files), len(law), len(court_files), len(court), len(lbox_files), len(lbox), len(rows)),
           "걸린 줄 %d건 — 기록에 있음 %d건, 없음 %d건(그 가운데 법제처·법원 본문을 받은 것 %d건), 번호가 없어 가리지 못한 것 %d건"
           % (len(hits), len(hits) - len(miss), sum(1 for r in miss if r["기록"] == "없음"),
              sum(1 for r in miss if r["기록"] == "없음" and r["본문"] == "받음"), sum(1 for r in miss if r["기록"] == "번호 없음")),
           "처리 칸이 빈 줄 %d건 — 기록에 없는 줄과 번호가 없는 줄은 '처리' 칸에 줄마다 무엇을 하였는지 적는다(같은 --out 으로 다시 돌려도 이어진다)"
           % sum(1 for r in miss if not r["처리"]),
           ""]
    if not lbox_files:
        out += ["LBOX 목록 파일이 없다. LBOX 를 멈춘 동안(`lbox-검색` 맨 앞 '사용 중지')에는 그대로 두고 법제처·법원 누리집 목록만 본다. "
                "그 밖에는 조종 탭에 모은 목록이 남아 있으면 `lboxUnread`로, 없으면 검색기록의 검색어로 다시 수확해 본다(`/검토의견` 4-2단계, `/서면` 8-1단계 ⑧).", ""]
    for title, part in (("기록에 없는 줄(본문을 읽고 반영하거나 유사 사례 표에 미반영 이유를 적고, 줄마다 '처리' 칸에 적는다)", miss),
                        ("기록에 있는 줄", [r for r in hits if r["기록"] == "있음"])):
        more = part is miss
        out += ["## %s" % title, "", "| 출처 | 사건번호·문서번호 | 일자 | 기관·법원 | 제목 | 걸린 낱말 | 기록 | 본문 |" + (" 처리 |" if more else ""),
                "|---|---|---|---|---|---|---|---|" + ("---|" if more else "")]
        out += ["| %s | %s | %s | %s | %s | %s | %s | %s |" % (cell(r["src"]), cell(r["id"]), cell(r["date"]), cell(r["org"], 20),
                                                              cell(r["title"], 90), cell(r["낱말"]), r["기록"], r["본문"])
                + (" %s |" % r["처리"] if more else "") for r in part]
        out.append("")
    text = "\n".join(out)
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(text)
        print("씀:", a.out)
    print(text if not a.out else "\n".join(out[:7]))


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
                c = [BREAKS.sub(" ", x) for x in (c + [""] * 6)[:6]]
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
    s.add_argument("--out", help="결과를 쓸 파일(.md). 있던 파일이면 줄마다 적어 둔 처리를 잇는다")
    s.add_argument("--잇기", nargs="*", help="처리를 이어 올 앞선 재확인 보고서(최종 관문이 쓴다)")
    s2 = sub.add_parser("lbox-save")
    s2.add_argument("results", nargs="+", help="lboxRowsDump 결과가 저장된 파일")
    s2.add_argument("--out", required=True, help="{사건 폴더}/작업/LBOX_목록.tsv")
    a = ap.parse_args()
    scan(a) if a.cmd == "scan" else lbox_save(a)


if __name__ == "__main__":
    main()
