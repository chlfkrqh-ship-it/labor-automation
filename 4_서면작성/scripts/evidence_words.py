"""쟁점 낱말을 호증 전체의 전 면에서 찾아 서면 인용과 맞댄다(`.claude/commands/서면.md` 6-1단계)

    python -B 4_서면작성/scripts/evidence_words.py "<사건 폴더>" --낱말 스피 피커 블루투 음악 [--라운드 N] [--호증 사 노]
           [--out "<라운드N>/작업/쟁점낱말_대조.md"] [--ocr-dir <폴더> ...] [--no-ocr] [--글 사6 ...]
    python -B 4_서면작성/scripts/evidence_words.py "<사건 폴더>" --확인      # '판단'이 빈 줄이 있으면 종료 코드 1(`/서면` 8-1단계)

호증 전부를 면마다 글자층(없거나 깨지면 Windows 문자인식, `ocr_win.ps1`)으로 읽어 낱말이 든 면을 표로 낸다. 낱말 글자 사이의 띄어쓰기는 무시한다.
문자인식은 글자를 잘못 읽으므로 낱말은 짧게 쓰고 일부('스피', '피커')도 함께 넣는다.
표의 '서면 인용' 칸은 각 라운드 `출력/서면초안.md` 본문('---' 위)에 그 호증의 그 면이 인용되었는지를 '이 면 인용'·'호증만 인용'·'인용 없음'으로 적는다.
'이 면 인용'이 아닌 줄을 먼저 싣는다. 판정은 작성 세션이 원본 그림으로 읽고 '판단' 칸에 적는다. 이 도구는 찾아 보여 줄 뿐 유불리를 판정하지 않는다.
글자가 없는 면(사진 등)과 PDF 가 아닌 호증은 끝에 목록으로 적으니 눈으로 본다. 찾지 못한 것을 '없다'로 단정하지 않는다.
문자인식 결과는 `증거관리/호증글자/` 에 쌓아 다시 쓰고, 그림은 남기지 않는다. `라운드*/작업/증거인용검토/ocr` 의 결과도 읽는다.

2026. 11. 2. GGM 정직 3월: 사 제6호증(38면, 글자층 없음) 3면의 쟁점 문구를 답변서(1)·(2)에 쓰지 못한 일로 만들었다.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import unicodedata
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_spec = importlib.util.spec_from_file_location('evidence_cite_review', Path(__file__).resolve().parent / 'evidence_cite_review.py')
_ecr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ecr)


def 호증_정렬(k: str):
    m = re.match(r'(\D+)(\d+)(?:-(\d+))?$', k)
    return (m.group(1), int(m.group(2)), int(m.group(3) or 0)) if m else (k, 0, 0)


def 호증_표시(k: str) -> str:
    m = re.match(r'(\D+)(\d+)(?:-(\d+))?$', k)
    return f'{m.group(1)} 제{m.group(2)}호증' + (f'의{m.group(3)}' if m.group(3) else '') if m else k


def 낱말_식(낱말: str):
    return re.compile(r'\s*'.join(re.escape(c) for c in re.sub(r'\s', '', 낱말)))


def 서면_본문(사건: Path) -> str:
    글 = []
    for p in sorted(사건.glob('라운드*/출력/서면초안.md')):
        t = p.read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n')
        글.append(t.split('\n---\n')[0])
    return '\n'.join(글)


def 면_목록(식: str) -> set:
    """'3', '3~5', '3, 5', '3·5~7' 꼴을 면 번호 모음으로 바꾼다. 쉼표·가운뎃점은 낱낱의 면이고 물결만 범위이다."""
    면들 = set()
    for 조각 in re.split(r'\s*[,·ㆍ]\s*', 식):
        a, _, b = 조각.partition('~')
        if a.strip().isdigit():
            시작 = int(a)
            면들.update(range(시작, (int(b) if b.strip().isdigit() else 시작) + 1))
    return 면들


def 인용_상태(본문: str, k: str, 면: int) -> str:
    m = re.match(r'(\D+)(\d+)(?:-(\d+))?$', k)
    if not m:
        return '인용 없음'
    호 = rf'{m.group(1)}\s*제\s*{m.group(2)}\s*호증' + (rf'\s*의\s*{m.group(3)}' if m.group(3) else '') + r'(?!\s*의)'
    if not re.search(호, 본문):
        return '인용 없음'
    # 면 표시는 그 호증 뒤에 다른 호증이 끼지 않은 것만 본다('사 제6호증, 사 제7호증 3면'의 3면은 사 제7호증의 것이다)
    for x in re.finditer(호 + r'(?:(?!호증)[^()\n]){0,40}?(\d+(?:\s*[~,·ㆍ]\s*\d+)*)\s*(?:면|쪽)', 본문):
        if 면 in 면_목록(x.group(1)):
            return '이 면 인용'
    return '호증만 인용'


def 표_글(s: str) -> str:
    return re.sub(r'\s+', ' ', s).replace('|', '｜').strip()


def 표시_키(표시: str):
    m = re.match(r'(\D+?)\s*제(\d+)호증(?:의(\d+))?$', 표시)
    return f'{m.group(1)}{m.group(2)}' + (f'-{m.group(3)}' if m.group(3) else '') if m else None


def 표_읽기(out: Path) -> list:
    """앞서 만든 표의 줄. [(호증 표시, 면, 낱말, 앞뒤 글, 서면 인용, 읽은 방식, 판단)]"""
    if not out.is_file():
        return []
    줄 = []
    for line in out.read_text(encoding='utf-8').splitlines():
        if not line.startswith('| ') or line.startswith('| 호증 |'):
            continue
        cells = [c.strip() for c in line.strip()[1:-1].split('|')]
        if len(cells) >= 7 and cells[1].isdigit():
            줄.append((cells[0], int(cells[1]), cells[2], cells[3], cells[4], cells[5], '|'.join(cells[6:]).strip()))
    return 줄


def 확인(out: Path, 본문: str) -> int:
    """`/서면` 8-1단계: 표가 있고, 서면이 그 면을 인용하지 않은 줄마다 '판단'이 적혔는지 본다. 서면 인용은 지금 초안으로 다시 본다."""
    if not out.is_file():
        print(f'쟁점 낱말 대조표가 없습니다: {out} (`/서면` 6-1단계를 먼저 한다)')
        return 1
    줄들, 빈 = 표_읽기(out), []
    for 표시, no, w, ctx, st, src, 판단 in 줄들:
        k = 표시_키(표시)
        지금 = 인용_상태(본문, k, no) if k else st
        if 지금 != '이 면 인용' and not 판단:
            빈.append(f'{표시} {no}면({w}, {지금}): {ctx[:80]}')
    if 빈:
        print(f"'판단' 칸이 빈 줄 {len(빈)}개 — 원본 그림으로 읽고 적는다({out})")
        for s in 빈:
            print('  - ' + s)
        return 1
    print(f"쟁점 낱말 대조표 {len(줄들)}줄, '판단'이 빈 줄 없음 → {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='쟁점 낱말을 호증 전체의 전 면에서 찾는다')
    ap.add_argument('case')
    ap.add_argument('--낱말', nargs='*', default=[])
    ap.add_argument('--라운드', type=int)
    ap.add_argument('--호증', nargs='*', help='호증 머리글자만 볼 때(사 노 등). 없으면 전부')
    ap.add_argument('--out')
    ap.add_argument('--ocr-dir', action='append', default=[])
    ap.add_argument('--no-ocr', action='store_true')
    ap.add_argument('--글', nargs='*', default=[], help='이 호증키(사6 등)의 면별 글을 화면에 보여 준다. 낱말 없이 쓰면 표를 쓰지 않는다')
    ap.add_argument('--확인', action='store_true',
                    help="호증을 다시 읽지 않고, 서면이 인용하지 않은 줄의 '판단' 칸이 다 찼는지 본다(빈 줄이 있으면 종료 코드 1)")
    a = ap.parse_args(argv)
    if not (a.낱말 or a.글 or a.확인):
        ap.error('--낱말, --글, --확인 가운데 하나는 준다')

    사건 = Path(a.case)
    라운드들 = sorted((p for p in 사건.glob('라운드*') if p.is_dir()), key=lambda p: int(re.sub(r'\D', '', p.name) or 0))
    if not 라운드들:
        print('라운드 폴더가 없습니다:', 사건)
        return 2
    라운드 = 사건 / f'라운드{a.라운드}' if a.라운드 else 라운드들[-1]
    out = Path(a.out) if a.out else 라운드 / '작업' / '쟁점낱말_대조.md'
    if a.확인:
        return 확인(out, 서면_본문(사건))
    캐시 = 사건 / '증거관리' / '호증글자'
    ocr_dirs = list(a.ocr_dir) + [str(p) for p in 사건.glob('라운드*/작업/증거인용검토/ocr')] + [str(캐시 / 'ocr')]

    호증들 = {}
    for k, ps in _ecr.find_exhibits(사건, 라운드).items():    # 작업/ 아래의 지난 판(옛 호증 번호)은 읽지 않는다
        ps = [p for p in ps if '작업' not in p.relative_to(사건).parts]
        if ps:
            호증들[k] = ps
    if a.호증:
        호증들 = {k: v for k, v in 호증들.items() if any(k.startswith(x) for x in a.호증)}
    식들 = [(w, 낱말_식(w)) for w in a.낱말]
    본문 = 서면_본문(사건)
    줄들, 없는면, 합계 = [], {}, {'글자층': 0, '문자인식': 0, '글자 없음': 0}
    for k in sorted(호증들, key=호증_정렬):
        ex = _ecr.Exhibit(k, 호증들[k][0], 캐시, ocr_dirs=ocr_dirs, use_ocr=not a.no_ocr)
        면수 = len(ex)
        try:
            ex.prepare(range(1, 면수 + 1))
            for no in range(1, 면수 + 1):
                e = ex.pages.get(no) or {'src': '글자 없음', 'units': []}
                글 = ' '.join(t for t, _ in e['units'])
                종류 = '문자인식' if e['src'].startswith('문자인식') else ('글자층' if e['src'].startswith('글자층') and 글.strip() else '글자 없음')
                합계[종류] += 1
                if k in a.글:
                    print(f'--- {호증_표시(k)} {no}면({e["src"]})\n{글}')
                if len(re.sub(r'\s', '', 글)) < 20:
                    없는면.setdefault(k, []).append(no)
                본 = set()
                for w, 식 in 식들:
                    for m in 식.finditer(글):
                        if any(abs(m.start() - x) < 60 for x in 본):
                            continue
                        본.add(m.start())
                        줄들.append((k, no, w, 표_글(글[max(0, m.start() - 60):m.end() + 70]), 인용_상태(본문, k, no), e['src']))
        finally:
            ex.close()
        print(f'{호증_표시(k)} {면수}면 읽음', flush=True)
    for p in 캐시.glob('ocr/*/*.png'):      # 글만 쌓고 그림은 남기지 않는다
        p.unlink()

    비pdf = []
    for dp, dn, fn in os.walk(사건):
        parts = Path(dp).relative_to(사건).parts
        if '백업' in parts or '작업' in parts or not any(x in _ecr.EVIDENCE_DIRS for x in parts):
            continue
        for f in fn:
            k = _ecr.file_key(f)
            if k and not f.lower().endswith('.pdf') and k not in 호증들 and (not a.호증 or any(k.startswith(x) for x in a.호증)):
                비pdf.append(unicodedata.normalize('NFC', f))

    if not a.낱말:                        # --글 만: 면별 글을 보여 주기만 하고 표는 그대로 둔다
        return 0

    # 다시 돌려도 앞서 적은 '판단'을 잃지 않는다. 이번에 찾지 않은 낱말·호증의 줄은 그대로 두고 서면 인용만 새로 본다
    옛줄 = 표_읽기(out)
    옛판단 = {(표시, no, w): 판단 for 표시, no, w, *_, 판단 in 옛줄 if 판단}
    면판단 = {}
    for 표시, no, w, *_, 판단 in 옛줄:
        if 판단:
            면판단.setdefault((표시, no), 판단)
    이번 = set(a.낱말)
    새줄, 이어받음, 남김 = [], 0, []
    for k, no, w, ctx, st, src in 줄들:
        판단 = 옛판단.get((호증_표시(k), no, w)) or 면판단.get((호증_표시(k), no), '')
        이어받음 += bool(판단)
        새줄.append((k, no, w, ctx, st, src, 판단))
    for 표시, no, w, ctx, st, src, 판단 in 옛줄:
        k = 표시_키(표시)
        if not k or (w in 이번 and k in 호증들):
            continue
        새줄.append((k, no, w, ctx, 인용_상태(본문, k, no), src, 판단))
        남김.append(w)
    낱말들 = list(dict.fromkeys(list(a.낱말) + 남김))

    먼저 = {'인용 없음': 0, '호증만 인용': 1, '이 면 인용': 2}
    새줄.sort(key=lambda r: (먼저.get(r[4], 0), 호증_정렬(r[0]), r[1]))
    글 = [f'# 쟁점 낱말 대조 — {사건.name} {라운드.name}', '',
          f"낱말: {', '.join(낱말들)}", f"읽은 호증 {len(호증들)}건 · 글자층 {합계['글자층']}면 · 문자인식 {합계['문자인식']}면 · 글자 없음 {합계['글자 없음']}면 · 걸린 줄 {len(새줄)}개", '',
          "`4_서면작성/scripts/evidence_words.py` 가 만든다. '판단' 칸은 원본 그림을 읽고 적는다(본문에 씀, 하단 ②에 적음, 쓰지 않음과 그 이유). "
          "다시 돌리면 같은 면의 '판단'은 이어받고, 이번에 찾지 않은 낱말의 줄은 남긴다. 다 적었는지는 `--확인` 으로 본다.", '',
          '| 호증 | 면 | 낱말 | 앞뒤 글 | 서면 인용 | 읽은 방식 | 판단 |', '|---|---|---|---|---|---|---|']
    for k, no, w, ctx, st, src, 판단 in 새줄:
        글.append(f'| {호증_표시(k)} | {no} | {w} | {ctx} | {st} | {src} | {판단} |')
    글 += ['', '## 글자로 찾지 못한 곳(눈으로 본다)', '']
    for k in sorted(없는면, key=호증_정렬):
        글.append(f"- {호증_표시(k)}: {', '.join(map(str, 없는면[k]))}면")
    for f in sorted(비pdf):
        글.append(f'- PDF 가 아닌 호증: {f}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(글) + '\n', encoding='utf-8')
    안쓴 = [r for r in 새줄 if r[4] != '이 면 인용']
    빈 = sum(1 for r in 안쓴 if not r[6])
    print(f"호증 {len(호증들)}건, 글자층 {합계['글자층']}면, 문자인식 {합계['문자인식']}면, 글자 없음 {합계['글자 없음']}면 / 걸린 줄 {len(새줄)}개, "
          f"이 면을 인용하지 않은 줄 {len(안쓴)}개(판단이 빈 줄 {빈}개, 이어받은 판단 {이어받음}줄) → {out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
