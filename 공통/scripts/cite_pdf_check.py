# -*- coding: utf-8 -*-
"""서면·검토의견 본문에 인용한 판결을 판결문 PDF 원본과 맞댄다(공통/자체검토.md 4-1절 4.). 모델을 쓰지 않는다.

    python -B 공통/scripts/cite_pdf_check.py "{사건 폴더}/라운드N/작업/인용대조표.md" "{사건 폴더}/라운드N/참고자료/인용판결_PDF"
    python -B 공통/scripts/cite_pdf_check.py "1_검토의견/사건/{의뢰인}_{검토내용}/작업/인용대조표.md" "1_검토의견/사건/{의뢰인}_{검토내용}/작업/인용판결_PDF" --target "{산출물}"

PDF 는 lbox-검색 9항 lboxPdfZip 으로 받은 판결문이고, 파일 이름에 사건번호가 들어 있어야 한다.
보는 것
  1) 대조표의 본문 인용 줄(번호 칸에 '참고'·'뺌'이 없고 사건 표시에 '법원'이 든 줄)마다 그 사건번호의 PDF 가 있는가
  2) PDF 첫 두 면에 사건 표시의 법원·선고일·사건번호가 있는가
  3) '원문 문장'이 PDF 글에 글자 그대로 있는가(공백·줄바꿈·따옴표 모양은 무시, 줄임표 … 로 나눈 조각이 차례로 있는지.
     떨어진 대목을 '"…" / "…"' 처럼 따옴표로 따로 묶어 적었으면 덩이마다 따로 찾는다)
  4) '확정' 칸에 적은 대법원 상급심의 처리. 그 판결문 PDF 가 있으면 심리불속행 기각인지 판결문으로 보아 칸의 표기와 맞대고,
     없으면 칸에 '심리불속행'이나 '문서 없음'이 적혀 있을 때만 넘어간다. LBOX 판결란의 '상고기각' 표시는 심리불속행 기각을 포함한다.
     --target 을 주면 산출물에 번호가 나오는 상급심만 본다(서면처럼 상급심을 본문에 적지 않는 글은 PDF 를 더 받지 않아도 된다)
찾은 자리마다 판시사항·판결요지 안인지, 가장 가까운 항목 머리(판단·주장·인정사실 등), 앞뒤 글, 앞 글에 든 '주장'·'원심' 같은
낱말을 보고서에 적는다. 그 문장이 판단 부분인지와 판결의 결론이 우리 주장과 같은 방향인지는 작성 세션이 PDF 를 직접 읽고
보고서 끝 '## 사람 판정' 표에 적는다. 보고서를 다시 만들어도 그 절은 그대로 남긴다. 문제가 하나라도 있으면 종료 코드 1 이다.
"""
import argparse
import os
import re
import sys

import pymupdf as fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cite_check import QUOTES, cases, dates, norm, pieces, read_target, table_rows, upper_courts  # noqa: E402

PAGE_NO = re.compile(r"(?m)^\s*-\s*\d{1,3}\s*-\s*$")      # 면 아래의 '- 3 -' 는 문장 사이에 끼어 찾기를 막는다
SHIMRI = re.compile(r"제5조(?:제1항)?에(?:의하여|따라)(?:이)?상고를(?:모두)?기각")      # 공백을 뺀 글에서 찾는다(상고심절차에 관한 특례법 제5조에 따른 기각)
HEAD = re.compile(r"(?:^|\s)((?:[1-9]\.|[가-하]\.|[1-9]\)|\([1-9]\)|[가-하]\))\s?[^ ]{1,4}[^.]{0,40}?"
                  r"(?:판단|주장|요지|인정사실|기초사실|사실관계|법리|결론|관하여|여부))")
WARN = ("주장", "원심", "인정사실", "기초사실", "다투", "제1심")      # 앞 글에 있으면 판단 부분인지 다시 읽을 낱말
COURT = re.compile(r"^(.*?)\s*(?:19|20)\d{2}\s*\.")


def pdf_texts(path):
    """면마다의 글. 면 번호 줄은 걷어 낸다."""
    with fitz.open(path) as d:
        return [PAGE_NO.sub(" ", pg.get_text()) for pg in d]


