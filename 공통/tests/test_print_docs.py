"""서류 인쇄 도구(공통/scripts/print_docs.py)를 종이 없이 확인한다.

없는 프린터·없는 파일·인쇄하지 않는 형식은 멈추고, PDF 는 면을 그려 부수만큼 한 부씩 모아 보내며 가로 면은 세로 용지에 돌려 낸다.
PDF 경로는 'Microsoft Print to PDF' 로 파일로 인쇄해 결과 PDF 를 연다(그 프린터가 없는 PC에서는 건너뛴다).
한글·Word 경로는 프로그램을 띄워야 하므로 여기서 다루지 않는다(2026. 10. 28. 직접 시험, `공통/운영.md` '인쇄' 4.).
"""
import argparse
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'print_docs', Path(__file__).parents[1] / 'scripts' / 'print_docs.py')
print_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(print_docs)

PDF_PRINTER = 'Microsoft Print to PDF'


def args(printer, files, copies=1, out=None):
    return argparse.Namespace(프린터=printer, 부수=copies, 파일로=out, 파일=[str(f) for f in files])


def printers():
    try:
        return {r['name'] for r in print_docs.printer_rows()}
    except Exception:
        return set()


@unittest.skipUnless(sys.platform == 'win32', 'Windows 인쇄 도구')
class PrintDocsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_unknown_printer_stops(self):
        f = self.dir / 'a.pdf'
        f.write_bytes(b'%PDF-1.4')
        with self.assertRaises(print_docs.PrintError):
            print_docs.cmd_print(args('없는 프린터 이름', [f]))

    @unittest.skipUnless(PDF_PRINTER in printers(), PDF_PRINTER + ' 없음')
    def test_missing_file_and_other_type_stop(self):
        with self.assertRaises(print_docs.PrintError):
            print_docs.cmd_print(args(PDF_PRINTER, [self.dir / '없는.pdf']))
        t = self.dir / '메모.txt'
        t.write_text('글', encoding='utf-8')
        with self.assertRaises(print_docs.PrintError):
            print_docs.cmd_print(args(PDF_PRINTER, [t]))

    @unittest.skipUnless(PDF_PRINTER in printers(), PDF_PRINTER + ' 없음')
    def test_pdf_copies_and_landscape(self):
        import pymupdf
        src = self.dir / '서류.pdf'
        doc = pymupdf.open()
        p = doc.new_page(width=595, height=842)                  # A4 세로, 글자 면
        p.insert_text((72, 100), 'page one', fontsize=20)
        q = doc.new_page(width=842, height=595)                  # A4 가로
        q.insert_text((72, 100), 'page two', fontsize=20)
        doc.save(src)
        out = self.dir / 'out'
        print_docs.cmd_print(args(PDF_PRINTER, [src], copies=2, out=out))
        res = pymupdf.open(out / '서류.pdf.prn', filetype='pdf')
        self.assertEqual(res.page_count, 4)                      # 2면 × 2부
        for page in res:
            self.assertLess(page.rect.width, page.rect.height)   # 모두 세로 용지(가로 면은 돌림)
            self.assertAlmostEqual(page.rect.width / 72 * 25.4, 210, delta=2)


if __name__ == '__main__':
    unittest.main()
