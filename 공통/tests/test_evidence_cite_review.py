"""증거 인용 대조 도구(4_서면작성/scripts/evidence_cite_review.py)를 확인한다.

서면의 인용 괄호를 호증별로 나누는지, 날짜·금액을 같은 꼴로 바꾸어 원문과 맞대는지, 파일 이름의 호증번호
(전자소송 내려받기 '(을104-2_', 앞머리 '갑 제3호증'·'갑14-4_')로 호증 파일을 찾는지, scan·doc 이 끝까지 도는지 본다.
문자인식 결과를 호증 파일의 해시 표지로 묶는지도 본다(OcrCacheMarkTest).
문자인식(Windows)은 돌리지 않는다(--no-ocr). 돌려야 하는 시험은 `run_windows_ocr` 를 흉내 낸다.
"""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import pymupdf

ROOT = Path(__file__).parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ecr = load('evidence_cite_review', '4_서면작성/scripts/evidence_cite_review.py')
er = load('evidence_read', '4_서면작성/scripts/evidence_read.py')        # 이 도구의 문자인식 결과를 다시 쓰는 전 면 읽기

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


def scan_pdf(path: Path, n: int, 판: str):
    """글자층이 없는 스캔 면 n 개. 판을 달리하면 바이트가 다른 파일(같은 번호에 넣은 다른 스캔본)이 된다."""
    d = pymupdf.open()
    for _ in range(n):
        d.new_page()
    d.set_metadata({'title': 판})
    d.save(path)
    d.close()


def ocr_cache(folder: Path, pages: dict, mark=None):
    """앞서 만든 문자인식 결과(pages.json). pages: {면: 글}. mark 가 있으면 표지를 붙이고, 없으면 표지를 뗀다."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'pages.json').write_text(json.dumps(
        {str(no): {'png': f'p{no:03d}.png', 'units': [[t, [40, 60, 940, 100]]], 'src': '문자인식'} for no, t in pages.items()},
        ensure_ascii=False), encoding='utf-8')
    if mark is None:
        (folder / ecr.OCR_MARK).unlink(missing_ok=True)
    else:
        (folder / ecr.OCR_MARK).write_text(mark, encoding='utf-8')


def ocr_json(folder: Path, files: dict, mark=None):
    """`ocr_win.ps1` 이 낸 꼴의 결과(ocr.json). files: {그림 이름: 글}. 호증키 폴더의 옛 판과 '<호증키>_p01.png' 묶음이 이 꼴이다."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'ocr.json').write_text(json.dumps(
        [{'file': n, 'lines': [{'t': t, 'x': 40, 'y': 60, 'w': 900, 'h': 40}]} for n, t in files.items()], ensure_ascii=False),
        encoding='utf-8')
    if mark is not None:
        (folder / ecr.OCR_MARK).write_text(mark, encoding='utf-8')


