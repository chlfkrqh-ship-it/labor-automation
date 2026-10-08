# -*- coding: utf-8 -*-
"""리서치 문서(docx)를 리서치 양식으로 만든다(문단 + 출처·원문 박스 + 표).

    python -B 공통/scripts/research_docx.py <내용.json>                docx 생성
    python -B 공통/scripts/research_docx.py <내용.json> --out <폴더>   시험 빌드. 그 폴더에만 쓰고 빌드기록·글 사본은 남기지 않는다
    python -B 공통/scripts/research_docx.py <내용.json> --check        현재 docx 가 마지막 빌드 그대로인지 확인(사람이 고쳤는지)
    python -B 공통/scripts/research_docx.py <내용.json> --force        사람이 고친 docx 라도 덮어쓴다
    python -B 공통/scripts/research_docx.py <내용.json> --md           docx 는 두고 글 사본(md)만 다시 쓴다

무엇을 어떻게 적는지는 2_판례검색/CLAUDE.md 5절 '리서치 문서(docx)'에 있다. 이 파일은 모양만 만든다.

내용 파일은 사건 폴더의 작업/빌드/ 에 둔다. docx 는 내용 파일의 "출력" 이름으로, 내용 파일이 빌드/ 폴더에
있으면 그 위 폴더(작업/)에, 아니면 내용 파일과 같은 폴더에 쓴다. "글사본"이 있으면 같은 자리에 md 도 쓴다.
빌드기록({이름}_빌드기록.json)은 내용 파일 옆에 둔다. 모양을 고쳐 보는 동안에는 --out 으로 사건 폴더가
아닌 곳에 빌드해 Word 로 확인하고, 다 된 뒤에 한 번만 사건 폴더에 쓴다(담당자가 중간본을 열어 보기 때문이다).

양식은 2_판례검색/양식/(리서치) 운전원 휴게시간 관련.docx 이다(의뢰인 자료가 든 실제 결과물이라 git 에는
없고 OneDrive 로만 온다). 양식의 머리말·꼬리말·스타일은 그대로 두고 word/document.xml 본문만 새로 쓰며,
머리글의 옛 전화번호(6010-6565·6566)는 6747-6565·6566 으로 바꾼다. '1.' 제목은 양식의 자동 번호이고,
'가.' 소제목은 번호를 글자로 적는다(sub_heading 설명 참조).

내용.json 의 맨 위
    "제목": "(리서치) ...", "출력": "(리서치) ....docx", "글사본": "....md"(없어도 됨)
    "문단나눔": true   본문 문단이 면 사이에서 갈라질 수 있다(면 아래 빈 곳이 줄어든다)
    "왼쪽정렬": true   본문·표지 문단을 왼쪽 정렬로 둔다(양쪽 정렬은 낱말 사이가 벌어지는 줄이 생긴다)
    "머리": [..]       제목 아래 문단. 담당자는 머리 문단을 두지 않으므로 쓰지 않는다
    "꼬리": [..]       문서 맨 끝의 작은 참고 줄. 검색 범위 같은 작업 내역은 적지 않는다

내용.json 의 절
    {"제목": "...", "새면": true, "블록": [..], "항": [{"제목": "...", "블록": [..]}]}   새면이면 새 면에서 시작

내용.json 의 블록
    {"문": "..."}                              본문 문단
    {"표지": "①", "문": "...", "너비": 300}    굵은 표지 + 내어쓰기 문단(번호·글머리 목록에도 쓴다)
    {"박스": [{"출처": "...", "원문": ["..."], "음영": true, "왼쪽": true}]}   출처(굵게) + 원문. 왼쪽은 그 행만 왼쪽 정렬
    {"표": {"열": [..], "머리": [..], "행": [[..]]}}             여러 칸짜리 표. 칸 안의 줄바꿈은 \n
                                               행에 {"묶음": "..."} 을 넣으면 가로로 합친 음영 행(묶음 제목)
    {"카드": {..}}, {"대비": {..}}             조서 진술과 자료를 맞세우는 표(card, contrast 설명 참조)

글자 안의 표시: **굵게**, [[회색]]. 문단·표·카드 어디서나 쓴다.

GGM_변호인의견서 사건의 피신리서치_build.py(2026. 10. 1.)를 하나기술 사건에서 다듬어(2026. 10. 8.) 여기로 옮겼다.
"""
import sys
sys.dont_write_bytecode = True

import datetime
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]      # 저장소 루트
TEMPLATE = ROOT / '2_판례검색' / '양식' / '(리서치) 운전원 휴게시간 관련.docx'

HINT = '<w:rFonts w:hint="eastAsia"/>'
NBSP = chr(0xA0)      # 줄바꿈 없는 공백(U+00A0). 글자로 직접 적으면 편집 도구가 보통 공백으로 바꿀 수 있어 코드로 만든다
LINE = 252            # 본문·박스 줄 간격(240 = 한 줄, 양식 기본은 276)
INDENT = 220          # '가.' 아래 본문 들여쓰기(1/20 pt). '가.' 번호 위치와 같다
LABEL = 1040          # '수정 방향'·'확인' 표지 너비
TEXT_W = 9016         # 본문 폭(1/20 pt)
SHADE = 'EEF1F5'      # 조서 진술 칸 음영
HEAD = 'E1E6EC'       # 표 머리 칸 음영
NUM_GAP = 360         # '가.' 번호와 제목 사이(양식 '가.' 번호 정의의 내어쓰기와 같다)
GANADA = '가나다라마바사아자차카타파하'
GRAY = '595959'       # [[...]] 로 적은 덜 중요한 글자(질문 요지 등)
CIRCLED = '①②③④⑤⑥⑦⑧⑨'
MARK = re.compile(r'(\*\*.+?\*\*|\[\[.+?\]\])')
TAB = '<w:r><w:tab/></w:r>'


