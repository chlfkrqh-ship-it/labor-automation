# -*- coding: utf-8 -*-
"""
docx_merge.py — 서면초안.md 를 서면_프레임.docx 의 "다음" 이후에 병합하여 최종서면.docx 로 저장

사용법
  python scripts/docx_merge.py <출력 폴더>                       # 폴더 안의 서면_프레임.docx + 서면초안.md → 최종서면.docx
  python scripts/docx_merge.py <프레임.docx> <초안.md> <출력.docx>

처리 순서
  1. 프레임의 '다음' 문단과 '귀중' 앞 빈 문단 사이를 비우고, md 본문(--- 앞까지)을 채운다.
     - "N. 제목" 줄이 프레임 대제목('1.번호매기기')과 같으면 프레임 요소를 그대로 재사용
     - "가. …" 줄 → 소제목(프레임의 같은 줄을 재사용, 없으면 복제) + 볼드
     - "[갑 제N호증 …]" 한 줄 → 증거 캡션('표의첫행제목', 가운데)
     - 들여쓴 "을나 제N호증  이름" 줄 → 입증방법 항목('(가)번호매기기_내용')
     - 그 밖의 줄 → 본문 문단(원문자는 본문 한글 글꼴, 가운뎃점 낱말은 noProof)
     - 요소 사이에는 빈 문단 하나
  2. docx_restyle  : 본문 문단에 제목 계층별 '내용' 스타일
  3. docx_footnotes: [[각주: …]] 표시를 실제 각주로
  4. docx_normalize: 원문자 글꼴 통일
  이미 최종서면.docx 가 있으면 <출력>.bak_merge_<시각>.docx 로 보관한 뒤 덮어쓴다.
"""
import re, copy, sys, os, shutil, datetime
from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docx_restyle, docx_footnotes, docx_normalize  # noqa: E402

CAPTION_RE = re.compile(r"^\[(?:(?:갑|을가|을나|을|사|노|증)\s*제\d+호증[^\]]*|[^\]]*(?:준비서면|참고서면|답변서|이유서|판결)[^\]]*)\]$")
KEY_RE = re.compile(r"^\[(갑|을가|을나|을|사|노|증)\s*제(\d+)호증(?:의\s*(\d+))?")
IMG_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)$")
EV_RE = re.compile(r'^(갑|을가|을나|을|사|노|증) 제\d+호증')
SUB_RE = re.compile(r'^[가나다라마바사아자차카타파하]\. ')


# 발췌 그림 삽입 규칙(2026. 9. 8. 박준선 사건 변호사 지시)
#  - 테두리는 이미지에 그리지 않고 Word '그림 테두리'(a:ln)로 준다. 나중에 자르기를 해도 테두리가 남는다.
#  - 폭 15cm 로 넣었을 때 세로가 MAX_PIC_CM 를 넘으면 캡션과 다른 면으로 밀리므로,
#    같은 그림을 두 번 넣고 Word 자르기(a:srcRect)로 위/아래를 나눠 자연스럽게 이어 보이게 한다.
PIC_W_CM = 15.0
MAX_PIC_CM = 14.0
PIC_OVERLAP = 0.02  # 분할 경계에서 글자가 잘려 보이지 않도록 2% 겹친다


def _pic_of(run):
    for el in run._r.iter():
        if el.tag == qn('pic:pic'):
            return el
    return None


