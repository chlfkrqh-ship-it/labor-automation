"""서면 초안의 인용이 호증목록·판례기록과 맞는지 대조한다.

세 가지를 본다. 판단을 대신하지 않고 어긋난 자리만 짚는다.

1. 본문이 인용했는데 호증목록에 없는 호증      → 위반. 번호 오기이거나 목록 누락이다.
2. 호증목록에 있는데 본문이 한 번도 인용 안 한 호증 → 참고. 제출하고 쓰지 않은 증거다.
3. 본문이 인용했는데 공통/판례기록/ 에 없는 사건번호 → 참고. 확정 여부·따름 판례를
   확인하지 않고 인용했을 수 있으므로 LBOX 원문에서 확인한다.

    python 4_서면작성/scripts/citation_check.py 4_서면작성/사건/{사건}/라운드N/출력/서면초안.md

호증번호·사건번호 정규식은 공통/scripts/system.py 의 것을 그대로 쓴다. 두 벌로
갈리면 한쪽만 고치게 되기 때문이다. '갑 제2, 3호증', '갑 제1 내지 3호증',
'갑 제21·22호증', '갑 제41호증 내지 제43호증' 같은 병기는 번호마다 펼쳐 대조하고,
가지번호('을나 제1호증의 2')는 모번호로 묶는다.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('workflow_system', ROOT / '공통/scripts/system.py')
_system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_system)

EVIDENCE = re.compile(_system.EVIDENCE_NUMBER)
CASE = re.compile(_system.CASE_NUMBER)
# 목록 표 첫 칸의 약식 표기: '을나1-1', '갑14', '사 제3호증' 을 모두 받는다.
SHORT = re.compile(r'^(' + _system.EVIDENCE_PREFIX + r')\s*(?:제\s*)?(\d+)(?:\s*[-의]\s*\d+)?\s*(?:호증)?$')


def normalize(label):
    return re.sub(r'\s+', '', label)


def case_numbers(text):
    """사건번호를 공백 없는 꼴('2018노3955')로 모은다. 판례기록 파일명과 같은 꼴이다."""
    return {normalize(hit) for hit in CASE.findall(text)}


def docx_text(path: Path):
    """docx 의 본문 문단과 각주. 판례 인용은 병합 때 각주로 옮겨 가므로 각주도 읽는다."""
    import docx
    lines = [p.text for p in docx.Document(str(path)).paragraphs]
    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with zipfile.ZipFile(path) as archive:
        if 'word/footnotes.xml' in archive.namelist():
            root = ET.fromstring(archive.read('word/footnotes.xml'))
            for note in root.iter(w + 'footnote'):
                if note.get(w + 'type') in ('separator', 'continuationSeparator', 'continuationNotice'):
                    continue
                lines.extend(''.join(t.text or '' for t in p.iter(w + 't')) for p in note.iter(w + 'p'))
    return '\n'.join(lines)


def body_text(path: Path):
    """제출용 본문. MD 하단의 보완 메모는 뺀다."""
    if path.suffix.lower() == '.docx':
        return docx_text(path)
    lines = path.read_text(encoding='utf-8-sig').split('\n')
    for number, line in enumerate(lines):
        if number and re.match(r'^\s*-{3,}\s*$', line):
            return '\n'.join(lines[:number])
    return '\n'.join(lines)


def catalogues(case_dir: Path):
    """호증목록 파일. 증거관리/ 뿐 아니라 라운드N/출력/증거정리/ 도 본다.

    노동위원회 단계는 노·사 체계, 행정소송 단계는 갑·을 체계로 호증을 다시 매기므로
    (.claude/commands/증거정리.md) 목록이 여러 벌 있다. 한 벌만 보면 다른 체계의
    인용이 전부 '목록에 없음'으로 잡힌다.
    """
    found = sorted(set(case_dir.rglob('*호증*목록*.md'))
                   | set(case_dir.rglob('*호증목록*.md')))
    return [p for p in found if '백업' not in p.parts]


def listed(case_dir: Path, own: str | None = None, names=()):
    """호증목록에 등재된 호증. 'A ~ B'·'제1 내지 3호증' 같은 범위와 병기는 펼친다.

    서면을 나눈 라운드(names, `system.split_names`)는 서면마다 호증 번호를 따로 매기므로, own(이 서면의 이름)을 주면 다른 서면의
    목록 절('## {다른 이름} 건')과 다른 서면 이름이 든 목록 파일의 줄은 뺀다. 어느 서면의 것도 아닌 절·파일(상대호증목록 등)의 줄은 넣는다.
    2026. 11. 8. `/하자보완`: 두 서면의 목록을 합쳐 보아, 14건짜리 서면의 증 제15~27호증 인용도 '목록에 있다'로 통과시켰다."""
    result = {}
    for p in catalogues(case_dir):
        name = p.relative_to(case_dir).as_posix()
        파일주인 = _system.name_owner(p.stem, names) if names else None
        주인 = 파일주인
        for row in p.read_text(encoding='utf-8-sig').split('\n'):
            if names and re.match(r'^\s*#{1,6}\s', row):
                주인 = _system.name_owner(row, names) or 파일주인
                continue
            if not row.strip().startswith('|'):
                continue
            if own and 주인 and 주인 != own:
                continue
            # 표 첫 칸은 그 자체가 호증번호이므로 '을나1-1', '갑14' 같은 약식도 받는다.
            cell = row.strip().strip('|').split('|')[0].strip()
            short = SHORT.match(cell)
            if short:
                result.setdefault('%s제%d호증' % (short[1], int(short[2])), name)
            for label in _system.evidence_labels(row):
                result.setdefault(label, name)
    return result


def recorded_cases():
    folder = ROOT / '공통/판례기록'
    found = set()
    if folder.is_dir():
        for p in folder.glob('*.md'):
            found |= case_numbers(p.stem + ' ' + p.read_text(encoding='utf-8-sig'))
    return found


def split_of(draft: Path, 서면=None) -> tuple:
    """(이 서면의 이름, 그 라운드의 서면 이름들). 서면을 나누지 않은 라운드면 (None, []).
    초안 md 는 파일 이름(`서면초안_{이름}.md`)으로, 병합한 docx 는 이름이 든 것으로 가린다. 서면(초안 경로나 이름)을 주면 그것을 쓴다."""
    here = draft.resolve().parent
    out = next((p for p in (here, *here.parents) if p.name == '출력'), here)      # 제출/{이름}/ 의 사본도 그 라운드의 출력/ 로 본다
    names = _system.split_names(out)
    if not names:
        return None, []
    if 서면:
        own = _system.draft_name(서면) if str(서면).lower().endswith('.md') else _system.name_form(서면)
    elif draft.suffix.lower() == '.md':
        own = _system.draft_name(draft)
    else:
        own = _system.name_owner(draft.name, names)
    return (own if own in names else None), names


def check(draft: Path, case_dir: Path, 서면=None):
    text = body_text(draft)
    cited = {}
    for hit in EVIDENCE.finditer(text):
        for label in _system.expand_evidence(hit[0]):
            cited.setdefault(label, set()).add(normalize(hit[0]))
    own, names = split_of(draft, 서면)
    catalogue = listed(case_dir, own, names)
    records = recorded_cases()
    cases = sorted(case_numbers(text))

    missing = sorted(k for k in cited if k not in catalogue)
    unused = sorted(k for k in catalogue if k not in cited)
    unrecorded = [c for c in cases if c not in records]
    # 목록이 비어 있는데 본문은 호증을 인용한다면 증거정리를 아직 돌리지 않은 것이다.
    needs_evidence_pass = bool(cited) and not catalogue
    return {
        'draft': draft.as_posix(),
        'case': case_dir.as_posix(),
        'cited_count': len(cited),
        'listed_count': len(catalogue),
        'not_in_list': missing,
        'listed_but_uncited': unused,
        'cases_cited': cases,
        'cases_without_record': unrecorded,
        'needs_evidence_pass': needs_evidence_pass,
        'split': names,
        'draft_name': own,
        'ok': not missing,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('draft', help='서면 초안 .md 또는 .docx')
    parser.add_argument('--case', help='사건 폴더 (생략하면 초안 경로에서 찾는다)')
    parser.add_argument('--서면', help='서면을 나눈 라운드에서 이 docx 가 어느 서면인지(서면초안_{이름}.md 경로나 이름). 생략하면 파일 이름으로 가린다')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    draft = Path(args.draft)
    if args.case:
        case_dir = Path(args.case)
    else:
        case_dir = next((p for p in draft.resolve().parents
                         if (p / '증거관리').is_dir()), None)
        if case_dir is None:
            print('사건 폴더를 찾지 못했습니다. --case 로 지정하십시오.', file=sys.stderr)
            return 2
    result = check(draft, case_dir, args.서면)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['ok'] else 1

    print('%s' % result['draft'])
    print('본문 인용 호증 %d건 / 목록 등재 %d건%s\n' % (result['cited_count'], result['listed_count'],
                                               f" ({result['draft_name']} 서면의 목록)" if result['draft_name'] else ''))
    if result['split'] and not result['draft_name']:
        print('  [참고] 서면을 나눈 라운드인데 어느 서면인지 가리지 못해 모든 서면의 목록과 맞댔습니다 — `--서면 "{서면초안_이름.md}"` 를 준다')
    if result['needs_evidence_pass']:
        print('  [위반] 호증목록이 비어 있는데 본문은 호증을 인용합니다.')
        print('         증거정리를 아직 돌리지 않았거나 결과가 증거관리/ 로 옮겨지지 않았습니다.')
        print('         `/증거정리 {사건명} 라운드N` 을 먼저 수행하십시오.')
    elif result['not_in_list']:
        print('  [위반] 목록에 없는 호증을 인용했습니다 — 번호 오기이거나 목록 누락입니다')
        for k in result['not_in_list']:
            print('         %s' % k)
    else:
        print('  인용한 호증은 모두 목록에 있습니다.')
    if result['listed_but_uncited']:
        print('\n  [참고] 목록에 있으나 이 서면이 인용하지 않은 호증 %d건 (전체 라운드 합산)'
              % len(result['listed_but_uncited']))
        print('         %s' % ', '.join(result['listed_but_uncited'][:20]))
        if len(result['listed_but_uncited']) > 20:
            print('         … 외 %d건' % (len(result['listed_but_uncited']) - 20))
    if result['cases_without_record']:
        print('\n  [참고] 판례기록에 없는 사건번호 %d건 — 확정 여부와 따름 판례를 확인하십시오'
              % len(result['cases_without_record']))
        print('         %s' % ', '.join(result['cases_without_record']))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
