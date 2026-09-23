# -*- coding: utf-8 -*-
"""
docx_footnotes.py — 서면 docx의 본문 속 각주 표시를 실제 Word 각주로 변환

사용법
  python scripts/docx_footnotes.py <파일.docx>            # [[각주: …]] 표시를 실제 각주로 변환하여 같은 파일에 저장
  python scripts/docx_footnotes.py <파일.docx> --check    # 변환하지 않고 남은 표시 개수와 현재 각주 수만 보고
  python scripts/docx_footnotes.py <파일.docx> --list     # 각주 본문을 번호와 함께 출력

표시 규칙(서면초안.md 단계)
  각주를 붙일 어구 바로 뒤에 붙여서 씁니다. 어구와 표시 사이에 띄어쓰기를 두지 않습니다.
    예) …대법원 2019도10516 판결[[각주: 근로자의 쟁의행위가 형법상 정당행위에 해당하려면 …(대법원 2003. 11. 13. 선고 2003도687 판결 참조).]]은 …
  변환 결과: 어구 뒤에 위첨자 각주번호가 붙고, 표시 안 문장은 페이지 아래 각주로 옮겨집니다.
  각주 안 문장은 어구에 적힌 그 판결문의 설시를 원문 그대로 복사한 것이어야 합니다(요약·재작성 금지, 판결문 안의 참조 표기도 그대로).

서식(2026. 9. 8. 변호사가 직접 넣은 각주에서 추출)
  - 각주번호: 문자 스타일 'footnote reference'(위첨자), 본문 어구 바로 뒤(조사 앞이라도 됨)
  - 각주 본문: 단락 스타일 'footnote text'(10pt, 줄간격 1.25, 왼쪽 정렬), 첫 run은 각주번호, 이어서 한 칸 띄고 문장
  - 원문자는 본문 한글 글꼴로 통일, 가운뎃점 낱말은 noProof (docx_normalize.py와 같은 규칙)

변환 방식
  담당자가 Word 로 고친 수정안에도 돌리므로 문단을 다시 짜지 않는다. 표시 글자만 떼어 내 그 자리에
  각주번호 run 을 넣고, 다른 run·탭·줄바꿈·변경 추적(w:ins)·하이퍼링크 안 글자는 제자리에 둔다.
  바꾼 뒤 문단 글자가 '표시만 뺀 원래 글자'와 다르면 저장하지 않고 멈춘다.
  닫는 ']]' 가 없거나 ']' 하나로 닫은 표시는 바꾸지 않고, --check 가 남은 표시로 센다(종료 코드 1).
"""
import sys, re, copy
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
# 내용에 '[[' 나 ']]' 가 끼면 표시로 보지 않는다. ']' 하나로 잘못 닫은 표시가 뒤따르는 정상 표시와
# 그 사이 본문 문장까지 삼켜 각주로 옮기는 일을 막는다.
MARK = re.compile(r"\[\[각주:\s*((?:(?!\[\[|\]\]).)*)\]\]", re.S)
OPEN = '[[각주'
CIRC = re.compile(r"([①-⑳]+)")


def _style_id(doc, name, create_type=None):
    for s in doc.styles.element.findall(qn('w:style')):
        n = s.find(qn('w:name'))
        if n is not None and n.get(qn('w:val')) == name:
            return s.get(qn('w:styleId'))
    if create_type is None:
        return None
    # create minimal style
    st = OxmlElement('w:style'); st.set(qn('w:type'), create_type); sid = name.replace(' ', '')
    st.set(qn('w:styleId'), sid)
    nm = OxmlElement('w:name'); nm.set(qn('w:val'), name); st.append(nm)
    if create_type == 'character':
        rpr = OxmlElement('w:rPr'); va = OxmlElement('w:vertAlign'); va.set(qn('w:val'), 'superscript'); rpr.append(va); st.append(rpr)
    else:
        ppr = OxmlElement('w:pPr'); sp = OxmlElement('w:spacing'); sp.set(qn('w:line'), '300'); sp.set(qn('w:lineRule'), 'auto'); ppr.append(sp)
        jc = OxmlElement('w:jc'); jc.set(qn('w:val'), 'left'); ppr.append(jc); st.append(ppr)
        rpr = OxmlElement('w:rPr'); sz = OxmlElement('w:sz'); sz.set(qn('w:val'), '20'); rpr.append(sz); st.append(rpr)
    doc.styles.element.append(st)
    return sid