def 흉내_문자인식(글: dict, 부름: list):
    """Windows 문자인식(`run_windows_ocr`)을 흉내 낸다. 폴더의 그림마다 지금의 글['t'] 한 줄을 읽은 것으로 낸다."""
    def run(folder):
        부름.append(sorted(p.name for p in Path(folder).glob('*.png')))
        return [{'file': n, 'lines': [{'t': 글['t'], 'x': 40, 'y': 60, 'w': 900, 'h': 40}]} for n in 부름[-1]]
    return run


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

    def test_every_page_of_a_listed_citation_is_read(self):
        """2026. 11. 3. '3·5면'·'2, 4면'의 앞 면을 버려 증거 인용 대조가 그 면을 보여 주지 않았다(쟁점 낱말 도구도 같은 날 고침)."""
        면 = lambda 괄호: [(r['key'], r['pages']) for r in ecr.parse_citations('- 다 음 -\n\n가. 문장입니다' + 괄호 + '.\n')]
        self.assertEqual(면('(사 제6호증 3·5면)'), [('사6', ['3', '5'])])
        self.assertEqual(면('(갑 제1호증 2, 4면)'), [('갑1', ['2', '4'])])
        self.assertEqual(면('(을 제110호증의2 5~7면, 9면, 11면)'), [('을110-2', ['5~7', '9', '11'])])
        self.assertEqual(면('(을 제110호증의2 3·5~7면)'), [('을110-2', ['3', '5~7'])])
        self.assertEqual(면('(갑 제1호증 제3면)'), [('갑1', ['3'])])
        self.assertEqual(면('(을 제5호증의3, 4면)'), [('을5-3', ['4'])])                  # 의3 의 3 은 면이 아니다
        self.assertEqual(면('(을 제1호증 2023. 3. 5.자 공문 1,000,000원 2면)'), [('을1', ['2'])])   # 날짜·금액은 면이 아니다
        self.assertEqual(ecr.expand_pages(['3', '5~7'], 10), [3, 5, 6, 7])

    def test_grouped_exhibits_and_page_ranges_are_expanded(self):
        """'내지'·'및'으로 묶은 호증과 가지번호, '면 내지 면'을 하나하나 펼친다. 2026. 11. 3. 문체 지침의 본보기 '313면 내지 321면'을
        313면으로만, '을 제103호증의1 내지 17 각'을 의1로만 읽고, '갑 제1 내지 5호증'은 통째로, '갑 제1호증 및 갑 제2호증'의 갑 제2호증은
        빠뜨려 증거 인용 대조가 그 호증·면을 보여 주지 않았다."""
        def pages(s):
            return [(r['key'], r['pages']) for r in ecr.parse_citations('가. 사실입니다(' + s + ').')]
        self.assertEqual(pages('갑 제18호증 근로복지공단 의견서 313면 내지 321면'), [('갑18', ['313~321'])])
        self.assertEqual(ecr.expand_pages(['313~321'], 400), list(range(313, 322)))
        self.assertEqual(pages('갑 제3호증 3 내지 5면'), [('갑3', ['3~5'])])
        self.assertEqual(pages('갑 제3호증 3∼5면'), [('갑3', ['3~5'])])
        self.assertEqual(pages('갑 제3호증 5면 및 9면'), [('갑3', ['5', '9'])])
        self.assertEqual(pages('을 제103호증의1 내지 17 각 출석 및 추가 서면자료 제출 현황'),
                         [(f'을103-{i}', []) for i in range(1, 18)])
        self.assertEqual(pages('을 제103호증의1 내지 의3'), [(f'을103-{i}', []) for i in (1, 2, 3)])
        self.assertEqual(pages('을 제103호증의1, 2'), [('을103-1', []), ('을103-2', [])])
        self.assertEqual(pages('사 제67호증의1·2'), [('사67-1', []), ('사67-2', [])])
        for s in ('갑 제1 내지 5호증', '갑 제1호증 내지 제5호증', '갑 제1~5호증'):
            self.assertEqual(pages(s), [(f'갑{i}', []) for i in range(1, 6)], s)
        self.assertEqual(pages('갑 제31호증 ~ 갑 제33호증'), [('갑31', []), ('갑32', []), ('갑33', [])])
        self.assertEqual(pages('갑 제1호증 및 갑 제2호증'), [('갑1', []), ('갑2', [])])
        self.assertEqual(pages('갑 제1호증 및 제2호증'), [('갑1', []), ('갑2', [])])
        self.assertEqual(pages('갑 제1호증과 을 제2호증 3면'), [('갑1', []), ('을2', ['3'])])
        self.assertEqual(pages('갑 제1호증, 갑 제2호증 5면'), [('갑1', []), ('갑2', ['5'])])     # 접두어를 다시 적은 나열은 면이 따로
        self.assertEqual(pages('을나 제1호증의 2'), [('을나1-2', [])])
        self.assertEqual(pages('갑 제1-1호증 2면'), [('갑1-1', ['2'])])
        self.assertEqual(pages('갑 제5호증의1, 2023. 3. 5.자 공문'), [('갑5-1', [])])          # 날짜는 가지번호가 아니다
        self.assertEqual(pages('갑 제5호증의1, 2,750만 원 영수증'), [('갑5-1', [])])           # 금액도
        self.assertEqual(pages('갑 제5호증의 기재'), [('갑5', [])])
        self.assertEqual(pages('원고가 낸 것을 제2호증으로 보면 갑 제1호증'), [('갑1', [])])  # '것을'의 '을'은 조사이다

    def test_pages_are_only_those_right_after_the_exhibit(self):
        """호증 표시 바로 뒤의 면 표시만 그 호증의 면이다(`evidence_words.py` 와 같은 규칙). 2026. 11. 3. 괄호 안의 'N면'을 모두
        그 호증의 면으로 읽어 '사진 2면, 제1심 판결문 13면'의 13면까지 맞대던 것을 바꾸었다."""
        def pages(s):
            return [(r['key'], r['pages']) for r in ecr.parse_citations('가. 사실입니다(' + s + ').')]
        self.assertEqual(pages('갑 제18호증 현수막 사진 2면, 제1심 판결문 13면'), [('갑18', ['2'])])
        self.assertEqual(pages('을 제110호증의2 5~7면, 9면, 11면, 을 제47호증의1 5면'),
                         [('을110-2', ['5~7', '9', '11']), ('을47-1', ['5'])])
        self.assertEqual(pages('사 제6호증 2, 4면'), [('사6', ['2', '4'])])
        self.assertEqual(pages('갑 제19호증의4 2025. 1. 8. 조합활동 방해영상3, 제1심 판결문 11면'), [('갑19-4', [])])
        self.assertEqual(pages('갑 제5호증 2,750만 원 영수증 제2면'), [('갑5', ['2'])])
        self.assertEqual(pages('갑 제8호증 제3조 제2호, 15면'), [('갑8', ['15'])])            # 면 바로 앞의 쉼표는 넘는다(박준선)
        self.assertEqual(pages('을나 제13호증 협정서 제1항, 제1심 판결문 12~13면'), [('을나13', [])])
        self.assertEqual(ecr.expand_pages(['5~7', '9'], 30), [5, 6, 7, 9])

    def test_headings(self):
        self.assertEqual([h for _, h in ecr.headings(MD)], ['1. 원고들의 주장', '가. 자금의 흐름'])


