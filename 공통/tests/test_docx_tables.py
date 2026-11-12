"""docx_tables.py — 글이 든 표 칸이 쪽 오른쪽 여백 밖이나 종이 밖에 놓였는지 본다.

2026. 11. 13. `/하자보완`: 서면 템플릿 프레임 2면 사건 표의 빈 셋째 칸(표 너비 17949) 때문에 11. 12. 이승민 준비서면(2)의
사건번호·당사자가 쪽 밖으로 잘렸고, 병합 뒤 점검과 관문 DOCX 검사가 지나보냈다. 추적되는 표준양식.docx 를 임시 폴더에서 고쳐 쓴다.
"""
import copy
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import docx
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.table import Table

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / '4_서면작성' / 'scripts'))
import docx_tables  # noqa: E402

TEMPLATE = ROOT / '4_서면작성' / 'templates' / '표준양식.docx'


def 사건표들(d):
    out = []
    for el in d.element.body.iter(qn('w:tbl')):
        tb = Table(el, d)
        if tb.rows and tb.rows[0].cells[0].text.replace(' ', '') == '사건':
            out.append(tb)
    return out


def 셋째_칸(tb, 글=True):
    """템플릿 결함처럼 격자에 8253 칸을 하나 더 두고 행마다 칸을 붙인다. 글이면 둘째 칸의 값을 셋째 칸으로 옮긴다."""
    tbl = tb._tbl
    grid = tbl.find(qn('w:tblGrid'))
    grid.append(copy.deepcopy(grid.findall(qn('w:gridCol'))[-1]))
    tbl.find(qn('w:tblPr')).find(qn('w:tblW')).set(qn('w:w'), '17949')
    for tr in tbl.findall(qn('w:tr')):
        tcs = tr.findall(qn('w:tc'))
        new = copy.deepcopy(tcs[1])
        if not 글:
            for t in new.iter(qn('w:t')):
                t.text = ''
        else:
            for t in tcs[1].iter(qn('w:t')):
                t.text = ''
        tr.append(new)


class DocxTablesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, d, name):
        p = self.dir / name
        d.save(str(p))
        return p

    def test_standard_form_passes(self):
        self.assertEqual(docx_tables.넘친_칸(TEMPLATE), [])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(docx_tables.main([str(TEMPLATE)]), 0)

    def test_value_in_stray_third_column_is_caught(self):
        d = docx.Document(str(TEMPLATE))
        표 = 사건표들(d)[-1]                        # 본문 첫 면(2면)의 사건 표
        셋째_칸(표, 글=True)
        p = self.save(d, '잘림.docx')
        probs = docx_tables.넘친_칸(p)
        self.assertEqual(len(probs), 4, probs)       # 사건·원고·피고·피고보조참가인 네 줄
        self.assertTrue(all('3칸' in x and '밖' in x for x in probs), probs)
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(docx_tables.main([str(p)]), 1)
            self.assertEqual(docx_tables.check(p), 1)          # 병합 뒤 점검(docx_merge._final_check)이 부르는 꼴
        self.assertIn('표 칸 넘침 4건', out.getvalue())

    def test_empty_stray_third_column_is_not_caught(self):
        """빈 칸은 쪽 밖에 있어도 보이지 않는다. 그전에 템플릿으로 만든 서면 261개가 이 꼴이고 값은 둘째 칸에 있다."""
        d = docx.Document(str(TEMPLATE))
        셋째_칸(사건표들(d)[-1], 글=False)
        self.assertEqual(docx_tables.넘친_칸(self.save(d, '빈칸.docx')), [])

    def test_extra_cell_beyond_the_grid_is_caught(self):
        """격자는 두 칸인데 한 행에만 칸을 덧붙이면 그 칸은 오른쪽 여백 밖에서 시작한다(2026. 11. 2. OES 답변서(2) 중간 판의 '담당노무사')."""
        d = docx.Document(str(TEMPLATE))
        tb = 사건표들(d)[-1]
        tr = tb._tbl.findall(qn('w:tr'))[0]
        new = copy.deepcopy(tr.findall(qn('w:tc'))[1])
        for t in new.iter(qn('w:t')):
            t.text = '담당노무사 최 락 보'
        tr.append(new)
        probs = docx_tables.넘친_칸(self.save(d, '덧칸.docx'))
        self.assertEqual(len(probs), 1, probs)
        self.assertIn('담당노무사', probs[0])

    def test_wide_table_in_a_landscape_section_passes(self):
        """가로 구역의 넓은 표는 그 구역의 쪽 크기로 본다(세로 구역 기준으로 막지 않는다)."""
        d = docx.Document()
        sec = d.sections[0]
        sec.left_margin = sec.right_margin = Cm(2)
        d.add_paragraph('세로 면')
        new = d.add_section()
        new.orientation = WD_ORIENT.LANDSCAPE
        new.page_width, new.page_height = sec.page_height, sec.page_width
        new.left_margin = new.right_margin = Cm(2)
        tb = d.add_table(rows=1, cols=3)
        for i, c in enumerate(tb.rows[0].cells):
            c.width = Cm(8)
            c.text = f'칸{i + 1}'
        for gc in tb._tbl.find(qn('w:tblGrid')).findall(qn('w:gridCol')):
            gc.set(qn('w:w'), str(int(Cm(8).twips)))
        p = self.save(d, '가로.docx')
        self.assertEqual(docx_tables.넘친_칸(p), [])
        # 같은 표를 세로 구역에 두면 셋째 칸(16cm 에서 시작)이 글 폭(약 17cm) 안에서 시작해도 종이 밖(19cm 넘음)으로 나간다
        d2 = docx.Document()
        s2 = d2.sections[0]
        s2.left_margin = s2.right_margin = Cm(2)
        tb2 = d2.add_table(rows=1, cols=3)
        for i, c in enumerate(tb2.rows[0].cells):
            c.text = f'칸{i + 1}'
        for gc in tb2._tbl.find(qn('w:tblGrid')).findall(qn('w:gridCol')):
            gc.set(qn('w:w'), str(int(Cm(8).twips)))
        probs = docx_tables.넘친_칸(self.save(d2, '세로.docx'))
        self.assertEqual(len(probs), 1, probs)
        self.assertIn('칸3', probs[0])

    def test_unreadable_file_is_reported(self):
        p = self.dir / '가짜.docx'
        p.write_bytes(b'PK')
        probs = docx_tables.넘친_칸(p)
        self.assertEqual(len(probs), 1)
        self.assertIn('읽지 못했다', probs[0])


if __name__ == '__main__':
    unittest.main()
