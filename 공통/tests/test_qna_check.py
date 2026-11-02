"""심문회의 예상 질의답변의 모양 규칙 검사(4_서면작성/scripts/qna_check.py)를 확인한다.

2026. 11. 2. 담당 노무사가 첫 판에서 지적한 제목·절·표시·회색 메모·정렬을 잡는지 본다(`.claude/commands/예상질의.md`).
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import docx
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import RGBColor

spec = importlib.util.spec_from_file_location('qna_check', Path(__file__).parents[2] / '4_서면작성/scripts/qna_check.py')
qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)


def memo(document, text):
    r = document.add_paragraph().add_run(text)
    r.font.color.rgb = RGBColor(0x59, 0x59, 0x59)


class QnaCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / '(가나) 심문회의 예상 질의답변_초안.docx'

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, title='제 목:\t가나 심문회의(2026.\xa011.\xa09.) 예상 질의 및 답변', head='조직 및 지시 계통', answer='결재선은 표와 같습니다.',
              note='[질의 이유] 조직도는 제출된 바 없고, 노동위원회는 심문회의 시 결재선을 물어보기도 합니다.', left=False):
        d = docx.Document()
        d.add_paragraph(title)
        d.styles.add_style('1.', WD_STYLE_TYPE.PARAGRAPH)
        d.add_paragraph(head, style='1.')
        p = d.add_paragraph(answer)
        if left:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        memo(d, note)
        d.save(self.path)
        return qc.check(self.path)

    def test_clean_document_passes(self):
        self.assertEqual(self.build(), [])

    def test_title_and_left_out_sections(self):
        self.assertIn('제목', self.build(title='제 목:\t가나 심문회의 예상 질의와 답변')[0])
        self.assertIn('넣지 않는 절', self.build(head='판정 이후의 조치')[0])

    def test_who_asks_and_who_answers_are_not_marked(self):
        self.assertIn('표시', self.build(answer='(사용자위원) 대리인이 답하겠습니다. 결재선은 표와 같습니다.')[0])

    def test_grey_memo_rules(self):
        self.assertIn('[질의 이유]', self.build(note='조직도는 제출된 바 없습니다.')[0])
        self.assertTrue(any('가져오십시오' in s for s in self.build(note='[질의 이유] 조직도를 가져오십시오.')))
        self.assertTrue(any('불리한 대목' in s for s in self.build(note='[질의 이유] 호증의 불리한 대목입니다.')))
        self.assertTrue(any('적혀' in s for s in self.build(note='[질의 이유] 호증에 적혀 있습니다.')))

    def test_body_must_not_be_left_aligned(self):
        self.assertIn('왼쪽 정렬', self.build(answer='결재선은 표와 같으며 부서장과 그룹장, 파트장으로 이어지는 것으로 정리되어 있습니다.', left=True)[0])


if __name__ == '__main__':
    unittest.main()