class SplitDraftTest(unittest.TestCase):
    def test_each_split_draft_has_its_own_review_folder(self):
        """서면을 나눈 라운드에서 뒤에 돌린 서면이 앞 서면의 대조와 판정을 덮지 않는다(2026. 11. 3.)."""
        with tempfile.TemporaryDirectory() as d:
            rnd = Path(d) / '라운드1'
            (rnd / '출력').mkdir(parents=True)
            a, b = rnd / '출력' / '서면초안_림프종.md', rnd / '출력' / '서면초안_우울증.md'
            for p in (a, b):
                p.write_text('본문\n', encoding='utf-8')
            (rnd / '출력' / '서면초안_본문.md').write_text('조각\n', encoding='utf-8')
            self.assertEqual(ecr.drafts_of(rnd), [a, b])
            self.assertEqual(ecr.review_dir(a).name, '증거인용검토_림프종')
            self.assertEqual(ecr.review_dir(b).name, '증거인용검토_우울증')
            one = rnd / '출력' / '서면초안.md'
            one.write_text('본문\n', encoding='utf-8')
            self.assertEqual(ecr.drafts_of(rnd), [one])                 # 서면초안.md 가 있으면 그 하나이다
            self.assertEqual(ecr.review_dir(one).name, '증거인용검토')


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


