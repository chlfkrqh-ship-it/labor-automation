"""4_서면작성/scripts/figure_fit.py(발췌 그림 크기 맞춤)를 확인한다.

Word 로 PDF 를 내보내는 부분은 흉내 내고, 문서 XML 처리·PDF 면 분석·고칠 곳 계획·되풀이 판단을 본다.
PDF 는 pymupdf 로 임시 폴더에 만든다. 사건 자료나 OneDrive 폴더에는 아무것도 쓰지 않는다.
"""
import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from lxml import etree

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / '4_서면작성' / 'scripts'))
import figure_fit as ff  # noqa: E402

NSDECL = ' '.join('xmlns:%s="%s"' % kv for kv in ff.NS.items())
SECT = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="2552" w:right="1418" w:bottom="1701" w:left="1418"/></w:sectPr>')


def 그림(cx, cy, keep=True):
    ppr = '<w:pPr><w:keepNext/><w:keepLines/></w:pPr>' if keep else ''
    return ('<w:p>%s<w:r><w:drawing><wp:inline><wp:extent cx="%d" cy="%d"/><a:graphic><a:graphicData><pic:pic>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>' % (ppr, cx, cy, cx, cy))


def 글문단(t, keep=False):
    ppr = '<w:pPr><w:keepNext/></w:pPr>' if keep else ''
    return '<w:p>%s<w:r><w:t>%s</w:t></w:r></w:p>' % (ppr, t)


def 문서(*문단):
    return etree.fromstring('<w:document %s><w:body>%s%s</w:body></w:document>' % (NSDECL, ''.join(문단), SECT))


def 표본():
    return 문서(
        글문단('본문'), '<w:p/>',
        글문단('[사 제1호증 근로계약서]', keep=True),
        그림(5400000, 2700000),
        '<w:p><w:pPr><w:keepNext/></w:pPr></w:p>',          # 그림 뒤 빈 문단에 keepNext(2026. 10. 16. 사 제8호증)
        글문단('본문2'),
        글문단('[사 제2호증 회의록]', keep=True), '<w:p/>',   # 캡션과 그림 사이 빈 문단 하나까지
        그림(5400000, 2000000), 그림(5400000, 2000000),       # 두 장으로 나눈 그림
        '<w:p/>',
        '<w:tbl><w:tr><w:tc>%s</w:tc></w:tr></w:tbl>' % 그림(900000, 300000, keep=False),   # 표 안 로고
        그림(900000, 300000, keep=False),                    # 캡션 없는 그림
        글문단('[사 제3호증 그림 없음]'), 글문단('본문3'),
        글문단('[사 제4호증 지운 그림]'),
        '<w:p><w:del w:id="1" w:author="x"><w:r><w:drawing><wp:inline><wp:extent cx="10" cy="10"/></wp:inline>'
        '</w:drawing></w:r></w:del></w:p>',
    )


