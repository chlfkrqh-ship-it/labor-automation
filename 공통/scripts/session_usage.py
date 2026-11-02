"""세션 기록에서 모델·노력 수준과 사용량을 본다. 모델을 쓰지 않는다.

    python -B 공통/scripts/session_usage.py --이세션                  # 지금 세션의 모델·노력(`/하자보완` 1단계). Opus 5.5·최대가 아니면 종료 코드 1
    python -B 공통/scripts/session_usage.py --낱말 노정일 [--시간 240]    # 그 낱말이 나온 세션마다 사용량과 쓰인 곳

이 PC의 세션 기록(`~/.claude/projects/{이 폴더}/*.jsonl`, 하위 작업은 `{세션}/subagents/*.jsonl`)만 읽는다. 기록은 프로젝트 설정
(`cleanupPeriodDays` 10)대로 열흘이 지나면 지워지므로 그 안의 세션만 셀 수 있다. 다른 PC와 클라우드 세션의 기록은 보지 못한다.

- 한 API 응답은 기록에 여러 줄로 남으므로 응답(message.id)마다 한 번만 센다.
- 비용은 응답마다 토큰과 모델 단가(API 요금 환산, 아래 `단가`)로 셈한다. 앱이 기록에 남긴 비용(`/cost` 값)은 세션 중간에 적힌 값이거나
  빈 값이어서(2026. 11. 3. 집 PC: 세션 15개 가운데 7개에만 있고, 응답 566회 가운데 329회까지만 반영된 세션, 0 달러로 남은 세션) 참고로만 적는다.
- '넣은 글'은 응답 다음 요청이 대화에 새로 넣은 토큰(입력·캐시 쓰기)이고, 앞 응답이 부른 도구의 갈래로 나눈다(대략). 도구 결과
  (호증 글·그림, 판례 원문, 검사 결과)는 대화에 얹혀 뒤의 요청마다 다시 읽히므로 사용량의 대부분을 정한다.
  한동안 쉬었다 이어 가거나 창을 다시 열어 캐시가 사라지면 대화 전체를 다시 쓰는데, 그 몫은 '캐시 다시 씀'으로 따로 센다.
- '요금 나눔'은 위 비용을 토큰 종류(입력·캐시 쓰기·캐시 읽기·출력)로 나눈 몫이다. 캐시 읽기는 요청마다 그때까지의 대화를 다시 읽는 값이어서
  대화가 길고 요청이 많을수록 커지고, 캐시 쓰기는 새로 얹힌 글과 쉬었다 이어 다시 쓴 대화의 값이다.

2026. 11. 3. 담당 노무사 "하자 고칠 땐 오푸스 5.5 최대 노력으로 가야 하고", "사용량 측면에서는 어떤 결과가 있었노"(노정일 사건).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_errors import 기록_폴더  # noqa: E402

모델 = 'claude-opus-5-5'
노력 = 'max'

# 100만 토큰당 달러(입력, 출력, 캐시 읽기). 캐시 쓰기는 입력의 1.25배(5분)·2배(1시간)이다. claude-api 스킬의 모델 표(2026. 10. 6.)이고,
# Opus 5.5 는 이 세션 기록의 앱 비용 기록과 맞대어 보았다. 표에 없는 모델의 토큰은 비용에 넣지 않고 따로 적는다.
단가 = {
    'claude-opus-5-5': (4.0, 20.0, 0.20),
    'claude-opus-5': (5.0, 25.0, 0.50),
    'claude-sonnet-5-5': (2.0, 10.0, 0.20),
    'claude-sonnet-5': (2.0, 10.0, 0.20),
    'claude-haiku-5-5': (0.10, 0.50, 0.01),      # 요청이 10만 토큰을 넘으면 0.50·2.50
    'claude-fable-5-1': (10.0, 50.0, 0.25),
}

# 앞 응답이 부른 도구로 다음 요청이 넣은 글의 갈래를 정한다. 앞의 것이 먼저이다.
갈래들 = [
    ('하위 작업', lambda n, s: n in ('Agent', 'Task', 'Workflow')),
    ('메일·팀즈', lambda n, s: 'Microsoft_365' in n),
    ('관문·검사', lambda n, s: re.search(r'final_check|style_check|citation_check|qna_check|unittest|system\.py', s)),
    ('판례', lambda n, s: re.search(r'lbox|lawgo|harvest_titles|cite_check|cite_pdf_check|comwel|법제처|판례', s, re.I)
             or re.search(r'chrome|Browser', n)),
    ('호증·자료 읽기', lambda n, s: re.search(r'evidence_(?:read|words|cite_review|check|split)|ocr_win|증거|호증|자료읽기|읽기기록', s)
                   or (n == 'Read' and re.search(r'\.(?:pdf|png|jpe?g|gif|webp|bmp|tiff?)"', s, re.I))),
    ('쓰기', lambda n, s: n in ('Edit', 'Write', 'NotebookEdit') or re.search(r'docx_merge|docx_build|memo_author', s)),
]


def 갈래(도구: list) -> str:
    for 이름, 맞나 in 갈래들:
        if any(맞나(n, s) for n, s in 도구):
            return 이름
    return '그 밖'


def 줄들(f: Path):
    with open(f, encoding='utf-8', errors='replace') as 기록:
        for line in 기록:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def 맨모델(m) -> str:
    return re.sub(r'\[.*\]$', '', str(m or ''))


def 읽기(f: Path) -> dict:
    """세션 기록 하나를 응답 차례대로 묶는다."""
    응답, 차례, 압축뒤 = {}, [], False
    s = {'처음': None, '끝': None, '첫지시': '', '비용': None, '모델별': {}, '압축': 0, '그림': 0, '도구낱말': '', '말': ''}
    for r in 줄들(f):
        때 = r.get('timestamp')
        if 때:
            s['처음'] = s['처음'] or 때
            s['끝'] = 때
        if r.get('type') == 'cost-state':
            s['비용'] = r.get('totalCostUSD')
            s['모델별'] = {k: v.get('costUSD') for k, v in (r.get('modelUsage') or {}).items() if isinstance(v, dict)}
        m = r.get('message') if isinstance(r.get('message'), dict) else {}
        if r.get('type') == 'user':
            if r.get('isCompactSummary'):
                압축뒤 = True
                s['압축'] += 1
                continue
            내용 = m.get('content')
            글들 = [내용] if isinstance(내용, str) else [b.get('text', '') for b in 내용 or [] if isinstance(b, dict) and b.get('type') == 'text']
            for 글 in ([] if r.get('isMeta') else 글들):
                s['말'] += 글 + '\n'
                if not s['첫지시'] and 글.strip() and not 글.lstrip().startswith('<'):      # 앱이 태그로 싸서 넣은 알림은 지시가 아니다
                    s['첫지시'] = re.sub(r'\s+', ' ', 글.strip())[:80]
            for b in 내용 if isinstance(내용, list) else ():
                if isinstance(b, dict) and b.get('type') == 'tool_result' and isinstance(b.get('content'), list):
                    s['그림'] += sum(1 for x in b['content'] if isinstance(x, dict) and x.get('type') == 'image')
        elif r.get('type') == 'assistant' and m.get('id'):
            k = m['id']
            if k not in 응답:
                응답[k] = {'쓰임': {}, '도구': [], '모델': 맨모델(m.get('model')), '노력': r.get('perTurnEffort') or r.get('effort'), '압축뒤': 압축뒤}
                차례.append(k)
                압축뒤 = False
            x = 응답[k]
            u = m.get('usage') or {}
            if (u.get('output_tokens') or 0) >= (x['쓰임'].get('output_tokens') or 0):
                x['쓰임'] = u
            for b in m.get('content') or []:
                if isinstance(b, dict) and b.get('type') == 'tool_use':
                    입력 = json.dumps(b.get('input'), ensure_ascii=False)
                    x['도구'].append((b.get('name', ''), 입력))
                    s['도구낱말'] += 입력 + '\n'
    s['응답'] = [응답[k] for k in 차례]
    return s


def 값(모델: str, u: dict) -> dict | None:
    """한 응답의 비용을 토큰 종류별로(달러). 단가를 모르는 모델이면 None."""
    p = 단가.get(모델)
    if not p:
        return None
    입, 출, 읽 = p
    입력, 읽기 = u.get('input_tokens') or 0, u.get('cache_read_input_tokens') or 0
    쓰기 = u.get('cache_creation_input_tokens') or 0
    if 모델 == 'claude-haiku-5-5' and 입력 + 읽기 + 쓰기 > 100_000:
        입, 출, 읽 = 0.50, 2.50, 0.05
    if u.get('speed') == 'fast':      # 빠른 모드는 두 배
        입, 출, 읽 = 입 * 2, 출 * 2, 읽 * 2
    cc = u.get('cache_creation') or {}
    한시간, 오분 = cc.get('ephemeral_1h_input_tokens'), cc.get('ephemeral_5m_input_tokens')
    if 한시간 is None and 오분 is None:
        한시간, 오분 = 쓰기, 0      # 나눔이 없으면 1시간 값(비싼 쪽)으로 본다
    else:
        한시간, 오분 = (한시간 or 0) + max(0, 쓰기 - (한시간 or 0) - (오분 or 0)), 오분 or 0
    return {'입력': 입력 * 입 / 1e6, '캐시 쓰기': (오분 * 1.25 + 한시간 * 2) * 입 / 1e6,
            '캐시 읽기': 읽기 * 읽 / 1e6, '출력': (u.get('output_tokens') or 0) * 출 / 1e6}


def 셈(응답: list) -> dict:
    """갈래별 넣은 글과 출력, 모두 합, 토큰 종류별 비용."""
    갈래별, 합 = {}, {'입력': 0, '캐시쓰기': 0, '캐시읽기': 0, '출력': 0, '생각': 0, '최대문맥': 0, '문맥합': 0, '단가모름': 0}
    비용 = {'입력': 0.0, '캐시 쓰기': 0.0, '캐시 읽기': 0.0, '출력': 0.0}
    앞, 앞문맥 = None, 0
    for x in 응답:
        u = x['쓰임']
        v = 값(x['모델'], u)
        for k, d in (v or {}).items():
            비용[k] += d
        넣은 = (u.get('input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0)
        읽은 = u.get('cache_read_input_tokens') or 0
        if v is None:
            합['단가모름'] += 넣은 + 읽은 + (u.get('output_tokens') or 0)
        합['최대문맥'] = max(합['최대문맥'], 넣은 + 읽은)
        합['문맥합'] += 넣은 + 읽은
        다시 = 0 if x['압축뒤'] or 앞 is None else max(0, min(넣은, 앞문맥 - 읽은))      # 앞 요청까지의 대화 가운데 캐시에서 읽지 못한 몫
        앞문맥 = (u.get('cache_creation_input_tokens') or 0) + 읽은      # 캐시에 남은 대화(캐시에 쓰지 않은 입력 몇 토큰은 빼고)
        if 다시:
            갈래별.setdefault('캐시 다시 씀(쉬었다 이음)', [0, 0])[0] += 다시
            넣은 -= 다시
        합['입력'] += u.get('input_tokens') or 0
        합['캐시쓰기'] += u.get('cache_creation_input_tokens') or 0
        합['캐시읽기'] += u.get('cache_read_input_tokens') or 0
        합['출력'] += u.get('output_tokens') or 0
        합['생각'] += (u.get('output_tokens_details') or {}).get('thinking_tokens') or 0
        if x['압축뒤']:
            g = '대화 압축'
        elif 앞 is None:
            g = '시작(지침·첫 지시)'
        else:
            g = 갈래(앞['도구']) if 앞['도구'] else '담당자 말·첨부'
        갈래별.setdefault(g, [0, 0])[0] += 넣은
        갈래별.setdefault(갈래(x['도구']) if x['도구'] else '답·생각', [0, 0])[1] += u.get('output_tokens') or 0
        앞 = x
    return {'갈래': 갈래별, '합': 합, '비용': 비용}


def 하위작업(f: Path) -> dict:
    합 = {'개수': 0, '넣은': 0, '캐시읽기': 0, '출력': 0, '비용': 0.0}
    for g in sorted((f.parent / f.stem / 'subagents').glob('*.jsonl')):
        합['개수'] += 1
        for x in 읽기(g)['응답']:
            u = x['쓰임']
            합['넣은'] += (u.get('input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0)
            합['캐시읽기'] += u.get('cache_read_input_tokens') or 0
            합['출력'] += u.get('output_tokens') or 0
            합['비용'] += sum((값(x['모델'], u) or {}).values())
    return 합


def 수(n) -> str:
    return f'{int(n):,}'


def 요금_나눔(비용: dict) -> str:
    전체 = sum(비용.values()) or 1
    return ' · '.join(f'{k} {v * 100 / 전체:.0f}%' for k, v in 비용.items())


def 보고(f: Path, s: dict, 낱말: str) -> list:
    c = 셈(s['응답'])
    h, sub = c['합'], 하위작업(f)
    s['셈한비용'] = sum(c['비용'].values()) + sub['비용']
    모델들 = sorted({x['모델'] for x in s['응답'] if x['모델']})
    노력들 = sorted({str(x['노력']) for x in s['응답'] if x['노력']})
    전체 = sum(v[0] for v in c['갈래'].values()) or 1
    out = [f"## {f.stem[:8]} · {(s['처음'] or '')[:16]} ~ {(s['끝'] or '')[:16]} (UTC) · {', '.join(모델들) or '모델 모름'} · 노력 {', '.join(노력들) or '모름'}",
           f"첫 지시: {s['첫지시']}",
           f"'{낱말}': 도구 입력 {s['도구낱말'].count(낱말)}회, 담당자 말 {s['말'].count(낱말)}회" if 낱말 else '',
           f"비용 ${s['셈한비용']:.2f}(토큰으로 셈" + (f", 하위 작업 ${sub['비용']:.2f} 포함" if sub['개수'] else '') + ')'
           + (f" · 단가를 모르는 모델 {수(h['단가모름'])}토큰 뺌" if h['단가모름'] else '')
           + f" · 앱 기록 {'$%.2f' % s['비용'] if s['비용'] is not None else '없음'}(중간 값일 수 있음)",
           f"응답 {len(s['응답'])}회 · 대화 압축 {s['압축']}회 · 그림 {s['그림']}장 · 하위 작업 {sub['개수']}개",
           f"토큰: 출력 {수(h['출력'])}(생각 {수(h['생각'])}) · 넣은 글 {수(h['입력'] + h['캐시쓰기'])} · 캐시 읽기 {수(h['캐시읽기'])}"
           + (f" · 하위 작업 넣은 글 {수(sub['넣은'])}·출력 {수(sub['출력'])}" if sub['개수'] else ''),
           f"요금 나눔: {요금_나눔(c['비용'])} · 문맥 최대 {수(h['최대문맥'])}, 평균 {수(h['문맥합'] / max(1, len(s['응답'])))}",
           '', '| 갈래 | 넣은 글 | 비율 | 출력 |', '|---|---:|---:|---:|']
    for g, (넣은, 출력) in sorted(c['갈래'].items(), key=lambda kv: -kv[1][0]):
        out.append(f'| {g} | {수(넣은)} | {넣은 * 100 / 전체:.0f}% | {수(출력)} |')
    return [x for x in out if x != ''] + ['']


def 이세션(폴더: Path, sid: str | None = None) -> tuple:
    """(세션 기록, 모델, 노력). 세션 id 는 CLAUDE_CODE_SESSION_ID, 없으면 가장 최근에 쓰인 기록이다."""
    sid = sid or os.environ.get('CLAUDE_CODE_SESSION_ID')
    f = 폴더 / f'{sid}.jsonl' if sid else None
    if not (f and f.is_file()):
        f = max(폴더.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, default=None)
    if f is None:
        return None, '', ''
    m, e = '', ''
    for r in 줄들(f):
        if r.get('type') == 'assistant' and isinstance(r.get('message'), dict) and r['message'].get('model'):
            m = 맨모델(r['message']['model'])
            e = r.get('perTurnEffort') or r.get('effort') or e
    e = e or os.environ.get('CLAUDE_EFFORT') or os.environ.get('CLAUDE_CODE_EFFORT_LEVEL') or ''
    return f, m, str(e)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='세션 기록의 모델·노력과 사용량')
    ap.add_argument('--이세션', action='store_true', help='지금 세션의 모델·노력을 보고 Opus 5.5·최대가 아니면 종료 코드 1')
    ap.add_argument('--낱말', help='도구 입력이나 담당자 말에 이 낱말이 나온 세션만 본다(사건 이름 등)')
    ap.add_argument('--시간', type=float, help='이 시간(시) 안에 쓰인 세션 기록만 본다')
    ap.add_argument('--폴더', help='세션 기록 폴더(시험용)')
    a = ap.parse_args(argv)
    폴더 = Path(a.폴더) if a.폴더 else 기록_폴더()
    if a.이세션:
        f, m, e = 이세션(폴더)
        맞음 = m == 모델 and e == 노력
        print(f"세션 {f.stem[:8] if f else '없음'} · 모델 {m or '모름'} · 노력 {e or '모름'} — "
              + ('맞음' if 맞음 else f'맞지 않음(하자보완은 {모델}·{노력}, `.claude/commands/하자보완.md`)'))
        return 0 if 맞음 else 1
    끝 = dt.datetime.now().timestamp() - a.시간 * 3600 if a.시간 else 0
    지금 = os.environ.get('CLAUDE_CODE_SESSION_ID')
    본, 비용, 뺀 = 0, 0.0, []
    for f in sorted(폴더.glob('*.jsonl'), key=lambda p: p.stat().st_mtime):
        if f.stat().st_mtime < 끝:
            continue
        if f.stem == 지금:      # 세고 있는 이 세션은 뺀다
            뺀.append(f'{f.stem[:8]}(지금 세션)')
            continue
        s = 읽기(f)
        if a.낱말 and a.낱말 not in s['도구낱말'] and a.낱말 not in s['말']:
            continue
        if a.낱말 and 'session_usage.py' in s['말']:      # 사용량을 세라고 한 세션은 그 사건의 작업이 아니다(요청문에 사건 이름이 든다)
            뺀.append(f'{f.stem[:8]}(사용량을 센 세션)')
            continue
        본 += 1
        print('\n'.join(보고(f, s, a.낱말 or '')))
        비용 += s['셈한비용']
    print(f"세션 {본}개 · 비용 합 ${비용:.2f}(토큰으로 셈)" + (f" · 낱말 '{a.낱말}'" if a.낱말 else '') + (f" · 뺀 세션: {', '.join(뺀)}" if 뺀 else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
