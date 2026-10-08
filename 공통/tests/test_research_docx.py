import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('research_docx', REPO / '공통' / 'scripts' / 'research_docx.py')
research_docx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research_docx)

DATA = {
    '제목': '(리서치) 시험 문서',
    '출력': '(리서치) 시험 문서.docx',
    '문단나눔': True,
    '절': [
        {'제목': '검토 요지', '블록': [{'표지': '①', '너비': 300, '문': '결론 한 줄입니다.'}]},
        {'제목': '적용되는지', '블록': [
            {'문': '2026. 10. 8. 기준으로 **굵은 글**이 있는 문단입니다.'},
            {'박스': [{'출처': '대법원 2000. 1. 1. 선고 2000다1 판결', '원문': ['원문 첫 문단이다.', '원문 둘째 문단이다.']},
                     {'출처': '왼쪽 정렬 행', '왼쪽': True, '원문': ['가ㆍ나ㆍ다ㆍ라']}]},
            {'표': {'열': [2000, 7016], '머리': ['구분', '내용'], '행': [['유리', '첫 줄\n둘째 줄']]}},
        ], '항': [{'제목': '소제목', '블록': [{'문': '항 안의 문단입니다.'}]}]},
    ],
}


class BuildDocumentTests(unittest.TestCase):
    """양식 없이 볼 수 있는 것: 본문 XML 을 만드는 부분."""

    TEMPLATE_XML = ('<w:document><w:body><w:p w:rsidR="1"><w:pPr><w:pStyle w:val="aff0"/></w:pPr></w:p>'
                    '<w:sectPr><w:pgSz/></w:sectPr></w:body></w:document>')

    def test_body_has_title_headings_boxes_and_no_head_paragraph(self):
        xml = research_docx.build_document(self.TEMPLATE_XML, DATA)
        self.assertIn('(리서치) 시험 문서', xml)
        self.assertIn('검토 요지', xml)
        self.assertIn('원문 둘째 문단이다.', xml)
        self.assertIn('<w:b/>', xml)                       # 출처 줄과 **굵게**
        self.assertEqual(xml.count('<w:tbl>'), 2)          # 박스 하나, 표 하나
        self.assertIn('가.', xml)                          # 소제목 번호는 글자로 적는다
        self.assertTrue(xml.rstrip().endswith('</w:body></w:document>'))

    def test_dates_do_not_break_inside(self):
        xml = research_docx.build_document(self.TEMPLATE_XML, DATA)
        nb = research_docx.NBSP
        self.assertIn('2026.' + nb + '10.' + nb + '8.', xml)

    def test_left_aligned_box_row(self):
        xml = research_docx.box([{'출처': '출처', '왼쪽': True, '원문': ['원문']}])
        self.assertEqual(xml.count('<w:jc w:val="left"/>'), 2)
        self.assertNotIn('<w:jc', research_docx.box([{'출처': '출처', '원문': ['원문']}]))

    def test_table_width_must_match_text_width(self):
        with self.assertRaises(SystemExit):
            research_docx.grid({'열': [1000, 1000], '머리': ['가', '나'], '행': [['1', '2']]})


class TargetsTests(unittest.TestCase):
    """내용 파일 위치에 따라 docx 와 빌드기록을 어디에 쓰는지."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, rel):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DATA, ensure_ascii=False), encoding='utf-8')
        return path

    def test_json_in_build_folder_writes_one_level_up(self):
        data_path = self.put('작업/빌드/리서치_내용.json')
        _, _, out, md, record = research_docx.targets([str(data_path)])
        self.assertEqual(out, (self.root / '작업' / DATA['출력']).resolve())
        self.assertIsNone(md)
        self.assertEqual(record.name, '리서치_빌드기록.json')
        self.assertEqual(record.parent, data_path.parent.resolve())

    def test_out_option_is_a_trial_build_without_record(self):
        data_path = self.put('작업/빌드/리서치_내용.json')
        trial = self.root / '시험'
        _, _, out, md, record = research_docx.targets([str(data_path), '--out', str(trial)])
        self.assertEqual(out, trial / DATA['출력'])
        self.assertIsNone(record)
        self.assertFalse(research_docx.edited_by_hand(out, record))

    def test_missing_content_file_is_an_error(self):
        with self.assertRaises(SystemExit):
            research_docx.targets([])
        with self.assertRaises(SystemExit):
            research_docx.targets([str(self.root / '없음.json')])


@unittest.skipUnless(research_docx.TEMPLATE.exists(), '리서치 양식(docx)은 git 에 없고 OneDrive 로만 온다')
class TrialBuildTests(unittest.TestCase):
    """양식이 있는 PC 에서만: 시험 빌드가 열리는 docx 를 만들고 머리글 전화번호를 바꾼다."""

    def test_trial_build_makes_a_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / '빌드' / '리서치_내용.json'
            data_path.parent.mkdir()
            data_path.write_text(json.dumps(DATA, ensure_ascii=False), encoding='utf-8')
            trial = root / '시험'
            self.assertEqual(research_docx.main([str(data_path), '--out', str(trial)]), 0)
            out = trial / DATA['출력']
            with zipfile.ZipFile(out) as z:
                body = z.read('word/document.xml').decode('utf-8')
                headers = b''.join(z.read(n) for n in z.namelist() if n.startswith('word/header'))
            self.assertIn('원문 첫 문단이다.', body)
            self.assertNotIn(b'6010-656', headers)
            self.assertFalse((data_path.parent / '리서치_빌드기록.json').exists())
            self.assertFalse((root / DATA['출력']).exists())


if __name__ == '__main__':
    unittest.main()
