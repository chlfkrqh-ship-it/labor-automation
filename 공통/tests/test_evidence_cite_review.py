"""증거 인용 대조 도구(4_서면작성/scripts/evidence_cite_review.py)를 확인한다.

서면의 인용 괄호를 호증별로 나누는지, 날짜·금액을 같은 꼴로 바꾸어 원문과 맞대는지, 파일 이름의 호증번호
(전자소송 내려받기 '(을104-2_', 앞머리 '갑 제3호증'·'갑14-4_')로 호증 파일을 찾는지, scan·doc 이 끝까지 도는지 본다.
문자인식(Windows)은 돌리지 않는다(--no-ocr).
"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pymupdf

ROOT = Path(__file__).parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ecr = load('evidence_cite_review', '4_서면작성/scripts/evidence_cite_review.py')

MD = """- 다 음 -

1. 원고들의 주장

가. 자금의 흐름

같은 날 배우자는 2018. 2. 8. 삼지에 2,750만 원을 지급하였고(갑 제1호증 계좌거래내역 1면), 원고는 이를 몰랐습니다.

나아가 배우자는 1억 3,000만 원을 받았습니다(을 제104호증의2 계좌거래내역 2면, 갑 제2호증 매매계약서).

[갑 제1호증 계좌거래내역]

참고로 위 자료는 을 제93·94·97호증과 같습니다(을 제93·94·97호증).

---

