# -*- coding: utf-8 -*-
"""인용 대조표를 원문 파일·산출물과 기계로 맞대어 본다(공통/자체검토.md 4절). 모델을 쓰지 않는다.

    python -B 공통/scripts/cite_check.py "{사건 폴더}/작업/인용대조표.md" --target "{산출물.md 또는 .docx}"

대조표는 머리줄에 '사건 표시'와 '원문 문장' 칸이 있는 마크다운 표이다. 칸 안에는 세로줄(|)을 쓰지 않는다.
보는 것
  1) 원문 문장이 '원문' 칸의 파일에 글자 그대로 있는가(공백·줄바꿈·따옴표 모양은 무시, 가운데 줄임 … 은 앞뒤 조각이 차례로 있는지)
  2) 그 파일에 사건번호(문서번호)와 선고일(회시일), 사건 표시의 법원 이름이 있는가(법원은 '서울고법'·'광주지법' 같은 줄임말과 같게 본다)
  3) 산출물에 그 사건번호와 선고일, 대조표의 본문 문장이 그대로 있는가
  4) 산출물에 나오는 사건번호 가운데 대조표에 줄이 없는 것. 본문(서면 MD 는 '---' 위, DOCX 는 전부)에 나오는 번호는 본문 인용 줄이나
     참고 줄이 있어야 하고, 하단 목록 줄(서면 대조표의 ①②③·'참고(하단 ②)')이나 뺀 줄만 있으면 불일치이다. 하단 목록의 번호는
     하단 목록 줄과 뺀 줄도 받친다(하단 메모가 그 판결을 뺀 까닭을 적는 자리이고, 뺀 줄도 1)·2)로 원문과 맞댄다)
  5) '확정' 칸에 심리불속행으로 적은 대법원 번호가 산출물에 나오면 그 곁에 '심리불속행'이 있는가
  6) 산출물에 '{법원} {날짜} 선고 {사건번호}' 꼴로 적은 자리마다 그 법원·날짜가 대조표 사건 표시의 법원·선고일과 같은가. 같은 판결을
     여러 번 적으면 자리마다 본다(3)은 산출물 어딘가에 그 날짜가 있는지만 본다)
원문이 LBOX 보관함·화면에만 있어 파일이 없는 줄은 '원문' 칸에 '보관함 일치'나 '화면 확인'이라고 적혀 있으면 그렇게 세고,
없으면 원문 미확인으로 알린다. 불일치가 하나라도 있으면 종료 코드 1, 원문 미확인만 있으면 0 이다(보고에 따로 적는다).
번호 칸에 '참고(이 사건)'·'참고(대상 서면)'이라고 적고 원문 문장과 원문 칸을 비운 줄은 사건을 가리키기만 하는 줄이다(표지의 사건번호,
대상 서면이 이미 인용한 판례). 4)에 걸리지 않게 두는 줄이고 인용이 아니므로 원문과 맞대지 않고, 원문 미확인이 아니라 '사건 표시만'으로 따로 센다.
"""
import argparse
import html
import os
import re
import sys
import zipfile

# 사건번호: 연도(두 자리나 네 자리) + 사건부호(한글 1~3자) + 일련번호. 날짜·수량 낱말은 사건부호가 아니다
CASE = re.compile(r"(?<![0-9가-힣])((?:19|20)?\d{2})([가-힣]{1,3})(\d{1,7})(?![0-9])")
NOT_CODE = {"년", "월", "일", "면", "항", "조", "호", "건", "개", "명", "분", "쪽", "회", "원", "만", "천", "억", "차", "세", "층", "번", "동", "시", "주",
            "개월", "시간", "퍼센트"}
NOT_FIRST = "조항년월일면쪽"      # '제60조제5항'·'10월31일'처럼 붙여 쓴 조문·날짜를 사건번호로 읽지 않는다(이 글자로 시작하는 사건부호는 없다)
DATE = re.compile(r"((?:19|20)\d{2})\s*[.\-년]\s*(\d{1,2})\s*[.\-월]\s*(\d{1,2})")
QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "「": "", "」": "", "『": "", "』": "", "​": "", "﻿": ""})
POINTER = ("이 사건", "대상 서면")      # 번호 칸에 '참고'와 함께 이 말이 든 줄은 사건을 가리키기만 한다(공통/자체검토.md 3절)


