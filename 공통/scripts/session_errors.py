"""최근 세션에서 우리 스크립트가 낸 오류를 모은다(`/하자보완`). 담당자가 말하지 않은 시스템 하자를 찾기 위한 것이다. 모델을 쓰지 않는다.

    python -B 공통/scripts/session_errors.py --시간 26

이 PC의 세션 기록(`~/.claude/projects/{이 폴더}/*.jsonl`)에서 도구 결과에 나온 Traceback 가운데 저장소의 스크립트 안에서 난 것을
스크립트·줄·오류 종류로 묶어 세션 수와 함께 적는다. 세션 기록은 읽기만 하고, 오류 글의 따옴표 안(파일 이름·사건 글)은 지운다.
다른 PC와 클라우드 세션의 기록은 보지 못한다. 시험(`공통/tests`)을 돌리다 난 오류는 세지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
틀 = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')


def 기록_폴더() -> Path:
    return Path.home() / '.claude' / 'projects' / re.sub(r'[^A-Za-z0-9]', '-', str(ROOT))


def 시각(rec: dict) -> float | None:
    try:
        return dt.datetime.fromisoformat(rec['timestamp'].replace('Z', '+00:00')).timestamp()
    except (KeyError, ValueError, AttributeError):
        return None


def 결과_글들(rec: dict):
    """세션 기록 한 줄의 도구 결과 글들."""
    내용 = (rec.get('message') or {}).get('content') if isinstance(rec.get('message'), dict) else None
    for c in 내용 if isinstance(내용, list) else ():
        if isinstance(c, dict) and c.get('type') == 'tool_result':
            t = c.get('content')
            if isinstance(t, list):
                t = '\n'.join(x.get('text', '') for x in t if isinstance(x, dict))
            if isinstance(t, str):
                yield t


def 오류들(글: str):
    """(스크립트, 줄, 함수, 오류 종류). 맨 안쪽의 저장소 스크립트 자리를 쓴다."""
    for tb in 글.split('Traceback (most recent call last)')[1:]:
        자리 = 틀.findall(tb)
        우리 = [x for x in 자리 if re.search(r'[\\/](?:공통|\d_[^\\/"]+)[\\/](?:scripts|engine)[\\/]', x[0])]
        if not 우리 or any(re.search(r'[\\/]공통[\\/]tests[\\/]', x[0]) for x in 자리):
            continue
        줄들 = [re.sub(r'^\s*\d+\t', '', l) for l in tb.splitlines()]      # 읽기 도구의 결과에는 줄 번호가 붙어 있다
        끝 = next((l.strip() for l in 줄들 if re.match(r'[A-Za-z_][\w.]*(?:[Ee]rror|Exception|Exit|Warning|Interrupt)\b', l)), '')
        yield Path(우리[-1][0].replace('\\', '/')).name, 우리[-1][1], 우리[-1][2], re.sub(r"'[^']*'|\"[^\"]*\"", "'…'", 끝)[:100]


def 모으기(폴더: Path, 시간: float) -> list:
    """[(스크립트, 줄, 함수, 오류 종류, 횟수, 세션 수, 마지막 시각)]. 많이 난 것부터."""
    끝 = time.time() - 시간 * 3600
    묶음 = {}
    for f in 폴더.glob('*.jsonl'):
        if f.stat().st_mtime < 끝:
            continue
        with open(f, encoding='utf-8', errors='replace') as 기록:
            for line in 기록:
                if 'Traceback (most recent call last)' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                때 = 시각(rec)
                if 때 is None or 때 < 끝:      # 때가 없는 줄은 앞 대화를 옮긴 것이다
                    continue
                for 글 in 결과_글들(rec):
                    for 키 in 오류들(글):
                        x = 묶음.setdefault(키, {'횟수': 0, '세션': set(), '때': 0})
                        x['횟수'] += 1
                        x['세션'].add(f.stem)
                        x['때'] = max(x['때'], 때)
    return sorted(((*k, v['횟수'], len(v['세션']), v['때']) for k, v in 묶음.items()), key=lambda r: (-r[4], r[0]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='최근 세션에서 우리 스크립트가 낸 오류를 모은다')
    ap.add_argument('--시간', type=float, default=26, help='이 시간(시) 안의 세션 기록을 본다')
    ap.add_argument('--폴더', help='세션 기록 폴더(시험용)')
    a = ap.parse_args(argv)
    줄 = 모으기(Path(a.폴더) if a.폴더 else 기록_폴더(), a.시간)
    for s, n, fn, err, 횟수, 세션, 때 in 줄:
        print(f"{s}:{n} {fn}() — {err or '오류 글 없음'} · {횟수}회, 세션 {세션}개, 마지막 {time.strftime('%m-%d %H:%M', time.localtime(때))}")
    print(f'{a.시간:g}시간 안의 스크립트 오류 {len(줄)}종')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
