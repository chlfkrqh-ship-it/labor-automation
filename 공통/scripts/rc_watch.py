"""Claude 앱이 다시 켜졌는지 보고, 원격 제어를 다시 붙일 창을 고른다(원격 제어 자동 복구).

앱이 업데이트로 혼자 다시 켜지면 모든 창의 원격 제어가 꺼진다. 앱의 예약 작업 `rc-watch`(가벼운 모델, 30분마다)가
사건 지침이 없는 폴더 `%LOCALAPPDATA%\\노동사건자동화\\원격복구\\` 에서 이 스크립트의 사본을 돌린다.

    python -B rc_watch.py                 # 감시: 첫 줄 NOTHING(할 일 없음) 또는 WAKE(깨울 창 JSON)
    python -B rc_watch.py wait 10         # 원격 제어가 붙기를 잠깐 기다린다(초, 최대 60)
    python -B rc_watch.py result "..."    # 깨운 결과를 기록에 한 줄 남긴다
    python -B 공통/scripts/rc_watch.py install [--cron "13,43 * * * *"] [--wait]   # 설치(앱을 끈 채로)

다시 켜졌는지는 앱 주 프로세스(claude.exe 가운데 --type= 이 없는 것)의 시작 시각이 지난 확인 때와 다른지로 본다.
같은 시작 시각에는 한 번만 WAKE 를 낸다(고르는 즉시 기준점을 옮기므로 작업이 중간에 멈춰도 두 번 깨우지 않는다).
고르는 창은 재시작 전 24시간 안에 쓴 창 가운데 최근 것 3개까지이다. 보관한 창, 원격 제어를 직접 끈 창,
이 감시 작업이 연 창은 뺀다. 창마다 원격 제어가 켜져 있었는지는 앱이 남기지 않아서 알 수 없다.

install 은 앱이 꺼져 있을 때만 한다. 앱이 켜져 있으면 예약 작업 목록(scheduled-tasks.json)을 앱이 다시 덮어쓴다.
출력은 ASCII JSON 이다(Windows 콘솔 인코딩과 무관).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

TASK_ID = 'rc-watch'
TASK_NAME = '원격 제어 자동 복구'
DEFAULT_CRON = '13,43 * * * *'      # 30분마다(:00·:30 을 피함)
MODEL = 'claude-haiku-5-5'
LOOKBACK_MS = 24 * 3600 * 1000      # 재시작 전 이만큼 안에 쓴 창만
MAX_TARGETS = 3
LOG_KEEP = 500                      # 기록 파일에 남기는 줄 수
WAKE_TEXT = '원격 제어 재연결용이다. 작업하지 말고 대기라고만 답하라'
ALLOW = [
    'Bash(python -B rc_watch.py:*)',
    'PowerShell(python -B rc_watch.py:*)',
    'mcp__ccd_session_mgmt__set_remote_control',
    'mcp__ccd_session_mgmt__send_message',
    'mcp__ccd_session_mgmt__get_session',
]

PROMPT = f"""원격 제어 복구 점검만 한다. 아래 말고는 파일을 읽거나 도구를 쓰지 않는다.

1. `python -B rc_watch.py` 를 실행한다.
2. 출력 첫 줄이 `NOTHING` 이면 '이상 없음' 한 줄로 바로 끝낸다.
3. 첫 줄이 `WAKE` 이면 둘째 줄 JSON 의 `targets` 마다 차례로 한다. 한 창에 아래 두 메시지 말고는 보내지 않는다.
   a. `set_remote_control` 로 그 창(`id`)의 원격 제어를 켠다.
   b. `send_message` 로 그 창에 `/remote-control` 만 보낸다.
   c. `python -B rc_watch.py wait 10` 을 실행한 뒤 `get_session` 으로 그 창의 원격 제어가 켜졌는지 본다. 켜졌으면 결과를 `ok` 로 하고 다음 창으로 간다.
   d. 켜지지 않았거나 알 수 없으면 `send_message` 로 `{WAKE_TEXT}` 를 보내고 결과를 `msg` 로 한다. 도구가 거부되면 `fail` 로 한다.
