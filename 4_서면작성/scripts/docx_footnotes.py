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
"""
import sys, re, copy
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MARK = re.compile(r"\[\[각주:\s*(.*?)\]\]", re.S)
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


def _text_run(template_r, text, font, rstyle=None):
    """new run copying template formatting, with circled-number / dot-word rules applied"""
    r = copy.deepcopy(template_r) if template_r is not None else OxmlElement('w:r')
    for child in list(r):
        if child.tag != qn('w:rPr'):
            r.remove(child)
    rpr = r.find(qn('w:rPr'))
    if rpr is None:
        rpr = OxmlElement('w:rPr'); r.insert(0, rpr)
    if rstyle:
        rs = OxmlElement('w:rStyle'); rs.set(qn('w:val'), rstyle); rpr.insert(0, rs)
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
        p.append(_text_run(None, seg, font))


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
    marks = sum(len(MARK.findall(p.text)) for p in doc.paragraphs)
    if check_only:
        print(f"남은 [[각주:]] 표시 {marks}건 / 현재 각주 {len(real)}개")
        return 1 if marks else 0
    if marks == 0:
        print(f"변환할 표시 없음 / 현재 각주 {len(real)}개")
        return 0
    part = _ensure_footnotes_part(doc)
    fn_root = etree.fromstring(part.blob)
    ref_sid = _style_id(doc, 'footnote reference', 'character')
    txt_sid = _style_id(doc, 'footnote text', 'paragraph')
    next_id = max([i for i in [int(f.get(qn('w:id'))) for f in fn_root.findall(qn('w:footnote'))]] + [0]) + 1
    done = 0
    for p in doc.paragraphs:
        if '[[각주:' not in p.text:
            continue
        runs = [r for r in p._p.findall(qn('w:r')) if r.find(qn('w:t')) is not None]
        full = "".join(r.find(qn('w:t')).text or '' for r in runs)
        spans = [(m.start(), m.end(), m.group(1)) for m in MARK.finditer(full)]
        if not spans:
            continue
        # rebuild runs
        new_runs = []
        pos = 0
        span_i = 0
        for r in runs:
            t = r.find(qn('w:t')).text or ''
            start, end = pos, pos + len(t)
            cursor = start
            while cursor < end:
                # inside a marker?
                inside = next(((s, e, c) for s, e, c in spans if s <= cursor < e), None)
                if inside:
                    s, e, c = inside
                    if cursor == s or (cursor == start and s < start):
                        pass
                    # emit reference at marker start
                    if cursor == s:
                        ref = OxmlElement('w:r'); rpr = OxmlElement('w:rPr')
                        rs = OxmlElement('w:rStyle'); rs.set(qn('w:val'), ref_sid); rpr.append(rs); ref.append(rpr)
                        fr = OxmlElement('w:footnoteReference'); fr.set(qn('w:id'), str(next_id)); ref.append(fr)
                        new_runs.append(ref)
                        _add_footnote_body(fn_root, next_id, c, ref_sid, txt_sid, font)
                        next_id += 1; done += 1
                    cursor = min(e, end)
                    continue
                nxt = min([s for s, e, c in spans if s > cursor] + [end])
                piece = t[cursor - start: nxt - start]
                if piece:
                    new_runs.append(_text_run(r, piece, font))
                cursor = nxt
            pos = end
        for r in runs:
            r.getparent().remove(r)
        # insert after pPr (keep any non-text runs like drawings at their place is not needed here)
        anchor = p._p.find(qn('w:pPr'))
        for i, nr in enumerate(new_runs):
            if anchor is None and i == 0:
                p._p.insert(0, nr)
            else:
                (anchor if i == 0 else new_runs[i - 1]).addnext(nr)
    part._blob = etree.tostring(fn_root, xml_declaration=True, encoding='UTF-8', standalone=True)
    doc.save(path)
    print(f"각주 {done}건 변환 → 총 {len(real) + done}개 (본문 한글 글꼴 {font})")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    sys.exit(convert(sys.argv[1], check_only='--check' in sys.argv, list_only='--list' in sys.argv))