def nb_dates(text):
    """'2024. 7. 16.' 같은 날짜가 줄 끝에서 갈라지지 않게 안의 공백을 줄바꿈 없는 공백으로 바꾼다."""
    text = re.sub(r'(\d{4})\. (\d{1,2})\. (\d{1,2})\.',
                  lambda m: NBSP.join((m.group(1) + '.', m.group(2) + '.', m.group(3) + '.')), text)
    text = re.sub(r'(\d{4})\. (\d{1,2})\.(?!\d)',
                  lambda m: NBSP.join((m.group(1) + '.', m.group(2) + '.')), text)
    return re.sub(r'(?<![\d.])(\d{1,2})\. (\d{1,2})\.(?!\d)',
                  lambda m: NBSP.join((m.group(1) + '.', m.group(2) + '.')), text)


def run(text, bold=False, size=None, color=None):
    rpr = '<w:rPr>%s%s%s%s</w:rPr>' % (
        HINT, '<w:b/><w:bCs/>' if bold else '',
        '<w:color w:val="%s"/>' % color if color else '',
        '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size) if size else '')
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, escape(nb_dates(text)))


def rich(text, bold=False, size=None):
    """글자 안의 **굵게**, [[회색]] 표시를 run 으로 바꾼다. 표시가 없으면 run 하나와 같다."""
    out = []
    for tok in MARK.split(text):
        if not tok:
            continue
        if tok.startswith('**') and tok.endswith('**') and len(tok) > 4:
            out.append(run(tok[2:-2], True, size))
        elif tok.startswith('[[') and tok.endswith(']]'):
            out.append(run(tok[2:-2], bold, size, GRAY))
        else:
            out.append(run(tok, bold, size))
    return ''.join(out)


def spacing(before=0, after=None, line=LINE):
    attrs = []
    if before:
        attrs.append('w:before="%d"' % before)
    if after is not None:
        attrs.append('w:after="%d"' % after)
    attrs.append('w:line="%d" w:lineRule="auto"' % line)
    return '<w:spacing %s/>' % ' '.join(attrs)


LEFT_ALIGN = False    # 내용 파일의 "왼쪽정렬". 켜면 본문·표지 문단을 양쪽 정렬 대신 왼쪽 정렬로 둔다


def body_par(text, bold=False, before=0, after=60, indent=0, keep_next=False, size=None,
             align=None, line=LINE, keep_lines=True):
    """본-문 문단."""
    # 양식의 본-문은 양쪽 정렬이라 어절 단위로 줄이 바뀌면 낱말 사이가 크게 벌어지는 줄이 생긴다
    if align is None and LEFT_ALIGN:
        align = 'left'
    # 갈라질 수 있는 문단은 면 끝·면 머리에 한 줄만 남지 않게 한다(widowControl)
    ppr = '<w:pPr><w:pStyle w:val="-"/>%s%s%s%s%s%s</w:pPr>' % (
        '<w:keepNext/>' if keep_next else '',
        '<w:keepLines/>' if keep_lines else '<w:widowControl/>',
        spacing(before, after, line),
        '<w:ind w:left="%d"/>' % indent if indent else '',
        '<w:jc w:val="%s"/>' % align if align else '',
        '<w:rPr><w:b/><w:bCs/></w:rPr>' if bold else '')
    return '<w:p>%s%s</w:p>' % (ppr, rich(text, bold, size) if text else '')


def label_par(label, text, before=0, after=90, indent=0, width=LABEL):
    """굵은 표지('수정 방향'·'확인' 등) 뒤에 내용을 내어쓰기로 붙인 문단. 표지가 비면 같은 위치로 들여 쓴다."""
    # keepLines 를 주지 않는다. 문단이 면 끝에서 갈라질 수 있어야 면 아래가 덜 빈다
    jc = '<w:jc w:val="left"/>' if LEFT_ALIGN else ''
    if not label:
        ppr = '<w:pPr><w:pStyle w:val="-"/><w:widowControl/>%s<w:ind w:left="%d"/>%s</w:pPr>' % (
            spacing(before, after), indent + width, jc)
        return '<w:p>%s%s</w:p>' % (ppr, rich(text))
    ppr = ('<w:pPr><w:pStyle w:val="-"/><w:widowControl/>'
           '<w:tabs><w:tab w:val="left" w:pos="%d"/></w:tabs>%s'
           '<w:ind w:left="%d" w:hanging="%d"/>%s</w:pPr>' % (
               indent + width, spacing(before, after), indent + width, width, jc))
    return '<w:p>%s%s<w:r><w:tab/></w:r>%s</w:p>' % (ppr, run(label, bold=True), rich(text))