def _body_font(doc):
    rpr = doc.styles['Normal'].element.find(qn('w:rPr'))
    rf = rpr.find(qn('w:rFonts')) if rpr is not None else None
    return (rf.get(qn('w:eastAsia')) if rf is not None else None) or '바탕체'


def _footnotes_part(doc):
    for rel in doc.part.rels.values():
        if rel.reltype == RT.FOOTNOTES:
            return rel.target_part
    return None


def _ensure_footnotes_part(doc):
    part = _footnotes_part(doc)
    if part is not None:
        return part
    # build a new footnotes part with separators
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:footnotes xmlns:w="{W}">'
           '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
           '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
           '</w:footnotes>').encode('utf-8')
    part = Part(PackURI('/word/footnotes.xml'),
                'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml', xml, doc.part.package)
    doc.part.relate_to(part, RT.FOOTNOTES)
    return part


def _text_run(text, font):
    """각주 본문용 새 run. 원문자·가운뎃점 낱말 규칙을 적용한다."""
    r = OxmlElement('w:r')
    rpr = OxmlElement('w:rPr'); r.append(rpr)
    if CIRC.fullmatch(text):
        for old in rpr.findall(qn('w:rFonts')): rpr.remove(old)
        f = OxmlElement('w:rFonts')
        for k in ('ascii', 'hAnsi', 'eastAsia', 'cs'): f.set(qn('w:' + k), font)
        f.set(qn('w:hint'), 'eastAsia'); rpr.insert(0, f)
    if '·' in text and rpr.find(qn('w:noProof')) is None:
        rpr.append(OxmlElement('w:noProof'))
    t = OxmlElement('w:t'); t.text = text; t.set(qn('xml:space'), 'preserve'); r.append(t)
    return r


def _segments(text):
    return [s for s in re.split(r"([①-⑳]+|\S*·\S*)", text) if s]


def _add_footnote_body(fn_root, fid, text, ref_sid, txt_sid, font):
    fn = etree.SubElement(fn_root, qn('w:footnote')); fn.set(qn('w:id'), str(fid))
    p = etree.SubElement(fn, qn('w:p'))
    ppr = etree.SubElement(p, qn('w:pPr'))
    ps = etree.SubElement(ppr, qn('w:pStyle')); ps.set(qn('w:val'), txt_sid)
    prpr = etree.SubElement(ppr, qn('w:rPr')); rf = etree.SubElement(prpr, qn('w:rFonts')); rf.set(qn('w:hint'), 'eastAsia')
    # footnote number run
    r0 = etree.SubElement(p, qn('w:r')); rpr0 = etree.SubElement(r0, qn('w:rPr'))
    rs = etree.SubElement(rpr0, qn('w:rStyle')); rs.set(qn('w:val'), ref_sid)
    etree.SubElement(r0, qn('w:footnoteRef'))
    # text runs
    for seg in _segments(' ' + text.strip()):
        p.append(_text_run(seg, font))


_SKIP = (qn('w:del'), qn('w:moveFrom'), qn('w:txbxContent'), qn('w:p'))


def _runs(p):
    """문단에 보이는 run 을 문서 순서대로. w:ins·w:hyperlink·누름틀 안의 run 은 넣고,
    삭제 표시(w:del·w:moveFrom) 안의 run 과 글상자 안 문단의 run 은 뺀다."""
    for r in p.iter(qn('w:r')):
        a = r.getparent()
        while a is not None and a is not p and a.tag not in _SKIP:
            a = a.getparent()
        if a is p:
            yield r


