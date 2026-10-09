#!/usr/bin/env python3
"""자체 검토에 넘길 검토 대상 글을 DOCX 에서 뽑는다(공통/자체검토.md 3절).

본문과 각주를 뽑되 각주가 붙은 자리를 본문에 {{n}} 으로 남긴다. n 은 본문에 나오는 순서이고 Word 가 매기는
각주 번호와 같다. system.py extract 는 본문과 각주를 따로 이어 붙여 어느 문장의 각주인지 보이지 않는다.

    python -B 공통/scripts/review_text.py "1_검토의견/사건/…/(…) … 관련 검토.docx" --out "1_검토의견/사건/…/작업/자체검토/검토대상.md"

면수·서식·그림은 나오지 않는다. 렌더 확인은 따로 한다.
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
    a = parser.parse_args()
    if Path(a.docx).suffix.lower() != '.docx':
        parser.error('DOCX 만 받는다. MD 는 보완 메모 앞까지를 검토대상.md 로 옮긴다(공통/자체검토.md 3절)')
    text, summary = review_text(a.docx)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding='utf-8')
        print(summary, '->', a.out)
    else:
        sys.stdout.write(text)
        print(summary, file=sys.stderr)


if __name__ == '__main__':
    main()