def heading(text, new_page=False):
    """'1.' 번호 제목. 양식의 첫 제목과 같이 앞 간격을 둔다. new_page 이면 새 면에서 시작한다."""
    return ('<w:p><w:pPr><w:pStyle w:val="1"/><w:keepNext/>%s<w:spacing w:before="%d" w:after="80"/></w:pPr>%s</w:p>'
            % ('<w:pageBreakBefore/>' if new_page else '', 0 if new_page else 320, run(text)))


def sub_heading(text, order):
    """'가.' 소제목. 양식의 '가.' 스타일 모양을 쓰되 번호는 글자로 적는다.

    절마다 번호를 다시 시작하려고 startOverride 를 준 자동 번호를 썼더니, Word 가 PDF 로 내보낼 때
    한 절 안에서 다섯째 항을 다시 '가.'로 매긴 일이 있었다(2026. 10. 1. 확인, LibreOffice 는 정상).
    1절 표와 본문이 '2-가'처럼 항 번호를 가리키므로 번호가 흔들리지 않게 글자로 고정한다.
    """
    if order >= len(GANADA):
        raise SystemExit("한 절의 항이 %d개를 넘습니다: %s" % (len(GANADA), text))
    return ('<w:p><w:pPr><w:pStyle w:val="a0"/><w:keepNext/>'
            '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>'
            '<w:tabs><w:tab w:val="left" w:pos="%d"/></w:tabs>'
            '<w:spacing w:before="220" w:after="40"/>'
            '<w:ind w:left="%d" w:hanging="%d"/></w:pPr>%s<w:r><w:tab/></w:r>%s</w:p>'
            % (INDENT + NUM_GAP, INDENT + NUM_GAP, NUM_GAP, run(GANADA[order] + '.'), run(text)))


def box(rows, indent=0):
    """출처(굵게) + 원문 문단으로 된 한 칸짜리 표.

    출처 하나가 한 칸으로 보이게 안쪽 가로줄을 지우되, 실제 행은 원문 문단마다 나눈다(첫 행은 출처 + 첫 문단).
    행을 통째로 묶으면 긴 칸이 다음 면으로 넘어가면서 앞 면 아래가 크게 비고, 행이 갈라지게 두면
    출처만 면 끝에 남을 수 있어서, 문단 사이에서만 면이 바뀌게 한 것이다.
    """
    width = TEXT_W - indent
    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="ae"/><w:tblW w:w="%d" w:type="dxa"/>%s'
           '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" '
           'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
           '<w:tblGrid><w:gridCol w:w="%d"/></w:tblGrid>'
           % (width, '<w:tblInd w:w="%d" w:type="dxa"/>' % indent if indent else '', width)]
    for row in rows:
        # "왼쪽": true 인 행은 왼쪽 정렬로 둔다(가운뎃점으로 이어진 긴 낱말 앞 줄이 양쪽 정렬로 크게 벌어질 때)
        left = 'left' if row.get('왼쪽') else None
        label = body_par(row['출처'], bold=True, after=30, keep_lines=False, align=left)
        quotes = [body_par(t, after=30, keep_lines=False, align=left) for t in row['원문']]
        groups = [label + ''.join(quotes[:1])] + quotes[1:]
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % SHADE if row.get('음영') else ''
        for k, cell in enumerate(groups):
            first, last = k == 0, k == len(groups) - 1
            edge = ('' if first else '<w:top w:val="nil"/>') + ('' if last else '<w:bottom w:val="nil"/>')
            out.append('<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr>'
                       '<w:tcW w:w="%d" w:type="dxa"/>%s%s'
                       '<w:tcMar><w:top w:w="%d" w:type="dxa"/><w:bottom w:w="%d" w:type="dxa"/></w:tcMar>'
                       '</w:tcPr>%s</w:tc></w:tr>'
                       % (width, '<w:tcBorders>%s</w:tcBorders>' % edge if edge else '', shade,
                          60 if first else 0, 50 if last else 0, cell))
    out.append('</w:tbl>')
    return ''.join(out)


