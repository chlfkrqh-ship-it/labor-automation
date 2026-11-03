"""원격(main)에 올라온 시스템 파일을 이 PC 작업본으로 받는다.

다른 PC가 올린 것은 OneDrive 가 작업본을 이미 맞춰 두었지만, 클라우드 세션(claude.ai/code)에서 고쳐
main 에 머지한 것은 작업본에 없다. 그대로 '시스템 파일 올리기'를 하면 작업본의 옛 판이 이 PC의
변경으로 잡혀 원격의 고침을 되돌린다. 이 스크립트가 둘을 가른다.

    python -B 공통/scripts/receive.py

fetch 뒤 HEAD 를 origin/main 으로 옮기고(reset --mixed, 파일은 그대로) 상태를 본다.

- 고침: 작업본 내용이 그 파일의 예전 커밋 판과 같으면 원격 판으로 바꾼다(받음).
- 없음: 원격에 있는데 작업본에 없는 파일은 받는다(원격에서 새로 생긴 것. 이 PC에서 지우고 올리지 않은 경우는 드물고,
  되살아나도 다시 지우면 된다).
- 새 파일: 원격 이력에 있던 파일이고 내용이 예전 커밋 판과 같으면 원격에서 지운 것이므로 지운다.
- 어느 커밋과도 다른 내용은 이 PC에서 고친 것이므로 건드리지 않는다. 그 파일을 원격도 고쳤으면 두 고침을 합치고
  (git merge-file, 고친 곳이 겹치지 않을 때), 겹치면 '충돌'로 알리고 그대로 둔다.

이 PC에서 만들고 원격에 올리지 못한 커밋(push 가 거절되어 남은 것)이 있으면 HEAD 를 origin/main 이 아니라 그 커밋을
origin/main 위에 차례로 다시 쌓은 끝으로 옮긴다(git pull --rebase 와 같다. merge-tree·commit-tree 로 만들어 작업본·색인은
건드리지 않는다). 고침이 이미 원격에 들어간 커밋은 빼고, 원격이 그대로이면 커밋도 그대로 둔다. 원격도 같은 곳을 고쳐
다시 쌓지 못하면 아무것도 바꾸지 않고 그 커밋을 알린다(종료 코드 3). 예전에는 그 커밋을 가지에서 빼고 그 고침을 작업본에서
원격 판으로 되돌렸다(2026. 11. 3. c192369).

색인에 담아 두고 커밋하지 않은 것(다른 세션이 올리려고 add 한 것)은 HEAD 를 옮긴 뒤 다시 담는다. 원격도 그 파일을
고쳤으면 그대로 담으면 원격 고침을 되돌리므로 '풀림'으로 알리고 담지 않는다.

새 작업(세션)을 열면 `.claude/settings.json` 의 시작 훅이 `--auto` 로 부른다. `--auto` 는 PC 구성(아래 repo.git)일 때만
돌고, 클라우드 세션처럼 그 구성이 없으면 아무것도 하지 않는다. 오류가 나도 작업 시작을 막지 않고(종료 코드 0), 받은 것이나
올리지 않은 커밋이 있을 때만 알린다.

사건 자료(.gitignore 대상)는 보지 않는다. 저장소(.git)는 g.bat 과 같은 순서로 찾는다(pc_repo). 없으면 작업본 안의
.git 을 쓴다. 종료 코드는 0 받음(받을 것이 없을 때 포함), 1 저장소가 없거나 fetch 실패(건너뛰고 본 작업을 한다), 2 충돌,
3 올리지 못한 커밋을 다시 쌓지 못해 받지 않음이다. `--auto` 는 늘 0 이다.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ZERO = '0' * 40


def pc_repo() -> Path | None:
    """이 PC의 저장소. %USERPROFILE%, %LOCALAPPDATA%, Claude 앱 가상 폴더 순서로 찾는다(g.bat 과 같다).

    Claude 데스크톱 앱은 스토어 앱이어서, 앱 안에서 %LOCALAPPDATA% 아래 만든 파일은 앱 전용 가상 폴더
    (%LOCALAPPDATA%\\Packages\\Claude_*\\LocalCache\\Local)로 간다. 앱 안의 git 은 그 저장소를 제자리에 있는 것처럼
    보지만, 앱 밖에서 도는 파이썬(스토어판 등)에는 보이지 않는다. 그래서 가상 폴더의 실제 경로까지 본다.
    """
    home, local = os.environ.get('USERPROFILE'), os.environ.get('LOCALAPPDATA')
    candidates = [Path(home) / 'labor-automation' / 'repo.git'] if home else []
    if local:
        candidates.append(Path(local) / 'labor-automation' / 'repo.git')
        candidates += sorted(Path(local).glob('Packages/Claude_*/LocalCache/Local/labor-automation/repo.git'))
    return next((c for c in candidates if c.is_dir()), None)


class Git:
    def __init__(self, root: Path, pc_only: bool = False):
        self.root = root
        gd = pc_repo()
        if gd:
            self.base = ['git', f'--git-dir={gd}', f'--work-tree={root}']
        elif (root / '.git').exists() and not pc_only:
            self.base = ['git']
        else:
            self.base = None

    def __call__(self, *args, check=True):
        r = subprocess.run(self.base + ['-c', 'core.quotepath=false', *args], cwd=self.root,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        if check and r.returncode:
            raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout if check else r


def blobs_in_history(git: Git, path: str, rev: str) -> set[str]:
    """rev(origin/main, 또는 그 위에 이 PC 커밋을 쌓은 끝) 이력에서 path 가 가졌던 모든 내용(blob)."""
    out = git('log', '--no-renames', '--format=', '--raw', '--no-abbrev', rev, '--', path)
    found = set()
    for line in out.splitlines():
        if line.startswith(':'):
            _, _, old, new, *_ = line[1:].split(None, 4)
            found |= {old, new}
    return found - {ZERO}


def merge_both(git: Git, root: Path, path: str, old: str, new: str) -> bool:
    """이 PC의 고침(작업본, old 기준)과 원격의 고침(new)을 합친다. 고친 곳이 겹치지 않아 합쳐지면 True."""
    def blob(rev):
        r = subprocess.run(git.base + ['cat-file', '-p', f'{rev}:{path}'], cwd=root, capture_output=True)
        return r.stdout if r.returncode == 0 else None

    base_b, theirs = blob(old), blob(new)
    if base_b is None or theirs is None:
        return False
    file = root / path
    mine = file.read_bytes()
    if b'\0' in mine + base_b + theirs:
        return False                                    # 바이너리는 합치지 않는다
    crlf = b'\r\n' in mine
    parts = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in (('mine', mine.replace(b'\r\n', b'\n')), ('base', base_b), ('theirs', theirs)):
            f = Path(tmp) / name
            f.write_bytes(data)
            parts.append(str(f))
        r = subprocess.run(git.base + ['merge-file', '-p', *parts], cwd=root, capture_output=True)
    if r.returncode != 0:
        return False
    merged = r.stdout.replace(b'\n', b'\r\n') if crlf else r.stdout
    file.write_bytes(merged)
    return True


class NotStacked(Exception):
    """올리지 못한 커밋을 원격 main 위에 다시 쌓지 못한 까닭."""


def commit_like(git: Git, commit: str, tree: str, parent: str) -> str:
    """commit 의 저자·날짜·글 그대로 tree 를 parent 위에 커밋한다(rebase 가 하는 것과 같다)."""
    raw = subprocess.run(git.base + ['cat-file', 'commit', commit], cwd=git.root, capture_output=True,
                         check=True).stdout
    header, _, message = raw.partition(b'\n\n')
    author = next((line[7:] for line in header.split(b'\n') if line.startswith(b'author ')), b'')
    m = re.fullmatch(r'(.*) <(.*)> (\d+ [+-]\d{4})', author.decode('utf-8', 'replace'))
    env = dict(os.environ, GIT_AUTHOR_NAME=m[1], GIT_AUTHOR_EMAIL=m[2], GIT_AUTHOR_DATE='@' + m[3]) if m else None
    r = subprocess.run(git.base + ['commit-tree', tree, '-p', parent], cwd=git.root, input=message, env=env,
                       capture_output=True)
    if r.returncode:
        raise NotStacked('커밋을 만들지 못함 — ' + (r.stderr.decode('utf-8', 'replace').strip().splitlines() or [''])[0])
    return r.stdout.decode().strip()


def stack_on_remote(git: Git, commits: list[str]) -> tuple[str, list[str]]:
    """원격에 없는 이 PC 커밋(오래된 것부터)을 origin/main 위에 차례로 다시 쌓는다. 작업본·색인·HEAD 는 건드리지 않는다.

    새 끝 커밋과, 고침이 이미 원격에 들어가 있어 뺀 커밋(같은 고침을 commit-tree 로 따로 올린 것 등)을 돌려준다.
    """
    tip, dropped = git('rev-parse', 'origin/main').strip(), []
    for c in commits:
        parents = git('rev-parse', f'{c}^@').split()
        if len(parents) != 1:
            raise NotStacked(f'{c[:7]} 은 부모가 하나가 아닌 커밋(합친 커밋 등)이다')
        r = git('merge-tree', '--write-tree', '--name-only', '--no-messages', '-z', f'--merge-base={parents[0]}',
                tip, c, check=False)
        out = r.stdout.split('\0')
        if r.returncode == 1:
            raise NotStacked('원격도 같은 곳을 고침 — ' + ', '.join(dict.fromkeys(filter(None, out[1:]))))
        if r.returncode:
            raise NotStacked('git merge-tree 실패(git 2.40 이상이 필요하다) — ' + (r.stderr.strip().splitlines() or [''])[0])
        if out[0].strip() == git('rev-parse', f'{tip}^{{tree}}').strip():
            dropped.append(c)
        else:
            tip = commit_like(git, c, out[0].strip(), tip)
    return tip, dropped


def staged_changes(git: Git) -> list[tuple[str, str, str, str]]:
    """색인에 담아 두고 아직 커밋하지 않은 것(다른 세션이 올리려고 add 한 것): (경로, 모드, 담은 개체, HEAD 판 개체)."""
    fields = git('diff', '--cached', '--raw', '-z', '--no-renames', '--no-abbrev').split('\0')
    found = []
    for meta, path in zip(fields[0::2], fields[1::2]):
        _, mode, head_obj, obj, status = meta[1:].split()
        if status != 'U':
            found.append((path, mode, obj, head_obj))
    return found


def restage(git: Git, target: str, held: list[tuple[str, str, str, str]]) -> list[str]:
    """reset 이 풀어 놓은 색인을 다시 담는다. target 이 그 파일을 바꾸었으면(원격도 고침) 담지 않고 그 경로를 돌려준다."""
    unstaged = []
    for path, mode, obj, head_obj in held:
        r = git('rev-parse', '-q', '--verify', f'{target}:{path}', check=False)
        now = r.stdout.strip() if r.returncode == 0 else ZERO
        if now == obj:
            continue
        if now != head_obj:
            unstaged.append(path)                       # 담은 그대로 두면 다음 커밋이 원격 고침을 되돌린다
        elif obj == ZERO:
            git('update-index', '--force-remove', '--', path)
        else:
            git('update-index', '--add', '--cacheinfo', f'{mode},{obj},{path}')
    return unstaged


def not_stacked(git: Git, commits: list[str], why: NotStacked, auto: bool) -> int:
    """올리지 못한 커밋을 다시 쌓지 못했을 때: 아무것도 바꾸지 않고 그 커밋을 알린다."""
    lines = git('log', '--no-walk=unsorted', '--format=%h %s', *reversed(commits)).splitlines()
    if auto:
        more = f' 외 {len(lines) - 1}개' if len(lines) > 1 else ''
        print(f'[시스템 파일 받기] 건너뜀 — 원격에 없는 이 PC 커밋({lines[0]}{more})을 원격 main 위로 옮겨 쌓지 못했다'
              f'({why}). 시스템 파일을 올리기 전에 receive.py 를 직접 돌린다.')
        return 0
    print(f'원격(main)에 없는 이 PC 커밋 {len(lines)}개를 원격 main 위로 옮겨 쌓지 못해 아무것도 받지 않았습니다({why}).')
    for line in lines:
        print(f'  커밋  {line}')
    print("작업본·색인·커밋은 그대로 두었습니다. 이 PC에서 시스템 파일을 올리지 말고, 그 커밋을 만든 세션이 두 고침을 합쳐 "
          "올린 뒤 다시 돌립니다(공통/운영.md '시스템 파일 올리기'의 push 가 거절되면).")
    return 3


def receive(root: Path, auto: bool = False) -> int:
    git = Git(root, pc_only=auto)
    if git.base is None:
        if not auto:
            print('저장소를 찾지 못했습니다 — 건너뜁니다.')
        return 0 if auto else 1
    r = git('fetch', '-q', 'origin', 'main', check=False)
    if r.returncode:
        print(f'원격에 연결하지 못했습니다 — 건너뜁니다. ({r.stderr.strip()})')
        return 0 if auto else 1
    head = git('rev-parse', '-q', '--verify', 'HEAD', check=False)
    old = head.stdout.strip() if head.returncode == 0 else None
    unpushed = git('rev-list', '--reverse', '--topo-order', 'origin/main..HEAD').split() if old else []
    target, dropped = git('rev-parse', 'origin/main').strip(), []
    if unpushed and git('merge-base', '--is-ancestor', 'origin/main', 'HEAD', check=False).returncode == 0:
        target = old                                    # 원격이 그대로다 — 올리지 않은 커밋을 그대로 둔다
    elif unpushed:
        try:
            target, dropped = stack_on_remote(git, unpushed)
        except NotStacked as why:
            return not_stacked(git, unpushed, why, auto)
    remote_since_old = set(git('diff', '--name-only', '-z', '--no-renames', old, target).split('\0')) - {''} \
        if old else set()
    held = staged_changes(git) if old else []
    if old and git('rev-parse', 'HEAD').strip() != old:
        raise RuntimeError('그사이 다른 세션이 커밋하였습니다 — 다시 돌리십시오.')
    git('reset', '-q', '--mixed', target)
    unstaged = restage(git, target, held)

    got, removed, merged, conflicts, local = [], [], [], [], []
    entries = git('status', '--porcelain=v1', '-z', '--untracked-files=all').split('\0')
    for entry in filter(None, entries):
        code, path = entry[:2], entry[3:]
        if code == ' M':
            mine = git('hash-object', f'--path={path}', '--', path).strip()
            if mine in blobs_in_history(git, path, target):
                git('checkout', '--', path)
                got.append(path)
            elif path in remote_since_old:
                if merge_both(git, root, path, old, target):
                    merged.append(path)
                else:
                    conflicts.append(path)
            else:
                local.append(entry)
        elif code == ' D':
            git('checkout', '--', path)
            got.append(path)
        elif code == '??':
            history = blobs_in_history(git, path, target)
            if history and git('hash-object', f'--path={path}', '--', path).strip() in history:
                (root / path).unlink()
                removed.append(path)
            else:
                local.append(entry)
        else:
            local.append(entry)

    pending = git('log', '--format=%h %s', 'origin/main..HEAD').splitlines()
    how = '원격 main 위로 옮겨 쌓았' if target != old else '그대로 두었'
    if auto and not (got or removed or merged or conflicts or unstaged):
        if pending:
            more = f' 외 {len(pending) - 1}개' if len(pending) > 1 else ''
            print(f'[시스템 파일 받기] 원격에 없는 이 PC 커밋({pending[0]}{more})을 {how}다 — push 하면 함께 올라간다.')
        return 0
    if auto:
        print('[시스템 파일 받기] 새 작업을 열면서 원격(main)의 시스템 파일을 받았다. 이번 작업에 쓰는 지침이 아래 목록에 있으면 '
              '다시 읽는다. 사용자에게는 받은 개수와 충돌만 한 줄로 알린다.')
    print(f'원격에서 받은 파일 {len(got)}개, 원격에서 지운 파일 {len(removed)}개.')
    for p in got:
        print(f'  받음  {p}')
    for p in removed:
        print(f'  지움  {p}')
    for p in merged:
        print(f'  합침  {p}  (원격 고침과 이 PC 고침을 함께 살림 — 올릴 때 이 PC 변경으로 잡힌다)')
    for p in unstaged:
        print(f'  풀림  {p}  (색인에 담아 둔 것을 풀었음 — 원격도 고친 파일이라 받은 판과 맞댄 뒤 다시 담는다)')
    if conflicts:
        print('충돌 — 원격도 고치고 이 PC에서도 고친 파일입니다. 올리지 말고 사용자에게 확인하십시오:')
        for p in conflicts:
            print(f'  충돌  {p}')
    if pending:
        print(f'원격에 없는 이 PC 커밋 {len(pending)}개를 {how}습니다. push 하면 함께 올라갑니다:')
        for line in pending:
            print(f'  커밋  {line}')
    if dropped:
        for line in git('log', '--no-walk=unsorted', '--format=%h %s', *reversed(dropped)).splitlines():
            print(f'  뺌    {line}  (고침이 이미 원격에 있는 이 PC 커밋)')
    print(f'이 PC의 변경 {len(local)}건은 그대로 두었습니다(다음 단계에서 status 로 확인).')
    return 2 if conflicts and not auto else 0


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2], help=argparse.SUPPRESS)
    ap.add_argument('--auto', action='store_true', help='새 작업 시작 훅용: PC 구성일 때만, 막지 않고 조용히')
    args = ap.parse_args()
    if not args.auto:
        sys.exit(receive(args.root.resolve()))
    try:
        sys.exit(receive(args.root.resolve(), auto=True))
    except Exception as exc:                            # 시작 훅은 작업을 막지 않는다
        print(f'[시스템 파일 받기] 실패 — 건너뜀: {exc}')
        sys.exit(0)


if __name__ == '__main__':
    main()
