"""Local workflow tools. No network or model calls."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

VERSION = 1
TEXT = {'.md', '.txt', '.json', '.yaml', '.yml', '.csv', '.jsonl'}
DOCUMENTS = TEXT | {'.pdf', '.docx', '.xlsx', '.png', '.jpg', '.jpeg', '.m4a', '.mp3', '.wav', '.mp4'}
SKIP = {'작업', '비교', '백업', '캐시', '추출캐시', '__pycache__', '.pytest_cache', '.venv', 'models', '.git'}
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

# 명령어별로 읽는 지침 파일. 글자 수만 집계하며 토큰 수로 환산하지 않는다.
COMMON = ['CLAUDE.md', '공통/운영.md']
LBOX = ['.claude/skills/lbox-검색/SKILL.md', '.claude/skills/lbox-하이라이트/SKILL.md', '.claude/skills/법제처-검색/SKILL.md']
STYLE = '4_서면작성/skills/노동서면작성/'
REFERENCES = [STYLE + 'references/' + n for n in
              ('문체-용례.md', '표기-어휘.md', '증거-인용.md', '판례-인용.md',
               '구성-논증.md', '서면별-구조.md', 'docx-스타일.md')]
# 초안 작성은 SKILL.md와 references 전부를 읽는다. 좁은 작업만 해당 조각을 읽는다.
BRIEF = ['4_서면작성/CLAUDE.md', STYLE + 'SKILL.md'] + REFERENCES
GUIDE_SETS = {
    '검토의견': COMMON + ['1_검토의견/CLAUDE.md', '.claude/commands/검토의견.md', '공통/사건상태.md'] + LBOX,
    '판례검색': COMMON + ['2_판례검색/CLAUDE.md', '.claude/commands/판례검색.md'] + LBOX,
    '서면보강': COMMON + ['3_서면보강/CLAUDE.md', '.claude/commands/서면보강.md'] + LBOX,
    # 서면 하나가 입구다. 반박 구성과 노동위 기록 추출은 자료에 따라 켜는 갈래이며
    # 해당할 때만 읽으므로 아래 분량에 더해질 수 있다.
    '서면': COMMON + BRIEF + ['.claude/commands/서면.md', '공통/사건상태.md', '공통/문서변환.md'] + LBOX,
    '서면(반박 구성)': COMMON + BRIEF + ['.claude/commands/서면.md', '공통/사건상태.md',
                                   '공통/문서변환.md', '4_서면작성/절차/반박-구성.md'] + LBOX,
    '서면(노동위 기록)': COMMON + BRIEF + ['.claude/commands/서면.md', '공통/사건상태.md',
                                    '공통/문서변환.md', '4_서면작성/절차/노동위기록-추출.md'] + LBOX,
    '증거정리': COMMON + ['4_서면작성/CLAUDE.md', '.claude/commands/증거정리.md', '공통/사건상태.md'],
    '증거발췌': COMMON + ['4_서면작성/CLAUDE.md', STYLE + 'references/증거-인용.md', '.claude/commands/증거발췌.md'],
    '문체검증': COMMON + [STYLE + 'SKILL.md', STYLE + 'references/문체-용례.md', '1_검토의견/문체가이드-서면.md', '.claude/commands/문체검증.md'],
    '녹취': COMMON + ['5_녹취록/CLAUDE.md', '5_녹취록/녹취서-작성-가이드.md', '.claude/commands/녹취.md'],
    '손배계산': COMMON + ['6_손해배상계산/CLAUDE.md', '.claude/commands/손배계산.md', '6_손해배상계산/노동금액-계산기준.md'],
    '손배검산': COMMON + ['6_손해배상계산/CLAUDE.md', '.claude/commands/손배검산.md', '6_손해배상계산/노동금액-계산기준.md'],
}
# 사건번호와 호증번호. 4_서면작성/scripts/citation_check.py 가 같은 정의를 가져다 쓴다.
CASE_NUMBER = r'\d{2,4}(?:다|두|누|구합|구단|가합|가단|나|도|부해|부노|재해)\d+'
EVIDENCE_NUMBER = r'(?:갑|을(?:가|나)?|병|정|노|사)\s*제\s*\d+호증(?:의\s*\d+)?'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(path: Path, data: str | bytes):
    """Atomic replacement, only called for explicitly owned/generated paths."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_bytes(data.encode('utf-8') if isinstance(data, str) else data)
    temporary.replace(path)


