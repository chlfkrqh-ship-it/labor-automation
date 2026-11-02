"""세션 기록의 모델·노력 수준과 사용량(공통/scripts/session_usage.py)을 확인한다.

한 API 응답이 기록에 여러 줄로 남아도 한 번만 세는지, 다음 요청이 넣은 글을 앞 응답이 부른 도구의 갈래로 나누는지,
쉬었다 이어 캐시를 다시 쓴 몫과 대화 압축을 따로 세는지, `--이세션` 이 Opus 5.5·최대가 아니면 1 을 돌려주는지 본다.
2026. 11. 3. 담당 노무사 "하자 고칠 땐 오푸스 5.5 최대 노력으로 가야 하고", "사용량 측면에서는 어떤 결과가 있었노".
"""
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
