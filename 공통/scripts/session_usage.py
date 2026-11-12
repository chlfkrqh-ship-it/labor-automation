"""세션 기록에서 모델·노력 수준과 사용량을 본다. 모델을 쓰지 않는다.

    python -B 공통/scripts/session_usage.py --이세션                  # 지금 세션의 모델·노력(`/하자보완` 1단계). Opus 5.5·최대가 아니면 종료 코드 1
    python -B 공통/scripts/session_usage.py --재검토                  # 이 세션에서 `전면재검토` 명령이 낸 마지막 응답 묶음의 모델·노력. Fable 5.2·high 가 아니면 종료 코드 1
    python -B 공통/scripts/session_usage.py --낱말 노정일 [--시간 240]    # 그 낱말이 나온 세션마다 사용량과 쓰인 곳
    python -B 공통/scripts/session_usage.py --시간 21                  # 그 시간 안의 세션마다(`/하자보완` 3단계). 범위 안의 응답만 센다

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
- `--시간` 을 주면 그 시간 안에 시각이 찍힌 줄만 센다. 앱은 창을 다시 열 때 지난 세션 기록 끝에 시각 없는 줄(mode·cost-state)을 덧붙여
  파일 시각을 바꾸므로, 파일 시각만으로 고르면 며칠 전 세션이 통째로 섞인다(2026. 11. 4. `/하자보완`: 10. 28.·10. 31. 에 끝난 세션 둘이 21시간
  범위에 들어와 비용 합에 $229 를 더하고, 그 하위 작업 4개가 범위 안의 일로 보였다). 범위 앞에서 이어진 세션은 범위 안의 응답만 세고,
  범위 앞 마지막 응답은 범위 안 첫 응답의 갈래와 캐시 다시 씀을 가르는 데만 쓴다. 범위 안에 응답이 없는 세션은 뺀다.
- 갈라 이어 쓴 세션은 앞 대화의 줄을 원래 uuid·시각 그대로 옮겨 담으므로, 세션을 처음 시각 차례로 읽어 앞서 읽은 세션에 있던 줄은 뒤
  세션에서 세지 않는다(2026. 11. 8. `/하자보완`: 한 대화의 응답 28회가 두 세션에 함께 세였다).

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
from session_errors import 기록_폴더, 시각, 차례  # noqa: E402

모델 = 'claude-opus-5-5'
노력 = 'max'

# 넘기기 전 전면 재검토는 작성 세션이 `전면재검토` 명령을 불러 그 차례만 이 모델·노력으로 돈다(`.claude/commands/전면재검토.md`).
# 노력은 `.claude/settings.json` 의 modelSettings 상한(high)이 정한다. 앱은 그 명령이 낸 응답의 기록 줄에 명령 이름(attributionSkill)을 남긴다.
# 2026. 11. 11. 담당 노무사 "전면 재검토는 Fable high로 하도록 세팅하고", "작업 개시 시에는 오푸스의 최대, 페이블 쓸때는 하이".
재검토_모델 = 'claude-fable-5-2'
재검토_노력 = 'high'
재검토_명령 = '전면재검토'

# 100만 토큰당 달러(입력, 출력, 캐시 읽기). 캐시 쓰기는 입력의 1.25배(5분)·2배(1시간)이다. claude-api 스킬의 모델 표(2026. 10. 6.,
# Fable 5.2 는 2026. 11. 3.)이고, Opus 5.5 는 이 세션 기록의 앱 비용 기록과 맞대어 보았다. 표에 없는 모델의 토큰은 비용에 넣지 않고 따로 적는다.
단가 = {
    'claude-opus-5-5': (4.0, 20.0, 0.20),
    'claude-opus-5': (5.0, 25.0, 0.50),
    'claude-sonnet-5-5': (2.0, 10.0, 0.20),
    'claude-sonnet-5': (2.0, 10.0, 0.20),
    'claude-haiku-5-5': (0.10, 0.50, 0.01),      # 요청이 10만 토큰을 넘으면 0.50·2.50
    'claude-fable-5-1': (10.0, 50.0, 0.25),
    'claude-fable-5-2': (8.0, 40.0, 0.20),
}

# 앞 응답이 부른 도구로 다음 요청이 넣은 글의 갈래를 정한다. 앞의 것이 먼저이다.
# 메일·팀즈 연결의 도구 이름은 커넥터 id 로 시작하므로(`mcp__e78f8043-…__read_resource`) 이름의 끝으로 가른다. 2026. 11. 4. `/하자보완`:
# 'Microsoft_365' 로만 가르다가 메일반영 세션의 메일·팀즈 호출 40회가 모두 '그 밖'으로 잡혔다.
메일_도구 = re.compile(r'Microsoft_365|__(?:outlook_|teams_|sharepoint_)|__(?:chat_message_search|read_resource|search_people|'
                     r'find_meeting_availability|get_me|get_granted_scopes)$')
갈래들 = [
    ('하위 작업', lambda n, s: n in ('Agent', 'Task', 'Workflow')),
    ('메일·팀즈', lambda n, s: 메일_도구.search(n) or 'mail_attach' in s),
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


def 읽기(f: Path, 부터: float | None = None, 본줄: dict | None = None) -> dict:
    """세션 기록 하나를 응답 차례대로 묶는다. 부터(시각)를 주면 그 앞의 줄과 시각 없는 줄(앱이 덧붙인 mode·cost-state, 옮긴 앞 대화)은
    세지 않는다. 그 앞의 응답은 '범위밖'으로 남겨 다음 응답의 갈래를 가르는 데만 쓴다. 첫 지시는 범위 안의 첫 지시이고, 없으면 세션의 첫 지시이다.
    본줄({줄 uuid: 세션})을 주면 앞서 읽은 세션에 있던 줄(갈라 이어 쓴 세션이 옮겨 담은 앞 대화)도 같이 세지 않고 '옮김'으로 둔다.
    옮긴 줄은 시각이 원래 대화의 시각 그대로여서 범위로는 걸러지지 않는다(2026. 11. 8. `/하자보완`: 11. 7. 한 사건의 결과 조회 세션을 갈라
    이은 세션이 앞 대화 157줄을 옮겨 담아, 응답 28회와 메일·팀즈 글 10만 토큰이 두 세션에 함께 세였다)."""
    응답, 차례, 압축뒤 = {}, [], False
    s = {'처음': None, '끝': None, '첫지시': '', '비용': None, '모델별': {}, '압축': 0, '그림': 0, '도구낱말': '', '말': '',
         '줄': set(), '옮겨온곳': set()}
    세션첫지시 = ''
    for r in 줄들(f):
        때 = r.get('timestamp')
        u = r.get('uuid')
        옮김 = bool(본줄 and u and u in 본줄)
        if u:
            s['줄'].add(u)
        if 옮김:
            s['옮겨온곳'].add(본줄[u])
        안 = (부터 is None or (시각(r) or 0) >= 부터) and not 옮김
        if 때 and 안:
            s['처음'] = s['처음'] or 때
            s['끝'] = 때
        if r.get('type') == 'cost-state':
            s['비용'] = r.get('totalCostUSD')
            s['모델별'] = {k: v.get('costUSD') for k, v in (r.get('modelUsage') or {}).items() if isinstance(v, dict)}
        m = r.get('message') if isinstance(r.get('message'), dict) else {}
        if r.get('type') == 'user':
            if r.get('isCompactSummary'):
                압축뒤 = True
                s['압축'] += 안
                continue
            내용 = m.get('content')
            글들 = [내용] if isinstance(내용, str) else [b.get('text', '') for b in 내용 or [] if isinstance(b, dict) and b.get('type') == 'text']
            for 글 in ([] if r.get('isMeta') else 글들):
                지시 = re.sub(r'\s+', ' ', 글.strip())[:80] if 글.strip() and not 글.lstrip().startswith('<') else ''      # 앱이 태그로 싸서 넣은 알림은 지시가 아니다
                세션첫지시 = 세션첫지시 or 지시
                if 안:
                    s['말'] += 글 + '\n'
                    s['첫지시'] = s['첫지시'] or 지시
            for b in 내용 if isinstance(내용, list) and 안 else ():
                if isinstance(b, dict) and b.get('type') == 'tool_result' and isinstance(b.get('content'), list):
                    s['그림'] += sum(1 for x in b['content'] if isinstance(x, dict) and x.get('type') == 'image')
        elif r.get('type') == 'assistant' and m.get('id'):
            k = m['id']
            if k not in 응답:
                # 기록의 effort 는 요청에 실어 보낸 값(output_config.effort, 설정의 상한을 거친 값)이고 perTurnEffort 는 대화에 적힌 차례 표시이다
                응답[k] = {'쓰임': {}, '도구': [], '모델': 맨모델(m.get('model')), '노력': r.get('effort') or r.get('perTurnEffort'), '압축뒤': 압축뒤,
                         '범위밖': not 안, '옮김': 옮김, '명령': r.get('attributionSkill') or ''}
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
                    if not x['범위밖']:
                        s['도구낱말'] += 입력 + '\n'
    s['응답'] = [응답[k] for k in 차례]
    s['첫지시'] = s['첫지시'] or 세션첫지시
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
    """갈래별 넣은 글과 출력, 모두 합, 토큰 종류별 비용. '범위밖' 응답은 세지 않고 다음 응답의 갈래와 캐시 다시 씀을 가르는 데만 쓴다."""
    갈래별, 합 = {}, {'응답': 0, '입력': 0, '캐시쓰기': 0, '캐시읽기': 0, '출력': 0, '생각': 0, '최대문맥': 0, '문맥합': 0, '단가모름': 0}
    비용 = {'입력': 0.0, '캐시 쓰기': 0.0, '캐시 읽기': 0.0, '출력': 0.0}
    앞, 앞문맥 = None, 0
    for x in 응답:
        u = x['쓰임']
        넣은 = (u.get('input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0)
        읽은 = u.get('cache_read_input_tokens') or 0
        다시 = 0 if x['압축뒤'] or 앞 is None else max(0, min(넣은, 앞문맥 - 읽은))      # 앞 요청까지의 대화 가운데 캐시에서 읽지 못한 몫
        앞문맥 = (u.get('cache_creation_input_tokens') or 0) + 읽은      # 캐시에 남은 대화(캐시에 쓰지 않은 입력 몇 토큰은 빼고)
        if x.get('범위밖'):
            앞 = x
            continue
        합['응답'] += 1
        v = 값(x['모델'], u)
        for k, d in (v or {}).items():
            비용[k] += d
        if v is None:
            합['단가모름'] += 넣은 + 읽은 + (u.get('output_tokens') or 0)
        합['최대문맥'] = max(합['최대문맥'], 넣은 + 읽은)
        합['문맥합'] += 넣은 + 읽은
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


def 하위작업(f: Path, 부터: float | None = None) -> dict:
    합 = {'개수': 0, '넣은': 0, '캐시읽기': 0, '출력': 0, '비용': 0.0}
    for g in sorted((f.parent / f.stem / 'subagents').glob('*.jsonl')):
        응답 = [x for x in 읽기(g, 부터)['응답'] if not x['범위밖']]
        if 부터 is not None and not 응답:      # 범위 앞에 돈 하위 작업
            continue
        합['개수'] += 1
        for x in 응답:
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


def 보고(f: Path, s: dict, 낱말: str, 부터: float | None = None) -> list:
    c = 셈(s['응답'])
    h, sub = c['합'], 하위작업(f, 부터)
    s['셈한비용'] = sum(c['비용'].values()) + sub['비용']
    센 = [x for x in s['응답'] if not x['범위밖']]
    옮긴 = sum(1 for x in s['응답'] if x.get('옮김'))
    앞 = len(s['응답']) - len(센) - 옮긴
    모델들 = sorted({x['모델'] for x in 센 if x['모델']})
    노력들 = sorted({str(x['노력']) for x in 센 if x['노력']})
    재 = [x for x in 센 if 재검토_명령 in x.get('명령', '')]
    전체 = sum(v[0] for v in c['갈래'].values()) or 1
    out = [f"## {f.stem[:8]} · {(s['처음'] or '')[:16]} ~ {(s['끝'] or '')[:16]} (UTC) · {', '.join(모델들) or '모델 모름'} · 노력 {', '.join(노력들) or '모름'}"
           + (f" · 범위 앞 응답 {앞}회는 세지 않음" if 앞 else '')
           + (f" · 앞 세션 {', '.join(sorted(x[:8] for x in s.get('옮겨온곳', ())))}에서 옮겨 담은 응답 {옮긴}회는 세지 않음" if 옮긴 else ''),
           f"첫 지시: {s['첫지시']}",
           f"'{낱말}': 도구 입력 {s['도구낱말'].count(낱말)}회, 담당자 말 {s['말'].count(낱말)}회" if 낱말 else '',
           f"비용 ${s['셈한비용']:.2f}(토큰으로 셈" + (f", 하위 작업 ${sub['비용']:.2f} 포함" if sub['개수'] else '') + ')'
           + (f" · 단가를 모르는 모델 {수(h['단가모름'])}토큰 뺌" if h['단가모름'] else '')
           + f" · 앱 기록 {'$%.2f' % s['비용'] if s['비용'] is not None else '없음'}({'세션 전체 값, ' if 앞 else ''}중간 값일 수 있음)",
           f"응답 {h['응답']}회 · 대화 압축 {s['압축']}회 · 그림 {s['그림']}장 · 하위 작업 {sub['개수']}개",
           (f"전면 재검토 응답 {len(재)}회 · 모델 {', '.join(sorted({x['모델'] for x in 재 if x['모델']})) or '모름'}"
            + ('' if {x['모델'] for x in 재 if x['모델']} == {재검토_모델} else f' — {재검토_모델} 가 아닌 응답이 있다(앱이 모델을 바꾸지 않음)')) if 재 else '',
           f"토큰: 출력 {수(h['출력'])}(생각 {수(h['생각'])}) · 넣은 글 {수(h['입력'] + h['캐시쓰기'])} · 캐시 읽기 {수(h['캐시읽기'])}"
           + (f" · 하위 작업 넣은 글 {수(sub['넣은'])}·출력 {수(sub['출력'])}" if sub['개수'] else ''),
           f"요금 나눔: {요금_나눔(c['비용'])} · 문맥 최대 {수(h['최대문맥'])}, 평균 {수(h['문맥합'] / max(1, h['응답']))}",
           '', '| 갈래 | 넣은 글 | 비율 | 출력 |', '|---|---:|---:|---:|']
    for g, (넣은, 출력) in sorted(c['갈래'].items(), key=lambda kv: -kv[1][0]):
        out.append(f'| {g} | {수(넣은)} | {넣은 * 100 / 전체:.0f}% | {수(출력)} |')
    return [x for x in out if x != ''] + ['']


def 이_기록(폴더: Path, sid: str | None = None) -> Path | None:
    """지금 세션의 기록. 세션 id 는 CLAUDE_CODE_SESSION_ID, 없으면 가장 최근에 쓰인 기록이다."""
    sid = sid or os.environ.get('CLAUDE_CODE_SESSION_ID')
    f = 폴더 / f'{sid}.jsonl' if sid else None
    if not (f and f.is_file()):
        f = max(폴더.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, default=None)
    return f


def 재검토(폴더: Path, sid: str | None = None) -> tuple:
    """(세션 기록, 응답들, 스스로 불렀는가). 응답들은 `전면재검토` 명령이 낸 응답(기록 줄의 attributionSkill)이 이어진 마지막 묶음이다.
    한 세션에서 여러 번 불렀으면 마지막 것만 본다. 묶음 바로 앞 응답이 Skill 도구로 그 명령을 불렀으면 세션이 스스로 부른 것이다.
    그러면 모델이 바뀌지 않는다(2026. 11. 12. GGM 세션 9796777a: 담당자가 친 명령만 그 차례의 요청 모델을 바꾼다)."""
    f = 이_기록(폴더, sid)
    if f is None:
        return None, [], False
    응답 = [x for x in 읽기(f)['응답'] if x['모델'] != '<synthetic>']     # 연결 오류 때 앱이 넣는 빈 응답은 묶음을 끊지 않는다
    끝 = next((i for i in range(len(응답) - 1, -1, -1) if 재검토_명령 in 응답[i].get('명령', '')), None)
    if 끝 is None:
        return f, [], False
    처음 = 끝
    while 처음 > 0 and 재검토_명령 in 응답[처음 - 1].get('명령', ''):
        처음 -= 1
    스스로 = 처음 > 0 and any(n == 'Skill' and 재검토_명령 in 입력 for n, 입력 in 응답[처음 - 1]['도구'])
    return f, 응답[처음:끝 + 1], 스스로


def 이세션(폴더: Path, sid: str | None = None) -> tuple:
    """(세션 기록, 모델, 노력). 세션 id 는 CLAUDE_CODE_SESSION_ID, 없으면 가장 최근에 쓰인 기록이다."""
    f = 이_기록(폴더, sid)
    if f is None:
        return None, '', ''
    m, e = '', ''
    for r in 줄들(f):
        if r.get('type') == 'assistant' and isinstance(r.get('message'), dict) and r['message'].get('model'):
            m = 맨모델(r['message']['model'])
            e = r.get('effort') or r.get('perTurnEffort') or e
    e = e or os.environ.get('CLAUDE_EFFORT') or os.environ.get('CLAUDE_CODE_EFFORT_LEVEL') or ''
    return f, m, str(e)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='세션 기록의 모델·노력과 사용량')
    ap.add_argument('--이세션', action='store_true', help='지금 세션의 모델·노력을 보고 Opus 5.5·최대가 아니면 종료 코드 1')
    ap.add_argument('--재검토', action='store_true', help='이 세션에서 전면재검토 명령이 낸 마지막 응답 묶음을 보고 Fable 5.2·high 가 아니면 종료 코드 1')
    ap.add_argument('--낱말', help='도구 입력이나 담당자 말에 이 낱말이 나온 세션만 본다(사건 이름 등)')
    ap.add_argument('--시간', type=float, help='이 시간(시) 안에 시각이 찍힌 기록만 센다(범위 안에 응답이 없는 세션은 뺀다)')
    ap.add_argument('--폴더', help='세션 기록 폴더(시험용)')
    a = ap.parse_args(argv)
    폴더 = Path(a.폴더) if a.폴더 else 기록_폴더()
    if a.이세션:
        f, m, e = 이세션(폴더)
        맞음 = m == 모델 and e == 노력
        print(f"세션 {f.stem[:8] if f else '없음'} · 모델 {m or '모름'} · 노력 {e or '모름'} — "
              + ('맞음' if 맞음 else f'맞지 않음(하자보완은 {모델}·{노력}, `.claude/commands/하자보완.md`)'))
        return 0 if 맞음 else 1
    if a.재검토:
        f, 묶음, 스스로 = 재검토(폴더)
        if not 묶음:
            print(f"세션 {f.stem[:8] if f else '없음'} · 전면재검토 명령이 낸 응답이 기록에 없다 — 담당자가 이 창에 `/전면재검토 …` 를 쳤는지 본다"
                  "(`.claude/commands/전면재검토.md`)")
            return 1
        모델들 = sorted({x['모델'] for x in 묶음 if x['모델']})
        노력들 = sorted({str(x['노력']) for x in 묶음 if x['노력']})
        왜 = ('세션이 Skill 도구로 스스로 불러 모델이 바뀌지 않음. 담당자가 이 창에 `/전면재검토 …` 를 쳐야 바뀐다' if 스스로
             else '앱이 모델을 바꾸지 않음')
        틀린것 = ([f'모델이 {재검토_모델} 가 아니다({왜})'] if 모델들 != [재검토_모델] else []) \
            + ([f"노력이 {재검토_노력} 가 아니다(`.claude/settings.json` 의 modelSettings 상한이 먹지 않음)"] if 노력들 != [재검토_노력] else [])
        print(f"세션 {f.stem[:8]} · 전면 재검토 응답 {len(묶음)}회 · 모델 {', '.join(모델들) or '모름'} · 노력 {', '.join(노력들) or '모름'} — "
              + ('맞음' if not 틀린것 else f"맞지 않음({'; '.join(틀린것)}. `.claude/commands/전면재검토.md` 1.)"))
        return 0 if not 틀린것 else 1
    부터 = dt.datetime.now().timestamp() - a.시간 * 3600 if a.시간 else None
    지금 = os.environ.get('CLAUDE_CODE_SESSION_ID')
    본, 비용, 뺀 = 0, 0.0, []
    본줄 = {}          # 앞서 읽은 세션의 줄 uuid → 세션. 갈라 이어 쓴 세션이 옮겨 담은 앞 대화를 한 번만 센다
    for f in 차례(f for f in 폴더.glob('*.jsonl') if 부터 is None or f.stat().st_mtime >= 부터):
        if f.stem == 지금:      # 세고 있는 이 세션은 뺀다
            뺀.append(f'{f.stem[:8]}(지금 세션)')
            continue
        s = 읽기(f, 부터, 본줄)
        for u in s['줄']:
            본줄.setdefault(u, f.stem)
        if 부터 is not None and all(x['범위밖'] for x in s['응답']):      # 앱이 시각 없는 줄만 덧붙여 파일 시각이 바뀐 지난 세션
            뺀.append(f'{f.stem[:8]}(범위 안 응답 없음' + (', 앞 대화를 옮겨 담기만 함' if any(x.get('옮김') for x in s['응답']) else '') + ')')
            continue
        if a.낱말 and a.낱말 not in s['도구낱말'] and a.낱말 not in s['말']:
            continue
        if a.낱말 and 'session_usage.py' in s['말']:      # 사용량을 세라고 한 세션은 그 사건의 작업이 아니다(요청문에 사건 이름이 든다)
            뺀.append(f'{f.stem[:8]}(사용량을 센 세션)')
            continue
        본 += 1
        print('\n'.join(보고(f, s, a.낱말 or '', 부터)))
        비용 += s['셈한비용']
    print(f"세션 {본}개 · 비용 합 ${비용:.2f}(토큰으로 셈)" + (f" · 낱말 '{a.낱말}'" if a.낱말 else '') + (f" · 뺀 세션: {', '.join(뺀)}" if 뺀 else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