class CarryJudgementsTest(unittest.TestCase):
    """판정은 순번이 아니라 인용에 붙는다. 2026. 11. 3. 초안 중간에 인용이 끼면 다시 대조할 때 뒤 판정이 한 칸씩 밀려 다른 인용에 붙었다."""

    def test_judgements_follow_their_citation_and_changed_ones_are_cleared(self):
        with tempfile.TemporaryDirectory() as tmp:
            rnd = Path(tmp) / '사건B' / '라운드1'
            for d in ('출력', '우리증거', '상대증거'):
                (rnd / d).mkdir(parents=True)
            make_pdf(rnd / '우리증거' / '갑 제1호증 계좌거래내역.pdf', [['20180208 8:21:20 Mobile 27,500,000 - SAMJI']])
            make_pdf(rnd / '우리증거' / '갑 제2호증 매매계약서.pdf', [['contract 170,000,000']])
            make_pdf(rnd / '상대증거' / '서증_(을104-2_계좌)_피고.pdf', [['page one'], ['20180309 15:16:15 IB - 130,000,000 KGW']])
            md = rnd / '출력' / '서면초안.md'
            앞 = '- 다 음 -\n\n'
            가 = '가. 첫째 사실입니다(갑 제1호증 계좌거래내역 1면).\n\n'
            나 = '나. 둘째 사실입니다(갑 제2호증 매매계약서).\n'
            md.write_text(앞 + 가 + 나, encoding='utf-8')
            ecr.main(['scan', str(md), '--no-ocr'])
            out = rnd / '작업' / '증거인용검토'
            (out / 'notes.json').write_text(json.dumps({'_요약': ['시험'], '1': ['일치', '가'], '2': ['고침', '나'], 'crops': {'2': [['갑2', 1, ['contract']]]}},
                                                       ensure_ascii=False), encoding='utf-8')
            새 = '가-1. 끼운 사실입니다(을 제104호증의2 계좌거래내역 2면).\n\n'
            md.write_text(앞 + 새 + 가 + 나, encoding='utf-8')                     # 앞에 인용이 끼었다
            ecr.main(['scan', str(md), '--no-ocr'])
            notes = json.loads((out / 'notes.json').read_text(encoding='utf-8'))
            self.assertNotIn('1', notes)                                             # 새 인용은 판정이 없다
            self.assertEqual(notes['2'], ['일치', '가'])
            self.assertEqual(notes['3'], ['고침', '나'])
            self.assertEqual(notes['crops'], {'3': [['갑2', 1, ['contract']]]})
            self.assertEqual(notes['_요약'], ['시험'])
            md.write_text(앞 + 새 + 가.replace('첫째 사실입니다', '첫째 사실을 고쳤습니다') + 나, encoding='utf-8')
            make_pdf(rnd / '우리증거' / '갑 제2호증 매매계약서.pdf', [['contract 180,000,000']])      # 호증 파일이 바뀌었다
            ecr.main(['scan', str(md), '--no-ocr'])
            notes = json.loads((out / 'notes.json').read_text(encoding='utf-8'))
            self.assertEqual([k for k in notes if k.isdigit()], [])                 # 문장을 고친 인용, 파일이 바뀐 인용은 다시 판정한다
            self.assertNotIn('crops', notes)

    def test_judgements_are_set_aside_when_the_earlier_scan_is_gone(self):
        """앞선 대조(review.json)가 없거나 깨지면 판정을 어느 인용에 옮길지 모르므로 순번대로 두지 않고 옮겨 둔 뒤 비운다."""
        with tempfile.TemporaryDirectory() as tmp:
            rnd = Path(tmp) / '사건B' / '라운드1'
            for d in ('출력', '우리증거'):
                (rnd / d).mkdir(parents=True)
            make_pdf(rnd / '우리증거' / '갑 제1호증 계좌거래내역.pdf', [['20180208 8:21:20 Mobile 27,500,000 - SAMJI']])
            md = rnd / '출력' / '서면초안.md'
            md.write_text('- 다 음 -\n\n가. 첫째 사실입니다(갑 제1호증 계좌거래내역 1면).\n', encoding='utf-8')
            ecr.main(['scan', str(md), '--no-ocr'])
            out = rnd / '작업' / '증거인용검토'
            판정 = {'_요약': ['시험'], '1': ['일치', '가'], 'crops': {'1': [['갑1', 1, ['SAMJI']]]}}
            for 깨기 in (lambda p: p.unlink(), lambda p: p.write_text('{깨짐', encoding='utf-8')):
                (out / 'notes.json').write_text(json.dumps(판정, ensure_ascii=False), encoding='utf-8')
                깨기(out / 'review.json')
                ecr.main(['scan', str(md), '--no-ocr'])
                self.assertEqual(json.loads((out / 'notes.json').read_text(encoding='utf-8')), {'_요약': ['시험']})
                self.assertEqual(json.loads((out / 'notes_옮기지못함.json').read_text(encoding='utf-8')), 판정)


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


