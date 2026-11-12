"""서면 docx 의 표에서 글이 든 칸이 쪽 오른쪽 여백 밖이나 종이 밖에 놓였는지 본다.

    python -B 4_서면작성/scripts/docx_tables.py <docx>          # 넘친 칸이 있으면 종료 코드 1

표마다 격자 칸 너비(w:tblGrid)와 표 들여쓰기·정렬로 칸의 왼쪽·오른쪽 자리를 셈하고, 그 표가 든 구역의 쪽 크기·여백과 맞댄다.
글이 든 칸이 오른쪽 여백 안쪽 끝을 넘어서 시작하거나 종이 오른쪽(왼쪽) 끝 밖까지 나가면 막는다. 빈 칸은 쪽 밖에 있어도 보이지 않으므로
세지 않는다. 표 안의 표는 바깥 칸에 맞춰 줄어 보이므로 보지 않는다.

2026. 11. 13. `/하자보완`: 서면 템플릿 프레임(`4_서면작성/사건/_템플릿`)의 2면 사건 표에 빈 셋째 칸(너비 8253, 표 너비 17949)이 있어,
값을 마지막 칸에 넣는 도구로 채운 11. 12. 이승민 준비서면(2)의 사건번호·당사자가 쪽 밖으로 밀려 잘렸다(담당자 "2면 상단 원고 피고
있는 표도 이상한데"). 병합 뒤 점검과 관문(`공통/scripts/final_check.py` 'DOCX')은 병합 시각만 보아 그 판을 지나보냈다.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
여유 = 20          # twip. 반올림으로 생기는 1mm 안쪽 어긋남은 넘침으로 보지 않는다


def q(tag: str) -> str:
    return f'{{{W}}}{tag}'


def _수(el, attr='w', 기본=None):
    if el is None:
        return 기본
    v = el.get(q(attr))
    try:
        return int(float(v)) if v is not None else 기본
    except ValueError:
        return 기본


def _글(el) -> str:
    return ''.join(t.text or '' for t in el.iter(q('t')))


def _구역들(body) -> list:
    """구역마다 (글 폭, 왼쪽 여백, 종이 폭). 쪽 크기나 여백이 없으면 None."""
    out = []
    for sp in [p.find(q('pPr') + '/' + q('sectPr')) for p in body.iter(q('p'))] + [body.find(q('sectPr'))]:
        if sp is None:
            continue
        pg, mar = sp.find(q('pgSz')), sp.find(q('pgMar'))
        w, left, right = _수(pg), _수(mar, 'left'), _수(mar, 'right')
        out.append((w - left - right, left, w) if None not in (w, left, right) else None)
    return out


def 넘친_칸(path) -> list[str]:
    """글이 든 칸이 쪽 오른쪽 여백 밖에서 시작하거나 종이 밖으로 나가는 자리. 문서를 읽지 못하면 그 까닭 한 줄."""
    try:
        with zipfile.ZipFile(path) as z:
            root = etree.fromstring(z.read('word/document.xml'))
    except (OSError, KeyError, zipfile.BadZipFile, etree.XMLSyntaxError) as e:
        return [f'문서를 읽지 못했다: {e}']
    body = root.find(q('body'))
    if body is None:
        return []
    구역 = _구역들(body)
    out, 순번, 구역번호 = [], 0, 0
    for el in body.iter(q('p'), q('tbl')):
        if el.tag == q('p'):
            if el.find(q('pPr') + '/' + q('sectPr')) is not None:
                구역번호 += 1
            continue
        if any(a.tag == q('tbl') for a in el.iterancestors()):
            continue                                   # 표 안의 표
        순번 += 1
        쪽 = 구역[min(구역번호, len(구역) - 1)] if 구역 else None
        if 쪽 is None:
            continue
        글폭, 왼여백, 종이 = 쪽
        격자 = [_수(c, 기본=0) for c in el.findall(q('tblGrid') + '/' + q('gridCol'))]
        if not 격자:
            continue
        tblpr = el.find(q('tblPr'))
        들여 = _수(tblpr.find(q('tblInd')) if tblpr is not None else None, 기본=0)
        정렬 = tblpr.find(q('jc')) if tblpr is not None else None
        정렬 = 정렬.get(q('val')) if 정렬 is not None else ''
        합 = sum(격자)
        if 정렬 == 'center':
            들여 = (글폭 - 합) // 2
        elif 정렬 in ('right', 'end'):
            들여 = 글폭 - 합
        머리 = re.sub(r'\s+', ' ', _글(el)).strip()[:12]
        for 행번호, tr in enumerate(el.findall(q('tr')), 1):
            trpr = tr.find(q('trPr'))
            칸자리 = _수(trpr.find(q('gridBefore')) if trpr is not None else None, 'val', 0)
            for 칸번호, tc in enumerate(tr.findall(q('tc')), 1):
                span = _수(tc.find(q('tcPr') + '/' + q('gridSpan')), 'val', 1)
                왼 = 들여 + sum(격자[:칸자리])
                오른 = 들여 + sum(격자[:칸자리 + span])
                칸자리 += span
                글 = re.sub(r'\s+', ' ', _글(tc)).strip()
                if not 글:
                    continue
                if 왼 >= 글폭 - 여유:
                    까닭 = f'칸이 오른쪽 여백 안쪽 끝({글폭 / 567:.1f}cm) 밖인 {왼 / 567:.1f}cm 에서 시작한다'
                elif 오른 > 종이 - 왼여백 + 여유:
                    까닭 = f'칸 오른쪽 끝({오른 / 567:.1f}cm)이 종이 밖(글 시작에서 {(종이 - 왼여백) / 567:.1f}cm)이다'
                elif 왼 < -왼여백 - 여유:
                    까닭 = f'칸 왼쪽 끝이 종이 왼쪽 밖({왼 / 567:.1f}cm)이다'
                else:
                    continue
                out.append(f"표 {순번}('{머리}') {행번호}행 {칸번호}칸 '{글[:20]}' — {까닭}(표 너비 {합 / 567:.1f}cm)")
    return out


def check(path) -> int:
    """병합 뒤 점검(`docx_merge.py`)에서 부른다. 출력하고 넘친 칸이 있으면 1."""
    probs = 넘친_칸(path)
    print(f'표 칸 넘침 {len(probs)}건' + (': ' + '; '.join(probs[:5]) if probs else ''))
    return 1 if probs else 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f'파일이 없다: {path}')
        return 2
    probs = 넘친_칸(path)
    for p in probs:
        print(p)
    print(f'표 칸 넘침 {len(probs)}건 — {path.name}')
    return 1 if probs else 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