def write_json(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


class System:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, value):
        p = Path(value)
        p = (p if p.is_absolute() else self.root / p).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError('작업 루트 밖의 경로는 지원하지 않습니다.')
        return p

    def rel(self, p):
        return self.path(p).relative_to(self.root).as_posix()

    def files(self, scope, include_work=False):
        scope = self.path(scope)
        if scope.is_file():
            return [scope]
        if not scope.is_dir():
            raise ValueError('입력 경로가 없습니다: ' + self.rel(scope))
        result = []
        # Do not follow directory symlinks or scan excluded trees.
        import os
        for folder, dirs, names in os.walk(scope, followlinks=False):
            skipped = SKIP - {'작업'} if include_work else SKIP
            dirs[:] = sorted(d for d in dirs if d not in skipped and not d.startswith('.')
                             and not (Path(folder) / d).is_symlink())
            for name in sorted(names):
                if (name.startswith(('~$', '.')) or '.bak' in name or '.폐기' in name
                        or name in {'자료목록.json', '사건상태.md', '_추출.txt'}):
                    continue
                p = self.path(Path(folder) / name)
                # Inventory unsupported formats too; never silently hide source files.
                result.append(p)
        return sorted(result)

    def check(self):
        """필수 지침과 명령어가 있고 스킬 머리말이 바른지 본다."""
        missing = [f for f in ('CLAUDE.md', '공통/운영.md', '공통/사건상태.md', '공통/브라우저.md')
                   if not self.path(f).is_file()]
        commands = {p.stem for p in self.path('.claude/commands').glob('*.md')}
        required = {'검토의견', '판례검색', '서면보강', '서면',
                    '증거정리', '증거발췌', '문체검증', '녹취', '손배계산', '손배검산'}
        missing.extend('.claude/commands/' + n + '.md' for n in sorted(required - commands))
        skill_errors = []
        for p in self.path('.claude/skills').glob('*/SKILL.md'):
            text = p.read_text(encoding='utf-8-sig')
            match = re.match(r'---\s*\n(.*?)\n---', text, re.S)
            if not match or not re.search(r'^name:\s*\S+', match[1], re.M) or not re.search(r'^description:\s*\S+', match[1], re.M):
                skill_errors.append(self.rel(p))
            elif re.search(r'^name:\s*(.+)$', match[1], re.M)[1].strip() != p.parent.name:
                skill_errors.append(self.rel(p))
        return {'missing': missing, 'skill_errors': skill_errors, 'ok': not missing and not skill_errors}

    def budget(self, only=None, record=False):
        """명령어별 지침 분량과 중복·고아 지침을 보고한다.

        상한을 두지 않는다. 분량은 판단 재료일 뿐이고, 이 수치를 근거로 지침을
        줄이지 않는다. 실패로 처리하는 것은 지침 파일이 없는 경우뿐이다.
        """
        sets = GUIDE_SETS if only is None else {only: GUIDE_SETS[only]}
        commands, missing, sizes = {}, [], {}
        for name, paths in sets.items():
            total = 0
            for rel in paths:
                if rel not in sizes:
                    p = self.path(rel)
                    sizes[rel] = len(p.read_text(encoding='utf-8-sig')) if p.is_file() else None
                if sizes[rel] is None:
                    if rel not in missing:
                        missing.append(rel)
                    continue
                total += sizes[rel]
            commands[name] = total

        history_path = self.path('공통/지침분량.json')
        previous = read_json(history_path) if history_path.exists() else {}
        before = previous.get('commands', {})
        changed = {k: v - before[k] for k, v in commands.items()
                   if k in before and v != before[k]}
        if record:
            write_json(history_path, {'version': VERSION, 'recorded': stamp(),
                                      'commands': commands})

        largest = sorted(((v, k) for k, v in sizes.items() if v), reverse=True)[:5]
        return {
            'unit': '글자',
            'commands': dict(sorted(commands.items(), key=lambda kv: -kv[1])),
            'largest_files': [{'path': k, 'chars': v} for v, k in largest],
            'changed_since_record': dict(sorted(changed.items(), key=lambda kv: -abs(kv[1]))),
            'recorded_at': previous.get('recorded'),
            'duplicated': self.duplicated(),
            'orphans': self.orphans(),
            'missing': missing,
            'ok': not missing,
        }

    def guide_files(self):
        seen = []
        for paths in GUIDE_SETS.values():
            for rel in paths:
                if rel not in seen:
                    seen.append(rel)
        return seen

    def duplicated(self, floor=40):
        """두 지침 파일에 똑같이 들어 있는 문장. 규칙이 두 벌로 갈린 자리다."""
        where = {}
        for rel in self.guide_files():
            p = self.path(rel)
            if not p.is_file():
                continue
            for line in p.read_text(encoding='utf-8-sig').splitlines():
                text = re.sub(r'\s+', ' ', line).strip(' -*|#>')
                if len(text) >= floor:
                    where.setdefault(text, set()).add(rel)
        # 적은 파일에만 겹치는 것부터 본다. 여러 파일에 두루 나오는 문장은 대개
        # 모든 명령어에 붙이는 정형 안내이고, 두세 파일에만 겹치는 문장이 규칙이
        # 갈린 자리일 가능성이 높다.
        found = [{'files': sorted(f), 'text': t[:80]}
                 for t, f in where.items() if len(f) > 1]
        return sorted(found, key=lambda d: (len(d['files']), d['text']))

    def orphans(self):
        """어느 명령어도 읽지 않고 다른 지침도 가리키지 않는 지침 파일."""
        used = set(self.guide_files())
        pool = ([self.rel(p) for p in self.path('공통').glob('*.md')]
                + [self.rel(p) for p in self.path('.claude/commands').glob('*.md')]
                + [self.rel(p) for p in self.path('4_서면작성/skills/노동서면작성').rglob('*.md')])
        body = ''
        for rel in used:
            p = self.path(rel)
            if p.is_file():
                body += p.read_text(encoding='utf-8-sig')
        return sorted(r for r in set(pool) - used if r not in body)

    def scan(self, scope, accept=False):
        scope = self.path(scope)
        if not scope.is_dir() or scope == self.root:
            raise ValueError('개별 사건 폴더를 지정하십시오.')
        current = {self.rel(p): {'sha256': digest(p.read_bytes()), 'bytes': p.stat().st_size}
                   for p in self.files(scope, include_work=True)}
        target = self.path(scope / '작업' / '자료목록.json')
        if not target.is_relative_to(scope):
            raise ValueError('사건 상태 경로가 사건 밖으로 연결되어 있습니다.')
        old = read_json(target).get('files', {}) if target.exists() else {}
        result = {'first_scan': not target.exists(), 'file_count': len(current),
                  'added': sorted(current.keys() - old.keys()),
                  'changed': sorted(k for k in current.keys() & old.keys() if current[k] != old[k]),
                  'deleted': sorted(old.keys() - current.keys()), 'accepted': accept}
        if accept:
            write_json(target, {'version': VERSION, 'at': stamp(), 'scope': self.rel(scope),
                                'files': current, 'note': '파일 기준 목록. 법적 검토 완료를 의미하지 않음.'})
        return result

    def extract(self, value):
        p = self.path(value)
        suffix = p.suffix.lower()
        library = 'stdlib'
        if suffix == '.pdf':
            library = 'pypdf-' + importlib.metadata.version('pypdf')
        source_hash = digest(p.read_bytes())
        key = digest(f'{VERSION}:{library}:{suffix}:{source_hash}'.encode())
        parts = p.relative_to(self.root).parts
        if '사건' in parts and parts.index('사건') + 1 < len(parts) - 1:
            case_root = self.root.joinpath(*parts[:parts.index('사건') + 2])
            cache_root = self.path(case_root / '작업' / '추출캐시')
            if not cache_root.is_relative_to(case_root):
                raise ValueError('추출 캐시 경로가 사건 밖으로 연결되어 있습니다.')
        else:
            cache_root = self.path('공통/캐시')
        cache = cache_root / (key + '.json')
        if cache.exists():
            data = read_json(cache)
            if data.get('source_sha256') == source_hash and data.get('text_sha256') == digest(data['text'].encode()):
                return {**data, 'cache_hit': True, 'cache': self.rel(cache)}
        warnings = []
        if suffix in TEXT:
            try:
                text = p.read_text(encoding='utf-8-sig')
            except UnicodeDecodeError:
                text = p.read_text(encoding='cp949')
                warnings.append('CP949 디코딩 적용: 원문 문자 확인 필요')
        elif suffix == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(p)
            pages = []
            warnings.append('PDF 순번은 인쇄 면수와 다를 수 있음. 인용 전 원문 확인 필요')
            for i, page in enumerate(reader.pages, 1):
                t = page.extract_text() or ''
                pages.append(f'\n[PDF 순번 {i}]\n{t}')
                if not t.strip():
                    warnings.append(f'PDF 순번 {i}: 추출 텍스트 없음, 스캔/OCR 확인 필요')
            text = '\n'.join(pages)
        elif suffix == '.docx':
            paragraphs = []
            with zipfile.ZipFile(p) as z:
                for part in ('word/document.xml', 'word/footnotes.xml', 'word/endnotes.xml'):
                    if part not in z.namelist():
                        continue
                    xml = ET.fromstring(z.read(part))
                    if xml.findall('.//w:ins', NS) or xml.findall('.//w:del', NS):
                        warnings.append('변경 추적 있음: 추출은 삽입 포함·삭제 제외. Word 원문 확인 필요')
                    paragraphs.append(f'[{part}]')
                    for para in xml.findall('.//w:p', NS):
                        paragraphs.append(''.join(n.text or '' for n in para.findall('.//w:t', NS)))
            text = '\n'.join(paragraphs)
            warnings.append('DOCX 본문·표·각주 텍스트만 추출. 면수·그림·머리말·서식은 렌더 확인 필요')
        else:
            raise ValueError('텍스트 추출 미지원 형식: ' + suffix)
        if not text.strip():
            warnings.append('추출 내용 없음')
        data = {'version': VERSION, 'source_sha256': source_hash, 'extractor': library,
                'text': text, 'text_sha256': digest(text.encode()), 'warnings': warnings}
        write_json(cache, data)
        return {**data, 'cache_hit': False, 'cache': self.rel(cache)}



