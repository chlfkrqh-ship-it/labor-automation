"""세션 기록의 모델·노력 수준과 사용량(공통/scripts/session_usage.py)을 확인한다.

한 API 응답이 기록에 여러 줄로 남아도 한 번만 세는지, 다음 요청이 넣은 글을 앞 응답이 부른 도구의 갈래로 나누는지,
쉬었다 이어 캐시를 다시 쓴 몫과 대화 압축을 따로 세는지, `--이세션` 이 Opus 5.5·최대가 아니면 1 을 돌려주는지,
`--시간` 이 범위 안의 줄만 세는지 본다.
2026. 11. 3. 담당 노무사 "하자 고칠 땐 오푸스 5.5 최대 노력으로 가야 하고", "사용량 측면에서는 어떤 결과가 있었노".
"""
import datetime as dt
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('session_usage', ROOT / '공통' / 'scripts' / 'session_usage.py')
su = importlib.util.module_from_spec(spec)
spec.loader.exec_module(su)


def 응답(i, 쓰기, 읽기, 출력, 도구=None, 모델='claude-opus-5-5', 노력='max', 줄=2):
    """한 응답을 기록 줄 여럿으로(앱은 내용 덩이마다 한 줄씩 적는다)."""
    usage = {'input_tokens': 1, 'cache_creation_input_tokens': 쓰기, 'cache_read_input_tokens': 읽기, 'output_tokens': 출력,
             'cache_creation': {'ephemeral_1h_input_tokens': 쓰기, 'ephemeral_5m_input_tokens': 0}}
    덩이 = [{'type': 'thinking', 'thinking': ''}] + ([{'type': 'tool_use', 'name': n, 'input': x} for n, x in 도구] if 도구 else [{'type': 'text', 'text': '답'}])
    out = []
    for k, b in enumerate(덩이[:줄] if 줄 < len(덩이) else 덩이):
        out.append({'type': 'assistant', 'timestamp': f'2026-11-02T10:{i:02d}:{k:02d}Z', 'effort': 노력, 'perTurnEffort': 노력,
                    'message': {'id': f'msg_{i}', 'model': 모델, 'usage': usage, 'content': [b]}})
    return out


def 말(글, 메타=False, 압축=False):
    r = {'type': 'user', 'timestamp': '2026-11-02T10:00:00Z', 'message': {'role': 'user', 'content': 글}}
    if 메타:
        r['isMeta'] = True
    if 압축:
        r['isCompactSummary'] = True
    return [r]


def 도구결과(그림=0):
    return [{'type': 'user', 'timestamp': '2026-11-02T10:00:00Z',
             'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': [{'type': 'image'}] * 그림 + [{'type': 'text', 'text': '결과'}]}]}}]


class UsageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, 이름, 줄들):
        f = self.d / f'{이름}.jsonl'
        f.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in 줄들) + '\n', encoding='utf-8')
        return f

    def test_each_response_is_counted_once_and_new_input_goes_to_the_tool_that_brought_it(self):
        f = self.put('s1', [
            *말('<command-name>알림</command-name>'), *말('4_서면작성/사건/노정일_해고/라운드1 서면 써 줘'),
            *응답(1, 1000, 0, 10, [('Read', {'file_path': '증거/갑 제1호증.pdf'})]),
            *도구결과(그림=3),
            *응답(2, 5000, 1000, 20, [('Bash', {'command': 'python -B 공통/scripts/final_check.py "x"'})]),
            *도구결과(),
            *응답(3, 300, 6000, 30),                                   # 관문 결과가 넣은 300
            *말('고쳐 줘'),
            *응답(4, 6500, 0, 40, [('Edit', {'file_path': 'a.md'})]),    # 쉬었다 이어 캐시에 있던 6300 을 다시 썼다
            *말('요약', 압축=True),
            *응답(5, 9000, 0, 50),
        ])
        s = su.읽기(f)
        self.assertEqual(len(s['응답']), 5)
        self.assertEqual(s['그림'], 3)
        self.assertEqual(s['압축'], 1)
        self.assertTrue(s['첫지시'].startswith('4_서면작성/사건/노정일'))     # 앱이 태그로 싼 알림은 첫 지시가 아니다
        c = su.셈(s['응답'])
        self.assertEqual(c['합']['출력'], 150)
        갈래 = {k: v[0] for k, v in c['갈래'].items()}
        self.assertEqual(갈래['호증·자료 읽기'], 5001)
        self.assertEqual(갈래['관문·검사'], 301)
        self.assertEqual(갈래['캐시 다시 씀(쉬었다 이음)'], 6300)
        self.assertEqual(갈래['담당자 말·첨부'], 201)
        self.assertEqual(갈래['대화 압축'], 9001)
        self.assertEqual(c['갈래']['쓰기'][1], 40)
        self.assertEqual(c['합']['최대문맥'], 9001)

    def test_keyword_filter_and_report(self):
        self.put('s1', [*말('노정일 사건'), *응답(1, 10, 0, 1, [('Read', {'file_path': '사건/노정일/a.md'})]), *도구결과(), *응답(2, 10, 10, 1)])
        self.put('s2', [*말('다른 사건'), *응답(1, 10, 0, 1)])
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(su.main(['--낱말', '노정일', '--폴더', str(self.d)]), 0)
        글 = buf.getvalue()
        self.assertIn('세션 1개', 글)
        self.assertIn("'노정일': 도구 입력 1회, 담당자 말 1회", 글)
        self.assertIn('요금 나눔', 글)

    def test_cost_is_counted_from_tokens_and_model_prices(self):
        """앱이 남긴 비용 기록은 세션 중간 값이거나 비어 있어(2026. 11. 3. 집 PC) 토큰과 단가로 셈한다."""
        u = {'input_tokens': 1_000_000, 'output_tokens': 1_000_000, 'cache_read_input_tokens': 1_000_000, 'cache_creation_input_tokens': 2_000_000,
             'cache_creation': {'ephemeral_1h_input_tokens': 1_000_000, 'ephemeral_5m_input_tokens': 1_000_000}}
        v = su.값('claude-opus-5-5', u)
        self.assertEqual({k: round(x, 2) for k, x in v.items()}, {'입력': 4.0, '캐시 쓰기': 13.0, '캐시 읽기': 0.2, '출력': 20.0})
        self.assertAlmostEqual(sum(su.값('claude-opus-5-5', {**u, 'speed': 'fast'}).values()), 2 * sum(v.values()))
        self.assertAlmostEqual(su.값('claude-opus-5-5', {'cache_creation_input_tokens': 1_000_000})['캐시 쓰기'], 8.0)   # 나눔이 없으면 1시간 값
        self.assertAlmostEqual(su.값('claude-haiku-5-5', {'input_tokens': 200_000})['입력'], 0.1)                       # 10만 토큰 넘는 요청
        self.assertIsNone(su.값('claude-unknown-9', u))
        f = self.put('s1', [*말('일'), *응답(1, 1_000_000, 0, 1_000_000)])
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'other'}):
            su.main(['--폴더', str(self.d)])
        self.assertIn('비용 $28.00(토큰으로 셈)', buf.getvalue())       # 캐시 쓰기 1시간 100만 $8 + 출력 100만 $20

    def test_the_measuring_session_is_left_out(self):
        """2026. 11. 3. 사용량을 세라는 요청문에 사건 이름이 들어 그 세션이 사건 작업으로 잡혔다."""
        self.put('지금', [*말('노정일 셈'), *응답(1, 10, 0, 1)])
        self.put('부탁', [*말('`python -B 공통/scripts/session_usage.py --낱말 노정일` 돌려 줘'), *응답(1, 10, 0, 1)])
        self.put('일', [*말('노정일 서면'), *응답(1, 10, 0, 1)])
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': '지금'}):
            su.main(['--낱말', '노정일', '--폴더', str(self.d)])
        글 = buf.getvalue()
        self.assertIn('세션 1개', 글)
        self.assertIn('지금 세션', 글)
        self.assertIn('사용량을 센 세션', 글)

    def test_time_range_counts_only_lines_in_range(self):
        """2026. 11. 4. `/하자보완`: 앱이 지난 세션 기록 끝에 시각 없는 줄(mode·cost-state)을 덧붙여 파일 시각이 바뀌자, 10. 28.·10. 31. 에 끝난
        세션 둘이 21시간 범위에 통째로 들어왔다. 범위 앞에서 이어진 세션은 범위 안의 응답만 세고, 앞 응답은 갈래를 가르는 데만 쓴다."""
        지금 = dt.datetime.now(dt.timezone.utc)
        오래, 요즘 = 지금 - dt.timedelta(hours=48), 지금 - dt.timedelta(hours=1)

        def 때(줄들, t):
            for r in 줄들:
                r['timestamp'] = t.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            return 줄들
        덧붙임 = [{'type': 'mode', 'mode': 'normal'}, {'type': 'cost-state', 'totalCostUSD': 0}]
        self.put('지난', [*때(말('지난 일'), 오래), *때(응답(1, 10, 0, 1, [('Agent', {'prompt': '찾기'})]), 오래), *덧붙임])
        f = self.put('이음', [*때(말('서면 써 줘'), 오래), *때(응답(1, 1_000_000, 0, 0, [('Read', {'file_path': '증거/갑 제1호증.pdf'})]), 오래),
                             *때(도구결과(그림=2), 오래), *때(응답(2, 500, 1_000_000, 10), 요즘),
                             *때(말('고쳐 줘'), 요즘), *때(응답(3, 300, 1_000_500, 20), 요즘)])
        sub = self.d / '이음' / 'subagents'
        sub.mkdir(parents=True)
        (sub / 'a.jsonl').write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in 때(응답(1, 10, 0, 1), 오래)) + '\n', encoding='utf-8')
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'other'}):
            su.main(['--시간', '24', '--폴더', str(self.d)])
        글 = buf.getvalue()
        self.assertIn('세션 1개', 글)
        self.assertIn('지난(범위 안 응답 없음)', 글)
        self.assertIn('범위 앞 응답 1회는 세지 않음', 글)
        self.assertIn('응답 2회 · 대화 압축 0회 · 그림 0장 · 하위 작업 0개', 글)
        self.assertIn('첫 지시: 고쳐 줘', 글)
        c = su.셈(su.읽기(f, (요즘 - dt.timedelta(minutes=30)).timestamp())['응답'])
        self.assertEqual({k: v[0] for k, v in c['갈래'].items() if v[0]}, {'호증·자료 읽기': 501, '담당자 말·첨부': 301})      # 범위 앞 응답이 부른 도구로 가른다
        self.assertEqual(su.셈(su.읽기(f)['응답'])['합']['응답'], 3)      # 범위를 주지 않으면 종전대로 세션 전체를 센다

    def test_forked_session_does_not_count_the_copied_conversation_again(self):
        """갈라 이어 쓴 세션은 앞 대화의 줄을 uuid·시각 그대로 옮겨 담는다. 앞 세션에서 센 응답은 뒤 세션에서 세지 않는다(2026. 11. 8. `/하자보완`:
        11. 7. 한 사건의 결과 조회 세션의 응답 28회가 두 세션에 함께 세였다). 차례는 파일 시각이 아니라 기록의 처음 시각으로 정한다."""
        def 이름표(줄들, 앞):
            for i, r in enumerate(줄들):
                r['uuid'] = f'{앞}-{i}'
            return 줄들
        원래 = [{'type': 'queue-operation', 'timestamp': '2026-11-02T09:59:59Z'}] + 이름표(
            [*말('조회 부탁'), *응답(1, 1000, 0, 10), *응답(2, 500, 1000, 20)], 'a')
        이음 = 이름표([*말('로그인 완료'), *응답(3, 800, 1500, 30)], 'b')
        for r in 이음:
            r['timestamp'] = r['timestamp'].replace('T10:', 'T11:')
        a = self.put('a', 원래)
        b = self.put('b', [{'type': 'queue-operation', 'timestamp': '2026-11-02T11:00:00Z'}] + [dict(r) for r in 원래[1:]] + 이음)
        옛 = dt.datetime(2026, 11, 1).timestamp()
        os.utime(b, (옛, 옛))                                           # 파일 시각은 갈라 낸 세션이 더 이르다
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'other'}):
            su.main(['--폴더', str(self.d)])
        글 = buf.getvalue()
        b절 = 글.split('## b')[1]
        self.assertIn('앞 세션 a에서 옮겨 담은 응답 2회는 세지 않음', b절)
        self.assertIn('첫 지시: 로그인 완료', b절)
        self.assertIn('응답 1회 ·', b절)
        self.assertIn('응답 2회 ·', 글.split('## a')[1].split('## b')[0])
        합 = sum(su.셈(su.읽기(a)['응답'])['비용'].values()) + sum((su.값('claude-opus-5-5', x['쓰임']) or {}).get(k, 0)
                                                                for x in su.읽기(b)['응답'][2:] for k in ('입력', '캐시 쓰기', '캐시 읽기', '출력'))
        self.assertIn(f'비용 합 ${합:.2f}', 글)
        self.assertEqual(su.차례([b, a]), [a, b])

    def test_mail_and_teams_connector_tools_are_their_own_branch(self):
        """2026. 11. 4. `/하자보완`: 메일·팀즈 연결의 도구 이름이 커넥터 id 로 시작해 메일반영 세션의 호출 40회가 '그 밖'으로 잡혔다."""
        for n, s in (('mcp__e78f8043-6cee-480b-9ebb-3d7500a1ebeb__read_resource', '{"uri": "teams:///chats/1/messages"}'),
                     ('mcp__e78f8043-6cee-480b-9ebb-3d7500a1ebeb__outlook_email_search', '{}'),
                     ('mcp__claude_ai_Microsoft_365__teams_list_chats', '{}'),
                     ('PowerShell', '{"command": "python -B 공통/scripts/mail_attach.py 메일"}')):
            self.assertEqual(su.갈래([(n, s)]), '메일·팀즈', n)
        for n in ('mcp__ccd_session_mgmt__list_sessions', 'mcp__ccd_session_mgmt__get_session', 'mcp__scheduled-tasks__list_task_runs'):
            self.assertEqual(su.갈래([(n, '{}')]), '그 밖', n)

    def test_this_session_must_be_opus_5_5_at_max_effort(self):
        self.put('s1', [*말('하자보완'), *응답(1, 10, 0, 1)])
        self.put('s2', [*말('하자보완'), *응답(1, 10, 0, 1, 모델='claude-sonnet-5-5')])
        self.put('s3', [*말('하자보완'), *응답(1, 10, 0, 1, 노력='high')])
        self.put('s4', [*말('하자보완'), *응답(1, 10, 0, 1, 모델='claude-opus-5-5[1m]', 노력=None)])
        for sid, 기대, env in (('s1', 0, {}), ('s2', 1, {}), ('s3', 1, {}), ('s4', 0, {'CLAUDE_CODE_EFFORT_LEVEL': 'max'}), ('s4', 1, {})):
            with mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': sid, **env}, clear=False):
                for k in ('CLAUDE_EFFORT', 'CLAUDE_CODE_EFFORT_LEVEL'):
                    if k not in env:
                        os.environ.pop(k, None)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    self.assertEqual(su.main(['--이세션', '--폴더', str(self.d)]), 기대, (sid, env, buf.getvalue()))
        self.assertIn('맞지 않음', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
