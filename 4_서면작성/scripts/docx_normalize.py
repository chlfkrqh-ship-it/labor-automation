# -*- coding: utf-8 -*-
"""
docx_normalize.py — 서면 docx 마무리 점검·정리 도구

사용법
  python scripts/docx_normalize.py <파일.docx>            # 원문자 글꼴을 본문 한글 글꼴로 통일하여 같은 파일에 저장
  python scripts/docx_normalize.py <파일.docx> --check    # 고치지 않고 검출 건수만 보고 (0건이면 종료코드 0)
  금지 낱말 검사는 이 스크립트가 하지 않는다: python 4_서면작성/scripts/style_check.py <파일>

원문자(①~⑳)가 본문 한글 글꼴(프레임 Normal 스타일의 eastAsia 글꼴, 통상 바탕체)로 찍히지 않는 run은
그 글꼴로 ascii·hAnsi·eastAsia·cs를 모두 지정하고 hint="eastAsia"를 붙인다.
(2026. 9. 7. 이케아 사건 변호사 지적: 원문자가 본문과 다른 글꼴로 찍히는 문제)
판정은 run 에 적힌 속성이 아니라 실제로 적용되는 글꼴로 한다. run 속성 → 문자 스타일 → 문단 스타일(basedOn 사슬)
→ docDefaults 순으로 따라가 본문 한글 글꼴과 다를 때만 비정합으로 센다(기준은 run_ok).
⑯~⑳ 은 바탕체·맑은 고딕에 글리프가 없어 어떻게 지정해도 본문 글꼴로 찍히지 않는다(바탕체로 지정해도 Word 는
Cambria Math 로 찍었다). 이 점검은 그것을 잡지 못한다.
run 은 원문자 조각과 나머지 조각으로만 나누고, 탭·줄바꿈 등 글자 아닌 자식은 원래 자리에 한 번만 둔다.
정리 전후 문단 글자(탭·줄바꿈 포함)가 다르면 저장하지 않고 멈춘다.
"""
import sys, re, copy
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CIRC = re.compile(r"[①-⑳]")
CIRC_RUN = re.compile(r"[①-⑳]+")


def body_font(doc):
    rpr = doc.styles['Normal'].element.find(qn('w:rPr'))
    rf = rpr.find(qn('w:rFonts')) if rpr is not None else None
    return (rf.get(qn('w:eastAsia')) if rf is not None else None) or '바탕체'


def _rfonts(el):
    """요소(run·스타일·rPrDefault) 바로 아래 w:rPr 의 w:rFonts"""
    rpr = el.find(qn('w:rPr')) if el is not None else None
    return rpr.find(qn('w:rFonts')) if rpr is not None else None


def _style_id(el, props, tag):
    """el 의 props(w:rPr·w:pPr) 안 tag(w:rStyle·w:pStyle)가 가리키는 스타일 ID"""
    pr = el.find(qn(props))
    ref = pr.find(qn(tag)) if pr is not None else None
    return ref.get(qn('w:val')) if ref is not None else None


def style_index(doc):
    """글꼴 상속을 따라갈 때 쓰는 ({스타일 ID: 스타일 요소}, 기본 문단 스타일, docDefaults 의 rFonts)"""
    root = doc.styles.element
    by_id = {s.get(qn('w:styleId')): s for s in root.findall(qn('w:style')) if s.get(qn('w:styleId'))}
    default_p = next((s for s in by_id.values() if s.get(qn('w:type')) == 'paragraph'
                      and s.get(qn('w:default')) in ('1', 'true', 'on')), None)
    dd = root.find(qn('w:docDefaults'))
    return by_id, default_p, _rfonts(dd.find(qn('w:rPrDefault')) if dd is not None else None)