def squash_map(text):
    """norm 과 같은 글(공백을 빼고 따옴표를 맞춘 글)과, 그 글자마다 원래 글(따옴표만 맞춘 글)의 자리."""
    t = text.translate(QUOTES)
    keep = [(ch, i) for i, ch in enumerate(t) if not ch.isspace()]
    return "".join(ch for ch, _ in keep), [i for _, i in keep], t


def passages(cell):
    """원문 문장 칸의 인용 덩이. 따옴표로 따로 묶은 덩이가 있으면 덩이마다, 없으면 칸 전체."""
    return re.findall(r'"([^"]{6,})"', cell.translate(QUOTES)) or [cell]


def part_label(sq, k):
    """찾은 자리가 판시사항·판결요지 안인지. 그 밖이면 '본문'."""
    for name, nxt in (("판시사항", ("판결요지", "참조조문")), ("판결요지", ("참조조문", "참조판례", norm("대 법 원 판 결"), "주문"))):
        a = sq.find(name)
        if a < 0 or k < a:
            continue
        ends = [e for e in (sq.find(n, a + len(name)) for n in nxt) if e > a]
        if ends and k < min(ends):
            return name
    return "본문"


def check_upper(cell, own, files, targets, used):
    """'확정' 칸의 대법원 상급심을 판결문과 맞댄다. (문제 수, 보고서 줄, 짧은 표시)를 돌려준다."""
    bad, body, notes = 0, [], []
    for c, says in upper_courts(cell):
        if c in own or (targets is not None and not any(c in t for t in targets)):
            continue
        path = files.get(c)
        if path:
            used.add(path)
            real = bool(SHIMRI.search(norm("\n".join(pdf_texts(path)))))
            body.append("- 상급심 대법원 %s: 판결문 PDF `%s` — %s" % (c, os.path.basename(path), "심리불속행 기각" if real else "상고이유를 판단한 판결"))
            if real != says:
                bad += 1
                notes.append("확정 칸의 대법원 %s 표기가 판결문과 다름(판결문은 %s)" % (c, "심리불속행 기각" if real else "심리불속행이 아님"))
                body.append("  - **확정 칸의 표기가 판결문과 다르다** — 칸과 산출물을 판결문대로 고친다")
        elif says or re.search(r"%s.{0,40}문서 없음" % c, cell):
            body.append("- 상급심 대법원 %s: PDF 없음(칸의 표기대로, 보고에 적는다)" % c)
        else:
            bad += 1
            notes.append("확정 칸의 대법원 %s 판결문 PDF 없음" % c)
            body.append("- **상급심 대법원 %s 판결문 PDF 없음** — 받아서 실제 처리를 본다. LBOX 에 없으면 칸에 '문서 없음'을 적는다" % c)
    return bad, body, notes


