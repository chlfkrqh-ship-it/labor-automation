# -*- coding: utf-8 -*-
"""
docx_restyle.py — 병합된 서면 docx의 제목·본문 문단에 프레임의 번호매기기 스타일을 1:1로 입힘

사용법
  python scripts/docx_restyle.py <파일.docx>            # 스타일을 입혀 같은 파일에 저장(원본은 <파일>.bak_restyle.docx 로 보관)
  python scripts/docx_restyle.py <파일.docx> --check    # 바꾸지 않고 계층에 맞지 않는 문단 수만 보고
  python scripts/docx_restyle.py <파일.docx> --dry      # 바꿀 문단을 스타일과 함께 출력만 함

--check 는 아래 구조 이상도 함께 보고하고, 하나라도 있으면 종료 코드 1을 낸다.
  - 범위('다음' 뒤 ~ '입 증 방 법' 앞)에 '1.번호매기기' 대제목 문단이 하나도 없음
  - 대제목 누락 의심: 'N. 제목' 꼴 글자로 시작하는데 본문(또는 대제목 앞 Normal)으로 남은 문단
  - 캡션 붙임 없음: 발췌 그림 바로 앞 캡션 문단에 keepNext 가 없음(공통/문서변환.md 나. 증거 이미지)
  대제목 앞의 그 밖의 문단은 스타일을 정할 수 없어 그대로 두고 '참고'로만 알린다.

규칙(2026. 9. 8. 변호사 지시: 제목 스타일과 _내용 스타일은 1:1 대응)
  제목                               그 아래 본문
  '1.번호매기기'  (자동 번호)         '1.번호매기기_내용'
  '가.번호매기기' (자동 가나다)        '가.번호매기기_내용'
  '(1) 번호매기기' (자동 (1))          '(1)번호매기기_내용'
  - 본문에 글자로 적힌 "가. ", "(1) " 번호는 지우고 스타일의 자동 번호를 쓴다(제목 run 의 직접 볼드도 지워 스타일에 맡긴다).
  - 가. 는 새 1. 아래에서, (1) 은 새 가. 아래에서 번호를 다시 시작한다(numbering.xml 의 abstractNum 을 복제한 새 목록을 추가.
    startOverride 방식은 PDF 저장 시 번호가 어긋나 쓰지 않음).
  - "(1) …" 로 시작하는 문단은 같은 가. 안의 (n) 문단이 모두 소제목감일 때만 소제목('(1) 번호매기기')으로 보고,
    하나라도 길거나 여러 문장이면 그 가. 안의 (n) 문단은 전부 본문('가.번호매기기_내용')으로 둔다(번호가 섞이지 않도록).
    소제목감은 90자 이내 한 문장이거나, '소결'·'판단 기준'처럼 마침표 없이 끝나는 40자 이내 명사구다(2026. 9. 22. 변호사 지시).
  - 빈 문단은 앞뒤 본문과 같은 _내용 스타일. 증거 캡션('표의첫행제목')·그림 문단·가운데 정렬 문단·입증방법 이후·'다음' 앞은 건드리지 않는다.
"""
import sys, re, shutil, os
from collections import Counter
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

S_H1, S_H1_BODY = '1.번호매기기', '1.번호매기기_내용'
S_SUB, S_SUB_BODY = '가.번호매기기', '가.번호매기기_내용'
S_SUB2, S_SUB2_BODY = '(1) 번호매기기', '(1)번호매기기_내용'
CAPTION, EV_TITLE = '표의첫행제목', '별지제목'
SUB_RE = re.compile(r'^[가나다라마바사아자차카타파하]\.\s*')
SUB2_RE = re.compile(r'^\(\d+\)\s*')
SENT = re.compile(r'(다|요|음|함)\.(?=\s|$)')
BODY_OF = {'h1': S_H1_BODY, 'sub': S_SUB_BODY, 'sub2': S_SUB2_BODY}


def _text(p):
    return "".join(t.text or '' for t in p.iter(qn('w:t')))


def _has_drawing(p):
    return p.find('.//' + qn('w:drawing')) is not None or p.find('.//' + qn('w:pict')) is not None


