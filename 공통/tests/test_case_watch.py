"""대화가 쉬는 사이 바뀐 사건 기록 알림(case_watch, Stop·UserPromptSubmit 훅)을 확인한다.

이어 쓰는 대화로 돌아왔을 때 다른 PC·다른 대화에서 바뀐 사건상태와 출력 파일은 알리고, 이 대화가 응답 도중에
고친 파일은 알리지 않아야 한다. 훅이 메시지를 막지 않도록 어떤 입력에도 종료 코드 0 이어야 한다.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from datetime import datetime, timezone

SCRIPT = Path(__file__).parents[1] / 'scripts' / 'case_watch.py'
spec = importlib.util.spec_from_file_location('case_watch', SCRIPT)
cw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cw)

T0 = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc).timestamp()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def no_receive(root):
    raise AssertionError('쉰 시간이 짧은데 시스템 파일을 받으려 하였다')


class CaseWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root, self.state = base / 'repo', base / 'state'
        case = self.root / '4_서면작성' / '사건' / 'OES_부당해고 구제신청'
        for d in ('라운드1/작업', '라운드1/출력/제출'):
            (case / d).mkdir(parents=True)
        self.status = case / '라운드1' / '작업' / '사건상태.md'
        self.status.write_text('1. 초안', encoding='utf-8')
        self.brief = case / '라운드1' / '출력' / '(OES) 답변서(1)_초안.docx'
        self.brief.write_bytes(b'v1')
        other = self.root / '1_검토의견' / '사건' / '하나기술_검토'
        (other / '작업').mkdir(parents=True)
        (other / '작업' / '사건상태.md').write_text('1. 검토', encoding='utf-8')
        self.opinion = other / '검토의견서.docx'
        self.opinion.write_bytes(b'v1')
        self.transcript = base / 'transcript.jsonl'
        self.data = {'session_id': 'sess-1', 'transcript_path': str(self.transcript)}

    def tearDown(self):
        self.tmp.cleanup()

    def set_mtime(self, path, t):
        os.utime(path, ns=(int(t * 1e9), int(t * 1e9)))

    def write_transcript(self, *entries):
        self.transcript.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in entries) + '\n',
                                   encoding='utf-8')

    def prompt(self, now, receive=no_receive):
        return cw.on_prompt(self.data, self.root, self.state, now=now, receive=receive)

    def test_silent_when_nothing_changed(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.assertIsNone(self.prompt(T0 + 60))

    def test_reports_case_changed_while_idle_once(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.status.write_text('1. 초안\n2. 다른 PC에서 고침', encoding='utf-8')
        self.brief.write_bytes(b'v2 - edited')
        out = self.prompt(T0 + 600)
        ctx = out['hookSpecificOutput']['additionalContext']
        self.assertEqual(out['hookSpecificOutput']['hookEventName'], 'UserPromptSubmit')
        self.assertIn('4_서면작성/사건/OES_부당해고 구제신청', ctx)
        self.assertIn('라운드1/작업/사건상태.md', ctx)
        self.assertIn('(OES) 답변서(1)_초안.docx', ctx)
        self.assertNotIn('사건상태에 기록 없이 출력 파일만 바뀜', ctx)
        self.assertLess(ctx.index('사건상태.md('), ctx.index('답변서(1)_초안.docx('))   # 사건상태를 먼저 적는다
        self.assertNotIn('하나기술', ctx)
        self.assertIn('OES_부당해고 구제신청', out['systemMessage'])
        cw.on_stop(self.data, self.root, self.state, now=T0 + 700)
        self.assertIsNone(self.prompt(T0 + 800))              # 같은 변경은 한 번만 알린다

    def test_output_changed_without_status_is_flagged(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.opinion.write_bytes(b'v2 - edited by hand')
        ctx = self.prompt(T0 + 600)['hookSpecificOutput']['additionalContext']
        self.assertIn('1_검토의견/사건/하나기술_검토: 사건상태에 기록 없이 출력 파일만 바뀜', ctx)
        self.assertNotIn('OES', ctx)

    def test_new_case_is_reported(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        new = self.root / '4_서면작성' / '사건' / 'GGM_정직3월' / '라운드1' / '작업'
        new.mkdir(parents=True)
        (new / '사건상태.md').write_text('1. 시작', encoding='utf-8')
        self.assertIn('GGM_정직3월', self.prompt(T0 + 600)['hookSpecificOutput']['additionalContext'])

    def test_lock_files_pdf_and_submission_copies_are_ignored(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        out_dir = self.brief.parent
        (out_dir / '~$OES) 답변서.docx').write_bytes(b'lock')
        (out_dir / '(OES) 답변서(1)_초안.pdf').write_bytes(b'pdf')
        (out_dir / '제출' / '(OES) 답변서(1)_초안.docx').write_bytes(b'copy')
        (out_dir / '서면초안.md').write_text('본문', encoding='utf-8')
        self.assertIsNone(self.prompt(T0 + 600))

    def test_message_sent_during_a_reply_is_silent(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.assertIsNone(self.prompt(T0 + 60))               # 응답 시작
        self.brief.write_bytes(b'v2 - this conversation')      # 이 대화가 응답 도중에 고침
        self.assertIsNone(self.prompt(T0 + 120))              # 응답 도중에 보낸 메시지

    def test_interrupted_reply_then_idle_is_reported_with_caveat(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.assertIsNone(self.prompt(T0 + 60))
        self.write_transcript(
            {'type': 'user', 'message': {'role': 'user', 'content': '고쳐 줘'}, 'timestamp': iso(T0 + 60)},
            {'type': 'user', 'message': {'role': 'user', 'content': [
                {'type': 'text', 'text': '[Request interrupted by user]'}]}, 'timestamp': iso(T0 + 90)})
        self.status.write_text('1. 초안\n2. 다른 PC', encoding='utf-8')
        ctx = self.prompt(T0 + 600)['hookSpecificOutput']['additionalContext']
        self.assertIn('라운드1/작업/사건상태.md', ctx)
        self.assertIn('도중에 끊겼으므로', ctx)

    def test_marker_inside_tool_result_is_not_an_interrupt(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.assertIsNone(self.prompt(T0 + 60))
        self.write_transcript(
            {'type': 'user', 'message': {'role': 'user', 'content': [
                {'type': 'tool_result', 'content': 'grep 결과: [Request interrupted by user]'}]},
             'timestamp': iso(T0 + 90)})
        self.status.write_text('1. 초안\n2. 이 대화가 고침', encoding='utf-8')
        self.assertIsNone(self.prompt(T0 + 600))

    def test_reply_without_stop_for_hours_is_reported(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.assertIsNone(self.prompt(T0 + 60))
        self.status.write_text('1. 초안\n2. 다른 PC', encoding='utf-8')
        ctx = self.prompt(T0 + 60 + 4 * 3600, receive=lambda r: '')['hookSpecificOutput']['additionalContext']
        self.assertIn('도중에 끊겼으므로', ctx)

    def test_conversation_without_baseline_uses_last_reply(self):
        self.write_transcript(
            {'type': 'user', 'message': {'role': 'user', 'content': '시작'}, 'timestamp': iso(T0)},
            {'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': '끝'}]},
             'timestamp': iso(T0 + 600)})
        for p in (self.status, self.brief, self.opinion, self.opinion.parent / '작업' / '사건상태.md'):
            self.set_mtime(p, T0 + 300)                        # 지난 응답 전에 고친 파일
        self.set_mtime(self.status, T0 + 900)                  # 지난 응답 뒤에 고친 파일
        ctx = self.prompt(T0 + 1200)['hookSpecificOutput']['additionalContext']
        self.assertIn('라운드1/작업/사건상태.md', ctx)
        self.assertNotIn('답변서', ctx)
        self.assertNotIn('하나기술', ctx)

    def test_new_conversation_is_silent(self):
        self.assertIsNone(self.prompt(T0))

    def test_system_files_are_received_only_after_long_idle(self):
        calls = []

        def receive(root):
            calls.append(root)
            return '[시스템 파일 받기] …\n원격에서 받은 파일 2개, 원격에서 지운 파일 0개.\n  받음  공통/운영.md'

        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.assertIsNone(self.prompt(T0 + 29 * 60, receive=receive))
        self.assertEqual(calls, [])
        cw.on_stop(self.data, self.root, self.state, now=T0 + 30 * 60)
        out = self.prompt(T0 + 30 * 60 + 31 * 60, receive=receive)
        self.assertEqual(len(calls), 1)
        self.assertIn('시스템 파일 받음 2개', out['systemMessage'])
        self.assertIn('공통/운영.md', out['hookSpecificOutput']['additionalContext'])

    def test_bad_input_never_blocks(self):
        self.assertEqual(cw.main(['없는모드']), 0)
        for raw in (b'', b'not json', b'[1, 2]', '{"session_id": "../../x"}'.encode()):
            r = subprocess.run([sys.executable, '-B', str(SCRIPT), 'prompt', '--root', str(self.root),
                                '--state', str(self.state)], input=raw, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, b'')
        self.assertFalse(self.state.exists())

    def test_hook_output_is_ascii_json(self):
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.status.write_text('1. 초안\n2. 다른 PC', encoding='utf-8')
        state = json.loads((self.state / 'sess-1.json').read_text(encoding='utf-8'))
        state['stop'] = time.time() - 60                     # 1분 쉰 대화(시스템 파일은 받지 않음)
        state['prompt'] = state['stop'] - 1
        (self.state / 'sess-1.json').write_text(json.dumps(state), encoding='utf-8')
        r = subprocess.run([sys.executable, '-B', str(SCRIPT), 'prompt', '--root', str(self.root),
                            '--state', str(self.state)],
                           input=json.dumps(self.data, ensure_ascii=False).encode('utf-8'), capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.isascii())
        out = json.loads(r.stdout)
        self.assertIn('OES_부당해고 구제신청', out['hookSpecificOutput']['additionalContext'])

    def test_feedback_messages_are_logged_for_the_nightly_check(self):
        """지적으로 보이는 메시지만 `공통/사건/_지적기록/{PC}.jsonl` 에 적고, `공통/사건/` 이 없으면(클라우드) 적지 않는다."""
        base = self.root / '공통' / '사건'
        self.assertIsNone(cw.log_feedback({'prompt': '왜 첫 면만 읽었지?', 'session_id': 's'}, self.root))
        base.mkdir(parents=True, exist_ok=True)
        with mock.patch.dict(os.environ, {'COMPUTERNAME': 'HOME-PC'}):
            self.assertIsNone(cw.log_feedback({'prompt': '좋아 진행해', 'session_id': 's'}, self.root))
            self.assertIsNone(cw.log_feedback({'prompt': '/하자보완 예약 작업을 만들어 줘', 'session_id': 's'}, self.root))
            self.assertIsNone(cw.log_feedback({'prompt': '<scheduled-task name="self-audit">하자보완.md 절차대로 왜</scheduled-task>', 'session_id': 's'}, self.root))
            path = cw.log_feedback({'prompt': '증거를 왜 빠뜨렸는지 확인하고 재발 방지', 'session_id': 's', 'cwd': 'x'}, self.root)
        self.assertEqual(path, base / '_지적기록' / 'HOME-PC.jsonl')
        rows = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['글'], '증거를 왜 빠뜨렸는지 확인하고 재발 방지')
        self.assertEqual(rows[0]['PC'], 'HOME-PC')

    def test_expectations_and_standing_instructions_are_logged(self):
        """2026. 11. 5. 지적 셋이 낱말에 걸리지 않았다. 기대('~야지')·평가('너무', '장황')·상시 지시('앞으로')도 적는다."""
        (self.root / '공통' / '사건').mkdir(parents=True, exist_ok=True)
        with mock.patch.dict(os.environ, {'COMPUTERNAME': 'HOME-PC'}):
            for 말 in ('사 제14호증같이 돌려져서 제출한건 적어도 내가 심문회의에서 볼 땐 보기 좋게 돌려줘야지 ;',
                      '최종진술 2. 부분은 잘 정리했는데 너무 길어서 위원들 집중 떨어질 수 있으니 분량좀 줄여보자',
                      '보니까 초안 만들면 메일 본문에 좀 장황하게 쓰던데, 어짜피 내부적으로 보내는 거니까 최소화해주기 바람',
                      '오 좋아 잘 고쳤네 앞으로도 들어오는 족족 어느 피시에서든 이렇게 진행해보자고',
                      '뭔가 여전히 증거는 대충 읽는 느낌이 있네'):
                self.assertIsNotNone(cw.log_feedback({'prompt': 말, 'session_id': 's'}, self.root), 말)
            for 말 in ('좋아 진행해', '둘 다 넣어 줘', '팀즈에 심문회의 결과 올림 확인해봐 수고 많았다'):
                self.assertIsNone(cw.log_feedback({'prompt': 말, 'session_id': 's'}, self.root), 말)

    def test_messages_sent_during_a_reply_are_logged_at_stop(self):
        """응답 도중에 보낸 말(대화 기록의 attachment 'queued_command')은 UserPromptSubmit 을 거치지 않으므로 Stop 이 적는다.
        지난 Stop 앞의 말·작업 알림·지적이 아닌 말은 적지 않고, 프롬프트 훅이 이미 적은 말은 되풀이하지 않는다."""
        base = self.root / '공통' / '사건'
        base.mkdir(parents=True, exist_ok=True)
        log = base / '_지적기록' / 'HOME-PC.jsonl'

        def 끼운말(t, 말):
            return {'type': 'attachment', 'timestamp': iso(t), 'attachment': {'type': 'queued_command', 'prompt': 말}}

        옛 = 끼운말(T0 - 100, '증거를 왜 빠뜨렸어')
        with mock.patch.dict(os.environ, {'COMPUTERNAME': 'HOME-PC'}):
            self.write_transcript(옛)
            cw.on_stop(self.data, self.root, self.state, now=T0)
            self.assertEqual(len(log.read_text(encoding='utf-8').splitlines()), 1)          # 첫 Stop 은 그 응답의 말을 본다
            cw.log_feedback({'prompt': '이미 적힌 말인데 너무 장황해', 'session_id': 'sess-1'}, self.root)
            self.write_transcript(옛, 끼운말(T0 + 10, '상대방 주장 짧게 언급하고 이에 답변하는 형식이 좋겠고\n2문단은 좀만 더 보충해주고'),
                                  끼운말(T0 + 11, '<task-notification>\n<status>completed</status>\n왜</task-notification>'),
                                  끼운말(T0 + 12, '아 그 아이패드 자료에는 qna 넣고'),
                                  끼운말(T0 + 14, '이미 적힌 말인데 너무 장황해'))
            cw.on_stop(self.data, self.root, self.state, now=T0 + 20)
            rows = [json.loads(l) for l in log.read_text(encoding='utf-8').splitlines()]
            self.assertEqual([r['글'][:12] for r in rows], ['증거를 왜 빠뜨렸어', '이미 적힌 말인데 너무', '상대방 주장 짧게 언급'])
            self.assertTrue(rows[2]['응답 도중'])
            self.assertEqual(rows[2]['session'], 'sess-1')
            cw.on_stop(self.data, self.root, self.state, now=T0 + 30)                       # 같은 말을 다시 적지 않는다
            self.assertEqual(len(log.read_text(encoding='utf-8').splitlines()), 3)

    def test_old_baselines_are_pruned(self):
        self.state.mkdir(parents=True)
        old = self.state / 'old-session.json'
        old.write_text('{}', encoding='utf-8')
        self.set_mtime(old, T0 - 40 * 86400)
        cw.on_stop(self.data, self.root, self.state, now=T0)
        self.assertFalse(old.exists())
        self.assertTrue((self.state / 'sess-1.json').exists())


if __name__ == '__main__':
    unittest.main()
