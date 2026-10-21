"""4_서면작성/scripts/evidence_stamp.py(호증 도장)를 확인한다.

빈 A4 PDF 를 임시 폴더에 만들어 도장을 넣고, 원본 바이트가 앞에 그대로 남는지(덧붙여 저장)와 도장 그림이 압축되어
파일이 조금만 늘어나는지 본다. 압축하지 않던 때에는 파일마다 2~3MB 가 늘었다(2026. 10. 21. OES 제출 증거).
글자를 바탕·궁서 글꼴(batang.ttc)로 그리므로 그 글꼴이 있는 Windows 에서만 돈다. 사건 자료에는 아무것도 쓰지 않는다.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import pymupdf

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / '4_서면작성' / 'scripts'))
import evidence_stamp as es  # noqa: E402

늘어난허용 = 100_000     # 바이트. 압축한 도장 그림·테두리는 수십 KB 이다


def 빈문서(경로, 면=2):
    d = pymupdf.open()
    for i in range(면):
        d.new_page(width=595, height=842).insert_text((72, 100), 'page %d' % (i + 1), fontsize=14)
    d.save(str(경로), garbage=3, deflate=True)
    d.close()


def 압축없는그림(경로):
    """필터 없이(압축 없이) 들어 있는 그림 스트림의 바이트 수."""
    d = pymupdf.open(str(경로))
    합 = 0
    for x in range(1, d.xref_length()):
        if (d.xref_is_stream(x) and d.xref_get_key(x, 'Subtype')[1] == '/Image'
                and d.xref_get_key(x, 'Filter')[0] == 'null'):
            합 += len(d.xref_stream_raw(x))
    d.close()
    return 합


@unittest.skipUnless(Path(es.글꼴묶음).exists(), '바탕·궁서 글꼴(batang.ttc)이 있는 Windows 에서만')
class 도장(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_폴더째_찍으면_원본_뒤에_압축해_덧붙인다(self):
        원본폴더, 낼폴더 = self.dir / '원본', self.dir / '낼'
        원본폴더.mkdir()
        원본 = 원본폴더 / '사제1호증_시험.pdf'
        빈문서(원본)
        출력 = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')     # main 이 stdout.reconfigure 를 부른다
        with redirect_stdout(출력):
            코드 = es.main([str(원본폴더), str(낼폴더), '--색', '파랑'])
        출력.flush()
        self.assertEqual(코드, 0, 출력.buffer.getvalue().decode('utf-8'))
        a, b = 원본.read_bytes(), (낼폴더 / '사 제1호증_시험.pdf').read_bytes()
        self.assertEqual(b[:len(a)], a)
        self.assertLess(len(b) - len(a), 늘어난허용)
        self.assertEqual(압축없는그림(낼폴더 / '사 제1호증_시험.pdf'), 0)

    def test_직접_만든_표시도_덧붙여저장으로_압축한다(self):
        경로 = self.dir / '노위 제2호증의1_시험.pdf'
        빈문서(경로, 면=1)
        크기 = 경로.stat().st_size
        표시 = {'종류': '호증', '머리': '노위', '번호': 2, '가지': 1}
        d = pymupdf.open(str(경로))
        r, 먹비율, 정한법 = es.도장(d[0], 표시, '파랑')
        es.덧붙여저장(d)
        d.close()
        self.assertEqual(es.표시글(표시), '노위 제2호증의 1')
        self.assertEqual(정한법, '기본 자리')
        self.assertEqual(먹비율, 0.0)
        self.assertLess(경로.stat().st_size - 크기, 늘어난허용)
        self.assertEqual(압축없는그림(경로), 0)


if __name__ == '__main__':
    unittest.main()