def _styles(doc):
    return {s.find(qn('w:name')).get(qn('w:val')): s for s in doc.styles.element.findall(qn('w:style')) if s.find(qn('w:name')) is not None}


def _style_name(p, sid2name):
    ppr = p.find(qn('w:pPr'))
    ps = ppr.find(qn('w:pStyle')) if ppr is not None else None
    return 'Normal' if ps is None else sid2name.get(ps.get(qn('w:val')), ps.get(qn('w:val')))


def _is_bold(p):
    return any(r.find(qn('w:rPr')) is not None and r.find(qn('w:rPr')).find(qn('w:b')) is not None for r in p.findall(qn('w:r')))


HEAD_MAX = 90   # (1) 소제목으로 볼 최대 글자 수(사무실 서면의 (1) 소제목 실측 최장 83자)
NOUN_HEAD_MAX = 40   # 마침표 없이 끝나는 명사구 제목('소결' 등)으로 볼 최대 글자 수("(1) " 번호 포함)
ENDING = re.compile(r'(다|요|음|함|까|죠|오)$')   # 종결어미로 끝나면 명사구 제목이 아니라 마침표를 빠뜨린 문장으로 본다


def _one_sentence(t):
    """(1) 소제목으로 볼 문단: 90자 이내 한 문장이거나, '소결'·'판단 기준' 같은 짧은 명사구 제목.
    명사구 제목은 2026. 9. 22. 변호사 지시로 받아들이게 넓혔다(마지막 (n)의 제목을 '소결'로 쓰기 때문)."""
    if len(t) > HEAD_MAX or len(SENT.findall(t)) > 1:
        return False
    if t.endswith('.'):
        return True
    return len(t) <= NOUN_HEAD_MAX and not SENT.search(t) and not ENDING.search(t)


H1_RE = re.compile(r'^([1-9]\d?)\.\s+(\S.*)$')
PLAIN_END = re.compile(r'(?:(?<!니)다|라)\.$')   # '…지급하라.', '…부담한다.' 같은 주문·청구취지 문장


def h1_candidate(text):
    """'N. 제목' 꼴의 대제목감이면 (N, 제목), 아니면 None.
    번호는 한두 자리이고('2025. 3. 1.' 같은 날짜는 아님), 제목은 90자 이내이며
    '…지급하라.'·'…부담한다.'처럼 해라체로 끝나는 주문·청구취지 문장이 아니어야 한다.
    docx_merge 가 프레임 목차와 짝이 없는 대제목 줄을 가를 때와 --check 의 '대제목 누락 의심'에 같이 쓴다."""
    m = H1_RE.match(text.strip().lstrip('\ufeff'))
    if not m:
        return None
    title = m.group(2).strip()
    if len(title) > HEAD_MAX or PLAIN_END.search(title):
        return None
    return int(m.group(1)), title


def _on(el):
    return el is not None and el.get(qn('w:val'), 'true') not in ('0', 'false', 'off')


def _keeps_next(p, styles_by_id):
    """문단에 keepNext 가 걸려 있는지(직접 서식, 없으면 스타일과 그 basedOn 을 따라 본다)."""
    ppr = p.find(qn('w:pPr'))
    if ppr is not None and ppr.find(qn('w:keepNext')) is not None:
        return _on(ppr.find(qn('w:keepNext')))
    ps = ppr.find(qn('w:pStyle')) if ppr is not None else None
    sid, seen = (ps.get(qn('w:val')) if ps is not None else None), set()
    while sid and sid not in seen and sid in styles_by_id:
        seen.add(sid)
        spr = styles_by_id[sid].find(qn('w:pPr'))
        if spr is not None and spr.find(qn('w:keepNext')) is not None:
            return _on(spr.find(qn('w:keepNext')))
        based = styles_by_id[sid].find(qn('w:basedOn'))
        sid = based.get(qn('w:val')) if based is not None else None
    return False


