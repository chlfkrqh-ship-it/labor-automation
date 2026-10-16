"""대화가 쉬는 사이 바뀐 사건 기록을 다음 메시지 때 알린다.

담당자는 대화를 끝내지 않은 채 다른 PC나 다른 대화로 옮겨 일하고 돌아온다. 그 사이 바뀐 사건상태와 출력 파일은
OneDrive 가 맞춰 두지만, 이어 쓰는 대화는 그것을 모른다. `.claude/settings.json` 의 두 훅이 이 스크립트를 부른다.

    python -B 공통/scripts/case_watch.py stop     # Stop: 응답을 마칠 때 사건 파일의 수정 시각을 적어 둔다
    python -B 공통/scripts/case_watch.py prompt   # UserPromptSubmit: 그 뒤 바뀐 파일을 맥락으로 알린다

보는 파일은 사건상태(`{폴더}/사건/{사건}/작업/사건상태.md`, `…/라운드N/작업/사건상태.md`)와 사람이 고치는 출력
(사건 폴더 바로 아래와 `출력/` 바로 아래의 docx·pptx·xlsx·hwp·hwpx, `~$` 잠금 파일 제외)이다. 사건상태는 그대로이고
출력 파일만 바뀐 사건은 '사건상태에 기록 없이'로 따로 적는다. 담당자가 직접 고친 것일 수 있다.

기준점은 대화(session_id)마다 `%LOCALAPPDATA%\\노동사건자동화\\사건감시\\` 에 둔다(PC마다 따로, OneDrive 밖).
기준점이 없는 대화(훅을 넣기 전에 시작한 대화)는 대화 기록의 마지막 응답 시각을 기준으로 삼는다.
지난 메시지 뒤 Stop 이 없으면 응답 도중에 보낸 메시지여서 이 대화가 고치는 파일과 섞이므로 알리지 않는다.
다만 대화 기록에 사용자가 끊은 표시가 있거나 3시간이 지났으면 끊긴 응답으로 보고 알린다.
30분 넘게 쉬었으면 `receive.py --auto` 로 시스템 파일도 받는다.

어떤 오류가 나도 종료 코드 0 으로 끝나 메시지를 막지 않는다. 출력은 ASCII JSON 이다(Windows 콘솔 인코딩과 무관).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

STATUS_GLOBS = ('*/사건/*/작업/사건상태.md', '*/사건/*/라운드*/작업/사건상태.md')
OUTPUT_DIRS = ('*/사건/*', '*/사건/*/출력', '*/사건/*/라운드*/출력')
OUTPUT_EXT = {'.docx', '.pptx', '.xlsx', '.hwp', '.hwpx'}
IDLE_RECEIVE = 30 * 60          # 이만큼 쉬었으면 시스템 파일도 받는다
MIDTURN_GRACE = 3 * 3600        # Stop 없이 이만큼 지나면 끊긴 응답으로 본다
KEEP_DAYS = 30                  # 기준점 파일을 남겨 두는 날 수
SHOW_CASES, SHOW_FILES = 8, 4
INTERRUPTED = b'[Request interrupted by user'


def default_state_dir() -> Path:
    local = os.environ.get('LOCALAPPDATA')
    base = Path(local) if local else Path.home() / '.cache'
    return base / '노동사건자동화' / '사건감시'


def session_id(data: dict) -> str | None:
    sid = data.get('session_id')
    return sid if isinstance(sid, str) and re.fullmatch(r'[\w.-]{1,128}', sid) else None


def snapshot(root: Path) -> dict[str, list[int]]:
    """사건상태와 출력 파일의 {상대경로: [수정 시각(ns), 크기]}."""
    paths = [p for pat in STATUS_GLOBS for p in root.glob(pat)]
    for pat in OUTPUT_DIRS:
        for d in root.glob(pat):
            if d.is_dir():
                paths += [p for p in d.iterdir()
                          if p.suffix.lower() in OUTPUT_EXT and not p.name.startswith('~$')]
    files = {}
    for p in paths:
        try:
            s = p.stat()
        except OSError:
            continue
        if stat.S_ISREG(s.st_mode):
            files[p.relative_to(root).as_posix()] = [s.st_mtime_ns, s.st_size]
    return files


def load_state(sdir: Path, sid: str) -> dict | None:
    try:
        state = json.loads((sdir / f'{sid}.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def save_state(sdir: Path, sid: str, state: dict) -> None:
    sdir.mkdir(parents=True, exist_ok=True)
    tmp = sdir / f'{sid}.json.tmp'
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, sdir / f'{sid}.json')


def prune(sdir: Path, now: float) -> None:
    for f in sdir.glob('*.json'):
        try:
            if now - f.stat().st_mtime > KEEP_DAYS * 86400:
                f.unlink()
        except OSError:
            pass


def is_interrupt(entry: dict) -> bool:
    """사용자가 응답을 끊은 표시인가. 도구 결과에 같은 글자가 찍힌 것(기록을 grep 한 출력 등)은 아니다."""
    content = (entry.get('message') or {}).get('content')
    if isinstance(content, str):
        return content.startswith(INTERRUPTED.decode())
    return isinstance(content, list) and any(
        isinstance(c, dict) and c.get('type') == 'text' and str(c.get('text', '')).startswith(INTERRUPTED.decode())
        for c in content)


def transcript_times(transcript: str | None) -> tuple[float | None, float | None]:
    """대화 기록(jsonl) 끝부분에서 (마지막 응답 시각, 사용자가 마지막으로 끊은 시각)."""
    if not transcript:
        return None, None
    try:
        with open(transcript, 'rb') as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 4_000_000))
            tail = f.read()
    except OSError:
        return None, None
    reply = cut = None
    for line in reversed(tail.splitlines()):
        want_reply = reply is None and b'"assistant"' in line
        want_cut = cut is None and INTERRUPTED in line
        if not (want_reply or want_cut):
            continue
        try:
            d = json.loads(line)
            t = datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00')).timestamp()
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if want_reply and d.get('type') == 'assistant':
            reply = t
        if want_cut and d.get('type') == 'user' and is_interrupt(d):
            cut = t
        if reply is not None and cut is not None:
            break
    return reply, cut


def run_receive(root: Path) -> str:
    script = root / '공통' / 'scripts' / 'receive.py'
    if not script.exists():
        return ''
    try:
        r = subprocess.run([sys.executable, '-B', str(script), '--auto'], cwd=root,
                           capture_output=True, timeout=40)
    except subprocess.TimeoutExpired:
        return '[시스템 파일 받기] 40초 안에 끝나지 않아 건너뛰었다.'
    except OSError as exc:
        return f'[시스템 파일 받기] 실패 — 건너뜀: {exc}'
    return r.stdout.decode('utf-8', 'replace').strip().replace('새 작업을 열면서', '쉬었던 대화를 이어 가면서')


def stamp(t: float) -> str:
    d = datetime.fromtimestamp(t)
    return f'{d.month}. {d.day}. {d:%H:%M}'


def compose(changes: list[str], cur: dict, since: float, caveat: bool, got: str) -> dict | None:
    context, notice = [], []
    if changes:
        groups: dict[str, tuple[list, list]] = {}
        for rel in changes:
            parts = rel.split('/')
            status, outs = groups.setdefault('/'.join(parts[:3]), ([], []))
            (status if parts[-1] == '사건상태.md' else outs).append((cur[rel][0] / 1e9, '/'.join(parts[3:])))
        order = sorted(groups, key=lambda c: max(t for t, _ in groups[c][0] + groups[c][1]), reverse=True)
        head = (f'[사건 기록 알림] 이 대화의 지난 응답({stamp(since)}) 뒤 이 대화 밖에서 바뀐 사건 파일이다. '
                '다른 PC·다른 대화의 작업이거나 담당자가 직접 고친 것이다.')
        if caveat:
            head += ' 지난 응답이 도중에 끊겼으므로 그 응답에서 이 대화가 고친 파일이 섞여 있을 수 있다.'
        context.append(head)
        for case in order[:SHOW_CASES]:
            status, outs = groups[case]
            files = sorted(status, reverse=True) + sorted(outs, reverse=True)
            listed = ', '.join(f'{name}({stamp(t)})' for t, name in files[:SHOW_FILES])
            more = f' 외 {len(files) - SHOW_FILES}개' if len(files) > SHOW_FILES else ''
            flag = '' if status else '사건상태에 기록 없이 출력 파일만 바뀜 — '
            context.append(f'- {case}: {flag}{listed}{more}')
        if len(order) > SHOW_CASES:
            context.append(f'- 그 밖에 {len(order) - SHOW_CASES}개 사건')
        context.append('이번 요청이 위 사건에 관한 것이면 그 일을 하기 전에 사건상태.md 의 새 항목부터 읽고, 바뀐 출력 파일은 '
                       '지금 파일을 기준으로 삼는다. 사건상태에 기록 없이 바뀐 출력 파일이 담당자 수정본이면 그 사실과 고친 곳을 '
                       "사건상태에 적는다(공통/사건상태.md '지시마다 적기'). 관련 없는 사건이면 무시한다.")
        names = [c.split('/')[-1] for c in order]
        notice.append('사건 기록 알림: ' + ', '.join(names[:3])
                      + (f' 외 {len(names) - 3}건' if len(names) > 3 else '') + ' — 이 대화가 쉬는 사이 바뀜')
    if got:
        context.append(got)
        m = re.search(r'원격에서 받은 파일 (\d+)개, 원격에서 지운 파일 (\d+)개', got)
        if m:
            notice.append(f'시스템 파일 받음 {m[1]}개' + (f'·지움 {m[2]}개' if m[2] != '0' else '')
                          + (' — 충돌 있음' if '충돌' in got else ''))
        else:
            notice.append('시스템 파일 받기 건너뜀')
    if not context:
        return None
    return {'systemMessage': ' / '.join(notice),
            'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': '\n'.join(context)}}


def on_stop(data: dict, root: Path, sdir: Path, now: float | None = None) -> None:
    sid = session_id(data)
    if not sid:
        return
    now = time.time() if now is None else now
    state = load_state(sdir, sid) or {}
    state.update(files=snapshot(root), stop=now)
    save_state(sdir, sid, state)
    prune(sdir, now)


def on_prompt(data: dict, root: Path, sdir: Path, now: float | None = None, receive=run_receive) -> dict | None:
    sid = session_id(data)
    if not sid:
        return None
    now = time.time() if now is None else now
    cur = snapshot(root)
    state = load_state(sdir, sid)
    changes, since, caveat, idle = [], 0.0, False, 0.0
    if state:
        stop, prompt = state.get('stop', 0.0), state.get('prompt', 0.0)
        last = max(stop, prompt)
        if prompt > stop:                               # 지난 메시지 뒤 응답이 끝나지 않았다
            _, cut = transcript_times(data.get('transcript_path'))
            if cut is not None and cut > prompt:        # 사용자가 끊었다
                last = cut
            elif now - prompt < MIDTURN_GRACE:          # 응답 도중에 보낸 메시지
                last = None
        if last is not None:
            old = state.get('files', {})
            changes = sorted(k for k, v in cur.items() if old.get(k) != v)
            since, caveat, idle = last, prompt > stop, now - last
    else:
        reply, _ = transcript_times(data.get('transcript_path'))
        if reply is not None:
            changes = sorted(k for k, v in cur.items() if v[0] / 1e9 > reply)
            since, idle = reply, now - reply
        state = {}
    state.update(files=cur, prompt=now)
    save_state(sdir, sid, state)
    got = receive(root) if idle >= IDLE_RECEIVE else ''
    return compose(changes, cur, since, caveat, got)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('mode', choices=['stop', 'prompt'])
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2], help=argparse.SUPPRESS)
    ap.add_argument('--state', type=Path, default=None, help=argparse.SUPPRESS)
    try:
        args = ap.parse_args(argv)
    except SystemExit:                                  # 종료 코드 2 는 메시지를 막으므로 쓰지 않는다
        return 0
    try:
        raw = sys.stdin.buffer.read()
        data = json.loads(raw.decode('utf-8-sig')) if raw.strip() else {}
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    sdir = args.state or default_state_dir()
    out = None
    try:
        if args.mode == 'stop':
            on_stop(data, args.root, sdir)
        else:
            out = on_prompt(data, args.root, sdir)
    except Exception as exc:                            # 훅은 메시지를 막지 않는다
        if args.mode == 'prompt':
            out = {'systemMessage': f'사건 기록 알림 훅 오류 — 건너뜀: {exc}'}
    if out:
        sys.stdout.write(json.dumps(out, ensure_ascii=True))
        sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
