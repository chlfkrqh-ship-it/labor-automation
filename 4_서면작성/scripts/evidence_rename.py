"""호증번호 접두어를 증거 파일에 일괄로 붙인다.

호증번호 부여는 사람이 판단하고, 이 스크립트는 적용만 한다. 계획 파일에 적힌
대로만 바꾸며 스스로 번호를 매기지 않는다. 이름을 임의로 줄이지 않으므로
계획에 적은 이름과 실제 파일명이 언제나 같다.

    python 4_서면작성/scripts/evidence_rename.py 계획.json           # 미리보기
    python 4_서면작성/scripts/evidence_rename.py 계획.json --apply   # 적용

계획.json:
    {"items": [{"path": "4_서면작성/사건/{사건}/라운드1/우리증거/문서.pdf",
                "호증": "노제24호증"},
               {"path": "...변경할 이름이 따로 있으면...",
                "호증": "노제25호증", "name": "노제25호증_징계처분서.pdf"}]}

`name` 을 적으면 그 이름을 그대로 쓴다. 법원에서 내려받은 파일명은 제목이 두 번
들어가고 대리인 이름이 붙어 있으므로, 그때 짧은 이름을 함께 지정한다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALREADY = re.compile(r'^(갑|을|을가|을나|노|사)\s*제?\s*\d+\s*호증')


def plan_one(item):
    source = (ROOT / item['path']).resolve()
    label = item['호증'].strip()
    result = {'path': item['path'], '호증': label}
    if not source.is_relative_to(ROOT):
        return dict(result, status='루트밖')
    if not source.is_file():
        return dict(result, status='없음')
    if ALREADY.match(source.name):
        return dict(result, status='이미부여', name=source.name)

    name = item.get('name') or label + '_' + source.name
    if Path(name).name != name:
        return dict(result, status='이름오류', name=name)
    target = source.with_name(name)
    return dict(result, status='변경', name=name,
                _source=source, _target=target)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('plan', help='계획 JSON 경로')
    parser.add_argument('--apply', action='store_true', help='실제로 이름을 바꾼다')
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
    rows = [plan_one(item) for item in plan['items']]

    changing = [r for r in rows if r['status'] == '변경']
    sources = {r['_source'] for r in changing}
    targets = [r['_target'] for r in changing]
    for row in changing:
        if targets.count(row['_target']) > 1 or (row['_target'].exists()
                                                 and row['_target'] not in sources):
            row['status'] = '이름충돌'

    applied = 0
    if args.apply:
        for row in rows:
            if row['status'] == '변경':
                row['_source'].rename(row['_target'])
                applied += 1

    output = {
        'applied': args.apply,
        'renamed': applied,
        'items': [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows],
        'blocked': [r['path'] for r in rows if r['status'] not in ('변경', '이미부여')],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not args.apply:
        print('\n미리보기입니다. 적용하려면 --apply 를 붙입니다.', file=sys.stderr)
    return 1 if output['blocked'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
