"""넘기기 전 마지막 관문. 서면·검토의견 하나에 문체·판례·증거(파악·인용·편철) 검사를 모두 돌리고, 빠뜨린 검사까지 잡는다.

    python -B 공통/scripts/final_check.py "4_서면작성/사건/{사건명}" [--라운드 N] [--대상 "<서면초안.md 또는 담당자 저장본 docx, 리서치·검토 메모 원고>"]
    python -B 공통/scripts/final_check.py "1_검토의견/사건/{의뢰인}_{검토내용}" [--대상 "<검토의견서 docx 또는 회신초안.md>"]
    python -B 공통/scripts/final_check.py --최근 24 --out "<보고.md>"   # 24시간 안에 손댄 사건의 고친 라운드마다. 화면에는 검사별 모음, 파일에 사건별 전문(`/하자보완`)

검사마다 '통과'·'막힘'·'해당 없음'을 적고, 막힘이 하나라도 있으면 종료 코드 1 이다. 각 검사는 그 스크립트를 그대로 부른다
(규칙을 두 벌로 두지 않는다). 이 관문이 보는 것은 검사를 했는지와 판정 칸이 다 찼는지이다. 판정이 맞는지는 작성 세션이
원문을 읽고 정한다(`공통/자체검토.md` 4-1절). 관문은 사건 폴더의 파일을 고치지 않는다.

서면(라운드의 출력/서면초안.md. 상병별로 나눈 심사청구처럼 서면이 여럿이면 서면초안_{이름}.md 마다, 표는 인용대조표*{이름}*.md)
  문체           style_check.py 위반 0
  호증 번호      citation_check.py 위반 0
  판례 대조      인용이 있으면 작업/인용대조표.md 가 있고 cite_check.py 불일치 0
  판례 검색 기록 LBOX 목록(작업/LBOX_목록.tsv)·법제처 목록·작업/검색기록.md 가 있다(찾은 것을 남겼는가)
  찾은 판례 다시 훑기  작업/수확목록_재확인*.md 의 낱말로 harvest_titles.py scan 을 다시 돌린다(보고서에 적은 처리를 잇는다). 걸린 줄은 원고·대조표·검색기록에
                 번호가 있거나, 재확인 보고서의 '처리' 칸에 줄마다 처리를 적었어야 한다(사안이 전혀 다른 줄도 묶지 않는다, `/검토의견` 4-2단계).
                 번호가 없는 줄과 보고서 뒤에 새로 걸린 줄도 처리 칸이 비면 막는다
  대조표 칸      본문 인용 줄마다 자리·주문·결론·다른 사유·전제·확정·원문이 찼고, 판결이 아닌 자료(판정·재결·행정해석)는 원문 파일이 있으며,
                 미확정·확인 못한 판결은 7일 안에 다시 본 날짜가 있다(미확정 줄은 '참고'로 따로 보인다)
  판결 원문      본문 인용 판결이 있으면 작업/판결원문_열람대조.md(법제처 본문·LBOX 화면 글을 열람해 맞댄 기록)의 '사람 판정' 표가
                 본문 인용 줄마다 판단 부분인지·방향·사안 비교까지 찼고, '주의'(앞 글에 주장·원심·인정사실) 줄은 비고가 있다.
                 판결문 PDF 를 받아 둔 폴더(참고자료/인용판결_PDF)가 있으면 예전대로 cite_pdf_check.py 문제 0 과 판결원문_PDF대조.md 의 표를 본다
                 (2026. 11. 6. 담당자 지시로 대조용 PDF 는 받지 않는다. 그래서 PDF 가 없는 줄·상급심은 열람 대조 기록으로 받는다)
  상급심 처리    산출물에 적은 상급심('확정' 칸의 대법원 판결. 심리불속행·문서 없음 표기가 없는 것)은 열람 대조 기록의 '상급심의 처리' 절에 번호가 있다
  증거 인용      증거 인용이 있으면 작업/증거인용검토/ (서면초안_{이름}.md 는 증거인용검토_{이름}/) 의 review.json 이 초안의 지금 인용과 같고, 대조한 뒤
                 호증 파일이 바뀌지 않았고(review.json 의 파일 해시), notes.json 에 인용마다 판정이 있다
  증거 파악      evidence_read.py check — 모든 호증의 전 면 읽기 기록이 찼고 파일이 그 뒤 바뀌지 않았고, 확인표와 세션 기록으로 잰 실측이 있다
  빠진 문구      evidence_words.py --확인 — 쟁점 낱말 대조표가 있고, 서면이 인용하지 않은 면마다 '판단'이 있다
                 (서면을 나눈 라운드는 두 검사 모두 `--서면 {이름}` 으로 그 서면의 호증, 번호에 서면 이름이 없는 공통 호증, 그 서면이 가리키거나
                 어느 서면도 가리키지 않는 자료만 본다. 다른 서면의 몫은 그 서면의 관문이 본다)
  증거 나누기    우리증거/ 에 상대방 서면·서증·법원 문서가 섞여 있지 않다(evidence_sort.py --확인. 섞여 있으면 아래 '상대 서면'이 상대방 서면을 찾지 못한다)
  상대 서면      상대증거/ 에 상대방 서면이 있으면 작업/상대주장_맞대기.md 가 있고 판정 칸이 다 찼고 초안보다 새것이다. 초안이 더 새것이어도
                 표 머리에 적은 '초안 본문:' 해시(`--본문해시`)가 지금 본문과 같으면 하단만 고친 것이다
  의뢰인 주장    작업/의뢰인주장_대조.md 가 있으면 '반영' 칸이 다 찼고, 인정 표의 '본문 문장' 칸에 따옴표로 옮긴 문장이 지금 초안 본문에
                 그대로 있다(고친 판에서 7-0단계를 다시 했는가)
  DOCX           9-2단계(`--대상 docx`)와 밤 점검에서, 병합한 서면 docx 가 서면초안.md 보다 낡지 않았다(8-1단계는 병합 전이라 보지 않는다).
                 초안이 더 새것이어도 본문(문단·제목·표·각주, 지운 문단까지)이 병합본과 같으면 하단 메모만 고친 것이다.
                 서면을 나눈 라운드의 docx 는 파일 이름의 서면 이름이나 `출력/제출/{이름}/` 자리로 짝 초안을 고르고, 가리지 못하면 막는다
  서증 압축      출력/제출/ 에 서증 압축파일이 있으면 evidence_zip.py --확인
  제출본         출력/제출/ 의 `_제출본` docx·pdf 가 넘길 판(DOCX 검사의 병합본)과 바이트까지 같다. 옛 이름 사본만 있으면 참고(4_서면작성/CLAUDE.md 2-1절)
  예상 질의답변  출력/ 에 심문회의 예상 질의답변 docx 가 있으면 qna_check.py·style_check.py·작업/예상질의_인용대조표.md 의 cite_check.py(`/예상질의` 5절)
서면 사건의 다른 인용 산출물(리서치 문서·검토 메모·회신 메일 초안. `--대상 "<그 원고>"`, 밤 점검은 그날 대조표나 산출물을 고친 것)
  서면 초안의 것이 아닌 인용대조표*.md(라운드·사건의 작업/)가 이름의 `_{산출물}` 이나 첫 줄 '# 인용 대조표 — {산출물 이름}' 으로 가리키는 원고를
  아래 검토의견과 같이 본다(판례 대조·대조표 칸·판례 검색 기록·다시 훑기·판결 원문·상급심 처리·문체). 원고를 찾지 못한 표는 '참고'로 알린다
검토의견(사건 폴더 맨 위의 검토의견서 docx(판 이름이 가장 높은 것. 검토용 변경 표시본은 빼고)·회신초안.md·간이안.md 가운데 가장 새것.
        이들이 없으면 `{사건}-…md` 처럼 다른 원고(의견서·내용증명·추가 질의 회신). 밤 점검은 그날 고친 다른 원고를
        `작업/인용대조표_{산출물 이름}.md` 가 있으면 따로 보고, 없으면 '참고'로 알린다)
  판례 대조·판결 원문   위와 같다(작업/인용대조표.md — 간이안은 _간이안, 다른 원고는 _{산출물 이름} 표가 있으면 그것, 작업/판결원문_열람대조.md,
                 PDF 를 받아 두었으면 작업/인용판결_PDF)
  자료 파악      evidence_read.py check --자료 — 사건 폴더의 의뢰인 자료마다 전 면 읽기 기록
  문체           루트 CLAUDE.md 가 쓰지 말라고 한 낙관 표현과 '적다'(→ 기재하다). 보완 메모는 보지 않는다
  송부판(_최종)  사건 폴더 맨 위의 `_최종.docx` 마다 변경 추적·메모가 없고 작성자·마지막 수정자가 '법무법인 평안'이며 같은 이름의 PDF 가 낡지 않았다(7절)
계산(6_손해배상계산/사건/{사건명})
  자료 파악      evidence_read.py check --자료 — 받은 자료마다 전 면 읽기 기록(`/손배계산` 2-1·3-1절)

2026. 11. 2. 담당 노무사 "노동사건자동화는 결국 문체, 증거, 판례 세 가지에 어떠한 하자도 없어야", "모든 자동화 시스템에 최종 재검토
완결성 100%로". GGM 사 제6호증 3면을 첫 면만 읽어 놓친 일이 인용 대조·맞대기·통독을 모두 지나갔다. 그 검사들은 서면에 쓴 것이
원문과 맞는지만 보고, 서면에 빠진 것(읽지 않은 면, 판정하지 않은 줄)은 보지 않았다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
S4 = ROOT / '4_서면작성' / 'scripts'
SC = ROOT / '공통' / 'scripts'
sys.path.insert(0, str(SC))
import cite_check                 # noqa: E402
import system as _system          # noqa: E402  사건번호 정규식은 한 벌만 둔다

CASE_NO = re.compile(_system.CASE_NUMBER)
EVIDENCE_REF = re.compile(_system.EVIDENCE_NUMBER)     # '갑 제1 내지 5호증'만 적은 서면도 증거 인용이 있다(2026. 11. 3.)
낙관 = ('다툴 실익이 충분', '인정될 가능성이 높', '유력하', '승소 가능성이 높', '이길 가능성이 높')
적다 = re.compile(r'(?<![가-힣])적(?:(?:혀|어)\s*있|었|은\s*바|고\s*있)')       # '목적은 바람직' 같은 말은 아니다
# 병합한 서면의 이름(4_서면작성/CLAUDE.md 3-1절). 같은 이름 꼴의 부속 문서(예상 질의답변 등)는 서면이 아니다
병합본_이름 = re.compile(r'(_초안|_Rev_\d+|_최종|^최종서면|_\d+차 수정안(?:\(클린\))?)\.docx$')
부속_이름 = re.compile(r'예상\s*질의|질의답변|요지|요약|별첨|목록|확인서|내용증명|통지서|연기 요청|대응안|문답')
번호_꼴 = r'(?:\d{1,2}\.|[가-하]\.|\(\d{1,2}\)|\([가-하]\)|\d{1,2}\)|[가-하]\))'       # 제목 번호는 docx 에서 자동 번호이다
_모듈 = {}


def 증거검토():
    """evidence_cite_review 를 한 번만 읽는다. 호증 열쇠·초안 목록·증거 인용 폴더의 규칙을 두 벌로 두지 않는다."""
    if 'ecr' not in _모듈:
        import importlib.util
        spec = importlib.util.spec_from_file_location('evidence_cite_review', S4 / 'evidence_cite_review.py')
        _모듈['ecr'] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_모듈['ecr'])
    return _모듈['ecr']


def RUN(args: list) -> tuple:
    """검사 스크립트를 부른다. (종료 코드, 출력)"""
    try:
        r = subprocess.run([sys.executable, '-B'] + [str(a) for a in args], capture_output=True, timeout=3600,
                           cwd=str(ROOT), env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    except subprocess.TimeoutExpired:
        return 1, '시간 초과'
    out = (r.stdout or b'').decode('utf-8', 'replace') + (r.stderr or b'').decode('utf-8', 'replace')
    return r.returncode, out


def 요약(out: str) -> str:
    """검사 출력에서 막힌 까닭만 남긴다. 맞은 줄('… — 일치', '… — 원문: 보관함 확인')은 뺀다."""
    줄 = [l.rstrip() for l in out.strip().splitlines() if l.strip()]
    return '\n'.join([l for l in 줄 if not re.search(r'— (?:일치|원문: [^/]*)$', l)][:40])


class 결과:
    def __init__(self):
        self.줄 = []
        self.대상 = None        # 본 산출물(보고 머리에 적는다)
        self.대상시각 = None
        self.넘긴판 = False     # 병합본·제출 묶음이 이미 있어 넘긴 판일 수 있다

    def add(self, 이름, 상태, 말=''):
        self.줄.append((이름, 상태, 말.strip()))

    def run(self, 이름, args, 통과말='', 없음말=None):
        """종료 코드 0 은 통과, 없음말을 주면 2(대상 없음)는 해당 없음, 그 밖은 막힘. 통과말이 함수이면 검사 출력으로 말을 짓는다."""
        code, out = RUN(args)
        if code == 2 and 없음말 is not None:
            self.add(이름, '해당 없음', 없음말)
        elif code == 0:
            self.add(이름, '통과', 통과말(out) if callable(통과말) else 통과말)
        else:
            self.add(이름, '막힘', 요약(out))
        return code

    @property
    def 막힘(self):
        return [r for r in self.줄 if r[1] == '막힘']


# ---------------------------------------------------------------- 표 읽기
def 표들(text: str) -> list:
    """마크다운 표마다 (머리 칸, [줄 칸...])."""
    out, head, rows = [], None, []
    for line in text.splitlines() + ['']:
        s = line.strip()
        if s.startswith('|'):
            cells = [c.strip() for c in s.strip('|').split('|')]
            if head is None:
                head = cells
            elif not all(re.fullmatch(r':?-+:?', c) for c in cells if c):
                rows.append(cells + [''] * (len(head) - len(cells)))
        else:
            if head is not None:
                out.append((head, rows))
            head, rows = None, []
    return out


def 절_글(text: str, 머리: str) -> str:
    k = text.find('\n## ' + 머리)
    if k < 0:
        return ''
    rest = text[k + 1:]
    m = re.search(r'\n## ', rest[3:])
    return rest[:m.start() + 3] if m else rest


def 빈_판정(path: Path, 칸말: tuple) -> tuple:
    """표에서 판정 칸(머리에 칸말 가운데 하나가 든 칸, 없으면 마지막 칸)이 빈 줄 수와 전체 줄 수."""
    빈, 전체 = 0, 0
    for head, rows in 표들(path.read_text(encoding='utf-8')):
        idx = next((i for i, h in enumerate(head) if any(w in h for w in 칸말)), len(head) - 1)
        for r in rows:
            if not any(c for c in r):
                continue
            전체 += 1
            빈 += not r[idx].strip()
    return 빈, 전체


def 본문_해시(초안: Path) -> str:
    """초안 본문(서면 MD 는 '---' 위, 공백은 뺀다)의 해시 앞 10자리. 맞대기 표 머리에 '초안 본문: …'으로 적어 두면 그 뒤 하단만 고친 초안을 알아본다.
    2026. 11. 4. `/하자보완`: 맞대기 검사가 초안의 수정 시각만 보아 하단 메모만 고쳐도 막았다(11. 3. 남은 하자). 표의 '우리 문장'은 줄여 적어
    글자로 맞댈 수 없으므로 본문 전체를 해시로 맞댄다."""
    본문 = cite_check.body_and_bottom(str(초안), cite_check.read_target(str(초안)))[0]
    return hashlib.sha1(cite_check.norm(본문).encode('utf-8')).hexdigest()[:10]


def 인정_문장_없음(대조: Path, 산출물들: list) -> tuple:
    """(의뢰인 인정 표의 '본문 문장' 칸에 따옴표로 옮긴 문장 가운데 지금 산출물 본문(서면 MD 는 '---' 위)에 없는 것, 맞댄 문장 수).
    2026. 11. 4. `/하자보완`: 10. 31. 에 만든 인정 표가 11. 2.·3. 고친 판의 바뀐 인정 문장(인정 범위가 넓어진 문장 포함)을 담지 않았는데도
    '반영' 칸이 찼다는 것만 보고 통과하였다(GGM 답변서(2) Rev_2). 따옴표 없이 자리만 적은 줄은 맞댈 글이 없어 넘긴다."""
    본문 = ''.join(cite_check.norm(cite_check.body_and_bottom(str(p), cite_check.read_target(str(p)))[0]) for p in 산출물들 if p.is_file())
    없음, 수 = [], 0
    for head, rows in 표들(대조.read_text(encoding='utf-8')):
        i = next((k for k, h in enumerate(head) if '본문 문장' in h), None)
        for r in rows if i is not None else ():
            for q in re.findall(r'["“]([^"”]{6,})["”]', r[i]):
                수 += 1
                if cite_check.in_order(본문, cite_check.pieces(q)):
                    없음.append(q)
    return 없음, 수


def 본문_줄(table: Path) -> list:
    """대조표의 본문 인용 줄(번호 칸에 '참고'가 없고 뺀 줄이 아니며, 서면 대조표이면 하단 목록 번호 ①②③ 으로 시작하지 않는 줄)."""
    return [r for r in cite_check.table_rows(str(table)) if cite_check.is_body(r, str(table))]


def 자리_머리(이름: str) -> str:
    """줄 이름의 번호 부분. '2.가.(1) 각주' → '2.가.(1)', '3. 라.(2줄)' → '3.라.', '7(재인용)' → '7', '4-2 (나.(4))' → '4-2'."""
    m = re.match(r'(?:[①-⑳]|\d+(?:-\d+)?\.?|[가-하]\.|\(\d+\)|\([가-하]\)|\s)+', 이름)
    return re.sub(r'\s', '', m.group(0)) if m else ''


def 같은_자리(줄: str, 표줄: str) -> bool:
    """'사람 판정' 표의 줄 이름이 이 인용 줄을 가리키는가. 표는 줄을 묶거나 줄여 적는다('2.가.(3), 4.가.(3줄)', '2.가.(1) 각주·둘째(2줄)', '7'과 '7(재인용)')."""
    머리 = 자리_머리(줄)
    if not 머리:
        return bool(줄) and (줄 in 표줄 or 표줄 in 줄)
    for 토막 in 표줄.split(','):
        표머리 = 자리_머리(토막.strip())
        if 표머리 and (머리 == 표머리 or re.match(re.escape(표머리) + r'(?![\d-])', 머리) or re.match(re.escape(머리) + r'(?![\d-])', 표머리)):
            return True
    return False


def 사람판정_빈(table: Path, report: Path, 만=None, 빼고=frozenset()) -> list:
    """판결 본문 인용 줄(cite_pdf_check 가 보는 줄)마다 '사람 판정' 표에 판단 부분인지·방향·사안 비교가 있는지,
    'PDF 의 자리'에 '주의'(앞 글에 주장·원심·인정사실 등)가 붙은 줄은 비고가 있는지. 빠진 줄을 '줄(빠진 칸)'로 돌려준다.
    같은 이름의 표 줄이 없으면 같은 판결이면서 번호가 겹치는 표 줄로 본다(묶어 적은 줄). 다른 목의 판정으로 이 줄을 통과시키지 않고,
    걸리는 표 줄이 여럿이면 하나라도 비었을 때 막는다. 2026. 11. 3. 같은 판결의 표 줄 하나만 차면 그 판결의 다른 인용 줄까지 통과하였다.
    만·빼고는 (줄 이름, 사건 표시) 묶음이다. PDF 를 받아 둔 사건에서 PDF 가 없는 줄은 열람 대조 기록에서, 나머지는 PDF 대조 보고서에서 본다."""
    want = [(r.get('번호', '').strip(), cite_check.cases(r.get('사건 표시', ''))) for r in 본문_줄(table) if '법원' in r.get('사건 표시', '')
            and (만 is None or (r.get('번호', '').strip(), r.get('사건 표시', '')) in 만)
            and (r.get('번호', '').strip(), r.get('사건 표시', '')) not in 빼고]
    if not want:
        return []
    if not report.is_file():
        return [f'{n}(표 없음)' for n, _ in want]
    표줄 = []          # (줄 이름, 그 줄의 판결 번호, 빠진 칸)
    for head, rs in 표들(절_글(report.read_text(encoding='utf-8'), '사람 판정')):
        def 칸(말):
            return next((i for i, h in enumerate(head) if 말 in h), None)
        i줄 = next((i for i, h in enumerate(head) if h in ('줄', '번호') or h.startswith('줄')), 0)
        i판결 = 칸('판결')
        칸들 = {'판단 부분인지': 칸('판단'), '방향': 칸('방향'), '사안 비교': 칸('사안')}
        i자리, i비고 = 칸('자리'), 칸('비고')
        for r in rs:
            빠짐 = [이름 for 이름, i in 칸들.items() if i is None or not r[i].strip()]
            if i자리 is not None and '주의' in r[i자리] and (i비고 is None or not r[i비고].strip()):
                빠짐.append('비고(주의 줄)')
            표줄.append((r[i줄].strip(), cite_check.cases(r[i판결]) if i판결 is not None else set(), 빠짐))
    이름_판결 = {}
    for n, 번호들 in want:
        이름_판결.setdefault(n, set()).add(frozenset(번호들))
    out = []
    for n, 번호들 in want:
        # 표 줄의 '판결' 칸이 비었으면 이름이 꼭 같고 그 이름으로 인용한 판결이 하나일 때만 그 줄로 본다.
        # 2026. 11. 3. 점검: 판결 칸이 빈 표 줄 하나가 번호가 겹치는 다른 판결의 인용 줄까지 통과시켰다
        def 같은판결(x, 느슨):
            return bool(x[1] & 번호들) if x[1] and 번호들 else 느슨
        후보 = ([x for x in 표줄 if x[0] == n and 같은판결(x, len(이름_판결[n]) == 1)]
              or [x for x in 표줄 if 같은판결(x, False) and 같은_자리(n, x[0])])
        빠짐 = max((x[2] for x in 후보), key=len) if 후보 else ['줄 없음']
        if 빠짐:
            out.append(f"{n}({', '.join(빠짐)})")
    return out


def 상급심_절(열람: Path) -> str:
    """열람 대조 기록에서 머리에 '상급심'이 든 절(본보기의 '## 상급심의 처리')의 글을 공백·따옴표를 맞추어 돌려준다."""
    if not 열람.is_file():
        return ''
    text = 열람.read_text(encoding='utf-8', errors='replace')
    out = []
    for m in re.finditer(r'(?m)^##+ [^\n]*상급심[^\n]*$', text):
        rest = text[m.end():]
        n = re.search(r'(?m)^## ', rest)
        out.append(rest[:n.start()] if n else rest)
    return cite_check.norm('\n'.join(out))


def 상급심_빠짐(table: Path, 산출물글: str, 열람: Path, 볼것=None, 줄들=frozenset()) -> tuple:
    """([빠진 '{줄} 대법원 {번호}'], 본 상급심 수). 본문 인용 줄의 '확정' 칸에 적은 대법원 상급심 가운데 산출물에 번호가 나오고
    (서면처럼 상급심을 적지 않는 글은 보지 않는다) 칸에 '심리불속행'·'문서 없음'이 없는 것은 판결문을 열람해 처리를 보았는지
    열람 대조 기록의 '상급심' 절에 그 번호가 있어야 한다(`공통/자체검토.md` 3절·4-1절 4.). 볼것(번호)을 주면 그 번호와,
    줄들((줄 이름, 사건 표시))에 든 줄의 상급심만 본다(PDF 대조가 보지 못한 것. PDF 가 없는 줄은 그 줄의 상급심도 PDF 대조가 보지 않는다).
    2026. 11. 7. `/하자보완`: 11. 6. 판결문 PDF 대신 화면 열람으로 맞대게 된 뒤, 관문이 상급심 처리를 판결문으로 보았는지 더는 보지 않았다
    (PDF 대조의 상급심 검사가 하던 일이다. 2026. 11. 2. 이케아 각주 16번 '판결로 확정'이 실제로는 심리불속행 기각이었다)."""
    t = cite_check.norm(산출물글)
    절 = 상급심_절(열람)
    빠짐, 본 = [], 0
    for r in 본문_줄(table):
        if '법원' not in r.get('사건 표시', ''):
            continue
        own = cite_check.cases(r.get('사건 표시', ''))
        cell = r.get('확정', '')
        줄 = (r.get('번호', '').strip(), r.get('사건 표시', ''))
        for c, says in cite_check.upper_courts(cell):
            if c in own or c not in t or (볼것 is not None and c not in 볼것 and 줄 not in 줄들):
                continue
            if says or re.search(r'%s.{0,40}문서 없음' % re.escape(c), cell):
                continue
            본 += 1
            if c not in 절:
                빠짐.append(f"{r.get('번호', '').strip()} 대법원 {c}")
    return list(dict.fromkeys(빠짐)), 본


def 날짜들(cell: str) -> list:
    out = []
    for y, m, d in re.findall(r'(20\d{2})\s*[.\-]\s*(\d{1,2})\s*[.\-]\s*(\d{1,2})', cell):
        try:
            out.append(dt.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    return out


def 대조표_칸(table: Path, 오늘=None) -> tuple:
    """본문 인용 줄의 칸이 다 찼는지(실존·해석·확정을 뒷받침하는 칸). (막힘 말들, 미확정 줄들)

    - 자리·주문·결론·다른 사유·전제·확정·원문 칸이 비지 않았다(공통/자체검토.md 3절)
    - 판결이 아닌 자료(결정례·재결·행정해석)는 원문 파일이 있다. '화면 확인'만으로는 실존과 문언을 다시 맞댈 수 없다
      (판결은 판결문 PDF 를 cite_pdf_check.py 가 맞댄다)
    - 확정 칸이 미확정·확인 못함이면 넘기기 전 7일 안에 다시 본 날짜가 있다"""
    오늘 = 오늘 or dt.date.today()
    막, 미확정 = [], []
    for r in 본문_줄(table):
        n = r.get('번호', '').strip() or r.get('사건 표시', '')[:20]
        빈 = [h for h in ('자리', '주문·결론', '다른 사유·전제', '확정', '원문') if not r.get(h, '').strip()]
        if 빈:
            막.append(f"{n}: {'·'.join(빈)} 칸이 비었다")
        if '법원' not in r.get('사건 표시', '') and not cite_check.source_files(r.get('원문', ''), table):
            막.append(f"{n}: 원문 파일이 없다(법제처 본문이나 화면 글을 파일로 받아 '원문' 칸에 경로를 적는다)")
        확정 = r.get('확정', '')
        if re.search(r'미확정|미확인|확인 못|모름|계속 중|상고 중|항소 중', 확정):
            본날 = max(날짜들(확정), default=None)
            미확정.append(f"{n} {r.get('사건 표시', '')[:40]} — {확정[:40]}")
            if not 본날 or (오늘 - 본날).days > 7:
                막.append(f"{n}: 확정되지 않았거나 확인하지 못한 판결은 넘기기 전에 다시 보고 본 날짜를 적는다(마지막 {본날 or '날짜 없음'})")
    return 막, 미확정


def 까닭별로(말들: list) -> str:
    """'줄: 까닭' 꼴의 막힘을 까닭마다 묶는다. 같은 까닭을 줄마다 되풀이하면 표가 길어지고 뒤의 다른 까닭이 잘린다."""
    묶음 = {}
    for 말 in 말들:
        줄, _, 까닭 = 말.partition(': ')
        묶음.setdefault(까닭, []).append(줄)
    return '; '.join(f"{까닭} — {', '.join(dict.fromkeys(줄들))}" for 까닭, 줄들 in 묶음.items())


def 인용_있나(text: str) -> bool:
    return bool(CASE_NO.search(text))


def 글(p: Path) -> str:
    """산출물의 글. docx 는 review_text.py 로 본문과 각주를 함께 뽑는다(판례 번호가 각주에 있다)."""
    if p.suffix.lower() == '.docx':
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / '글.md'
            RUN([SC / 'review_text.py', p, '--out', out])
            return out.read_text(encoding='utf-8', errors='replace') if out.is_file() else ''
    return p.read_text(encoding='utf-8', errors='replace')


def 라운드_번호(p: Path) -> int:
    return int(re.sub(r'\D', '', p.name) or 0)


def 앞_라운드(폴더: Path) -> list:
    """서면의 라운드 폴더이면 앞선 라운드들. 뒤 라운드의 판례는 앞 라운드 검색에서 나오기도 한다."""
    if not re.fullmatch(r'라운드\d+', 폴더.name):
        return []
    return [p for p in 폴더.parent.glob('라운드*') if p.is_dir() and 라운드_번호(p) < 라운드_번호(폴더)]


def 기록에_없는_줄(글: str) -> list:
    """다시 훑은 보고서의 '기록에 없는 줄'(기록에 번호가 없거나 번호를 알 수 없는 줄). [(번호나 제목, 처리)].
    '처리' 칸은 harvest_titles.py 가 앞선 재확인 보고서에서 이어 적는다('같음'·'상동'만 적은 칸은 잇지 않는다)."""
    out = []
    for head, rows in 표들(절_글(글, '기록에 없는 줄')):
        i = next((k for k, h in enumerate(head) if h == '처리'), None)
        for r in rows:
            if len(r) > 6 and r[6] in ('없음', '번호 없음'):
                out.append((r[1] or r[4][:20], r[i].strip() if i is not None else ''))
    return out


# ---------------------------------------------------------------- 판례(두 계열 같다)
def 검색_완결(res: 결과, 폴더: Path):
    """찾지 않은 판례: 검색 기록(LBOX·법제처 목록, 검색기록)이 남았고, 받아 둔 목록에서 사안 고유어가 걸린 줄을 모두 가렸는가.
    기록(원고·대조표·검색기록)에 번호가 없는 줄과 번호를 알 수 없는 줄은 재확인 보고서의 '처리' 칸에 줄마다 무엇을 하였는지 적어야 지나간다.
    2026. 11. 3. 점검: 묶어 적은 한 문장('나머지는 사안이 다름')으로 기록에 없는 줄 161건을 가린 것으로 보았다. 보고서 뒤에 새로 걸린 줄은
    처리 칸이 비어 막힌다."""
    작업 = 폴더 / '작업'
    폴더들 = [폴더] + 앞_라운드(폴더)
    없는것 = [이름 for 이름, 있나 in (('작업/LBOX_목록.tsv', any(x for d in 폴더들 for x in d.rglob('LBOX_목록*.tsv'))),
                                    ('법제처_목록.json', any(x for d in 폴더들 for x in d.rglob('법제처_목록.json'))),
                                    ('검색기록.md', any((d / '작업' / '검색기록.md').is_file() or (d / '검색기록.md').is_file() for d in 폴더들)))
             if not 있나]
    res.add('판례 검색 기록', '막힘' if 없는것 else '통과',
            ('없다: ' + ', '.join(없는것) + ' (`lbox-검색` 4·7항, `법제처-검색`)') if 없는것 else 'LBOX·법제처 목록과 검색기록 있음')
    재확인들 = sorted(작업.glob('수확목록_재확인*.md'))
    if not 재확인들:
        res.add('찾은 판례 다시 훑기', '막힘', f"수확 목록 재확인(harvest_titles.py scan)을 하지 않았다: {작업 / '수확목록_재확인.md'}")
        return
    옛글 = [p.read_text(encoding='utf-8') for p in 재확인들]
    낱말 = []
    for 글자 in 옛글:
        m = re.search(r'^낱말:[ \t]*(.+)$', 글자, re.M)
        낱말 += [w.strip() for w in m.group(1).split(', ') if w.strip()] if m else []
    낱말 = list(dict.fromkeys(낱말))
    if not 낱말:
        res.add('찾은 판례 다시 훑기', '막힘', f'재확인 보고서에 낱말이 없다: {재확인들[0]}')
        return
    머리 = re.match(r'# 수확 목록 제목 다시 훑기 — (.+)', 옛글[0])          # 앞 라운드 목록을 훑은 보고서이면 그 라운드를 다시 훑는다
    훑을곳 = 폴더.parent / 머리.group(1).strip() if 머리 and (폴더.parent / 머리.group(1).strip()).is_dir() else 폴더
    with tempfile.TemporaryDirectory() as d:          # 같은 낱말로 지금 기록과 다시 맞댄다(LBOX 에는 요청하지 않는다)
        out = Path(d) / '재확인.md'
        RUN([SC / 'harvest_titles.py', 'scan', 훑을곳, '--낱말', *낱말, '--out', out, '--잇기', *재확인들])
        t = out.read_text(encoding='utf-8') if out.is_file() else ''
    n = re.search(r'없음 (\d+)건', t)
    빠짐 = int(n.group(1)) if n else -1
    목록 = re.search(r'같은 줄 합친 뒤 (\d+)줄', t)
    if 빠짐 < 0:
        res.add('찾은 판례 다시 훑기', '막힘', '다시 훑기를 돌리지 못했다')
    elif 목록 and int(목록.group(1)) == 0:
        res.add('찾은 판례 다시 훑기', '막힘', f'다시 훑을 법제처·LBOX 목록이 없다: {훑을곳}')
    else:
        미기록 = 기록에_없는_줄(t)
        빈 = [n for n, h in 미기록 if not h]
        if 빈:
            res.add('찾은 판례 다시 훑기', '막힘', f"기록에 없는 줄 {len(미기록)}건 가운데 '처리' 칸이 빈 줄 {len(빈)}건: " + ', '.join(빈[:15]) +
                    (' 외' if len(빈) > 15 else '') + " — 본문을 읽고 반영하거나 유사 사례 표에 미반영 이유를 적고, 사안이 전혀 다른 줄도 묶지 않고 "
                    f"그 줄의 '처리' 칸에 다른 점을 적는다(`harvest_titles.py scan` 을 같은 --out `{재확인들[0].name}` 으로 다시 돌리면 적어 둔 처리는 이어진다)")
        elif not 미기록:
            res.add('찾은 판례 다시 훑기', '통과', f"낱말 {', '.join(낱말)} — 걸린 줄 모두 기록에 있음")
        else:
            res.add('찾은 판례 다시 훑기', '통과', f'기록에 없는 {len(미기록)}줄은 재확인 보고서에 줄마다 처리를 적음')


def 판례(res: 결과, 대상: Path, table: Path, pdfdir: Path, 폴더: Path, report: Path | None = None):
    text = 글(대상)
    if not table.is_file():
        if 인용_있나(text):
            res.add('판례 대조', '막힘', f'산출물에 사건번호가 있는데 대조표가 없다: {table}')
        else:
            res.add('판례 대조', '해당 없음', '사건번호 없음')
        return
    res.run('판례 대조', [SC / 'cite_check.py', table, '--target', 대상], '불일치 0')
    막, 미확정 = 대조표_칸(table)
    res.add('대조표 칸(실존·해석·확정)', '막힘' if 막 else '통과', 까닭별로(막) if 막 else '본문 인용 줄의 칸이 모두 찼다')
    if 미확정:
        res.add('미확정·확인 못한 판결', '참고', '보고에 적고 제출 전에 다시 본다: ' + '; '.join(미확정[:8]))
    검색_완결(res, 폴더)
    본문줄 = [r for r in 본문_줄(table) if '법원' in r.get('사건 표시', '')]
    if not 본문줄:
        res.add('판결문 PDF', '해당 없음', '본문 인용 판결 없음')
        return
    report = report or table.parent / '판결원문_PDF대조.md'
    열람 = report.with_name(report.name.replace('PDF대조', '열람대조'))
    if not pdfdir.is_dir():
        # 2026. 11. 6. 담당자 지시: 판결문 PDF 를 내려받지 않고 법제처 본문·LBOX 화면 글을 열람해 맞댄다(공통/자체검토.md 4-1절 4.).
        # 그 기록은 판결원문_열람대조*.md 의 '사람 판정' 표와 '상급심의 처리' 절이다. PDF 폴더가 있으면 아래에서 cite_pdf_check.py 로 본다.
        if not 열람.is_file():
            res.add('판결 원문 대조', '막힘', f'판결 원문 열람 대조 기록이 없다 — 법제처 본문·LBOX 화면 글로 맞대고 {열람} 의 사람 판정 표를 채운다'
                                          '(`공통/자체검토.md` 4-1절 4.)')
            return
        빈 = 사람판정_빈(table, 열람)
        res.add('판결 판단 부분·방향·사안 비교', '막힘' if 빈 else '통과',
                (f"'사람 판정' 표에서 빈 줄: {', '.join(빈[:12])} ({열람})") if 빈 else f'{len(본문줄)}줄 판정(원문 열람 대조 {열람.name})')
        빠짐, 본 = 상급심_빠짐(table, text, 열람)
        if 본:
            res.add('상급심 처리', '막힘' if 빠짐 else '통과',
                    (f"산출물에 적은 상급심의 처리를 판결문을 열람해 본 기록이 없다: {', '.join(빠짐[:12])} — {열람.name} 의 '상급심의 처리' 절에 "
                     "번호와 판결문에서 본 기각 이유를 적는다(LBOX·법제처에 없으면 대조표 '확정' 칸에 '문서 없음', `공통/자체검토.md` 3절)")
                    if 빠짐 else f'{본}건 열람 기록 있음')
        return
    with tempfile.TemporaryDirectory() as d:          # 사건 기록의 보고서는 고치지 않는다(밤 점검이 고치면 다음 밤에 손댄 사건으로 잡힌다)
        임시 = Path(d) / '대조.md'
        code = res.run('판결문 PDF', [SC / 'cite_pdf_check.py', table, pdfdir, '--out', 임시, '--target', 대상], '문제 0')
        res.줄[-1] = (*res.줄[-1][:2], res.줄[-1][2].replace(f' → {임시}', ''))     # 곧 지워질 파일을 가리키지 않는다
    PDF없는줄 = frozenset()
    if code != 0 and 열람.is_file():
        # 2026. 11. 7. `/하자보완`: 11. 6. 뒤로 대조용 PDF 를 받지 않으므로, PDF 를 받아 둔 사건에서 고친 판에 더한 판결·상급심은 PDF 가 없다.
        # 문제가 모두 'PDF 없음'이고 그 줄·상급심을 열람 대조 기록이 다루면 지나간다(그 줄의 사람 판정은 열람 대조 기록에서 본다).
        # 그때까지는 PDF 폴더만 있으면 PDF 를 더 받으라고 막아 지침(받지 않는다)과 어긋났다(이승민 심사청구 상급심 2건).
        import cite_pdf_check
        결과값 = cite_pdf_check.check(str(table), str(pdfdir), [str(대상)])
        없음 = 결과값.get('없음', [])
        if 없음 and 결과값['문제'] == len(없음):
            상급 = {x['판결'] for x in 없음 if x['종류'] == '상급심'}
            없는줄 = frozenset((x['줄'].strip(), x['표시']) for x in 없음 if x['종류'] == '본문')
            빠짐, 본상급 = 상급심_빠짐(table, text, 열람, 상급, 없는줄)
            if 빠짐:
                res.줄[-1] = (res.줄[-1][0], '막힘', res.줄[-1][2] + f" — 판결문 PDF 가 없는 상급심을 {열람.name} 의 '상급심의 처리' 절에도 적지 않았다: "
                                                                 + ', '.join(빠짐[:12]))
            else:
                PDF없는줄 = 없는줄
                res.줄[-1] = (res.줄[-1][0], '통과', f"PDF 로 맞댄 판결 {결과값['판결']}건 문제 0, PDF 가 없는 본문 줄 {len(PDF없는줄)}·상급심 {본상급}건은 "
                                                   f"원문 열람 대조 {열람.name} 으로 봄")
                code = 0
    if code == 0:
        빈 = 사람판정_빈(table, report, 빼고=PDF없는줄) + (사람판정_빈(table, 열람, 만=PDF없는줄) if PDF없는줄 else [])
        res.add('판결 판단 부분·방향·사안 비교', '막힘' if 빈 else '통과',
                (f"'사람 판정' 표에서 빈 줄: {', '.join(빈[:12])} ({report}{', ' + 열람.name if PDF없는줄 else ''})") if 빈 else f'{len(본문줄)}줄 판정')


# ---------------------------------------------------------------- 서면
def 최근_라운드(사건: Path):
    rs = sorted((p for p in 사건.glob('라운드*') if p.is_dir()), key=lambda p: int(re.sub(r'\D', '', p.name) or 0))
    return rs[-1] if rs else None


def 상대_서면(라운드: Path) -> list:
    ecr = 증거검토()
    d = 라운드 / '상대증거'
    if not d.is_dir():
        return []
    return [p for p in d.iterdir() if p.is_file() and not p.name.startswith('~$')
            and p.suffix.lower() in ('.pdf', '.docx', '.hwp', '.hwpx') and not ecr.file_key(p.name)]


def 초안_목록(라운드: Path) -> list:
    return 증거검토().drafts_of(라운드)


def 붙임(s: str) -> str:
    return re.sub(r'[*`]', '', cite_check.norm(s)).translate(str.maketrans('․‧ㆍ・', '····'))


def 초안_조각(초안: Path) -> tuple:
    """(본문 조각들, 각주들). 본문('---' 위)을 줄과 표 칸으로 나눈다. 제목 번호와 그림은 docx 에 글자로 없다."""
    본문 = 초안.read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n').split('\n---\n')[0]
    각주 = [붙임(x) for x in re.findall(r'\[\[각주:(.*?)\]\]', 본문, flags=re.S)]
    본문 = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', re.sub(r'\[\[각주:.*?\]\]', '', 본문, flags=re.S))
    조각 = []
    for 줄 in 본문.splitlines():
        줄 = 줄.strip()
        if 줄.startswith('|'):
            if not re.fullmatch(r'[|\s:\-]+', 줄):
                조각 += [붙임(c) for c in 줄.strip('|').split('|')]
        else:
            줄 = re.sub(r'^#+\s*|^〔[^〕]*〕', '', 줄.replace('**', '')).strip()     # '〔원문〕'은 병합 때 빠지는 표시이다
            조각.append(붙임(re.sub('^' + 번호_꼴 + r'\s*', '', 줄)))
    return [x for x in 조각 if x and not re.fullmatch(r'-?다음-?', x)], 각주


def 병합본_글(병합본: Path) -> tuple:
    """(본문 글자, 각주 글자, 본문 시작을 찾았나). 본문은 프레임의 '다음' 뒤이다(표지 없는 소장은 '청구원인' 뒤). 표지와 목차는 프레임의 것이다."""
    with zipfile.ZipFile(병합본) as z:
        본 = z.read('word/document.xml').decode('utf-8', 'replace')
        주 = z.read('word/footnotes.xml').decode('utf-8', 'replace') if 'word/footnotes.xml' in z.namelist() else ''
    뽑기 = lambda x: 붙임(html.unescape(''.join(re.findall(r'<w:t(?: [^>]*)?>([^<]*)</w:t>', x))))
    문단들 = [뽑기(p) for p in re.findall(r'<w:p[ >].*?</w:p>', 본, flags=re.S)]
    시작 = next((i for 꼴 in (r'-?다음-?', '청구원인') for i, p in enumerate(문단들) if re.fullmatch(꼴, p)), None)
    return ''.join(문단들[시작 + 1 if 시작 is not None else 0:]), 뽑기(주), 시작 is not None


def 본문이_같은가(초안: Path, 병합본: Path) -> bool:
    """초안을 병합본보다 뒤에 고쳤어도 본문('---' 위)이 병합본과 같으면 하단 보완 메모만 고친 것이다. 문단·짧은 제목·표 칸을 차례대로 맞대고,
    그 사이에 초안에 없는 글이 끼면(초안에서 지운 문단이 병합본에 남은 것) 다르다고 본다. 각주도 맞댄다.
    2026. 11. 3. 스무 글자 넘는 문단이 병합본에 있기만 보다가, 각주의 판결 번호·표의 금액·짧은 제목을 고치거나 문단을 지운 초안을 통과시켰다."""
    try:
        글자, 주, 시작있음 = 병합본_글(병합본)
    except (OSError, zipfile.BadZipFile, KeyError):
        return False
    조각, 각주 = 초안_조각(초안)
    자리 = 0
    for i, x in enumerate(조각):
        k = 글자.find(x, 자리)
        if k < 0:
            if x == '입증방법':       # 새로 내는 호증이 없으면 병합이 입증방법 제목을 넣지 않는다
                continue
            return False
        if (i or 시작있음) and not re.fullmatch(f'{번호_꼴}*', 글자[자리:k]):
            return False
        자리 = k + len(x)
    남은글 = 글자[자리:]            # 끝은 프레임의 제출일·대리인 블록이다
    if 시작있음 and 남은글 and not re.match(r'(?:20\d{2}|\s*\.)', 남은글):
        return False
    return bool(조각) and ''.join(각주) == 주


def 초안_이름(초안: Path) -> str:
    return 초안.stem.replace('서면초안', '').strip('_')


def 짝_초안(라운드: Path, 대상: Path) -> tuple:
    """서면을 나눈 라운드에서 docx 대상(병합본·담당자 저장본·제출본 사본)의 짝 초안 `서면초안_{이름}.md`. (초안, 막힌 까닭).
    서면 이름은 파일 이름(`({의뢰인명}) {서면명}({이름})_초안.docx`)에서 먼저 찾고, 없으면 라운드 안의 폴더(`출력/제출/{이름}/`)에서 찾는다
    (`system.name_owner`. 호증 번호 검사 `citation_check.split_of` 와 같은 꼴). 나누지 않은 라운드면 (None, '').
    2026. 11. 9. 이승민 심사청구: 적응장애·우울증 서면 docx 를 `--대상` 으로 주자 초안 목록의 첫째(서면초안_림프종.md)와 짝지어, 문체 말고는
    호증 번호·판례 대조·DOCX·제출본을 모두 림프종 서면의 목록·대조표·초안·제출본과 맞대었다."""
    names = _system.split_names(라운드 / '출력')
    if not names:
        return None, ''
    이름 = _system.name_owner(대상.name, names)
    if not 이름 and 대상.resolve().is_relative_to(라운드.resolve()):
        이름 = _system.folder_owner(대상.resolve(), 라운드.resolve(), names)
    짝 = next((p for p in 초안_목록(라운드) if _system.draft_name(p) == 이름), None) if 이름 else None
    if 짝:
        return 짝, ''
    return None, (f"서면을 나눈 라운드({', '.join(names)})인데 {대상.name} 이 어느 서면의 것인지 파일 이름이나 `출력/제출/{{이름}}/` 자리로 "
                  "가리지 못했다 — 파일 이름에 서면 이름을 넣는다(예: `(의뢰인) 심사청구 취지 및 이유(림프종)_초안.docx`)")


def 범위_붙여(기본: str):
    """통과 말에 검사 출력의 '범위:' 줄(서면을 나눈 라운드에서 그 서면의 몫만 보았다는 말)을 붙이는 함수. `결과.run` 의 통과말로 준다."""
    def 말(out: str) -> str:
        줄 = next((l.strip() for l in out.splitlines() if l.strip().startswith('범위:')), '')
        return f'{기본} — {줄}' if 줄 else 기본
    return 말


def 제출_자리(라운드: Path, 초안: Path) -> Path:
    """제출 묶음 폴더. 서면을 나눈 라운드는 `출력/제출/{이름}/` 이다(이름은 `system.name_form` 으로 맞댄다. '소음성 난청·이명' = 서면초안_소음성난청이명).
    2026. 11. 8. `/하자보완`: `출력/제출/` 맨 위만 보아 서면마다 나눈 묶음의 서증 압축·제출본 검사를 '해당 없음'으로 넘겼다."""
    제출 = 라운드 / '출력' / '제출'
    names = _system.split_names(라운드 / '출력')
    이름 = _system.draft_name(초안) if names else ''
    if 이름 and 제출.is_dir():
        for d in sorted(p for p in 제출.iterdir() if p.is_dir()):
            if _system.name_owner(d.name, names) == 이름:
                return d
    return 제출


def 대조표_자리(사건: Path, 라운드: Path, 초안: Path) -> tuple:
    """(인용 대조표, 판결문 PDF 대조 보고서). 서면초안_{이름}.md 는 이름이 든 표(라운드나 사건 폴더의 작업/)를 쓴다."""
    이름 = 초안_이름(초안)
    if not 이름:
        return 라운드 / '작업' / '인용대조표.md', 라운드 / '작업' / '판결원문_PDF대조.md'
    for d in (라운드 / '작업', 사건 / '작업'):
        걸림 = sorted(d.glob(f'인용대조표*{이름}*.md'))
        if 걸림:
            return 걸림[0], d / f'판결원문_PDF대조_{이름}.md'
    return 라운드 / '작업' / f'인용대조표_{이름}.md', 라운드 / '작업' / f'판결원문_PDF대조_{이름}.md'


def 예상질의(res: 결과, 라운드: Path):
    """심문회의 예상 질의답변을 만들었으면 `/예상질의` 5절의 검사를 본다. 사내 인사위원회 리허설 문서는 모양이 달라 보지 않는다."""
    질의 = [p for p in (라운드 / '출력').glob('*심문회의 예상 질의답변*.docx') if not p.name.startswith('~$')]
    if not 질의:
        return
    최신 = max(질의, key=lambda p: p.stat().st_mtime)
    res.run('예상 질의답변 모양', [S4 / 'qna_check.py', 최신], '위반 0')
    res.run('예상 질의답변 문체', [S4 / 'style_check.py', 최신], '위반 0')
    표 = 라운드 / '작업' / '예상질의_인용대조표.md'
    if 표.is_file():
        res.run('예상 질의답변 판례 대조', [SC / 'cite_check.py', 표, '--target', 최신], '불일치 0')
    elif 인용_있나(글(최신)):
        res.add('예상 질의답변 판례 대조', '막힘', f'사건번호가 있는데 대조표가 없다: {표}')


def 서면(사건: Path, 라운드번호=None, 대상=None, 초안없음_허용=False, 초안=None) -> 결과:
    res = 결과()
    라운드 = 사건 / f'라운드{라운드번호}' if 라운드번호 else 최근_라운드(사건)
    if not 라운드 or not 라운드.is_dir():
        res.add('초안', '막힘', f'라운드 폴더가 없다: {사건}')
        return res
    if 초안 is None and 대상 and Path(대상).suffix.lower() == '.md' and Path(대상).name.startswith('서면초안'):
        초안 = Path(대상)
    if 초안 is None and 대상 and Path(대상).suffix.lower() == '.docx':
        초안, 까닭 = 짝_초안(라운드, Path(대상))        # 서면을 나눈 라운드는 그 docx 의 서면 초안과 맞댄다
        if 까닭:
            res.add('초안', '막힘', 까닭)
            return res
    if 초안 is None:
        후보 = 초안_목록(라운드)
        초안 = 후보[0] if 후보 else 라운드 / '출력' / '서면초안.md'
    제출 = 제출_자리(라운드, 초안)
    if not 초안.is_file():
        if 초안없음_허용:       # 밤 점검: 증거만 새로 받은 사건이면 읽기 기록만 본다
            res.add('초안', '해당 없음', f'{라운드.name} 초안 없음')
            res.run('증거 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건], '모든 호증 기록 완료', '호증 없음')
            예상질의(res, 라운드)
            return res
        res.add('초안', '막힘', f'초안이 없다: {초안}')
        return res
    대상 = Path(대상) if 대상 else 초안
    작업 = 라운드 / '작업'
    res.대상 = f'{라운드.name}/출력/{초안.name}' + (f' ← {대상.name}' if 대상.suffix.lower() == '.docx' else '')
    res.대상시각 = 초안.stat().st_mtime
    나눈 = _system.split_names(라운드 / '출력')
    # 서면을 나눈 라운드는 전 면 읽기·쟁점 낱말을 그 서면의 몫으로 본다. 다른 서면의 호증·자료는 그 서면의 관문이 본다
    # (2026. 11. 9. 이승민 심사청구: 림프종 서면 관문의 전 면 읽기 막힘 119건 가운데 85건이 적응장애·우울증 서면 몫이었다).
    # 전 면 읽기는 마지막 라운드의 서면 이름으로 호증을 가르므로(`evidence_read.서면_호증`) 그 라운드를 볼 때만 좁힌다
    몫 = ['--서면', _system.draft_name(초안)] if 나눈 and _system.draft_name(초안) in 나눈 else []
    몫_읽기 = 몫 if 라운드.resolve() == 최근_라운드(사건).resolve() else []
    res.run('문체', [S4 / 'style_check.py', 대상], '위반 0')
    res.run('호증 번호', [S4 / 'citation_check.py', 대상, '--서면', 초안], '목록에 없는 호증 0')
    표, 보고서 = 대조표_자리(사건, 라운드, 초안)
    판례(res, 대상, 표, 라운드 / '참고자료' / '인용판결_PDF', 라운드, 보고서)

    본문 = 초안.read_text(encoding='utf-8', errors='replace')
    if EVIDENCE_REF.search(본문.split('\n---\n')[0]):
        검토 = 증거검토().review_dir(초안)
        rj, nj = 검토 / 'review.json', 검토 / 'notes.json'
        if not rj.is_file():
            res.add('증거 인용', '막힘', f'증거 인용 대조를 하지 않았다(evidence_cite_review.py scan): {rj}')
        else:
            items = json.loads(rj.read_text(encoding='utf-8'))
            # 초안이 더 새것이어도 인용이 그대로이면 대조는 낡지 않았다(2026. 11. 3. 하단 메모만 고친 초안을 막았다). 거꾸로 대조가 더 새것이어도
            # 지금 읽은 인용과 다르면 낡은 것이다(같은 날 '3·5면'의 3면을 버리던 인용 읽기를 고쳤다)
            새것, 없어짐 = 증거검토().citation_changes(초안, items)
            바뀐파일 = [] if 새것 or 없어짐 else 증거검토().file_changes(초안, items)      # 판정한 뒤 호증 파일을 바꾸면 판정은 낡았다
            if 새것 or 없어짐:
                res.add('증거 인용', '막힘', f'지금 초안의 인용과 대조해 둔 인용이 다르다(새로 생긴 인용 {새것}건, 없어진 인용 {없어짐}건. '
                        '초안을 고쳤거나 인용 읽기가 바뀌었다) — scan 을 다시 돌리면 같은 인용의 판정은 옮겨지고 바뀐 인용만 다시 판정한다')
            elif 바뀐파일:
                res.add('증거 인용', '막힘', f'대조한 뒤 호증 파일이 바뀌었다({", ".join(바뀐파일[:10])}{" 외" if len(바뀐파일) > 10 else ""}) — '
                        'scan 을 다시 돌리면 그 호증 인용의 판정만 비워지고 나머지는 옮겨진다. 바뀐 파일로 다시 판정한다')
            else:
                notes = json.loads(nj.read_text(encoding='utf-8')) if nj.is_file() else {}
                빈 = [str(r.get('n')) for r in items if not (notes.get(str(r.get('n'))) or [''])[0]]
                res.add('증거 인용', '막힘' if 빈 else '통과',
                        f'notes.json 에 판정이 없는 인용 {len(빈)}건: {", ".join(빈[:20])}' if 빈 else f'{len(items)}건 판정')
    else:
        res.add('증거 인용', '해당 없음', '본문에 증거 인용 없음')

    if res.run('증거 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건, *몫_읽기], 범위_붙여('모든 호증 기록 완료'), '호증 없음') == 2:
        res.add('빠진 문구(쟁점 낱말)', '해당 없음', '호증 없음')
    else:
        res.run('빠진 문구(쟁점 낱말)', [S4 / 'evidence_words.py', 사건, '--라운드', re.sub(r'\D', '', 라운드.name), '--확인', *몫],
                범위_붙여('판단 빈 줄 0'))

    res.run('증거 나누기', [S4 / 'evidence_sort.py', 사건, '--라운드', re.sub(r'\D', '', 라운드.name), '--확인'], '우리·상대 증거가 섞여 있지 않다')
    상대 = 상대_서면(라운드)
    맞대기 = 작업 / '상대주장_맞대기.md'
    if 상대:
        if not 맞대기.is_file():
            res.add('상대 서면 맞대기', '막힘', f'상대방 서면({", ".join(p.name for p in 상대)})을 첫 면부터 다시 읽고 맞댄 표가 없다: {맞대기}')
        else:
            빈, 전체 = 빈_판정(맞대기, ('판정',))
            if 빈 or not 전체:
                res.add('상대 서면 맞대기', '막힘', f'판정이 빈 줄 {빈}/{전체}')
            elif 맞대기.stat().st_mtime + 1 < 초안.stat().st_mtime:
                적은 = re.search(r'초안 본문:\s*`?([0-9a-f]{10})', 맞대기.read_text(encoding='utf-8'))
                if 적은 and 적은.group(1) == 본문_해시(초안):
                    res.add('상대 서면 맞대기', '통과', f'{전체}줄 판정(맞댄 뒤 초안은 하단만 고침)')
                else:
                    res.add('상대 서면 맞대기', '막힘', '초안을 고친 뒤 맞대기 표를 다시 보지 않았다(고친 목을 다시 맞대고 표를 고친다'
                            + (". 표 머리의 '초안 본문' 해시가 지금 본문과 다르다" if 적은 else '') + ')')
            else:
                res.add('상대 서면 맞대기', '통과', f'{전체}줄 판정')
    else:
        res.add('상대 서면 맞대기', '해당 없음', '이 라운드 상대증거/ 에 상대방 서면 없음')

    대조 = 작업 / '의뢰인주장_대조.md'
    if 대조.is_file():
        빈, 전체 = 빈_판정(대조, ('반영',))
        # 표는 라운드에 하나이다. docx 를 볼 때도 서면을 나눈 라운드의 다른 서면 문장은 그 서면의 초안에서 찾는다
        글들 = ([대상] + [p for p in 초안_목록(라운드) if p.resolve() != 초안.resolve()]) if 대상.suffix.lower() == '.docx' else (초안_목록(라운드) or [초안])
        없는, 인정 = 인정_문장_없음(대조, 글들)
        말 = ([f"'반영' 칸이 빈 줄 {빈}/{전체}"] if 빈 else []) + (
            [f"인정 표의 본문 문장 {len(없는)}/{인정}개가 지금 초안 본문에 없다(초안을 고친 뒤 7-0단계를 다시 하여 바뀐 인정 문장을 글자 그대로 옮긴다): "
             + ' / '.join(f"'{q[:30]}…'" for q in 없는[:5])] if 없는 else [])
        res.add('의뢰인 주장', '막힘' if 말 else '통과', ' — '.join(말) if 말 else f'{전체}줄 반영 표시' + (f', 인정 문장 {인정}개 초안과 같음' if 인정 else ''))
    else:
        res.add('의뢰인 주장', '해당 없음', '의뢰인주장_대조.md 없음')

    # 병합한 서면(3-1절 이름. 서면_프레임.docx 는 아니다). 8-1단계는 병합 전에 돌리므로 그때는 보지 않고,
    # 9-2단계(--대상 docx)와 밤 점검에서 초안을 고친 뒤 병합하지 않은 판을 잡는다
    이름 = 초안_이름(초안)
    docxs = [p for p in (라운드 / '출력').glob('*.docx')
             if not p.name.startswith('~$') and 병합본_이름.search(p.name) and not 부속_이름.search(p.name)
             and (not 이름 or _system.name_form(이름) in _system.name_form(p.name))]
    res.넘긴판 = bool(docxs) or 제출.is_dir()
    병합본 = 대상 if 대상.suffix.lower() == '.docx' else (max(docxs, key=lambda p: p.stat().st_mtime) if docxs and 초안없음_허용 else None)
    if 병합본 is None:
        res.add('DOCX', '해당 없음', '병합 전에 돌림(9-2단계에서 `--대상 "{docx}"` 로 다시 돌린다)' if docxs else '아직 병합 전')
    elif 초안.stat().st_mtime > 병합본.stat().st_mtime + 1 and not 본문이_같은가(초안, 병합본):
        res.add('DOCX', '막힘', f'서면초안.md 를 고친 뒤 병합하지 않았다: {병합본.name}')
    else:
        res.add('DOCX', '통과', 병합본.name)

    if list(제출.glob('*_서증.zip')):
        res.run('서증 압축', [S4 / 'evidence_zip.py', 제출, '--확인'], '증거/ 와 같다')
    else:
        res.add('서증 압축', '해당 없음', '제출 묶음 압축파일 없음')
    제출본_검사(res, 제출, 병합본)
    예상질의(res, 라운드)
    return res


def 제출본_검사(res, 제출: Path, 병합본):
    """제출/ 의 `({의뢰인명}) {서면명}_제출본.docx`·`.pdf` 가 넘길 판과 같은지 본다(4_서면작성/CLAUDE.md 2-1절).
    2026. 11. 3. 한전 태양광 준비서면(3) "서면도 그떄그때 바꿔주면 좋겠고 (_제출본)으로 해놓으면 좋을 듯" — 그때까지 제출 폴더에
    9차판 사본이 남아 있었다. 옛 이름(_초안 등) 사본만 있는 사건은 막지 않고 참고로 알린다."""
    if 병합본 is None or not 제출.is_dir():
        res.add('제출본', '해당 없음', '넘길 판이나 제출 폴더가 없다')
        return
    사본 = sorted(p for p in 제출.glob('*_제출본.docx') if not p.name.startswith('~$'))
    if not 사본:
        옛 = sorted(p.name for p in 제출.glob('*.docx') if not p.name.startswith('~$'))
        if 옛:
            res.add('제출본', '참고', f'제출/ 의 서면 사본 이름이 `_제출본` 이 아니다: {", ".join(옛)}(2-1절)')
        else:
            res.add('제출본', '해당 없음', '제출/ 에 서면 사본이 없다')
        return
    원본 = 병합본.read_bytes()
    같은 = [p for p in 사본 if p.read_bytes() == 원본]
    if not 같은:
        res.add('제출본', '막힘', f'제출/ 의 {사본[0].name} 이 넘길 판({병합본.name})과 다르다 — 서면을 고칠 때마다 제출본도 바꾼다(2-1절)')
        return
    pdf, 사본pdf = 병합본.with_suffix('.pdf'), 같은[0].with_suffix('.pdf')
    if pdf.is_file() and (not 사본pdf.is_file() or 사본pdf.read_bytes() != pdf.read_bytes()):
        res.add('제출본', '막힘', f'제출/ 의 {사본pdf.name} 이 {pdf.name} 과 다르거나 없다')
        return
    res.add('제출본', '통과', 같은[0].name)


# ---------------------------------------------------------------- 서면 사건의 다른 인용 산출물
# 2026. 11. 7. `/하자보완`: 서면 사건에서 서면 초안이 아닌 인용 산출물(리서치 문서, 담당 변호사에게 올리는 검토 메모, 회신 메일 초안)은
# 관문이 찾지 못해 판례 검사를 하나도 돌리지 않았다. `--대상` 으로 주어도 '초안이 없다'로 막혔다. 11. 6. 최문희 중노위 재심 가능성 검토
# (`라운드1/작업/…검토.md`, 대조표 있음)에서 담당 노무사가 "안산 판결도 사실관계 보면 강등에 대한 판단만 있지 우리 사안에 원용하기
# 어려워 보임(그 전에도 이런 식으로 판례 수집했나? 문젠데)"라고 짚었는데, 관문이 보았으면 '사안 비교' 칸이 빈 것으로 막혔을 일이다.
# 검토의견 사건의 다른 원고(11. 6. 고침)와 같은 꼴이다. 그 대조표(`인용대조표_{산출물}.md`, 또는 머리 '# 인용 대조표 — {산출물 이름}')로
# 산출물을 찾아 검토의견과 같은 검사(판례·판결 원문 대조·상급심·문체)를 돌린다.
기록_이름 = re.compile(r'^(?:인용대조표|판결원문_|검색기록|사건상태|수확목록|쟁점낱말|의뢰인주장|상대주장|사실관계|하이라이트|소요시간|~\$)')


def _열쇠(s: str) -> str:
    return re.sub(r'[\s_]', '', cite_check.norm(s) if s else '')


def 대조표_머리(표: Path) -> str:
    """대조표 첫 줄 '# 인용 대조표 — {제목}' 의 제목."""
    try:
        첫 = 표.read_text(encoding='utf-8', errors='replace').lstrip('﻿').splitlines()[0]
    except (OSError, IndexError):
        return ''
    m = re.match(r'#\s*인용\s*대조표\s*[—–-]+\s*(.+)', 첫)
    return m.group(1).strip() if m else ''


def 다른_산출물_찾기(사건: Path, 라운드: Path | None, 표: Path) -> Path | None:
    """대조표가 가리키는 산출물(.md·.docx). 대조표 이름이 `인용대조표_{이름}.md` 이면 그 이름이 든 파일, 아니면 머리 제목에 이름이 든 파일.
    대조표 폴더, 라운드의 작업/·출력/, 사건의 작업/ 에서 찾고 여럿이면 가장 새것이다."""
    제목 = _열쇠(대조표_머리(표))
    꼬리 = _열쇠(표.stem[len('인용대조표_'):]) if 표.stem.startswith('인용대조표_') else ''
    폴더들 = [표.parent] + ([라운드 / '작업', 라운드 / '출력'] if 라운드 else []) + [사건 / '작업']
    후보 = []
    for d in dict.fromkeys(폴더들):
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if not p.is_file() or p.suffix.lower() not in ('.md', '.docx') or 기록_이름.search(p.name):
                continue
            k = _열쇠(p.stem)
            if len(k) >= 4 and ((꼬리 and 꼬리 in k) or (제목 and k in 제목)):
                후보.append(p)
    return max(후보, key=lambda p: p.stat().st_mtime) if 후보 else None


def 서면_다른_대조표(사건: Path) -> list:
    """[(대조표, 산출물 또는 None, 라운드)]. 서면 사건의 인용 대조표 가운데 어느 라운드의 서면 초안의 것도 아닌 표(빌드·이전판·백업 폴더 밖)."""
    라운드들 = sorted((p for p in 사건.glob('라운드*') if p.is_dir()), key=lambda p: int(re.sub(r'\D', '', p.name) or 0))
    초안표 = {대조표_자리(사건, r, p)[0].resolve() for r in 라운드들 for p in 초안_목록(r)}
    out = []
    for 라운드, d in [(r, r / '작업') for r in 라운드들] + [(라운드들[-1] if 라운드들 else None, 사건 / '작업')]:
        if not d.is_dir():
            continue
        for 표 in sorted(d.rglob('인용대조표*.md')):
            if any(x in ('빌드', '백업', '이전판', '자체검토') or x.startswith('이전') for x in 표.relative_to(d).parts[:-1]):
                continue
            if 표.resolve() not in 초안표:
                out.append((표, 다른_산출물_찾기(사건, 라운드, 표), 라운드))
    return out


def 다른_산출물(사건: Path, 대상: Path, 표: Path) -> 결과:
    """서면 사건의 다른 인용 산출물을 검토의견 산출물처럼 본다. 판결 원문 대조 기록은 대조표 옆(`판결원문_열람대조{_이름}.md`)이다."""
    res = 결과()
    res.대상, res.대상시각 = str(대상.relative_to(사건)) if 대상.is_relative_to(사건) else 대상.name, 대상.stat().st_mtime
    폴더 = next((p.parent for p in 표.parents if p.name == '작업'), 표.parent)
    판례(res, 대상, 표, 표.parent / '인용판결_PDF', 폴더, 표.with_name(표.name.replace('인용대조표', '판결원문_PDF대조', 1)))
    text = 글(대상).split('## 보완 메모')[0].split('\n---\n')[0]
    걸림 = [w for w in 낙관 if w in text] + [m.group(0) for m in 적다.finditer(text)]
    res.add('문체(낙관 표현·적다)', '막힘' if 걸림 else '통과',
            ('쓰지 않는 표현: ' + ', '.join(dict.fromkeys(걸림))) if 걸림 else '낙관 표현·적다 없음')
    return res


def 다른_산출물_대상(사건: Path, 대상: Path) -> list:
    """`--대상` 이 서면 초안·병합본이 아닌 원고이면 [('', 결과)], 아니면 []. 대조표는 그 산출물을 가리키는 표이다."""
    if 대상.name.startswith('서면초안') or (대상.suffix.lower() == '.docx' and 병합본_이름.search(대상.name)):
        return []
    짝 = [표 for 표, p, _ in 서면_다른_대조표(사건) if p and p.resolve() == 대상.resolve()]
    if 짝:
        return [('', 다른_산출물(사건, 대상, 짝[0]))]
    res = 결과()
    res.대상, res.대상시각 = 대상.name, (대상.stat().st_mtime if 대상.is_file() else time.time())
    있나 = 대상.is_file() and 인용_있나(글(대상))
    res.add('판례 대조', '막힘' if 있나 else '해당 없음',
            f"이 산출물을 가리키는 인용 대조표가 없다 — `인용대조표_{{산출물 이름}}.md` 로 두거나 첫 줄을 '# 인용 대조표 — {대상.name}' 으로 쓴다"
            '(`공통/자체검토.md` 3절)' if 있나 else '사건번호 없음')
    return [('', res)]


def 서면_다른_산출물들(사건: Path, 끝: float) -> list:
    """밤 점검: 이번 범위에 대조표나 산출물을 고친 다른 인용 산출물마다 [(표제, 결과)]. 산출물을 찾지 못한 대조표는 '참고'로 알린다."""
    out, 못찾음 = [], []
    for 표, 대상, _ in 서면_다른_대조표(사건):
        if 대상 is None:
            if 표.stat().st_mtime >= 끝:
                못찾음.append(str(표.relative_to(사건)))
            continue
        if max(표.stat().st_mtime, 대상.stat().st_mtime) >= 끝:
            out.append((f'다른 산출물 {대상.name}', 다른_산출물(사건, 대상, 표)))
    if 못찾음:
        res = 결과()
        res.add('다른 산출물', '참고', f"이번 범위에 고친 대조표 {', '.join(못찾음)} 의 산출물을 대조표 이름·머리 제목으로 찾지 못해 맞대지 않았다 — "
                '넘긴 세션이 `--대상` 으로 관문을 돌렸는지 사건상태에서 본다')
        out.append(('다른 산출물(찾지 못함)', res))
    return out


def 돌리기(사건: Path, 라운드번호=None, 대상=None, 밤=False, 끝=None) -> list:
    """[(표제, 결과)]. 한 라운드에 서면이 여럿이면 서면마다 본다. 끝(밤 점검 범위의 시작)을 주면 검토의견 사건의 다른 원고도 본다.
    서면 사건에서 `--대상` 이 서면 초안이 아닌 원고(리서치·검토 메모)이면 그 대조표로 본다(서면 사건의 밤 점검은 main 이 사건마다 한 번 본다)."""
    종류 = 사건_종류(사건)
    if 종류 == '계산':
        return [('', 계산(사건))]
    if 종류 == '검토의견':
        기본 = 검토의견(사건, 대상, 밤)
        return [('', 기본)] + (다른_원고들(사건, 기본, 끝) if 끝 is not None and not 대상 else [])
    if 대상:
        다른 = 다른_산출물_대상(사건, Path(대상))
        if 다른:
            return 다른
    라운드 = 사건 / f'라운드{라운드번호}' if 라운드번호 else 최근_라운드(사건)
    후보 = 초안_목록(라운드) if 라운드 and 라운드.is_dir() else []
    if 대상 or len(후보) < 2:
        return [('', 서면(사건, 라운드번호, 대상, 밤))]
    return [(p.name, 서면(사건, 라운드번호, None, 밤, p)) for p in 후보]


# ---------------------------------------------------------------- 검토의견
def 판_순위(p: Path) -> int:
    """뒤 판일수록 크다(`_Rev_N`, `_N차 수정안`). 수정 시각만으로 고르면 나중에 건드린 지난 판을 본다."""
    m = re.search(r'_Rev_(\d+)|_(\d+)차 수정안', p.name)
    return int(m.group(1) or m.group(2)) if m else 0


def 검토의견_산출물(사건: Path) -> tuple:
    """사건 폴더 맨 위의 우리 산출물(`1_검토의견/CLAUDE.md` 7절)을 (주, 그 밖) 으로 나눈다.
    주는 검토의견서 docx(`관련 검토_…`. 검토용 변경 표시본은 같은 판의 사본이라 뺀다)와 `-회신초안.md`·`-간이안.md` 이고,
    그 밖은 사건 폴더 이름으로 시작하거나 이름에 '회신초안'이 든 다른 원고(`-의견서원고.md`·`-추가질의 회신초안.md`·`-회신초안(2차).md`)다.
    2026. 11. 6. `/하자보완`: 11. 5. SR노조 제3자 의견서(원고 `…-의견서원고.md`, 판결 인용)를 밤 점검이 '검토의견서·회신초안이 없다'로
    넘겨 판례 검사를 하나도 돌리지 않았다. 다른 원고를 주와 같이 고르면 회신 둘이 대조표 하나를 쓰는 옛 사건(첫 회신의 줄만 있다)을
    잘못 막으므로, 그 밖의 원고는 주가 없을 때만 고르고 밤 점검에서는 그 이름의 대조표가 있을 때 함께 본다(`돌리기`)."""
    주, 그밖 = [], []
    for p in 사건.iterdir():
        n = p.name
        if not p.is_file() or n.startswith('~$'):
            continue
        if (re.search(r'관련 검토_.*\.docx$', n) and not re.search(r'검토용|변경분 표시', n)) or n.endswith(('-회신초안.md', '-간이안.md')):
            주.append(p)
        elif n.endswith('.md') and (n.startswith(사건.name + '-') or '회신초안' in n):
            그밖.append(p)
    return 주, 그밖


def 산출물_꼬리(사건: Path, 대상: Path) -> str:
    """원고 이름의 산출물 이름(`{사건}-의견서원고.md` → '의견서원고'). 사건 이름으로 시작하지 않으면 마지막 '-' 뒤."""
    s = 대상.stem
    return s[len(사건.name) + 1:] if s.startswith(사건.name + '-') else s.rsplit('-', 1)[-1]


def 검토의견_대조표(사건: Path, 대상: Path) -> Path:
    """산출물에 맞는 인용 대조표. 간이안은 `인용대조표_간이안.md`, 다른 원고는 `인용대조표_{산출물 이름}.md` 가 있으면 그것
    (`-추가질의 회신초안.md` → `인용대조표_추가질의 회신초안.md`), 나머지는 `인용대조표.md` 이다(`1_검토의견/CLAUDE.md` 7절)."""
    작업 = 사건 / '작업'
    if '간이안' in 대상.name:
        return 작업 / '인용대조표_간이안.md'
    따로 = 작업 / f'인용대조표_{산출물_꼬리(사건, 대상)}.md'
    return 따로 if 대상.suffix.lower() == '.md' and 따로.is_file() else 작업 / '인용대조표.md'


def 다른_원고들(사건: Path, 기본: 결과, 끝: float) -> list:
    """밤 점검: 이번 범위에 고친 다른 원고 가운데 기본 대상이 아닌 것. 그 이름의 대조표가 있는 것은 따로 보고([(이름, 결과)]),
    없는 것은 기본 결과에 '참고'로 적는다(대조표를 함께 쓰면 줄이 맞지 않아 기계로 맞대지 못한다)."""
    out = []
    for p in sorted(검토의견_산출물(사건)[1]):
        if p.name == 기본.대상 or p.stat().st_mtime < 끝:
            continue
        표 = 사건 / '작업' / f'인용대조표_{산출물_꼬리(사건, p)}.md'
        if 표.is_file():
            out.append((p.name, 검토의견(사건, p, True)))
        else:
            기본.add('다른 원고', '참고', f'이번 범위에 고친 {p.name} 은 따로 둔 대조표(작업/{표.name})가 없어 기계로 맞대지 않았다 — '
                    '넘긴 세션이 `--대상` 으로 관문을 돌렸는지 사건상태에서 본다(1_검토의견/CLAUDE.md 7절)')
    return out


def 검토의견(사건: Path, 대상=None, 초안없음_허용=False) -> 결과:
    res = 결과()
    if 대상:
        대상 = Path(대상)
    else:
        주, 그밖 = 검토의견_산출물(사건)
        후보 = 주 or 그밖                     # 다른 원고는 검토의견서·회신초안이 없을 때만
        대상 = max(후보, key=lambda p: (판_순위(p), p.stat().st_mtime)) if 후보 else None
    if not 대상 or not 대상.is_file():
        res.add('산출물', '해당 없음' if 초안없음_허용 else '막힘', f'검토의견서·회신초안이 없다: {사건}')
        if 초안없음_허용:
            res.run('자료 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건, '--자료', 사건], '자료 기록 완료', '자료 없음')
        return res
    res.대상, res.대상시각 = 대상.name, 대상.stat().st_mtime
    res.넘긴판 = any(p.suffix.lower() == '.docx' and '관련 검토_' in p.name for p in 사건.iterdir())
    판례(res, 대상, 검토의견_대조표(사건, 대상), 사건 / '작업' / '인용판결_PDF', 사건)
    res.run('자료 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건, '--자료', 사건], '의뢰인 자료 기록 완료',
            '사건 폴더에 의뢰인 자료 없음')
    text = 글(대상).split('## 보완 메모')[0]       # 보완 메모는 의뢰인에게 가는 글이 아니다
    걸림 = [w for w in 낙관 if w in text] + [m.group(0) for m in 적다.finditer(text)]
    res.add('문체(낙관 표현·적다)', '막힘' if 걸림 else '통과',
            ('쓰지 않는 표현: ' + ', '.join(dict.fromkeys(걸림))) if 걸림 else '낙관 표현·적다 없음')
    for 최종 in sorted(p for p in 사건.glob('*_최종.docx') if not p.name.startswith('~$')):
        res.add('송부판(_최종)', *최종판_검사(최종))
    return res


def 최종판_검사(docx: Path) -> tuple:
    """(상태, 말). 의뢰인에게 보낼 `_최종` docx 에 변경 추적·메모가 남지 않았고 작성자·마지막으로 수정한 사람이 '법무법인 평안'이며,
    Word 로 내보낸 같은 이름의 PDF 가 docx 보다 낡지 않았는가(`1_검토의견/CLAUDE.md` 7절). 2026. 11. 7. `/하자보완`: 11. 6. 담당 노무사가
    정한 이 확인("_최종 이런거")이 글로만 있었다. PDF 면수와 Word 면수의 맞대기는 Word 가 있어야 하므로 작성 세션이 한다."""
    문제 = []
    try:
        with zipfile.ZipFile(docx) as z:
            이름들 = z.namelist()
            본문 = ''.join(z.read(n).decode('utf-8', 'replace') for n in 이름들 if re.fullmatch(r'word/(?:document|footnotes|endnotes|header\d*|footer\d*)\.xml', n))
            메모 = z.read('word/comments.xml').decode('utf-8', 'replace') if 'word/comments.xml' in 이름들 else ''
            core = z.read('docProps/core.xml').decode('utf-8', 'replace') if 'docProps/core.xml' in 이름들 else ''
    except (OSError, zipfile.BadZipFile, KeyError) as e:
        return '막힘', f'{docx.name} 을 열지 못했다({e})'
    추적 = len(re.findall(r'<w:(?:ins|del|moveFrom|moveTo)\b', 본문))
    if 추적:
        문제.append(f'변경 추적 {추적}곳')
    if re.search(r'<w:comment\b', 메모):
        문제.append(f"메모 {len(re.findall(r'<w:comment\b', 메모))}개")
    for 칸, 이름 in (('dc:creator', '작성자'), ('cp:lastModifiedBy', '마지막으로 수정한 사람')):
        m = re.search(rf'<{칸}>(.*?)</{칸}>', core, re.S)
        값 = html.unescape(m.group(1)).strip() if m else ''
        if 값 != '법무법인 평안':
            문제.append(f"{이름} '{값}'")
    pdf = docx.with_suffix('.pdf')
    if not pdf.is_file():
        문제.append(f'{pdf.name} 없음')
    elif pdf.stat().st_mtime + 1 < docx.stat().st_mtime:
        문제.append(f'{pdf.name} 이 docx 보다 낡음')
    if 문제:
        return '막힘', f"{docx.name}: {', '.join(문제)} — 변경 추적·메모를 걷고 문서 속성을 '법무법인 평안'으로 맞춘 뒤 Word 로 PDF 를 다시 내보낸다(`1_검토의견/CLAUDE.md` 7절)"
    return '통과', f'{docx.name} 변경 추적·메모 없음, 작성자 법무법인 평안, PDF 있음'


# ---------------------------------------------------------------- 계산
def 계산(사건: Path) -> 결과:
    res = 결과()
    res.run('자료 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건, '--자료', 사건], '자료 기록 완료', '자료 없음')
    return res


# ---------------------------------------------------------------- 명령
def 사건_종류(사건: Path) -> str:
    parts = 사건.resolve().parts
    if '4_서면작성' in parts:
        return '서면'
    if '1_검토의견' in parts:
        return '검토의견'
    if '6_손해배상계산' in parts:
        return '계산'
    return '서면' if any(사건.glob('라운드*')) else '검토의견'


def 바뀐_파일_있나(폴더: Path, 끝: float) -> bool:
    """끝(시각) 뒤에 고친 파일이 있나. 면별 글·문자인식 캐시와 백업은 세지 않는다."""
    for dp, dn, fn in os.walk(폴더):
        if any(x in Path(dp).parts for x in ('호증글자', 'ocr', '백업')):
            continue
        if any(os.path.getmtime(os.path.join(dp, f)) >= 끝 for f in fn if not f.startswith('~$')):
            return True
    return False


def 최근_사건(시간: float) -> list:
    """시간(시) 안에 파일을 고친 사건 폴더."""
    끝 = time.time() - 시간 * 3600
    out = []
    for 폴더 in ('4_서면작성', '1_검토의견', '6_손해배상계산'):
        base = ROOT / 폴더 / '사건'
        if not base.is_dir():
            continue
        out += [c for c in sorted(base.iterdir()) if c.is_dir() and not c.name.startswith('_') and 바뀐_파일_있나(c, 끝)]
    return out


# 사건 전체를 보는 검사. 밤 점검에서 한 사건의 라운드를 여럿 보면 첫 라운드에서만 센다
사건_전체_검사 = ('증거 파악(전 면 읽기)',)


def 바뀐_라운드들(사건: Path, 끝: float) -> list:
    """밤 점검(`--최근`)에서 볼 라운드 번호. 그 시간 안에 파일을 고친 라운드마다 보고, 고친 라운드가 없으면(증거관리/ 만 바뀜) 빈 목록이다.
    마지막 라운드만 보면 새 라운드 폴더가 생긴 날 앞 라운드에서 고쳐 넘긴 판을 보지 않는다(2026. 11. 5. `/하자보완`: 11. 4. 상대방의
    새 이유서로 GGM 라운드3 이 생긴 뒤 같은 날 고친 라운드2 의 답변서(2) Rev_3·예상 질의답변 Rev_2 를 밤 점검이 라운드3(초안 없음)만 보고 넘겼다)."""
    라운드들 = sorted((p for p in 사건.glob('라운드*') if p.is_dir()), key=lambda p: int(re.sub(r'\D', '', p.name) or 0))
    return [int(re.sub(r'\D', '', p.name) or 0) for p in 라운드들 if 바뀐_파일_있나(p, 끝)]


def 한_번만(줄: list, 본: set) -> list:
    """한 사건의 라운드를 여럿 볼 때 사건 전체를 보는 검사는 처음 나온 결과만 세고, 뒤 라운드의 같은 결과는 '해당 없음'으로 둔다."""
    out = []
    for 이름, 상태, 말 in 줄:
        if 이름 in 사건_전체_검사:
            if (이름, 상태, 말) in 본:
                out.append((이름, '해당 없음', '앞 라운드의 줄과 같다(사건 전체를 보는 검사)'))
                continue
            본.add((이름, 상태, 말))
        out.append((이름, 상태, 말))
    return out


def 보고(사건: Path, res: 결과, 표제='', 길이=None, 끝=None) -> str:
    """사건 하나의 표. 길이를 주면 내용을 그만큼만 싣는다(화면용. 파일에는 전문을 쓴다). 끝은 밤 점검 범위의 시작 시각이다."""
    줄 = [f"## {사건.name}{' · ' + 표제 if 표제 else ''} ({사건_종류(사건)}) — 막힘 {len(res.막힘)}", '']
    if res.대상:
        때 = time.strftime('%Y-%m-%d %H:%M', time.localtime(res.대상시각))
        범위 = '' if 끝 is None else (' · 이번 범위에 고침' if res.대상시각 >= 끝 else ' · 이번 범위에 안 고침(막힘은 앞서 만든 판의 것)')
        줄 += [f"대상: {res.대상} ({때}{범위}){' · 넘긴 판일 수 있음' if res.넘긴판 else ''}", '']
    줄 += ['| 검사 | 결과 | 내용 |', '|---|---|---|']
    for 이름, 상태, 말 in res.줄:
        한줄 = re.sub(r'\s+', ' ', 말).replace('|', '｜')
        줄.append(f'| {이름} | {상태} | {한줄[:길이] if 길이 else 한줄} |')
    return '\n'.join(줄) + '\n'


def 검사별_모음(묶음: list, 끝: float) -> str:
    """밤 점검의 화면 보고. 사건마다가 아니라 검사마다 모은다. `/하자보완` 은 이 표로 검사가 잘못 막거나 통과시키는지, 지침에 빈틈이 있는지 가른다.
    묶음은 [(사건 이름, 결과)]이다. 사건 이름 뒤의 *는 이번 범위에 고친 판이다."""
    막, 통 = {}, {}
    for 이름, res in 묶음:
        표시 = 이름 + ('*' if res.대상시각 and res.대상시각 >= 끝 else '')
        for 검사, 상태, 말 in res.줄:
            if 상태 == '막힘':
                막.setdefault(검사, []).append((표시, 말))
            elif 상태 == '통과':
                통.setdefault(검사, []).append(표시)
    줄 = ['## 검사별 모음', '', '| 검사 | 막힘 | 통과 | 막힌 사건(*는 이번 범위에 고친 판) | 표본 |', '|---|---|---|---|---|']
    for 검사 in sorted(set(막) | set(통), key=lambda x: (-len(막.get(x, ())), x)):
        걸림 = 막.get(검사, [])
        표본 = re.sub(r'\s+', ' ', 걸림[0][1].replace(str(ROOT) + os.sep, '')).replace('|', '｜')[:200] if 걸림 else ''
        줄.append(f"| {검사} | {len(걸림)} | {len(통.get(검사, ()))} | {', '.join(n for n, _ in 걸림)} | {표본} |")
    return '\n'.join(줄) + '\n'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='넘기기 전 마지막 관문(문체·판례·증거)')
    ap.add_argument('case', nargs='?')
    ap.add_argument('--라운드', type=int)
    ap.add_argument('--대상', help='맞댈 산출물(담당자 저장본 위의 수정안이면 그 docx)')
    ap.add_argument('--최근', type=float, help='이 시간(시) 안에 손댄 사건마다 돌린다')
    ap.add_argument('--out', help='보고를 이 md 파일에도 쓴다')
    ap.add_argument('--본문해시', metavar='초안', help="초안 본문의 해시를 낸다(맞대기 표 머리에 '초안 본문: …'으로 적는다)")
    a = ap.parse_args(argv)
    if a.본문해시:
        print(f'초안 본문: {본문_해시(Path(a.본문해시))}')
        return 0
    if a.최근:
        사건들 = 최근_사건(a.최근)
    elif a.case:
        사건들 = [Path(a.case)]
    else:
        ap.error('사건 폴더나 --최근 을 준다')
    글들, 막힘, 묶음 = [], 0, []
    끝 = time.time() - a.최근 * 3600 if a.최근 else None
    for c in 사건들:
        라운드들 = [a.라운드]
        if a.최근 and a.라운드 is None and 사건_종류(c) == '서면':
            라운드들 = 바뀐_라운드들(c, 끝) or [None]          # 고친 라운드마다. 없으면 마지막 라운드
        본 = set()
        돌릴것 = []
        for 라운드 in 라운드들:
            for 표제, res in 돌리기(c, 라운드, a.대상, bool(a.최근), 끝):
                if len(라운드들) > 1:
                    표제 = f'라운드{라운드}' + (f' · {표제}' if 표제 else '')
                    res.줄 = 한_번만(res.줄, 본)
                돌릴것.append((표제, res))
        if 끝 is not None and not a.대상 and 사건_종류(c) == '서면':
            돌릴것 += 서면_다른_산출물들(c, 끝)           # 서면이 아닌 인용 산출물(리서치·검토 메모)은 사건마다 한 번
        for 표제, res in 돌릴것:
            막힘 += len(res.막힘)
            글들.append(보고(c, res, 표제, 끝=끝))
            묶음.append((c.name + (' · ' + 표제 if 표제 else ''), res))
            if not a.최근:
                print(보고(c, res, 표제, 400, 끝))
    모음 = 검사별_모음(묶음, 끝) + '\n' if a.최근 and 사건들 else ''
    if 모음:
        print(모음)
    if a.최근 and not 사건들:
        print(f'{a.최근:g}시간 안에 손댄 사건이 없다.')
    print(f'사건 {len(사건들)}건, 막힘 {막힘}건' + ('' if 막힘 or not 사건들 else ' — 넘겨도 된다(판정의 옳고 그름은 작성 세션이 원문으로 본다)'))
    if a.out:          # 같은 날 다시 돌려도 앞 실행의 전문을 지우지 않고, 손댄 사건이 없는 밤도 돌았다는 줄을 남긴다
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        범위 = f' · 최근 {a.최근:g}시간' if a.최근 else ''
        with open(a.out, 'a', encoding='utf-8') as f:
            f.write(f"# {time.strftime('%Y-%m-%d %H:%M')} 실행{범위} · 사건 {len(사건들)}건, 막힘 {막힘}건\n\n" + 모음 + ''.join(g + '\n' for g in 글들))
    return 1 if 막힘 else 0


if __name__ == '__main__':
    raise SystemExit(main())
