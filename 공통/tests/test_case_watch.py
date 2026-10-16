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