def _atoms(p):
    """[(요소, 글자)] — w:t 는 그 글자, w:tab 은 '\\t', w:br·w:cr 은 '\\n'."""
    out = []
    for r in _runs(p):
        for ch in r:
            if ch.tag == qn('w:t'):
                out.append((ch, ch.text or ''))
            elif ch.tag == qn('w:tab'):
                out.append((ch, '\t'))
            elif ch.tag in (qn('w:br'), qn('w:cr')):
                out.append((ch, '\n'))
    return out


def visible_text(p):
    """문단의 보이는 글자(탭·줄바꿈 포함, 삭제 표시 제외). p 는 w:p 요소."""
    return ''.join(t for _, t in _atoms(p))


def _paragraphs(doc):
    """본문의 모든 문단(표 칸·글상자 안 포함). 문단마다 제 run 만 보므로 글자를 두 번 세지 않는다."""
    return list(doc.element.body.iter(qn('w:p')))


def _in_textbox(p):
    a = p.getparent()
    while a is not None:
        if a.tag == qn('w:txbxContent'):
            return True
        a = a.getparent()
    return False


def _content(r):
    return [ch for ch in r if ch.tag != qn('w:rPr')]


def _set_t(t, text):
    t.text = text
    t.set(qn('xml:space'), 'preserve')


def _split_before(child):
    """child 가 든 run 을 둘로 나눠 child 부터 끝까지를 같은 서식의 새 run 으로 옮긴다. child 가 든 run 을 돌려준다."""
    r = child.getparent()
    kids = _content(r)
    i = kids.index(child)
    if i == 0:
        return r
    new = r.makeelement(qn('w:r'), dict(r.attrib))
    rpr = r.find(qn('w:rPr'))
    if rpr is not None:
        new.append(copy.deepcopy(rpr))
    for ch in kids[i:]:
        new.append(ch)
    r.addnext(new)
    return new


def _isolate(t, lo, hi):
    """w:t 의 글자 [lo, hi) 만 담은 run 을 떼어 내 그 w:t 를 돌려준다.
    앞뒤 글자와 같은 run 의 다른 자식(탭·줄바꿈 등)은 같은 서식의 run 에 담겨 제자리에 남는다."""
    text = t.text or ''
    if hi < len(text):
        tail = t.makeelement(qn('w:t'), {}); _set_t(tail, text[hi:])
        _set_t(t, text[:hi]); t.addnext(tail)
        _split_before(tail)
    if lo > 0:
        mid = t.makeelement(qn('w:t'), {}); _set_t(mid, (t.text or '')[lo:])
        _set_t(t, (t.text or '')[:lo]); t.addnext(mid)
        t = mid
    _split_before(t)
    if t.getnext() is not None:
        _split_before(t.getnext())
    return t


def _ref_run(ref_sid, fid):
    ref = OxmlElement('w:r'); rpr = OxmlElement('w:rPr')
    rs = OxmlElement('w:rStyle'); rs.set(qn('w:val'), ref_sid); rpr.append(rs); ref.append(rpr)
    fr = OxmlElement('w:footnoteReference'); fr.set(qn('w:id'), str(fid)); ref.append(fr)
    return ref


def _convert_paragraph(p, add_note):
    """문단 안의 [[각주: …]] 표시를 각주번호로 바꾸고 바꾼 개수를 돌려준다.
    add_note(각주 문장) 는 각주 본문을 만들고 본문 자리에 넣을 각주번호 run 을 돌려준다."""
    done = 0
    while True:
        atoms = _atoms(p)
        text = ''.join(t for _, t in atoms)
        m = MARK.search(text)
        if not m:
            return done
        s, e = m.span()
        pieces, pos = [], 0
        for el, t in atoms:
            a, b = pos, pos + len(t); pos = b
            if b <= s or a >= e:
                continue
            if el.tag == qn('w:t'):
                el = _isolate(el, max(s, a) - a, min(e, b) - a)
            pieces.append(el)
        note = m.group(1).replace('\t', ' ').replace('\n', ' ')
        pieces[0].getparent().addprevious(add_note(note))
        for el in pieces:
            r = el.getparent(); r.remove(el)
            if not _content(r):
                r.getparent().remove(r)
        expected = text[:s] + text[e:]
        if visible_text(p) != expected:
            raise SystemExit("각주 변환 중 문단 글자가 달라져 저장하지 않았습니다(원문 보존). 문단 앞부분: "
                             + repr(text[:60]))
        done += 1


