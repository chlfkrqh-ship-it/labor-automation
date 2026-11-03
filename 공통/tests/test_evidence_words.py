"""쟁점 낱말 대조(4_서면작성/scripts/evidence_words.py)를 확인한다.

서면이 그 호증의 그 면을 인용하였는지 가르는 판정(다른 호증의 면을 이 호증의 면으로 보지 않는지, '3, 5면'을 범위로 보지 않는지,
'5~7면, 9면, 11면'처럼 묶음마다 '면'을 붙여 이은 뒤 묶음도 읽는지),
다시 돌려도 앞서 적은 '판단'을 잃지 않는지, `--확인` 이 판단이 빈 줄을 막는지 본다. 문자인식(Windows)은 돌리지 않는다(--no-ocr).
2026. 11. 2. GGM 사 제6호증 3면을 놓친 일 뒤에 넣었다.
"""
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

import pymupdf

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('evidence_words', ROOT / '4_서면작성/scripts/evidence_words.py')
ew = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ew)

글 = ('공지 문자 안내입니다 오늘도 안전한 하루 되십시오\n'       # 글자층이 넉넉한 면(80자 넘게)
     '현장의 모든 구성원은 안전 수칙을 지켜 주시기 바랍니다\n'
     '작업 전후 점검표를 확인하고 이상이 있으면 즉시 보고합니다\n'
     '보호구를 갖추고 정해진 통로로만 다닙니다\n')


def make_pdf(path: Path, pages):
    d = pymupdf.open()
    for t in pages:
        d.new_page().insert_text((40, 72), t, fontsize=7, fontname='korea')
    d.save(path)


def run(*args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = ew.main([str(a) for a in args])
    return code, out.getvalue()


class CitedPageTest(unittest.TestCase):
    def test_page_after_another_exhibit_is_not_this_exhibits_page(self):
        본문 = '안전 수칙을 알렸습니다(사 제6호증, 사 제7호증 3면).'
        self.assertEqual(ew.인용_상태(본문, '사6', 3), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '사7', 3), '이 면 인용')

    def test_comma_lists_pages_and_tilde_is_a_range(self):
        본문 = '(사 제6호증 2, 4면) (사 제8호증 2~4면) (사 제9호증 제3면) (사 제10호증 5쪽)'
        self.assertEqual(ew.인용_상태(본문, '사6', 3), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '사6', 4), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '사8', 3), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '사9', 3), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '사10', 5), '이 면 인용')

    def test_page_groups_each_with_its_own_mark_are_all_read(self):
        """'5~7면, 9면, 11면'의 9면부터도 그 호증의 면이다(2026. 11. 3. 한전 을 제110호증의2·갑 제18호증의5 를 '호증만 인용'으로 적었다)."""
        본문 = ('(을 제110호증의2 5~7면, 9면, 11면, 을 제47호증의1 5면) (갑 제18호증의5 우장하 소명서 1면, 4~9면) '
               '(을 제43호증 8~9면, 12면) (사 제2호증 3면·5면)')
        for 면 in (5, 6, 7, 9, 11):
            self.assertEqual(ew.인용_상태(본문, '을110-2', 면), '이 면 인용')
        for 면 in (8, 10, 12):
            self.assertEqual(ew.인용_상태(본문, '을110-2', 면), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '을47-1', 5), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '을47-1', 9), '호증만 인용')
        for 면 in (1, 4, 6, 9):
            self.assertEqual(ew.인용_상태(본문, '갑18-5', 면), '이 면 인용')
        for 면 in (2, 3, 10):
            self.assertEqual(ew.인용_상태(본문, '갑18-5', 면), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '을43', 12), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '을43', 10), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '사2', 5), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '사2', 4), '호증만 인용')

    def test_pages_after_a_break_belong_to_something_else(self):
        """면 번호가 아닌 말·다른 호증·닫는 괄호 뒤의 면은 그 호증의 면으로 보지 않는다."""
        본문 = ('(갑 제19호증 현수막 사진 2면, 제1심 판결문 13면) (사 제9호증 1면, 2면), 80면부터 '
               '(사 제11호증 2면, 사 제12호증 파트장 관리일지 4면) 갑 제20호증 3면, 사실조사서 6면')
        self.assertEqual(ew.인용_상태(본문, '갑19', 2), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '갑19', 13), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '사9', 2), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '사9', 80), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '사11', 4), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '사12', 4), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '갑20', 3), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '갑20', 6), '호증만 인용')

    def test_branch_numbers_and_longer_numbers_are_other_exhibits(self):
        본문 = '(사 제6호증의1 3면) (사 제16호증 3면)'
        self.assertEqual(ew.인용_상태(본문, '사6', 3), '인용 없음')
        self.assertEqual(ew.인용_상태(본문, '사6-1', 3), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '사1', 3), '인용 없음')


