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
        본문 = ('(을 제110호증의2 5~7면, 9면, 11면, 을 제47호증의1 5면) (갑 제18호증의5 원고 소명서 1면, 4~9면) '
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

    def test_grouped_exhibits_and_page_ranges_count_as_cited(self):
        """'을 제103호증의1 내지 17 각'·'갑 제1 내지 5호증'·'갑 제1호증 및 갑 제2호증'의 호증 하나하나와 '313면 내지 321면'의 면 하나하나가
        인용이다(2026. 11. 3. 의2부터·갑 제2호증부터를 '인용 없음'으로, 314면부터를 '호증만 인용'으로 적었다)."""
        본문 = ('(을 제103호증의1 내지 17 각 출석 현황) (갑 제18호증 근로복지공단 의견서 313면 내지 321면) (갑 제1 내지 5호증) '
               '(사 제1호증 및 사 제2호증 4면) (노 제3호증 3 내지 5면) (병 제2호증 5면 및 9면) 원고가 낸 것을 제40호증으로 삼았다')
        for k in ('을103-1', '을103-5', '을103-17', '갑1', '갑3', '갑5', '사1'):
            self.assertEqual(ew.인용_상태(본문, k, 1), '호증만 인용', k)
        self.assertEqual(ew.인용_상태(본문, '을103-18', 1), '인용 없음')
        for 면 in (313, 315, 321):
            self.assertEqual(ew.인용_상태(본문, '갑18', 면), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '갑18', 322), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '사2', 4), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '노3', 4), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '병2', 9), '이 면 인용')
        self.assertEqual(ew.인용_상태(본문, '병2', 7), '호증만 인용')
        self.assertEqual(ew.인용_상태(본문, '을40', 1), '인용 없음')                 # '것을 제40호증'의 '을'은 조사이다

    def test_pages_after_a_break_belong_to_something_else(self):
        """면 번호가 아닌 말·다른 호증·닫는 괄호 뒤의 면, 호증 설명 뒤 쉼표 다음의 면은 그 호증의 면으로 보지 않는다."""
        본문 = ('(갑 제19호증 현수막 사진 2면, 제1심 판결문 13면) (사 제9호증 1면, 2면), 80면부터 '
               '(사 제11호증 2면, 사 제12호증 파트장 관리일지 4면) 갑 제20호증 3면, 사실조사서 6면 '
               '(갑 제21호증의4 2025. 1. 8. 조합활동 방해영상3, 제1심 판결문 11면) (갑 제22호증 2,750만 원 영수증 2면) '
               '(갑 제23호증 제3조 제2호, 15면)')
        self.assertEqual(ew.인용_상태(본문, '갑21-4', 11), '호증만 인용')        # 쉼표 다음은 판결문의 면이다
        self.assertEqual(ew.인용_상태(본문, '갑22', 2), '이 면 인용')            # 천 단위 쉼표는 넘는다
        self.assertEqual(ew.인용_상태(본문, '갑23', 15), '이 면 인용')           # 면 표시 바로 앞의 쉼표도 넘는다
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

    def test_split_drafts_with_own_numbering(self):
        """서면마다 호증 번호를 따로 매긴 라운드: 같은 번호의 두 호증을 모두 찾고, 서면 인용은 그 서면의 본문으로만 본다(2026. 11. 8. `/하자보완`:
        한 번호에 한 파일만 찾고 두 서면의 인용을 합쳐 보았다)."""
        with tempfile.TemporaryDirectory() as d:
            사건 = Path(d) / '이○○_심사청구'
            출력 = 사건 / '라운드1' / '출력'
            for n, 폴더 in (('림프종', '림프종'), ('적응장애우울증', '적응장애·우울증')):
                (출력 / '제출' / 폴더 / '증거').mkdir(parents=True)
                make_pdf(출력 / '제출' / 폴더 / '증거' / f'증 제2호증_{n} 진단서.pdf', [글 + f'{n} 상병 진단 시험'])
            (출력 / '서면초안_림프종.md').write_text('진단받았습니다(증 제2호증 1면).\n', encoding='utf-8')
            (출력 / '서면초안_적응장애우울증.md').write_text('진단받았습니다(증 제1호증).\n', encoding='utf-8')
            본문 = ew.서면_본문들(사건)
            self.assertEqual(ew.인용_상태(본문, '증2@림프종', 1), '이 면 인용')
            self.assertEqual(ew.인용_상태(본문, '증2@적응장애우울증', 1), '인용 없음')    # 다른 서면의 인용이다
            self.assertEqual(ew.인용_상태(본문, '증2', 1), '이 면 인용')                  # 서면 이름이 없는 키는 모든 서면으로 본다
            표 = 사건 / '라운드1' / '작업' / '쟁점낱말_대조.md'
            code, out = run(사건, '--낱말', '시험', '--no-ocr')
            self.assertEqual(code, 0)
            줄 = [l for l in 표.read_text(encoding='utf-8').splitlines() if l.startswith('| 증')]
            self.assertTrue(any(l.startswith('| 증 제2호증(림프종) | 1 | 시험 |') and '| 이 면 인용 |' in l for l in 줄), 줄)
            self.assertTrue(any(l.startswith('| 증 제2호증(적응장애우울증) | 1 | 시험 |') and '| 인용 없음 |' in l for l in 줄), 줄)
            self.assertEqual(ew.표시_키('증 제2호증(적응장애우울증)'), '증2@적응장애우울증')
            code, out = run(사건, '--확인')
            self.assertEqual(code, 1)
            self.assertIn('증 제2호증(적응장애우울증) 1면', out)
            self.assertNotIn('표를 만든 뒤', out)                              # 찾은 호증 절의 이름 붙은 키를 읽어 들인다


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

    def test_check_blocks_exhibits_added_or_changed_after_the_table(self):
        """표를 만든 뒤 들어오거나 파일이 바뀐 호증은 낱말로 찾지 않았다(2026. 11. 5. `/하자보완`: 표의 줄만 보아 통과시켰다)."""
        r = self.case / '라운드1'
        run(self.case, '--낱말', '시험', '--no-ocr')
        self.set_judgement('사 제6호증', 3, '본문 2항에 씀')
        self.assertEqual(run(self.case, '--확인')[0], 0)
        make_pdf(r / '우리증거' / '사 제8호증 추가.pdf', [글 + '시험 기기 반입 금지'])
        code, out = run(self.case, '--확인')
        self.assertEqual(code, 1)
        self.assertIn('표를 만든 뒤 들어온 호증 1건: 사 제8호증', out)
        run(self.case, '--낱말', '시험', '--no-ocr')
        self.assertTrue(any('| 사 제6호증 | 3 |' in l and '본문 2항에 씀' in l for l in self.rows()))      # 판단은 이어받는다
        self.set_judgement('사 제8호증', 1, '본문 3항에 씀')
        self.assertEqual(run(self.case, '--확인')[0], 0)
        make_pdf(r / '우리증거' / '사 제7호증 공지.pdf', [글 + '공지 1면 바뀐 판'])                       # 같은 번호에 다른 파일
        code, out = run(self.case, '--확인')
        self.assertEqual(code, 1)
        self.assertIn('표를 만든 뒤 파일이 바뀐 호증 1건: 사 제7호증', out)
        run(self.case, '--낱말', '시험', '--no-ocr')
        self.assertEqual(run(self.case, '--확인')[0], 0)

    def test_rerun_of_some_exhibits_keeps_the_others_in_the_list(self):
        상대 = self.case / '라운드1' / '상대증거'
        상대.mkdir()
        make_pdf(상대 / '노 제1호증 주장.pdf', [글 + '노 1면'])
        run(self.case, '--낱말', '시험', '--no-ocr')
        self.set_judgement('사 제6호증', 3, '본문 2항에 씀')
        make_pdf(상대 / '노 제1호증 주장.pdf', [글 + '노 1면 바뀐 판'])
        run(self.case, '--낱말', '시험', '--호증', '사', '--no-ocr')                  # 사 호증만 다시 찾았다
        code, out = run(self.case, '--확인')
        self.assertEqual(code, 1)
        self.assertIn('파일이 바뀐 호증 1건: 노 제1호증', out)                          # 노 호증은 앞 표의 해시가 남아 바뀐 것을 안다
        run(self.case, '--낱말', '시험', '--호증', '노', '--no-ocr')
        self.assertEqual(run(self.case, '--확인')[0], 0)

    def test_old_table_without_the_list_compares_only_counts(self):
        run(self.case, '--낱말', '시험', '--no-ocr')
        self.set_judgement('사 제6호증', 3, '본문 2항에 씀')
        self.table.write_text(self.table.read_text(encoding='utf-8').split(ew.찾은_머리)[0], encoding='utf-8')   # 11. 5. 앞에 만든 표
        self.assertEqual(run(self.case, '--확인')[0], 0)
        make_pdf(self.case / '라운드1' / '우리증거' / '사 제8호증 추가.pdf', [글])
        code, out = run(self.case, '--확인')
        self.assertEqual(code, 1)
        self.assertIn('표를 만든 뒤 호증이 늘었다(표 2건, 지금 3건)', out)

    def test_text_only_does_not_touch_the_table(self):
        code, out = run(self.case, '--글', '사6', '--no-ocr')
        self.assertEqual(code, 0)
        self.assertIn('--- 사 제6호증 3면', out)
        self.assertFalse(self.table.exists())
        self.assertEqual(run(self.case, '--확인')[0], 1)          # 표가 없으면 막는다


if __name__ == '__main__':
    unittest.main()
