"""4_서면작성/scripts/nlrc_members.py(`/노동위서류` '위원 명단·프로필')를 확인한다.

누리집에 닿지 않는다. 통지서 글과 누리집 표는 가공한 글로 넣고, 이름도 가공한 것이다. 2026. 11. 9. GGM 정직 3월 심문회의 날
위원 명단·프로필을 OES 판(강민석 변호사가 올린 '노동위원회 위원명단.pdf')과 같은 모양으로 정리한 빌드를 도구로 옮겼다.
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '4_서면작성' / 'scripts' / 'nlrc_members.py'
spec = importlib.util.spec_from_file_location('nlrc_members', SCRIPT)
nm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nm)

통지글 = """전남지방노동위원회
수신
수신자 참조
제목
심문일정 통지
사        건
2026부해0000 주식회사 가나다 부당정직 구제신청
심판위원
회위원
 공 익 위 원: 가나다, 라마바, 사아자
참 여 위 원 근로자위원: 차카타
사용자위원: 파하가
심 문 일 시
2026. 12. 1.(화) 16:00
전남지방노동위원회위원장
/ http://jeonnam.nlrc.go.kr
"""


def 누리집(줄들, 수=None):
    몸 = ''.join(f'<tr><td>{a}</td><td><span class="pc_blue">{b}</span></td><td class="al">{c}</td><td>{d}</td></tr>' for a, b, c, d in 줄들)
    return (f'<h4 class="titT2 mt-4">위원수 : {len(줄들) if 수 is None else 수}명(공무원노동관계조정위원 6명 포함)</h4>'
            f'<table><thead><tr><th>구분</th><th>성명</th><th>현직</th><th>업무</th></tr></thead><tbody>{몸}</tbody></table>')


표 = [('공익위원', '라마바', '공인노무사(가나노무법인)', '심판'),
     ('위원장', '가나다', '전남지방노동위원회 위원장', '조정, 심판 등'),
     ('사용자위원', '파하가', '(주)가나 전문위원', '조정, 심판 등'),
     ('공익위원', '사아자', '가나대학교 교수', '심판'),
     ('근로자위원', '차카타', '가나노조 지회장', '조정, 심판 등'),
     ('공익위원', '거너더', '변호사', '차별시정')]


class 통지서Tests(unittest.TestCase):
    def test_reads_committee_and_members_in_notice_order(self):
        r = nm.통지서_읽기(통지글)
        self.assertEqual(r['위원회'], '전남')
        self.assertEqual(r['공익'], ['가나다', '라마바', '사아자'])
        self.assertEqual(r['근로자'], ['차카타'])
        self.assertEqual(r['사용자'], ['파하가'])

    def test_central_commission_is_named_without_jibang(self):
        r = nm.통지서_읽기('중앙노동위원회\n공 익 위 원: 가나다\n근로자위원: 라마바\n사용자위원: 사아자\n중앙노동위원회위원장')
        self.assertEqual(r['위원회'], '중앙')


class 누리집Tests(unittest.TestCase):
    def test_list_rows_and_count(self):
        줄들, 수 = nm.목록_읽기(누리집(표))
        self.assertEqual(수, len(표))
        self.assertEqual(줄들[1], ('위원장', '가나다', '전남지방노동위원회 위원장', '조정, 심판 등'))

    def test_pick_follows_notice_order_public_worker_employer(self):
        줄들, _ = nm.목록_읽기(누리집(표))
        고른 = nm.고르기(줄들, nm.통지서_읽기(통지글))
        self.assertEqual([r[1] for r in 고른], ['가나다', '라마바', '사아자', '차카타', '파하가'])
        self.assertEqual(고른[0][0], '위원장')

    def test_missing_or_duplicate_name_stops(self):
        줄들, _ = nm.목록_읽기(누리집(표 + [('공익위원', '라마바', '다른 사람', '심판')]))
        with self.assertRaises(nm.멈춤) as c:
            nm.고르기(줄들, {'공익': ['라마바', '없는이'], '근로자': [], '사용자': []})
        self.assertIn('같은 이름이 2명', str(c.exception))
        self.assertIn('없는이', str(c.exception))


class 표Tests(unittest.TestCase):
    def setUp(self):
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            self.skipTest('PyMuPDF 가 없다')

    def test_draws_one_page_with_every_cell(self):
        줄들, _ = nm.목록_읽기(누리집(표))
        고른 = nm.고르기(줄들, nm.통지서_읽기(통지글))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '(가나) 노동위원회 위원명단.pdf'
            nm.그리기(고른, p)
            문제, 그림 = nm.확인(p, 고른)
            self.assertEqual(문제, [])
            self.assertTrue(그림 and 그림.is_file())

    def test_long_title_is_shrunk_to_fit_and_still_found(self):
        긴 = [('공익위원', '가나다', '가나다라마바사 대학교 법학전문대학원 노동법 담당 교수 겸 가나다 연구소장', '심판')]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.pdf'
            nm.그리기(긴, p)
            self.assertEqual(nm.확인(p, 긴)[0], [])


class 기타Tests(unittest.TestCase):
    def test_short_name_from_case_folder(self):
        self.assertEqual(nm.약칭_읽기(Path('4_서면작성/사건/GGM_정직3월/라운드3')), 'GGM')
        self.assertEqual(nm.약칭_읽기(Path('4_서면작성/사건/OES_부당해고 구제신청/라운드1')), 'OES')

    def test_no_notice_and_no_names_stops_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            라운드 = Path(d) / '가나_사건' / '라운드1'
            (라운드 / '참고자료').mkdir(parents=True)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = nm.main([str(라운드)])
            self.assertEqual(rc, 1)
            self.assertIn('오류:', out.getvalue())

    def test_notice_found_in_latest_round_first(self):
        with tempfile.TemporaryDirectory() as d:
            사건 = Path(d) / '가나_사건'
            for n in (1, 2):
                (사건 / f'라운드{n}' / '참고자료').mkdir(parents=True)
            (사건 / '라운드1' / '참고자료' / '심문일정 통지.pdf').write_bytes(b'%PDF-1.4')
            (사건 / '라운드2' / '참고자료' / '심문일정 통지(변경).pdf').write_bytes(b'%PDF-1.4')
            self.assertEqual(nm.통지서_찾기(사건 / '라운드2').parent.parent.name, '라운드2')


if __name__ == '__main__':
    unittest.main()
