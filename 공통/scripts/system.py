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

# 2: DOCX 글상자 문장을 한 번만 추출한다. 옛 추출 캐시를 다시 쓰지 않도록 올렸다.
VERSION = 2
TEXT = {'.md', '.txt', '.json', '.yaml', '.yml', '.csv', '.jsonl'}
EXTRACTABLE = TEXT | {'.pdf', '.docx'}
# scan 이 건너뛰는 폴더. 도구가 만드는 캐시는 조용히 뺀다(공통/사건상태.md '추출 재사용').
# 그 밖의 이름('백업', 'models')은 원자료를 조용히 숨기지 않도록 scan 결과의 skipped_dirs 에 적는다.
# 점으로 시작하는 폴더(.git, .venv 등)는 files() 가 따로 뺀다.
CACHE_DIRS = {'캐시', '추출캐시', '__pycache__'}
SKIP = CACHE_DIRS | {'백업', 'models'}
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
MC_FALLBACK = '{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback'

# 명령어별로 읽는 지침 파일. 글자 수만 집계하며 토큰 수로 환산하지 않는다.
COMMON = ['CLAUDE.md', '공통/운영.md']
CITE = ['공통/자체검토.md']      # 판례·결정례·행정해석을 인용하는 산출물을 넘기기 전에 읽는다(인용 대조표와 스크립트 검사)
LBOX = ['.claude/skills/lbox-검색/SKILL.md', '.claude/skills/lbox-하이라이트/SKILL.md', '.claude/skills/법제처-검색/SKILL.md']
# LBOX 를 멈춘 날. 비어 있지 않으면 최종 관문이 LBOX 목록 대신 검색기록의 'LBOX 중지' 줄을 본다(`lbox-검색` 맨 앞 '사용 중지').
# LBOX 의 서면 동의를 받아 담당자가 다시 쓰기로 하면 '' 로 둔다. 2026. 11. 11. LBOX 가 이용약관 제11조(자동화 수단 금지)를 들어 계정을 제한하였다.
LBOX_중지 = '2026. 11. 11.'
STYLE = '4_서면작성/skills/노동서면작성/'
REFERENCES = [STYLE + 'references/' + n for n in
              ('문체-용례.md', '표기-어휘.md', '증거-인용.md', '판례-인용.md',
               '구성-논증.md', '서면별-구조.md', 'docx-스타일.md')]
