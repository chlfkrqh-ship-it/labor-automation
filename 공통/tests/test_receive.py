"""receive.py — 클라우드에서 머지한 시스템 파일을 PC 작업본으로 받는지 임시 저장소로 확인한다."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'receive.py'
# 시험이 이 PC의 진짜 저장소(%USERPROFILE%·%LOCALAPPDATA% 아래)를 잡지 않게 둘 다 없는 곳으로 돌린다
NOWHERE = str(Path(tempfile.gettempdir()) / 'receive-tests-nowhere')
ENV = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t',
           GIT_COMMITTER_EMAIL='t@t', GIT_CONFIG_NOSYSTEM='1', USERPROFILE=NOWHERE, LOCALAPPDATA=NOWHERE)


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
        write(self.pc, '판례기록.md', '첫 줄\n둘째\n셋째\n넷째\n끝 줄\n')
        git(self.pc, 'add', '-A')
        git(self.pc, 'commit', '-q', '-m', 'A')
        git(self.pc, 'push', '-q', 'origin', 'HEAD:main')
        # 클라우드 세션: a 고침, b 지움, e 추가, d 고침 → main 에 머지
        git(t, 'clone', '-q', str(self.remote), str(self.cloud))
        write(self.cloud, '지침/a.md', '2\n')
        (self.cloud / 'b.md').unlink()
        write(self.cloud, 'e.md', 'new\n')
        write(self.cloud, 'd.md', '2\n')
        write(self.cloud, '판례기록.md', '첫 줄(클라우드)\n둘째\n셋째\n넷째\n끝 줄\n')
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

    def test_changes_to_different_parts_of_one_file_are_merged(self):
        write(self.pc, '판례기록.md', '첫 줄\r\n둘째\r\n셋째\r\n넷째\r\n끝 줄\r\n더한 줄(PC)\r\n')     # PC 편집기가 CRLF 로 저장
        r = self.run_receive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('합침  판례기록.md', r.stdout)
        text = (self.pc / '판례기록.md').read_bytes().decode('utf-8')
        self.assertEqual(text, '첫 줄(클라우드)\r\n둘째\r\n셋째\r\n넷째\r\n끝 줄\r\n더한 줄(PC)\r\n')   # 줄끝은 이 PC 것 그대로

    def move_repo_to_appdata(self):
        appdata = Path(self.tmp.name) / 'appdata'
        (appdata / 'labor-automation').mkdir(parents=True)
        shutil.move(str(self.pc / '.git'), str(appdata / 'labor-automation' / 'repo.git'))   # g.bat 과 같은 구성
        return appdata

    def test_unpushed_commit_is_stacked_on_remote_and_its_fix_kept(self):
        # push 가 원격 진행으로 거절되어 남은 이 PC 커밋(2026. 11. 3. c192369 의 고침이 작업본에서 원격 판으로 되돌려졌다)
        write(self.pc, 'c.md', 'pc\n')                                       # 원격은 그대로인 파일
        write(self.pc, '판례기록.md', '첫 줄\n둘째\n셋째\n넷째\n끝 줄(PC 커밋)\n')   # 원격은 첫 줄을 고친 파일
        git(self.pc, 'commit', '-q', '-am', 'unpushed fix')
        write(self.pc, '판례기록.md', '첫 줄\n둘째\n셋째(다른 세션)\n넷째\n끝 줄(PC 커밋)\n')   # 다른 세션이 같은 파일을 고치는 중
        r = self.run_receive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read('c.md'), 'pc\n')                          # 커밋의 고침이 작업본에 남는다
        self.assertEqual(self.read('판례기록.md'), '첫 줄(클라우드)\n둘째\n셋째(다른 세션)\n넷째\n끝 줄(PC 커밋)\n')
        self.assertEqual(self.read('지침/a.md'), '2\n')                       # 원격 고침도 받는다
        self.assertFalse((self.pc / 'b.md').exists())
        self.assertIn('옮겨 쌓았습니다', r.stdout)
        self.assertEqual(git(self.pc, 'log', '--format=%s', 'origin/main..HEAD'), 'unpushed fix\n')
        self.assertEqual(git(self.pc, 'rev-parse', 'HEAD^'), git(self.pc, 'rev-parse', 'origin/main'))   # 원격 main 바로 위
        self.assertEqual(git(self.pc, 'show', 'HEAD:판례기록.md'), '첫 줄(클라우드)\n둘째\n셋째\n넷째\n끝 줄(PC 커밋)\n')
        status = git(self.pc, '-c', 'core.quotepath=false', 'status', '--porcelain', '--untracked-files=all')
        self.assertEqual(status.splitlines(), [' M 판례기록.md'])                # 다른 세션의 고침만 남는다
        git(self.pc, 'push', '-q', 'origin', 'HEAD:main')                        # 같은 push 를 다시 하면 올라간다

    def test_unpushed_commit_clashing_with_remote_stops_and_touches_nothing(self):
        write(self.pc, 'd.md', 'pc\n')                                       # 원격도 d 를 고쳤다
        git(self.pc, 'commit', '-q', '-am', 'unpushed fix')
        write(self.pc, 'c.md', 'other session\n')                            # 다른 세션이 고치는 중
        write(self.pc, 'n.md', 'staged\n')
        git(self.pc, 'add', 'n.md')                                          # 다른 세션이 올리려고 담아 둠

        def state():
            return (git(self.pc, 'rev-parse', 'HEAD'), git(self.pc, 'ls-files', '-s'),
                    git(self.pc, 'status', '--porcelain', '--untracked-files=all'),
                    self.read('d.md'), self.read('지침/a.md'))

        before = state()
        r = self.run_receive()
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn('unpushed fix', r.stdout)
        self.assertIn('원격도 같은 곳을 고침 — d.md', r.stdout)
        self.assertEqual(state(), before)                                    # 커밋·색인·작업본 모두 그대로
        r = self.run_auto(self.move_repo_to_appdata())                       # 시작 훅은 막지 않고 한 줄로 알린다
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(r.stdout.splitlines()), 1, r.stdout)
        self.assertIn('[시스템 파일 받기] 건너뜀', r.stdout)
        self.assertEqual((self.read('d.md'), self.read('지침/a.md')), ('pc\n', '1\n'))

    def test_clash_merged_by_hand_with_both_parents_is_then_received(self):
        # 종료 코드 3 뒤 운영.md 순서: 합친 tree 에서 충돌 파일만 손으로 합쳐, 부모가 origin/main 과 그 커밋인 커밋으로 올린다
        write(self.pc, 'd.md', 'pc\n')
        git(self.pc, 'commit', '-q', '-am', 'unpushed fix')
        write(self.pc, 'c.md', 'other session\n')                            # 다른 세션이 고치는 중
        self.assertEqual(self.run_receive().returncode, 3)
        merged = subprocess.run(['git', 'merge-tree', '--write-tree', '--name-only', 'origin/main', 'HEAD'],
                                cwd=self.pc, env=ENV, capture_output=True, text=True, encoding='utf-8').stdout.splitlines()
        self.assertEqual(merged[1], 'd.md')                                  # 첫 줄은 합친 tree, 다음 줄부터 충돌 파일
        blob = subprocess.run(['git', 'hash-object', '-w', '--stdin'], cwd=self.pc, env=ENV, input=b'2 and pc\n',
                              capture_output=True, check=True).stdout.decode().strip()
        index = dict(ENV, GIT_INDEX_FILE=str(Path(self.tmp.name) / 'merge-index'))
        for args in (['read-tree', merged[0]], ['update-index', '--cacheinfo', f'100644,{blob},d.md']):
            subprocess.run(['git', *args], cwd=self.pc, env=index, check=True)
        tree = subprocess.run(['git', 'write-tree'], cwd=self.pc, env=index, capture_output=True, text=True,
                              check=True).stdout.strip()
        commit = git(self.pc, 'commit-tree', tree, '-p', 'origin/main', '-p', 'HEAD', '-m', 'merge by hand').strip()
        git(self.pc, 'push', '-q', 'origin', f'{commit}:main')
        r = self.run_receive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(git(self.pc, 'rev-parse', 'HEAD').strip(), commit)
        self.assertEqual((self.read('d.md'), self.read('c.md'), self.read('지침/a.md')),
                         ('2 and pc\n', 'other session\n', '2\n'))

    def test_unpushed_commit_on_unchanged_remote_is_left_as_it_is(self):
        git(self.pc, 'fetch', '-q', 'origin', 'main')
        git(self.pc, 'merge', '-q', '--ff-only', 'origin/main')             # 원격까지 받은 PC
        write(self.pc, 'c.md', 'pc\n')
        git(self.pc, 'commit', '-q', '-am', 'unpushed fix')                  # 아직 올리지 않았다(연결이 끊겨 push 실패 등)
        head = git(self.pc, 'rev-parse', 'HEAD')
        r = self.run_receive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('이 PC 커밋 1개를 그대로 두었습니다', r.stdout)
        self.assertEqual(git(self.pc, 'rev-parse', 'HEAD'), head)
        self.assertEqual(self.read('c.md'), 'pc\n')
        self.assertEqual(git(self.pc, 'status', '--porcelain', '--untracked-files=all'), '')
        r = self.run_auto(self.move_repo_to_appdata())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(r.stdout.splitlines()), 1, r.stdout)
        self.assertIn('unpushed fix', r.stdout)

    def test_unpushed_commit_already_on_remote_is_dropped(self):
        # push 가 거절된 뒤 같은 고침을 원격 main 위에 따로 만들어 올린 경우(commit-tree 우회)
        write(self.pc, 'c.md', 'pc\n')
        git(self.pc, 'commit', '-q', '-am', 'unpushed fix')
        write(self.cloud, 'c.md', 'pc\n')
        git(self.cloud, 'commit', '-q', '-am', 'same fix on remote')
        git(self.cloud, 'push', '-q', 'origin', 'HEAD:main')
        r = self.run_receive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('unpushed fix  (고침이 이미 원격에 있는 이 PC 커밋)', r.stdout)
        self.assertEqual(git(self.pc, 'rev-parse', 'HEAD'), git(self.pc, 'rev-parse', 'origin/main'))
        self.assertEqual((self.read('c.md'), self.read('지침/a.md')), ('pc\n', '2\n'))
        self.assertEqual(git(self.pc, 'status', '--porcelain', '--untracked-files=all'), '')

    def test_changes_staged_by_another_session_stay_staged(self):
        write(self.pc, 'c.md', 'staged\n')
        write(self.pc, 'n.md', 'new\n')
        write(self.pc, '판례기록.md', '첫 줄\n둘째\n셋째\n넷째\n끝 줄\n더한 줄\n')
        git(self.pc, 'add', 'c.md', 'n.md', '판례기록.md')                    # 다른 세션이 올리려고 담아 둠
        write(self.pc, 'c.md', 'staged\nstill editing\n')                    # 담은 뒤에도 고치는 중
        r = self.run_receive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read('지침/a.md'), '2\n')
        self.assertEqual(git(self.pc, 'show', ':c.md'), 'staged\n')
        # 원격도 고친 판례기록은 담아 둔 판을 풀고(그대로 커밋하면 원격 고침을 되돌린다) 작업본에서 두 고침을 합친다
        self.assertIn('풀림  판례기록.md', r.stdout)
        self.assertEqual(self.read('판례기록.md'), '첫 줄(클라우드)\n둘째\n셋째\n넷째\n끝 줄\n더한 줄\n')
        status = git(self.pc, '-c', 'core.quotepath=false', 'status', '--porcelain', '--untracked-files=all')
        self.assertEqual(sorted(status.splitlines()), [' M 판례기록.md', 'A  n.md', 'MM c.md'])

    def run_auto(self, appdata, home=NOWHERE):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(self.pc), '--auto'],
                              env=dict(ENV, LOCALAPPDATA=str(appdata), USERPROFILE=str(home)),
                              capture_output=True, text=True, encoding='utf-8')

    def test_auto_finds_repo_in_claude_app_private_folder(self):
        # Claude 앱(스토어 앱) 안에서 %LOCALAPPDATA% 에 만든 저장소는 앱 전용 가상 폴더에 실제로 있다
        appdata = Path(self.tmp.name) / 'appdata'
        private = appdata / 'Packages' / 'Claude_pzs8sxrjxfjjc' / 'LocalCache' / 'Local' / 'labor-automation'
        private.mkdir(parents=True)
        shutil.move(str(self.pc / '.git'), str(private / 'repo.git'))
        r = self.run_auto(appdata)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read('지침/a.md'), '2\n')

    def test_repo_under_user_profile_is_found_first(self):
        home = Path(self.tmp.name) / 'home'
        (home / 'labor-automation').mkdir(parents=True)
        shutil.move(str(self.pc / '.git'), str(home / 'labor-automation' / 'repo.git'))
        r = self.run_auto(Path(self.tmp.name) / 'no-appdata', home=home)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.read('지침/a.md'), '2\n')

    def test_auto_does_nothing_outside_pc_layout(self):
        # 클라우드 세션처럼 작업본 안에 .git 이 있고 %LOCALAPPDATA% 저장소가 없으면 손대지 않는다
        head = git(self.pc, 'rev-parse', 'HEAD')
        r = self.run_auto(Path(self.tmp.name) / 'no-appdata')
        self.assertEqual((r.returncode, r.stdout), (0, ''))
        self.assertEqual(self.read('지침/a.md'), '1\n')
        self.assertEqual(git(self.pc, 'rev-parse', 'HEAD'), head)

    def test_auto_receives_in_pc_layout_and_is_quiet_when_nothing_changed(self):
        appdata = Path(self.tmp.name) / 'appdata'
        (appdata / 'labor-automation').mkdir(parents=True)
        shutil.move(str(self.pc / '.git'), str(appdata / 'labor-automation' / 'repo.git'))   # g.bat 과 같은 구성
        r = self.run_auto(appdata)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('[시스템 파일 받기]', r.stdout)
        self.assertEqual(self.read('지침/a.md'), '2\n')
        again = self.run_auto(appdata)
        self.assertEqual((again.returncode, again.stdout), (0, ''))

    def test_missing_repository_is_skipped(self):
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        r = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(empty)],
                           env=dict(ENV, LOCALAPPDATA=str(empty)), capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 1)
        self.assertIn('건너뜁니다', r.stdout)


if __name__ == '__main__':
    unittest.main()
