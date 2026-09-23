"""서면 인용 대조(4_서면작성/scripts/citation_check.py)를 확인한다.

호증번호·사건번호 정규식은 공통/scripts/system.py 한 곳에 있다. 병기('갑 제2, 3호증',
'갑 제1 내지 3호증', '갑 제21·22호증')를 번호마다 펼치는지, 노동 사건에서 쓰는 사건부호
(다카·고단·고정·노·마·카합·라·가소·헌바 등)를 빠뜨리지 않는지 본다. 같은 호증번호 정의를
쓰는 evidence_rename.py(파일명 앞머리의 호증번호)도 여기서 본다.
"""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import docx

ROOT = Path(__file__).parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


system = load('workflow_system', '공통/scripts/system.py')
citation_check = load('citation_check', '4_서면작성/scripts/citation_check.py')
evidence_rename = load('evidence_rename', '4_서면작성/scripts/evidence_rename.py')


class EvidenceNumberTests(unittest.TestCase):
    def test_list_and_range_forms_expand_to_each_number(self):
        table = {
            '(갑 제1호증)': ['갑제1호증'],
            '(갑제1호증)': ['갑제1호증'],
            '(갑 제 1 호증)': ['갑제1호증'],
            '(갑 제2, 3호증)': ['갑제2호증', '갑제3호증'],
            '(갑 제51, 52호증)': ['갑제51호증', '갑제52호증'],
            '(갑 제1 내지 3호증)': ['갑제1호증', '갑제2호증', '갑제3호증'],
            '(갑 제21·22호증)': ['갑제21호증', '갑제22호증'],
            '(갑 제21·22·35·43호증)': ['갑제21호증', '갑제22호증', '갑제35호증', '갑제43호증'],
            '(사 제61~63호증)': ['사제61호증', '사제62호증', '사제63호증'],
            # 한글 입력기가 넣는 전각 물결표·가운뎃점
            '(사 제61～63호증)': ['사제61호증', '사제62호증', '사제63호증'],
            '(갑 제21ㆍ22호증)': ['갑제21호증', '갑제22호증'],
            '(갑 제41호증 내지 제43호증)': ['갑제41호증', '갑제42호증', '갑제43호증'],
            '(갑 제31호증 ~ 갑 제33호증)': ['갑제31호증', '갑제32호증', '갑제33호증'],
            '(갑 제1호증 - 갑 제3호증)': ['갑제1호증', '갑제2호증', '갑제3호증'],
            '(갑 제1호증, 2, 3호증)': ['갑제1호증', '갑제2호증', '갑제3호증'],
            '갑 제3호증과 제4호증에 의하면': ['갑제3호증', '갑제4호증'],
            '(갑 제1호증 근로계약서, 갑 제2호증 해고통지서)': ['갑제1호증', '갑제2호증'],
            '(갑 제1호증 및 을 제2호증)': ['갑제1호증', '을제2호증'],
            # 접두어가 바뀌면 범위가 아니다
            '(갑 제1호증 ~ 을 제3호증)': ['갑제1호증', '을제3호증'],
        }
        for text, expected in table.items():
            with self.subTest(text=text):
                self.assertEqual(system.evidence_labels(text), expected)

    def test_branch_numbers_fold_into_parent(self):
        table = {
            '(을나 제1호증의 2)': ['을나제1호증'],
            '(사 제67호증의1·2)': ['사제67호증'],
            '(갑 제5호증의 1 내지 3)': ['갑제5호증'],
            '(갑 제1, 2호증의 각 1)': ['갑제1호증', '갑제2호증'],
            '(갑 제1-1호증)': ['갑제1호증'],
            # '의 1' 뒤에 '제'가 다시 나오면 모번호의 범위다
            '(갑 제5호증의 1 내지 제7호증)': ['갑제5호증', '갑제6호증', '갑제7호증'],
            '(갑 제5호증의 1, 제6호증)': ['갑제5호증', '갑제6호증'],
        }
        for text, expected in table.items():
            with self.subTest(text=text):
                self.assertEqual(system.evidence_labels(text), expected)

    def test_prefixes_of_every_numbering_system(self):
        self.assertEqual(system.evidence_labels('(노 제24호증, 사 제1호증, 을가 제3호증, 을다 제2호증, 병 제1호증, 증 제2호증)'),
                         ['노제24호증', '사제1호증', '을가제3호증', '을다제2호증', '병제1호증', '증제2호증'])

    def test_text_that_only_looks_like_evidence(self):
        for text in ('원고가 제출한 것을 제2호증으로 삼았습니다', '입증 제1호증', '갑 제1, 2019. 3.'):
            with self.subTest(text=text):
                self.assertEqual(system.evidence_labels(text), [])
        # 쉼표 뒤의 날짜·면수는 호증번호가 아니다
        for text in ('(갑 제2호증, 2019. 5. 1.자)', '(갑 제2호증, 3면)', '(갑 제2호증의 1, 2023. 5. 1.자)',
                     '(갑 제18호증 근로복지공단 의견서 313면 내지 321면)'):
            with self.subTest(text=text):
                self.assertEqual(len(system.evidence_labels(text)), 1)