class Numbering:
    """번호 다시 시작: 스타일이 쓰는 abstractNum 을 통째로 복제해 새 목록(w:num)을 만든다.
    w:lvlOverride/w:startOverride 방식은 Word 화면(ListString)에서는 맞게 보이지만 PDF 저장·인쇄 레이아웃에서
    세 번째 항목부터 다시 '가.'로 찍히는 현상이 있어(2026. 9. 8. 실측) 쓰지 않는다."""
    def __init__(self, doc, styles):
        import copy
        self.copy = copy
        self.part = doc.part.numbering_part.element
        self.abs = {a.get(qn('w:abstractNumId')): a for a in self.part.findall(qn('w:abstractNum'))}
        self.abs_of_style = {}
        for name in (S_SUB, S_SUB2):
            ppr = styles[name].find(qn('w:pPr'))
            nid = ppr.find(qn('w:numPr')).find(qn('w:numId')).get(qn('w:val'))
            for n in self.part.findall(qn('w:num')):
                if n.get(qn('w:numId')) == nid:
                    self.abs_of_style[name] = n.find(qn('w:abstractNumId')).get(qn('w:val'))
        self.next_id = max(int(n.get(qn('w:numId'))) for n in self.part.findall(qn('w:num'))) + 1
        self.next_abs = max(int(k) for k in self.abs) + 1
        self.last_abs = self.part.findall(qn('w:abstractNum'))[-1]
        self.last_num = self.part.findall(qn('w:num'))[-1]

    def restart(self, style_name):
        clone = self.copy.deepcopy(self.abs[self.abs_of_style[style_name]])
        clone.set(qn('w:abstractNumId'), str(self.next_abs))
        ns = clone.find(qn('w:nsid'))
        if ns is not None:
            ns.set(qn('w:val'), format(0x0DB40000 + self.next_abs, '08X'))
        for lvl in clone.findall(qn('w:lvl')):          # 스타일과의 연결(pStyle)은 원본 목록에만 남긴다
            for ps in lvl.findall(qn('w:pStyle')):
                lvl.remove(ps)
        self.last_abs.addnext(clone); self.last_abs = clone
        num = OxmlElement('w:num'); num.set(qn('w:numId'), str(self.next_id))
        a = OxmlElement('w:abstractNumId'); a.set(qn('w:val'), str(self.next_abs)); num.append(a)
        self.last_num.addnext(num); self.last_num = num
        self.next_id += 1; self.next_abs += 1
        return str(self.next_id - 1)


def _unbold(p):
    for r in p.findall(qn('w:r')):
        rpr = r.find(qn('w:rPr'))
        if rpr is not None:
            for b in rpr.findall(qn('w:b')) + rpr.findall(qn('w:bCs')):
                rpr.remove(b)


def _apply(p, sid, num_id=None, strip=None):
    ppr = p.find(qn('w:pPr'))
    if ppr is None:
        ppr = OxmlElement('w:pPr'); p.insert(0, ppr)
    ps = ppr.find(qn('w:pStyle'))
    if ps is None:
        ps = OxmlElement('w:pStyle'); ppr.insert(0, ps)
    ps.set(qn('w:val'), sid)
    for tag in ('w:numPr', 'w:ind'):
        for old in ppr.findall(qn(tag)):
            ppr.remove(old)
    if num_id is not None:
        npr = OxmlElement('w:numPr')
        il = OxmlElement('w:ilvl'); il.set(qn('w:val'), '0'); npr.append(il)
        ni = OxmlElement('w:numId'); ni.set(qn('w:val'), num_id); npr.append(ni)
        ps.addnext(npr)
    if strip:
        n = len(strip)
        for r in p.findall(qn('w:r')):
            if n <= 0:
                break
            for t in r.findall(qn('w:t')):
                cut = min(n, len(t.text or ''))
                t.text = (t.text or '')[cut:]; n -= cut
                if t.text:
                    t.set(qn('xml:space'), 'preserve')


