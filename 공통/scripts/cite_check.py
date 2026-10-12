# -*- coding: utf-8 -*-
"""인용 대조표를 원문 파일·산출물과 기계로 맞대어 본다(공통/자체검토.md 4절). 모델을 쓰지 않는다.

    python -B 공통/scripts/cite_check.py "{사건 폴더}/작업/인용대조표.md" --target "{산출물.md 또는 .docx}"

대조표는 머리줄에 '사건 표시'와 '원문 문장' 칸이 있는 마크다운 표이다. 칸 안에는 세로줄(|)을 쓰지 않는다.
보는 것
  1) 원문 문장이 '원문' 칸의 파일에 글자 그대로 있는가(공백·줄바꿈·따옴표 모양은 무시, 가운데 줄임 … 은 앞뒤 조각이 차례로 있는지)
  2) 그 파일에 사건번호(문서번호)와 선고일(회시일)이 있는가
  3) 산출물에 그 사건번호와 선고일, 대조표의 본문 문장이 그대로 있는가
  4) 산출물에 나오는 사건번호 가운데 대조표에 줄이 없는 것
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


def norm(s):
    return re.sub(r"\s+", "", s.translate(QUOTES))


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


def in_order(text, parts):
    i = 0
    for p in parts:
        k = text.find(p, i)
        if k < 0:
            return p
        i = k + len(p)
    return None


def source_text(cell, table_path, key):
    """'원문' 칸에 적힌 파일의 글. 법제처 묶음이면 그 사건의 대목만. 없으면 None."""
    names = re.findall(r"`([^`]+)`", cell) or [w for w in re.split(r"\s+", cell) if re.search(r"\.(md|txt)$", w)]
    bases = ["", os.path.dirname(table_path), os.path.dirname(os.path.dirname(table_path))]
    for n in names:
        for b in bases:
            p = os.path.join(b, n) if b else n
            if os.path.isfile(p):
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
        # 3) 산출물
        gone = any(w in r.get("번호", "") for w in ("뺌", "참고")) or r.get("본문 문장", "").startswith("뺌")      # 뺀 인용과 참고 줄(원심 등)은 산출물과 맞대지 않는다
        for p, t in ([] if gone else tgt):
            n = norm(t)
            if key and key not in n:
                bad += 1; notes.append("불일치: 산출물에 %s 없음(%s)" % (key, os.path.basename(p)))
            if day and not (day & dates(t)):
                bad += 1; notes.append("불일치: 산출물에 날짜 %s 없음(%s)" % (sorted(day), os.path.basename(p)))
            miss = in_order(n, pieces(r.get("본문 문장", "")))
            if miss:
                bad += 1; notes.append("불일치: 산출물에 없는 본문 문장 조각 '%s…'(%s)" % (miss[:30], os.path.basename(p)))
        lines.append(("%s — %s" % (name, " / ".join(notes) if notes else "일치")))
    # 4) 대조표에 줄이 없는 사건번호
    known = set()
    for r in rows:
        known |= cases(" ".join(r.values()))
    for p, t in tgt:
        for c in sorted(cases(t) - known):
            bad += 1; lines.append("불일치: 산출물의 %s 가 대조표에 없다(%s)" % (c, os.path.basename(p)))
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