class 문서처리(unittest.TestCase):
    def test_발췌목록(self):
        body = 표본().find(ff.W + 'body')
        figs = ff.발췌목록(body)
        self.assertEqual([f['cap'] for f in figs], ['[사 제1호증 근로계약서]', '[사 제2호증 회의록]'])
        self.assertEqual([len(f['inls']) for f in figs], [1, 2])
        self.assertEqual([len(f['paras']) for f in figs], [1, 2])

    def test_묶음풀기는_마지막_그림_문단만(self):
        root = 표본()
        body = root.find(ff.W + 'body')
        figs = ff.발췌목록(body)
        self.assertEqual(ff.묶음풀기(figs), 2)
        self.assertFalse(ff.keep_next(figs[0]['paras'][-1]))
        self.assertTrue(ff.keep_next(figs[1]['paras'][0]))   # 나눈 그림의 앞 조각은 뒤 조각과 붙어 있어야 한다
        self.assertFalse(ff.keep_next(figs[1]['paras'][1]))
        self.assertTrue(ff.keep_next(figs[0]['cap_p']))      # 캡션은 그대로
        self.assertEqual(ff.묶음풀기(figs), 0)                # 두 번 돌려도 같다

    def test_크기와_비율(self):
        figs = ff.발췌목록(표본().find(ff.W + 'body'))
        inl = figs[0]['inls'][0]
        self.assertAlmostEqual(ff.비율(inl), 1.0)
        ff.크기바꾸기(inl, 5400000 * 0.8, 2700000 * 0.8)
        self.assertEqual(ff.크기(inl), (4320000, 2160000))
        self.assertEqual(inl.find('.//a:ext', ff.NS).get('cx'), '4320000')
        self.assertAlmostEqual(ff.비율(inl), 0.8)
        tall = ff.발췌목록(문서(글문단('[사 제9호증]'), 그림(2700000, 5040000)).find(ff.W + 'body'))[0]['inls'][0]
        self.assertAlmostEqual(ff.비율(tall), 1.0)          # 세로 14cm 로 맞춘 그림도 처음 크기

    def test_본문범위(self):
        self.assertEqual(ff.본문범위(표본()), (127.6, 841.9 - 85.05))

    def test_하한값(self):
        self.assertEqual(ff.하한값('[사 제24호증 결과보고]', 0.7, {'사 제24호증': 0.65}), 0.65)
        self.assertEqual(ff.하한값('[사 제2호증 회의록]', 0.7, {'사 제24호증': 0.65}), 0.7)
        self.assertEqual(ff.하한값('[사 제24호증 결과보고]', 0.7, {'사제24호증': 0.6}), 0.6)   # 공백 무시

    def test_짝짓기(self):
        문서발췌 = [{'cap': '[사 제1호증 가]'}, {'cap': '[사 제2호증 나]'}, {'cap': '[사 제1호증 가]'}]
        짝, 못 = ff.짝짓기([{'cap': '[사 제1호증  가]'}, {'cap': '[사 제1호증가]'}], 문서발췌)
        self.assertEqual((짝, 못), ([0, 2], [1]))
        with self.assertRaises(SystemExit):
            ff.짝짓기([{'cap': '[사 제5호증]'}], 문서발췌)

    def test_저장은_document_xml_만_바꾼다(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'a.docx')
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', etree.tostring(표본()))
                z.writestr('word/media/image1.png', b'PNGDATA')
            root = ff.읽기(p)
            ff.크기바꾸기(ff.발췌목록(root.find(ff.W + 'body'))[0]['inls'][0], 100, 50)
            ff.저장(p, root)
            with zipfile.ZipFile(p) as z:
                self.assertEqual(z.read('word/media/image1.png'), b'PNGDATA')
            self.assertEqual(ff.크기(ff.발췌목록(ff.읽기(p).find(ff.W + 'body'))[0]['inls'][0]), (100, 50))

    def test_보관이름은_덮어쓰지_않는다(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, '서면.docx')
            a = ff.보관이름(src, os.path.join(d, '보관'))
            open(a, 'w').close()
            b = ff.보관이름(src, os.path.join(d, '보관'))
            self.assertNotEqual(a, b)
            self.assertTrue(os.path.basename(a).startswith('서면.bak_그림맞춤_'))


def 면(bottom, first):
    return {'bottom': bottom, 'first': first}


def 발(k, cap_top, top, bottom, cap='[c]'):
    return {'k': k, 'cap': cap, 'cap_top': cap_top, 'top': top, 'bottom': bottom}


class 계획(unittest.TestCase):
    아래 = 757.0

    def test_그림만_줄여_들어가면_그림만(self):
        면들 = [면(450, 140), 면(700, 135)]
        발췌들 = [발(1, 135, 160, 460)]                        # 캡션 25 + 그림 300
        안 = ff.계획(면들, 발췌들, 40, self.아래, [90.0])
        # 필요 = 40 + 325 + 8 = 373, 남은 = 307 → 66 모자람
        self.assertEqual(안['k'], 1)
        self.assertAlmostEqual(안['남은'], 307)
        self.assertEqual(set(안['줄일']), {0})
        self.assertAlmostEqual(안['줄일'][0], 66)

    def test_앞_그림과_여력에_비례해_나눈다(self):
        면들 = [면(450, 140), 면(700, 135)]
        발췌들 = [발(0, 200, 220, 300), 발(1, 135, 160, 460)]
        안 = ff.계획(면들, 발췌들, 40, self.아래, [30.0, 60.0])
        self.assertAlmostEqual(안['줄일'][1], 44)
        self.assertAlmostEqual(안['줄일'][0], 22)

    def test_세_면_앞_그림은_나누지_않는다(self):
        면들 = [면(450, 140), 면(757, 128), 면(450, 140), 면(700, 135)]
        발췌들 = [발(0, 200, 220, 300), 발(3, 135, 160, 460)]
        self.assertIsNone(ff.계획(면들, 발췌들, 40, self.아래, [30.0, 60.0])['줄일'])
        발췌들[0]['k'] = 1                                    # 두 면 앞이면 나눈다
        self.assertEqual(set(ff.계획(면들, 발췌들, 40, self.아래, [30.0, 60.0])['줄일']), {0, 1})

    def test_하한까지_줄여도_모자라면_None(self):
        안 = ff.계획([면(450, 140), 면(700, 135)], [발(1, 135, 160, 460)], 40, self.아래, [50.0])
        self.assertIsNone(안['줄일'])
        self.assertAlmostEqual(안['모자람'], 66)

    def test_어림으로_들어가면_빈_사전(self):
        안 = ff.계획([면(350, 140), 면(700, 135)], [발(1, 135, 160, 460)], 40, self.아래, [90.0])
        self.assertEqual(안['줄일'], {})
        self.assertLessEqual(안['모자람'], 0)

    def test_보탬과_제외(self):
        면들, 발췌들 = [면(350, 140), 면(700, 135)], [발(1, 135, 160, 460)]
        안 = ff.계획(면들, 발췌들, 40, self.아래, [90.0], 보탬={0: 50.0})
        self.assertAlmostEqual(안['줄일'][0], 373 + 50 - 407)
        self.assertIsNone(ff.계획(면들, 발췌들, 40, self.아래, [90.0], 제외={0}))

    def test_고칠_곳이_아닌_경우(self):
        # 캡션이 면 머리가 아니다 / 앞 면이 거의 차 있다 / 첫 면이다
        self.assertIsNone(ff.계획([면(450, 140), 면(700, 135)], [발(1, 300, 320, 460)], 40, self.아래, [90.0]))
        self.assertIsNone(ff.계획([면(720, 140), 면(700, 135)], [발(1, 135, 160, 460)], 40, self.아래, [90.0]))
        self.assertIsNone(ff.계획([면(700, 135)], [발(0, 135, 160, 460)], 40, self.아래, [90.0]))


