"""라운드의 우리증거·상대증거가 섞여 있으면 묻지 않고 제자리로 나눈다.

전자소송 기록을 한꺼번에 받거나 메일 첨부를 한 폴더에 받으면 피고 서면·서증과 법원 문서가 `우리증거/` 에 섞인다.
그러면 `/서면` 의 반박 구성과 관문의 '상대 서면 맞대기'가 상대방 서면이 없다고 보고 건너뛴다.
2026. 11. 3. 한전 태양광 22명: 피고 2026. 10. 8.자 서면이 우리증거/ 에 있어 관문이 '해당 없음'으로 넘어갔고,
담당자가 "우리증거 상대증거 안나눠져있으면 자동으로 나누는 방향으로 가고"라고 하였다.

    python -B 4_서면작성/scripts/evidence_sort.py "4_서면작성/사건/{사건명}" [--라운드 N]            # 미리보기
    python -B 4_서면작성/scripts/evidence_sort.py "4_서면작성/사건/{사건명}" [--라운드 N] --apply    # 옮기기
    python -B 4_서면작성/scripts/evidence_sort.py "4_서면작성/사건/{사건명}" [--라운드 N] --확인     # 옮길 것이 있으면 종료 코드 1

나누는 기준(파일 이름만 본다. 내용은 열지 않는다):
- 호증 표시 '(갑12_', '(을17_', '사제3호증…': 증거관리/ 의 호증목록에 그 부호가 어느 쪽인지 있으면 그 쪽. 목록에 없으면 평안이 낸 파일의 부호로 정한다.
- 제출자 '…_피고 대리인_법무법인(유한)바른': 법무법인 평안이 있거나 평안이 낸 파일과 같은 당사자이면 우리, 다른 당사자이면 상대.
- 제출자가 없는 법원 문서(변론조서, 보정명령, 판결 등)와 제출자가 '기타_…' 인 제3자 회신: 참고자료.
- 어느 것도 없으면(의뢰인 자료의 이름 등) 그대로 두고 목록으로 보인다.
옮기기는 라운드의 `우리증거/`·`상대증거/` 바로 아래 파일만 한다. 하위 폴더(`호증별/`, 회신 자료 묶음)는 건드리지 않는다.
같은 이름의 파일이 이미 있으면 옮기지 않고 막힘으로 보인다. 옮기면 `증거관리/호증읽기/*.md` 의 '파일:' 줄과 사건 문서(.md)에 적힌 그 파일의 경로를 함께 고친다.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('evidence_cite_review_for_sort', Path(__file__).with_name('evidence_cite_review.py'))
_ecr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ecr)

우리, 상대, 참고 = '우리증거', '상대증거', '참고자료'
당사자 = r'(?:재심피신청인|재심신청인|피신청인|신청인|피고보조참가인|원고보조참가인|보조참가인|피고인|피고|원고|참가인|피청구인|청구인|피진정인|진정인)'
제출자_꼴 = re.compile(r'_(' + 당사자 + r'[^_()]*(?:_[^()]*)?|기타[^()]*|피|원)$')
법원_문서 = re.compile(r'조서|명령|결정|판결|기일|통지|촉탁|판정|화해|조정|권고|안내문|접수증|독촉')
우리_글 = '평안'


def _nfc(s: str) -> str:
    return unicodedata.normalize('NFC', s)


def _long(p) -> str:
    """이름이 긴 전자소송 파일도 다룰 수 있는 경로."""
    s = os.path.abspath(str(p))
    return '\\\\?\\' + s if os.name == 'nt' and not s.startswith('\\\\?\\') else s


def 줄기(이름: str) -> str:
    n = _nfc(이름)
    return re.sub(r'\.(pdf|docx?|hwpx?|xlsx?|zip|jpe?g|png|p|pd)$', '', n, flags=re.I)


def 제출자(이름: str) -> str:
    """이름 끝의 제출자. 전자소송 꼴은 표제 괄호 뒤, 아니면 끝의 '_원고 대리인_법무법인 평안' 꼴."""
    s = 줄기(이름)
    if ')_' in s:
        return s.rsplit(')_', 1)[1].strip()
    m = 제출자_꼴.search(s)
    return m.group(1).strip() if m else ''


def _라벨(제출: str) -> str:
    m = re.match(당사자, 제출)
    return m.group(0) if m else ''


def 부호(이름: str) -> str:
    k = _ecr.file_key(_nfc(이름))
    return re.match(r'\D+', k).group(0) if k else ''


def 목록_부호(사건: Path) -> dict:
    """증거관리 호증목록에 적힌 부호 → 쪽."""
    out = {}
    for 쪽, 파일 in ((우리, '우리호증목록.md'), (상대, '상대호증목록.md')):
        f = 사건 / '증거관리' / 파일
        if not f.is_file():
            continue
        for line in f.read_text(encoding='utf-8').splitlines():
            m = re.match(r'\|\s*(' + _ecr.PREFIX + r')\s*(?:제\s*)?\d', line)
            if m:
                out.setdefault(m.group(1), 쪽)
    return out


def 우리_라벨(이름들) -> set:
    """법무법인 평안이 낸 파일의 당사자 라벨(원고 등)과 호증 부호."""
    라벨, 부호들 = set(), set()
    for n in 이름들:
        제 = 제출자(n)
        if 우리_글 in 제:
            if _라벨(제):
                라벨.add(_라벨(제))
            if 부호(n):
                부호들.add(부호(n))
    return 라벨 | 부호들


def 분류(이름: str, 목록: dict, 우리표: set) -> tuple:
    """(쪽 또는 None, 이유)"""
    제 = 제출자(이름)
    호 = 부호(이름)
    if 우리_글 in 제:
        return 우리, f'제출자 {제}'
    if 호:
        if 호 in 목록:
            return 목록[호], f'호증 부호 {호}(호증목록)'
        if 호 in 우리표:
            return 우리, f'호증 부호 {호}(평안이 낸 호증과 같음)'
        if 제 and 우리표:
            return 상대, f'호증 부호 {호}, 제출자 {제}'
    if 제.startswith('기타'):
        return 참고, f'제3자 제출({제})'
    if 제:
        라 = _라벨(제)
        if 라 and 라 in 우리표:
            return 우리, f'제출자 {제}'
        if 라 or 제 in ('피', '원'):
            return (상대, f'제출자 {제}') if 우리표 else (None, f'우리 쪽을 알 수 없음(제출자 {제})')
    if ')_' not in 줄기(이름) and 줄기(이름).endswith(')') and re.match(r'.+_\d{4}\.\d{2}\.\d{2}_', _nfc(이름)):
        return 참고, '제출자가 없는 법원 문서'
    if re.match(r'.+_\d{4}\.\d{2}\.\d{2}_', _nfc(이름)) and 법원_문서.search(_nfc(이름)):
        return 참고, '법원 문서'
    return None, '표시 없음'


def 대상_라운드(사건: Path, 번호) -> Path:
    if 번호:
        return 사건 / f'라운드{번호}'
    rs = sorted((p for p in 사건.glob('라운드*') if p.is_dir()), key=lambda p: int(re.sub(r'\D', '', p.name) or 0))
    if not rs:
        raise SystemExit(f'라운드 폴더가 없습니다: {사건}')
    return rs[-1]


def _파일들(폴더: Path) -> list:
    if not os.path.isdir(_long(폴더)):
        return []
    return sorted(e.name for e in os.scandir(_long(폴더)) if e.is_file() and not e.name.startswith('~$') and e.name != 'desktop.ini')


def 계획(사건: Path, 라운드: Path) -> dict:
    """{'옮김': [(옛 폴더, 새 폴더, 이름, 이유)], '막힘': [...], '그대로': [(폴더, 이름, 이유)]}"""
    목록 = 목록_부호(사건)
    전체 = {쪽: _파일들(라운드 / 쪽) for 쪽 in (우리, 상대)}
    우리표 = 우리_라벨(전체[우리] + 전체[상대])
    옮김, 막힘, 그대로 = [], [], []
    for 쪽, 이름들 in 전체.items():
        for n in 이름들:
            새, 이유 = 분류(n, 목록, 우리표)
            if 새 is None:
                그대로.append((쪽, n, 이유))
            elif 새 != 쪽:
                if os.path.exists(_long(라운드 / 새 / n)):
                    막힘.append((쪽, 새, n, '같은 이름의 파일이 이미 있음'))
                else:
                    옮김.append((쪽, 새, n, 이유))
    return {'옮김': 옮김, '막힘': 막힘, '그대로': 그대로}


def 경로_고치기(사건: Path, 라운드: Path, 옮김: list) -> int:
    """옮긴 파일의 경로를 사건 문서에서 고친다. 호증읽기 기록의 '파일:' 줄과 작업 문서에 적힌 '{폴더}/{이름}'."""
    표 = {}
    for 옛, 새, n, _ in 옮김:
        표[f'{옛}/{n}'] = f'{새}/{n}'
        표[f'{옛}\\{n}'] = f'{새}\\{n}'
    if not 표:
        return 0
    짝 = sorted(표, key=len, reverse=True)
    고친 = 0
    문서들 = []
    for d, p in ((사건 / '증거관리', '**/*.md'), (사건 / '작업', '*.md'), (라운드 / '작업', '*.md')):
        if d.is_dir():
            문서들 += list(d.glob(p))
    for f in 문서들:
        t = f.read_text(encoding='utf-8')
        if '증거' not in t:
            continue
        새글 = t
        for k in 짝:
            if k in 새글:
                새글 = 새글.replace(k, 표[k])
        if 새글 != t:
            f.write_text(새글, encoding='utf-8')
            고친 += 1
    return 고친


def 옮기기(사건: Path, 라운드: Path, 안: dict) -> list:
    끝낸 = []
    for 옛, 새, n, 이유 in 안['옮김']:
        os.makedirs(_long(라운드 / 새), exist_ok=True)
        os.rename(_long(라운드 / 옛 / n), _long(라운드 / 새 / n))
        끝낸.append((옛, 새, n, 이유))
    return 끝낸


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='우리증거·상대증거·참고자료를 파일 이름으로 나눈다')
    ap.add_argument('case')
    ap.add_argument('--라운드', type=int)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--확인', action='store_true')
    ap.add_argument('--목록', action='store_true', help='옮길 파일과 그대로 둘 파일을 모두 보인다')
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    사건 = Path(a.case)
    if not 사건.is_absolute():
        사건 = (Path.cwd() / 사건)
    라운드 = 대상_라운드(사건, a.라운드)
    안 = 계획(사건, 라운드)
    셈 = {}
    for 옛, 새, _, _ in 안['옮김']:
        셈[(옛, 새)] = 셈.get((옛, 새), 0) + 1
    print(f'{라운드.name}: 옮길 파일 {len(안["옮김"])}건, 같은 이름이 있어 막힌 파일 {len(안["막힘"])}건, 표시가 없어 그대로 둘 파일 {len(안["그대로"])}건')
    for (옛, 새), n in sorted(셈.items()):
        print(f'  {옛}/ → {새}/ {n}건')
    if a.확인:
        if 안['옮김'] or 안['막힘']:
            print(f'나누기: python -B 4_서면작성/scripts/evidence_sort.py "{a.case}" --라운드 {re.sub(chr(92) + "D", "", 라운드.name)} --apply')
        return 1 if 안['옮김'] or 안['막힘'] else 0
    if a.목록:
        for 옛, 새, n, 이유 in 안['옮김']:
            print(f'  옮김 {옛} → {새} | {이유} | {n}')
    for 옛, 새, n, 이유 in 안['막힘']:
        print(f'  막힘 {옛} → {새} | {이유} | {n}')
    for 쪽, n, 이유 in 안['그대로']:
        print(f'  그대로 {쪽} | {이유} | {n}')
    if a.apply:
        끝낸 = 옮기기(사건, 라운드, 안)
        고친 = 경로_고치기(사건, 라운드, 끝낸)
        print(f'옮김 {len(끝낸)}건, 경로를 고친 문서 {고친}개')
        print(f'다음: python -B 공통/scripts/system.py scan "{a.case}" --accept')
    else:
        print('미리보기입니다. --apply 를 붙이면 옮깁니다.')
    return 1 if 안['막힘'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
