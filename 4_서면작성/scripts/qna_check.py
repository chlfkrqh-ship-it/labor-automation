"""심문회의 예상 질의답변 docx 를 `.claude/commands/예상질의.md` 의 모양 규칙과 맞댄다.

    python -B 4_서면작성/scripts/qna_check.py "<출력>/({의뢰인명}) 심문회의 예상 질의답변_초안.docx"

보는 것(그 명령어에 적힌 것만 본다)
  제목        '예상 질의 및 답변'('질의와 답변'은 쓰지 않는다)
  넣지 않는 절  유의사항·심문회의 순서·위원별 질의·회의 시작·화해·판정 이후·신청인 측 예상 질의
  표시        누가 묻는지('(사용자위원)')와 누가 답하는지('대리인이 답하겠습니다', '최종 진술(대리인)')
  회색 메모    '[질의 이유]'로 시작한다. 지시·자료 요구와 쓰지 말라고 한 말, 진행 상황, '적다'가 없다
  정렬        본문과 음영 칸을 왼쪽 정렬로 두지 않는다(양쪽 맞춤)
위반이 있으면 종료 코드 1 이다. 사내 인사위원회 리허설 문서는 유의사항을 두는 등 모양이 달라 보지 않는다.

2026. 11. 2. 담당 노무사가 첫 판을 보고 지적한 것이 지침으로만 남아 있어 `/하자보완` 이 검사로 옮겼다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import docx
from docx.oxml.ns import qn

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

회색 = '595959'         # 공통/scripts/research_docx.py 의 회색 글자
표시 = re.compile(r'\(\s*(?:공익|근로자|사용자)\s*위원\s*\)|대리인이\s*답(?:하겠습니다|변드리겠습니다)|최종\s*진술\s*\(\s*대리인\s*\)')
안_넣는_절 = re.compile(r'유의사항|심문회의\s*순서|위원별\s*질의|회의\s*시작|화해|판정\s*이후|신청인\s*측에\s*대한')
메모_금지 = re.compile(r'짚어\s*묻|물을\s*곳|불리한\s*대목|말씀하지\s*마|가져오(?:십시오|시기|시면|셔)|지참|준비해\s*두|보여\s*(?:주십시오|주시기|드리)|확인\s*중')
메모_적다 = re.compile(r'(?<![가-힣])적(?:혀|힌|었|습니다|어\s*있)')


def 글(p) -> str:
    return ''.join(t.text or '' for t in p.iter(qn('w:t')))


def 첫_글자색(p):
    """문단에서 글자가 있는 첫 run 의 색."""
    for r in p.iter(qn('w:r')):
        if ''.join(t.text or '' for t in r.iter(qn('w:t'))).strip():
            c = r.find(qn('w:rPr') + '/' + qn('w:color'))
            return c.get(qn('w:val')) if c is not None else None
    return None


def 왼쪽_정렬(p) -> bool:
    jc = p.find(qn('w:pPr') + '/' + qn('w:jc'))
    return jc is not None and jc.get(qn('w:val')) in ('left', 'start')


def check(path: Path) -> list:
    d = docx.Document(str(path))
    out = []
    문단들 = [p for p in d.element.body.iter(qn('w:p')) if 글(p).strip()]
    제목 = next((글(p) for p in 문단들 if re.match(r'제\s*목', 글(p))), 글(문단들[0]) if 문단들 else '')
    if '예상 질의 및 답변' not in re.sub(r'\s+', ' ', 제목.replace('\xa0', ' ')):
        out.append(f"제목: '예상 질의 및 답변'이 아니다: {제목[:60]}")
    for p in d.paragraphs:
        if p.style.name == '1.' and 안_넣는_절.search(p.text):
            out.append(f'넣지 않는 절: {p.text[:40]}')
    for p in 문단들:
        t = 글(p)
        for m in 표시.finditer(t):
            out.append(f"묻는 이·답하는 이 표시: {m.group(0)} — {t[:50]}")
        if 왼쪽_정렬(p) and len(t.strip()) > 30:
            out.append(f'왼쪽 정렬(본문은 양쪽 맞춤): {t[:50]}')
        if 첫_글자색(p) == 회색:
            if not t.lstrip().startswith('[질의 이유]'):
                out.append(f"회색 메모가 '[질의 이유]'로 시작하지 않는다: {t[:50]}")
            for m in list(메모_금지.finditer(t)) + list(메모_적다.finditer(t)):
                앞 = max(0, m.start() - 20)
                out.append(f"회색 메모의 쓰지 않는 말 '{m.group(0)}': …{t[앞:m.end() + 15]}…")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='심문회의 예상 질의답변의 모양 규칙 검사')
    ap.add_argument('file')
    a = ap.parse_args(argv)
    문제 = check(Path(a.file))
    for s in 문제:
        print('[위반] ' + s)
    print(f'{Path(a.file).name}: 위반 {len(문제)}건')
    return 1 if 문제 else 0


if __name__ == '__main__':
    raise SystemExit(main())
