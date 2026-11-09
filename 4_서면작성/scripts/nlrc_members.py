# -*- coding: utf-8 -*-
"""노동위원회 심문회의 위원 명단·프로필을 한 면 표 PDF 로 만든다(`/노동위서류` '위원 명단·프로필').

    python -B 4_서면작성/scripts/nlrc_members.py "4_서면작성/사건/{사건명}/라운드N"
    python -B 4_서면작성/scripts/nlrc_members.py "…/라운드N" --통지 "{심문일정 통지.pdf}"
    python -B 4_서면작성/scripts/nlrc_members.py "…/라운드N" --위원회 전남 --공익 최영범 권순근 김재민 --근로자 서경남 --사용자 김용훈
    python -B 4_서면작성/scripts/nlrc_members.py "…/라운드N" --out "{파일.pdf}" --약칭 GGM

1. 위원: 사건 폴더 라운드들의 `참고자료/` 에서 이름에 '심문일정 통지'가 든 PDF(가장 뒤 라운드의 것)를 읽어
   '공 익 위 원:', '근로자위원:', '사용자위원:' 줄의 이름과 노동위원회 이름을 뽑는다. 통지서가 없거나 읽히지 않으면
   `--위원회`·`--공익`·`--근로자`·`--사용자` 로 넘긴다.
2. 프로필: 중앙노동위원회 누리집 '위원소개' 표(구분·성명·현직·업무, https://nlrc.go.kr/nlrc/commIntro/member/list.do 에
   위원회 코드를 붙여 받는다)에서 이름으로 고른다. 같은 이름이 둘 이상이거나 없으면 멈춘다(사람이 누리집에서 고른다).
3. 표: OES 부당해고 사건 라운드3 `참고자료/노동위원회 위원명단.pdf`(2026. 11. 5. 강민석 변호사가 팀즈에 올린 판)에서 잰
   모양으로 그린다. A4 가로 한 면, 칸은 구분·성명·현직·업무, 순서는 통지서대로 공익위원(위원장 포함)·근로자위원·사용자위원.
4. 확인: 낸 PDF 의 글을 다시 뽑아 칸마다 누리집 값이 들어 있는지와 한 면인지 맞대고, 첫 면 그림을 임시 폴더에 그린다.
   보고에 옮길 마크다운 표와 출처 줄을 찍는다.

낼 곳은 `라운드N/출력/({약칭}) 노동위원회 위원명단.pdf` 이다(약칭은 사건 폴더 이름의 '_' 앞, 예: GGM_정직3월 → GGM).
같은 이름이 있으면 덮어쓴다.

2026. 11. 9. GGM 정직 3월 심문회의 날 강민석 변호사가 "위원명단이랑 프로필 좀 부탁드림다", 담당 노무사가 OES 판과 같은 양식으로
정리하게 한 뒤 "앞으로도 요런 식으로 위원프로필 정리 부탁"(그날 사건 폴더의 빌드를 이 도구로 옮겼다).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import re
import sys
import tempfile
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

목록주소 = 'https://nlrc.go.kr/nlrc/commIntro/member/list.do'
누리집_면 = 'https://nlrc.go.kr/nlrc/commIntro/member.do'
위원회코드 = {'중앙': '00', '서울': '01', '부산': '02', '경기': '03', '충남': '04', '전남': '05', '경북': '06',
          '경남': '07', '인천': '08', '강원': '09', '충북': '10', '전북': '11', '제주': '12', '울산': '13'}
머리 = ('구분', '성명', '현직', '업무')

# OES 판(노동위원회 위원명단.pdf)에서 잰 값. 단위 pt.
면너비, 면높이 = 841.92, 594.96
칸X = (57.0, 195.0, 333.8, 618.0, 785.2)
윗선 = (57.0, 58.5)
머리줄 = (57.8, 97.5)
줄높이 = 39.0
글크기, 최소크기 = 13.0, 8.5
안쪽 = 10.8                       # 현직 칸 왼쪽 띄움, 다른 칸의 좌우 여백
색값 = {'머리채움': 'F7FBFF', '윗선': '17337F', '칸선': 'DDE4EB', '머리글': '1F2A3C', '본문글': '444444', '성명': '1D4A9E'}


class 멈춤(Exception):
    """사람이 확인해야 해서 멈춘다."""


def 붙인글(s: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', s or ''))


# ---------------------------------------------------------------- 1. 통지서

def 통지서_찾기(라운드: Path) -> Path | None:
    """라운드 폴더와 같은 사건의 다른 라운드 `참고자료/` 에서 이름에 '심문일정 통지'가 든 PDF. 뒤 라운드의 것을 먼저 고른다."""
    사건 = 라운드.parent if re.match(r'라운드\d+$', 라운드.name) else 라운드
    후보 = []
    for d in sorted((x for x in 사건.glob('라운드*') if x.is_dir()), key=lambda x: int(re.sub(r'\D', '', x.name) or 0), reverse=True):
        for p in sorted((d / '참고자료').rglob('*.pdf')) if (d / '참고자료').is_dir() else []:
            if '심문일정' in unicodedata.normalize('NFC', p.name) and '통지' in unicodedata.normalize('NFC', p.name):
                후보.append(p)
        if 후보:
            return 후보[0]
    return None


def 통지서_글(p: Path) -> str:
    import pymupdf
    with pymupdf.open(p) as d:
        return '\n'.join(pg.get_text('text') for pg in d)


def 통지서_읽기(글: str) -> dict:
    """통지서 글에서 위원회와 위원 이름. {'위원회': '전남', '공익': [...], '근로자': [...], '사용자': [...]}"""
    글 = unicodedata.normalize('NFC', 글)
    이름들 = lambda s: re.findall(r'[가-힣]{2,4}', s or '')
    m = re.search(r'공\s*익\s*위\s*원\s*[:：]\s*([가-힣\s,，·ㆍ]+?)(?=\n\s*참|\n\s*근로자|\n\s*사용자|\n\s*심\s*문|$)', 글)
    공익 = 이름들(m.group(1)) if m else []
    근 = re.search(r'근로자\s*위원\s*[:：]\s*([가-힣\s,，·ㆍ]+?)(?=\n|$)', 글)
    사 = re.search(r'사용자\s*위원\s*[:：]\s*([가-힣\s,，·ㆍ]+?)(?=\n|$)', 글)
    횟수 = {}
    for k in 위원회코드:
        n = len(re.findall(k + (r'노동위원회' if k == '중앙' else r'지방노동위원회'), 글))
        if n:
            횟수[k] = n
    위원회 = max(횟수, key=횟수.get) if 횟수 else ''
    return {'위원회': 위원회, '공익': 공익, '근로자': 이름들(근.group(1)) if 근 else [], '사용자': 이름들(사.group(1)) if 사 else []}


# ---------------------------------------------------------------- 2. 누리집

def 목록_받기(위원회: str, timeout: int = 30) -> str:
    if 위원회 not in 위원회코드:
        raise 멈춤(f"위원회 '{위원회}' 를 모른다(가능: {', '.join(위원회코드)})")
    data = urllib.parse.urlencode({'cmitCd': 위원회코드[위원회], 'mcmtJbpsSeCd': '', 'pageIndex': '1', 'recordCountPerPage': '1000',
                                   'likeColumn': 'KORN_FLNM', 'likeCondition': ''}).encode()
    req = urllib.request.Request(목록주소, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def 목록_읽기(문서: str) -> tuple[list[tuple[str, str, str, str]], int | None]:
    """누리집 표의 줄(구분, 성명, 현직, 업무)과 '위원수 : N명'의 N."""
    몸 = re.search(r'<tbody>(.*?)</tbody>', 문서, re.S)
    줄들 = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', 몸.group(1) if 몸 else '', re.S):
        칸 = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', c))).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        if len(칸) == 4 and 칸[1]:
            줄들.append(tuple(칸))
    n = re.search(r'위원수\s*:\s*(\d+)\s*명', 문서)
    return 줄들, (int(n.group(1)) if n else None)


def 고르기(줄들, 위원: dict) -> list[tuple[str, str, str, str]]:
    """통지서 순서(공익·근로자·사용자)대로 누리집 줄을 고른다. 없거나 둘 이상이면 멈춘다."""
    고른, 문제 = [], []
    for 갈래 in ('공익', '근로자', '사용자'):
        for 이름 in 위원.get(갈래) or []:
            맞음 = [r for r in 줄들 if 붙인글(r[1]) == 붙인글(이름)]
            if len(맞음) == 1:
                고른.append(맞음[0])
            elif not 맞음:
                문제.append(f'{이름}({갈래}위원): 누리집 위원소개에 없다')
            else:
                문제.append(f'{이름}({갈래}위원): 같은 이름이 {len(맞음)}명 — ' + ' / '.join(' · '.join(r) for r in 맞음))
    if 문제:
        raise 멈춤('; '.join(문제) + ' — 누리집에서 사람이 확인한 뒤 --공익/--근로자/--사용자 로 이름을 고쳐 넘기거나 표를 손으로 고친다')
    if not 고른:
        raise 멈춤('위원 이름이 없다 — 통지서의 심판위원회 위원 칸을 읽지 못했으면 --공익/--근로자/--사용자 로 넘긴다')
    return 고른


# ---------------------------------------------------------------- 3. 표

def 글꼴들():
    import pymupdf
    win = Path(r'C:\Windows\Fonts')
    if (win / 'malgun.ttf').is_file():
        보통 = pymupdf.Font(fontfile=str(win / 'malgun.ttf'))
        굵게 = pymupdf.Font(fontfile=str(win / 'malgunbd.ttf')) if (win / 'malgunbd.ttf').is_file() else 보통
        return 보통, 굵게
    한 = pymupdf.Font(ordering=3)        # 맑은 고딕이 없는 PC(리눅스·클라우드)는 PyMuPDF 의 한글 글꼴
    return 한, 한


def _색(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def 그리기(고른, 낼곳: Path, 제목: str = '노동위원회 위원명단') -> None:
    import pymupdf
    보통, 굵게 = 글꼴들()
    줄수 = len(고른)
    높이 = min(줄높이, (면높이 - 57.0 - 머리줄[1]) / max(줄수, 1))
    doc = pymupdf.open()
    pg = doc.new_page(width=면너비, height=면높이)
    pg.insert_font(fontname='mg', fontbuffer=보통.buffer)
    pg.insert_font(fontname='mgb', fontbuffer=굵게.buffer)
    아래끝 = 머리줄[1] + 높이 * 줄수
    채움 = lambda r, c: pg.draw_rect(pymupdf.Rect(*r), color=None, fill=_색(색값[c]), width=0)
    채움((칸X[0], 머리줄[0], 칸X[-1], 머리줄[1]), '머리채움')
    채움((칸X[0], 윗선[0], 칸X[-1], 윗선[1]), '윗선')
    for x in 칸X[1:-1]:
        채움((x - 0.4, 윗선[1], x + 0.4, 아래끝), '칸선')
    for i in range(줄수 + 1):
        y = 머리줄[1] + 높이 * i
        채움((칸X[0], y - 0.7, 칸X[-1], y), '칸선')

    def 쓰기(칸, 위, 아래, s, font, name, 색, 왼쪽=False):
        너비 = 칸X[칸 + 1] - 칸X[칸] - 2 * 안쪽
        크기 = 글크기
        while 크기 > 최소크기 and font.text_length(s, fontsize=크기) > 너비:
            크기 -= 0.5
        줄 = [s]
        if font.text_length(s, fontsize=크기) > 너비 and ' ' in s:      # 가장 작게 해도 넘치면 가운데에 가까운 빈칸에서 두 줄로
            빈칸 = [i for i, ch in enumerate(s) if ch == ' ']
            k = min(빈칸, key=lambda i: abs(i - len(s) / 2))
            줄 = [s[:k], s[k + 1:]]
        가운데 = (위 + 아래) / 2
        for j, t in enumerate(줄):
            w = font.text_length(t, fontsize=크기)
            x = 칸X[칸] + 안쪽 if 왼쪽 else (칸X[칸] + 칸X[칸 + 1] - w) / 2
            기준 = 가운데 + 크기 * 0.34 + (j - (len(줄) - 1) / 2) * 크기 * 1.2   # 맑은 고딕 한글 글자 몸이 줄 가운데에 오게
            pg.insert_text((x, 기준), t, fontname=name, fontsize=크기, color=_색(색))

    for i, h in enumerate(머리):
        쓰기(i, 윗선[1], 머리줄[1], h, 굵게, 'mgb', 색값['머리글'])
    for r, (a, b, c, d) in enumerate(고른):
        위 = 머리줄[1] + 높이 * r
        아래 = 위 + 높이
        쓰기(0, 위, 아래, a, 보통, 'mg', 색값['본문글'])
        쓰기(1, 위, 아래, b, 굵게, 'mgb', 색값['성명'])
        쓰기(2, 위, 아래, c, 보통, 'mg', 색값['본문글'], 왼쪽=True)
        쓰기(3, 위, 아래, d, 보통, 'mg', 색값['본문글'])
    doc.set_metadata({'title': 제목, 'author': '법무법인 평안', 'creator': '', 'producer': ''})
    try:
        doc.subset_fonts()        # 맑은 고딕을 통째로 넣으면 14MB 넘게 된다
    except Exception as e:  # noqa: BLE001 — fontTools 가 없으면 크게라도 낸다
        print(f'알림: 글꼴 줄이기를 못 했다({type(e).__name__}) — 파일이 크다')
    낼곳.parent.mkdir(parents=True, exist_ok=True)
    doc.save(낼곳, garbage=4, deflate=True)
    doc.close()


def 확인(낼곳: Path, 고른) -> tuple[list[str], Path | None]:
    """낸 PDF 의 글에 칸마다 누리집 값이 있는지, 한 면인지. 문제 목록과 첫 면 그림 경로."""
    import pymupdf
    문제 = []
    with pymupdf.open(낼곳) as d:
        if len(d) != 1:
            문제.append(f'면이 {len(d)}개다(한 면이어야 한다)')
        글 = 붙인글(d[0].get_text('text')) if len(d) else ''
        for 줄 in [머리] + list(고른):
            for 값 in 줄:
                if 붙인글(값) not in 글:
                    문제.append(f"PDF 에 '{값}' 이 없다")
        그림 = None
        if len(d):
            폴더 = Path(tempfile.gettempdir()) / '노동위위원명단'
            폴더.mkdir(parents=True, exist_ok=True)
            그림 = 폴더 / (낼곳.stem + '.png')
            d[0].get_pixmap(dpi=110).save(그림)
    return 문제, 그림


def 표_글(고른, 위원회: str, 날: str) -> str:
    이름 = '중앙노동위원회' if 위원회 == '중앙' else f'{위원회}지방노동위원회'
    줄 = ['| 구분 | 성명 | 현직 | 업무 |', '|---|---|---|---|'] + [f'| {a} | {b} | {c} | {d} |' for a, b, c, d in 고른]
    return '\n'.join(줄) + f'\n\n출처: 중앙노동위원회 누리집 {이름} 위원소개({누리집_면}, {날} 확인)'


def 약칭_읽기(라운드: Path) -> str:
    사건 = 라운드.parent if re.match(r'라운드\d+$', 라운드.name) else 라운드
    return unicodedata.normalize('NFC', 사건.name).split('_')[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='노동위원회 심문회의 위원 명단·프로필 PDF')
    ap.add_argument('라운드', help='4_서면작성/사건/{사건명}/라운드N')
    ap.add_argument('--통지', help='심문일정 통지 PDF(없으면 사건 폴더 참고자료/ 에서 찾는다)')
    ap.add_argument('--위원회', help='중앙·서울·부산·경기·충남·전남·경북·경남·인천·강원·충북·전북·제주·울산')
    ap.add_argument('--공익', nargs='*', help='공익위원 이름(위원장 포함), 통지서 순서대로')
    ap.add_argument('--근로자', nargs='*', help='근로자위원 이름')
    ap.add_argument('--사용자', nargs='*', help='사용자위원 이름')
    ap.add_argument('--약칭', help='파일 이름 앞 괄호(없으면 사건 폴더 이름의 _ 앞)')
    ap.add_argument('--out', help='낼 PDF 경로(없으면 라운드N/출력/({약칭}) 노동위원회 위원명단.pdf)')
    a = ap.parse_args(argv)
    라운드 = Path(a.라운드).resolve()
    try:
        위원 = {'위원회': '', '공익': [], '근로자': [], '사용자': []}
        통지 = Path(a.통지).resolve() if a.통지 else 통지서_찾기(라운드)
        if 통지 and 통지.is_file():
            위원 = 통지서_읽기(통지서_글(통지))
            print(f'통지서: {통지}')
        elif not (a.공익 or a.근로자 or a.사용자):
            raise 멈춤("심문일정 통지 PDF 를 찾지 못했다 — '참고자료/' 에 받아 두거나 --통지, 또는 --위원회·--공익·--근로자·--사용자 로 넘긴다")
        for k in ('위원회', '공익', '근로자', '사용자'):
            v = getattr(a, k)
            if v:
                위원[k] = v
        if not 위원['위원회']:
            raise 멈춤('노동위원회 이름을 통지서에서 읽지 못했다 — --위원회 로 넘긴다')
        print(f"위원회: {위원['위원회']} · 공익위원 {', '.join(위원['공익']) or '-'} · 근로자위원 {', '.join(위원['근로자']) or '-'} · 사용자위원 {', '.join(위원['사용자']) or '-'}")
        줄들, 수 = 목록_읽기(목록_받기(위원['위원회']))
        if not 줄들:
            raise 멈춤('누리집 위원소개 표를 읽지 못했다(누리집 구조가 바뀌었을 수 있다) — 인앱 브라우저로 위원소개 면을 열어 확인한다')
        if 수 is not None and 수 != len(줄들):
            print(f'알림: 누리집이 적은 위원수 {수}명과 읽은 줄 {len(줄들)}개가 다르다')
        고른 = 고르기(줄들, 위원)
        낼곳 = Path(a.out).resolve() if a.out else 라운드 / '출력' / f'({a.약칭 or 약칭_읽기(라운드)}) 노동위원회 위원명단.pdf'
        있었음 = 낼곳.exists()
        그리기(고른, 낼곳)
        문제, 그림 = 확인(낼곳, 고른)
        if 문제:
            raise 멈춤('만든 PDF 확인: ' + '; '.join(문제))
        print(f"{'덮어씀' if 있었음 else '저장'}: {낼곳} ({낼곳.stat().st_size:,}바이트, 1면)")
        print(f'확인 그림: {그림}')
        print()
        오늘 = _dt.date.today()
        print(표_글(고른, 위원['위원회'], f'{오늘.year}. {오늘.month}. {오늘.day}.'))
        return 0
    except 멈춤 as e:
        print(f'오류: {e}')
        return 1
    except OSError as e:          # 누리집에 닿지 못함
        print(f'오류: 누리집에서 위원소개를 받지 못했다({e}) — 인앱 브라우저로 위원소개 면을 열어 확인한다')
        return 1


if __name__ == '__main__':
    sys.exit(main())
