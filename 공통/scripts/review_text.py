#!/usr/bin/env python3
"""자체 검토에 넘길 검토 대상 글을 DOCX 에서 뽑는다(공통/자체검토.md 3절).

본문과 각주를 뽑되 각주가 붙은 자리를 본문에 {{n}} 으로 남긴다. n 은 본문에 나오는 순서이고 Word 가 매기는
각주 번호와 같다. system.py extract 는 본문과 각주를 따로 이어 붙여 어느 문장의 각주인지 보이지 않는다.

    python -B 공통/scripts/review_text.py "1_검토의견/사건/…/(…) … 관련 검토.docx" --out "1_검토의견/사건/…/작업/자체검토/검토대상.md"

면수·서식·그림은 나오지 않는다. 렌더 확인은 따로 한다. Word 메모(word/comments.xml)의 글도 뽑지 않고, 메모가 있으면 건수만 경고한다.
메모가 있으면 --memos 로 메모의 글과 그 메모가 붙은 본문 구절(w:commentRangeStart 와 w:commentRangeEnd 사이의 글), 메모가 달린 문단을
다른 파일에 따로 뽑는다. 메모의 글만으로는 '이 문장은 빼 주세요'가 어느 문장인지 알 수 없다. 답글도 메모 한 건으로 적고, 해결 표시는 가리지 않는다.

    python -B 공통/scripts/review_text.py "…/검토의견서.docx" --out "…/작업/자체검토/검토대상.md" --memos "…/작업/자체검토/Word메모.md"
"""
import argparse
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MC_FALLBACK = '{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback'
# 글자로 읽지 않는 것: mc:Choice 와 같은 내용의 옛 형식 사본, 문단·글자 속성(탭 자리 정의가 w:tab 으로 들어 있다),
# 변경 추적에서 옮기기 전 자리의 글(w:moveFrom. 옮긴 자리 w:moveTo 에 같은 글이 있다)과 지운 글(w:del. 지운 각주 참조와
# 탭·줄바꿈도 그 안에 있다). 변경 추적이 있는 문서는 모두 수락한 모습으로 뽑는다
SKIP = {MC_FALLBACK, W + 'pPr', W + 'rPr', W + 'moveFrom', W + 'del'}
TRACKED = ('ins', 'del', 'moveFrom', 'moveTo')


def paragraphs(root, mark):
    """문단마다 글자를 모은다(표 칸 포함). 글상자 안의 문단은 바깥 문단 뒤에 따로 낸다. mark(종류, id) 는 각주 자리의 표시를 돌려준다."""
    out = []

    def visit(p):
        own, nested = [], []

        def collect(node):
            for child in node:
                if child.tag in SKIP:
                    continue
                if child.tag == W + 'p':
                    nested.append(child)
                elif child.tag == W + 't':
                    own.append(child.text or '')
                elif child.tag == W + 'tab':
                    own.append('\t')
                elif child.tag in (W + 'br', W + 'cr'):
                    own.append('\n')
                elif child.tag == W + 'footnoteReference':
                    own.append(mark('각주', child.get(W + 'id')))
                elif child.tag == W + 'endnoteReference':
                    own.append(mark('미주', child.get(W + 'id')))
                else:
                    collect(child)

        collect(p)
        out.append(''.join(own))
        for q in nested:
            visit(q)

    def walk(node):
        for child in node:
            if child.tag in SKIP:
                continue
            if child.tag == W + 'p':
                visit(child)
            else:
                walk(child)

    walk(root)
    return out


def notes(z, part, tag):
    """각주(미주) id -> 글. 구분선 같은 특수 각주(w:type)는 뺀다."""
    if part not in z.namelist():
        return {}
    found = {}
    for n in ET.fromstring(z.read(part)).iter(W + tag):
        if n.get(W + 'type'):
            continue
        found[n.get(W + 'id')] = ' '.join(t.strip() for t in paragraphs(n, lambda kind, i: '') if t.strip())
    return found


def comments(z):
    """Word 메모 요소의 목록. 메모 파일이 없으면 빈 목록, 있는데 읽지 못하면 None."""
    if 'word/comments.xml' not in z.namelist():
        return []
    try:
        return list(ET.fromstring(z.read('word/comments.xml')).iter(W + 'comment'))
    # 비었거나 깨진 메모 파일, 파이썬이 읽지 못하는 인코딩 선언(모르는 이름은 LookupError, euc-kr 같은 다바이트 인코딩은 ValueError)
    # 때문에 본문까지 뽑지 못하는 일이 없게 한다
    except (ET.ParseError, LookupError, ValueError):
        return None