def _leftovers(texts):
    """남은 표시 수: (전체 '[[각주' 수, 그중 짝이 맞지 않아 바꿀 수 없는 수)"""
    opened = sum(t.count(OPEN) for t in texts)
    complete = sum(len(MARK.findall(t)) for t in texts)
    return opened, opened - complete


def convert(path, check_only=False, list_only=False):
    doc = Document(path)
    font = _body_font(doc)
    part = _footnotes_part(doc)
    fn_root = etree.fromstring(part.blob) if part is not None else None
    existing = [int(f.get(qn('w:id'))) for f in fn_root.findall(qn('w:footnote'))] if fn_root is not None else []
    real = [i for i in existing if i > 0]
    if list_only:
        for f in fn_root.findall(qn('w:footnote')) if fn_root is not None else []:
            i = int(f.get(qn('w:id')))
            if i > 0:
                print(f"[{i}] " + "".join(t.text or '' for t in f.iter(qn('w:t'))).strip())
        print(f"각주 {len(real)}개")
        return 0
    paras = _paragraphs(doc)
    opened, broken = _leftovers([visible_text(p) for p in paras])
    if check_only:
        # 각주 본문에 표시 글자가 들어간 경우(잘못 닫은 표시를 예전 방식으로 바꾼 흔적)도 센다
        in_notes = sum("".join(t.text or '' for t in f.iter(qn('w:t'))).count(OPEN)
                       for f in (fn_root.findall(qn('w:footnote')) if fn_root is not None else []))
        print(f"남은 [[각주:]] 표시 {opened}건" + (f"(닫는 ']]' 가 맞지 않는 표시 {broken}건 포함)" if broken else "")
              + f" / 현재 각주 {len(real)}개" + (f" / 각주 본문에 남은 표시 {in_notes}건" if in_notes else ""))
        return 1 if opened or in_notes else 0
    if opened == broken:
        if broken:
            print(f"변환할 표시 없음 / 닫는 ']]' 가 맞지 않는 [[각주 표시 {broken}건은 바꾸지 않았습니다 — 초안을 고쳐 다시 병합합니다")
            return 1
        print(f"변환할 표시 없음 / 현재 각주 {len(real)}개")
        return 0
    part = _ensure_footnotes_part(doc)
    fn_root = etree.fromstring(part.blob)
    ref_sid = _style_id(doc, 'footnote reference', 'character')
    txt_sid = _style_id(doc, 'footnote text', 'paragraph')
    next_id = max([i for i in [int(f.get(qn('w:id'))) for f in fn_root.findall(qn('w:footnote'))]] + [0]) + 1

    def add_note(note):
        nonlocal next_id
        _add_footnote_body(fn_root, next_id, note, ref_sid, txt_sid, font)
        ref = _ref_run(ref_sid, next_id)
        next_id += 1
        return ref

    done = sum(_convert_paragraph(p, add_note) for p in paras
               if OPEN in visible_text(p) and not _in_textbox(p))
    part._blob = etree.tostring(fn_root, xml_declaration=True, encoding='UTF-8', standalone=True)
    doc.save(path)
    print(f"각주 {done}건 변환 → 총 {len(real) + done}개 (본문 한글 글꼴 {font})")
    left, _ = _leftovers([visible_text(p) for p in _paragraphs(doc)])
    if left:
        print(f"바꾸지 못한 [[각주 표시 {left}건 — 닫는 ']]' 를 확인해 초안을 고칩니다")
        return 1
    return 0


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__); sys.exit(0)
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    sys.exit(convert(sys.argv[1], check_only='--check' in sys.argv, list_only='--list' in sys.argv))