4. `python -B rc_watch.py result "창id앞8자리=결과 ..."` 로 한 줄 남긴 뒤, 창 제목과 결과를 한 줄씩 적고 끝낸다.
"""


def local_base() -> Path:
    local = os.environ.get('LOCALAPPDATA')
    return Path(local) if local else Path.home() / 'AppData' / 'Local'


def watch_dir() -> Path:
    return local_base() / '노동사건자동화' / '원격복구'


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def app_start() -> str | None:
    """앱 주 프로세스의 시작 시각(UTC ISO). 앱이 꺼져 있으면 None."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" | Where-Object { "
          "($_.ExecutablePath -like '*\\WindowsApps\\Claude_*' -or $_.ExecutablePath -like '*\\AnthropicClaude\\*') "
          "-and $_.CommandLine -notmatch '--type=' } | ForEach-Object { "
          "$_.CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }")
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                             capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    times = sorted(t.strip() for t in out.splitlines() if t.strip())
    return times[0] if times else None


def iso_ms(text: str) -> int:
    return int(datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp() * 1000)


def session_files() -> list[Path]:
    roots = [*local_base().glob('Claude-Data/claude_*/claude-code-sessions'),
             Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude-code-sessions']
    return [f for r in roots if r.is_dir() for f in r.glob('*/*/local_*.json')]


def load_sessions(files) -> list[dict]:
    rows = []
    for f in files:
        try:
            rows.append(json.loads(Path(f).read_text(encoding='utf-8')))
        except (OSError, ValueError):
            continue
    return [r for r in rows if isinstance(r, dict)]


def pick_targets(sessions: list[dict], start_ms: int, own_dir: Path) -> list[dict]:
    """재시작 전 24시간 안에 쓴 창 가운데 최근 것 3개까지."""
    own = os.path.normcase(str(own_dir))
    picked = []
    for s in sessions:
        sid, last = s.get('sessionId'), s.get('lastActivityAt')
        if not isinstance(sid, str) or not isinstance(last, (int, float)):
            continue
        if s.get('isArchived') or s.get('remoteControlUserEnabled') is False:
            continue
        if s.get('scheduledTaskId') == TASK_ID or os.path.normcase(str(s.get('cwd') or '')) == own:
            continue
        if not (start_ms - LOOKBACK_MS <= last):
            continue
        picked.append({'id': sid, 'title': s.get('title') or '', 'last': int(last)})
    picked.sort(key=lambda r: r['last'], reverse=True)
    return picked[:MAX_TARGETS]


def read_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def log(base: Path, text: str) -> None:
    path = base / 'log.txt'
    try:
        lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    except OSError:
        lines = []
    lines.append(f'{now_iso()} {text}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines[-LOG_KEEP:]) + '\n', encoding='utf-8')


def decide(state: dict, start: str | None, sessions: list[dict], own_dir: Path) -> tuple[dict, list[dict] | None]:
    """(새 기준점, 깨울 창 또는 None)."""
    if start is None or state.get('appStart') == start:
        return state, None
    new = {**state, 'appStart': start, 'seenAt': now_iso()}
    if 'appStart' not in state and not state.get('armed'):
        return new, None                     # 처음 보는 PC: 기준점만 적는다
    new.pop('armed', None)
    return new, pick_targets(sessions, iso_ms(start), own_dir)


def cmd_check(base: Path) -> int:
    state_path = base / 'state.json'
    state = read_state(state_path)
    start = app_start()
    new, targets = decide(state, start, load_sessions(session_files()), base)
    if new != state:
        write_json(state_path, new)
    if targets is None:
        print('NOTHING')
        print(json.dumps({'appStart': start}))
        if start != state.get('appStart'):
            log(base, f'baseline appStart={start}')
        return 0
    log(base, f'restart appStart={start} targets=' + ','.join(t['id'][6:14] for t in targets))
    if not targets:
        print('NOTHING')
        print(json.dumps({'appStart': start, 'restarted': True, 'targets': []}))
        return 0
    print('WAKE')
    print(json.dumps({'appStart': start, 'targets': [{'id': t['id'], 'title': t['title']} for t in targets]}))
    return 0


def task_store() -> Path | None:
    stores = sorted(local_base().glob('Claude-Data/claude_*/claude-code-sessions/*/*/scheduled-tasks.json'))
    return stores[0] if len(stores) == 1 else None


def cmd_install(cron: str, wait: bool) -> int:
    if wait:
        while app_start() is not None:
            time.sleep(2)
    elif app_start() is not None:
        print(json.dumps({'error': 'app_running', 'hint': 'quit the Claude app first'}))
        return 2
    store = task_store()
    if store is None:
        print(json.dumps({'error': 'task_store_not_found'}))
        return 2
    base = watch_dir()
    base.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), base / 'rc_watch.py')
    write_json(base / '.claude' / 'settings.json', {'permissions': {'allow': ALLOW}})
    state = read_state(base / 'state.json')
    state['armed'] = True                    # 설치 뒤 처음 켜질 때 한 번 깨운다(시험)
    write_json(base / 'state.json', state)

    skill = Path.home() / '.claude' / 'scheduled-tasks' / TASK_ID / 'SKILL.md'
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(f'---\nname: {TASK_ID}\ndescription: 앱이 다시 켜졌으면 직전에 쓰던 창의 원격 제어를 다시 켜고 깨운다'
                     f'(30분마다, 할 일 없으면 바로 끝)\n---\n\n{PROMPT}', encoding='utf-8')

    shutil.copy2(store, store.with_name(store.name + '.bak'))
    data = json.loads(store.read_text(encoding='utf-8'))
    tasks = [t for t in data.get('scheduledTasks', []) if t.get('id') != TASK_ID]
    old = next((t for t in data.get('scheduledTasks', []) if t.get('id') == TASK_ID), {})
    tasks.append({
        'id': TASK_ID, 'displayName': TASK_NAME, 'enabled': True, 'filePath': str(skill),
        'createdAt': old.get('createdAt') or int(time.time() * 1000), 'cwd': str(base),
        'cronExpression': cron, 'model': MODEL, 'permissionMode': 'default',
        **({'lastRunAt': old['lastRunAt']} if old.get('lastRunAt') else {}),
    })
    data['scheduledTasks'] = tasks
    write_json(store, data)
    trust_folder(base)
    log(base, f'install cron="{cron}"')
    print(json.dumps({'installed': True, 'cron': cron, 'cwd': str(base), 'skill': str(skill)}))
    return 0


