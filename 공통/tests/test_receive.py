"""receive.py — 클라우드에서 머지한 시스템 파일을 PC 작업본으로 받는지 임시 저장소로 확인한다."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'receive.py'
ENV = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t',
           GIT_COMMITTER_EMAIL='t@t', GIT_CONFIG_NOSYSTEM='1')


def git(cwd, *args):
    return subprocess.run(['git', '-c', 'init.defaultBranch=main', *args], cwd=cwd, env=ENV, check=True,
                          capture_output=True, text=True, encoding='utf-8').stdout


def write(root, name, text):
    p = Path(root) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8', newline='')


class ReceiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.remote, self.pc, self.cloud = t / 'remote.git', t / 'pc', t / 'cloud'
        git(t, 'init', '-q', '--bare', str(self.remote))
        git(t, 'clone', '-q', str(self.remote), str(self.pc))
        for name in ('지침/a.md', 'b.md', 'c.md', 'd.md'):
            write(self.pc, name, '1\n')
        git(self.pc, 'add', '-A')
        git(self.pc, 'commit', '-q', '-m', 'A')
        git(self.pc, 'push', '-q', 'origin', 'HEAD:main')
        # 클라우드 세션: a 고침, b 지움, e 추가, d 고침 → main 에 머지
        git(t, 'clone', '-q', str(self.remote), str(self.cloud))
        write(self.cloud, '지침/a.md', '2\n')
        (self.cloud / 'b.md').unlink()
        write(self.cloud, 'e.md', 'new\n')
        write(self.cloud, 'd.md', '2\n')
        git(self.cloud, 'add', '-A')
        git(self.cloud, 'commit', '-q', '-m', 'B')
        git(self.cloud, 'push', '-q', 'origin', 'HEAD:main')

    def tearDown(self):
        self.tmp.cleanup()

    def run_receive(self):
        env = dict(ENV, LOCALAPPDATA=str(Path(self.tmp.name) / 'no-appdata'))
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(self.pc)], env=env,
                              capture_output=True, text=True, encoding='utf-8')

    def read(self, name):
        return (self.pc / name).read_text(encoding='utf-8')

    def test_cloud_changes_are_received_and_local_edits_kept(self):
        write(self.pc, 'c.md', 'local\n')                     # 이 PC에서 고침(원격은 그대로)
        write(self.pc, 'n.md', 'mine\n')                      # 이 PC의 새 파일
        r = self.run_receive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read('지침/a.md'), '2\n')        # 원격 고침을 받음
        self.assertFalse((self.pc / 'b.md').exists())         # 원격에서 지운 것
        self.assertEqual(self.read('e.md'), 'new\n')          # 원격에서 새로 생긴 것
        self.assertEqual(self.read('d.md'), '2\n')
        self.assertEqual(self.read('c.md'), 'local\n')        # 이 PC의 고침은 그대로
        self.assertEqual(self.read('n.md'), 'mine\n')
        status = git(self.pc, '-c', 'core.quotepath=false', 'status', '--porcelain', '--untracked-files=all')
        self.assertEqual(sorted(status.splitlines()), [' M c.md', '?? n.md'])

    def test_stale_head_from_old_procedure_still_receives(self):
        # 예전 절차(reset --mixed 만)로 HEAD 는 원격을 가리키는데 작업본은 옛 판인 PC
        git(self.pc, 'fetch', '-q', 'origin', 'main')
        git(self.pc, 'reset', '-q', '--mixed', 'origin/main')
        r = self.run_receive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read('지침/a.md'), '2\n')
        self.assertFalse((self.pc / 'b.md').exists())
        self.assertEqual(self.read('e.md'), 'new\n')
        self.assertEqual(git(self.pc, 'status', '--porcelain', '--untracked-files=all'), '')

    def test_file_changed_on_both_sides_is_a_conflict_and_left_alone(self):
        write(self.pc, 'd.md', 'pc\n')
        r = self.run_receive()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('충돌  d.md', r.stdout)
        self.assertEqual(self.read('d.md'), 'pc\n')
        self.assertEqual(self.read('지침/a.md'), '2\n')        # 나머지는 받음

    def test_missing_repository_is_skipped(self):
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        r = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(empty)],
                           env=dict(ENV, LOCALAPPDATA=str(empty)), capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 1)
        self.assertIn('건너뜁니다', r.stdout)


if __name__ == '__main__':
    unittest.main()