def memo_anchors(root):
    """메모 id -> (붙은 구절, 메모가 달린 문단). 붙은 구절은 w:commentRangeStart 와 w:commentRangeEnd 사이의 글이고 문단이 바뀌는
    자리는 줄바꿈으로 남긴다. 지운 글은 본문과 같이 뺀다. 범위 없이 메모 표시(w:commentReference)만 있으면 붙은 구절은 None 이고,
    범위는 있는데 그 안에 글로 뽑힌 것이 없으면(지운 글·그림·공백·각주 번호뿐인 범위, 빈 범위 등) 빈 글이다."""
    spans, where, opened = {}, {}, []

    def add(text):
        for i in opened:
            spans[i].append(text)

    def walk(node, para):
        for child in node:
            if child.tag in SKIP:
                continue
            if child.tag in (W + 'commentRangeStart', W + 'commentReference'):
                i = child.get(W + 'id')
                if para is not None:
                    where.setdefault(i, para)
                if child.tag == W + 'commentRangeStart' and i not in spans:
                    spans[i] = []
                    opened.append(i)
            elif child.tag == W + 'commentRangeEnd':
                if child.get(W + 'id') in opened:
                    opened.remove(child.get(W + 'id'))
            elif child.tag == W + 't':
                add(child.text or '')
            elif child.tag == W + 'tab':
                add('\t')
            elif child.tag in (W + 'br', W + 'cr'):
                add('\n')
            elif child.tag == W + 'p':
                for i in opened:      # 범위가 문단 사이에서 시작한 메모는 범위에 든 첫 문단을 달린 문단으로 적는다
                    where.setdefault(i, child)
                walk(child, child)
                add('\n')
            else:
                walk(child, para)

    walk(root, None)
    return {i: (''.join(spans[i]).strip() if i in spans else None, paragraphs([where[i]], lambda kind, n: '')[0].strip() if i in where else '')
            for i in set(spans) | set(where)}


def memo_notes(path):
    """Word 메모마다 작성자·날짜·글과 붙은 구절·범위가 있는지·달린 문단·자리(본문·각주·미주)를 메모 파일에 적힌 순서로 돌려준다.
    메모가 없으면 빈 목록, 메모 파일을 읽지 못하면 None."""
    with zipfile.ZipFile(path) as z:
        found = comments(z)
        if not found:
            return found
        anchors = {}
        for part, label in (('word/document.xml', '본문'), ('word/footnotes.xml', '각주'), ('word/endnotes.xml', '미주')):
            if part in z.namelist():
                for i, (span, para) in memo_anchors(ET.fromstring(z.read(part))).items():
                    anchors.setdefault(i, (span, para, label))
    out = []
    for c in found:
        span, para, label = anchors.get(c.get(W + 'id'), (None, '', ''))
        out.append({'작성자': c.get(W + 'author') or '', '날짜': c.get(W + 'date') or '',
                    '글': '\n'.join(t for t in paragraphs(c, lambda kind, i: '') if t.strip()),
                    '붙은 구절': span or '', '범위': span is not None, '문단': para, '자리': label})
    return out


def memo_text(name, found):
    """memo_notes 의 결과를 자체 검토 폴더에 둘 글로 적는다. 메모의 글과 붙은 구절은 받은 글 그대로 옮긴다."""
    def quote(text, empty):
        return ['> ' + line for line in text.split('\n')] if text.strip() else ['> (' + empty + ')']

    out = ['# Word 메모: ' + name, '',
           f'메모 {len(found)}건(답글도 한 건으로 센다). 붙은 구절은 그 메모의 범위에 든 글이고, 달린 문단은 메모가 달린 자리의 문단이다. '
           '변경 추적으로 지운 글은 빠져 있고, 해결 표시는 가리지 않았다.']
    for n, m in enumerate(found, 1):
        who = ', '.join(x for x in (m['작성자'], m['날짜']) if x)
        out += ['', f'## 메모 {n}' + (' — ' + who if who else ''), '']
        if not m['자리']:
            out += ['붙은 구절:', '> (본문·각주·미주에서 이 메모의 자리를 찾지 못하였다. Word 에서 따로 확인한다)']
        else:
            empty = ('범위는 있으나 그 안에 글로 뽑힌 것이 없다. 변경 추적으로 지운 글, 그림·공백, 각주·미주 번호만 든 범위이거나 빈 범위일 수 있다. '
                     '무엇에 단 메모인지는 Word 에서 따로 확인한다') if m['범위'] else '범위 없이 메모 표시만 있다'
            out += [f"붙은 구절({m['자리']}):"] + quote(m['붙은 구절'], empty)
            out += ['', '메모가 달린 문단:'] + quote(m['문단'], '문단을 찾지 못하였다')
        out += ['', '메모의 글:'] + quote(m['글'], '글 없음')
    return '\n'.join(out) + '\n'