def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('check')
    bud = subs.add_parser('budget'); bud.add_argument('--command', dest='only', choices=sorted(GUIDE_SETS))
    bud.add_argument('--record', action='store_true', help='지금 분량을 기준선으로 기록한다')
    scan = subs.add_parser('scan'); scan.add_argument('case'); scan.add_argument('--accept', action='store_true')
    ex = subs.add_parser('extract'); ex.add_argument('file')
    ex.add_argument('--start-line', type=int)
    ex.add_argument('--line-count', type=int, default=80)
    args = vars(parser.parse_args())
    name = args.pop('command')
    system = System(Path(__file__).resolve().parents[2])
    try:
        if name == 'extract':
            result = system.extract(args['file'])
            if args['start_line'] is not None:
                if args['start_line'] < 1 or not 1 <= args['line_count'] <= 300:
                    raise ValueError('시작 행은 1 이상, 행 수는 1~300으로 지정하십시오.')
                rows = result['text'].splitlines()
                start = args['start_line'] - 1
                result['excerpt'] = '\n'.join(f'{i + 1}: {rows[i]}' for i in range(start, min(len(rows), start + args['line_count'])))
                result['total_lines'] = len(rows)
            result = {k: v for k, v in result.items() if k not in ('text', 'text_sha256')}
        elif name == 'scan':
            result = system.scan(args['case'], args['accept'])
        else:
            result = getattr(system, name)(**args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if name in ('check', 'budget') and not result['ok'] else 0
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, importlib.metadata.PackageNotFoundError) as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