# 사건 표시의 법원 이름. 지원은 본원 이름 뒤에 붙은 것만 보고, 뜻이 넓은 '…지원' 낱말 하나는 법원으로 읽지 않는다
COURT = (r"(?:[가-힣]+(?:고등법원|지방법원|행정법원|가정법원|회생법원|고법|지법|행법|가법)(?:\s*[가-힣]+지원)?"
         r"|대법원|특허법원|헌법재판소|헌재|[가-힣]*노동위원회)")
MARK = re.compile(r"(%s)?\s*((?:19|20)\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?\s*(?:선고|자)?\s*$" % COURT)
SHORT = (("고등법원", "고법"), ("지방법원", "지법"), ("행정법원", "행법"), ("가정법원", "가법"), ("헌법재판소", "헌재"))


def norm(s):
    return re.sub(r"\s+", "", s.translate(QUOTES))


def court_form(s):
    """법원 이름을 맞대는 꼴. 공백을 빼고 줄임말로 맞춘다(법제처 본문 머리는 '서울고법 2022-05-12 2021누40722' 꼴이다)."""
    s = norm(s)
    for a, b in SHORT:
        s = s.replace(a, b)
    return s


def same_court(a, b):
    """두 법원 이름이 같은가. 한쪽이 다른 쪽의 끝과 같으면 같게 본다('안산지원' ↔ '수원지방법원 안산지원'). 본원과 지원은 다르다."""
    a, b = court_form(a), court_form(b)
    return a.endswith(b) or b.endswith(a)


def marks(text):
    """'{법원} {날짜} 선고 {사건번호}' 꼴로 적은 자리 [(사건번호, 법원(없으면 ''), (연, 월, 일))]. 번호 바로 앞에 날짜가 있는 자리만 본다
    ('…, 2017두12346(병합)'처럼 앞 번호에 이어 적은 번호와 날짜 없이 적은 번호는 보지 않는다)."""
    out = []
    for m in CASE.finditer(text):
        y, c, n = m.groups()
        if c in NOT_CODE or c[0] in NOT_FIRST:
            continue
        b = MARK.search(text[max(0, m.start() - 60):m.start()])
        if b:
            out.append((y + c + n, b.group(1) or "", (int(b.group(2)), int(b.group(3)), int(b.group(4)))))
    return out


def mark_text(court, day):
    return ("%s %d. %d. %d." % ((court,) + day)).strip()


def cases(text):
    return {y + c + n for y, c, n in CASE.findall(text) if c not in NOT_CODE and c[0] not in NOT_FIRST}


def dates(text):
    return {(int(y), int(m), int(d)) for y, m, d in DATE.findall(text)}


def read_target(path):
    """산출물의 글. MD 는 보완 메모 앞까지, DOCX 는 본문과 각주."""
    if path.lower().endswith(".docx"):
        out = []
        with zipfile.ZipFile(path) as z:
            for part in ("word/document.xml", "word/footnotes.xml"):
                if part in z.namelist():
                    x = z.read(part).decode("utf-8")
                    out.append(html.unescape("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", x))))
        return "\n".join(out)
    t = open(path, encoding="utf-8").read()
    i = t.find("## 보완 메모")
    return t if i < 0 else t[:i]


def table_rows(path):
    """대조표의 줄을 {칸 이름: 글} 로 돌려준다."""
    rows, head = [], None
    for line in open(path, encoding="utf-8").read().splitlines():
        if not line.strip().startswith("|"):
            head = None if not line.strip() else head
            continue
        cells = [c.strip().replace("<br>", " ") for c in line.strip().strip("|").split("|")]
        if "사건 표시" in cells and "원문 문장" in cells:
            head = cells
        elif head and not all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            rows.append(dict(zip(head, cells + [""] * (len(head) - len(cells)))))
    return rows


def pieces(quote):
    """줄임표로 끊은 조각. 따옴표와 짧은 조각은 버린다."""
    out = [norm(p).strip("'\"") for p in re.split(r"…|\.\.\.", quote)]
    return [p for p in out if len(p) >= 6]


def upper_courts(cell):
    """'확정' 칸의 대법원 사건번호와, 그 번호에 심리불속행 표기가 붙었는지. [(번호, 참·거짓)]."""
    out = []
    for c in re.findall(r"대법원\s*(?:(?:19|20)\d{2}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*선고\s*)?((?:19|20)?\d{2}[가-힣]{1,3}\d{1,7})", cell):
        out.append((c, bool(re.search(r"%s.{0,15}심리불속행|심리불속행.{0,15}%s" % (c, c), cell))))
    return out


