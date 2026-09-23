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

사건 자료(.gitignore 대상)는 보지 않는다. .git 은 g.bat 과 같이 %LOCALAPPDATA%\\labor-automation\\repo.git
이고, 없으면 작업본 안의 .git 을 쓴다. 저장소가 없거나 fetch 가 실패하면 종료 코드 1 — 건너뛰고 본 작업을 한다.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ZERO = '0' * 40


class Git:
    def __init__(self, root: Path):
        self.root = root
        gd = Path(os.environ.get('LOCALAPPDATA') or '/nonexistent') / 'labor-automation' / 'repo.git'
        if gd.is_dir():
            self.base = ['git', f'--git-dir={gd}', f'--work-tree={root}']
        elif (root / '.git').exists():
            self.base = ['git']
        else:
            self.base = None

    def __call__(self, *args, check=True):
        r = subprocess.run(self.base + ['-c', 'core.quotepath=false', *args], cwd=self.root,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        if check and r.returncode:
            raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout if check else r


def blobs_in_history(git: Git, path: str) -> set[str]:
    """origin/main 이력에서 path 가 가졌던 모든 내용(blob)."""
    out = git('log', '--no-renames', '--format=', '--raw', '--no-abbrev', 'origin/main', '--', path)
    found = set()
    for line in out.splitlines():
        if line.startswith(':'):
            _, _, old, new, *_ = line[1:].split(None, 4)
            found |= {old, new}
    return found - {ZERO}


def merge_both(git: Git, root: Path, path: str, old: str) -> bool:
    """이 PC의 고침과 원격의 고침을 합친다. 고친 곳이 겹치지 않아 합쳐지면 True."""
    def blob(rev):
        r = subprocess.run(git.base + ['cat-file', '-p', f'{rev}:{path}'], cwd=root, capture_output=True)
        return r.stdout if r.returncode == 0 else None

    base_b, theirs = blob(old), blob('origin/main')
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


def receive(root: Path) -> int:
    git = Git(root)
    if git.base is None:
        print('저장소를 찾지 못했습니다 — 건너뜁니다.')
        return 1
    r = git('fetch', '-q', 'origin', 'main', check=False)
    if r.returncode:
        print(f'원격에 연결하지 못했습니다 — 건너뜁니다. ({r.stderr.strip()})')
        return 1
    head = git('rev-parse', '-q', '--verify', 'HEAD', check=False)
    old = head.stdout.strip() if head.returncode == 0 else None
    remote_since_old = set(git('diff', '--name-only', '-z', '--no-renames', old, 'origin/main').split('\0')) - {''} \
        if old else set()
    git('reset', '-q', '--mixed', 'origin/main')

    got, removed, merged, conflicts, local = [], [], [], [], []
    entries = git('status', '--porcelain=v1', '-z', '--untracked-files=all').split('\0')
    for entry in filter(None, entries):
        code, path = entry[:2], entry[3:]
        if code == ' M':
            mine = git('hash-object', f'--path={path}', '--', path).strip()
            if mine in blobs_in_history(git, path):
                git('checkout', '--', path)
                got.append(path)
            elif path in remote_since_old:
                if merge_both(git, root, path, old):
                    merged.append(path)
                else:
                    conflicts.append(path)
            else:
                local.append(entry)
        elif code == ' D':
            git('checkout', '--', path)
            got.append(path)
        elif code == '??':
            history = blobs_in_history(git, path)
            if history and git('hash-object', f'--path={path}', '--', path).strip() in history:
                (root / path).unlink()
                removed.append(path)
            else:
                local.append(entry)
        else:
            local.append(entry)

    print(f'원격에서 받은 파일 {len(got)}개, 원격에서 지운 파일 {len(removed)}개.')
    for p in got:
        print(f'  받음  {p}')
    for p in removed:
        print(f'  지움  {p}')
    for p in merged:
        print(f'  합침  {p}  (원격 고침과 이 PC 고침을 함께 살림 — 올릴 때 이 PC 변경으로 잡힌다)')
    if conflicts:
        print('충돌 — 원격도 고치고 이 PC에서도 고친 파일입니다. 올리지 말고 사용자에게 확인하십시오:')
        for p in conflicts:
            print(f'  충돌  {p}')
    print(f'이 PC의 변경 {len(local)}건은 그대로 두었습니다(다음 단계에서 status 로 확인).')
    return 2 if conflicts else 0


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2], help=argparse.SUPPRESS)
    args = ap.parse_args()
    sys.exit(receive(args.root.resolve()))


if __name__ == '__main__':
    main()