① [확인 필요 사항]
1. 하단은 세지 않습니다(갑 제9호증 1면).
"""


def make_pdf(path: Path, pages):
    d = pymupdf.open()
    for lines in pages:
        p = d.new_page()
        y = 72
        for line in lines:
            p.insert_text((50, y), line, fontsize=10)
            y += 14
    d.save(path)


class CanonTest(unittest.TestCase):
    def test_dates_and_amounts_meet(self):
        self.assertIn(ecr.canon('2018. 2. 8.'), ecr.canon('20180208 8:21:20'))
        self.assertIn(ecr.canon('2018. 2. 8.'), ecr.canon('2018-02-08 08:21'))
        self.assertEqual(ecr.canon('2,750만 원'), '27500000')
        self.assertEqual(ecr.canon('1억 3,000만 원'), '130000000')
        self.assertEqual(ecr.canon('24,091,631원'), '24091631')
        self.assertIn(ecr.canon('2,750만 원'), ecr.canon('모바일 27,500,000 - 삼지'))

    def test_keys_of_lists_date_amount_quote(self):
        kinds = [k[0] for k in ecr.keys_of("2018. 3. 9. '손실보전금' 명목으로 600만 원")]
        self.assertEqual(sorted(kinds), ['금액', '날짜', '따옴표'])

    def test_quality_tells_garbage(self):
        self.assertGreater(ecr.quality('2023-03-19 20:41 서동근 800,000'), 0.6)
        self.assertLess(ecr.quality('al olnl \\ BtEti?i*l\'gE:r .l t)\'l I o FnJ'), 0.3)


class ParseTest(unittest.TestCase):
    def test_citations_split_and_spans(self):
        rows = ecr.parse_citations(MD)
        keys = [r['key'] for r in rows]
        self.assertEqual(keys, ['갑1', '을104-2', '갑2', '갑1', '을93', '을94', '을97'])
        first = rows[0]
        self.assertEqual(first['pages'], ['1'])
        self.assertTrue(first['span'].endswith('2,750만 원을 지급하였고'))      # 괄호 바로 앞 구절까지만
        self.assertNotIn('몰랐습니다', first['span'])
        self.assertEqual(rows[1]['pages'], ['2'])
        self.assertEqual(rows[2]['pages'], [])
        self.assertTrue(rows[3]['caption'])
        self.assertNotIn('갑9', keys)                                        # '---' 아래는 세지 않는다

    def test_headings(self):
        self.assertEqual([h for _, h in ecr.headings(MD)], ['1. 원고들의 주장', '가. 자금의 흐름'])


class ExhibitTest(unittest.TestCase):
    def test_file_names(self):
        self.assertEqual(ecr.file_key('2025나21206_080001_준비서면_서증_계좌_(을104-2_구교웅 관련 계좌)_피고.pdf'), '을104-2')
        self.assertEqual(ecr.file_key('갑 제32호증 인사관리규정.pdf'), '갑32')
        self.assertEqual(ecr.file_key('갑 제14호증의4 거래내역.pdf'), '갑14-4')
        self.assertEqual(ecr.file_key('갑14-4_부친 계좌.pdf'), '갑14-4')
        self.assertEqual(ecr.file_key('을나13의2_징계.pdf'), '을나13-2')
        self.assertIsNone(ecr.file_key('증거목록.pdf'))

    def test_round_original_first_and_sub_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / '사건A'
            r1, r2 = case / '라운드1', case / '라운드2'
            for d in (r1 / '우리증거', r2 / '우리증거', r2 / '출력' / '제출' / '증거'):
                d.mkdir(parents=True)
            for p in (r1 / '우리증거' / '갑 제1호증 옛판.pdf', r2 / '우리증거' / '갑 제1호증 계좌.pdf',
                      r2 / '출력' / '제출' / '증거' / '갑 제1호증_계좌.pdf', r1 / '우리증거' / '갑2-1_계약서.pdf'):
                make_pdf(p, [['x']])
            found = ecr.find_exhibits(case.resolve(), r2.resolve())
            self.assertEqual(ecr.lookup(found, '갑1').name, '갑 제1호증 계좌.pdf')
            self.assertEqual(ecr.lookup(found, '갑2').name, '갑2-1_계약서.pdf')
            self.assertIsNone(ecr.lookup(found, '갑3'))


class EndToEndTest(unittest.TestCase):
    def test_scan_then_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            rnd = Path(tmp) / '사건B' / '라운드1'
            (rnd / '출력').mkdir(parents=True)
            (rnd / '우리증거').mkdir()
            (rnd / '상대증거').mkdir()
            md = rnd / '출력' / '서면초안.md'
            md.write_text(MD, encoding='utf-8')
            make_pdf(rnd / '우리증거' / '갑 제1호증 계좌거래내역.pdf',
                     [['20180207 12:22:09 Mobile - 24,091,631 JMS', '20180208 8:21:20 Mobile 27,500,000 - SAMJI',
                       '20180208 17:29:40 CD 100,900 -']])
            make_pdf(rnd / '상대증거' / '서증_(을104-2_계좌)_피고.pdf',
                     [['page one'], ['20180309 15:16:15 IB - 130,000,000 KGW', '20180309 15:46:41 Mobile 30,000,000']])
            make_pdf(rnd / '우리증거' / '갑 제2호증 매매계약서.pdf', [['contract 170,000,000']])
            self.assertEqual(ecr.main(['scan', str(md), '--no-ocr']), 1)       # 을93 등 파일이 없어 1
            out = rnd / '작업' / '증거인용검토'
            report = json.loads((out / 'review.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report), 7)
            first = report[0]
            self.assertIn('날짜:2018. 2. 8.', first['found'])
            self.assertIn('금액:2,750만 원', first['found'])
            self.assertEqual(first['windows'][0]['page'], 1)
            self.assertTrue(Path(first['crop']).is_file())
            self.assertTrue(any('27,500,000' in row for row in first['rows']))   # 글자층 표 줄을 옮겨 적는다
            self.assertEqual(report[1]['windows'][0]['page'], 2)
            self.assertIn('금액:1억 3,000만 원', report[1]['found'])
            self.assertIsNone(report[4]['file'])
            notes = {'_요약': ['시험'], '1': ['일치', '2. 8. 삼지 2,750만 원'], '2': ['고침', '면 표시 고침'],
                     'crops': {'2': [['을104-2', 2, ['20180309 15:16']]]}}
            (out / 'notes.json').write_text(json.dumps(notes, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(ecr.main(['doc', str(md), '--no-pdf', '--no-ocr']), 0)
            docx_path = out / f'{ecr.OUT_NAME}.docx'
            self.assertTrue(docx_path.is_file())
            import docx
            text = '\n'.join(p.text for p in docx.Document(docx_path).paragraphs)
            self.assertIn('[1] ', text)
            self.assertIn('— 일치', text)
            self.assertIn('— 고침', text)
            self.assertIn('— 확인 전', text)
            self.assertIn('을104-2 2면 | 20180309 15:16:15', text)        # 지정한 줄이 원본 글자로 들어간다


class PrintedPageTest(unittest.TestCase):
    def test_report_page_number_printed_on_page(self):
        """'220면'이 보고서에 인쇄된 쪽 번호이면 그 쪽이 인쇄된 PDF 면에서 찾는다(감사보고서 '- 220 -' = PDF 226면)."""
        with tempfile.TemporaryDirectory() as tmp:
            rnd = Path(tmp) / '사건C' / '라운드1'
            (rnd / '출력').mkdir(parents=True)
            (rnd / '상대증거').mkdir()
            md = rnd / '출력' / '서면초안.md'
            md.write_text('감사원은 2023. 3. 9. 1,000만 원을 기준으로 분석하였습니다(을 제12호증의2 감사보고서 2면).\n',
                          encoding='utf-8')
            make_pdf(rnd / '상대증거' / '을 제12호증의2 감사보고서.pdf',
                     [['- 0 -', 'cover cover cover'], ['- 1 -', 'nothing here at all, unrelated text'],
                      ['- 2 -', 'standard 20230309 10,000,000 analysis of transfers']])
            ecr.main(['scan', str(md), '--no-ocr'])
            report = json.loads((rnd / '작업' / '증거인용검토' / 'review.json').read_text(encoding='utf-8'))
            self.assertEqual(report[0]['windows'][0]['page'], 3)
            self.assertIn('인쇄 쪽 2', report[0]['windows'][0]['src'])

    def test_brief_page_numbers_with_and_without_cover(self):
        """서면 PDF 의 인쇄 쪽 번호: 표지 있는 서면은 표지 None·본문 1부터, 표지 없는 소장 청구원인은 첫 면부터 1."""
        with tempfile.TemporaryDirectory() as tmp:
            cover, plain = Path(tmp) / 'cover.pdf', Path(tmp) / 'plain.pdf'
            make_pdf(cover, [['cover cover'], ['- 1 -', 'body text'], ['body text', 'more text', '- 2 -']])
            make_pdf(plain, [['1', 'body text 300,000,000'], ['2', 'body text']])
            self.assertEqual(ecr.brief_page_numbers(cover), [None, 1, 2])
            self.assertEqual(ecr.brief_page_numbers(plain), [1, 2])


if __name__ == '__main__':
    unittest.main()