def in_order(text, parts):
    i = 0
    for p in parts:
        k = text.find(p, i)
        if k < 0:
            return p
        i = k + len(p)
    return None


RULE = re.compile(r"^\s*-{3,}\s*$")      # 서면 초안의 본문과 하단 세 목록을 가르는 줄(docx_merge.py·citation_check.py 와 같은 규칙)


def brief_table(table):
    """서면의 대조표인가(라운드 폴더 아래). 하단 세 목록(①②③)은 서면 초안에만 있다."""
    return any(re.fullmatch(r"라운드\d+", seg) for seg in re.split(r"[\\/]", os.path.abspath(table)))


def is_gone(row):
    """뺀 인용 줄(번호 칸이나 본문 문장 칸에 '뺌')."""
    return "뺌" in row.get("번호", "") or row.get("본문 문장", "").strip().startswith("뺌")


def is_body(row, table=None):
    """본문 인용 줄인가. 번호 칸에 '참고'가 있는 줄, 뺀 줄, 서면 대조표에서 하단 목록의 번호(①②③)로 시작하는 줄은 본문 인용이 아니다.
    2026. 11. 3. '② 2.'처럼 적은 하단 메모 줄까지 판결문 PDF 와 '사람 판정'을 요구하였다. 검토의견은 질의 번호를 '[질의 ①]'처럼 적으므로
    (`1_검토의견/CLAUDE.md` 공단 자문 짜임) 그 대조표의 ①②③ 줄은 본문 인용으로 본다. table 을 주지 않으면 서면 대조표로 본다."""
    no = row.get("번호", "").strip()
    if "참고" in no or is_gone(row):
        return False
    return not (re.match(r"[①②③]", no) and (table is None or brief_table(table)))


def body_and_bottom(path, text):
    """산출물의 본문과 하단 목록. 서면 MD 는 첫 줄이 아닌 '---' 줄 아래가 하단 세 목록이고(`4_서면작성/CLAUDE.md`), DOCX 에는 하단 목록이 없다."""
    if path.lower().endswith(".docx"):
        return text, ""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i and RULE.match(line):
            return "\n".join(lines[:i]), "\n".join(lines[i + 1:])
    return text, ""


def source_files(cell, table_path):
    """'원문' 칸에 적힌 파일의 자리. 칸의 경로는 표 폴더·라운드·사건 폴더·저장소 루트 가운데 어디를 기준으로 적어도 찾는다.
    2026. 11. 3. 사건 폴더 기준으로 적은 줄을 찾지 못해 인용 대조가 원문 미확인으로 넘어가고, final_check.py 는 따로 찾다가 있는 파일을 없다고 막았다."""
    names = re.findall(r"`([^`]+)`", cell) or [w for w in re.split(r"\s+", cell) if re.search(r"\.(md|txt)$", w)]
    d = os.path.dirname(os.path.abspath(table_path))
    bases = ["", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))]
    for _ in range(4):      # 표 폴더 → 라운드 → 사건 폴더 → 사건 묶음
        bases.append(d)
        d = os.path.dirname(d)
    out = []
    for n in names:
        p = next((os.path.join(b, n) if b else n for b in bases if os.path.isfile(os.path.join(b, n) if b else n)), None)
        if p:
            out.append(p)
    return out


def source_text(cell, table_path, key):
    """'원문' 칸에 적힌 파일의 글. 법제처 묶음이면 그 사건의 대목만. 없으면 None."""
    for p in source_files(cell, table_path):
        if p.lower().endswith(".pdf"):      # PDF 글은 cite_pdf_check.py 가 본다
            continue
        t = open(p, encoding="utf-8", errors="replace").read()
        parts = re.split(r"\n(?=## \[)", t)
        if len(parts) > 2:      # 여러 건을 묶은 법제처 본문 파일
            hit = [s for s in parts if key and key in norm(s[:400])] or [s for s in parts if key and key in norm(s)]
            t = hit[0] if hit else ""
        return t
    return None