def grid(spec, indent=0):
    """여러 칸짜리 표. 머리 칸은 음영·굵게·가운데, 면이 바뀌면 머리 행을 되풀이한다."""
    cols = spec['열']
    total = sum(cols)
    if total != TEXT_W - indent:
        raise SystemExit('표의 열 너비 합이 %d 이어야 합니다(지금 %d): %r'
                         % (TEXT_W - indent, total, spec.get('머리')))
    size = spec.get('크기', 18)
    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="ae"/><w:tblW w:w="%d" w:type="dxa"/>%s'
           '<w:tblLayout w:type="fixed"/>'
           '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" '
           'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr><w:tblGrid>%s</w:tblGrid>'
           % (total, '<w:tblInd w:w="%d" w:type="dxa"/>' % indent if indent else '',
              ''.join('<w:gridCol w:w="%d"/>' % w for w in cols))]

    def cell(text, w, head=False, bold=False, center=False):
        pars = [body_par(t, bold=head or bold, after=20, size=size, line=240,
                         align='center' if head or center else 'left', keep_lines=False)
                for t in str(text).split('\n')]
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % HEAD if head else ''
        return ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s'
                '<w:tcMar><w:top w:w="50" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
                '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar>'
                '<w:vAlign w:val="center"/></w:tcPr>%s</w:tc>'
                % (w, shade, ''.join(pars)))

    out.append('<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>%s</w:tr>'
               % ''.join(cell(t, w, head=True) for t, w in zip(spec['머리'], cols)))
    bold_first = spec.get('첫열굵게', True)
    center_cols = set(spec.get('가운데', []))
    for row in spec['행']:
        if isinstance(row, dict):
            # 묶음 제목: 가로로 합친 음영 행. 다음 행과 떨어지지 않게 묶는다
            out.append('<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>'
                       '<w:gridSpan w:val="%d"/><w:shd w:val="clear" w:color="auto" w:fill="%s"/>'
                       '<w:tcMar><w:top w:w="50" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
                       '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar>'
                       '<w:vAlign w:val="center"/></w:tcPr>%s</w:tc></w:tr>'
                       % (total, len(cols), SHADE,
                          body_par(row['묶음'], bold=True, after=20, size=size, line=240, align='left',
                                   keep_lines=False, keep_next=True)))
            continue
        if len(row) != len(cols):
            raise SystemExit('표의 칸 수가 맞지 않습니다: %r' % row)
        out.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>%s</w:tr>'
                   % ''.join(cell(t, w, bold=bold_first and i == 0, center=i in center_cols)
                             for i, (t, w) in enumerate(zip(row, cols))))
    out.append('</w:tbl>')
    return ''.join(out)


def para(inner, before=0, after=40, left=0, hanging=0, tabs=(), keep_next=False, align='left', line=LINE):
    """표 칸 안에 넣는 본-문 문단. inner 는 run 들을 이은 XML 이다."""
    ppr = ['<w:pStyle w:val="-"/>']
    if keep_next:
        ppr.append('<w:keepNext/>')
    ppr.append('<w:widowControl/>')
    if tabs:
        ppr.append('<w:tabs>%s</w:tabs>' % ''.join('<w:tab w:val="left" w:pos="%d"/>' % t for t in tabs))
    ppr.append(spacing(before, after, line))
    if left or hanging:
        ppr.append('<w:ind w:left="%d"%s/>' % (left, ' w:hanging="%d"' % hanging if hanging else ''))
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    return '<w:p><w:pPr>%s</w:pPr>%s</w:p>' % (''.join(ppr), inner)


