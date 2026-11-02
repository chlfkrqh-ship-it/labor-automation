"""세션 오류 모으기(공통/scripts/session_errors.py)를 확인한다. `/하자보완` 이 담당자가 말하지 않은 스크립트 오류를 찾는 데 쓴다."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import time
import unittest

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('session_errors', ROOT / '공통/scripts/session_errors.py')
se = importlib.util.module_from_spec(spec)
spec.loader.exec_module(se)

우리 = ('Traceback (most recent call last):\n'
      '  File "C:\\Users\\x\\OneDrive\\노동사건자동화\\4_서면작성\\scripts\\evidence_split.py", line 48, in main\n'
      "    계획 = json.load(open(sys.argv[1]))\n"
      "FileNotFoundError: [Errno 2] No such file or directory: 'GGM_정직3월/계획.json'\n")
바깥 = ('Traceback (most recent call last):\n  File "C:\\Python\\Lib\\json\\__init__.py", line 293, in load\n    x\nValueError: 잘못됨\n')
시험중 = ('Traceback (most recent call last):\n'
       '  File "C:\\Users\\x\\노동사건자동화\\공통\\tests\\test_x.py", line 5, in test_a\n    y\n'
       '  File "C:\\Users\\x\\노동사건자동화\\공통\\scripts\\final_check.py", line 9, in f\n    z\nKeyError: 1\n')


def 줄(글, 때=None, 목록=True):
    내용 = [{'type': 'text', 'text': 글}] if 목록 else 글
    return json.dumps({'type': 'user', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(때 or time.time())),
                       'message': {'content': [{'type': 'tool_result', 'content': 내용}]}}, ensure_ascii=False) + '\n'


class SessionErrorsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_errors_inside_our_scripts_are_grouped_across_sessions(self):
        (self.d / 'a.jsonl').write_text(줄(우리) + 줄(우리, 목록=False) + 줄(바깥) + 줄(시험중), encoding='utf-8')
        (self.d / 'b.jsonl').write_text(줄('출력\n' + 우리), encoding='utf-8')
        결과 = se.모으기(self.d, 26)
        self.assertEqual(len(결과), 1)
        s, n, fn, err, 횟수, 세션, _ = 결과[0]
        self.assertEqual((s, n, fn, 횟수, 세션), ('evidence_split.py', '48', 'main', 3, 2))
        self.assertTrue(err.startswith('FileNotFoundError'))
        self.assertNotIn('GGM', err)                           # 오류 글의 사건 이름을 옮기지 않는다

    def test_errors_outside_the_range_are_left_out(self):
        (self.d / 'a.jsonl').write_text(줄(우리, 때=time.time() - 3600 * 50) + 줄('Traceback (most recent call last) 깨진 글'), encoding='utf-8')
        self.assertEqual(se.모으기(self.d, 26), [])
        old = self.d / 'old.jsonl'
        old.write_text(줄(우리), encoding='utf-8')
        import os
        os.utime(old, (time.time() - 3600 * 50, time.time() - 3600 * 50))    # 범위 전에 끝난 세션은 열지 않는다
        self.assertEqual(se.모으기(self.d, 26), [])

    def test_screen_says_how_many_kinds(self):
        (self.d / 'a.jsonl').write_text(줄(우리), encoding='utf-8')
        화면 = io.StringIO()
        with contextlib.redirect_stdout(화면):
            self.assertEqual(se.main(['--시간', '26', '--폴더', str(self.d)]), 0)
        self.assertIn('evidence_split.py:48 main()', 화면.getvalue())
        self.assertIn('스크립트 오류 1종', 화면.getvalue())

    def test_folder_name_follows_the_app_rule(self):
        self.assertEqual(se.기록_폴더().parent.name, 'projects')
        self.assertNotRegex(se.기록_폴더().name, r'[^A-Za-z0-9-]')


if __name__ == '__main__':
    unittest.main()