class SplitDraftTest(unittest.TestCase):
    def test_body_of_split_drafts_is_read(self):
        """서면을 나눈 라운드(서면초안_{이름}.md)의 인용을 '인용 없음'으로 적지 않는다(2026. 11. 3.). 지난 판과 본문 조각 파일은 읽지 않는다."""
        with tempfile.TemporaryDirectory() as d:
            사건 = Path(d)
            출력 = 사건 / '라운드1' / '출력'
            출력.mkdir(parents=True)
            (출력 / '서면초안_림프종.md').write_text('사실입니다(사 제6호증 3면).\n\n---\n\n메모(사 제9호증)\n', encoding='utf-8')
            (출력 / '서면초안_본문.md').write_text('사 제7호증\n', encoding='utf-8')
            본문 = ew.서면_본문(사건)
            self.assertEqual(ew.인용_상태(본문, '사6', 3), '이 면 인용')
            self.assertEqual(ew.인용_상태(본문, '사7', 1), '인용 없음')
            self.assertEqual(ew.인용_상태(본문, '사9', 1), '인용 없음')
            (사건 / '라운드2' / '출력').mkdir(parents=True)
            (사건 / '라운드2' / '출력' / '서면초안.md').write_text('다시 봅니다(사 제8호증 1면).\n', encoding='utf-8')
            (사건 / '라운드2' / '출력' / '서면초안_긴판.md').write_text('지난 판(사 제7호증)\n', encoding='utf-8')
            본문 = ew.서면_본문(사건)
            self.assertEqual(ew.인용_상태(본문, '사8', 1), '이 면 인용')
            self.assertEqual(ew.인용_상태(본문, '사7', 1), '인용 없음')


class TableTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / 'GGM_정직'
        r = self.case / '라운드1'
        for d in ('우리증거', '출력', '작업'):
            (r / d).mkdir(parents=True)
        make_pdf(r / '우리증거' / '사 제6호증 문자.pdf',
                 [글 + '1면', 글 + '2면', 글 + '작업 중 시험 기기 등 전자 장비 사용 금지'])
        make_pdf(r / '우리증거' / '사 제7호증 공지.pdf', [글 + '공지 1면', 글 + '공지 2면 무선 장비 안내', 글 + '공지 3면'])
        self.draft = r / '출력' / '서면초안.md'
        self.draft.write_text('- 다 음 -\n\n1. 가\n\n안전 수칙을 알렸습니다(사 제6호증, 사 제7호증 3면).\n\n---\n\n① (사 제6호증 3면)\n',
                              encoding='utf-8')
        self.table = r / '작업' / '쟁점낱말_대조.md'

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        return [l for l in self.table.read_text(encoding='utf-8').splitlines() if l.startswith('| 사')]

    def set_judgement(self, 호증, 면, 판단):
        lines = self.table.read_text(encoding='utf-8').splitlines()
        for i, l in enumerate(lines):
            if l.startswith(f'| {호증} | {면} |'):
                lines[i] = l[:l.rstrip().rstrip('|').rstrip().rfind('|') + 1] + f' {판단} |'
        self.table.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def test_uncited_page_is_listed_first_and_check_blocks_it(self):
        code, out = run(self.case, '--낱말', '시험', '--no-ocr')
        self.assertEqual(code, 0)
        rows = self.rows()
        self.assertTrue(rows[0].startswith('| 사 제6호증 | 3 | 시험 |'))
        self.assertIn('| 호증만 인용 |', rows[0])                 # 하단 목록('---' 아래)의 인용은 세지 않는다
        code, out = run(self.case, '--확인')
        self.assertEqual(code, 1)
        self.assertIn('사 제6호증 3면', out)
        self.set_judgement('사 제6호증', 3, '본문 2항에 씀')
        self.assertEqual(run(self.case, '--확인')[0], 0)

    def test_rerun_keeps_judgements_and_rows_of_words_not_searched_again(self):
        run(self.case, '--낱말', '시험', '전자', '--no-ocr')
        self.set_judgement('사 제6호증', 3, '본문 2항에 씀')
        run(self.case, '--낱말', '전자', '시험', '--no-ocr')        # 낱말 순서가 바뀌어 같은 면의 줄 낱말이 달라져도
        self.assertTrue(any('| 사 제6호증 | 3 |' in l and '본문 2항에 씀' in l for l in self.rows()))
        run(self.case, '--낱말', '무선', '--no-ocr')               # 새 낱말만 다시 돌려도 앞선 줄과 판단이 남는다
        rows = self.rows()
        self.assertTrue(any('| 사 제6호증 | 3 |' in l and '본문 2항에 씀' in l for l in rows))
        self.assertTrue(any(l.startswith('| 사 제7호증 | 2 | 무선 |') for l in rows))
        self.assertIn('낱말: 무선, ', self.table.read_text(encoding='utf-8'))

    def test_check_rereads_the_draft(self):
        run(self.case, '--낱말', '시험', '--no-ocr')
        self.draft.write_text('- 다 음 -\n\n1. 가\n\n금지하였습니다(사 제6호증 3면).\n', encoding='utf-8')
        self.assertEqual(run(self.case, '--확인')[0], 0)          # 지금 초안이 그 면을 인용하면 판단 없이도 된다
        self.assertEqual(run(self.case / 'x', '--확인')[0], 2)

    def test_text_only_does_not_touch_the_table(self):
        code, out = run(self.case, '--글', '사6', '--no-ocr')
        self.assertEqual(code, 0)
        self.assertIn('--- 사 제6호증 3면', out)
        self.assertFalse(self.table.exists())
        self.assertEqual(run(self.case, '--확인')[0], 1)          # 표가 없으면 막는다


if __name__ == '__main__':
    unittest.main()