class CaseNumberTests(unittest.TestCase):
    def test_case_types_used_in_labor_practice(self):
        text = ('대법원 1991. 3. 27. 선고 90다카25277 판결, 서울중앙지방법원 2020. 1. 1.자 2020카합12345 결정, '
                '대법원 2019. 1. 1.자 2019마1234 결정, 서울고등법원 2020라1234 결정, 대전지방법원천안지원 2015고단900 판결, '
                '창원지방법원통영지원 2020고정70 판결, 수원지방법원 2018노 3955 판결, 서울중앙지방법원 2018가소24967 판결, '
                '헌법재판소 2019헌마123 결정, 헌법재판소 2014헌바202 결정, 중앙노동위원회 중앙2024부해1677 판정, '
                '2019년3월 12일 근로계약 제3조 제2항')
        self.assertEqual(citation_check.case_numbers(text),
                         {'90다카25277', '2020카합12345', '2019마1234', '2020라1234', '2015고단900', '2020고정70',
                          '2018노3955', '2018가소24967', '2019헌마123', '2014헌바202', '2024부해1677'})


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / '사건'
        (self.case / '증거관리').mkdir(parents=True)
        (self.case / '라운드1' / '출력').mkdir(parents=True)
        rows = ''.join('| 갑 제%d호증 | 자료%d.pdf | 요약 |\n' % (n, n) for n in range(1, 6))
        (self.case / '증거관리' / '우리호증목록.md').write_text(
            '| 호증번호 | 파일명 | 내용 요약 |\n|---|---|---|\n' + rows, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def draft(self, text, name='서면초안.md'):
        path = self.case / '라운드1' / '출력' / name
        path.write_text(text, encoding='utf-8')
        return path

    def test_unlisted_numbers_inside_list_citations_are_violations(self):
        path = self.draft('원고는 입사하였습니다(갑 제21·22호증).\n\n원고는 근무하였습니다(갑 제31~33호증).\n\n'
                          '원고는 해고되었습니다(갑 제41호증 내지 제43호증).\n\n원고는 다투었습니다(갑 제51, 52호증).\n')
        result = citation_check.check(path, self.case)
        self.assertFalse(result['ok'])
        self.assertEqual(sorted(result['not_in_list'], key=lambda x: int(x[2:-2])),
                         ['갑제%d호증' % n for n in (21, 22, 31, 32, 33, 41, 42, 43, 51, 52)])

    def test_listed_numbers_cited_in_list_form_count_as_cited(self):
        path = self.draft('원고는 입사하였습니다(갑 제2, 3호증).\n\n원고는 근무하였습니다(갑 제1 내지 3호증).\n')
        result = citation_check.check(path, self.case)
        self.assertTrue(result['ok'])
        self.assertEqual(result['cited_count'], 3)
        self.assertEqual(result['listed_but_uncited'], ['갑제4호증', '갑제5호증'])

    def test_catalogue_ranges_and_short_first_cells(self):
        (self.case / '증거관리' / '상대호증목록.md').write_text(
            '| 호증번호 | 파일명 |\n|---|---|\n| 을나1-1 | a.pdf |\n| 을 제1~3호증 | b.pdf |\n'
            '| 을 제4호증 내지 제5호증 | c.pdf |\n| 을 제6호증 ~ 을 제7호증 | d.pdf |\n', encoding='utf-8')
        listed = citation_check.listed(self.case)
        for label in ['을나제1호증'] + ['을제%d호증' % n for n in range(1, 8)]:
            self.assertIn(label, listed)

    def test_cases_without_record_include_every_case_type(self):
        path = self.draft('대법원 2099. 1. 1. 선고 2099다카1234 판결, 수원지방법원 2099노9999 판결, '
                          '2099고단1234 판결, 2099마1234 결정, 헌법재판소 2099헌바1234 결정을 봅니다.\n')
        result = citation_check.check(path, self.case)
        self.assertEqual(set(result['cases_without_record']),
                         {'2099다카1234', '2099노9999', '2099고단1234', '2099마1234', '2099헌바1234'})

    def test_memo_below_rule_is_not_body(self):
        path = self.draft('원고는 입사하였습니다(갑 제1호증).\n\n---\n\n① [확인 필요 사항] 갑 제9호증 원본 확인\n')
        result = citation_check.check(path, self.case)
        self.assertTrue(result['ok'])
        self.assertEqual(result['cited_count'], 1)

    def test_docx_footnotes_are_read(self):
        path = self.case / '라운드1' / '출력' / '서면.docx'
        document = docx.Document()
        document.add_paragraph('원고는 입사하였습니다(갑 제1호증).')
        document.save(path)
        footnotes = ('<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                     '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
                     '<w:footnote w:id="1"><w:p><w:r><w:t>대법원 2099. 1. 1. 선고 2099다카777 판결 참조</w:t></w:r></w:p>'
                     '</w:footnote></w:footnotes>')
        patched = path.with_name('각주.docx')
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(patched, 'w') as target:
            for item in source.infolist():
                target.writestr(item, source.read(item.filename))
            target.writestr('word/footnotes.xml', footnotes)
        result = citation_check.check(patched, self.case)
        self.assertEqual(result['cases_cited'], ['2099다카777'])
        self.assertEqual(result['cited_count'], 1)


class EvidenceRenameTests(unittest.TestCase):
    """이미 호증번호로 시작하는 파일의 계획을 조용히 넘기지 않는다(.claude/commands/증거정리.md 5단계)."""

    LONG = '을 제3호증 인사규정_을 제3호증 인사규정_피고 소송대리인 법무법인 가나 담당변호사 홍길동.pdf'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = mock.patch.object(evidence_rename, 'ROOT', self.root)
        self.patch.start()
        self.folder = self.root / '사건' / '라운드1' / '상대증거'
        self.folder.mkdir(parents=True)
        for name in (self.LONG, '인사규정.pdf'):
            (self.folder / name).write_bytes(b'%PDF-1.4')

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def run_plan(self, *items, apply=True):
        plan = self.root / '리네임계획.json'
        items = [dict(item, path='사건/라운드1/상대증거/' + item['path']) for item in items]
        plan.write_text(json.dumps({'items': items}, ensure_ascii=False), encoding='utf-8')
        argv = ['evidence_rename.py', str(plan)] + (['--apply'] if apply else [])
        with mock.patch.object(sys, 'argv', argv), mock.patch('sys.stdout', new_callable=io.StringIO) as out, \
                mock.patch('sys.stderr', new_callable=io.StringIO):
            code = evidence_rename.main()
        return code, json.loads(out.getvalue())

    def names(self):
        return sorted(p.name for p in self.folder.iterdir())

    def test_long_download_name_is_shortened(self):
        code, output = self.run_plan({'path': self.LONG, '호증': '을제3호증', 'name': '을제3호증_인사규정.pdf'})
        self.assertEqual((code, output['renamed'], output['blocked']), (0, 1, []))
        self.assertEqual(self.names(), ['을제3호증_인사규정.pdf', '인사규정.pdf'])

    def test_number_differing_from_file_name_is_blocked(self):
        code, output = self.run_plan({'path': self.LONG, '호증': '을제4호증', 'name': '을제4호증_인사규정.pdf'})
        self.assertEqual((code, output['renamed'], output['items'][0]['status']), (1, 0, '번호불일치'))
        self.assertEqual(len(output['blocked']), 1)
        self.assertIn(self.LONG, self.names())

    def test_name_must_carry_the_planned_number(self):
        code, output = self.run_plan({'path': '인사규정.pdf', '호증': '을제5호증', 'name': '을제6호증_인사규정.pdf'})
        self.assertEqual((code, output['items'][0]['status']), (1, '번호불일치'))
        self.assertIn('인사규정.pdf', self.names())
        code, output = self.run_plan({'path': '인사규정.pdf', '호증': '인사규정'})
        self.assertEqual((code, output['items'][0]['status']), (1, '호증오류'))
        self.assertIn('인사규정.pdf', self.names())

    def test_plain_numbering_is_unchanged(self):
        code, output = self.run_plan({'path': '인사규정.pdf', '호증': '을제5호증'}, {'path': self.LONG, '호증': '을제3호증'})
        self.assertEqual((code, [row['status'] for row in output['items']]), (0, ['변경', '이미부여']))
        self.assertIn('을제5호증_인사규정.pdf', self.names())
        self.assertIn(self.LONG, self.names())


if __name__ == '__main__':
    unittest.main()
