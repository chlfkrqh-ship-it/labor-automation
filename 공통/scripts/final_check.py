"""넘기기 전 마지막 관문. 서면·검토의견 하나에 문체·판례·증거(파악·인용·편철) 검사를 모두 돌리고, 빠뜨린 검사까지 잡는다.

    python -B 공통/scripts/final_check.py "4_서면작성/사건/{사건명}" [--라운드 N] [--대상 "<서면초안.md 또는 담당자 저장본 docx>"]
    python -B 공통/scripts/final_check.py "1_검토의견/사건/{의뢰인}_{검토내용}" [--대상 "<검토의견서 docx 또는 회신초안.md>"]
    python -B 공통/scripts/final_check.py --최근 24          # 24시간 안에 손댄 사건마다(`/하자보완`)

검사마다 '통과'·'막힘'·'해당 없음'을 적고, 막힘이 하나라도 있으면 종료 코드 1 이다. 각 검사는 그 스크립트를 그대로 부른다
(규칙을 두 벌로 두지 않는다). 이 관문이 보는 것은 검사를 했는지와 판정 칸이 다 찼는지이다. 판정이 맞는지는 작성 세션이
원문을 읽고 정한다(`공통/자체검토.md` 4-1절).

서면(라운드의 출력/서면초안.md)
  문체           style_check.py 위반 0
  호증 번호      citation_check.py 위반 0
  판례 대조      인용이 있으면 작업/인용대조표.md 가 있고 cite_check.py 불일치 0
  판례 검색 기록 LBOX 목록(작업/LBOX_목록.tsv)·법제처 목록·작업/검색기록.md 가 있다(찾은 것을 남겼는가)
  찾은 판례 다시 훑기  작업/수확목록_재확인.md 의 낱말로 harvest_titles.py scan 을 다시 돌려, 걸린 줄이 모두 원고·대조표·검색기록에 있다
  대조표 칸      본문 인용 줄마다 자리·주문·결론·다른 사유·전제·확정·원문이 찼고, 판결이 아닌 자료(판정·재결·행정해석)는 원문 파일이 있으며,
                 미확정·확인 못한 판결은 7일 안에 다시 본 날짜가 있다(미확정 줄은 '참고'로 따로 보인다)
  판결문 PDF     본문 인용 판결이 있으면 참고자료/인용판결_PDF 가 있고 cite_pdf_check.py 문제 0, '사람 판정' 표가 본문 인용 줄마다
                 판단 부분인지·방향·사안 비교까지 찼고, '주의'(앞 글에 주장·원심·인정사실) 줄은 비고가 있다
  증거 인용      증거 인용이 있으면 작업/증거인용검토/ 의 review.json 이 초안보다 새것이고 notes.json 에 인용마다 판정이 있다
  증거 파악      evidence_read.py check — 모든 호증의 전 면 읽기 기록이 찼고 파일이 그 뒤 바뀌지 않았다
  빠진 문구      evidence_words.py --확인 — 쟁점 낱말 대조표가 있고, 서면이 인용하지 않은 면마다 '판단'이 있다
  상대 서면      상대증거/ 에 상대방 서면이 있으면 작업/상대주장_맞대기.md 가 있고 판정 칸이 다 찼고 초안보다 새것이다
  의뢰인 주장    작업/의뢰인주장_대조.md 가 있으면 '반영' 칸이 다 찼다
  DOCX           9-2단계(`--대상 docx`)와 밤 점검에서, 병합한 서면 docx 가 서면초안.md 보다 낡지 않았다(8-1단계는 병합 전이라 보지 않는다)
  서증 압축      출력/제출/ 에 서증 압축파일이 있으면 evidence_zip.py --확인
검토의견(사건 폴더의 검토의견서 docx 또는 회신초안.md)
  판례 대조·판결문 PDF   위와 같다(작업/인용대조표.md, 작업/인용판결_PDF)
  자료 파악      evidence_read.py check --자료 — 사건 폴더의 의뢰인 자료마다 전 면 읽기 기록
  문체           루트 CLAUDE.md 가 쓰지 말라고 한 낙관 표현과 '적다'(→ 기재하다)

2026. 11. 2. 담당 노무사 "노동사건자동화는 결국 문체, 증거, 판례 세 가지에 어떠한 하자도 없어야", "모든 자동화 시스템에 최종 재검토
완결성 100%로". GGM 사 제6호증 3면을 첫 면만 읽어 놓친 일이 인용 대조·맞대기·통독을 모두 지나갔다. 그 검사들은 서면에 쓴 것이
원문과 맞는지만 보고, 서면에 빠진 것(읽지 않은 면, 판정하지 않은 줄)은 보지 않았다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
S4 = ROOT / '4_서면작성' / 'scripts'
SC = ROOT / '공통' / 'scripts'
sys.path.insert(0, str(SC))
import system as _system          # noqa: E402  사건번호 정규식은 한 벌만 둔다

CASE_NO = re.compile(_system.CASE_NUMBER)
EVIDENCE_REF = re.compile(r'(' + _system.EVIDENCE_PREFIX + r')\s*제\s*\d+\s*호증')
낙관 = ('다툴 실익이 충분', '인정될 가능성이 높', '유력하', '승소 가능성이 높', '이길 가능성이 높')
적다 = re.compile(r'적(?:혀|어)\s*있|적었|적은\s*바|적고\s*있')
산출물_이름 = re.compile(r'(-회신초안|-간이안)\.md$|관련 검토_|_수정\(|_최종|_Rev_\d|_초안\.(?:docx|pdf)$|_간이안\.(?:docx|pdf)$')


def RUN(args: list) -> tuple:
    """검사 스크립트를 부른다. (종료 코드, 출력)"""
    try:
        r = subprocess.run([sys.executable, '-B'] + [str(a) for a in args], capture_output=True, timeout=3600,
                           cwd=str(ROOT), env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    except subprocess.TimeoutExpired:
        return 1, '시간 초과'
    out = (r.stdout or b'').decode('utf-8', 'replace') + (r.stderr or b'').decode('utf-8', 'replace')
    return r.returncode, out


class 결과:
    def __init__(self):
        self.줄 = []

    def add(self, 이름, 상태, 말=''):
        self.줄.append((이름, 상태, 말.strip()))

    def run(self, 이름, args, 통과말='', 없음말=None):
        """종료 코드 0 은 통과, 없음말을 주면 2(대상 없음)는 해당 없음, 그 밖은 막힘."""
        code, out = RUN(args)
        tail = '\n'.join(l for l in out.strip().splitlines()[-12:])
        if code == 2 and 없음말 is not None:
            self.add(이름, '해당 없음', 없음말)
        else:
            self.add(이름, '통과' if code == 0 else '막힘', 통과말 if code == 0 else tail)
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


def 본문_줄(table: Path) -> list:
    """대조표의 본문 인용 줄(번호 칸에 '참고'·'뺌'이 없는 줄)."""
    sys.path.insert(0, str(SC))
    import cite_check
    return [r for r in cite_check.table_rows(str(table)) if not any(w in r.get('번호', '') for w in ('참고', '뺌'))]


def 사람판정_빈(table: Path, report: Path) -> list:
    """판결 본문 인용 줄(cite_pdf_check 가 보는 줄)마다 '사람 판정' 표에 판단 부분인지·방향·사안 비교가 있는지,
    'PDF 의 자리'에 '주의'(앞 글에 주장·원심·인정사실 등)가 붙은 줄은 비고가 있는지. 빠진 줄을 '줄(빠진 칸)'로 돌려준다."""
    want = [r.get('번호', '').strip() for r in 본문_줄(table) if '법원' in r.get('사건 표시', '')]
    if not report.is_file():
        return [f'{n}(표 없음)' for n in want]
    판정 = {}
    for head, rs in 표들(절_글(report.read_text(encoding='utf-8'), '사람 판정')):
        def 칸(말):
            return next((i for i, h in enumerate(head) if 말 in h), None)
        i줄 = next((i for i, h in enumerate(head) if h in ('줄', '번호') or h.startswith('줄')), 0)
        칸들 = {'판단 부분인지': 칸('판단'), '방향': 칸('방향'), '사안 비교': 칸('사안')}
        i자리, i비고 = 칸('자리'), 칸('비고')
        for r in rs:
            빠짐 = [이름 for 이름, i in 칸들.items() if i is None or not r[i].strip()]
            if i자리 is not None and '주의' in r[i자리] and (i비고 is None or not r[i비고].strip()):
                빠짐.append('비고(주의 줄)')
            판정[r[i줄].strip()] = 빠짐
    return [f"{n}({', '.join(판정[n]) if n in 판정 else '줄 없음'})" for n in want if 판정.get(n, ['줄 없음'])]


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
        원문 = r.get('원문', '')
        파일 = re.findall(r'`([^`]+)`', 원문)
        if '법원' not in r.get('사건 표시', '') and not any((table.parent / f).exists() or (ROOT / f).exists() for f in 파일):
            막.append(f"{n}: 원문 파일이 없다(법제처 본문이나 화면 글을 파일로 받아 '원문' 칸에 경로를 적는다)")
        확정 = r.get('확정', '')
        if re.search(r'미확정|미확인|확인 못|모름|계속 중|상고 중|항소 중', 확정):
            본날 = max(날짜들(확정), default=None)
            미확정.append(f"{n} {r.get('사건 표시', '')[:40]} — {확정[:40]}")
            if not 본날 or (오늘 - 본날).days > 7:
                막.append(f"{n}: 확정되지 않았거나 확인하지 못한 판결은 넘기기 전에 다시 보고 본 날짜를 적는다(마지막 {본날 or '날짜 없음'})")
    return 막, 미확정


def 인용_있나(text: str) -> bool:
    return bool(CASE_NO.search(text))


def 글(p: Path) -> str:
    """산출물의 글. docx 는 review_text.py 로 본문과 각주를 함께 뽑는다(판례 번호가 각주에 있다)."""
    if p.suffix.lower() == '.docx':
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / '글.md'
            RUN([SC / 'review_text.py', p, '--out', out])
            return out.read_text(encoding='utf-8', errors='replace') if out.is_file() else ''
    return p.read_text(encoding='utf-8', errors='replace')


# ---------------------------------------------------------------- 판례(두 계열 같다)
def 검색_완결(res: 결과, 폴더: Path):
    """찾지 않은 판례: 검색 기록(LBOX·법제처 목록, 검색기록)이 남았고, 받아 둔 목록에서 사안 고유어가 걸린 줄을 모두 가렸는가."""
    작업 = 폴더 / '작업'
    없는것 = [이름 for 이름, 있나 in (('작업/LBOX_목록.tsv', any(폴더.rglob('LBOX_목록.tsv'))),
                                    ('법제처_목록.json', any(폴더.rglob('법제처_목록.json'))),
                                    ('검색기록.md', (작업 / '검색기록.md').is_file() or (폴더 / '검색기록.md').is_file())) if not 있나]
    res.add('판례 검색 기록', '막힘' if 없는것 else '통과',
            ('없다: ' + ', '.join(없는것) + ' (`lbox-검색` 4·7항, `법제처-검색`)') if 없는것 else 'LBOX·법제처 목록과 검색기록 있음')
    재확인 = 작업 / '수확목록_재확인.md'
    if not 재확인.is_file():
        res.add('찾은 판례 다시 훑기', '막힘', f'수확 목록 재확인(harvest_titles.py scan)을 하지 않았다: {재확인}')
        return
    m = re.search(r'^낱말:[ \t]*(.+)$', 재확인.read_text(encoding='utf-8'), re.M)
    낱말 = [w.strip() for w in m.group(1).split(', ') if w.strip()] if m else []
    if not 낱말:
        res.add('찾은 판례 다시 훑기', '막힘', f'재확인 보고서에 낱말이 없다: {재확인}')
        return
    import tempfile
    with tempfile.TemporaryDirectory() as d:          # 같은 낱말로 지금 기록과 다시 맞댄다(LBOX 에는 요청하지 않는다)
        out = Path(d) / '재확인.md'
        RUN([SC / 'harvest_titles.py', 'scan', 폴더, '--낱말', *낱말, '--out', out])
        t = out.read_text(encoding='utf-8') if out.is_file() else ''
    n = re.search(r'없음 (\d+)건', t)
    빠짐 = int(n.group(1)) if n else -1
    줄 = 절_글(t, '기록에 없는 줄')
    번호 = [r[1] for head, rows in 표들(줄) for r in rows if len(r) > 6 and r[6] == '없음'][:15]
    if 빠짐 != 0:
        res.add('찾은 판례 다시 훑기', '막힘',
                (f'받아 둔 목록에서 낱말이 걸렸는데 원고·대조표·검색기록 어디에도 없는 줄 {빠짐}건: ' + ', '.join(번호) +
                 ' — 본문을 읽고 반영하거나 검색기록 유사 사례 표에 미반영 이유를 적는다') if 빠짐 > 0 else '다시 훑기를 돌리지 못했다')
    else:
        res.add('찾은 판례 다시 훑기', '통과', f"낱말 {', '.join(낱말)} — 걸린 줄 모두 기록에 있음")


def 판례(res: 결과, 대상: Path, table: Path, pdfdir: Path, 폴더: Path):
    text = 글(대상)
    if not table.is_file():
        if 인용_있나(text):
            res.add('판례 대조', '막힘', f'산출물에 사건번호가 있는데 대조표가 없다: {table}')
        else:
            res.add('판례 대조', '해당 없음', '사건번호 없음')
        return
    res.run('판례 대조', [SC / 'cite_check.py', table, '--target', 대상], '불일치 0')
    막, 미확정 = 대조표_칸(table)
    res.add('대조표 칸(실존·해석·확정)', '막힘' if 막 else '통과', '; '.join(막[:12]) if 막 else '본문 인용 줄의 칸이 모두 찼다')
    if 미확정:
        res.add('미확정·확인 못한 판결', '참고', '보고에 적고 제출 전에 다시 본다: ' + '; '.join(미확정[:8]))
    검색_완결(res, 폴더)
    sys.path.insert(0, str(SC))
    import cite_check
    본문줄 = [r for r in 본문_줄(table) if '법원' in r.get('사건 표시', '')]
    if not 본문줄:
        res.add('판결문 PDF', '해당 없음', '본문 인용 판결 없음')
        return
    if not pdfdir.is_dir():
        res.add('판결문 PDF', '막힘', f'판결문 PDF 폴더가 없다(`lbox-검색` 9항으로 받는다): {pdfdir}')
        return
    report = table.parent / '판결원문_PDF대조.md'
    if res.run('판결문 PDF', [SC / 'cite_pdf_check.py', table, pdfdir, '--out', report, '--target', 대상], '문제 0') == 0:
        빈 = 사람판정_빈(table, report)
        res.add('판결 판단 부분·방향·사안 비교', '막힘' if 빈 else '통과',
                (f"'사람 판정' 표에서 빈 줄: {', '.join(빈[:12])} ({report})") if 빈 else f'{len(본문줄)}줄 판정')


# ---------------------------------------------------------------- 서면
def 최근_라운드(사건: Path):
    rs = sorted((p for p in 사건.glob('라운드*') if p.is_dir()), key=lambda p: int(re.sub(r'\D', '', p.name) or 0))
    return rs[-1] if rs else None


def 상대_서면(라운드: Path) -> list:
    sys.path.insert(0, str(S4))
    import importlib.util
    spec = importlib.util.spec_from_file_location('evidence_cite_review', S4 / 'evidence_cite_review.py')
    ecr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ecr)
    d = 라운드 / '상대증거'
    if not d.is_dir():
        return []
    return [p for p in d.iterdir() if p.is_file() and not p.name.startswith('~$')
            and p.suffix.lower() in ('.pdf', '.docx', '.hwp', '.hwpx') and not ecr.file_key(p.name)]


def 서면(사건: Path, 라운드번호=None, 대상=None, 초안없음_허용=False) -> 결과:
    res = 결과()
    라운드 = 사건 / f'라운드{라운드번호}' if 라운드번호 else 최근_라운드(사건)
    if not 라운드 or not 라운드.is_dir():
        res.add('초안', '막힘', f'라운드 폴더가 없다: {사건}')
        return res
    초안 = 라운드 / '출력' / '서면초안.md'
    if not 초안.is_file():
        if 초안없음_허용:       # 밤 점검: 증거만 새로 받은 사건이면 읽기 기록만 본다
            res.add('초안', '해당 없음', f'{라운드.name} 초안 없음')
            res.run('증거 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건], '모든 호증 기록 완료', '호증 없음')
            return res
        res.add('초안', '막힘', f'초안이 없다: {초안}')
        return res
    대상 = Path(대상) if 대상 else 초안
    작업 = 라운드 / '작업'
    res.run('문체', [S4 / 'style_check.py', 대상], '위반 0')
    res.run('호증 번호', [S4 / 'citation_check.py', 대상], '목록에 없는 호증 0')
    판례(res, 대상, 작업 / '인용대조표.md', 라운드 / '참고자료' / '인용판결_PDF', 라운드)

    본문 = 초안.read_text(encoding='utf-8', errors='replace')
    if EVIDENCE_REF.search(본문.split('\n---\n')[0]):
        rj, nj = 작업 / '증거인용검토' / 'review.json', 작업 / '증거인용검토' / 'notes.json'
        if not rj.is_file():
            res.add('증거 인용', '막힘', f'증거 인용 대조를 하지 않았다(evidence_cite_review.py scan): {rj}')
        elif rj.stat().st_mtime + 1 < 초안.stat().st_mtime:
            res.add('증거 인용', '막힘', '초안을 고친 뒤 증거 인용 대조(scan)를 다시 하지 않았다')
        else:
            items = json.loads(rj.read_text(encoding='utf-8'))
            notes = json.loads(nj.read_text(encoding='utf-8')) if nj.is_file() else {}
            빈 = [str(r.get('n')) for r in items if not (notes.get(str(r.get('n'))) or [''])[0]]
            res.add('증거 인용', '막힘' if 빈 else '통과',
                    f'notes.json 에 판정이 없는 인용 {len(빈)}건: {", ".join(빈[:20])}' if 빈 else f'{len(items)}건 판정')
    else:
        res.add('증거 인용', '해당 없음', '본문에 증거 인용 없음')

    if res.run('증거 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건], '모든 호증 기록 완료', '호증 없음') == 2:
        res.add('빠진 문구(쟁점 낱말)', '해당 없음', '호증 없음')
    else:
        res.run('빠진 문구(쟁점 낱말)', [S4 / 'evidence_words.py', 사건, '--라운드', re.sub(r'\D', '', 라운드.name), '--확인'], '판단 빈 줄 0')

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
                res.add('상대 서면 맞대기', '막힘', '초안을 고친 뒤 맞대기 표를 다시 보지 않았다(고친 목을 다시 맞대고 표를 고친다)')
            else:
                res.add('상대 서면 맞대기', '통과', f'{전체}줄 판정')
    else:
        res.add('상대 서면 맞대기', '해당 없음', '이 라운드 상대증거/ 에 상대방 서면 없음')

    대조 = 작업 / '의뢰인주장_대조.md'
    if 대조.is_file():
        빈, 전체 = 빈_판정(대조, ('반영',))
        res.add('의뢰인 주장', '막힘' if 빈 else '통과', f"'반영' 칸이 빈 줄 {빈}/{전체}" if 빈 else f'{전체}줄 반영 표시')
    else:
        res.add('의뢰인 주장', '해당 없음', '의뢰인주장_대조.md 없음')

    # 병합한 서면(3-1절 이름. 서면_프레임.docx 는 아니다). 8-1단계는 병합 전에 돌리므로 그때는 보지 않고,
    # 9-2단계(--대상 docx)와 밤 점검에서 초안을 고친 뒤 병합하지 않은 판을 잡는다
    docxs = [p for p in (라운드 / '출력').glob('*.docx')
             if not p.name.startswith('~$') and re.search(r'(_초안|_Rev_\d+|_최종|^최종서면)\.docx$', p.name)]
    병합본 = 대상 if 대상.suffix.lower() == '.docx' else (max(docxs, key=lambda p: p.stat().st_mtime) if docxs and 초안없음_허용 else None)
    if 병합본 is None:
        res.add('DOCX', '해당 없음', '병합 전에 돌림(9-2단계에서 `--대상 "{docx}"` 로 다시 돌린다)' if docxs else '아직 병합 전')
    elif 초안.stat().st_mtime > 병합본.stat().st_mtime + 1:
        res.add('DOCX', '막힘', f'서면초안.md 를 고친 뒤 병합하지 않았다: {병합본.name}')
    else:
        res.add('DOCX', '통과', 병합본.name)

    제출 = 라운드 / '출력' / '제출'
    if list(제출.glob('*_서증.zip')):
        res.run('서증 압축', [S4 / 'evidence_zip.py', 제출, '--확인'], '증거/ 와 같다')
    else:
        res.add('서증 압축', '해당 없음', '제출 묶음 압축파일 없음')
    return res


# ---------------------------------------------------------------- 검토의견
def 검토의견(사건: Path, 대상=None, 초안없음_허용=False) -> 결과:
    res = 결과()
    if 대상:
        대상 = Path(대상)
    else:
        후보 = [p for p in 사건.iterdir() if p.is_file() and not p.name.startswith('~$')
              and (re.search(r'관련 검토_.*\.docx$', p.name) or p.name.endswith('-회신초안.md') or p.name.endswith('-간이안.md'))]
        대상 = max(후보, key=lambda p: p.stat().st_mtime) if 후보 else None
    if not 대상 or not 대상.is_file():
        res.add('산출물', '해당 없음' if 초안없음_허용 else '막힘', f'검토의견서·회신초안이 없다: {사건}')
        if 초안없음_허용:
            res.run('자료 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건, '--자료', 사건], '자료 기록 완료', '자료 없음')
        return res
    간이 = '간이안' in 대상.name
    판례(res, 대상, 사건 / '작업' / ('인용대조표_간이안.md' if 간이 else '인용대조표.md'), 사건 / '작업' / '인용판결_PDF', 사건)
    res.run('자료 파악(전 면 읽기)', [S4 / 'evidence_read.py', 'check', 사건, '--자료', 사건], '의뢰인 자료 기록 완료',
            '사건 폴더에 의뢰인 자료 없음')
    text = 글(대상)
    걸림 = [w for w in 낙관 if w in text] + [m.group(0) for m in 적다.finditer(text)]
    res.add('문체(낙관 표현·적다)', '막힘' if 걸림 else '통과',
            ('쓰지 않는 표현: ' + ', '.join(dict.fromkeys(걸림))) if 걸림 else '낙관 표현·적다 없음')
    return res


# ---------------------------------------------------------------- 명령
def 사건_종류(사건: Path) -> str:
    parts = 사건.resolve().parts
    if '4_서면작성' in parts:
        return '서면'
    if '1_검토의견' in parts:
        return '검토의견'
    return '서면' if any(사건.glob('라운드*')) else '검토의견'


def 최근_사건(시간: float) -> list:
    """시간(시) 안에 파일을 고친 사건 폴더. 면별 글·문자인식 캐시는 세지 않는다."""
    끝 = time.time() - 시간 * 3600
    out = []
    for 폴더 in ('4_서면작성', '1_검토의견'):
        base = ROOT / 폴더 / '사건'
        if not base.is_dir():
            continue
        for c in sorted(base.iterdir()):
            if not c.is_dir() or c.name.startswith('_'):
                continue
            for dp, dn, fn in os.walk(c):
                if any(x in Path(dp).parts for x in ('호증글자', 'ocr', '백업')):
                    continue
                if any(os.path.getmtime(os.path.join(dp, f)) >= 끝 for f in fn if not f.startswith('~$')):
                    out.append(c)
                    break
    return out


def 보고(사건: Path, res: 결과) -> str:
    줄 = [f'## {사건.name} ({사건_종류(사건)}) — 막힘 {len(res.막힘)}', '', '| 검사 | 결과 | 내용 |', '|---|---|---|']
    for 이름, 상태, 말 in res.줄:
        한줄 = re.sub(r'\s+', ' ', 말).replace('|', '｜')[:400]
        줄.append(f'| {이름} | {상태} | {한줄} |')
    return '\n'.join(줄) + '\n'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='넘기기 전 마지막 관문(문체·판례·증거)')
    ap.add_argument('case', nargs='?')
    ap.add_argument('--라운드', type=int)
    ap.add_argument('--대상', help='맞댈 산출물(담당자 저장본 위의 수정안이면 그 docx)')
    ap.add_argument('--최근', type=float, help='이 시간(시) 안에 손댄 사건마다 돌린다')
    ap.add_argument('--out', help='보고를 이 md 파일에도 쓴다')
    a = ap.parse_args(argv)
    if a.최근:
        사건들 = 최근_사건(a.최근)
    elif a.case:
        사건들 = [Path(a.case)]
    else:
        ap.error('사건 폴더나 --최근 을 준다')
    글들, 막힘 = [], 0
    for c in 사건들:
        밤 = bool(a.최근)
        res = 서면(c, a.라운드, a.대상, 밤) if 사건_종류(c) == '서면' else 검토의견(c, a.대상, 밤)
        막힘 += len(res.막힘)
        글들.append(보고(c, res))
        print(글들[-1])
    if a.최근 and not 사건들:
        print(f'{a.최근:g}시간 안에 손댄 사건이 없다.')
    print(f'사건 {len(사건들)}건, 막힘 {막힘}건' + ('' if 막힘 or not 사건들 else ' — 넘겨도 된다(판정의 옳고 그름은 작성 세션이 원문으로 본다)'))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text('\n'.join(글들), encoding='utf-8')
    return 1 if 막힘 else 0


if __name__ == '__main__':
    raise SystemExit(main())