def check(table, pdfdir, targets=None):
    rows = [r for r in table_rows(table)
            if not any(w in r.get("번호", "") for w in ("참고", "뺌")) and "법원" in r.get("사건 표시", "")]
    files = {}
    for n in sorted(os.listdir(pdfdir)):
        if n.lower().endswith(".pdf"):
            for c in cases(n):
                files.setdefault(c, os.path.join(pdfdir, n))
    tgt = None if targets is None else [norm(read_target(p)) for p in targets]
    used, bad, lines, body, cache = set(), 0, [], [], {}
    for r in rows:
        mark, no = r.get("사건 표시", ""), r.get("번호", "")
        nums = sorted(cases(mark), key=mark.find)
        path = next((files[c] for c in nums if c in files), None)
        body.append("## %s — %s" % (no, mark))
        if not nums or not path:
            bad += 1; body += ["- **PDF 없음**", ""]; lines.append("%s — PDF 없음" % no); continue
        used.add(path)
        if path not in cache:
            pages = pdf_texts(path)
            cache[path] = (pages,) + squash_map("\n".join(pages))
        pages, sq, pos, flat = cache[path]
        notes = []
        # 2) 첫 두 면의 사건 표시
        head = "\n".join(pages[:2])
        m = COURT.match(mark)
        miss = [w for w, ok in (("법원", m and norm(m.group(1)) in norm(head)),
                                ("선고일", dates(mark) and dates(mark) <= dates(head)),
                                ("사건번호", nums[0] in cases(head))) if not ok]
        body.append("- 파일 `%s` %d면, 첫 두 면의 사건 표시: %s" % (os.path.basename(path), len(pages), "없음 — " + "·".join(miss) if miss else "법원·선고일·사건번호 있음"))
        if miss:
            bad += 1; notes.append("첫 두 면에 " + "·".join(miss) + " 없음")
        # 3) 원문 문장
        groups = [pieces(q) for q in passages(r.get("원문 문장", ""))]
        if not any(groups):
            bad += 1; notes.append("원문 문장 칸이 비었다"); body.append("- **원문 문장 칸이 비었다**")
        for parts in groups:
            i = 0
            for p in parts:
                k = sq.find(p, i)
                if k < 0:
                    bad += 1; notes.append("PDF 에서 못 찾음: " + p[:30]); body.append("- **PDF 에서 못 찾음**: %s…" % p[:60]); continue
                i = k + len(p)
                a, b = pos[k], pos[min(k + len(p), len(pos) - 1)]
                before = re.sub(r"\s+", " ", flat[max(0, a - 6000):a])
                heads = HEAD.findall(before)
                warn = [w for w in WARN if w in before[-300:]]
                body += ["- 찾음(%s): %s…" % (part_label(sq, k), p[:50]),
                         "  - 가까운 항목 머리: %s" % (heads[-1].strip()[:70] if heads else "(찾지 못함)"),
                         "  - 앞 글: …%s" % before[-220:],
                         "  - 뒤 글: %s…" % re.sub(r"\s+", " ", flat[b:b + 140])]
                if warn:
                    body.append("  - 앞 글 300자에 든 낱말: %s — 판단 부분인지 다시 읽는다" % "·".join(warn))
        # 4) '확정' 칸의 상급심
        b, more, upper_notes = check_upper(r.get("확정", ""), nums, files, tgt, used)
        bad += b; body += more; notes += upper_notes
        body += ["- 대조표 자리: %s" % r.get("자리", "")[:120],
                 "- 대조표 주문·결론: %s / 확정: %s" % (r.get("주문·결론", "")[:120], r.get("확정", "")[:80]), ""]
        lines.append("%s — %s" % (no, " / ".join(notes) if notes else "일치"))
    extra = sorted(os.path.basename(p) for p in set(files.values()) - used)
    if extra:
        body += ["## 대조표 본문 줄이 가리키지 않는 PDF", ""] + ["- `%s`" % n for n in extra] + [""]
    return {"줄": len(rows), "판결": len(used), "문제": bad, "내용": lines, "보고서": body}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table", help="인용 대조표(.md)")
    ap.add_argument("pdfdir", help="판결문 PDF 폴더(파일 이름에 사건번호)")
    ap.add_argument("--out", help="보고서(.md). 주지 않으면 대조표 옆의 판결원문_PDF대조.md")
    ap.add_argument("--target", nargs="*", help="산출물(.md·.docx). 주면 산출물에 번호가 나오는 상급심만 본다")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.table)), "판결원문_PDF대조.md")
    res = check(a.table, a.pdfdir, a.target)
    keep = ""
    if os.path.isfile(out):      # 작성 세션이 적은 '사람 판정' 절은 다시 만들어도 남긴다
        old = open(out, encoding="utf-8").read()
        k = old.find("\n## 사람 판정")
        keep = old[k:] if k >= 0 else ""
    head = ["# 판결문 PDF 원본 대조", "",
            "대조표 `%s` 의 본문 인용 %d줄(판결 %d건)을 `%s` 의 판결문 PDF 와 맞댄 결과이다(문제 %d건). "
            "판단 부분인지와 결론 방향은 작성 세션이 PDF 를 직접 읽어 끝의 '사람 판정' 표에 적는다(공통/자체검토.md 4-1절 4.)."
            % (a.table, res["줄"], res["판결"], a.pdfdir, res["문제"]), ""]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(head + res["보고서"]).rstrip("\n") + "\n" + keep)
    print("\n".join(res["내용"]))
    print("본문 인용 %d줄 · 판결 %d건 · 문제 %d건 → %s" % (res["줄"], res["판결"], res["문제"], out))
    sys.exit(1 if res["문제"] or not res["줄"] else 0)


if __name__ == "__main__":
    main()