def effective_font(index, p_el, r_el, slot):
    """run 에 실제로 적용되는 글꼴 이름(slot: hAnsi·eastAsia 등). run 속성 → 문자 스타일 → 문단 스타일(각각
    basedOn 사슬) → docDefaults 순으로 보아 그 칸을 처음 지정한 곳의 값이다. 문단에 스타일이 없거나 없는 스타일을
    가리키면 기본 문단 스타일에서 시작하고, 표 스타일은 보지 않는다(문단 스타일이 지정한 글꼴은 표 스타일이 덮지
    못한다). 처음 지정한 곳이 테마 글꼴(w:eastAsiaTheme 등)이면 이름을 정하지 않고 None 을 돌려준다(같은 요소에
    글꼴 이름이 함께 적혀 있어도 Word 는 테마 글꼴을 쓴다)."""
    by_id, default_p, doc_default = index
    rs, ps = _style_id(r_el, 'w:rPr', 'w:rStyle'), _style_id(p_el, 'w:pPr', 'w:pStyle')
    p_style = by_id.get(ps) if ps else None
    levels = [_rfonts(r_el)]
    for st in (by_id.get(rs) if rs else None, default_p if p_style is None else p_style):
        seen = set()
        while st is not None and id(st) not in seen:      # basedOn 이 서로를 가리키는 파일에서 돌지 않게
            seen.add(id(st))
            levels.append(_rfonts(st))
            base = st.find(qn('w:basedOn'))
            st = by_id.get(base.get(qn('w:val'))) if base is not None else None
    for rf in levels + [doc_default]:
        if rf is None:
            continue
        if rf.get(qn('w:' + slot + 'Theme')):
            return None
        if rf.get(qn('w:' + slot)):
            return rf.get(qn('w:' + slot))
    return None


def run_ok(r, p, font, index):
    """원문자가 본문 한글 글꼴로 찍히는 run 인가. run 에 적힌 속성이 아니라 실제로 적용되는 글꼴로 본다.
    2026. 10. 8. 표준양식에 변형을 넣어 Word 16 으로 PDF 를 내보내 원문자가 찍힌 글꼴을 확인한 기준이다
    (변형과 찍힌 글꼴은 공통/tests/test_docx_pipeline.py 의 NormalizeTests 에 있다).
      - run 에 hint="eastAsia" 가 있으면 원문자는 eastAsia 글꼴로 찍힌다. 그 글꼴이 상속으로 본문 글꼴이면
        정상이다. Word 는 저장할 때 스타일과 같은 값인 w:eastAsia 를 run 에서 지우므로 run 에 적힌 속성만 보면
        오탐이 난다(2026. 10. 7. 담당자가 Word 로 저장한 답변서의 11건).
      - run 에 hint 가 없으면 원문자는 hAnsi 글꼴로 찍힌다. 프레임은 hAnsi 가 Times New Roman 이고 그 글꼴에는
        원문자가 없어 Cambria Math 로 찍힌다. 이때는 hAnsi 도 본문 글꼴이어야 정상이다.
      - 어느 쪽이든 eastAsia 글꼴이 본문 글꼴과 다르면(테마 글꼴로 정해지는 경우 포함) 비정합이다. hint 가 없어
        지금은 hAnsi 글꼴로 찍히는 run 도 hint 가 붙으면 eastAsia 글꼴로 찍힌다.
      - hint 는 run 에 직접 적힌 것만 본다. 문자 스타일과 문단표식의 hint 는 Word 도 따르지 않는다. 문단 스타일의
        hint 는 Word 가 따르지만 여기서는 없는 것으로 보아 엄격한 쪽으로 판정한다."""
    def font_of(slot):
        return effective_font(index, p._p, r._r, slot)
    if font_of('eastAsia') != font:
        return False
    rf = _rfonts(r._r)
    if rf is not None and rf.get(qn('w:hint')) == 'eastAsia':
        return True
    return font_of('hAnsi') == font


def iter_paragraphs(doc):
    for p in doc.paragraphs:
        yield p
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    yield p