def plan(doc):
    """([(p, kind, target_style, strip)], styles, sid2name, issues)  kind: h1 | sub | sub2 | body | blank
    issues: {'no_h1': bool, 'suspects': [문단 글자], 'orphans': [문단 글자], 'loose_captions': [캡션 글자]}"""
    styles = _styles(doc)
    sid2name = {s.get(qn('w:styleId')): n for n, s in styles.items()}
    by_id = {s.get(qn('w:styleId')): s for s in styles.values()}
    paras = [k for k in doc.element.body.iterchildren() if k.tag == qn('w:p')]
    i_start = next((i for i, p in enumerate(paras) if _text(p).replace('\t', '').replace(' ', '') == '다음'), None)
    if i_start is None:
        raise SystemExit("'다음' 문단을 찾지 못했습니다")
    # 끝 경계는 '다음' 뒤의 입증방법 제목이다. 서면명 제목('재심답변서(2)')에 별지제목을 쓰는 프레임도 있어
    # 스타일만 보고 '다음' 앞의 문단을 잡으면 범위가 비어 아무것도 검사하지 않게 된다.
    i_end = next((i for i, p in enumerate(paras) if i > i_start and _style_name(p, sid2name) == EV_TITLE
                  and re.sub(r'\s', '', _text(p)) == '입증방법'), None)
    if i_end is None:
        raise SystemExit("'다음' 뒤에서 '입 증 방 법'(별지제목) 문단을 찾지 못했습니다. "
                         "초안 끝에 '입 증 방 법' 줄이 있는지, 프레임의 입증방법 제목이 '별지제목' 스타일인지 확인합니다")
    # 1차: 대제목/소제목/(n)후보/본문/빈 문단 분류
    recs = []          # [p, kind, raw_text]
    ctx = None
    orphans = []       # 첫 대제목 앞이라 스타일을 정할 수 없는 글자 문단
    loose = []         # 그림 바로 앞 캡션인데 keepNext 가 없는 문단
    for p in paras[i_start + 1:i_end]:
        sn = _style_name(p, sid2name); raw = _text(p); t = raw.strip()
        if sn == S_H1 and t:
            ctx = 'h1'; recs.append([p, 'h1', raw]); continue
        nxt = p.getnext()
        if (sn in (CAPTION, 'Caption') and nxt is not None and nxt.tag == qn('w:p') and _has_drawing(nxt)
                and not _keeps_next(p, by_id)):
            loose.append(t)
        if sn == CAPTION or _has_drawing(p):
            continue
        ppr = p.find(qn('w:pPr')); jc = ppr.find(qn('w:jc')) if ppr is not None else None
        if jc is not None and jc.get(qn('w:val')) == 'center':
            continue
        if ctx is None:
            if t:
                orphans.append(p)
            continue
        if not t:
            recs.append([p, 'blank', raw]); continue
        if sn == S_SUB or SUB_RE.match(t):
            ctx = 'sub'; recs.append([p, 'sub', raw]); continue
        if sn == S_SUB2 or (ctx == 'sub' and SUB2_RE.match(t)):
            recs.append([p, 'cand', raw]); continue
        recs.append([p, 'body', raw])
    # 2차: 가. 구역마다 (n) 후보가 전부 한 문장이면 소제목, 아니면 본문
    out = []; i = 0
    while i < len(recs):
        p, kind, raw = recs[i]
        if kind != 'sub':
            out.append((p, kind, None, None)); i += 1; continue
        j = i + 1
        while j < len(recs) and recs[j][1] not in ('sub', 'h1'):
            j += 1
        section = recs[i + 1:j]
        cands = [r for r in section if r[1] == 'cand']
        as_head = bool(cands) and all(_one_sentence(r[2].strip()) or _style_name(r[0], sid2name) == S_SUB2 for r in cands)
        out.append((p, 'sub', None, None))
        sub_ctx = 'sub'
        for q, k, rw in section:
            if k == 'cand':
                if as_head:
                    sub_ctx = 'sub2'; out.append((q, 'sub2', None, None))
                else:
                    out.append((q, 'body', None, None))
            else:
                out.append((q, k, None, None))
        i = j
    # 목표 스타일과 지울 번호 글자 확정
    final = []; ctx = None
    for p, kind, _, _ in out:
        raw = _text(p)
        if kind == 'h1':
            ctx = 'h1'; final.append((p, kind, S_H1, None))
        elif kind == 'sub':
            ctx = 'sub'; m = SUB_RE.match(raw.lstrip()); final.append((p, kind, S_SUB, m.group(0) if m else None))
        elif kind == 'sub2':
            ctx = 'sub2'; m = SUB2_RE.match(raw.lstrip()); final.append((p, kind, S_SUB2, m.group(0) if m else None))
        else:
            final.append((p, kind, BODY_OF[ctx], None))
    suspects = [_text(p).strip() for p in orphans + [p for p, kind, _, _ in final if kind == 'body']
                if h1_candidate(_text(p))]
    issues = {'no_h1': not any(kind == 'h1' for _, kind, _, _ in final),
              'suspects': suspects,
              'orphans': [_text(p).strip() for p in orphans],
              'loose_captions': loose}
    return final, styles, sid2name, issues


