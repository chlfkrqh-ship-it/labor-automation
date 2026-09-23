"""4_서면작성/scripts/evidence_check.py 와 저장소 .gitignore 를 확인한다.

- stamp: 2026. 9. 16. 이케아 사건처럼 호증 경계가 한 면 밀린 편철을 합성 PDF 로 만들어,
  본문에 '사 제3호증에 의하면' 인용이 있는 면을 도장으로 치지 않고 '1면에 도장 없음' 으로
  잡는지 본다. 표지 라벨은 면 오른쪽 위에 호증번호만 적힌 줄일 때만 도장으로 친다.
- trace: 없는 폴더를 받으면 세 수치가 모두 0인 '이상 없음' 모양으로 끝나지 않고 실패한다.
- sheet: 의뢰인 증거 첫 면 모음을 현재 폴더(저장소 루트)가 아니라 사건 폴더의
  증거관리/ 에 쓴다. 사건 폴더 아래가 아니면 --out 을 달라고 하고 멈춘다.
- .gitignore: AI 가 add -A 로 올리므로, 사건/ 밖에 생긴 문서·이미지·음성·녹취 산출물이
  위치와 상관없이 무시되는지, 추적하는 양식·자료는 무시되지 않는지 본다.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'evidence_check', ROOT / '4_서면작성' / 'scripts' / 'evidence_check.py')
evidence_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence_check)
pymupdf = evidence_check.pymupdf


def make_pdf(path, pages):
    """pages 는 면마다 dict(stamp=붉은 도장, label=오른쪽 위 표지 글자, at=표지 위치, body=본문,
    rotated=가로 용지를 90도 돌려 세로로 보이게 한 면). 위치는 모두 화면에 보이는 면 기준이다."""
    doc = pymupdf.open()
    for item in pages:
        if item.get('rotated'):
            page = doc.new_page(width=842, height=595)
            page.set_rotation(90)
        else:
            page = doc.new_page(width=595, height=842)
        shown = page.derotation_matrix   # 화면 좌표 → PDF 좌표

        def write(at, text, size):
            page.insert_text(pymupdf.Point(at) * shown, text, fontname='korea', fontsize=size,
                             rotate=page.rotation)

        if item.get('stamp'):
            page.draw_circle(pymupdf.Point(520, 70) * shown, 28, color=(0.85, 0.1, 0.1), width=4)
        if item.get('label'):
            write(item.get('at', (440, 60)), item['label'], 14)
        write((72, 200), item.get('body', '본문'), 11)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()
    return path


def run(*argv):
    """evidence_check 를 명령줄처럼 부르고 (종료 코드, 표준출력) 을 돌려준다."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, 'argv', ['evidence_check.py', *map(str, argv)]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = evidence_check.main()
    return code, out.getvalue()


CONTRACT = [dict(stamp=True, body='근로계약서 1면'), dict(body='근로계약서 2면')]
RULING = [dict(stamp=True, body='판정서 1면'), dict(body='신청인이 제출한 사 제3호증에 의하면')]
MINUTES = [dict(stamp=True, body='회의록 1면')]


class StampTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / '편철'

    def tearDown(self):
        self.tmp.cleanup()

    def line(self, output, name):
        return next(row for row in output.splitlines() if row.startswith(name))

    def test_body_citation_is_not_a_stamp_so_shifted_boundary_is_caught(self):
        # 판정서 1면이 앞 호증 끝에 붙고, 갑제2호증은 본문에 '사 제3호증' 이 있는 2면부터 시작한다.
        make_pdf(self.folder / '갑제1호증_근로계약서.pdf', CONTRACT + RULING[:1])
        make_pdf(self.folder / '갑제2호증_판정서.pdf', RULING[1:] + MINUTES)
        code, output = run('stamp', self.folder)
        self.assertEqual(code, 0)
        self.assertIn('<<< 1면에 도장 없음', self.line(output, '갑제2호증_판정서.pdf'))
        self.assertIn('도장면=[2]', self.line(output, '갑제2호증_판정서.pdf'))
        self.assertIn('1면에 도장이 없는 파일 1건', output)
        self.assertNotIn('모든 파일의 1면에 도장이 있다', output)

    def test_normal_bundle_has_no_warning(self):
        make_pdf(self.folder / '갑제1호증_근로계약서.pdf', CONTRACT)
        make_pdf(self.folder / '갑제2호증_판정서.pdf', RULING)
        make_pdf(self.folder / '갑제3호증_회의록.pdf', MINUTES)
        code, output = run('stamp', self.folder)
        self.assertEqual(code, 0)
        self.assertNotIn('<<<', output)
        self.assertNotIn('⚠️', output)
        self.assertIn('모든 파일의 1면에 도장이 있다', output)

    def test_black_label_alone_at_top_right_counts_as_stamp(self):
        make_pdf(self.folder / '갑제1호증_근로계약서.pdf', [dict(label='갑 제1호증', body='근로계약서')])
        _, output = run('stamp', self.folder)
        row = self.line(output, '갑제1호증_근로계약서.pdf')
        self.assertIn('도장면=[1]', row)
        self.assertIn('표지=갑제1호증', row)
        self.assertNotIn('<<<', row)

    def test_label_only_cell_outside_stamp_area_is_not_a_stamp(self):
        # 증거목록 표의 첫 칸처럼 번호만 있는 줄이라도 면 왼쪽 아래에 있으면 도장이 아니다.
        make_pdf(self.folder / '갑제1호증_증거설명서.pdf',
                 [dict(label='갑 제1호증', at=(72, 400), body='증거설명서')])
        _, output = run('stamp', self.folder)
        self.assertIn('<<< 1면에 도장 없음', self.line(output, '갑제1호증_증거설명서.pdf'))

    def test_label_number_differs_from_file_name_with_same_party(self):
        make_pdf(self.folder / '갑제2호증_판정서.pdf', [dict(label='갑 제3호증', body='회의록')])
        _, output = run('stamp', self.folder)
        self.assertIn('<<< 표지 번호가 파일명과 다름', self.line(output, '갑제2호증_판정서.pdf'))
        self.assertIn('1면 표지 번호가 파일명과 다른 파일 1건', output)

    def test_renumbered_exhibit_keeps_old_label_without_warning(self):
        # 노동위 사 제61호증을 법원에 갑 제2호증으로 새로 매기면 옛 표지가 남는 것이 정상이다.
        make_pdf(self.folder / '갑제2호증_판정서.pdf', [dict(label='사 제61호증', body='판정서')])
        _, output = run('stamp', self.folder)
        row = self.line(output, '갑제2호증_판정서.pdf')
        self.assertIn('표지=사제61호증', row)
        self.assertNotIn('<<<', row)

    def test_different_label_on_later_page_warns(self):
        make_pdf(self.folder / '갑제1호증_근로계약서.pdf',
                 [dict(label='갑 제1호증'), dict(), dict(label='갑 제2호증', body='다음 호증 첫 장')])
        _, output = run('stamp', self.folder)
        self.assertIn('<<< 1면과 다른 표지: 3면 갑제2호증', self.line(output, '갑제1호증_근로계약서.pdf'))
        self.assertIn('2면 이후에 1면과 다른 호증 표지가 있는 파일 1건', output)

    def test_label_on_rotated_page_is_read_where_it_is_shown(self):
        # 가로 용지를 돌려 세운 스캔본. PDF 좌표로는 왼쪽 위지만 화면에서는 오른쪽 위에 보인다.
        make_pdf(self.folder / '갑제1호증_근로계약서.pdf', [dict(label='갑 제1호증', rotated=True)])
        _, output = run('stamp', self.folder)
        row = self.line(output, '갑제1호증_근로계약서.pdf')
        self.assertIn('표지=갑제1호증', row)
        self.assertNotIn('<<<', row)

    def test_same_label_on_every_page_does_not_warn(self):
        make_pdf(self.folder / '갑제1호증_근로계약서.pdf',
                 [dict(label='갑 제1호증'), dict(label='갑 제1호증'), dict(label='갑 제1호증')])
        _, output = run('stamp', self.folder)
        self.assertNotIn('<<<', self.line(output, '갑제1호증_근로계약서.pdf'))
        self.assertIn('모든 파일의 1면에 도장이 있다', output)


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_folder_fails_instead_of_reporting_zero(self):
        make_pdf(self.root / '편철' / '갑제1호증_근로계약서.pdf', CONTRACT)
        code, output = run('trace', self.root / '없는폴더', self.root / '편철')
        self.assertNotEqual(code, 0)
        self.assertIn('폴더 없음', output)
        self.assertIn('대조하지 않았다', output)
        self.assertNotIn('중복 사용', output)

    def test_folder_without_pdf_fails(self):
        make_pdf(self.root / '원본' / '근로계약서.pdf', CONTRACT)
        (self.root / '편철').mkdir()
        code, output = run('trace', self.root / '원본', self.root / '편철')
        self.assertNotEqual(code, 0)
        self.assertIn('PDF 없음', output)

    def test_matching_bundle_still_traces(self):
        make_pdf(self.root / '원본' / '근로계약서.pdf', CONTRACT)
        make_pdf(self.root / '편철' / '갑제1호증_근로계약서.pdf', CONTRACT)
        code, output = run('trace', self.root / '원본', self.root / '편철')
        self.assertEqual(code, 0)
        self.assertIn('원본 2면 중 2면 사용, 0면 미사용', output)


class SheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cwd = self.root / '작업위치'
        self.cwd.mkdir()
        self.previous = os.getcwd()
        os.chdir(self.cwd)   # 기본 출력이 현재 폴더에 떨어지면 여기에 남는다

    def tearDown(self):
        os.chdir(self.previous)
        self.tmp.cleanup()

    def test_default_output_goes_to_case_evidence_folder_not_cwd(self):
        case = self.root / '4_서면작성' / '사건' / '테스트사건'
        folder = case / '라운드1' / '출력' / '제출' / '증거'
        make_pdf(folder / '갑제1호증_근로계약서.pdf', CONTRACT)
        code, output = run('sheet', folder, '--dpi', 20)
        self.assertEqual(code, 0)
        self.assertTrue((case / '증거관리' / '증거확인.png').is_file())
        self.assertEqual(list(self.cwd.iterdir()), [])
        self.assertEqual(list(folder.parent.glob('*.png')), [])   # 제출 묶음에 섞지 않는다

    def test_folder_outside_case_requires_out(self):
        folder = self.root / '편철'
        make_pdf(folder / '갑제1호증_근로계약서.pdf', CONTRACT)
        code, output = run('sheet', folder, '--dpi', 20)
        self.assertNotEqual(code, 0)
        self.assertIn('--out', output)
        self.assertEqual(list(self.root.rglob('*.png')), [])

    def test_case_folder_is_searched_inside_repository_only(self):
        # 저장소를 품은 바깥 폴더 이름이 '사건' 이면 그 아래(저장소 루트)를 사건 폴더로 보지 않는다.
        repo = self.root / '사건' / '노동사건자동화'
        with mock.patch.object(evidence_check, 'ROOT', repo.resolve()):
            self.assertIsNone(evidence_check._case_dir(repo / '2_판례검색' / '자료'))
            self.assertEqual(evidence_check._case_dir(repo / '4_서면작성' / '사건' / 'A' / '라운드1' / '우리증거'),
                             (repo / '4_서면작성' / '사건' / 'A').resolve())

    def test_explicit_out_creates_parent_folder(self):
        folder = self.root / '편철'
        make_pdf(folder / '갑제1호증_근로계약서.pdf', CONTRACT)
        out = self.root / '사건' / '테스트사건' / '증거관리' / '확인.png'
        code, _ = run('sheet', folder, '--out', out, '--dpi', 20)
        self.assertEqual(code, 0)
        self.assertTrue(out.is_file())