# 초안 작성은 SKILL.md와 references 전부를 읽는다. 좁은 작업만 해당 조각을 읽는다.
BRIEF = ['4_서면작성/CLAUDE.md', STYLE + 'SKILL.md'] + REFERENCES
GUIDE_SETS = {
    '검토의견': COMMON + CITE + ['1_검토의견/CLAUDE.md', '.claude/commands/검토의견.md', '공통/사건상태.md'] + LBOX,
    # 배당 메일과 후속 메일을 가른 뒤 검토의견 절차를 그대로 탄다.
    '배당확인': COMMON + CITE + ['1_검토의견/CLAUDE.md', '.claude/commands/배당확인.md', '.claude/commands/검토의견.md',
                            '공통/사건상태.md'] + LBOX,
    # 하루치 메일·팀즈를 사건 폴더에 받아 넣고 기록만 한다. 인용하는 산출물이 없어 자체검토·LBOX 지침은 읽지 않는다.
    '메일반영': COMMON + ['.claude/commands/메일반영.md', '공통/사건상태.md'],
    # 매일 자정 시스템 시험·최종 관문·그날 지적의 반영을 본다. 인용하는 산출물을 쓰지 않으므로 자체검토·문체 지침은 읽지 않는다.
    '하자보완': COMMON + ['.claude/commands/하자보완.md'],
    '판례검색': COMMON + CITE + ['2_판례검색/CLAUDE.md', '.claude/commands/판례검색.md'] + LBOX,
    '서면보강': COMMON + CITE + ['3_서면보강/CLAUDE.md', '.claude/commands/서면보강.md'] + LBOX,
    # 서면 하나가 입구다. 반박 구성과 노동위 기록 추출은 자료에 따라 켜는 갈래이며
    # 해당할 때만 읽으므로 아래 분량에 더해질 수 있다.
    '서면': COMMON + CITE + BRIEF + ['.claude/commands/서면.md', '공통/사건상태.md', '공통/문서변환.md'] + LBOX,
    '서면(반박 구성)': COMMON + CITE + BRIEF + ['.claude/commands/서면.md', '공통/사건상태.md',
                                   '공통/문서변환.md', '4_서면작성/절차/반박-구성.md'] + LBOX,
    '서면(노동위 기록)': COMMON + CITE + BRIEF + ['.claude/commands/서면.md', '공통/사건상태.md',
                                    '공통/문서변환.md', '4_서면작성/절차/노동위기록-추출.md'] + LBOX,
    '증거정리': COMMON + ['4_서면작성/CLAUDE.md', '.claude/commands/증거정리.md', '공통/사건상태.md'],
    '증거발췌': COMMON + ['4_서면작성/CLAUDE.md', STYLE + 'references/증거-인용.md', '.claude/commands/증거발췌.md'],
    # 1_검토의견/문체가이드-서면.md 는 검토의견서용이라 소송 서면 채점 기준과 맞지 않는다('생각건대' 권장 등).
    '문체검증': COMMON + [STYLE + 'SKILL.md', STYLE + 'references/문체-용례.md', '.claude/commands/문체검증.md'],
    # 한글 양식에 값을 채우는 작업이다. 서면 문체 지침과 사건상태를 읽지 않고 통지서와 이미 낸 대리인 서류만 본다.
    '노동위서류': COMMON + ['4_서면작성/CLAUDE.md', '.claude/commands/노동위서류.md'],
    # 답은 서면 계열(BRIEF), 회색 메모는 검토의견 계열(1_검토의견/CLAUDE.md 3절)이다.
    '예상질의': COMMON + CITE + BRIEF + ['1_검토의견/CLAUDE.md', '.claude/commands/예상질의.md', '4_서면작성/절차/심문회의-예상질의.md', '공통/사건상태.md'],
    '녹취': COMMON + ['5_녹취록/CLAUDE.md', '5_녹취록/녹취서-작성-가이드.md', '.claude/commands/녹취.md'],
    '손배계산': COMMON + ['6_손해배상계산/CLAUDE.md', '.claude/commands/손배계산.md', '6_손해배상계산/노동금액-계산기준.md'],
    '손배검산': COMMON + ['6_손해배상계산/CLAUDE.md', '.claude/commands/손배검산.md', '6_손해배상계산/노동금액-계산기준.md'],
    '자체검토': COMMON + CITE + ['.claude/commands/자체검토.md'],
    # 작성 세션이 넘기기 전 재검토를 시작할 때 부른다. 부른 명령의 지침은 그 명령 쪽에서 센다.
    '전면재검토': COMMON + CITE + ['.claude/commands/전면재검토.md'],
}
# 사건번호와 호증번호의 단일 원본. 4_서면작성/scripts/citation_check.py·style_check.py 와
# 공통/scripts/lawgo.py 가 가져다 쓴다. 두 벌로 갈리면 한쪽만 고치게 된다.
#
# 사건부호. '2019년3월'처럼 날짜가 사건번호로 잡히지 않도록 쓰이는 부호만 적는다(긴 것을 앞에).
# .claude/skills/lbox-검색/SKILL.md 의 JS 사본('사건부호')도 같은 목록이어야 한다(공통/tests/test_system.py 가 대조한다).
CASE_TYPES = ('다카|다라|재다|재두|재누|구합|구단|구소|가합|가단|가소|고합|고단|고정|카합|카단|카기|부해|부노|헌가|헌바|헌마|헌라|헌사|헌아|'
              '다|두|누|구|나|노|도|마|머|그|스|므|르|브|재|허|후|추|초|모|로|오|트|즈|느|드|흐|카|라|사|자|차|파')
# 부호 앞뒤의 공백 하나는 허용한다('2018노 3955'). 비교할 때는 공백을 지운다.
CASE_NUMBER = r'(?<!\d)\d{2,4}\s?(?:' + CASE_TYPES + r')\s?\d{1,7}(?!\d)'