class 면분석(unittest.TestCase):
    def test_각주가_있는_면은_구분선까지를_아래_끝으로_본다(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as d:
            pdf = os.path.join(d, 't.pdf')
            doc = pymupdf.open()
            p1 = doc.new_page(width=595, height=842)
            p1.insert_text((72, 300), 'Body line', fontsize=11)
            p1.draw_line((72, 700), (216, 700))                  # 각주 구분선
            p1.insert_text((72, 720), 'Footnote', fontsize=9)
            p2 = doc.new_page(width=595, height=842)
            p2.insert_text((72, 300), 'Body line', fontsize=11)
            p2.draw_line((72, 500), (497, 500))                  # 본문 폭의 줄은 구분선이 아니다
            p2.insert_text((72, 700), 'Body end', fontsize=11)
            doc.save(pdf)
            doc.close()
            면들, _, _ = ff.면분석(pdf, 127.6, 757.0)
        self.assertAlmostEqual(면들[0]['foot'], 700, delta=1)
        self.assertLess(면들[0]['bottom'], 310)
        self.assertIsNone(면들[1]['foot'])
        self.assertGreater(면들[1]['bottom'], 695)

    def test_PDF_에서_캡션과_그림을_짝짓는다(self):
        import pymupdf
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (40, 20), 'gray').save(buf, 'PNG')
        png = buf.getvalue()
        with tempfile.TemporaryDirectory() as d:
            pdf = os.path.join(d, 't.pdf')
            doc = pymupdf.open()
            p1 = doc.new_page(width=595, height=842)
            p1.insert_text((72, 150), 'Body line 1', fontsize=11)
            p1.insert_text((72, 400), 'Body line 2', fontsize=11)
            p1.insert_text((72, 450), '[Exhibit 1]', fontsize=11)
            p1.insert_image(pymupdf.Rect(100, 465, 495, 560), stream=png, keep_proportion=False)
            p1.insert_image(pymupdf.Rect(100, 563, 495, 600), stream=png, keep_proportion=False)    # 두 장으로 나눈 그림의 뒤 조각
            p1.insert_image(pymupdf.Rect(60, 780, 160, 820), stream=png, keep_proportion=False)     # 바닥글 로고(본문 밖)
            p2 = doc.new_page(width=595, height=842)
            p2.insert_text((72, 140), '[Exhibit 2]', fontsize=11)
            p2.insert_image(pymupdf.Rect(100, 150, 495, 400), stream=png, keep_proportion=False)
            p2.insert_text((72, 430), 'Body line 3', fontsize=11)
            p2.insert_image(pymupdf.Rect(100, 500, 300, 600), stream=png, keep_proportion=False)    # 캡션 없는 그림
            doc.save(pdf)
            doc.close()
            면들, 발췌들, 간격 = ff.면분석(pdf, 127.6, 757.0)
        self.assertEqual([(f['k'], f['cap']) for f in 발췌들], [(0, '[Exhibit 1]'), (1, '[Exhibit 2]')])
        self.assertAlmostEqual(발췌들[0]['top'], 465, delta=0.2)
        self.assertAlmostEqual(발췌들[0]['bottom'], 600, delta=0.2)
        self.assertAlmostEqual(면들[1]['first'], 발췌들[1]['cap_top'])
        self.assertAlmostEqual(면들[0]['bottom'], 600, delta=0.2)
        self.assertGreater(간격, 30)
        self.assertLess(간격, 60)


