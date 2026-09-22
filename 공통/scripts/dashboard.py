"""사건 현황을 한 장으로 만든다.

폴더에 이미 있는 것만 읽는다. 새로 입력할 자료가 없고, 이 파일은 아무것도
고치지 않는다. 결과는 `공통/캐시/현황.html` 에 쓰고 재생성되는 파일로 다룬다.

    python 공통/scripts/dashboard.py            # 만들고 경로를 알려 준다
    python 공통/scripts/dashboard.py --open     # 만들고 바로 연다
    python 공통/scripts/dashboard.py --json     # 표만 JSON 으로

표에 나오는 수치는 판단이 아니라 관측이다. '다음 할 일'은 폴더 상태에서 짐작한
것이므로 그대로 따르지 말고 사건을 열어 보고 정한다.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_ROOTS = ['1_검토의견/사건', '3_서면보강/사건', '4_서면작성/사건',
              '5_녹취록/사건', '6_손해배상계산/사건']
SKIP_CASE = {'_템플릿', '.claude'}
MARKERS = re.compile(r'\[내용 확인 필요\]|\[확인 필요\]|【확인 필요】|\[반박 보완 필요\]|\[내용 보완 필요\]')
OUT = ROOT / '공통/캐시/현황.html'


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


style_check = load('4_서면작성/scripts/style_check.py', 'style_check')
citation_check = load('4_서면작성/scripts/citation_check.py', 'citation_check')


def newest(folder: Path):
    latest = 0
    for dp, dns, fns in os.walk(folder):
        dns[:] = [d for d in dns if d not in ('__pycache__', '추출캐시')]
        for f in fns:
            try:
                latest = max(latest, os.path.getmtime(os.path.join(dp, f)))
            except OSError:
                pass
    return latest


def open_items(case: Path, rounds):
    """아직 채우지 못했다고 표시해 둔 자리의 수."""
    total = 0
    targets = list((case / '증거관리').glob('*.md'))
    if rounds:
        targets += list((case / rounds[-1]).rglob('*.md'))
    for p in targets:
        try:
            total += len(MARKERS.findall(p.read_text(encoding='utf-8-sig')))
        except OSError:
            pass
    return total


def survey():
    rows = []
    for base in CASE_ROOTS:
        folder = ROOT / base
        if not folder.is_dir():
            continue
        for case in sorted(p for p in folder.iterdir() if p.is_dir()):
            if case.name in SKIP_CASE:
                continue
            rounds = sorted((p.name for p in case.iterdir()
                             if p.is_dir() and p.name.startswith('라운드')),
                            key=lambda n: int(re.sub(r'\D', '', n) or 0))
            draft = None
            for r in reversed(rounds):
                candidate = case / r / '출력' / '서면초안.md'
                if candidate.is_file():
                    draft = candidate
                    break
            row = {
                'folder': base.split('/')[0],
                'case': case.name,
                'rounds': len(rounds),
                'latest_round': rounds[-1] if rounds else '',
                'draft': draft.relative_to(ROOT).as_posix() if draft else '',
                'updated': time.strftime('%Y-%m-%d', time.localtime(newest(case))),
                'open_items': open_items(case, rounds),
                'style': None, 'citation': None, 'note': '',
            }
            if draft:
                try:
                    s = style_check.check(draft)
                    row['style'] = s['violation_count']
                    row['sentence_mean'] = s['measured']['sentence_chars_mean']
                except Exception as exc:                      # 검사 실패를 현황판이 삼키지 않는다
                    row['note'] = '문체검사 실패: %s' % type(exc).__name__
                if (case / '증거관리').is_dir():
                    try:
                        c = citation_check.check(draft, case)
                        row['citation'] = len(c['not_in_list'])
                    except Exception as exc:
                        row['note'] = (row['note'] + ' / 인용검사 실패: %s'
                                       % type(exc).__name__).strip(' /')
            row['next'] = suggest(case, rounds, draft, row)
            rows.append(row)
    return sorted(rows, key=lambda r: r['updated'], reverse=True)


def suggest(case: Path, rounds, draft, row):
    """폴더 상태에서 짐작한 다음 할 일. 근거로 삼지 않는다."""
    if not rounds:
        # 검토의견·녹취·손배는 라운드 공방 구조가 아니다.
        return '—' if row['folder'] != '4_서면작성' else '라운드 폴더 없음'
    last = case / rounds[-1]
    theirs = last / '상대증거'
    if theirs.is_dir() and any(theirs.iterdir()) and not draft:
        return '상대 자료가 있는데 초안이 없음'
    if not draft:
        return '초안 없음'
    final = last / '출력' / '최종서면.docx'
    if not final.is_file():
        return 'DOCX 미생성'
    if row['citation']:
        return '목록에 없는 호증 인용 %d건' % row['citation']
    if row['style']:
        return '문체 위반 %d건' % row['style']
    if row['open_items']:
        return '미해결 표시 %d건' % row['open_items']
    return '—'


def cell(value, warn=False):
    if value is None:
        return '<td class="dim">—</td>'
    css = 'warn' if warn and value else ('ok' if value == 0 else '')
    return '<td class="%s">%s</td>' % (css, html.escape(str(value)))


def render(rows):
    body = []
    for r in rows:
        body.append(
            '<tr><td class="case"><b>%s</b><span class="dim"> · %s</span></td>'
            '<td>%s</td><td>%s</td>%s%s%s<td class="next">%s</td></tr>' % (
                html.escape(r['case']), html.escape(r['folder']),
                html.escape(r['latest_round'] or '—'), r['updated'],
                cell(r['open_items'], warn=True),
                cell(r['citation'], warn=True),
                cell(r['style'], warn=True),
                html.escape(r['next'] + ((' · ' + r['note']) if r['note'] else ''))))
    # CSS 에 % 가 들어 있어 %-포맷을 쓰지 않는다.
    return (TEMPLATE
            .replace('{{when}}', time.strftime('%Y-%m-%d %H:%M'))
            .replace('{{count}}', str(len(rows)))
            .replace('{{rows}}', '\n'.join(body)))


TEMPLATE = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>사건 현황</title>
<style>
:root { --bg:#fbfbfa; --fg:#1c1b19; --dim:#8a8781; --line:#e4e2dd;
        --warn:#a8331a; --ok:#2f6b3f; --head:#f2f0eb; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#1b1a18; --fg:#eceae5; --dim:#918d86; --line:#33312d;
  --warn:#e2846c; --ok:#7fb98d; --head:#232220; } }
* { box-sizing:border-box; }
body { margin:0; padding:2rem 1.25rem; background:var(--bg); color:var(--fg);
  font:15px/1.6 "Malgun Gothic","맑은 고딕",system-ui,sans-serif; }
.wrap { max-width:1100px; margin:0 auto; }
h1 { font-size:1.35rem; margin:0 0 .25rem; letter-spacing:-.01em; }
.sub { color:var(--dim); font-size:.85rem; margin-bottom:1.5rem; }
.scroll { overflow-x:auto; border:1px solid var(--line); border-radius:8px; }
table { border-collapse:collapse; width:100%; min-width:760px; }
th,td { padding:.6rem .75rem; text-align:left; border-bottom:1px solid var(--line);
  white-space:nowrap; }
th { background:var(--head); font-weight:600; font-size:.8rem; color:var(--dim);
  position:sticky; top:0; }
tr:last-child td { border-bottom:none; }
td.case { white-space:normal; min-width:15rem; }
td.next { white-space:normal; color:var(--dim); }
.dim { color:var(--dim); }
.warn { color:var(--warn); font-weight:600; }
.ok { color:var(--ok); }
footer { margin-top:1.25rem; color:var(--dim); font-size:.8rem; }
</style></head><body><div class="wrap">
<h1>사건 현황</h1>
<div class="sub">{{when}} 기준 · {{count}}건 · 폴더에 있는 자료만 읽어 만들었습니다</div>
<div class="scroll"><table>
<thead><tr><th>사건</th><th>최근 라운드</th><th>최근 활동</th>
<th>미해결 표시</th><th>목록 밖 호증</th><th>문체 위반</th><th>다음 할 일(짐작)</th></tr></thead>
<tbody>
{{rows}}
</tbody></table></div>
<footer>수치는 관측이고 판단이 아닙니다. '다음 할 일'은 폴더 상태에서 짐작한 것이므로
그대로 따르지 말고 사건을 열어 보고 정합니다. 다시 만들려면
<code>python 공통/scripts/dashboard.py</code> 를 실행합니다.</footer>
</div></body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--open', action='store_true', dest='open_it')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    rows = survey()
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(rows), encoding='utf-8')
    print('%s  (%d건)' % (OUT.relative_to(ROOT).as_posix(), len(rows)))
    for r in rows[:8]:
        print('  %-26s %-7s %s  미해결 %-3d  %s'
              % (r['case'][:26], r['latest_round'] or '-', r['updated'],
                 r['open_items'], r['next']))
    if args.open_it:
        os.startfile(OUT)                                    # noqa: S606 (Windows 전용)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