class OcrCacheMarkTest(unittest.TestCase):
    """문자인식 결과는 그것을 만든 호증 파일의 해시 표지(파일해시.txt)로 묶는다. 2026. 11. 3. 전에는 호증키로만 묶어, 같은 번호에
    다른 PDF(더 나은 스캔본 등)를 넣으면 앞 파일의 글을 새 파일의 것으로 썼고, 전 면 읽기의 면별 글에도 들어갈 수 있었다.
    표지가 없는 옛 결과는 쓰던 대로 쓴다(다시 문자인식하면 PC에서 오래 걸린다). 문자인식은 Windows 에서만 돌므로 흉내 낸다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / '갑 제1호증 스캔.pdf'
        scan_pdf(self.pdf, 4, '새 스캔본')
        self.review = self.root / '라운드1' / '작업' / '증거인용검토'
        self.own = self.review / 'ocr' / '갑1'                                   # 자기 캐시
        self.글, self.부름 = {'t': '새 파일을 읽은 문자인식 글입니다'}, []
        p = mock.patch.object(ecr, 'run_windows_ocr', 흉내_문자인식(self.글, self.부름))
        p.start()
        self.addCleanup(p.stop)

    def read(self, pages, **kw):
        """호증을 읽고 닫는다. 돌려주는 것: ({면: (출처, 글)}, 쓰지 않은 결과 폴더)."""
        ex = ecr.Exhibit('갑1', self.pdf, self.review, **kw)
        try:
            ex.prepare(pages)
            return {no: (e['src'], ' '.join(t for t, _ in e['units'])) for no, e in ex.pages.items()}, ex.stale
        finally:
            ex.close()

    def test_results_marked_for_another_file_are_not_used(self):
        """표지가 지금 파일과 다른 결과는 쓰지 않는다. --ocr-map 폴더, --ocr-dir 의 호증키 폴더와 묶음, 자기 캐시가 모두 그렇다."""
        옛 = 'deadbeef0000'
        ocr_cache(self.own, {1: '앞 파일의 글(자기 캐시)'}, 옛)
        ocr_cache(self.root / '넘긴결과' / '갑1', {2: '앞 파일의 글(호증키 폴더)'}, 옛)
        ocr_cache(self.root / '지정', {3: '앞 파일의 글(--ocr-map)'}, 옛)
        ocr_json(self.root / '묶음', {'갑1_p04.png': '앞 파일의 글(묶음)', '을2_p01.png': '다른 호증의 글'}, f'갑1 {옛}\n을2 0123456789ab\n')
        kw = dict(ocr_dirs=[self.root / '넘긴결과', self.root / '묶음'], ocr_map={'갑1': str(self.root / '지정')})
        면, 안씀 = self.read([1, 2, 3, 4], use_ocr=False, **kw)
        self.assertEqual(면, {no: ('글자 없음', '') for no in (1, 2, 3, 4)})
        self.assertEqual(len(안씀), 4)
        self.assertFalse(self.own.exists())                                      # 자기 캐시는 지운다
        for f in (self.root / '넘긴결과' / '갑1' / 'pages.json', self.root / '지정' / 'pages.json', self.root / '묶음' / 'ocr.json'):
            self.assertTrue(f.is_file(), f)                                       # 넘겨받은 결과는 건드리지 않는다
        면, _ = self.read([1, 2, 3, 4], **kw)                                     # 문자인식을 돌리면 지금 파일을 읽는다
        self.assertEqual(면, {no: ('문자인식', '새 파일을 읽은 문자인식 글입니다') for no in (1, 2, 3, 4)})
        self.assertEqual(self.부름, [['p001.png', 'p002.png', 'p003.png', 'p004.png']])

    def test_results_without_mark_are_used_as_before(self):
        """표지가 없는 옛 결과는 다시 문자인식하지 않고 쓴다. 표지가 지금 파일과 같은 결과도 쓴다. 표지는 자기 캐시에만 붙인다."""
        ocr_cache(self.own, {1: '옛 자기 캐시의 글'})
        ocr_cache(self.root / '넘긴결과' / '갑1', {2: '옛 호증키 폴더의 글'})
        ocr_json(self.root / '지정', {'p003.png': '옛 판 ocr.json 의 글'})
        ocr_json(self.root / '묶음', {'갑1_p04.png': '표지가 맞는 묶음의 글'}, f'을2 deadbeef0000\n갑1 {ecr.hash_file(self.pdf)}\n')
        면, 안씀 = self.read([1, 2, 3, 4], ocr_dirs=[self.root / '넘긴결과', self.root / '묶음'], ocr_map={'갑1': str(self.root / '지정')})
        self.assertEqual([면[no] for no in (1, 2, 3, 4)],
                         [('문자인식', '옛 자기 캐시의 글'), ('문자인식', '옛 호증키 폴더의 글'),
                          ('문자인식', '옛 판 ocr.json 의 글'), ('문자인식', '표지가 맞는 묶음의 글')])
        self.assertEqual((self.부름, 안씀), ([], []))                             # 다시 문자인식하지 않았다
        self.assertEqual((self.own / ecr.OCR_MARK).read_text(encoding='utf-8'), ecr.hash_file(self.pdf))
        self.assertFalse((self.root / '넘긴결과' / '갑1' / ecr.OCR_MARK).exists())
        self.assertFalse((self.root / '지정' / ecr.OCR_MARK).exists())

    def test_new_ocr_writes_the_mark_with_pages(self):
        """문자인식을 새로 하면 pages.json 과 함께 표지가 생긴다. 같은 파일이면 앞 결과에 덧붙이고, 다른 파일을 넣으면 앞 결과를 버린다."""
        면들 = lambda: sorted(json.loads((self.own / 'pages.json').read_text(encoding='utf-8')))
        self.read([1, 2])
        self.assertEqual(면들(), ['1', '2'])
        표지 = (self.own / ecr.OCR_MARK).read_text(encoding='utf-8')
        self.assertEqual(표지, ecr.hash_file(self.pdf))
        self.assertEqual(표지, er.해시(self.pdf))                                 # 전 면 읽기의 표지와 같은 꼴
        self.read([1, 2, 3])                                                     # 같은 파일: 3면만 더 읽어 덧붙인다
        self.assertEqual(self.부름, [['p001.png', 'p002.png'], ['p003.png']])
        self.assertEqual(면들(), ['1', '2', '3'])
        scan_pdf(self.pdf, 4, '더 나은 스캔본')                                   # 같은 번호에 다른 PDF
        self.assertNotEqual(ecr.hash_file(self.pdf), 표지)
        self.글['t'] = '더 나은 스캔본을 읽은 글입니다'
        면, 안씀 = self.read([1])
        self.assertEqual(면[1], ('문자인식', '더 나은 스캔본을 읽은 글입니다'))
        self.assertEqual(안씀, [str(self.own)])
        self.assertEqual(면들(), ['1'])                                           # 앞 파일의 2·3면은 버렸다
        self.assertEqual((self.own / ecr.OCR_MARK).read_text(encoding='utf-8'), ecr.hash_file(self.pdf))

    def test_mark_is_a_hash_or_lines_of_key_and_hash(self):
        f = self.root / '표지'
        f.mkdir()
        self.assertIsNone(ecr.read_mark(f, '갑1'))                               # 표지 없음
        (f / ecr.OCR_MARK).write_text('0123456789ab', encoding='utf-8')
        self.assertEqual(ecr.read_mark(f, '갑1'), '0123456789ab')               # 호증 하나의 폴더
        (f / ecr.OCR_MARK).write_text('﻿갑1  0123456789ab\r\n을2\t89abcdef0123\r\n', encoding='utf-8')
        self.assertEqual((ecr.read_mark(f, '갑1'), ecr.read_mark(f, '을2')), ('0123456789ab', '89abcdef0123'))
        self.assertIsNone(ecr.read_mark(f, '갑3'))                               # 묶음에 줄이 없는 호증은 옛 결과처럼 본다
        (f / ecr.OCR_MARK).write_text('', encoding='utf-8')
        self.assertEqual(ecr.read_mark(f, '갑1'), '')                            # 빈 표지는 어느 파일과도 맞지 않는다

    def test_unmarked_results_are_dropped_when_review_records_another_file(self):
        """표지가 없는 옛 결과라도 증거인용검토의 review.json 이 그 호증에 다른 파일의 해시를 적었으면 쓰지 않는다. 그 대조 뒤에 호증
        파일을 바꾼 때(자기 캐시는 지운다)와 앞 라운드의 같은 번호 파일이 지금 것과 다른 때(넘겨받은 결과는 둔다)이다."""
        def 대조기록(폴더: Path, rows):
            폴더.mkdir(parents=True, exist_ok=True)
            (폴더 / 'review.json').write_text(json.dumps(rows), encoding='utf-8')
        지금 = ecr.hash_file(self.pdf)
        앞라운드 = self.root / '라운드0' / '작업' / '증거인용검토'
        ocr_cache(self.own, {1: '바꾸기 전 파일의 글'})
        대조기록(self.review, [{'n': 1, 'key': '갑1', 'file_hash': 'deadbeef0000'}, {'n': 2, 'key': '을2', 'file_hash': 지금}])
        ocr_cache(앞라운드 / 'ocr' / '갑1', {2: '앞 라운드 파일의 글'})
        대조기록(앞라운드, [{'n': 1, 'key': '갑1', 'file_hash': 'deadbeef0000'}])
        면, 안씀 = self.read([1, 2], ocr_dirs=[앞라운드 / 'ocr'], use_ocr=False)
        self.assertEqual(면, {1: ('글자 없음', ''), 2: ('글자 없음', '')})
        self.assertEqual(sorted(안씀), sorted([str(self.own), str(앞라운드 / 'ocr' / '갑1')]))
        self.assertFalse(self.own.exists())
        self.assertTrue((앞라운드 / 'ocr' / '갑1' / 'pages.json').is_file())
        # review.json 이 지금 파일의 해시를 적었거나 해시를 적지 않은 옛 대조이면 쓴다
        ocr_cache(self.own, {1: '지금 파일의 글'})
        대조기록(self.review, [{'n': 1, 'key': '갑1', 'file_hash': 지금}])
        대조기록(앞라운드, [{'n': 1, 'key': '갑1'}])
        면, 안씀 = self.read([1, 2], ocr_dirs=[앞라운드 / 'ocr'], use_ocr=False)
        self.assertEqual(면, {1: ('문자인식', '지금 파일의 글'), 2: ('문자인식', '앞 라운드 파일의 글')})
        self.assertEqual(안씀, [])

    def test_scan_reads_a_replaced_scan_again(self):
        """대조를 다시 돌릴 때 같은 번호에 다른 스캔본을 넣었으면 앞 스캔본의 글을 쓰지 않고 다시 읽는다. 표지가 생기기 전에 만든
        결과도 앞선 대조(review.json)가 적은 해시로 가린다."""
        rnd = self.root / '사건D' / '라운드1'
        (rnd / '출력').mkdir(parents=True)
        (rnd / '우리증거').mkdir()
        md = rnd / '출력' / '서면초안.md'
        md.write_text('- 다 음 -\n\n가. 사실입니다(갑 제1호증 확인서 1면).\n', encoding='utf-8')
        갑1 = rnd / '우리증거' / '갑 제1호증 확인서.pdf'
        out = rnd / '작업' / '증거인용검토'

        def 대조(글):
            self.글['t'] = 글
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(ecr.main(['scan', str(md)]), 0)
            r = json.loads((out / 'review.json').read_text(encoding='utf-8'))[0]
            return r['windows'][0]['text'], r['file_hash'], buf.getvalue()

        scan_pdf(갑1, 1, '첫 스캔본')
        글, 해시, 말 = 대조('첫 스캔본을 읽은 글입니다')
        self.assertEqual((글, 해시), ('첫 스캔본을 읽은 글입니다', ecr.hash_file(갑1)))
        self.assertEqual((out / 'ocr' / '갑1' / ecr.OCR_MARK).read_text(encoding='utf-8'), 해시)
        self.assertNotIn('쓰지 않은 호증', 말)
        self.assertEqual(대조('다시 읽으면 안 되는 글입니다')[0], '첫 스캔본을 읽은 글입니다')   # 같은 파일은 다시 읽지 않는다
        scan_pdf(갑1, 1, '더 나은 스캔본')
        글, _, 말 = 대조('더 나은 스캔본을 읽은 글입니다')
        self.assertEqual(글, '더 나은 스캔본을 읽은 글입니다')
        self.assertIn('지금 호증 파일의 것이 아니어서 쓰지 않은 호증 1건: 갑1', 말)
        (out / 'ocr' / '갑1' / ecr.OCR_MARK).unlink()                            # 표지가 생기기 전에 만든 결과
        scan_pdf(갑1, 1, '세 번째 스캔본')
        self.assertEqual(대조('세 번째 스캔본을 읽은 글입니다')[0], '세 번째 스캔본을 읽은 글입니다')
        self.assertEqual(len(self.부름), 3)

    def test_whole_page_reading_does_not_take_another_files_result(self):
        """전 면 읽기(`evidence_read.py make`)도 증거인용검토의 문자인식 결과를 다시 쓴다. 표지가 다른 결과는 면별 글에 넣지 않고,
        표지가 없는 옛 결과와 표지가 맞는 결과는 넣는다."""
        case = self.root / '사건E'
        ours = case / '라운드1' / '우리증거'
        ours.mkdir(parents=True)
        스캔 = ours / '갑 제1호증 스캔.pdf'
        scan_pdf(스캔, 1, '새 스캔본')
        결과 = case / '라운드1' / '작업' / '증거인용검토' / 'ocr' / '갑1'

        def 면별_글(표지):
            ocr_cache(결과, {1: '증거인용검토가 읽은 글입니다'}, 표지)
            with redirect_stdout(io.StringIO()):
                er.main(['make', str(case), '--no-ocr', '--호증', '갑1', '--글다시', '갑1'])
            return (case / '증거관리' / '호증글자' / '갑1.txt').read_text(encoding='utf-8')

        self.assertNotIn('증거인용검토가 읽은 글입니다', 면별_글('deadbeef0000'))
        self.assertIn('증거인용검토가 읽은 글입니다', 면별_글(None))
        self.assertIn('증거인용검토가 읽은 글입니다', 면별_글(er.해시(스캔)))


if __name__ == '__main__':
    unittest.main()
