# -*- coding: utf-8 -*-
"""서면 docx 의 발췌 그림이 다음 면으로 밀려 앞 면 아래가 크게 비는 곳을 찾아, 그림을 비율대로 조금 줄여 앞 면에 들어가게 맞춘다.

2026. 10. 16. 담당 노무사 지시: "앞으로는 그림자료 넣을 때 크기때문에 애매하게 한 장에 여백 많이 생기면 전체적으로 조금 사이즈
줄이면서 조정까지 해보는걸로". 2026. 10. 3. 한영대 사건의 같은 취지 지시("사진이 커서 다음장으로 넘어가 한 장에 반 이상이 공백인
경우도 있는데 사진 크기 조금 조절해서 멀끔하게 처리")로 그 사건 빌드에 만든 `그림_크기_맞추기.py`·`제목_면끝_방지.py` 3항을
어느 서면에나 쓰게 옮겼다.

 - 발췌 그림은 캡션('[' 로 시작하는 문단) 바로 뒤(빈 문단 하나까지)에 이어지는 그림 문단이다. 두 장으로 나눈 그림(docx_merge.py)은
   잇달은 그림 문단을 한 그림으로 보고 함께 줄인다. 표지·서명 블록의 로고처럼 캡션이 없는 그림, 표 안의 그림, 변경 추적으로 지운
   그림은 건드리지 않는다. PDF 의 그림과는 캡션 글자로 짝짓는다.
 - 1단계: 발췌 그림의 마지막 그림 문단에 걸린 '다음 문단과 함께'(keepNext)를 푼다. 캡션의 설정은 그대로 두어 캡션과 그림은 같은
   면에 남는다. 걸려 있으면 그림 뒤 빈 문단까지(그 빈 문단에도 걸려 있으면 뒤 본문까지) 한 면에 들어가야 해서 그림이 통째로 다음
   면으로 밀린다(2026. 10. 16. OES 답변서(1) 사 제8호증은 58pt 그림인데 앞 면 187pt 가 비었다).
 - 2단계: Word 로 PDF 를 내보내(변경 추적을 모두 받아들이고 메모를 지운 최종 모습) 면 머리가 캡션이고 앞 면 아래가 크게 빈 곳을
   앞에서부터 찾는다. 앞 면 남은 높이에 (캡션 앞 간격 + 캡션 + 그림)이 들어가도록 그 그림과 바로 앞 발췌 그림(앞 면이나 그 앞 면에
   있는 것)을 줄일 수 있는 만큼에 비례해 나누어 줄인다. 하한까지 줄여도 모자라면 손대지 않고 알린다. 줄였는데도 넘어가지 않으면
   12pt 씩 더 줄여 보고, 하한에 닿으면 그 자리를 위해 줄인 그림을 원래 크기로 되돌린다. 줄이면 뒤쪽 면 나눔이 바뀌므로 한 번에
   한 곳씩 고치고 다시 내보내 확인한다.
 - 하한은 처음 넣은 크기(폭 15cm, 세로 최대 14cm, docx_merge.py) 대비 --하한(기본 0.7)이다. 그림 속 글자가 읽히는 선을 지킨다.
   하한이 모자라 그대로 둔 그림은 '이 그림만 줄이면 얼마까지'를 알려 준다. 그림을 열어 글자가 커서 더 줄여도 읽히면 그 그림에만
   --그림하한 "캡션 일부=값" 으로 낮추어 다시 돌린다(한영대 사건은 말풍선 글자가 큰 캡처를 0.66 까지 줄였다).
 - 앞 면에 각주가 있으면 각주가 면 아래를 차지하므로 빈 곳으로 보지 않는다.
 - 바꾸는 것은 그림의 표시 크기(wp:extent, a:ext)와 1단계의 keepNext 뿐이다. 글자·그림 파일·캡션은 건드리지 않고 변경 내용
   추적에도 남지 않는다. 검토본(변경 추적본)에 돌리면 클린본은 그 검토본에서 다시 만든다(목차 쪽 번호도 그때 맞춘다).
 - OneDrive 밖(%TEMP%/figure_fit)의 사본에서 고치고 확인한 뒤에 원래 자리에 쓴다. 고치기 전 파일은 docx_merge.py 처럼
   '{이름}.bak_그림맞춤_{일시}.docx' 로 같은 폴더(--보관 을 주면 그 폴더)에 남긴다. Word 는 이 스크립트가 띄운 것만 닫는다.

쓰는 법:
    python -B 4_서면작성/scripts/figure_fit.py "<서면.docx>"             # 고친다
    python -B 4_서면작성/scripts/figure_fit.py "<서면.docx>" --확인      # 사본에서 끝까지 해 보고 무엇을 바꿀지만 알린다
    python -B 4_서면작성/scripts/figure_fit.py "<서면.docx>" --그림하한 "사 제24호증=0.65" --보관 "<폴더>"
    python -B 4_서면작성/scripts/figure_fit.py "<서면.docx>" --하한 0.65 --시도 15
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import statistics
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'}
W = '{%s}' % NS['w']
INLINE = '{%s}inline' % NS['wp']
처음폭, 처음높이 = 5400000, 5040000          # docx_merge.py 가 넣는 크기(폭 15cm, 세로 최대 14cm), EMU
최소빈자리 = 60.0                            # 앞 면에 남은 높이가 이보다 작으면 손대지 않는다(pt)
여유 = 8.0                                   # 계산 오차 여유(pt)
더줄임 = 12.0                                # 줄였는데도 넘어가지 않을 때 한 번에 더 줄이는 높이(pt)
기본간격 = 42.0                              # 문서에서 재지 못할 때 캡션 앞 간격(pt). 2026. 10. 3. 한영대 실측 41pt
붙은그림 = 12.0                              # PDF 에서 이 간격 안으로 잇달은 그림은 한 그림(두 장으로 나눈 그림)
캡션거리 = 30.0                              # 캡션 아래 끝과 그림 위 끝 사이가 이 안이면 그 그림의 캡션


def 글(el) -> str:
    return ''.join(t.text or '' for t in el.iter(W + 't'))


def 키(text) -> str:
    return ''.join(text.split())


def keep_next(p) -> bool:
    pPr = p.find(W + 'pPr')
    k = pPr.find(W + 'keepNext') if pPr is not None else None
    return k is not None and k.get(W + 'val') not in ('0', 'false', 'off')


def 지운것(el) -> bool:
    """변경 추적으로 지운 자리(w:del 안)인가."""
    p = el.getparent()
    while p is not None:
        if p.tag == W + 'del':
            return True
        p = p.getparent()
    return False


def 그림들(p) -> list:
    return [i for i in p.iter(INLINE) if not 지운것(i)]


def 발췌목록(body) -> list:
    """본문 차례대로 발췌 그림마다 {'cap': 캡션 글, 'inls': [inline…], 'paras': [그림 문단…], 'cap_p': 캡션 문단}."""
    문단 = [e for e in body if e.tag == W + 'p']
    out, i = [], 0
    while i < len(문단):
        p = 문단[i]
        if not 글(p).strip().startswith('[') or 그림들(p):
            i += 1
            continue
        j = i + 1
        if j < len(문단) and not 글(문단[j]).strip() and not 그림들(문단[j]):
            j += 1                                   # 캡션과 그림 사이 빈 문단 하나까지
        paras = []
        while j < len(문단) and 그림들(문단[j]) and not 글(문단[j]).strip():
            paras.append(문단[j])
            j += 1
        if paras:
            out.append({'cap': 글(p).strip(), 'inls': [x for q in paras for x in 그림들(q)], 'paras': paras, 'cap_p': p})
            i = j
        else:
            i += 1
    return out


def 묶음풀기(발췌들) -> int:
    """발췌 그림의 마지막 그림 문단에 직접 걸린 keepNext 를 끈다(앞 그림 문단과 캡션의 설정은 그대로)."""
    풀림 = 0
    for f in 발췌들:
        p = f['paras'][-1]
        if keep_next(p):
            p.find(W + 'pPr').find(W + 'keepNext').set(W + 'val', '0')
            풀림 += 1
    return 풀림


def 크기(inl):
    e = inl.find('wp:extent', NS)
    return int(e.get('cx')), int(e.get('cy'))


def 크기바꾸기(inl, cx, cy):
    e = inl.find('wp:extent', NS)
    e.set('cx', str(int(round(cx))))
    e.set('cy', str(int(round(cy))))
    a = inl.find('.//pic:spPr/a:xfrm/a:ext', NS)
    if a is not None:
        a.set('cx', str(int(round(cx))))
        a.set('cy', str(int(round(cy))))


def 비율(inl) -> float:
    """처음 넣은 크기(폭 15cm, 세로 최대 14cm 안에 가로세로 비대로) 대비 지금 크기."""
    cx, cy = 크기(inl)
    return max(cx / 처음폭, cy / 처음높이)


def 본문범위(root):
    """첫 구역의 (본문 위 끝, 본문 아래 끝) pt. 머리글·바닥글(로고·쪽 번호)은 이 밖에 있다."""
    sect = root.find('.//' + W + 'sectPr')
    sz, mar = sect.find(W + 'pgSz'), sect.find(W + 'pgMar')
    h = int(sz.get(W + 'h')) / 20
    return int(mar.get(W + 'top')) / 20, h - int(mar.get(W + 'bottom')) / 20


def 면분석(pdf_path, 위, 아래):
    """(면들, 발췌들, 캡션 앞 간격). 면마다 {'bottom': 보이는 것의 아래 끝, 'first': 위 끝}.
    발췌들은 캡션이 바로 위에 있는 그림(잇달은 그림은 하나로)마다 {'k': 면 번호, 'cap': 캡션 글, 'cap_top', 'top', 'bottom'}."""
    import pymupdf
    d = pymupdf.open(pdf_path)
    면들, 발췌들, 앞간격 = [], [], []
    for k, pg in enumerate(d):
        줄들 = []
        for b in pg.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                t = ''.join(s['text'] for s in ln['spans'])
                y0, y1 = ln['bbox'][1], ln['bbox'][3]
                if t.strip() and y0 >= 위 - 6 and y1 <= 아래 + 6:
                    줄들.append((y0, y1, t))
        줄들.sort()
        rects = []
        for x in pg.get_images(full=True):
            for r in pg.get_image_rects(x[0]):
                if r.y0 >= 위 - 6 and r.y1 <= 아래 + 6 and r.height > 2:
                    rects.append((r.y0, r.y1))
        rects = sorted(set((round(a, 1), round(b, 1)) for a, b in rects))
        뭉치 = []
        for a, b in rects:                           # 잇달은 그림(두 장으로 나눈 그림, 나란한 그림)은 한 뭉치
            if 뭉치 and a - 뭉치[-1][1] <= 붙은그림:
                뭉치[-1] = (뭉치[-1][0], max(뭉치[-1][1], b))
            else:
                뭉치.append((a, b))
        for a, b in 뭉치:
            위줄 = [z for z in 줄들 if z[1] <= a + 2 and a - z[1] <= 캡션거리]
            if not 위줄:
                continue
            n = 줄들.index(max(위줄, key=lambda z: z[1]))
            캡 = [줄들[n]]
            while not 캡[0][2].strip().startswith('[') and n > 0 and len(캡) < 3 and 캡[0][0] - 줄들[n - 1][1] <= 8:
                n -= 1
                캡.insert(0, 줄들[n])
            if not 캡[0][2].strip().startswith('['):
                continue
            cap_top = 캡[0][0]
            발췌들.append({'k': k, 'cap': ''.join(z[2] for z in 캡), 'cap_top': cap_top, 'top': a, 'bottom': b})
            앞 = [z[1] for z in 줄들 if z[1] <= cap_top - 1] + [y1 for y0, y1 in 뭉치 if y1 <= cap_top - 1]
            if 앞:
                앞간격.append(cap_top - max(앞))
        보임 = [z[0] for z in 줄들] + [a for a, _ in 뭉치]
        면들.append({'bottom': max([z[1] for z in 줄들] + [b for _, b in 뭉치] + [위]),
                     'first': min(보임) if 보임 else None})
    return 면들, 발췌들, (statistics.median(앞간격) if 앞간격 else 기본간격)


def 짝짓기(pdf발췌, 문서발췌) -> tuple:
    """PDF 발췌마다 문서 발췌 번호를 캡션 글자(공백 무시)로 차례대로 짝짓는다. (짝 목록, PDF 에서 못 찾은 문서 발췌 번호)."""
    짝, j = [], 0
    for f in pdf발췌:
        while j < len(문서발췌) and 키(문서발췌[j]['cap']) != 키(f['cap']):
            j += 1
        if j == len(문서발췌):
            raise SystemExit('PDF 의 캡션 "%s" 를 문서의 발췌 그림 캡션에서 찾지 못하였다' % f['cap'][:40])
        짝.append(j)
        j += 1
    return 짝, [i for i in range(len(문서발췌)) if i not in 짝]


def 계획(면들, 발췌들, 간격, 아래, 여력, 보탬=None, 제외=()):
    """처음 고칠 한 곳: {'k': 면, 'n': 발췌 번호, '남은', '모자람', '줄일': {발췌 번호: 줄일 높이 pt} 또는 None}.
    '줄일' 이 None 이면 하한까지 줄여도 모자란다. 크기로 설명되지 않는 곳(어림으로는 이미 들어가야 하는 곳)은 '모자람' 이 0 이하로
    돌아오고 '줄일' 은 빈 사전이다. 없으면 None. 발췌 번호는 발췌들(PDF 차례)의 번호이다."""
    보탬 = 보탬 or {}
    for n, f in enumerate(발췌들):
        k = f['k']
        if n in 제외 or k == 0 or 면들[k]['first'] is None or abs(면들[k]['first'] - f['cap_top']) > 1:
            continue                                 # 캡션이 면 머리에 있지 않다
        남은 = 아래 - 면들[k - 1]['bottom']
        if 남은 <= 최소빈자리:
            continue
        필요 = 간격 + (f['bottom'] - f['cap_top']) + 보탬.get(n, 0.0) + 여유
        모자람 = 필요 - 남은
        안 = {'k': k, 'n': n, '남은': 남은, '모자람': 모자람}
        if 모자람 <= 0:
            return dict(안, 줄일={})
        F = 여력[n]
        G = n - 1 if n >= 1 and 발췌들[n - 1]['k'] in (k - 1, k - 2) and 여력[n - 1] > 0 else None
        Gm = 여력[G] if G is not None else 0.0
        if 모자람 > F + Gm:
            return dict(안, 줄일=None)
        if G is None:
            return dict(안, 줄일={n: 모자람})
        return dict(안, 줄일={n: 모자람 * F / (F + Gm), G: 모자람 * Gm / (F + Gm)})
    return None


def 워드열기():
    import win32com.client
    app = win32com.client.DispatchEx('Word.Application')
    app.Visible = False
    app.DisplayAlerts = 0
    return app


def 내보내기(app, docx, 작업):
    """사본에서 변경 추적을 모두 받아들이고 메모를 지운 최종 모습을 PDF 로 내보낸다."""
    src, pdf = os.path.join(작업, 'export.docx'), os.path.join(작업, 'export.pdf')
    for f in (src, pdf):
        if os.path.exists(f):
            os.remove(f)
    shutil.copyfile(docx, src)
    doc = app.Documents.Open(src, False, False)
    try:
        doc.TrackRevisions = False
        doc.Revisions.AcceptAll()
        if doc.Comments.Count:
            doc.DeleteAllComments()
        doc.ExportAsFixedFormat(pdf, 17)
    finally:
        doc.Close(False)
    if not os.path.exists(pdf):
        raise SystemExit('Word 로 PDF 를 내보내지 못하였다')
    return pdf


def 읽기(docx):
    from lxml import etree
    with zipfile.ZipFile(docx) as z:
        return etree.fromstring(z.read('word/document.xml'))


def 저장(docx, root):
    from lxml import etree
    tmp = docx + '.tmp'
    with zipfile.ZipFile(docx) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            zout.writestr(item, data)
    os.replace(tmp, docx)


def 보관이름(docx, 폴더=None):
    stem = os.path.splitext(os.path.basename(docx))[0] + '.bak_그림맞춤_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    폴더 = os.path.abspath(폴더) if 폴더 else os.path.dirname(docx)
    os.makedirs(폴더, exist_ok=True)
    bak, k = os.path.join(폴더, stem + '.docx'), 2
    while os.path.exists(bak):
        bak, k = os.path.join(폴더, '%s_%d.docx' % (stem, k)), k + 1
    return bak


def 하한값(cap, 하한, 그림하한=None) -> float:
    """캡션에 '캡션 일부'(공백 무시)가 든 그림은 --그림하한 값, 아니면 --하한."""
    for 앞, v in (그림하한 or {}).items():
        if 키(앞) in 키(cap):
            return v
    return 하한


def 맞추기(app, 일본, 작업, 하한, 시도, 말, 그림하한=None):
    """일본(사본 docx)을 고친다. 바뀐 것이 있으면 True."""
    root = 읽기(일본)
    위, 아래 = 본문범위(root)
    문서 = 발췌목록(root.find(W + 'body'))
    말('발췌 그림 %d개, 본문 %.0f~%.0fpt' % (len(문서), 위, 아래))
    풀림 = 묶음풀기(문서)
    if 풀림:
        저장(일본, root)
    말('1단계: 발췌 그림 문단의 \'다음 문단과 함께\' %d곳을 풂(캡션과는 붙어 있음)' % 풀림)
    바뀜 = bool(풀림)
    원래 = {}           # 자리(문서 발췌 번호) → {문서 발췌 번호: 줄이기 전 [(cx, cy)…]}
    보탬, 포기, 지난 = {}, set(), None
    회, 새로 = 0, True  # 새로: 문서가 바뀌어 다시 내보내야 한다
    while True:
        if 새로:
            if 회 == 시도:
                말('시도 %d회를 다 썼다. 남은 빈 곳은 --확인 으로 다시 본다' % 시도)
                return 바뀜
            회, 새로 = 회 + 1, False
            면들, pdf발췌, 간격 = 면분석(내보내기(app, 일본, 작업), 위, 아래)
            짝, 못찾음 = 짝짓기(pdf발췌, 문서)
            if 회 == 1 and 못찾음:
                말('  참고: PDF 에서 캡션 바로 아래 그림을 찾지 못한 발췌 %d개(손대지 않음): %s'
                  % (len(못찾음), ', '.join(문서[i]['cap'][:24] for i in 못찾음)))
            높이 = [f['bottom'] - f['top'] for f in pdf발췌]
            여력 = [max(0.0, h * (1 - 하한값(문서[짝[n]]['cap'], 하한, 그림하한) / min(비율(x) for x in 문서[짝[n]]['inls'])))
                   for n, h in enumerate(높이)]
        제외 = {n for n in range(len(pdf발췌)) if 짝[n] in 포기}
        보탬n = {n: 보탬[짝[n]] for n in range(len(pdf발췌)) if 짝[n] in 보탬}
        안 = 계획(면들, pdf발췌, 간격, 아래, 여력, 보탬n, 제외)
        if 안 is None:
            말('%d회: 그림 때문에 앞 면이 크게 빈 곳이 없다(%d면, 캡션 앞 간격 %.0fpt)' % (회, len(면들), 간격))
            return 바뀜
        자리 = 짝[안['n']]
        이름 = 문서[자리]['cap'][:30]
        줄일 = 안['줄일']
        if 줄일 == {}:                               # 어림으로는 이미 들어가야 하는데 넘어가 있다
            if 지난 != 자리:
                말('%d회: %d면 머리 %s — 앞 면 남은 %.0fpt 에 크기로는 들어가야 하는데 넘어가 있어 그대로 둠'
                  '(앞뒤 문단의 \'다음 문단과 함께\'·면 나눔을 본다)' % (회, 안['k'] + 1, 이름, 안['남은']))
                포기.add(자리)
                continue
            보탬[자리] = 보탬.get(자리, 0.0) - 안['모자람'] + 더줄임
            보탬n[안['n']] = 보탬[자리]
            안 = 계획(면들, pdf발췌, 간격, 아래, 여력, 보탬n, 제외)
            줄일 = 안['줄일']
            말('%d회: 줄였는데도 넘어가 있어 %.0fpt 더 줄여 봄' % (회, 더줄임))
        if 줄일 is None:
            if 자리 in 원래:
                for i, 크기들 in 원래.pop(자리).items():
                    for inl, (cx, cy) in zip(문서[i]['inls'], 크기들):
                        크기바꾸기(inl, cx, cy)
                저장(일본, root)
                새로 = True
                말('%d회: %d면 머리 %s — 하한(%.2f)까지 줄여도 넘어가지 않아 이 자리를 위해 줄인 그림을 원래 크기로 되돌림'
                  % (회, 안['k'] + 1, 이름, 하한값(문서[자리]['cap'], 하한, 그림하한)))
            else:
                h = 높이[안['n']]
                혼자 = min(비율(x) for x in 문서[자리]['inls']) * (h - 안['모자람']) / h
                말('%d회: %d면 머리 %s — 앞 면 남은 %.0fpt 에 넣으려면 %.0fpt 를 줄여야 하는데 하한(%.2f)까지 줄여도 모자라 그대로 둠'
                  '(이 그림만 줄이면 처음 크기 대비 %.2f)'
                  % (회, 안['k'] + 1, 이름, 안['남은'], 안['모자람'], 하한값(문서[자리]['cap'], 하한, 그림하한), 혼자))
            포기.add(자리)
            지난 = None
            continue
        for n, d in 줄일.items():
            i = 짝[n]
            원래.setdefault(자리, {}).setdefault(i, [크기(x) for x in 문서[i]['inls']])
            s = (높이[n] - d) / 높이[n]
            전 = min(비율(x) for x in 문서[i]['inls'])
            for inl in 문서[i]['inls']:
                cx, cy = 크기(inl)
                크기바꾸기(inl, cx * s, cy * s)
            말('%d회: %d면 앞 면 남은 %.0fpt — %s 높이 %.0f → %.0fpt(처음 크기 대비 %.2f → %.2f)'
              % (회, 안['k'] + 1, 안['남은'], 문서[i]['cap'][:30], 높이[n], 높이[n] - d, 전, 전 * s))
        저장(일본, root)
        바뀜, 지난, 새로 = True, 자리, True


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('docx')
    ap.add_argument('--하한', type=float, default=0.7, help='처음 넣은 크기 대비 줄일 수 있는 하한(기본 0.7)')
    ap.add_argument('--시도', type=int, default=12, help='고치고 다시 내보내 보는 횟수(기본 12)')
    ap.add_argument('--그림하한', action='append', default=[], metavar='캡션 일부=값',
                    help='그 그림에만 쓸 하한(글자가 커서 더 줄여도 읽히는 그림). 여러 번 줄 수 있다')
    ap.add_argument('--확인', action='store_true', help='사본에서만 해 보고 원래 파일은 고치지 않는다')
    ap.add_argument('--보관', help='고치기 전 파일을 남길 폴더(기본: 같은 폴더)')
    a = ap.parse_args(argv)
    그림하한 = {}
    for s in a.그림하한:
        앞, _, v = s.rpartition('=')
        if not 앞.strip():
            ap.error('--그림하한 은 "캡션 일부=값" 으로 준다: %s' % s)
        그림하한[앞.strip()] = float(v)
    docx = os.path.abspath(a.docx)
    if not a.확인:
        try:
            with open(docx, 'r+b'):
                pass
        except PermissionError:
            raise SystemExit('파일이 Word 에서 열려 있어 고칠 수 없다. 닫고 다시 돌린다: %s' % docx)
    작업 = os.path.join(tempfile.gettempdir(), 'figure_fit')
    os.makedirs(작업, exist_ok=True)
    일본 = os.path.join(작업, 'work.docx')
    shutil.copyfile(docx, 일본)
    app = 워드열기()
    try:
        바뀜 = 맞추기(app, 일본, 작업, a.하한, a.시도, print, 그림하한)
    finally:
        if app.Documents.Count == 0:
            app.Quit()
    if not 바뀜:
        print('바꾼 것이 없다')
        return 0
    if a.확인:
        print('확인만 하였다(원래 파일은 그대로). 해 본 결과: %s' % 일본)
        return 0
    bak = 보관이름(docx, a.보관)
    shutil.copyfile(docx, bak)
    shutil.copyfile(일본, docx)
    print('저장: %s\n고치기 전: %s' % (docx, bak))
    return 0


if __name__ == '__main__':
    sys.exit(main())
