import fnmatch
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('dashboard', REPO / '공통' / 'scripts' / 'dashboard.py')
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)

CLEAN = '- 다 음 -\n\n1. 사실관계\n\n신청인은 2020. 1. 1. 입사하였습니다.\n'


class DashboardTests(unittest.TestCase):
    """임시 폴더에 사건을 꾸며 survey() 가 내는 '다음 할 일' 을 본다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = mock.patch.object(dashboard, 'ROOT', self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def put(self, rel, text='', when=None):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        if when is not None:
            os.utime(path, (when, when))
        return path

    def row(self, case):
        rows = [r for r in dashboard.survey() if r['case'] == case]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_new_round_with_opponent_material_is_not_hidden_by_old_draft(self):
        case = '4_서면작성/사건/을사건'
        self.put(case + '/라운드1/출력/서면초안.md', CLEAN)
        self.put(case + '/라운드1/출력/(을) 준비서면_초안.docx')
        self.put(case + '/라운드2/상대증거/상대준비서면.pdf')
        row = self.row('을사건')
        self.assertEqual(row['latest_round'], '라운드2')
        self.assertEqual(row['draft'], '')
        self.assertEqual(row['next'], '상대 자료가 있는데 초안이 없음(1건)')
        self.assertIsNone(row['style'])                  # 앞 라운드 초안으로 채점하지 않는다

    def test_new_round_without_draft_is_draft_missing(self):
        case = '4_서면작성/사건/병사건'
        self.put(case + '/라운드1/출력/서면초안.md', CLEAN)
        (self.root / case / '라운드2' / '출력').mkdir(parents=True)
        self.assertEqual(self.row('병사건')['next'], '초안 없음')

    def test_copied_round_draft_older_than_new_opponent_material(self):
        case = '4_서면작성/사건/정사건'
        now = time.time()
        self.put(case + '/라운드2/출력/서면초안.md', CLEAN, when=now - 86400)   # 직전 라운드에서 복사됨
        self.put(case + '/라운드2/출력/(정) 준비서면_초안.docx', when=now - 86400)
        self.put(case + '/라운드2/상대증거/을 제1호증.pdf', when=now - 2 * 86400)
        self.put(case + '/라운드2/상대증거/상대준비서면.pdf', when=now)
        self.assertEqual(self.row('정사건')['next'], '초안 이후 상대 자료 도착')

    def test_system_files_are_not_opponent_material(self):
        case = '4_서면작성/사건/무사건'
        self.put(case + '/라운드1/상대증거/desktop.ini')
        self.put(case + '/라운드1/상대증거/Thumbs.db')
        self.assertEqual(self.row('무사건')['next'], '초안 없음')

    def test_docx_named_by_current_rule_counts_as_merged(self):
        names = ['(GGM) 답변서_초안.docx', '(이케아) 준비서면_1차 수정안.docx', '최종서면.docx']
        for i, name in enumerate(names):
            case = '4_서면작성/사건/사건%d' % i
            self.put(case + '/라운드1/출력/서면초안.md', CLEAN)
            self.put(case + '/라운드1/출력/서면_프레임.docx')
            self.put(case + '/라운드1/출력/' + name)
            with self.subTest(name=name):
                self.assertNotEqual(self.row('사건%d' % i)['next'], 'DOCX 미생성')

    def test_frame_merge_backup_and_word_lock_are_not_merged_docx(self):
        case = '4_서면작성/사건/GGM_정직3월'
        self.put(case + '/라운드1/출력/서면초안.md', CLEAN)
        self.put(case + '/라운드1/출력/서면_프레임.docx')
        self.put(case + '/라운드1/출력/(GGM) 답변서_초안.bak_merge_20260922_1530.docx')
        self.put(case + '/라운드1/출력/~$(GGM) 답변서_초안.docx')
        self.assertEqual(self.row('GGM_정직3월')['next'], 'DOCX 미생성')

    def test_documented_markers_are_counted_but_list_headings_are_not(self):
        case = '4_서면작성/사건/기사건'
        self.put(case + '/라운드1/출력/서면초안.md', CLEAN + (
            '\n---\n\n① [확인 필요 사항]\n'
            '- [금액: 계산 확인 전] 2.가. 미지급 수당\n'
            '- 【판례 확인 필요】 대법원 판결 선고일\n'
            '- [서증 보완 필요] 근태기록\n'
            '\n② ⚠️ [취약 논리 및 보완 방향]\n\n③ 📎 [추가 확보 필요 증거]\n'))
        self.assertEqual(self.row('기사건')['open_items'], 3)

    def test_empty_case_folder_has_no_epoch_date_and_sorts_last(self):
        (self.root / '1_검토의견/사건/빈사건').mkdir(parents=True)
        self.put('1_검토의견/사건/갑사건/회신초안.md', '메모')
        rows = dashboard.survey()
        self.assertEqual([r['case'] for r in rows], ['갑사건', '빈사건'])
        self.assertEqual(rows[1]['updated'], '—')
        self.assertNotIn('1970', rows[1]['updated'])


class ScriptOutputEncodingTests(unittest.TestCase):
    """운영 배치(점검.bat·노임표추출)가 부르는 스크립트는 출력이 파이프로 읽혀도 UTF-8 로 낸다.

    한국어 Windows 에서 파이썬은 출력이 콘솔이 아니면 cp949 로 쓴다. Claude Code 는 명령
    출력을 파이프로 받아 UTF-8 로 읽으므로 그대로 두면 한글이 깨진다.
    """

    def run_script(self, *args):
        env = dict(os.environ, PYTHONIOENCODING='cp949')
        env.pop('PYTHONUTF8', None)
        return subprocess.run([sys.executable, '-B', *args], cwd=REPO / '6_손해배상계산',
                              env=env, capture_output=True, timeout=120)

    def test_table_check_prints_utf8(self):
        done = self.run_script('scripts/점검.py')
        self.assertIn('=== 1. 파일 ===', done.stdout.decode('utf-8'))

    def test_normalize_error_prints_utf8(self):
        done = self.run_script('scripts/normalize.py', '없는_폴더')
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('[중단] 폴더가 없습니다', done.stderr.decode('utf-8'))


def launchers(*suffixes):
    """저장소 루트에서 두 단계 아래까지의 배치·PowerShell 파일. 사건·작업 트리는 보지 않는다."""
    found = []
    for depth in ('*', '*/*', '*/*/*'):
        for suffix in suffixes:
            found += [p for p in REPO.glob(depth + suffix)
                      if p.is_file() and '사건' not in p.relative_to(REPO).parts]
    return sorted(set(found))


class LauncherTests(unittest.TestCase):
    """Windows 에서만 도는 .bat·.ps1 을 여기서는 실행할 수 없어 파일 내용으로 확인한다."""

    def test_batch_files_keep_crlf_and_an_encoding_cmd_can_read(self):
        # cmd 는 배치 파일을 콘솔 코드 페이지로 읽는다. UTF-8 로 두려면 한글 줄보다 앞에
        # chcp 65001 이 있어야 하고, 그렇지 않은 파일은 CP949 로 두어야 한다.
        for path in launchers('.bat'):
            raw = path.read_bytes()
            with self.subTest(path=path.name):
                self.assertEqual(raw.count(b'\n'), raw.count(b'\r\n'))
                try:
                    lines = raw.decode('utf-8').split('\r\n')
                except UnicodeDecodeError:
                    raw.decode('cp949')
                    continue
                first_korean = next((i for i, l in enumerate(lines) if not l.isascii()), None)
                if first_korean is not None:
                    chcp = next((i for i, l in enumerate(lines) if l.strip().startswith('chcp 65001')), None)
                    self.assertIsNotNone(chcp)
                    self.assertLess(chcp, first_korean)

    def read(self, path):
        raw = path.read_bytes()
        try:
            return raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            return raw.decode('cp949')

    def test_scripts_named_by_launchers_exist(self):
        for path in launchers('.bat', '.ps1'):
            bases = (path.parent, path.parent.parent, REPO)
            for line in self.read(path).splitlines():
                if line.lstrip().startswith(('#', 'rem ')):
                    continue
                for rel in re.findall(r'((?:[^\s"\'\\/]+[\\/])*scripts[\\/][^\s"\'\\/]+\.py)', line):
                    rel = rel.replace('\\', '/')
                    with self.subTest(path=path.name, script=rel):
                        self.assertTrue(any((base / rel).is_file() for base in bases))

    def test_launchers_do_not_promise_a_fixed_test_count(self):
        for path in launchers('.bat', '.ps1'):
            with self.subTest(path=path.name):
                self.assertIsNone(re.search(r'\d+\s*(passed|건이 통과)', self.read(path)))

    def test_backup_keeps_client_docx_and_reports_robocopy_failures(self):
        text = self.read(REPO / '백업.ps1')
        patterns = re.findall(r'"([^"]+)"', re.search(r'^\s*\$산출물 = @\((.*)\)\s*$', text, re.M)[1])
        for name in ('(GGM) 답변서_초안.docx', '(이케아) 준비서면_1차 수정안.docx',
                     '(HPS) 근로시간면제 부여 관련 검토.docx', '최종서면.docx', '서면초안.md'):
            with self.subTest(name=name):
                self.assertTrue(any(fnmatch.fnmatch(name, p) for p in patterns))
        self.assertIn('공통\\캐시\\판례검색기록', text)
        self.assertIn('"2_판례검색\\사건"', text)
        lines = [l for l in text.splitlines() if not l.lstrip().startswith('#')]
        calls = [i for i, l in enumerate(lines) if re.match(r'\s*robocopy\s', l)]
        self.assertGreaterEqual(len(calls), 3)
        for i in calls:
            with self.subTest(line=lines[i].strip()[:40]):
                self.assertTrue(any('Test-Robocopy' in l for l in lines[i + 1:i + 3]))


if __name__ == '__main__':
    unittest.main()