def _short(texts, n=3):
    return "; ".join(repr(t[:30]) for t in texts[:n]) + (" …" if len(texts) > n else "")


def report(issues):
    """구조 이상을 출력하고, 점검 실패로 셀 건수를 돌려준다(대제목 앞 문단은 참고로만 알린다)."""
    bad = 0
    if issues['no_h1']:
        print("대제목('1.번호매기기') 문단이 하나도 없습니다 — 초안의 'N. 제목' 줄이 대제목으로 들어갔는지 확인합니다")
        bad += 1
    if issues['suspects']:
        print(f"대제목 누락 의심 {len(issues['suspects'])}건(번호 글자로 시작하는 본문 문단): " + _short(issues['suspects']))
        bad += len(issues['suspects'])
    if issues['loose_captions']:
        print(f"캡션 붙임(keepNext) 없음 {len(issues['loose_captions'])}건: " + _short(issues['loose_captions']))
        bad += len(issues['loose_captions'])
    if issues['orphans'] and not issues['no_h1']:
        print(f"참고: 첫 대제목 앞 문단 {len(issues['orphans'])}건은 스타일을 바꾸지 않았습니다: " + _short(issues['orphans']))
    return bad


def main(path, check=False, dry=False, backup=True):
    doc = Document(path)
    items, styles, sid2name, issues = plan(doc)
    for n in (S_H1_BODY, S_SUB, S_SUB_BODY, S_SUB2, S_SUB2_BODY):
        if n not in styles:
            raise SystemExit("프레임에 없는 스타일: " + n)
    sid = {n: styles[n].get(qn('w:styleId')) for n in styles}
    diff = [(p, kind, tgt, strip) for p, kind, tgt, strip in items
            if _style_name(p, sid2name) != tgt or strip or (kind == 'body' and _is_bold(p))]
    if check:
        print(f"계층 스타일 비정합 {len(diff)}건 / 대상 문단 {len(items)}건")
        bad = report(issues)
        return 1 if diff or bad else 0
    if dry:
        for p, kind, tgt, strip in diff:
            print(f"{_style_name(p, sid2name):>14} → {tgt:<14} {kind:<5} {_text(p)[:40]!r}")
        print(f"바꿀 문단 {len(diff)}건 / 대상 {len(items)}건")
        report(issues)
        return 0
    if not diff:
        print("바꿀 문단 없음"); return 0
    bak = os.path.splitext(path)[0] + '.bak_restyle.docx'
    if backup and not os.path.exists(bak):
        shutil.copy2(path, bak)
    numbering = Numbering(doc, styles)
    cur = {'sub': None, 'sub2': None}
    for p, kind, tgt, strip in items:          # 번호 다시 시작은 전체 순서를 따라야 하므로 items 전체를 돈다
        if kind == 'h1':
            cur['sub'] = cur['sub2'] = None; continue
        if kind == 'sub':
            if cur['sub'] is None:
                cur['sub'] = numbering.restart(S_SUB)
            cur['sub2'] = None
            _apply(p, sid[tgt], cur['sub'], strip); _unbold(p)
        elif kind == 'sub2':
            if cur['sub2'] is None:
                cur['sub2'] = numbering.restart(S_SUB2)
            _apply(p, sid[tgt], cur['sub2'], strip); _unbold(p)
        elif _style_name(p, sid2name) != tgt or (kind == 'body' and _is_bold(p)):
            _apply(p, sid[tgt])
            if kind == 'body':
                _unbold(p)
    doc.save(path)
    c = Counter(tgt for _, _, tgt, _ in diff)
    print(f"{len(diff)}건 변경: " + ", ".join(f"{k} {v}" for k, v in c.items()) + (f" (원본 → {os.path.basename(bak)})" if backup else ""))
    return 0


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__); sys.exit(0)
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1], check='--check' in sys.argv, dry='--dry' in sys.argv))