# 호증번호. 접두어와 '제' 뒤의 번호 목록을 한 묶음으로 잡는다. '갑 제2, 3호증', '갑 제21·22호증',
# '갑 제1 내지 3호증', '사 제61~63호증', '갑 제41호증 내지 제43호증', '갑 제31호증 ~ 갑 제33호증',
# '을나 제1호증의 2', '사 제67호증의1·2' 가 모두 한 묶음이다. 번호별로 펼치는 것은 expand_evidence() 이다.
# 접두어 글자는 흔한 조사·어미이기도 하므로('것을 제2호증') 앞에 한글이 붙으면 호증으로 보지 않는다.
EVIDENCE_PREFIX = r'(?:갑|을가|을나|을다|을라|을|병|정|노|사|증)'
_EV_RANGE = r'(?:내지|[~∼～〜])'
_EV_SEP = r'\s*(?:,|[·ㆍ・]|및|과|와|' + _EV_RANGE + r')\s*'
_EV_NO = r'\d+(?:\s*-\s*\d+)?'                  # '1-1' 은 약식 가지번호다. 본문에서 '-' 를 범위로 읽지 않는다
_EV_UNIT = (_EV_NO + r'(?:' + _EV_SEP + r'(?:제\s*)?' + _EV_NO + r')*\s*호증'
            + r'(?:\s*의\s*(?:각\s*)?\d+(?:\s*(?:,|[·ㆍ・]|' + _EV_RANGE + r')\s*\d+)*)?')
EVIDENCE_NUMBER = (r'(?<![가-힣])' + EVIDENCE_PREFIX + r'\s*제\s*' + _EV_UNIT
                   + r'(?:(?:' + _EV_SEP + r'(?:' + EVIDENCE_PREFIX + r'\s*)?|\s*-\s*' + EVIDENCE_PREFIX + r'\s*)'
                   + r'(?:제\s*)?' + _EV_UNIT + r')*')
_EV_TOKEN = re.compile(r'(호증)|(의)|(제)|(' + EVIDENCE_PREFIX + r')|(\d+)(?:\s*-\s*\d+)?|(' + _EV_RANGE + r'|-)')
_EV_RANGE_LIMIT = 1000                          # 오기로 생긴 터무니없는 범위는 펼치지 않는다


def expand_evidence(group: str) -> list[str]:
    """EVIDENCE_NUMBER 한 묶음을 모번호 표기('갑제2호증') 목록으로 펼친다.

    쉼표·가운뎃점·'및'·'과'는 나열, '내지'·'~'는 앞 번호부터의 범위다. '의' 뒤의 가지번호와
    약식 가지번호('1-1')는 모번호로 묶는다. 접두어가 다시 나오면('갑 제31호증 ~ 갑 제33호증')
    같은 접두어일 때만 범위를 잇는다.
    """
    labels, prefix, last, pending, branch = [], None, None, False, False
    for token in _EV_TOKEN.finditer(group):
        if token[1]:                            # 호증
            continue
        if token[2]:                            # 의 → 가지번호가 이어진다
            branch = True
        elif token[3]:                          # 제 → 모번호로 돌아온다
            branch = False
        elif token[4]:                          # 접두어
            if token[4] != prefix:
                last, pending = None, False
            prefix, branch = token[4], False
        elif token[6]:                          # 범위
            pending = True
        elif branch:                            # 가지번호는 모번호로 묶는다
            pending = False
        else:
            number = int(token[5])
            if pending and last is not None and last < number <= last + _EV_RANGE_LIMIT:
                numbers = range(last + 1, number + 1)
            else:
                numbers = (number,)
            for n in numbers:
                label = '%s제%d호증' % (prefix, n)
                if label not in labels:
                    labels.append(label)
            last, pending = number, False
    return labels


def evidence_labels(text: str) -> list[str]:
    """글 전체의 호증 인용을 모번호 표기로 펼친다. 처음 나온 순서대로, 중복 없이."""
    labels = []
    for match in re.finditer(EVIDENCE_NUMBER, text):
        labels.extend(x for x in expand_evidence(match[0]) if x not in labels)
    return labels