def card(spec, indent=0):
    """항 하나를 표 한 장으로 보여 준다.

    위 두 칸은 조서 진술(왼쪽, 음영)과 그에 맞세울 자료(오른쪽)를 나란히 두고, 그 아래에
    수정 방향·유의·확인을 가로로 합친 칸으로 둔다. 진술과 자료를 위아래로 쌓은 박스는 어긋나는 대목을
    찾으려면 여러 칸을 오르내려야 해서 보기 어렵다는 지적이 있었다(2026. 10. 1.).
    좁은 칸은 양쪽 정렬을 하면 낱말 사이가 벌어지므로 왼쪽 정렬로 둔다.
    """
    width = TEXT_W - indent
    # "대조"는 [{"조서": [..], "자료": [..]}] 이고 한 쌍이 한 행이다(진술 하나에 맞세울 자료 하나).
    # "대조" 없이 "조서"·"자료"만 주면 한 행으로 본다.
    pairs = spec.get('대조') or [{'조서': spec['조서'], '자료': spec['자료']}]

    def plain(t):
        return re.sub(r'\*\*|\[\[|\]\]', '', t)

    def weight(side):
        n = 0
        for p in pairs:
            for e in p[side]:
                if isinstance(e, str):
                    n += len(plain(e))
                else:
                    n += sum(len(plain(v)) for v in (e.get('면', ''), e.get('문', ''), e.get('답', ''),
                                                      e.get('출처', '')))
                    n += sum(len(plain(q)) for q in e.get('원문', []))
        return n

    # 두 칸의 글 양에 맞추어 너비를 나눈다(한쪽만 길어 칸이 비는 것을 줄인다)
    share = weight('조서') / max(1, weight('조서') + weight('자료'))
    lw = spec.get('왼쪽') or max(3800, min(4600, int(round(width * share / 50.0)) * 50))
    rw = width - lw
    mar = ('<w:tcMar><w:top w:w="70" w:type="dxa"/><w:left w:w="110" w:type="dxa"/>'
           '<w:bottom w:w="50" w:type="dxa"/><w:right w:w="110" w:type="dxa"/></w:tcMar>')

    def tc(w, inner, fill=None, span=1):
        return ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s%s%s</w:tcPr>%s</w:tc>'
                % (w, '<w:gridSpan w:val="%d"/>' % span if span > 1 else '',
                   '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill if fill else '', mar, inner))

    def side(items):
        """조서 항목({"면","문","답"}), 자료 항목({"출처","원문"}), 글줄을 문단으로 바꾼다."""
        out = []
        for k, e in enumerate(items):
            last = k == len(items) - 1
            if isinstance(e, str):
                out.append(para(rich(e), after=0 if last else 50))
            elif '출처' in e:
                quotes = e.get('원문', [])
                out.append(para(run(plain(e['출처']), True), after=20 if quotes else (0 if last else 50)))
                for j, q in enumerate(quotes):
                    out.append(para(rich(q), after=0 if last and j == len(quotes) - 1 else 40))
            else:
                inner = run(e['면'] + ' ', True) if e.get('면') else ''
                if e.get('문'):
                    inner += run('(' + e['문'] + ') ', color=GRAY)
                out.append(para(inner + rich(e['답']), after=0 if last else 60))
        return ''.join(out)

    def lines(items, w):
        """칸에 들어갈 글줄 수 어림(맑은 고딕 10pt 한 글자 약 9.5pt, 칸 여백 11pt)."""
        per = max(8, int((w / 20.0 - 11) / 9.5))
        n = 0
        for e in items:
            if isinstance(e, str):
                texts = [e]
            elif '출처' in e:
                texts = [e['출처']] + e.get('원문', [])
            else:
                texts = [' '.join(v for v in (e.get('면', ''), e.get('문', ''), e['답']) if v)]
            n += sum(-(-len(plain(t)) // per) for t in texts)
        return n

    names = spec.get('머리', ['조서에서 한 말', '대조 자료'])
    rows = ['<w:tr><w:trPr><w:cantSplit/></w:trPr>%s%s</w:tr>' % (
        tc(lw, para(run(names[0], True), after=0, align='center', keep_next=True), HEAD),
        tc(rw, para(run(names[1], True), after=0, align='center', keep_next=True), HEAD))]
    for p in pairs:
        # 낮은 행은 면 사이에서 갈라지지 않게 하고, 높은 행은 갈라지게 둔다(통째로 넘어가면 앞 면이 크게 빈다)
        short = max(lines(p['조서'], lw), lines(p['자료'], rw)) <= spec.get('묶는줄', 10)
        rows.append('<w:tr>%s%s%s</w:tr>'
                    % ('<w:trPr><w:cantSplit/></w:trPr>' if short else '',
                       tc(lw, side(p['조서']), SHADE), tc(rw, side(p['자료']))))

    gap = 300                                   # ①·· 표시 너비
    for label in ('수정 방향', '유의', '확인'):
        items = spec.get(label)
        if not items:
            continue
        if isinstance(items, str):
            items = [items]
        if len(items) > 1:
            marks = CIRCLED if label == '수정 방향' else '-' * len(items)
        else:
            marks = None
        pars = []
        for k, text in enumerate(items):
            last = k == len(items) - 1
            after = 30 if not last else 0
            if marks:
                if k == 0:
                    pars.append(para(run(label, True) + TAB + run(marks[k]) + TAB + rich(text), after=after,
                                     tabs=(LABEL, LABEL + gap), left=LABEL + gap, hanging=LABEL + gap))
                else:
                    pars.append(para(run(marks[k]) + TAB + rich(text), after=after,
                                     tabs=(LABEL + gap,), left=LABEL + gap, hanging=gap))
            elif k == 0:
                pars.append(para(run(label, True) + TAB + rich(text), after=after,
                                 tabs=(LABEL,), left=LABEL, hanging=LABEL))
            else:
                pars.append(para(rich(text), after=after, left=LABEL))
        rows.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>%s</w:tr>' % tc(width, ''.join(pars), span=2))

    return ('<w:tbl><w:tblPr><w:tblStyle w:val="ae"/><w:tblW w:w="%d" w:type="dxa"/>%s'
            '<w:tblLayout w:type="fixed"/>'
            '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" '
            'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
            '<w:tblGrid><w:gridCol w:w="%d"/><w:gridCol w:w="%d"/></w:tblGrid>%s</w:tbl>'
            % (width, '<w:tblInd w:w="%d" w:type="dxa"/>' % indent if indent else '', lw, rw, ''.join(rows)))


def contrast(spec, indent=0):
    """상충점 하나를 표 한 장으로 보여 준다(왼쪽 칸은 누구의 말인지, 오른쪽 칸은 그 내용).

    위에서부터 기준이 되는 자료(의견서·동봉 증거, "기준": true), 진술인별 진술, '상충점', '수정 방향' 순이다.
    진술과 자료를 좌우로 나눈 카드는 좁은 칸에서 줄이 잘게 끊겨 읽기 어렵다는 지적이 있어(2026. 10. 1.),
    글은 한 칸에 넓게 쓰고 사람을 행으로 나눈다. 표 하나가 면 사이에서 갈라지지 않게 묶는다.
    """
    width = TEXT_W - indent
    lw = spec.get('왼쪽', 1300)
    rw = width - lw
    mar = ('<w:tcMar><w:top w:w="50" w:type="dxa"/><w:left w:w="110" w:type="dxa"/>'
           '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="110" w:type="dxa"/></w:tcMar>')

    def tc(w, inner, fill=None):
        return ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s%s</w:tcPr>%s</w:tc>'
                % (w, '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill if fill else '', mar, inner))

    def listed(v):
        return [v] if isinstance(v, str) else list(v or [])

    tail = [k for k in ('상충점', '수정 방향') if spec.get(k)]
    total = len(spec['행']) + len(tail)
    size = spec.get('크기', 19)                 # 표 안 글자 크기(반 pt 단위). 본문 10pt 보다 반 pt 작게 둔다
    line = spec.get('줄', 245)
    rows = []
    for n, r in enumerate(spec['행']):
        keep = n < total - 1                    # 마지막 행만 빼고 다음 행과 묶는다
        names = r['누구'].split('\n')
        label = ''.join(para(run(t, True, size), after=0, keep_next=keep, line=line) for t in names)
        quotes = listed(r.get('원문'))
        if r.get('요지') and quotes and not spec.get('요지줄'):
            # 요지(굵게) 뒤에 첫 원문을 같은 문단으로 잇는다. 줄 수가 줄어 표 두세 개가 한 면에 들어간다
            inners = ([rich(r['요지'], bold=True, size=size) + run('  ', size=size) + rich(quotes[0], size=size)]
                      + [rich(q, size=size) for q in quotes[1:]])
        else:
            inners = (([rich(r['요지'], bold=True, size=size)] if r.get('요지') else [])
                      + [rich(q, size=size) for q in quotes])
        body = ''.join(para(x, after=0 if k == len(inners) - 1 else 10, keep_next=keep, line=line)
                       for k, x in enumerate(inners))
        base = r.get('기준')
        rows.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>%s%s</w:tr>'
                    % (tc(lw, label, HEAD if base else SHADE), tc(rw, body, SHADE if base else None)))
    gap = 290
    for n, key in enumerate(tail):
        keep = len(spec['행']) + n < total - 1
        items = listed(spec[key])
        if len(items) == 1:
            body = para(rich(items[0], size=size), after=0, keep_next=keep, line=line)
        else:
            body = ''.join(para(run(CIRCLED[k], size=size) + TAB + rich(t, size=size),
                                after=0 if k == len(items) - 1 else 10,
                                tabs=(gap,), left=gap, hanging=gap, keep_next=keep, line=line)
                           for k, t in enumerate(items))
        rows.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>%s%s</w:tr>'
                    % (tc(lw, para(run(key, True, size), after=0, keep_next=keep, line=line), HEAD), tc(rw, body)))
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="ae"/><w:tblW w:w="%d" w:type="dxa"/>%s'
            '<w:tblLayout w:type="fixed"/>'
            '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" '
            'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
            '<w:tblGrid><w:gridCol w:w="%d"/><w:gridCol w:w="%d"/></w:tblGrid>%s</w:tbl>'
            % (width, '<w:tblInd w:w="%d" w:type="dxa"/>' % indent if indent else '', lw, rw, ''.join(rows)))


def title_par(text):
    return ('<w:p><w:pPr><w:pStyle w:val="aff"/></w:pPr>'
            '<w:r><w:rPr>%s</w:rPr><w:t>제 목</w:t></w:r><w:r><w:t>:</w:t></w:r><w:r><w:tab/></w:r>%s</w:p>'
            % (HINT, run(text)))


def blocks(items, indent, split=False):
    """split 이면 본문 문단이 면 사이에서 갈라질 수 있게 한다(내용 파일의 "문단나눔").

    제목 → 소제목 → 문단 → 박스 첫 행이 한 덩어리로 묶이면 덩어리가 통째로 다음 면으로 넘어가
    앞 면 아래가 크게 빈다. 문단이 갈라질 수 있으면 제목과 문단 앞 줄이 앞 면에 남는다.
    """
    parts = []
    after_table = False
    for i, blk in enumerate(items):
        before = 120 if after_table else 0
        nxt = items[i + 1] if i + 1 < len(items) else {}
        if '표지' in blk:
            parts.append(label_par(blk['표지'], blk['문'], before=before, indent=indent,
                                   width=blk.get('너비', LABEL)))
            after_table = False
        elif '문' in blk:
            # 바로 뒤가 박스·표·카드·대비·표지 문단이면 면이 바뀌어도 떨어지지 않게 묶는다
            tied = any(k in nxt for k in ('박스', '표', '표지', '카드', '대비'))
            parts.append(body_par(blk['문'], before=before, indent=indent, keep_next=tied, after=80,
                                  keep_lines=not split))
            after_table = False
        elif '박스' in blk:
            parts.append(box(blk['박스'], indent=indent))
            after_table = True
        elif '카드' in blk:
            parts.append(card(blk['카드'], indent=indent))
            after_table = True
        elif '대비' in blk:
            parts.append(contrast(blk['대비'], indent=indent))
            after_table = True
        elif '표' in blk:
            parts.append(grid(blk['표'], indent=indent))
            after_table = True
        else:
            raise SystemExit('알 수 없는 블록: %r' % blk)
    return parts, after_table


def build_document(template_xml, data):
    global LEFT_ALIGN
    LEFT_ALIGN = bool(data.get('왼쪽정렬'))
    head = template_xml[:template_xml.index('<w:body>') + len('<w:body>')]
    rule = re.search(r'<w:p [^>]*>(?:(?!</w:p>).)*?<w:pStyle w:val="aff0"/>.*?</w:p>', template_xml, re.S)
    sect = re.search(r'<w:sectPr.*?</w:sectPr>', template_xml, re.S)
    if not rule or not sect:
        raise SystemExit('양식에서 제목 밑줄 문단 또는 구역 설정을 찾지 못했습니다: %s' % TEMPLATE)
    parts = [head, title_par(data['제목']), rule.group(0)]
    for i, text in enumerate(data.get('머리', [])):
        if isinstance(text, dict):              # 범례 줄: 굵은 표지 + 설명
            parts.append(label_par(text['표지'], text['문'], after=text.get('뒤', 30),
                                   width=text.get('너비', 760)))
        else:
            parts.append(body_par(text, before=120 if i == 0 else 0, after=70))
    ended_with_table = False
    split = data.get('문단나눔', False)
    for sec in data['절']:
        parts.append(heading(sec['제목'], new_page=sec.get('새면', False)))
        if '블록' in sec:
            got, ended_with_table = blocks(sec['블록'], 0, split)
            parts += got
        for order, item in enumerate(sec.get('항', [])):
            parts.append(sub_heading(item['제목'], order))
            got, ended_with_table = blocks(item['블록'], INDENT, split)
            parts += got
    for i, text in enumerate(data.get('꼬리', [])):      # 맨 끝의 작은 참고 줄(면수 표기 기준 등)
        parts.append(body_par(text, before=200 if i == 0 else 0, after=30, size=18, keep_lines=False))
        ended_with_table = False
    if ended_with_table:
        parts.append(body_par(''))      # 표로 끝나면 Word 가 요구하는 마지막 문단
    parts.append(sect.group(0))
    parts.append('</w:body></w:document>')
    return ''.join(parts)


def md_blocks(items):
    out = []
    for blk in items:
        if '표지' in blk:
            out.append('**%s** %s' % (blk['표지'], blk['문']) if blk['표지'] else blk['문'])
        elif '문' in blk:
            out.append(blk['문'])
        elif '박스' in blk:
            lines = []
            for row in blk['박스']:
                lines.append('- **%s**%s' % (row['출처'], ' (조서 진술)' if row.get('음영') else ''))
                lines += ['  - %s' % t for t in row['원문']]
            out.append('\n'.join(lines))
        elif '표' in blk:
            spec = blk['표']
            cell = lambda c: str(c).replace('|', '\\|').replace('\n', '<br>')
            rows = ['| ' + ' | '.join(cell(c) for c in spec['머리']) + ' |', '|' + '---|' * len(spec['머리'])]
            for r in spec['행']:
                if isinstance(r, dict):
                    r = ['**%s**' % r['묶음']] + [''] * (len(spec['머리']) - 1)
                rows.append('| ' + ' | '.join(cell(c) for c in r) + ' |')
            out.append('\n'.join(rows))
        elif '카드' in blk:
            spec = blk['카드']
            lines = []

            def md_side(items, pad):
                for e in items:
                    if isinstance(e, str):
                        lines.append('%s- %s' % (pad, e))
                    elif '출처' in e:
                        lines.append('%s- **%s**' % (pad, e['출처']))
                        lines.extend('%s  - %s' % (pad, q) for q in e.get('원문', []))
                    else:
                        lines.append('%s- %s%s%s' % (pad, e['면'] + ' ' if e.get('면') else '',
                                                     '(%s) ' % e['문'] if e.get('문') else '', e['답']))

            for p in spec.get('대조') or [{'조서': spec['조서'], '자료': spec['자료']}]:
                lines.append('- **조서 진술**')
                md_side(p['조서'], '  ')
                lines.append('  - **대조 자료**')
                md_side(p['자료'], '    ')
            for label in ('수정 방향', '유의', '확인'):
                items = spec.get(label)
                if items:
                    items = [items] if isinstance(items, str) else items
                    lines.append('- **%s**' % label)
                    lines += ['  - %s' % t for t in items]
            out.append('\n'.join(lines))
        elif '대비' in blk:
            spec = blk['대비']
            as_list = lambda v: [v] if isinstance(v, str) else list(v or [])
            lines = []
            for r in spec['행']:
                lines.append('- **%s**%s' % (r['누구'].replace('\n', '·'), ' ' + r['요지'] if r.get('요지') else ''))
                lines += ['  - %s' % q for q in as_list(r.get('원문'))]
            for label in ('상충점', '수정 방향'):
                if spec.get(label):
                    lines.append('- **%s**' % label)
                    lines += ['  - %s' % t for t in as_list(spec[label])]
            out.append('\n'.join(lines))
    return out


def build_markdown(data, data_name):
    """docx 와 같은 내용의 글 사본. 검색하거나 다른 PC 에서 이어 볼 때 쓴다."""
    parts = ['# ' + data['제목'],
             '`빌드/%s` 에서 만든 글 사본이다. 고칠 때는 json 을 고치고 다시 빌드한다. '
             '같은 폴더의 docx 를 사람이 고친 뒤에는 docx 가 기준이다.' % data_name]
    parts += ['**%s** %s' % (t['표지'], t['문']) if isinstance(t, dict) else t for t in data.get('머리', [])]
    for n, sec in enumerate(data['절'], 1):
        parts.append('## %d. %s' % (n, sec['제목']))
        parts += md_blocks(sec.get('블록', []))
        for order, item in enumerate(sec.get('항', [])):
            parts.append('### %s. %s' % (GANADA[order], item['제목']))
            parts += md_blocks(item['블록'])
    return '\n\n'.join(parts) + '\n'


def core_props(xml):
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    xml = re.sub(r'(<cp:lastModifiedBy>).*?(</cp:lastModifiedBy>)', r'\g<1>Claude\g<2>', xml)
    xml = re.sub(r'(<cp:revision>).*?(</cp:revision>)', r'\g<1>1\g<2>', xml)
    xml = re.sub(r'<cp:lastPrinted>.*?</cp:lastPrinted>', '', xml)
    xml = re.sub(r'(<dcterms:created[^>]*>).*?(</dcterms:created>)', r'\g<1>%s\g<2>' % now, xml)
    xml = re.sub(r'(<dcterms:modified[^>]*>).*?(</dcterms:modified>)', r'\g<1>%s\g<2>' % now, xml)
    return xml


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def targets(argv):
    """내용 파일과 그에 딸린 출력 docx, 글 사본, 빌드기록 경로."""
    argv = list(argv)
    out_dir = None
    if '--out' in argv:                           # 시험 빌드: 사건 폴더가 아닌 곳에 쓴다
        k = argv.index('--out')
        out_dir = Path(argv[k + 1])
        del argv[k:k + 2]
    names = [a for a in argv if not a.startswith('--')]
    if not names:
        raise SystemExit('내용 파일(json)을 적어야 합니다. 예: python -B 공통/scripts/research_docx.py "<사건>/작업/빌드/리서치_내용.json"')
    data_path = Path(names[0]).resolve()
    if not data_path.exists():
        raise SystemExit('내용 파일이 없습니다: %s' % names[0])
    data = json.loads(data_path.read_text(encoding='utf-8'))
    if not data.get('출력'):
        raise SystemExit('내용 파일에 "출력"(docx 이름)이 없습니다: %s' % data_path.name)
    here = data_path.parent
    work = here.parent if here.name == '빌드' else here
    out = (out_dir or work) / data['출력']
    md = work / data['글사본'] if data.get('글사본') and not out_dir else None
    record = None if out_dir else here / (data_path.stem.replace('_내용', '') + '_빌드기록.json')
    return data_path, data, out, md, record


def shown(path):
    """보고에 적을 경로. 저장소 안이면 루트 기준 상대경로로 적는다."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def edited_by_hand(out, record):
    """마지막 빌드 뒤에 docx 가 바뀌었으면 True. 기록이 없으면(처음) False."""
    if record is None or not out.exists() or not record.exists():
        return False
    rec = json.loads(record.read_text(encoding='utf-8'))
    return rec.get('sha256') != sha256(out)


def main(argv):
    data_path, data, OUT, MD, RECORD = targets(argv)
    if '--check' in argv:
        if not OUT.exists():
            print('문서가 아직 없습니다: %s' % OUT.name)
        elif edited_by_hand(OUT, RECORD):
            print('마지막 빌드 뒤에 docx 가 바뀌었습니다. 다시 빌드하면 그 수정이 사라집니다.')
            return 1
        else:
            print('docx 는 마지막 빌드 그대로입니다.')
        return 0
    if '--md' in argv:
        if not MD:
            print('이 내용 파일에는 "글사본"이 없습니다: %s' % data_path.name)
            return 1
        MD.write_text(build_markdown(data, data_path.name), encoding='utf-8', newline='\n')
        print('글 사본만 다시 씀: %s' % shown(MD))
        return 0
    if edited_by_hand(OUT, RECORD) and '--force' not in argv:
        print('중단: 마지막 빌드 뒤에 docx 가 바뀌었습니다(사람이 고친 것으로 보임).')
        print('그 파일을 직접 고치거나, 덮어쓰려면 --force 를 붙이십시오.')
        return 1

    if not TEMPLATE.exists():
        print('중단: 양식이 없습니다(OneDrive 동기화 확인): %s' % shown(TEMPLATE))
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(TEMPLATE) as zin:
        names = zin.infolist()
        document = build_document(zin.read('word/document.xml').decode('utf-8'), data)
        tmp = OUT.with_suffix('.tmp')
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info in names:
                raw = zin.read(info.filename)
                if info.filename == 'word/document.xml':
                    raw = document.encode('utf-8')
                elif info.filename == 'docProps/core.xml':
                    raw = core_props(raw.decode('utf-8')).encode('utf-8')
                elif info.filename.startswith('word/header'):
                    # 양식 머리글의 옛 전화번호를 지금 번호로 바꾼다
                    raw = raw.replace(b'6010-6565', b'6747-6565').replace(b'6010-6566', b'6747-6566')
                zout.writestr(info.filename, raw)
    try:
        tmp.replace(OUT)
    except PermissionError:
        tmp.unlink()
        print('중단: %s 가 열려 있어 쓸 수 없습니다. Word 에서 닫은 뒤 다시 실행하십시오.' % OUT.name)
        return 1
    if MD:
        MD.write_text(build_markdown(data, data_path.name), encoding='utf-8', newline='\n')
    if RECORD is None:
        print('시험 빌드: %s' % OUT)
        return 0
    RECORD.write_text(json.dumps({'sha256': sha256(OUT),
                                  '빌드시각': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                                  '출력': shown(OUT)},
                                 ensure_ascii=False, indent=2), encoding='utf-8')
    print('만듦: %s' % shown(OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