def review_text(path):
    """(글, 요약) 을 돌려준다. 요약: 문단 수, 각주 수, 경고."""
    order = {'각주': [], '미주': []}
    twice = {'각주': [], '미주': []}

    def mark(kind, i):
        if i not in order[kind]:
            order[kind].append(i)
        elif i not in twice[kind]:
            twice[kind].append(i)
        n = order[kind].index(i) + 1
        return '{{%d}}' % n if kind == '각주' else '{{미주 %d}}' % n

    warnings = []
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read('word/document.xml'))
        for part in ('word/document.xml', 'word/footnotes.xml', 'word/endnotes.xml'):
            if part in z.namelist() and any(ET.fromstring(z.read(part)).find('.//' + W + t) is not None for t in TRACKED):
                warnings.append('변경 추적이 있다(' + part + '). 삽입·옮겨 온 글은 들어 있고 삭제·옮기기 전 글은 빠져 있다')
        # 메모의 글은 본문이 아니어서 뽑지 않는다. 담당자가 메모로 남긴 말을 모르고 지나가지 않게 건수를 알린다
        memos = comments(z)
        if memos is None:
            warnings.append('word/comments.xml 을 읽지 못하였다. Word 메모가 있는지 Word 에서 따로 확인한다')
        elif memos:
            warnings.append(f'Word 메모 {len(memos)}건이 있다(word/comments.xml). 메모의 글은 이 글에 들어 있지 않다')
        lines = [t for t in paragraphs(body, mark) if t.strip()]
        if not lines:
            warnings.append('본문에 글자가 없다. 그림만 든 문서이거나 추출에 실패한 것이다')
        texts = {'각주': notes(z, 'word/footnotes.xml', 'footnote'), '미주': notes(z, 'word/endnotes.xml', 'endnote')}
    out = ['# 검토 대상: ' + Path(path).name, '',
           '본문의 {{n}} 은 각주 n 이 붙은 자리이다. 면수·서식·그림은 이 글에 나오지 않는다.', ''] + lines
    for kind in ('각주', '미주'):
        if not order[kind] and not texts[kind]:
            continue
        out += ['', '## ' + kind]
        for n, i in enumerate(order[kind], 1):
            label = '{{%d}}' % n if kind == '각주' else '{{미주 %d}}' % n
            if not texts[kind].get(i):
                warnings.append(f'{kind} {n} 의 글을 찾지 못하였다(글이 비어 있거나 각주 파일에 없다)')
            out.append(label + ' ' + (texts[kind].get(i) or '(글 없음)'))
        if twice[kind]:
            warnings.append(f'본문의 두 자리에서 참조한 {kind}: ' + ', '.join(str(order[kind].index(i) + 1) for i in twice[kind]))
        # 변경 추적으로 지운 각주는 참조가 빠지고 글도 비어 있다. 글이 남은 것만 참조하지 않는 각주로 알린다
        unused = [i for i in texts[kind] if i not in order[kind] and texts[kind][i]]
        if unused:
            warnings.append(f'본문에서 참조하지 않는 {kind} {len(unused)}개')
            out += ['', f'본문에서 참조하지 않는 {kind}:'] + ['- ' + texts[kind][i] for i in unused]
    return '\n'.join(out) + '\n', {'문단': len(lines), '각주': len(order['각주']), '미주': len(order['미주']), '경고': warnings}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('docx')
    parser.add_argument('--out', help='쓸 파일. 없으면 화면에 낸다')
    parser.add_argument('--memos', help='Word 메모의 글과 메모가 붙은 본문 구절을 따로 쓸 파일. 메모가 없으면 쓰지 않는다')
    a = parser.parse_args()
    if Path(a.docx).suffix.lower() != '.docx':
        parser.error('DOCX 만 받는다. MD 는 보완 메모 앞까지를 검토대상.md 로 옮긴다(공통/자체검토.md 3절)')
    if a.memos and a.out and Path(a.memos).resolve() == Path(a.out).resolve():
        parser.error('--memos 는 --out 과 다른 파일로 준다(같은 파일이면 검토 대상 글이 덮어써진다)')
    text, summary = review_text(a.docx)
    notice = sys.stdout if a.out else sys.stderr      # 글을 화면에 낼 때에는 알림이 글에 섞이지 않게 한다
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding='utf-8')
        print(summary, '->', a.out)
    else:
        sys.stdout.write(text)
        print(summary, file=sys.stderr)
    if a.memos:
        found = memo_notes(a.docx)
        if found:
            Path(a.memos).parent.mkdir(parents=True, exist_ok=True)
            Path(a.memos).write_text(memo_text(Path(a.docx).name, found), encoding='utf-8')
            print(f'Word 메모 {len(found)}건 ->', a.memos, file=notice)
        else:
            print('Word 메모를 쓰지 않았다(' + ('word/comments.xml 을 읽지 못하였다' if found is None else '메모가 없다') + ')', file=notice)
    elif any('Word 메모' in w and '건이 있다' in w for w in summary['경고']):
        print('메모의 글과 붙은 구절은 --memos "{쓸 파일}" 을 붙여 따로 뽑는다', file=notice)


if __name__ == '__main__':
    main()