# 서면을 나눈 라운드. 상병별로 결론이 갈릴 수 있으면 서면을 나누고(`4_서면작성/skills/노동서면작성/references/서면별-구조.md`), 절차가
# 따로 진행되므로 서면마다 호증 번호를 1부터 따로 매긴다. 호증목록은 서면마다 '## {이름} 건' 절로, 제출 묶음은 `출력/제출/{이름}/` 로 나눈다
# (`.claude/commands/증거정리.md` '서면을 나눈 라운드'). 같은 번호가 서면마다 다른 호증이므로 호증을 찾는 도구는 서면 이름으로 가른다.
# 이름은 띄어쓰기·가운뎃점·밑줄·붙임표·괄호를 뺀 꼴로 맞댄다(`서면초안_소음성난청이명.md` = `제출/소음성 난청·이명/` = '## 소음성 난청·이명 건').
# 2026. 11. 8. `/하자보완`: 상병별로 나눈 심사청구의 두 서면(호증 14건·27건)을 도구마다 한 번호로 보아, 호증 번호 검사가 두 목록을
# 합쳐 14건짜리 서면의 증 제15~27호증 인용을 통과시켰고, 증거 인용 대조는 번호마다 경로가 짧은 쪽 파일(증 제8호증은 다른 서면의 진단서)을
# 골랐으며, 전 면 읽기와 쟁점 낱말은 같은 번호의 다른 서면 호증 14건을 읽을 대상에서 뺐다. 관문의 서증 압축·제출본 검사는 `제출/` 맨 위만 보아
# '해당 없음'으로 넘겼다.
_NAME_DROP = re.compile(r'[\s·ㆍ・_\-()（）\[\]]')


def name_form(text) -> str:
    """서면 이름·폴더 이름·목록 절 제목을 맞대는 꼴."""
    import unicodedata
    return _NAME_DROP.sub('', unicodedata.normalize('NFC', str(text)))


def draft_name(path) -> str:
    """`서면초안_{이름}.md` 의 이름(name_form). `서면초안.md` 와 다른 파일은 ''."""
    stem = Path(path).stem
    return name_form(stem[len('서면초안'):]) if stem.startswith('서면초안') else ''


def split_names(out_dir) -> list[str]:
    """서면을 나눈 라운드의 서면 이름. `출력/` 에 `서면초안.md` 가 없고 `서면초안_{이름}.md` 가 둘 이상일 때만이다(evidence_cite_review.drafts_of)."""
    out_dir = Path(out_dir)
    if not out_dir.is_dir() or (out_dir / '서면초안.md').is_file():
        return []
    names = sorted({draft_name(p) for p in out_dir.glob('서면초안_*.md') if not re.search(r'본문|백업|\.bak', p.name)} - {''})
    return names if len(names) > 1 else []


def name_owner(text, names) -> str | None:
    """글(폴더 이름·목록 절 제목·파일 이름)이 가리키는 서면 이름. 이름꼴이 그 이름을 담으면 그 서면이고, 여럿이면 긴 것이다."""
    t = name_form(text)
    hit = [n for n in names if len(n) >= 2 and n in t]
    return max(hit, key=len) if hit else None