def trust_folder(folder: Path) -> None:
    """새 폴더를 신뢰 목록(~/.claude.json)에 넣는다. 넣지 않으면 그 폴더의 허용 목록이 먹지 않는다."""
    path = Path.home() / '.claude.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return
    projects = data.setdefault('projects', {})
    keys = {str(folder), str(folder).replace('\\', '/')}
    if all(projects.get(k, {}).get('hasTrustDialogAccepted') for k in keys):
        return
    for k in keys:
        projects.setdefault(k, {})['hasTrustDialogAccepted'] = True
    shutil.copy2(path, path.with_name(path.name + '.rcwatch.bak'))
    write_json(path, data)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd')
    w = sub.add_parser('wait'); w.add_argument('seconds', type=int)
    r = sub.add_parser('result'); r.add_argument('text')
    i = sub.add_parser('install'); i.add_argument('--cron', default=DEFAULT_CRON); i.add_argument('--wait', action='store_true')
    args = ap.parse_args(argv)
    here = Path(__file__).resolve().parent
    base = here if here == watch_dir().resolve() else watch_dir()
    if args.cmd == 'wait':
        time.sleep(max(0, min(args.seconds, 60)))
        print('OK')
        return 0
    if args.cmd == 'result':
        log(base, 'result ' + args.text)
        print('OK')
        return 0
    if args.cmd == 'install':
        return cmd_install(args.cron, args.wait)
    return cmd_check(base)


if __name__ == '__main__':
    sys.exit(main())