@unittest.skipIf(shutil.which('git') is None, 'git 이 없다')
class GitignoreTests(unittest.TestCase):
    """저장소 .gitignore 를 빈 저장소에 옮겨 놓고 git 에게 직접 묻는다."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.tmp.name)
        subprocess.run(['git', 'init', '-q'], cwd=cls.repo, check=True, capture_output=True)
        shutil.copyfile(ROOT / '.gitignore', cls.repo / '.gitignore')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ignored(self, paths):
        """paths 가운데 무시되는 것. 한글 경로가 따옴표로 바뀌지 않게 NUL 로 주고받는다."""
        result = subprocess.run(['git', 'check-ignore', '--no-index', '--stdin', '-z'],
                                input='\0'.join(paths).encode('utf-8'), cwd=self.repo, capture_output=True)
        self.assertIn(result.returncode, (0, 1), result.stderr.decode('utf-8', 'replace'))
        return {p for p in result.stdout.decode('utf-8').split('\0') if p}

    def test_client_files_are_ignored_anywhere(self):
        paths = [
            # evidence_check sheet 의 옛 기본 출력과 문서 예시
            '증거확인.png', '증거확인_1.png', '확인용.png',
            # 서면전환 가이드의 작업 산출물
            'out.docx', 'out.pdf', 'page-1.jpg', 'unpacked/word/document.xml', 'unpacked/_rels/.rels',
            '1_검토의견/작업/word/document.xml',
            # 간이 녹취 산출물과 녹음 형식
            '5_녹취록/통화.녹취.txt', '5_녹취록/통화.녹취.json', '5_녹취록/통화.부분.jsonl',
            '5_녹취록/녹취록_통화.md', '5_녹취록/녹취서_통화.md', '5_녹취록/녹취_쟁점요약.md',
            '1_검토의견/첨부/통화.녹취.txt', '5_녹취록/통화.m4a', '5_녹취록/통화.amr', '5_녹취록/면담.aac',
            '5_녹취록/면담.3gp', '5_녹취록/면담.webm',
            # 검산 입력과 계산표
            '6_손해배상계산/검산.yaml', '사건.yaml',
            '6_손해배상계산/2025나1234(김철수)_노동금액계산표.xlsx',
            # 의뢰인이 보낸 자료
            '진단서.hwp', '징계통보서.pdf', '의뢰인메일.msg', '의뢰인메일.eml', '사진묶음.zip',
            '임금대장.csv', '임금대장.xlsx', '2_판례검색/양식/리서치.docx',
            # 사건 폴더와 Claude Code 실행 파일
            '4_서면작성/사건/테스트사건/증거관리/증거확인.png', '4_서면작성/사건/테스트사건/작업/메모.md',
            '.claude/scheduled_tasks.lock', '.claude/worktrees/agent-1/CLAUDE.md',
            '.claude/settings.local.json',
        ]
        self.assertEqual(sorted(set(paths) - self.ignored(paths)), [])

    def test_tracked_templates_and_system_files_stay_trackable(self):
        paths = [
            '4_서면작성/templates/표준양식.docx', '6_손해배상계산/00_양식/입력서.xlsx',
            '6_손해배상계산/data/life_table.csv', '6_손해배상계산/data/wage_quarterly.csv',
            '공통/실행검증/20260910_주요3기능/6_손해배상계산_재산출.xlsx',
            '6_손해배상계산/cases/sample.yaml', '6_손해배상계산/cases/labor_sample.yaml',
            '6_손해배상계산/01_입력/.gitkeep', '5_녹취록/녹취서-작성-가이드.md',
            '5_녹취록/녹취록 환경설치.bat', '4_서면작성/requirements.txt',
            '4_서면작성/scripts/evidence_check.py', '공통/tests/test_evidence_check.py',
            '.claude/settings.json', '.claude/commands/서면.md', 'CLAUDE.md', '.gitattributes',
        ]
        self.assertEqual(sorted(self.ignored(paths)), [])

    def test_no_tracked_file_matches_gitignore(self):
        # 저장소 안에서 돌 때만 본다. 작업본에 .git 이 없는 PC(.git 은 OneDrive 밖)에서는 건너뛴다.
        inside = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'],
                                cwd=ROOT, capture_output=True, text=True)
        top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, capture_output=True, text=True)
        if inside.returncode != 0 or Path(top.stdout.strip()).resolve() != ROOT:
            self.skipTest('저장소 작업본이 아니다')
        result = subprocess.run(['git', 'ls-files', '-ci', '--exclude-per-directory=.gitignore', '-z'],
                                cwd=ROOT, capture_output=True, check=True)
        tracked = [p for p in result.stdout.decode('utf-8').split('\0') if p]
        self.assertEqual(tracked, [], '추적 중인 파일이 .gitignore 에 걸린다. 맨 아래 예외 절에 더한다.')


if __name__ == '__main__':
    unittest.main()
