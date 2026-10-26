"""노동위원회 심문회의 준비 서류를 한글 양식에 채워 만든다(`/노동위서류`).

심문일정 통지를 받으면 내는 서류 세 가지를 사건 폴더의 지시표 하나로 만든다.

    참석자명단   심문회의 참석자 명단(노동위원회규칙 제52조 제3항, 별지 제12호서식)
    지정서       담당변호사(노무사) 추가 지정서(사무소 양식. 법무법인이 위임받은 사건에 담당자를 더할 때 낸다)
    선임신고서   대리인 선임신고서(노동위원회규칙 제36조 제2항, 별지 제8호서식)

    # 1) 지시표를 사건 폴더에 만든다(이미 있으면 그대로 둔다)
    python -B 4_서면작성/scripts/nlrc_forms.py init "4_서면작성/사건/{사건명}/라운드N"
    # 2) 지시표(라운드N/작업/노동위서류.json)를 채운 뒤 서류를 만든다
    python -B 4_서면작성/scripts/nlrc_forms.py build "4_서면작성/사건/{사건명}/라운드N"
    python -B 4_서면작성/scripts/nlrc_forms.py build "…/라운드N" --only 참석자명단
    # 한글 문서의 글·개체·칸 이름을 살펴본다(고치지 않는다)
    python -B 4_서면작성/scripts/nlrc_forms.py look "어떤 문서.hwp" --cells

양식은 `4_서면작성/templates/노동위원회/` 에 있다. 지정서와 선임신고서 양식에는 사무소 직인 그림이 들어 있어
git 에 올리지 않는다(.gitignore 가 hwp·hwpx 를 형식으로 막는다). OneDrive 로만 두 PC에 옮겨진다.

한글 자동화(HWPFrame.HwpObject)를 쓰므로 한글과 보안 모듈이 있는 Windows PC에서만 돈다. 양식은 고치지 않고
임시 폴더의 사본을 열어 채운 뒤 `라운드N/출력/` 에 hwp(x)와 PDF 로 낸다. 확인용 첫 면 그림은
`라운드N/작업/노동위서류_확인/` 에 쓴다(사건 폴더 안이어서 git 이 무시한다).

만든 뒤 스스로 확인한다. 참석자 명단은 저장본(hwpx)을 다시 읽어 칸마다 넣은 글과 맞대고, 지정서와 선임신고서는
채울 자리 표시(〔 〕)가 남지 않았는지, 넣은 글(대리하는 쪽에 맞는 본문 문장과 √ 줄 포함)이 들어 있는지, 한 면인지
본다. 어긋나면 파일을 내지 않고 실패한다.

알아 둘 것(2026. 10. 14. GGM 정직 3월 사건에서 확인):
 - 누름틀 여러 개로 나뉜 글은 이어진 글로 찾아지지 않는다. 양식의 채울 자리는 누름틀을 없앤 보통 글이다.
 - 한글의 '모두 바꾸기'는 바뀌어도, 못 바꾸어도 같은 값을 돌려준다. 바꾼 뒤 문서의 글을 다시 읽어 확인한다.
   지정서 본문의 '사용자'와 선임신고서의 당사자 지위 줄은 누름틀·조판 부호로 나뉘어 있어 낱말로는 바뀌지 않으므로
   대리하는 쪽에 맞는 글을 지어 문단을 통째로 바꾼다(근로자 쪽 지시표로 처음 돌렸을 때 오류 없이 사용자로 남았다).
 - 지정서는 표 하나가 한 면을 채우고 직인 그림이 면에 고정되어 있다. 사건 글이 두 줄이 되면 표가 통째로
   다음 면으로 넘어가므로, 한 면을 넘으면 사건 문단의 장평을 5%씩 줄여 한 줄에 맞춘다.
 - 참석자 줄은 병합된 '당사자 지위' 칸이 함께 늘어나도록 가운데 줄 아래에 넣는다.

참석자 명단의 제출자 도장(2026. 10. 26. 담당 노무사 "제출자 최락보인건 내 도장 저번에 보여준거 찍어주면 됨"):
 - 지시표의 `참석자명단.도장` 에 적은 그림(투명 PNG)을 '(서명 또는 날인)' 위에 글 앞으로 찍는다. 사람의 도장이어서
   OneDrive·git 에 두지 않고 PC마다 `%LOCALAPPDATA%\\노동사건자동화\\도장\\` 에 둔다. 비우면 찍지 않는다.
 - 그림은 제출자 줄 위의 날짜 문단에 맨다(문단 기준 위치는 그 문단 위쪽으로 올라가지 못한다). PDF 로 내보내 그림과
   '(서명 또는 날인)'의 자리를 재고 어긋난 만큼 옮기기를 되풀이한다(선임신고서 양식에 직인을 넣을 때와 같은 방법).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / '4_서면작성' / 'templates' / '노동위원회'
SPEC_NAME = '노동위서류.json'
SAMPLE_SPEC = '지시표_본보기.json'
KINDS = ('참석자명단', '지정서', '선임신고서')
SIDES = ('근로자', '노동조합', '사용자')
TEMPLATE_FILES = {'참석자명단': '양식_심문회의 참석자 명단.hwpx',
                  '지정서': '양식_담당노무사 추가 지정서.hwp',
                  '선임신고서': '양식_대리인 선임신고서.hwp'}
HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
# 별지 제12호서식의 당사자 지위 칸과 별지 제8호서식의 당사자 지위 줄에 적힌 글자 그대로이다
ATTENDEE_SIDE_TEXT = {'근로자': '[  ] 근 로 자', '노동조합': '[  ] 노동조합', '사용자': '[  ] 사 용 자'}
FIRST_ATTENDEE_ROW = 7          # 양식에서 참석자 첫 줄의 칸 이름(C7·D7·E7)
BLANK = '〔'
# 제출자 개인 도장 그림. 사람의 도장이어서 OneDrive·git·사건 폴더에 두지 않고 PC마다 이 폴더에 둔다
SEAL_DIR = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / '노동사건자동화' / '도장'
SEAL_MM = 13.0                  # 2026. 10. 22. 이승민 의견진술신청서의 '(서명 또는 인)'에 찍은 크기
SEAL_DROP = 2.0                 # 도장 가운데를 '(서명 또는 날인)' 줄 가운데보다 이만큼(점) 아래에 둔다
SIGN_MARK = '(서명 또는 날인)'


class FormError(Exception):
    """지시표나 양식이 맞지 않아 서류를 만들 수 없다."""


# ── 지시표 ──────────────────────────────────────────────────────────────────

def load_spec(round_dir: Path) -> dict:
    path = round_dir / '작업' / SPEC_NAME
    if not path.is_file():
        raise FormError('지시표가 없습니다: %s (init 으로 만든다)' % path)
    spec = json.loads(path.read_text(encoding='utf-8-sig'))
    for key in ('의뢰인', '노동위원회', '사건', '우리쪽', '당사자'):
        if not spec.get(key):
            raise FormError('지시표에 %r 이 비어 있습니다.' % key)
    if spec['우리쪽'] not in SIDES:
        raise FormError("'우리쪽'은 %s 가운데 하나입니다." % '·'.join(SIDES))
    if not (spec['당사자'].get('이름') or '').strip():
        raise FormError("지시표의 당사자 '이름'이 비어 있습니다.")
    return spec


def output_stem(spec: dict, kind: str) -> str:
    """파일 이름(확장자 없이). `({의뢰인}) {서류명}_초안` — 4_서면작성/CLAUDE.md 3-1절의 이름 규칙."""
    title = {'참석자명단': '심문회의 참석자 명단',
             '지정서': '%s 추가 지정서' % (spec.get('지정서') or {}).get('구분', '담당노무사'),
             '선임신고서': '대리인 선임신고서'}[kind]
    stage = spec.get('판', '초안')
    return '(%s) %s%s' % (spec['의뢰인'], title, '_' + stage if stage else '')


def designation_sentence(spec: dict) -> str:
    role = (spec.get('지정서') or {}).get('구분', '담당노무사')
    return '위 사건에 관하여 이 사건 %s의 대리인인 당 법무법인은 아래 %s를 추가 지정합니다.' % (spec['우리쪽'], role)


def appointment_side_line(side: str) -> str:
    """별지 제8호서식의 당사자 지위 줄. 양식의 글자와 빈칸 수 그대로이고 √ 자리만 다르다."""
    mark = {s: '[√]' if s == side else '[  ]' for s in SIDES}
    return '  %s근로자       %s 노동조합      %s사용자   (해당란에 √표시)' % (mark['근로자'], mark['노동조합'], mark['사용자'])


def designation_ops(spec: dict) -> list[tuple]:
    """지정서 양식에 할 일. 양식은 사용자 쪽을 대리하는 모양(사용자 줄에 ✓)이다.

    근로자·노동조합 쪽을 대리하면 ✓가 있는 줄의 이름표를 바꾼다(줄의 차례는 뜻이 없다). 이름표를 바꾸는 일은
    채울 자리에 사건·당사자 글을 넣기 전에 한다(그 글에 '근로자'·'사용자'가 들어 있을 수 있다).
    """
    part = spec.get('지정서') or {}
    role = part.get('구분', '담당노무사')
    if role not in ('담당노무사', '담당변호사'):
        raise FormError("지정서의 '구분'은 담당노무사 또는 담당변호사입니다.")
    if not part.get('성명'):
        raise FormError("지정서의 '성명'이 비어 있습니다.")
    side = spec['우리쪽']
    ops: list[tuple] = []
    if side != '사용자':
        ops += [('para', '근로자', '〔다른쪽〕'), ('para', '사용자', side), ('replace', '〔다른쪽〕', '사용자')]
    # 본문 문장의 '사용자'는 누름틀이어서 이어진 글로 바뀌지 않는다. 문장을 지어 문단을 통째로 바꾼다
    ops.append(('para', '위 사건에 관하여', designation_sentence(spec)))
    if role != '담당노무사':
        ops.append(('replace', '담당노무사', role))
    ops += [('replace', '〔사건〕', spec['사건']),
            ('replace', '〔사용자〕', spec['당사자']['이름']),
            ('replace', '〔성명〕', part['성명']),
            ('replace', '〔날짜〕', part.get('날짜') or '    .     .     .'),
            ('replace', '〔노동위원회〕', spec['노동위원회']),
            ('fit', spec['사건'][:12], '')]
    return ops


def appointment_ops(spec: dict) -> list[tuple]:
    """선임신고서 양식에 할 일. 위임인 전화를 적지 않으면 주소 문단을 통째로 바꾸어 전화 칸을 없앤다."""
    part = spec.get('선임신고서') or {}
    party = spec['당사자']
    if not party.get('주소'):
        raise FormError("선임신고서에는 당사자 '주소'가 필요합니다.")
    for key in ('담당', '신고인'):
        if not part.get(key):
            raise FormError('선임신고서의 %r 이 비어 있습니다.' % key)
    name = ' '.join(x for x in (party['이름'], party.get('대표자', '')) if x)
    ops: list[tuple] = [('replace', '〔사건〕', part.get('사건표기') or spec['사건']), ('replace', '〔위임인〕', name)]
    if party.get('전화'):
        ops += [('replace', '〔위임인 주소〕', party['주소']), ('replace', '〔위임인 전화〕', party['전화'])]
    else:
        ops.append(('para', '〔위임인 주소〕', ' ' + party['주소']))
    if spec['우리쪽'] != '사용자':
        # 양식은 사용자에 √가 있다. 이 줄은 조판 부호로 나뉘어 있어 낱말로 바뀌지 않으므로 문단을 통째로 바꾼다
        ops.append(('para', '해당란에', appointment_side_line(spec['우리쪽'])))
    ops += [('replace', '〔담당〕', part['담당']),
            ('replace', '〔날짜〕', part.get('날짜') or '    년      월      일'),
            ('replace', '〔신고인〕', part['신고인']),
            ('replace', '〔노동위원회〕', spec['노동위원회'])]
    return ops


def seal_file(part: dict) -> Path | None:
    """참석자 명단 제출자의 도장 그림. 지시표에 '도장'이 없으면 찍지 않는다."""
    name = (part.get('도장') or '').strip()
    if not name:
        return None
    if '/' in name or '\\' in name:
        raise FormError("참석자명단의 '도장'에는 파일 이름만 적습니다(그림은 %s 에 둔다): %r" % (SEAL_DIR, name))
    filer = (part.get('제출자') or '').replace(' ', '')
    if filer and filer not in Path(name).stem:
        raise FormError("제출자(%s)와 도장(%s)이 다릅니다. 제출자의 도장으로 바꾸거나 도장을 비웁니다." % (part['제출자'], name))
    path = SEAL_DIR / name
    if not path.is_file():
        raise FormError('도장 그림이 이 PC 에 없습니다: %s (다른 PC 의 같은 자리에서 옮겨 두거나, 지시표의 도장을 비우면 찍지 않는다)' % path)
    return path


def expected_texts(spec: dict, kind: str) -> list[str]:
    """만든 문서에 들어 있어야 할 글."""
    if kind == '지정서':
        part = spec['지정서']
        return [spec['사건'], spec['당사자']['이름'], part['성명'], spec['노동위원회'], designation_sentence(spec)]
    part = spec['선임신고서']
    return [part.get('사건표기') or spec['사건'], spec['당사자']['이름'], spec['당사자']['주소'],
            part['담당'], part['신고인'], spec['노동위원회'], appointment_side_line(spec['우리쪽']).strip()]


# ── 한글 자동화 ─────────────────────────────────────────────────────────────

def open_hwp():
    """새 한글 창을 띄운다. 이미 떠 있는 창은 쓰지 않는다(끝낼 때 내가 띄운 창만 닫는다)."""
    try:
        import win32com.client as win32
    except ImportError as exc:      # 리눅스·클라우드 세션
        raise FormError('한글 자동화는 Windows 에서만 됩니다(pywin32).') from exc
    hwp = win32.DispatchEx('HWPFrame.HwpObject')
    if not hwp.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModuleExample'):
        print('[주의] 보안 모듈이 등록되지 않아 파일 접근 창이 뜰 수 있습니다(뜨면 모두 허용).')
    if hwp.XHwpDocuments.Count != 1:
        hwp.Quit()
        raise FormError('새 한글 창이 아닙니다.')
    return hwp


def close_hwp(hwp) -> None:
    hwp.Clear(1)
    hwp.Quit()


def hwp_format(path: Path) -> str:
    return 'HWPX' if path.suffix.lower() == '.hwpx' else 'HWP'


def document_text(hwp) -> str:
    return (hwp.GetTextFile('TEXT', '') or '').replace('\r\n', '\n')


def insert_text(hwp, text: str) -> None:
    ps = hwp.HParameterSet.HInsertText
    hwp.HAction.GetDefault('InsertText', ps.HSet)
    ps.Text = text
    hwp.HAction.Execute('InsertText', ps.HSet)


def replace_all(hwp, old: str, new: str) -> None:
    ps = hwp.HParameterSet.HFindReplace
    hwp.HAction.GetDefault('AllReplace', ps.HSet)
    ps.FindString, ps.ReplaceString = old, new
    ps.IgnoreMessage, ps.FindType, ps.ReplaceMode = 1, 1, 1
    ps.Direction = hwp.FindDir('AllDoc')
    hwp.HAction.Execute('AllReplace', ps.HSet)      # 바뀌어도 False 를 돌려주므로 결과는 글로 확인한다


def find_first(hwp, text: str) -> bool:
    hwp.MovePos(2, 0, 0)                            # 문서 처음. 집 PC 한글은 인자를 다 주어야 한다(2026. 10. 26.)
    ps = hwp.HParameterSet.HFindReplace
    hwp.HAction.GetDefault('RepeatFind', ps.HSet)
    ps.FindString = text
    ps.IgnoreMessage, ps.FindType = 1, 1
    ps.Direction = hwp.FindDir('Forward')
    return bool(hwp.HAction.Execute('RepeatFind', ps.HSet))


def select_block(hwp, unit: str) -> None:
    """커서가 있는 문단('para')이나 칸('cell')의 내용을 모두 고른다."""
    hwp.HAction.Run('Cancel')
    hwp.HAction.Run('MoveParaBegin' if unit == 'para' else 'MoveListBegin')
    hwp.HAction.Run('MoveSelParaEnd' if unit == 'para' else 'MoveSelListEnd')


def run_ops(hwp, ops: list[tuple], pages: int = 1) -> None:
    for kind, old, new in ops:
        if old not in document_text(hwp):
            raise FormError('양식에서 찾을 글이 없습니다: %r' % old)
        if kind == 'replace':
            replace_all(hwp, old, new)
            if old not in new and old in document_text(hwp):
                # 글로는 이어져 보여도 누름틀이나 조판 부호로 나뉘어 있으면 바뀌지 않는다. 'para' 로 문단을 통째로 바꾼다
                raise FormError('바뀌지 않았습니다(누름틀로 나뉜 글일 수 있다): %r' % old)
        elif kind in ('para', 'cell'):
            if not find_first(hwp, old):
                raise FormError('양식에서 자리를 찾지 못했습니다: %r' % old)
            select_block(hwp, kind)
            hwp.HAction.Run('Delete')
            insert_text(hwp, new)
        elif kind == 'fit':
            for ratio in range(95, 65, -5):
                if hwp.PageCount <= pages:
                    break
                if not find_first(hwp, old):
                    raise FormError('장평을 맞출 문단을 찾지 못했습니다: %r' % old)
                select_block(hwp, 'para')
                cs = hwp.HParameterSet.HCharShape
                hwp.HAction.GetDefault('CharShape', cs.HSet)
                for script in ('Hangul', 'Latin', 'Hanja', 'Japanese', 'Other', 'Symbol', 'User'):
                    setattr(cs, 'Ratio' + script, ratio)
                hwp.HAction.Execute('CharShape', cs.HSet)
                hwp.HAction.Run('Cancel')
                print('  장평 %d%% → 면수 %d' % (ratio, hwp.PageCount))
        else:
            raise FormError('모르는 지시: %r' % kind)


def cell_map(hwp) -> dict[str, int]:
    """칸 이름(B3 …) → 목록 번호. 한글이 상태 줄에 보여 주는 칸 이름을 읽는다."""
    found: dict[str, int] = {}
    for index in range(2, 300):
        if not hwp.SetPos(index, 0, 0):
            break
        match = re.match(r'\((\w+)\)', str(hwp.KeyIndicator()[-1]))
        if not match:
            break
        found.setdefault(match.group(1), index)
    return found


def fill_cell(hwp, cells: dict[str, int], name: str, text: str, center: bool = False) -> None:
    if name not in cells:
        raise FormError('양식에 칸이 없습니다: %s' % name)
    hwp.SetPos(cells[name], 0, 0)
    select_block(hwp, 'cell')
    hwp.HAction.Run('Delete')
    if center:                                      # 양식의 빈 칸은 왼쪽 맞춤이다. 참석자 칸은 머리 칸처럼 가운데로 맞춘다
        hwp.HAction.Run('ParagraphShapeAlignCenter')
    if text:
        insert_text(hwp, text)


# ── 만들기 ──────────────────────────────────────────────────────────────────

def work_dir() -> Path:
    path = Path(tempfile.gettempdir()) / 'nlrc_forms'
    path.mkdir(exist_ok=True)
    return path


def template_path(kind: str) -> Path:
    path = TEMPLATES / TEMPLATE_FILES[kind]
    if not path.is_file():
        raise FormError('양식이 없습니다: %s (git 에 올리지 않는 파일이다. OneDrive 동기화를 확인한다)' % path)
    return path


def save_png(pdf: Path, png: Path) -> int:
    import pymupdf
    png.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(str(pdf)) as doc:
        doc[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(str(png))
        return doc.page_count


def deliver(spec: dict, kind: str, round_dir: Path, saved: Path, pdf: Path, problems: list[str]) -> None:
    stem = output_stem(spec, kind)
    pages = save_png(pdf, round_dir / '작업' / '노동위서류_확인' / (kind + '.png'))
    if pages != 1:
        problems.append('PDF 가 %d면입니다.' % pages)
    if problems:
        for f in (saved, pdf):
            f.unlink(missing_ok=True)
        raise FormError('%s: 확인에서 어긋나 파일을 내지 않았습니다 — %s' % (kind, ' / '.join(problems)))
    out_dir = round_dir / '출력'
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(saved, out_dir / (stem + saved.suffix))
    shutil.copyfile(pdf, out_dir / (stem + '.pdf'))
    for f in (saved, pdf):
        f.unlink(missing_ok=True)
    print('%s: %s%s · PDF 1면' % (kind, stem, saved.suffix))


def build_replaced(spec: dict, kind: str, round_dir: Path) -> None:
    """지정서·선임신고서: 양식의 채울 자리를 바꾸어 낸다."""
    ops = designation_ops(spec) if kind == '지정서' else appointment_ops(spec)
    template = template_path(kind)
    tmp = work_dir()
    work, saved, pdf = tmp / ('work' + template.suffix), tmp / ('out' + template.suffix), tmp / 'out.pdf'
    shutil.copyfile(template, work)
    hwp = open_hwp()
    try:
        if not hwp.Open(str(work), hwp_format(work), 'forceopen:true'):
            raise FormError('양식을 열지 못했습니다: %s' % template.name)
        run_ops(hwp, ops)
        text, pages = document_text(hwp), hwp.PageCount
        hwp.SaveAs(str(saved), hwp_format(saved), '')
        hwp.SaveAs(str(pdf), 'PDF', '')
    finally:
        close_hwp(hwp)
        work.unlink(missing_ok=True)
    problems = ['글이 없음: %r' % s for s in expected_texts(spec, kind) if s not in text]
    if BLANK in text:
        problems.append('채울 자리 표시(〔 〕)가 남았습니다.')
    if pages != 1:
        problems.append('한글 면수 %d' % pages)
    deliver(spec, kind, round_dir, saved, pdf, problems)


def read_saved_cells(path: Path) -> tuple[dict[tuple[int, int], str], int]:
    """저장한 hwpx 의 (줄, 칸) → 글, 표의 줄 수."""
    from lxml import etree
    with zipfile.ZipFile(path) as z:
        doc = etree.fromstring(z.read('Contents/section0.xml'))
    table = next(doc.iter('{%s}tbl' % HP))
    cells = {}
    for tc in table.iter('{%s}tc' % HP):
        addr = tc.find('{%s}cellAddr' % HP)
        text = '\n'.join(
            ''.join((t.text or '') + ''.join((k.tail or '') for k in t) for t in p.iter('{%s}t' % HP))
            for p in tc.iter('{%s}p' % HP))
        cells[(int(addr.get('rowAddr')), int(addr.get('colAddr')))] = text
    return cells, int(table.get('rowCnt'))


def seal_position(pdf: Path):
    """PDF 첫 면에서 (도장 그림 자리, '(서명 또는 날인)' 자리) — 점 단위."""
    import pymupdf
    side = SEAL_MM * 72 / 25.4
    with pymupdf.open(str(pdf)) as doc:
        page = doc[0]
        seals = [pymupdf.Rect(i['bbox']) for i in page.get_image_info() if abs(pymupdf.Rect(i['bbox']).width - side) < 3]
        marks = page.search_for(SIGN_MARK)
    if len(seals) != 1 or len(marks) != 1:
        raise FormError('도장 자리를 재지 못했습니다: 그림 %d개, %r %d곳' % (len(seals), SIGN_MARK, len(marks)))
    return seals[0], marks[0]


def seal_gap(pdf: Path) -> tuple[float, float]:
    """도장 가운데가 바라는 자리('(서명 또는 날인)' 가운데에서 SEAL_DROP 아래)에서 벗어난 만큼(점)."""
    seal, mark = seal_position(pdf)
    return ((mark.x0 + mark.x1) / 2 - (seal.x0 + seal.x1) / 2,
            (mark.y0 + mark.y1) / 2 + SEAL_DROP - (seal.y0 + seal.y1) / 2)


def stamp_seal(hwp, png: Path, anchor: str, pdf: Path) -> None:
    """도장 그림을 날짜 문단(anchor)에 매어 글 앞으로 넣고 '(서명 또는 날인)' 위로 옮긴다."""
    if not find_first(hwp, anchor):
        raise FormError('도장을 맬 날짜 문단을 찾지 못했습니다: %r' % anchor)
    hwp.HAction.Run('Cancel')
    hwp.HAction.Run('MoveParaBegin')
    ctrl = hwp.InsertPicture(str(png), True, 1, False, False, 0, SEAL_MM, SEAL_MM)
    if ctrl is None:
        raise FormError('도장 그림을 넣지 못했습니다.')
    side = int(round(SEAL_MM / 25.4 * 7200))          # HWPUNIT

    def place(x: float, y: float) -> None:
        # InsertPicture 의 크기 인자로는 크기가 바뀌지 않아 Properties 에 직접 넣는다(2026. 10. 22. 이승민 사건에서 확인)
        p = ctrl.Properties
        for key, value in (('TreatAsChar', 0), ('TextWrap', 3), ('VertRelTo', 2), ('VertAlign', 0), ('VertOffset', int(y)),
                           ('HorzRelTo', 3), ('HorzAlign', 0), ('HorzOffset', int(x)), ('AllowOverlap', 1),
                           ('Width', side), ('Height', side)):
            p.SetItem(key, value)
        ctrl.Properties = p

    x = y = 0.0
    place(x, y)
    for _ in range(6):
        hwp.SaveAs(str(pdf), 'PDF', '')
        dx, dy = seal_gap(pdf)
        if abs(dx) < 0.8 and abs(dy) < 0.8:
            return
        x, y = x + dx * 100, y + dy * 100              # 1점 = 100 HWPUNIT
        place(x, y)
    raise FormError('도장 자리를 맞추지 못했습니다.')


def build_attendees(spec: dict, round_dir: Path) -> None:
    """참석자 명단: 별지 제12호서식의 칸을 칸 이름으로 찾아 채운다. 네 명을 넘으면 줄을 늘린다."""
    part = spec.get('참석자명단') or {}
    if not part.get('일시'):
        raise FormError("참석자명단의 '일시'가 비어 있습니다.")
    seal = seal_file(part)
    people = part.get('참석자') or []
    rows = max(4, len(people))
    side_text = ATTENDEE_SIDE_TEXT[spec['우리쪽']]
    checked = side_text.replace('[  ]', '[√]')
    template = template_path('참석자명단')
    tmp = work_dir()
    work, saved, pdf, seal_copy = tmp / 'work.hwpx', tmp / 'out.hwpx', tmp / 'out.pdf', tmp / 'seal.png'
    shutil.copyfile(template, work)
    hwp = open_hwp()
    try:
        if not hwp.Open(str(work), 'HWPX', 'forceopen:true'):
            raise FormError('양식을 열지 못했습니다: %s' % template.name)
        cells = cell_map(hwp)
        for _ in range(rows - 4):
            hwp.SetPos(cells['C%d' % (FIRST_ATTENDEE_ROW + 2)], 0, 0)
            hwp.HAction.Run('TableInsertLowerRow')
            cells = cell_map(hwp)
        last = FIRST_ATTENDEE_ROW + rows                 # 붙임·제출자 칸이 놓인 줄
        needed = ['B3', 'B4', 'A7', 'A%d' % last] + ['%s%d' % (c, FIRST_ATTENDEE_ROW + k) for k in range(rows) for c in 'CDE']
        missing = [n for n in needed if n not in cells]
        if missing:
            raise FormError('양식의 칸을 찾지 못했습니다: %s' % ', '.join(missing))
        fill_cell(hwp, cells, 'B3', ' ' + spec['사건'])    # 앞의 빈칸 하나는 칸 테두리와 띄우려는 것이다
        fill_cell(hwp, cells, 'B4', ' ' + part['일시'])
        for k in range(rows):
            person = people[k] if k < len(people) else {}
            for column, key in zip('CDE', ('성명', '관계', '직위')):
                fill_cell(hwp, cells, '%s%d' % (column, FIRST_ATTENDEE_ROW + k), person.get(key, ''), center=True)
        replace_all(hwp, side_text, checked)
        if part.get('제출일'):
            replace_all(hwp, '년       월       일', part['제출일'])
        if part.get('제출자'):
            replace_all(hwp, '제출자               ', '제출자  %s  ' % part['제출자'])
        replace_all(hwp, '○○(지방)노동위원회위원장', spec['노동위원회'] + '위원장')
        if seal:
            shutil.copyfile(seal, seal_copy)             # 한글은 임시 폴더의 사본을 읽는다(양식과 같다)
            stamp_seal(hwp, seal_copy, part.get('제출일') or '년       월       일', pdf)
        pages = hwp.PageCount
        hwp.SaveAs(str(saved), 'HWPX', '')
        hwp.SaveAs(str(pdf), 'PDF', '')
    finally:
        close_hwp(hwp)
        work.unlink(missing_ok=True)
        seal_copy.unlink(missing_ok=True)

    cells_saved, row_count = read_saved_cells(saved)
    problems = []
    for (row, column), want, label in (((2, 1), spec['사건'], '사건'), ((3, 1), part['일시'], '일시'), ((6, 0), checked, '당사자 지위')):
        if want not in cells_saved.get((row, column), ''):
            problems.append('%s 칸에 %r 없음' % (label, want))
    for k in range(rows):
        person = people[k] if k < len(people) else {}
        for column, key in zip((2, 3, 4), ('성명', '관계', '직위')):
            got = cells_saved.get((6 + k, column))
            if got is None or got.strip() != person.get(key, ''):
                problems.append('참석자 %d %s: %r' % (k + 1, key, got))
    tail = cells_saved.get((6 + rows, 0), '')
    for label, want in (('제출일', part.get('제출일')), ('제출자', part.get('제출자')), ('수신', spec['노동위원회'] + '위원장')):
        if want and want not in tail:
            problems.append('%s: 끝 칸에 %r 없음' % (label, want))
    if row_count != 8 + rows:
        problems.append('표의 줄 수 %d (바란 것 %d)' % (row_count, 8 + rows))
    if pages != 1:
        problems.append('한글 면수 %d (참석자가 많으면 한 면을 넘는다. 줄 높이를 손본다)' % pages)
    if seal:
        try:
            dx, dy = seal_gap(pdf)
            if abs(dx) > 1.5 or abs(dy) > 1.5:
                problems.append('도장이 %r 자리에서 (%.1f, %.1f)점 벗어남' % (SIGN_MARK, dx, dy))
        except FormError as exc:
            problems.append(str(exc))
    deliver(spec, '참석자명단', round_dir, saved, pdf, problems)


# ── 명령 ────────────────────────────────────────────────────────────────────

def cmd_init(round_dir: Path) -> int:
    target = round_dir / '작업' / SPEC_NAME
    if target.exists():
        print('지시표가 이미 있습니다: %s' % target)
        return 0
    if not round_dir.is_dir():
        raise FormError('라운드 폴더가 없습니다: %s' % round_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATES / SAMPLE_SPEC, target)
    print('지시표를 만들었습니다: %s' % target)
    return 0


def cmd_build(round_dir: Path, only: list[str] | None) -> int:
    spec = load_spec(round_dir)
    kinds = [k for k in KINDS if spec.get(k)] if not only else only
    if not kinds:
        raise FormError('지시표에 만들 서류(참석자명단·지정서·선임신고서)가 없습니다.')
    for kind in kinds:
        if not spec.get(kind):
            raise FormError('지시표에 %r 이 없습니다.' % kind)
        if kind == '참석자명단':
            build_attendees(spec, round_dir)
        else:
            build_replaced(spec, kind, round_dir)
    print('낸 곳: %s' % (round_dir / '출력'))
    print('확인 그림: %s' % (round_dir / '작업' / '노동위서류_확인'))
    return 0


def cmd_look(path: Path, cells: bool) -> int:
    if not path.is_file():
        raise FormError('파일이 없습니다: %s' % path)
    tmp = work_dir()
    work = tmp / ('look' + path.suffix.lower())
    shutil.copyfile(path, work)
    hwp = open_hwp()
    try:
        if not hwp.Open(str(work), hwp_format(work), 'forceopen:true'):
            raise FormError('문서를 열지 못했습니다.')
        print('면수 %d' % hwp.PageCount)
        print(document_text(hwp).strip())
        kinds: dict[str, int] = {}
        ctrl = hwp.HeadCtrl
        while ctrl is not None:
            kinds[ctrl.CtrlID] = kinds.get(ctrl.CtrlID, 0) + 1
            ctrl = ctrl.Next
        print('개체: %s' % kinds)
        if cells:
            for name, index in cell_map(hwp).items():
                hwp.SetPos(index, 0, 0)
                select_block(hwp, 'cell')
                text = (hwp.GetTextFile('TEXT', 'saveblock:true') or '').replace('\r\n', ' / ')
                hwp.HAction.Run('Cancel')
                print('%-4s 목록 %-3d %r' % (name, index, text[:60]))
    finally:
        close_hwp(hwp)
        work.unlink(missing_ok=True)
    return 0


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('init', help='사건 폴더에 지시표(작업/노동위서류.json)를 만든다')
    p.add_argument('round_dir', help='라운드 폴더(저장소 루트 기준)')
    p = sub.add_parser('build', help='지시표대로 서류를 만든다')
    p.add_argument('round_dir', help='라운드 폴더(저장소 루트 기준)')
    p.add_argument('--only', nargs='+', choices=KINDS, help='만들 서류만 고른다')
    p = sub.add_parser('look', help='한글 문서의 글·개체·칸을 살펴본다')
    p.add_argument('path')
    p.add_argument('--cells', action='store_true', help='표의 칸 이름과 내용을 함께 본다')
    args = ap.parse_args()

    def resolve(text: str) -> Path:
        path = Path(text)
        return path if path.is_absolute() else ROOT / path

    try:
        if args.cmd == 'init':
            return cmd_init(resolve(args.round_dir))
        if args.cmd == 'build':
            return cmd_build(resolve(args.round_dir), args.only)
        return cmd_look(resolve(args.path), args.cells)
    except FormError as exc:
        print('오류: %s' % exc)
        return 1


if __name__ == '__main__':
    sys.exit(main())