def folder_owner(path, base, names) -> str | None:
    """파일이 어느 서면의 폴더 아래에 있는지(base 아래 폴더 이름으로). 서면의 폴더가 아니면 None."""
    path, base = Path(path), Path(base)
    try:
        parts = path.relative_to(base).parts[:-1]
    except ValueError:
        parts = path.parts[:-1]
    for part in parts:
        owner = name_owner(part, names)
        if owner:
            return owner
    return None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    """큰 영상·녹음 원본도 메모리에 통째로 올리지 않고 1MB씩 읽어 해시한다."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


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


def paragraph_texts(xml) -> list[str]:
    """DOCX 파트의 문단 글자를 문단마다 한 번씩 모은다(표 칸 문단 포함).

    글상자(w:txbxContent) 안의 문단은 바깥 문단에 붙이지 않고 그 뒤에 따로 내보낸다.
    mc:Fallback 은 mc:Choice 와 같은 내용의 옛 형식 사본이므로 읽지 않는다.
    """
    paragraph, text = '{%s}p' % NS['w'], '{%s}t' % NS['w']
    out = []

    def visit(p):
        own, nested = [], []

        def collect(node):
            for child in node:
                if child.tag == MC_FALLBACK:
                    continue
                if child.tag == paragraph:
                    nested.append(child)
                    continue
                if child.tag == text:
                    own.append(child.text or '')
                collect(child)

        collect(p)
        out.append(''.join(own))
        for child in nested:
            visit(child)

    def top(node):
        for child in node:
            if child.tag == MC_FALLBACK:
                continue
            if child.tag == paragraph:
                visit(child)
            else:
                top(child)

    top(xml)
    return out


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

    def files(self, scope):
        """scope 아래 파일 목록과, 이름 규칙으로 건너뛴 폴더(도구 캐시 제외) 목록."""
        scope = self.path(scope)
        if scope.is_file():
            return [scope], []
        if not scope.is_dir():
            raise ValueError('입력 경로가 없습니다: ' + self.rel(scope))
        result, skipped = [], []
        # Do not follow directory symlinks or scan excluded trees.
        import os
        for folder, dirs, names in os.walk(scope, followlinks=False):
            skipped.extend(self.rel(Path(folder) / d) for d in dirs
                           if d in SKIP - CACHE_DIRS and not (Path(folder) / d).is_symlink())
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith('.')
                             and not (Path(folder) / d).is_symlink())
            for name in sorted(names):
                if (name.startswith(('~$', '.')) or '.bak' in name or '.폐기' in name
                        or name in {'자료목록.json', '사건상태.md', '_추출.txt'}):
                    continue
                p = self.path(Path(folder) / name)
                # Inventory unsupported formats too; never silently hide source files.
                result.append(p)
        return sorted(result), sorted(skipped)

    def broken_refs(self):
        """지침·명령이 부르는 스크립트와 명령 파일이 실제로 있는지 본다. 이름을 바꾸고 지침을 고치지 않은 것을 잡는다(2026. 11. 3. `/하자보완`)."""
        guides = [*self.path('.claude/commands').glob('*.md'), *self.path('.claude/skills').glob('*/SKILL.md'),
                  self.path('CLAUDE.md'), *self.root.glob('*/CLAUDE.md'), *self.path('공통').glob('*.md')]
        out = []
        for p in guides:
            if not p.is_file():
                continue
            for ref in re.findall(r'(?<![\w/{}.-])((?:공통|\d_[가-힣]+)/(?:scripts|engine)/[\w.-]+\.(?:py|ps1|bat)|\.claude/commands/[가-힣\w-]+\.md)',
                                  p.read_text(encoding='utf-8-sig')):
                if not self.path(ref).is_file():
                    out.append(f'{self.rel(p)} → {ref}')
        return sorted(set(out))

    def unreferenced_scripts(self):
        """지침(사건·캐시·백업 밖의 모든 md 와 설정)이 파일 이름을 들지 않고 다른 코드(시험 제외)도 부르지 않는 `scripts/` 폴더의 스크립트.
        세션이 쓰는 법을 모르는 도구다. 2026. 11. 3. 지침 없는 배치 파일이, 2026. 11. 5. 담당자가 시켜 11. 4. 만든 메일 초안 도구가
        지침 어디에도 없었다(`/하자보완`). 배치 파일은 CP949 인 것도 있으므로 UTF-8 로 읽히지 않으면 CP949 로 읽는다."""
        import os

        def 읽기(p):
            b = p.read_bytes()
            try:
                return b.decode('utf-8-sig')
            except UnicodeDecodeError:
                return b.decode('cp949', errors='replace')

        제외 = SKIP | {'사건', '캐시', '백업', '__pycache__', 'tests', 'models', 'data'}
        글, 코드 = [], {}
        for folder, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in 제외 and (not d.startswith('.') or d == '.claude')]
            for n in names:
                p = Path(folder) / n
                if n.endswith('.md') or n == 'settings.json':
                    글.append(읽기(p))
                elif n.endswith(('.py', '.ps1', '.bat')):
                    코드[p] = 읽기(p)
        지침 = '\n'.join(글)
        out = []
        for p in sorted(코드):
            if p.parent.name != 'scripts' or p.name == '__init__.py':
                continue
            부름 = re.compile(rf'(?<![\w가-힣]){re.escape(p.name)}(?![\w가-힣])|(?:^|\n)\s*(?:import|from)\s+{re.escape(p.stem)}\b')
            if 부름.search(지침) or any(q != p and 부름.search(t) for q, t in 코드.items()):
                continue
            out.append(self.rel(p))
        return out

    def check(self):
        """필수 지침과 명령어가 있고, 지침이 부르는 파일이 있고, 지침이 모르는 스크립트가 없고, 스킬 머리말이 바른지 본다."""
        missing = [f for f in ('CLAUDE.md', '공통/운영.md', '공통/사건상태.md', '공통/브라우저.md', '공통/자체검토.md')
                   if not self.path(f).is_file()]
        commands = {p.stem for p in self.path('.claude/commands').glob('*.md')}
        required = {'검토의견', '판례검색', '서면보강', '서면', '증거정리', '증거발췌', '문체검증',
                    '노동위서류', '예상질의', '녹취', '손배계산', '손배검산', '자체검토', '배당확인', '메일반영', '하자보완'}
        missing.extend('.claude/commands/' + n + '.md' for n in sorted(required - commands))
        skill_errors = []
        for p in self.path('.claude/skills').glob('*/SKILL.md'):
            text = p.read_text(encoding='utf-8-sig')
            match = re.match(r'---\s*\n(.*?)\n---', text, re.S)
            if not match or not re.search(r'^name:\s*\S+', match[1], re.M) or not re.search(r'^description:\s*\S+', match[1], re.M):
                skill_errors.append(self.rel(p))
            elif re.search(r'^name:\s*(.+)$', match[1], re.M)[1].strip() != p.parent.name:
                skill_errors.append(self.rel(p))
        broken, unreferenced = self.broken_refs(), self.unreferenced_scripts()
        return {'missing': missing, 'skill_errors': skill_errors, 'broken_refs': broken, 'unreferenced': unreferenced,
                'ok': not missing and not skill_errors and not broken and not unreferenced}

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
        found, skipped = self.files(scope)
        current = {self.rel(p): {'sha256': digest_file(p), 'bytes': p.stat().st_size} for p in found}
        target = self.path(scope / '작업' / '자료목록.json')
        if not target.is_relative_to(scope):
            raise ValueError('사건 상태 경로가 사건 밖으로 연결되어 있습니다.')
        old = read_json(target).get('files', {}) if target.exists() else {}
        result = {'first_scan': not target.exists(), 'file_count': len(current),
                  'added': sorted(current.keys() - old.keys()),
                  'changed': sorted(k for k in current.keys() & old.keys() if current[k] != old[k]),
                  'deleted': sorted(old.keys() - current.keys()), 'accepted': accept,
                  # 이름 규칙으로 목록에서 뺀 폴더. 원자료가 들어 있으면 폴더 이름을 바꾼다
                  'skipped_dirs': skipped}
        if accept:
            write_json(target, {'version': VERSION, 'at': stamp(), 'scope': self.rel(scope),
                                'files': current, 'note': '파일 기준 목록. 법적 검토 완료를 의미하지 않음.'})
        return result

    def extract(self, value):
        p = self.path(value)
        suffix = p.suffix.lower()
        if suffix not in EXTRACTABLE:           # 큰 영상·녹음을 해시하기 전에 거른다
            raise ValueError('텍스트 추출 미지원 형식: ' + suffix)
        library = 'stdlib'
        if suffix == '.pdf':
            library = 'pypdf-' + importlib.metadata.version('pypdf')
        source_hash = digest_file(p)
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
                    paragraphs.extend(paragraph_texts(xml))
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
