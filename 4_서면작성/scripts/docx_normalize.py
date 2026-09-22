# -*- coding: utf-8 -*-
"""
docx_normalize.py — 서면 docx 마무리 점검·정리 도구

사용법
  python scripts/docx_normalize.py <파일.docx>            # 원문자 글꼴을 본문 한글 글꼴로 통일하여 같은 파일에 저장
  python scripts/docx_normalize.py <파일.docx> --check    # 고치지 않고 검출 건수만 보고 (0건이면 종료코드 0)
  python scripts/docx_normalize.py <파일.docx|md> --words # 금지 낱말(뒷받침, 우선, 먼저, 첫째 …) 검출

원문자(①~⑳)를 담은 run은 프레임 Normal 스타일의 eastAsia 글꼴(통상 바탕체)로
ascii·hAnsi·eastAsia·cs를 모두 지정하고 hint="eastAsia"를 붙인다.
(2026. 9. 7. 이케아 사건 변호사 지적: 원문자가 본문과 다른 글꼴로 찍히는 문제)
"""
import sys, re, copy, io
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CIRC = re.compile(r"[①-⑳]")
BANNED = re.compile(r"뒷받침|국가기관인|객관적으로 확인|우선,|먼저,|다음으로,|마지막으로,|첫째|둘째|셋째|사료|살피건대|생각건대|요컨대|할 것입니다|다름 아|알 수 있습니다|입증합니다|증명합니다|방증|예상됩니다|본건|금번|재판장님")


def body_font(doc):
    rpr = doc.styles['Normal'].element.find(qn('w:rPr'))
    rf = rpr.find(qn('w:rFonts')) if rpr is not None else None
    return (rf.get(qn('w:eastAsia')) if rf is not None else None) or '바탕체'


def run_ok(r, font):
    rpr = r._r.find(qn('w:rPr'))
    rf = rpr.find(qn('w:rFonts')) if rpr is not None else None
    if rf is None:
        return False
    return all(rf.get(qn('w:' + k)) == font for k in ('ascii', 'hAnsi', 'eastAsia')) and rf.get(qn('w:hint')) == 'eastAsia'


def iter_paragraphs(doc):
    for p in doc.paragraphs:
        yield p
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    yield p


def normalize(path, check_only=False):
    doc = Document(path)
    font = body_font(doc)
    bad = 0
    for p in iter_paragraphs(doc):
        for r in list(p.runs):
            if not CIRC.search(r.text):
                continue
            if CIRC.fullmatch(r.text) and run_ok(r, font):
                continue
            bad += 1
            if check_only:
                continue
            # split run into circled / non-circled segments
            segs = [s for s in re.split(r"([①-⑳]+)", r.text) if s]
            base = r._r.find(qn('w:rPr'))
            prev = r._r
            for s in segs:
                new_r = copy.deepcopy(r._r)
                for t in new_r.findall(qn('w:t')):
                    new_r.remove(t)
                t = OxmlElement('w:t'); t.text = s; t.set(qn('xml:space'), 'preserve')
                new_r.append(t)
                rpr = new_r.find(qn('w:rPr'))
                if re.fullmatch(r"[①-⑳]+", s):
                    if rpr is None:
                        rpr = OxmlElement('w:rPr'); new_r.insert(0, rpr)
                    for old in rpr.findall(qn('w:rFonts')):
                        rpr.remove(old)
                    f = OxmlElement('w:rFonts')
                    for k in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
                        f.set(qn('w:' + k), font)
                    f.set(qn('w:hint'), 'eastAsia')
                    rpr.insert(0, f)
                prev.addnext(new_r); prev = new_r
            r._r.getparent().remove(r._r)
    if not check_only and bad:
        doc.save(path)
    return font, bad


def scan_words(path):
    if path.lower().endswith('.docx'):
        text = "\n".join(p.text for p in iter_paragraphs(Document(path)))
    else:
        text = io.open(path, encoding='utf-8').read()
    hits = [(m.group(0), text[max(0, m.start() - 30):m.end() + 20].replace("\n", " ")) for m in BANNED.finditer(text)]
    return hits


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    path = sys.argv[1]
    if '--words' in sys.argv:
        hits = scan_words(path)
        for w, ctx in hits:
            print(f"[{w}] …{ctx}…")
        print(f"금지 낱말 검출: {len(hits)}건")
        sys.exit(1 if hits else 0)
    check = '--check' in sys.argv
    font, bad = normalize(path, check_only=check)
    print(f"본문 한글 글꼴: {font} / 원문자 run 비정합 {bad}건" + ("" if check else " → 정리 완료" if bad else ""))
    sys.exit(1 if (check and bad) else 0)