def check(table_path, targets):
    rows = table_rows(table_path)
    bad, unseen, only, lines = 0, 0, 0, []
    tgt = [(p, read_target(p)) for p in targets]
    for r in rows:
        mark = r.get("사건 표시", "")
        nums = sorted(cases(mark))
        key = norm(nums[0]) if nums else norm(mark.split(",")[0])
        day = dates(mark)
        no = r.get("번호", "")
        pointer = "참고" in no and any(w in no for w in POINTER)      # 사건을 가리키기만 하는 줄(표지의 사건번호, 대상 서면이 이미 인용한 판례)
        name = (no + " " + mark).strip()
        notes = []
        # 1)·2) 원문 파일
        cell = r.get("원문", "")
        src = source_text(cell, table_path, key)
        parts = pieces(r.get("원문 문장", ""))
        if src is None:
            if "보관함 일치" in cell or "화면 확인" in cell:
                notes.append("원문: " + ("보관함 확인" if "보관함 일치" in cell else "화면 확인"))
            elif pointer and not parts:      # 원문 문장을 적지 않은 가리킴 줄은 인용이 아니다. 원문 미확인으로 세지 않는다
                only += 1
                notes.append("사건 표시만(인용이 아니어서 대조하지 않음)")
            else:
                unseen += 1
                notes.append("원문 미확인(파일도 보관함 표시도 없음)")
        else:
            s = norm(src)
            if not parts:
                bad += 1; notes.append("불일치: 원문 문장 칸이 비었다")
            else:
                miss = in_order(s, parts)
                if miss:
                    bad += 1; notes.append("불일치: 원문 파일에 없는 조각 '%s…'" % miss[:30])
            if key and key not in s:
                bad += 1; notes.append("불일치: 원문 파일에 %s 없음" % key)
            if day and not (day & dates(src)):
                bad += 1; notes.append("불일치: 원문 파일에 날짜 %s 없음" % sorted(day))
            # 2026. 11. 9. `/하자보완`: 11. 6. 판결문 PDF 를 받지 않게 된 뒤로 사건 표시의 법원은 원문과 맞대는 곳이 없었다(PDF 대조만 보았다)
            court = next((c for n_, c, _ in marks(mark) if nums and n_ == nums[0] and c), "")
            if court and court_form(court) not in court_form(src):
                bad += 1; notes.append("불일치: 원문 파일에 법원 %s 없음" % court)
        # 3) 산출물
        gone = not is_body(r, table_path)      # 뺀 인용과 참고 줄(원심, 하단 목록 등)은 산출물과 맞대지 않는다
        for p, t in ([] if gone else tgt):
            n = norm(t)
            if key and key not in n:
                bad += 1; notes.append("불일치: 산출물에 %s 없음(%s)" % (key, os.path.basename(p)))
            if day and not (day & dates(t)):
                bad += 1; notes.append("불일치: 산출물에 날짜 %s 없음(%s)" % (sorted(day), os.path.basename(p)))
            miss = in_order(n, pieces(r.get("본문 문장", "")))
            if miss:
                bad += 1; notes.append("불일치: 산출물에 없는 본문 문장 조각 '%s…'(%s)" % (miss[:30], os.path.basename(p)))
            for c, says in upper_courts(r.get("확정", "")):      # 확정 칸이 심리불속행인 상급심을 산출물이 다르게 적었는지(적지 않은 글은 건드리지 않는다)
                if says and c in n and not re.search(r"%s.{0,15}심리불속행|심리불속행.{0,15}%s" % (c, c), n):
                    bad += 1; notes.append("불일치: 산출물의 대법원 %s 확정 표기에 심리불속행이 없다(%s)" % (c, os.path.basename(p)))
        lines.append(("%s — %s" % (name, " / ".join(notes) if notes else "일치")))
    # 4) 대조표에 줄이 없는 사건번호. 본문(서면 MD 는 '---' 위, DOCX 는 전부)의 번호는 본문 인용 줄이나 참고 줄(가리킴·다른 심급)이 받쳐야 한다.
    #    하단 목록 줄과 뺀 줄만 있는 번호가 본문에 있으면 그 문장은 3)을 거치지 않는다(2026. 11. 3. 점검: '② 2.' 줄이나 '뺌' 줄 하나로 본문 인용이 빠져나갔다).
    #    하단 목록에서는 뺀 줄도 받친다. 2026. 11. 4. `/하자보완`: 하단 ① 메모가 '이번 판에서 … 뺐습니다'라고 적으며 뺀 판결 번호를 들자
    #    '본문 인용 줄을 두라'고 막았다(본문이 아닌 자리에 본문 인용 줄을 요구하였다)
    def nums(rs):
        out = set()
        for r in rs:
            out |= cases(" ".join(r.values()))
        return out
    ref = [r for r in rows if "참고" in r.get("번호", "") and "하단" not in r.get("번호", "") and not is_gone(r)]
    body_known = nums([r for r in rows if is_body(r, table_path)] + ref)
    bottom_known = nums([r for r in rows if not is_gone(r) and not is_body(r, table_path)])
    gone_known = nums([r for r in rows if is_gone(r)])
    for p, t in tgt:
        body, bottom = body_and_bottom(p, t)
        seen = set()
        for part, ok in ((body, body_known), (bottom, body_known | bottom_known | gone_known)):
            for c in sorted(cases(part) - ok - seen):
                seen.add(c)
                bad += 1
                if c in bottom_known:
                    lines.append("불일치: 산출물 본문의 %s 가 대조표에 하단 목록 줄로만 있다 — 본문 인용이면 번호 칸을 본문의 항·문단으로 적은 줄을 둔다(%s)"
                                 % (c, os.path.basename(p)))
                elif c in gone_known:
                    lines.append("불일치: 뺀 인용의 %s 가 산출물에 남아 있다 — 지우거나, 남길 것이면 본문 인용 줄을 둔다(%s)" % (c, os.path.basename(p)))
                else:
                    lines.append("불일치: 산출물의 %s 가 대조표에 없다(%s)" % (c, os.path.basename(p)))
    # 6) 산출물에 적은 판결 표시를 자리마다 대조표의 사건 표시와 맞댄다. 2026. 11. 9. `/하자보완`: 3)은 산출물 어딘가에 그 날짜가 있는지만 보아
    #    같은 판결을 두 번 적은 산출물의 둘째 자리 날짜가 틀려도 지나갔고, 법원 이름은 어디서도 맞대지 않았다. 실제 산출물 사본의 표시 자리를
    #    하나씩 바꾸어 보니 날짜 302곳 가운데 122곳, 법원 301곳 가운데 246곳이 지나갔다(사건 표시를 잘못 옮기는 것, 루트 CLAUDE.md 판례 인용 ①)
    표시 = {}
    for r in rows:
        for c, court, d in marks(r.get("사건 표시", "")):
            표시.setdefault(c, set()).add((court, d))
    for p, t in tgt:
        틀림 = {}
        for c, court, d in marks(t):
            if c in 표시 and not any(d == d2 and (not court or not c2 or same_court(court, c2)) for c2, d2 in 표시[c]):
                틀림[(c, court, d)] = 틀림.get((c, court, d), 0) + 1
        for (c, court, d), k in 틀림.items():
            bad += k
            lines.append("불일치: 산출물의 '%s 선고 %s'%s 가 대조표의 사건 표시(%s)와 다르다 — 원문으로 맞는 쪽을 확인해 고친다(%s)"
                         % (mark_text(court, d), c, " (%d곳)" % k if k > 1 else "",
                            " / ".join(mark_text(c2, d2) for c2, d2 in sorted(표시[c])), os.path.basename(p)))
    return {"줄": len(rows), "불일치": bad, "원문미확인": unseen, "사건표시만": only, "내용": lines}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table", help="인용 대조표(.md)")
    ap.add_argument("--target", nargs="*", default=[], help="산출물(.md 는 보완 메모 앞까지, .docx 는 본문과 각주)")
    a = ap.parse_args()
    try:
        res = check(a.table, a.target)
    except PermissionError as e:      # 담당자가 Word 에서 열어 둔 docx 는 읽히지 않는다. 닫힌 뒤에 다시 돌리거나 사본으로 본다
        print("읽지 못함(다른 프로그램에서 열려 있다):", e.filename)
        sys.exit(2)
    print("\n".join(res["내용"]))
    print("대조표 %d줄 · 불일치 %d건 · 원문 미확인 %d줄" % (res["줄"], res["불일치"], res["원문미확인"])
          + (" · 사건 표시만 %d줄" % res["사건표시만"] if res["사건표시만"] else ""))
    sys.exit(1 if res["불일치"] or not res["줄"] else 0)


if __name__ == "__main__":
    main()