def 작은문서(path):
    root = 문서(글문단('본문'), '<w:p/>', 글문단('[사 제1호증 가]', keep=True), 그림(5400000, 800000), '<w:p/>',
              글문단('본문2'), '<w:p/>', 글문단('[사 제2호증 나]', keep=True), 그림(5400000, 3000000), '<w:p/>')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('word/document.xml', etree.tostring(root))


class 되풀이(unittest.TestCase):
    """내보내기·면분석을 흉내 내어 맞추기의 판단(줄임, 더 줄임, 되돌림, 원인 모를 빈 곳)을 본다."""
    A = ('[사 제1호증 가]', '[사 제2호증 나]')

    def 돌리기(self, 분석들, 하한=0.7):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'w.docx')
            작은문서(p)
            말 = []
            with mock.patch.object(ff, '내보내기', return_value='x.pdf') as 내, \
                    mock.patch.object(ff, '면분석', side_effect=분석들):
                바뀜 = ff.맞추기(None, p, d, 하한, 12, 말.append)
            figs = ff.발췌목록(ff.읽기(p).find(ff.W + 'body'))
            return 바뀜, [ff.크기(f['inls'][0]) for f in figs], 내.call_count, 말

    def 분석(self, 앞면_bottom, 그림1, 그림2):
        """그림2 가 둘째 면 머리에 있다. 그림1·그림2 는 PDF 높이(pt)."""
        return ([면(앞면_bottom, 140), 면(700, 135)],
                [발(0, 200, 220, 220 + 그림1, self.A[0]), 발(1, 135, 160, 160 + 그림2, self.A[1])], 40.0)

    def 끝(self):
        return ([면(700, 140), 면(700, 135)], [발(0, 200, 220, 280, self.A[0]), 발(1, 300, 320, 560, self.A[1])], 40.0)

    def test_줄이고_끝난다(self):
        바뀜, 크기들, 횟수, _ = self.돌리기([self.분석(450, 60, 240), self.끝()])
        self.assertTrue(바뀜)
        self.assertEqual(횟수, 2)
        # 필요 = 40 + 265 + 8 = 313, 남은 = 본문 아래 끝(841.9 - 85.05) - 450 → 모자람을 여력 18 : 72 로 나눔
        모자람 = 313 - (841.9 - 85.05 - 450)
        self.assertAlmostEqual(크기들[1][0] / 5400000, (240 - 모자람 * 72 / 90) / 240, places=5)
        self.assertAlmostEqual(크기들[0][0] / 5400000, (60 - 모자람 * 18 / 90) / 60, places=5)

    def test_줄였는데도_넘어가면_더_줄인다(self):
        바뀜, 크기들, 횟수, 말 = self.돌리기([self.분석(450, 60, 240), self.분석(440, 59, 235), self.끝()])
        self.assertEqual(횟수, 3)
        self.assertTrue(any('더 줄여 봄' in m for m in 말))
        self.assertLess(크기들[1][0] / 5400000, (240 - 6 * 72 / 90) / 240 - 0.01)

    def test_하한에_닿으면_되돌린다(self):
        바뀜, 크기들, 횟수, 말 = self.돌리기([self.분석(450, 60, 240), self.분석(600, 59, 235), self.분석(450, 60, 240)])
        self.assertTrue(바뀜)                                 # 1단계(keepNext 풀기)는 남는다
        self.assertEqual(크기들, [(5400000, 800000), (5400000, 3000000)])
        self.assertEqual(횟수, 3)
        self.assertTrue(any('원래 크기로 되돌림' in m for m in 말))

    def test_크기로_설명되지_않는_빈_곳은_그대로(self):
        바뀜, 크기들, 횟수, 말 = self.돌리기([self.분석(300, 60, 240)])
        self.assertEqual(횟수, 1)                             # 다시 내보내지 않는다
        self.assertEqual(크기들, [(5400000, 800000), (5400000, 3000000)])
        self.assertTrue(any('크기로는 들어가야 하는데' in m for m in 말))

    def test_하한까지_모자라면_손대지_않는다(self):
        바뀜, 크기들, 횟수, 말 = self.돌리기([self.분석(600, 60, 240)])
        self.assertEqual(횟수, 1)
        self.assertEqual(크기들, [(5400000, 800000), (5400000, 3000000)])
        self.assertTrue(any('이 그림만 줄이면' in m for m in 말))


if __name__ == '__main__':
    unittest.main()
