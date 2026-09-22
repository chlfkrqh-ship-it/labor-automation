"""제출처별 대리인 표기 검사(4_서면작성/CLAUDE.md 2-2절)를 확인한다.

노동위원회에 내는 서면에 '소송대리인'이 남아 있으면 위반으로 잡혀야 한다.
표지·서명 블록은 표 칸과 누름틀(내용 컨트롤) 안에 있어 python-docx 의
paragraph.text 로는 보이지 않으므로, 그 자리까지 읽는지도 함께 본다.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import docx
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

spec = importlib.util.spec_from_file_location(
    'style_check', Path(__file__).parents[2] / '4_서면작성' / 'scripts' / 'style_check.py')
style_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(style_check)

RULE = '노동위 서면에 소송대리인'


class VenueAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, name, body=(), cells=(), stamped=None):
        """body 는 본문 문단, cells 는 표 칸, stamped 는 누름틀 안에 넣을 글자."""
        path = self.root / name
        document = docx.Document()
        for line in body:
            document.add_paragraph(line)
        if stamped is not None:
            paragraph = document.add_paragraph()
            paragraph._p.append(parse_xml(
                '<w:sdt %s><w:sdtPr/><w:sdtContent><w:r><w:t>%s</w:t></w:r>'
                '</w:sdtContent></w:sdt>' % (nsdecls('w'), stamped)))
            paragraph.add_run(' 귀중')
        if cells:
            table = document.add_table(rows=len(cells), cols=1)
            for row, line in enumerate(cells):
                table.cell(row, 0).text = line
        document.save(path)
        return path

    def rules(self, path):
        return [row['rule'] for row in style_check.check(path)['violations']]

    def test_labor_venue_with_litigation_agent_is_violation(self):
        path = self.make('노동위.docx',
                         body=['위 사건에 관하여 피신청인의 소송대리인은 다음과 같이 답변서를 제출합니다.',
                               '전남지방노동위원회 귀중'],
                         cells=['소송대리인', '법무법인 평안'])
        result = style_check.check(path)
        self.assertIn(RULE, [row['rule'] for row in result['violations']])
        self.assertFalse(result['ok'])
        # 본문 문단과 표 칸을 각각 잡는다
        self.assertEqual(sum(1 for row in result['violations'] if row['rule'] == RULE), 2)

    def test_venue_inside_content_control_is_read(self):
        path = self.make('누름틀.docx',
                         body=['위 사건에 관하여 피신청인의 소송대리인은 다음과 같이 답변서를 제출합니다.'],
                         stamped='중앙노동위원회')
        self.assertIn(RULE, self.rules(path))

    def test_court_venue_keeps_litigation_agent(self):
        path = self.make('법원.docx',
                         body=['위 사건에 관하여 피고보조참가인의 소송대리인은 다음과 같이 변론을 준비합니다.',
                               '서울행정법원 제1부 귀중'],
                         cells=['피고보조참가인 소송대리인'])
        self.assertNotIn(RULE, self.rules(path))

    def test_labor_venue_with_plain_agent_is_clean(self):
        path = self.make('노동위_정상.docx',
                         body=['위 사건에 관하여 피신청인의 대리인은 다음과 같이 답변서를 제출합니다.',
                               '전남지방노동위원회 귀중'],
                         cells=['대리인', '담당노무사 최 락 보'])
        self.assertNotIn(RULE, self.rules(path))

    def test_cited_decision_is_not_a_venue(self):
        """본문에서 노동위원회 판정을 인용한 법원 서면은 제출처가 법원이다."""
        path = self.make('인용.docx',
                         body=['중앙노동위원회 2026부해109 판정의 취지는 다음과 같습니다.',
                               '위 사건에 관하여 원고의 소송대리인은 다음과 같이 변론을 준비합니다.',
                               '서울행정법원 제1부 귀중'])
        self.assertNotIn(RULE, self.rules(path))

    def test_markdown_draft_has_no_cover(self):
        path = self.root / '서면초안.md'
        path.write_text('피신청인은 다음과 같이 답변합니다.\n', encoding='utf-8')
        self.assertEqual(style_check.cover_texts(path), [])
        self.assertNotIn(RULE, self.rules(path))


if __name__ == '__main__':
    unittest.main()