def _visible(p_el):
    """문단 글자(탭 '\\t', 줄바꿈 '\\n' 포함). 탭 위치 정의(w:tabs 안의 w:tab)는 빼고 run 안의 것만 본다."""
    out = []
    for el in p_el.iter(qn('w:t'), qn('w:tab'), qn('w:br'), qn('w:cr')):
        if el.getparent().tag != qn('w:r'):
            continue
        if el.tag == qn('w:t'):
            out.append(el.text or '')
        else:
            out.append('\t' if el.tag == qn('w:tab') else '\n')
    return ''.join(out)


def _circled_font(rpr, font):
    for old in rpr.findall(qn('w:rFonts')):
        rpr.remove(old)
    f = OxmlElement('w:rFonts')
    for k in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
        f.set(qn('w:' + k), font)
    f.set(qn('w:hint'), 'eastAsia')
    rs = rpr.find(qn('w:rStyle'))          # 스키마 순서: rStyle 다음이 rFonts
    (rs.addnext(f) if rs is not None else rpr.insert(0, f))


def _split_run(r_el, font):
    """run 을 원문자 조각과 나머지 조각으로 나눈다. w:t 는 글자 단위로 쪼개고,
    탭·줄바꿈 등 다른 자식은 원래 순서 그대로 나머지 조각 run 에 한 번만 옮긴다."""
    groups = []                                   # [원문자 조각인가, [자식]]
    for ch in list(r_el):
        if ch.tag == qn('w:rPr'):
            continue
        if ch.tag == qn('w:t'):
            for seg in re.split(r"([①-⑳]+)", ch.text or ''):
                if not seg:
                    continue
                t = OxmlElement('w:t'); t.text = seg; t.set(qn('xml:space'), 'preserve')
                circ = bool(CIRC_RUN.fullmatch(seg))
                if not circ and groups and not groups[-1][0]:
                    groups[-1][1].append(t)
                else:
                    groups.append([circ, [t]])
        elif groups and not groups[-1][0]:
            groups[-1][1].append(ch)
        else:
            groups.append([False, [ch]])
    base = r_el.find(qn('w:rPr'))
    prev = r_el
    for circ, kids in groups:
        new_r = r_el.makeelement(qn('w:r'), dict(r_el.attrib))
        rpr = copy.deepcopy(base) if base is not None else (OxmlElement('w:rPr') if circ else None)
        if circ:
            _circled_font(rpr, font)
        if rpr is not None:
            new_r.append(rpr)
        for k in kids:
            new_r.append(k)
        prev.addnext(new_r); prev = new_r
    r_el.getparent().remove(r_el)


def normalize(path, check_only=False):
    doc = Document(path)
    font = body_font(doc)
    index = style_index(doc)
    bad = 0
    for p in iter_paragraphs(doc):
        before = None
        for r in list(p.runs):
            if not CIRC.search(r.text) or run_ok(r, p, font, index):
                continue
            bad += 1
            if check_only:
                continue
            if before is None:
                before = _visible(p._p)
            _split_run(r._r, font)
        if before is not None and _visible(p._p) != before:
            raise SystemExit("원문자 정리 중 문단 글자가 달라져 저장하지 않았습니다(원문 보존). 문단 앞부분: "
                             + repr(before[:60]))
    if not check_only and bad:
        doc.save(path)
    return font, bad


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__); sys.exit(0)
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    path = sys.argv[1]
    if '--words' in sys.argv:
        # 금지 낱말 목록은 style_check.py 한 곳에만 둔다(두 벌이면 한쪽만 고쳐져 이미 갈라졌다).
        print("금지 낱말 검사는 style_check.py 로 합니다: python 4_서면작성/scripts/style_check.py " + path)
        sys.exit(2)
    check = '--check' in sys.argv
    font, bad = normalize(path, check_only=check)
    print(f"본문 한글 글꼴: {font} / 원문자 run 비정합 {bad}건" + ("" if check else " → 정리 완료" if bad else ""))
    sys.exit(1 if (check and bad) else 0)