def _style_picture(run, crop_t=0.0, crop_b=0.0, line_pt=0.75):
    """그림 테두리와 자르기(srcRect)를 도형 서식으로 넣는다."""
    from docx.oxml import OxmlElement
    pic = _pic_of(run)
    if pic is None:
        return
    if crop_t or crop_b:
        blip_fill = pic.find(qn('pic:blipFill'))
        if blip_fill is not None:
            src = OxmlElement('a:srcRect')
            if crop_t:
                src.set('t', str(int(round(crop_t * 100000))))
            if crop_b:
                src.set('b', str(int(round(crop_b * 100000))))
            blip = blip_fill.find(qn('a:blip'))
            (blip.addnext(src) if blip is not None else blip_fill.insert(0, src))
    sp_pr = pic.find(qn('pic:spPr'))
    if sp_pr is None:
        return
    for old in sp_pr.findall(qn('a:ln')):
        sp_pr.remove(old)
    ln = OxmlElement('a:ln')
    ln.set('w', str(int(round(line_pt * 12700))))
    fill = OxmlElement('a:solidFill')
    clr = OxmlElement('a:srgbClr')
    clr.set('val', '000000')
    fill.append(clr)
    ln.append(fill)
    sp_pr.append(ln)


def _insert_picture(anchor, blank_tpl, parent, styles, img):
    """캡션 뒤에 그림 문단을 넣는다. 너무 크면 두 문단으로 나눠 각각 자른다."""
    from docx.shared import Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from PIL import Image
    with Image.open(img) as im:
        w, h = im.size
    full_cm = PIC_W_CM * h / w
    parts = [(0.0, 0.0)] if full_cm <= MAX_PIC_CM else [
        (0.0, 0.5 - PIC_OVERLAP / 2), (0.5 - PIC_OVERLAP / 2, 0.0)]
    made = []
    for crop_t, crop_b in parts:
        el = copy.deepcopy(blank_tpl)
        anchor.addprevious(el)
        par = Paragraph(el, parent)
        par.style = styles['Normal']
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = par.add_run()
        run.add_picture(img, width=Cm(PIC_W_CM),
                        height=Cm(full_cm * (1 - crop_t - crop_b)))
        _style_picture(run, crop_t, crop_b)
        made.append(el)
    return made, full_cm, len(parts)


def merge(frame, md, out):
    d = Document(frame)
    paras = d.paragraphs

    def find(pred):
        for i, p in enumerate(paras):
            if pred(p):
                return i
        raise SystemExit("프레임에서 기준 문단을 찾지 못했습니다")
    i_daum = find(lambda p: p.text.replace('\t', '').replace(' ', '') == '다음')
    i_gwi = max(i for i, p in enumerate(paras) if p.text.strip().endswith('귀중'))
    i_end = i_gwi - 1
    p_end = paras[i_end]
    if p_end.text.strip():
        raise SystemExit("'귀중' 바로 앞에 빈 문단이 없습니다")
    # 본문 run 서식 표본: '다음' 앞의 첫 본문 문단
    body_font_rpr = None
    for p in paras[:i_daum]:
        if p.runs and p.style.name == 'Normal' and p.text.strip():
            body_font_rpr = p.runs[0]._r.find(qn('w:rPr'))
    blank_tpl = copy.deepcopy(p_end._p)

    h1 = {}; sub = {}; ev_title = None; ev_tpl = None; sub_tpl = None
    for p in paras[i_daum + 1:i_end]:
        t = p.text.strip()
        if p.style.name == '1.번호매기기' and t:
            h1[t] = p._p
        elif p.style.name == '별지제목' and t.replace(' ', '') == '입증방법':
            ev_title = p._p
        elif p.style.name == '(가)번호매기기_내용' and '호증' in t:
            ev_tpl = p._p
        elif SUB_RE.match(t):
            sub[t] = p._p
            if sub_tpl is None:
                sub_tpl = p._p
    for p in paras[i_daum + 1:i_end]:
        p._p.getparent().remove(p._p)

    st = d.styles['Normal'].element.find(qn('w:rPr'))
    rfs = st.find(qn('w:rFonts')) if st is not None else None
    EA = (rfs.get(qn('w:eastAsia')) if rfs is not None else None) or '바탕체'

    def set_text(elem, text, bold=None):
        for r in elem.findall(qn('w:r')):
            elem.remove(r)
        p = Paragraph(elem, p_end._parent)
        for seg in re.split(r"([①-⑳]+|\S*·\S*)", text):
            if not seg:
                continue
            run = p.add_run(seg)
            rpr = copy.deepcopy(body_font_rpr) if body_font_rpr is not None else None
            if rpr is not None:
                for b in rpr.findall(qn('w:b')) + rpr.findall(qn('w:bCs')):
                    rpr.remove(b)
            if re.fullmatch(r"[①-⑳]+", seg):
                if rpr is None:
                    rpr = blank_tpl.makeelement(qn('w:rPr'), {})
                for old in rpr.findall(qn('w:rFonts')):
                    rpr.remove(old)
                f = rpr.makeelement(qn('w:rFonts'), {})
                for k in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
                    f.set(qn('w:' + k), EA)
                f.set(qn('w:hint'), 'eastAsia'); rpr.insert(0, f)
            elif '·' in seg:
                if rpr is None:
                    rpr = blank_tpl.makeelement(qn('w:rPr'), {})
                rpr.append(rpr.makeelement(qn('w:noProof'), {}))
            if rpr is not None:
                run._r.insert(0, rpr)
            if bold is not None:
                run.bold = bold
        return elem

    def new_body(text):
        return set_text(copy.deepcopy(blank_tpl), text, bold=False)

    cap_style = next((s.name for s in d.styles if s.name in ('표의첫행제목', 'Caption')), None)

    def new_caption(text):
        e = copy.deepcopy(blank_tpl); set_text(e, text)
        p = Paragraph(e, p_end._parent)
        if cap_style:
            p.style = d.styles[cap_style]
        p.alignment = 1
        return e

    lines = open(md, encoding='utf-8').read().split('\n')
    body_lines = []
    for ln in lines:
        if ln.strip() == '---':
            break
        body_lines.append(ln.rstrip())

    out_elems = []; used_sub = set(); img_map = {}
    for ln in body_lines:
        s = ln.strip()
        if not s:
            continue
        mi = IMG_RE.match(s)
        if mi:
            if out_elems:
                img_map[len(out_elems) - 1] = os.path.basename(mi.group(1))
            continue
        m1 = re.match(r'^(\d+)\. (.+)$', s)
        if m1 and m1.group(2) in h1:
            out_elems.append(h1[m1.group(2)]); continue
        if s.replace(' ', '') == '입증방법' and ev_title is not None:
            out_elems.append(ev_title); continue
        if ln.startswith('    ') and EV_RE.match(s) and ev_tpl is not None:
            parts = re.split(r'\s{2,}', s, maxsplit=1)
            e = copy.deepcopy(ev_tpl)
            set_text(e, parts[0] + '\t\t' + (parts[1] if len(parts) > 1 else ''), bold=False)
            out_elems.append(e); continue
        if SUB_RE.match(s):
            if s in sub and s not in used_sub:
                e = sub[s]; used_sub.add(s); set_text(e, s, bold=True)
            elif sub_tpl is not None:
                e = copy.deepcopy(sub_tpl); set_text(e, s, bold=True)
            else:
                e = copy.deepcopy(blank_tpl); set_text(e, s, bold=True)
            out_elems.append(e); continue
        if CAPTION_RE.match(s):
            out_elems.append(new_caption(s)); continue
        out_elems.append(new_body(s))

    # 삽입 기준점: '다음' 문단과 '귀중' 앞 빈 문단 사이에 표(날짜·대리인 마무리 블록)가 있으면
    # 그 표 앞에 본문을 넣는다. 그렇지 않으면 마무리 표가 본문 앞으로 밀려 나온다(2026. 9. 8. 변호사 지적).
    anchor = p_end._p
    node = paras[i_daum]._p.getnext()
    while node is not None and node is not p_end._p:
        if node.tag == qn('w:tbl'):
            anchor = node
            break
        node = node.getnext()
    # '다음' 제목과 본문 사이 빈 문단 하나
    anchor.addprevious(copy.deepcopy(blank_tpl))
    def _is_ev(el):
        return el is not None and el is not ev_title and ev_tpl is not None and             "".join(t.text or '' for t in el.iter(qn('w:t'))).strip().startswith(tuple('갑을사노증'))            and EV_RE.match("".join(t.text or '' for t in el.iter(qn('w:t'))).strip()) is not None             and el.find(qn('w:pPr')) is not None and el.find(qn('w:pPr')).find(qn('w:pStyle')) is not None             and el.find(qn('w:pPr')).find(qn('w:pStyle')).get(qn('w:val')) == (ev_tpl.find(qn('w:pPr')).find(qn('w:pStyle')).get(qn('w:val')) if ev_tpl.find(qn('w:pPr')) is not None and ev_tpl.find(qn('w:pPr')).find(qn('w:pStyle')) is not None else None)
    prev = None
    cap_seen = {}
    for idx, e in enumerate(out_elems):
        if e is ev_title:
            # 입증방법은 새 면에서 시작(Ctrl+Enter)
            br_r = e.makeelement(qn('w:r'), {}); br = br_r.makeelement(qn('w:br'), {qn('w:type'): 'page'}); br_r.append(br)
            ppr = e.find(qn('w:pPr'))
            (ppr.addnext(br_r) if ppr is not None else e.insert(0, br_r))
        if prev is not None and not (_is_ev(prev) and _is_ev(e)) and not getattr(e, '_no_blank_before', False):
            anchor.addprevious(copy.deepcopy(blank_tpl))
        anchor.addprevious(e)
        prev = e
        # 발췌 이미지: 캡션 바로 뒤(빈 줄 없이) 삽입. md 의 ![](파일) 지정이 우선하고,
        # 없으면 호증키(같은 캡션 반복 시 -2, -3)로 라운드N/발췌/ 에서 찾는다.
        cap_text = "".join(t.text or '' for t in e.iter(qn('w:t'))).strip()
        if not (cap_text.startswith('[') and CAPTION_RE.match(cap_text)):
            continue
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(out))), '발췌')
        img = img_map.get(idx)
        img = os.path.join(base, img) if img else None
        if img is None:
            m = KEY_RE.match(cap_text)
            if not m:
                continue
            key = m.group(1) + m.group(2) + ('-' + m.group(3) if m.group(3) else '')
            n = cap_seen.get(key, 0) + 1; cap_seen[key] = n
            img = os.path.join(base, key + ('' if n == 1 else '-%d' % n) + '.png')
        if not os.path.exists(img):
            print("발췌 이미지 없음:", os.path.basename(img)); continue
        made, full_cm, n = _insert_picture(anchor, blank_tpl, p_end._parent, d.styles, img)
        prev = made[-1]
        print("발췌 이미지 삽입: %s (%.1fcm%s)" % (
            os.path.basename(img), full_cm, ", 2장 분할" if n > 1 else ""))
    if anchor is not p_end._p:
        anchor.addprevious(copy.deepcopy(blank_tpl))

    if os.path.exists(out):
        bak = os.path.splitext(out)[0] + '.bak_merge_' + datetime.datetime.now().strftime('%Y%m%d_%H%M') + '.docx'
        shutil.copy2(out, bak)
        print("기존 파일 보관 →", os.path.basename(bak))
    d.save(out)
    print("병합 저장", out, "요소", len(out_elems))
    docx_restyle.main(out, backup=False)
    docx_footnotes.convert(out)
    docx_normalize.normalize(out)
    return 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) == 1 and os.path.isdir(a[0]):
        frame, md, out = (os.path.join(a[0], n) for n in ('서면_프레임.docx', '서면초안.md', '최종서면.docx'))
    elif len(a) == 3:
        frame, md, out = a
    else:
        print(__doc__); sys.exit(2)
    sys.exit(merge(frame, md, out))
