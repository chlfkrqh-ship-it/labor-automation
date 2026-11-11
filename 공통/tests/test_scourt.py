"""법원 누리집 판결 게시판 도구(공통/scripts/scourt.py)를 네트워크 없이 확인한다.

2026. 11. 11. LBOX 가 이용약관 제11조(자동화 수단 금지)를 들어 계정을 제한하여, 하급심을 보태는 경로로 대법원 누리집 대국민서비스의
'전국법원 주요판결'·'판례속보'·'언론보도판결'을 붙였다. 화면은 그날 받은 화면의 구조를 줄여 옮긴 것이다. 보는 것:
  - 목록·게시물·판결공보 요약본 해석(제목 전문, 판결 표시, 첨부 주소, 확정·항소 표시)
  - 본문이 인용한 다른 판결을 그 글의 판결로 잡지 않는다(판례속보 대법원 글의 '대법원 1991. 9. 10. 선고 91다10565 판결')
  - robots.txt 를 가장 긴 규칙으로 판정한다(file.scourt.go.kr 는 'Disallow: /' 뒤에 Allow 폴더를 둔다)
  - 간격·하루 상한·차단 화면에서 멈춤·멈춤 표시가 있으면 보내지 않음
  - harvest 가 법제처_목록.json 과 같은 칸의 법원_목록.json 을 쓰고, harvest_titles.py 가 그 줄을 읽는다
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
import zipfile
from unittest import mock

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('scourt', ROOT / '공통' / 'scripts' / 'scourt.py')
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)
hspec = importlib.util.spec_from_file_location('harvest_titles', ROOT / '공통' / 'scripts' / 'harvest_titles.py')
ht = importlib.util.module_from_spec(hspec)
hspec.loader.exec_module(ht)

WWW_ROBOTS = 'User-agent: AhrefsBot\nDisallow: /\n\nUser-agent: *\nDisallow: /news/\nDisallow: /search/\nDisallow: /notice/\n'
FILE_ROBOTS = 'User-agent: *\nDisallow: /\nAllow: /cboard/\nAllow: /dcboard/\nAllow: /nboard/\nAllow: /sc/board/\n'


def row44(no, seq, code, title, court):
    return (f'<tr><td class="mhid">{no}</td><td class="tit">\n<a href="#" onclick="fn_view(\'{seq}\',\'{code}\');return false;">\n'
            f'{title}\n</a>\n</td>\n<td>{court}</td>\n<td class="attach mhid">\n<img src="/portal/common/images/attfile.gif" alt="첨부파일">\n</td>'
            f'\n<td class="mhid">10</td></tr>')


def list44(rows, total, last):
    return ('<script>function fn_view(seqnum, cbub_code){}</script><div class="result">총 %d건 (1/%dpage)</div>'
            '<table class="tableHor"><tbody>%s</tbody></table>'
            '<a class="prev" href="?pageIndex=%d" onclick="fn_egov_select_brdMstr(%d);return false; " title="마지막 페이지"></a>'
            % (total, last, ''.join(rows), last, last))


def rownews(no, seq, gubun, title, author, day, empty_cell=False):
    return (f'<tr><td class="mhid">{no}</td>' + ('<td class="tit"> </td>' if empty_cell else '') +
            f'<td class="tit"><a href=\'/portal/news/NewsViewAction.work?pageIndex=1&amp;searchWord=&amp;searchOption=&amp;seqnum={seq}'
            f'&amp;gubun={gubun}&amp;type=5\' > {title} </a></td><td class="mhid"> {author} </td><td> {day} </td>'
            '<td class="attach mhid"><img src="/portal/common/images/attfile.gif" alt="첨부파일있음" /></td><td class="mhid"> 3 </td></tr>')


def listnews(rows, last=1):
    return ('<table class="tableHor"><tbody>%s</tbody></table>' % ''.join(rows) +
            '<a class="prev" onclick="fn_egov_select_brdMstr(%d);return false; " title="마지막 페이지"></a>' % last)


VIEW44 = """<script>function download(file,name){
  var form = document.downForm;
  form.file.value= file;
  form.path.value='003';
  form.action="https://file.scourt.go.kr//AttachDownload";
 }</script>
<table class="tableVer" summary="전국법원 주요판결 내용"><caption>x</caption>
<tr><th>제목</th><td colspan="3">[노동] 징계해고를 무효라고 판단한 사안(남원지원 2026가합1002)</td></tr>
<tr><th>작성자</th><td>전주지방법원</td><th>작성일</th><td>2026-11-10</td></tr>
<tr><th>첨부파일</th><td colspan="5" class="attTxt">&nbsp;[1]<a href="javascript:download('1794287520565_141200.pdf','(비실명화 변환)전주지방법원 남원지원_2026가합1002.pdf')">(비실명화 변환)전주지방법원 남원지원_2026가합1002.pdf</a><br /></td></tr>
<tr><td colspan="4" class="contArea"><p><span>○ </span><span>전주지방법원 남원지원 </span><span>2026. 10. 8. </span><span>선고 </span><span>2026</span><span>가합</span><span>1002 </span><span>판결</span></p>
<p>○ 재판부 판단</p><p> - 대법원 1991. 9. 10. 선고 91다10565 판결의 법리에 따라 징계해고를 무효로 봄.</p></td></tr></table>"""

VIEW4 = """<script>function download(file,name){ var form = document.downForm; form.path.value='001'; }</script>
<table class="tableVer"><tr><th>제목</th><td colspan="3">해고 사유의 서면 통지가 문제 된 사건[대법원 2026. 10. 30. 선고 중요판결]</td></tr>
<tr><th>작성자</th><td>법원도서관</td><th>작성일</th><td>2026-11-05</td></tr>
<tr><th>첨부파일</th><td colspan="3" class="attTxt">
<a href="https://www.scourt.go.kr/sjudge/1793877480310_201800.hwpx" target="_blank" >대법원_2026두31230_0_0(비실명).hwpx</a>
<a href="https://www.scourt.go.kr/sjudge/1793877480354_201800.pdf" target="_blank" >대법원_2026두31230_0_0(비실명).pdf</a></td></tr>
<tr><td colspan="4" class="contArea"><p>2026두31230&nbsp; &nbsp;부당해고구제재심판정취소&nbsp; &nbsp;(마)&nbsp; &nbsp;상고기각</p>
<p>1. 법리는 대법원 1991. 9. 10. 선고 91다10565 판결 참조.</p></td></tr></table>"""

VIEW2 = """<script>function download(file,name){ var form = document.downForm; form.file.value= file; form.path.value='001'; }</script>
<table class="tableVer"><tr><th>제목</th><td colspan="3">"근무시간만으론 산업재해 부정 못해"</td></tr>
<tr><th>작성일</th><td>2026-11-11</td></tr>
<tr><th>첨부파일</th><td colspan="3" class="attTxt"><a href="javascript:download('1794373829980_141029.pdf','2024두40400_판결문.pdf')">2024두40400_판결문.pdf</a></td></tr>
<tr><td colspan="4" class="contArea"></td></tr></table>"""

GONGBO_BODY = """2026. 10. 10. 각급법원(제1,2심) 판결공보 요약본 278호
[민사]
대전지법 2026. 9. 3. 선고 2025가합200819 판결 〔징계무효확인의소〕: 확정
서울고법 2026. 7. 10. 선고 2025나208215, 208216 판결 〔매매대금반환⋅기타분양대금청구의소〕: 상고
광주지법 2026. 9. 17. 선고 2022가합58532 판결 〔손해배상(기)〕: 항소
[일반행정]
서울행법 2026. 6. 24. 선고 2024구합56313 판결 〔해고예고수당청구〕: 확정"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / 'home'
        self.env = mock.patch.dict(os.environ, {'SCOURT_HOME': str(self.home)})
        self.env.start()
        self.delay = mock.patch.object(sc, 'DELAY', 0)
        self.delay.start()
        self.sent = []

    def tearDown(self):
        self.delay.stop()
        self.env.stop()
        self.tmp.cleanup()

    def site(self, pages):
        """pages: {(경로 앞부분, 검색어 또는 None): HTML 또는 (상태, 타입, 바이트)}. 보낸 요청은 self.sent 에 쌓인다."""
        def opener(url, data=None, timeout=60):
            parts = urllib.parse.urlsplit(url)
            form = urllib.parse.parse_qs(data.decode('ascii'), encoding='cp949') if data else {}
            word = (form.get('searchWord') or [''])[0]
            page = (form.get('pageIndex') or ['1'])[0]
            self.sent.append((parts.netloc + parts.path + ('?' + parts.query if parts.query else ''), word, page))
            if parts.path == '/robots.txt':
                if parts.netloc.startswith('lx.'):              # 법고을은 robots.txt 가 없다(404)
                    return 404, 'text/html', b''
                return 200, 'text/plain', (FILE_ROBOTS if parts.netloc.startswith('file.') else WWW_ROBOTS).encode()
            for (prefix, w, p), body in pages.items():
                if (parts.path + '?' + parts.query).startswith(prefix) and (w is None or w == word) and (p is None or p == page):
                    if isinstance(body, tuple):
                        return body
                    return 200, 'text/html; charset=euc-kr', body.encode('cp949')
            return 404, 'text/html', b'not found'
        return mock.patch.object(sc, 'OPEN', opener)


class ParseTest(Base):
    def test_list_pages_of_both_kinds(self):
        t = list44([row44(12, '28730', '000520', '[민사] 구상금 사안 ...', '전주지방법원'),
                    row44(11, '28729', '000220', '[행정][노동] 해고 사안 ...', '서울행정법원')], 12, 2)
        total, last, rows = sc.parse_list('주요판결', t)
        self.assertEqual((total, last, len(rows)), (12, 2, 2))
        self.assertEqual((rows[0]['seqnum'], rows[0]['법원코드'], rows[0]['게시']), ('28730', '000520', '전주지방법원'))
        t = listnews([rownews(55, '11255', '4', '정년 재고용 거절이 부당해고인지', '법원도서관', '2026-10-01'),
                      rownews(54, '11200', '2', '"근무시간만으론 산업재해 부정 못해"', '공보관실', '2026-09-01', empty_cell=True)], 6)
        total, last, rows = sc.parse_list('판례속보', t)
        self.assertEqual((total, last, len(rows)), (55, 6, 2))     # 검색 결과의 첫 줄 번호가 전체 건수이다
        self.assertEqual((rows[1]['seqnum'], rows[1]['게시일'], rows[1]['제목']), ('11200', '2026-09-01', '"근무시간만으론 산업재해 부정 못해"'))

    def test_last_page_is_found_without_the_last_button(self):
        """쪽이 적으면 '마지막 페이지' 단추가 없다. 2026. 11. 11. 주요판결 '강등' 17건에서 첫 쪽 10건만 받았다."""
        t = '<div class="result">총 17건 (1/2page)</div><table class="tableHor"><tbody>%s</tbody></table>' % row44(17, '9', '000220', 'x', '서울행정법원')
        self.assertEqual(sc.parse_list('주요판결', t)[:2], (17, 2))
        t = '<table class="tableHor"><tbody>%s</tbody></table>' % rownews(15, '9', '2', 'x', '공보관실', '2026-01-01', empty_cell=True)
        self.assertEqual(sc.parse_list('언론보도', t)[:2], (15, 2))
        self.assertEqual(sc.parse_list('언론보도', '<table class="tableHor"></table>')[:2], (0, 0))

    def test_level_from_court_or_case_type(self):
        self.assertEqual(sc.level('', '2024두40400'), '대법원')          # 언론보도판결은 법원 표시가 없다
        self.assertEqual(sc.level('', '2024구합1'), '하급심')
        self.assertEqual(sc.level('', '2025나208215'), '하급심')
        self.assertEqual(sc.level('서울행정법원', ''), '하급심')
        self.assertEqual(sc.level('', ''), '')

    def test_view_of_major_judgment_takes_the_first_line_not_a_cited_case(self):
        d = sc.parse_view('주요판결', VIEW44, '28730', '000520')
        self.assertEqual((d['기관'], d['일자'], d['사건번호']), ('전주지방법원 남원지원', '2026-10-08', '2026가합1002'))
        self.assertEqual(d['첨부'][0]['주소'], 'https://file.scourt.go.kr/dcboard/1794287520565_141200.pdf')   # AttachDownload 가 아니다
        self.assertTrue(d['링크'].endswith('seqnum=28730&cbub_code=000520'))

    def test_view_of_supreme_court_bulletin_uses_the_title_and_first_line(self):
        d = sc.parse_view('판례속보', VIEW4, '11387')
        self.assertEqual((d['기관'], d['일자'], d['사건번호']), ('대법원', '2026-10-30', '2026두31230'))
        self.assertEqual([a['주소'].rsplit('.', 1)[1] for a in d['첨부']], ['hwpx', 'pdf'])

    def test_view_of_press_judgment_reads_the_number_from_the_attachment(self):
        d = sc.parse_view('언론보도', VIEW2, '6347')
        self.assertEqual(d['사건번호'], '2024두40400')
        self.assertEqual(d['첨부'][0]['주소'], 'https://file.scourt.go.kr/nboard/1794373829980_141029.pdf')

    def test_gongbo_lines_expand_numbers_and_keep_status(self):
        got = sc.parse_gongbo(GONGBO_BODY)
        self.assertEqual([g['사건번호'] for g in got], ['2025가합200819', '2025나208215', '2025나208216', '2022가합58532', '2024구합56313'])
        self.assertEqual([g['확정'] for g in got], ['확정', '상고', '상고', '항소', '확정'])
        self.assertEqual(got[3]['사건명'], '손해배상(기)')        # 괄호가 든 사건명
        self.assertEqual(sc.case_info('판례속보', '2026. 10. 10. 각급법원(제1,2심) 판결공보 요약본', GONGBO_BODY)['사건번호'], '')

    def test_robots_longest_rule_wins(self):
        rules = sc.parse_robots(FILE_ROBOTS)
        self.assertTrue(sc.robots_decide(rules, '/dcboard/1.pdf'))
        self.assertTrue(sc.robots_decide(rules, '/nboard/2.pdf'))
        self.assertFalse(sc.robots_decide(rules, '//AttachDownload'))
        self.assertFalse(sc.robots_decide(rules, '/AttachDownload'))
        rules = sc.parse_robots(WWW_ROBOTS)          # AhrefsBot 묶음의 'Disallow: /' 는 우리에게 해당하지 않는다
        self.assertTrue(sc.robots_decide(rules, '/portal/news/NewsListAction.work?gubun=4'))
        self.assertTrue(sc.robots_decide(rules, '/sjudge/1.pdf'))
        self.assertFalse(sc.robots_decide(rules, '/news/x'))

    def test_hwpx_text(self):
        p = Path(self.tmp.name) / 'a.hwpx'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('Contents/section0.xml', '<hs:sec><hp:p><hp:run><hp:t>대 법 원</hp:t></hp:run></hp:p>'
                                                '<hp:p><hp:run><hp:t>상고를 기각한다.</hp:t><hp:t> &amp; 끝</hp:t></hp:run></hp:p></hs:sec>')
        self.assertEqual(sc.hwpx_text(p), '대 법 원\n상고를 기각한다. & 끝')


LX_PAGE = """<span class="num">2</span>건 <input type="hidden" id="search_cnt_hidden" value="2"> 이 검색되었습니다
<ul class="search_result_list">
<li class="search_result_item" id="3303168"> <div class="tit_wrap"> <div class="tit"> <span class="ctg ctg_green_ty01">서울고등법원</span>
<a class="ellipsis wrap" href="javascript:void(0);" onclick="showViewerPopup('P01', '/search/detail/precedent/0/3303168','3303168');" title="새 창">
 2023. 1. 20. 선고 2021누63022 판결 [신분보장등조치결정취소소송] </a> </div> </div> <div class="txt_wrap" data-limit="270"> 요약정보가 존재하지 않습니다. </div>
<ul class="btns"><li>저장</li></ul></li>
<!-- 줄 사이에 주석이 낀다 -->
<li class="search_result_item" id="3300001"> <div class="tit_wrap"> <div class="tit"> <span class="ctg ctg_blue">대법원</span>
<a class="ellipsis wrap" onclick="showViewerPopup('P01', '/search/detail/precedent/0/3300001','3300001');"> 2020. 6. 25. 선고 2016두56042 판결 [부당해고구제재심판정취소] </a>
</div> </div> <div class="txt_wrap"> [1] 징계혐의 사실을 통지할 의무가 있는지 여부(소극) </div></li>
</ul>"""


class LxTest(Base):
    def test_lx_list_and_harvest(self):
        total, rows = sc.parse_lx(LX_PAGE)
        self.assertEqual(total, 2)
        self.assertEqual([(r['기관'], r['일자'], r['사건번호'], r['사건명']) for r in rows],
                         [('서울고등법원', '2023-01-20', '2021누63022', '신분보장등조치결정취소소송'),
                          ('대법원', '2020-06-25', '2016두56042', '부당해고구제재심판정취소')])
        self.assertEqual(rows[0]['요지'], '')                                # '요약정보가 존재하지 않습니다'는 비운다
        self.assertEqual(rows[1]['링크'], 'https://lx.scourt.go.kr/search/detail/precedent/0/3300001')
        out = Path(self.tmp.name) / 'o'
        with self.site({('/search/precedent/get/list', None, None): LX_PAGE}):
            r = sc.harvest(['징계'], ['법고을'], out=str(out))
        got = json.loads((out / '법원_목록.json').read_text(encoding='utf-8'))['법고을']['rows']
        self.assertEqual([x['심급'] for x in got], ['하급심', '대법원'])
        self.assertEqual(r['게시판별']['법고을']['하급심'], 1)
        self.assertIn('lx.scourt.go.kr/robots.txt', [s[0] for s in self.sent])   # robots.txt 를 먼저 본다(없으면 막은 곳이 없다)


class RequestTest(Base):
    def test_spacing_daily_cap_and_robots(self):
        with self.site({('/portal/x', None, None): '<table class="tableHor"></table>'}), mock.patch.object(sc, 'DAILY_MAX', 3):
            sc._request('https://www.scourt.go.kr/portal/x', expect='tableHor')
            with self.assertRaisesRegex(sc.ScourtError, 'robots'):
                sc._request('https://www.scourt.go.kr/news/x')
            self.assertNotIn('www.scourt.go.kr/news/x', [s[0] for s in self.sent])      # 막힌 주소는 보내지 않는다
            sc._request('https://www.scourt.go.kr/portal/x', expect='tableHor')
            with self.assertRaisesRegex(sc.ScourtError, '하루 상한'):                  # robots.txt 요청도 센다
                sc._request('https://www.scourt.go.kr/portal/x', expect='tableHor')
        self.assertEqual(sc.usage()['count'], 3)

    def test_block_page_stops_and_marker_prevents_more_requests(self):
        with self.site({('/portal/a', None, None): '<html>자동입력 방지 문자를 입력하십시오</html>',
                        ('/portal/b', None, None): (429, 'text/html', b'')}):
            with self.assertRaisesRegex(sc.ScourtError, '멈춤'):
                sc._request('https://www.scourt.go.kr/portal/a', expect='tableHor')
            self.assertTrue(sc.stop_marker().is_file())
            n = len(self.sent)
            with self.assertRaisesRegex(sc.ScourtError, '멈춤 표시'):
                sc._request('https://www.scourt.go.kr/portal/b', expect='tableHor')
            self.assertEqual(len(self.sent), n)
            sc.stop_marker().unlink()
            with self.assertRaisesRegex(sc.ScourtError, 'HTTP 429'):
                sc._request('https://www.scourt.go.kr/portal/b', expect='tableHor')
            self.assertTrue(sc.stop_marker().is_file())

    def test_unexpected_page_without_block_words_is_an_error_not_a_stop(self):
        with self.site({('/portal/a', None, None): '<html>점검 중</html>'}):
            with self.assertRaisesRegex(sc.ScourtError, '예상한 화면'):
                sc._request('https://www.scourt.go.kr/portal/a', expect='tableHor')
        self.assertFalse(sc.stop_marker().is_file())


class HarvestTest(Base):
    def pages(self):
        p1 = list44([row44(3, '300', '000220', '[노동] 징계해고 사안 ...', '서울행정법원'),
                     row44(2, '200', '000210', '[노동] 정직 처분 사안 ...', '서울중앙지방법원')], 3, 2)
        p2 = list44([row44(1, '100', '000220', '[노동] 해고 사안 ...', '서울행정법원')], 3, 2)
        q2 = list44([row44(1, '200', '000210', '[노동] 정직 처분 사안 ...', '서울중앙지방법원')], 1, 1)
        v = lambda title, first: VIEW44.replace('[노동] 징계해고를 무효라고 판단한 사안(남원지원 2026가합1002)', title).replace(
            '<span>전주지방법원 남원지원 </span><span>2026. 10. 8. </span><span>선고 </span><span>2026</span><span>가합</span><span>1002 </span>', first)
        return {
            ('/portal/dcboard/DcNewsListAction.work', '해고', '1'): p1,
            ('/portal/dcboard/DcNewsListAction.work', '해고', '2'): p2,
            ('/portal/dcboard/DcNewsListAction.work', '정직', '1'): q2,
            ('/portal/dcboard/DcNewsViewAction.work?gubun=44&seqnum=200', None, None):
                v('[노동] 정직 처분을 취소한 사안(서울중앙지방법원 2025가합100)', '서울중앙지방법원 2026. 5. 1. 선고 2025가합100 '),
            ('/portal/dcboard/DcNewsViewAction.work?gubun=44&seqnum=300', None, None):
                v('[노동] 징계해고 사안(서울행정법원 2025구합300)', '서울행정법원 2026. 6. 1. 선고 2025구합300 '),
        }

    def test_harvest_ranks_rows_hit_by_more_queries_and_writes_the_list(self):
        out = Path(self.tmp.name) / '사건' / '라운드1' / '작업' / '법원'
        with self.site(self.pages()):
            r = sc.harvest(['해고', '정직'], ['주요판결'], views=2, out=str(out))
        listing = json.loads((out / '법원_목록.json').read_text(encoding='utf-8'))
        rows = listing['주요판결']['rows']
        self.assertEqual([x['seqnum'] for x in rows], ['200', '300', '100'])      # 두 검색어에 걸린 글이 앞이다
        self.assertEqual((rows[0]['사건번호'], rows[0]['기관'], rows[0]['일자']), ('2025가합100', '서울중앙지방법원', '2026-05-01'))
        self.assertEqual(rows[0]['검색어'], '해고 / 정직')
        self.assertFalse(rows[2]['상세'])                                          # views=2 라 셋째는 열지 않았다
        self.assertEqual(r['게시판별']['주요판결']['상세'], 2)
        self.assertEqual(listing['주요판결']['검색'][0], {'검색어': '해고', '전체': 3, '받은건수': 3})
        # 같은 날 다시 돌리면 목록·게시물을 캐시에서 읽는다
        n = len(self.sent)
        with self.site(self.pages()):
            sc.harvest(['해고', '정직'], ['주요판결'], views=2, out=str(out))
        self.assertEqual(len(self.sent), n)
        # harvest_titles.py 가 법원 목록을 읽는다(열지 않은 글은 번호가 없다)
        files, got = ht.load_court(str(out.parents[2]))
        self.assertEqual(len(files), 1)
        self.assertEqual([g['id'] for g in got], ['2025가합100', '2025구합300', ''])
        self.assertEqual(got[0]['src'], '법원-주요판결')

    def test_gongbo_rows_come_from_the_index_without_requests(self):
        idx = {'게시물': {'11351': {'제목': '2026. 10. 10. 각급법원(제1,2심) 판결공보 요약본', '게시일': '2026-10-13', '링크': 'x',
                                    '첨부': [], '사건': sc.parse_gongbo(GONGBO_BODY)}}}
        sc.write(sc.gongbo_index_path(), json.dumps(idx, ensure_ascii=False))
        with self.site({}):
            r = sc.harvest(['징계', '해고'], ['공보'], out=str(Path(self.tmp.name) / 'o'))
        self.assertEqual(self.sent, [])
        rows = json.loads((Path(self.tmp.name) / 'o' / '법원_목록.json').read_text(encoding='utf-8'))['공보']['rows']
        self.assertEqual([(x['사건번호'], x['확정']) for x in rows], [('2025가합200819', '확정'), ('2024구합56313', '확정')])
        self.assertEqual(r['게시판별']['공보']['확정'], 2)
        got = sc.gongbo_lookup(['2025나 208216', '2099가합1'])         # 사건번호로 확정 표시를 찾는다(뒤 번호만 적은 줄도 펼쳐 둔다)
        self.assertEqual([(g['사건번호'], g['확정']) for g in got], [('2025나208216', '상고')])

    def test_judgment_text_prefers_text_layer_then_hwpx(self):
        import pymupdf
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), 'judgment text ' * 10)
        good = pdf.tobytes()
        empty = pymupdf.open()
        empty.new_page()
        blank = empty.tobytes()
        hw = Path(self.tmp.name) / 'h.hwpx'
        with zipfile.ZipFile(hw, 'w') as z:
            z.writestr('Contents/section0.xml', '<hp:p><hp:t>한글 판결문</hp:t></hp:p>')
        folder = Path(self.tmp.name) / 'case'
        d = sc.parse_view('판례속보', VIEW4, '11387')
        with self.site({('/sjudge/1793877480354_201800.pdf', None, None): (200, 'application/pdf', good),
                        ('/sjudge/1793877480310_201800.hwpx', None, None): (200, 'application/octet-stream', hw.read_bytes())}):
            t = sc.judgment_text(d, folder)
        self.assertTrue(t['글출처'].startswith('글자층'))
        self.assertIn('judgment text', t['글'])
        self.assertTrue((folder / '판결문' / '대법원_2026두31230_0_0(비실명).pdf').is_file())
        # PDF 에 글자층이 없으면(문자인식도 못 하면) hwpx 의 글을 쓴다
        for f in list((sc.home() / '파일').glob('*')) + list((folder / '판결문').glob('*')):
            f.unlink()
        with self.site({('/sjudge/1793877480354_201800.pdf', None, None): (200, 'application/pdf', blank),
                        ('/sjudge/1793877480310_201800.hwpx', None, None): (200, 'application/octet-stream', hw.read_bytes())}), \
                mock.patch.object(sc, 'ocr_pdf', lambda doc: None):
            t = sc.judgment_text(d, folder)
        self.assertTrue(t['글출처'].startswith('hwpx'))
        self.assertEqual(t['글'], '한글 판결문')
        md = sc.markdown(d, t)
        self.assertTrue(md.startswith('## [판례속보] 대법원 2026-10-30 2026두31230 '))
        self.assertIn('법원·법원도서관이 쓴 요지. 판결의 판단이 아니다', md)


class CliTest(unittest.TestCase):
    def test_out_must_be_a_folder(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / '법원_목록.json'
            r = subprocess.run([sys.executable, '-B', str(ROOT / '공통/scripts/scourt.py'), 'harvest', '--query', '해고', '--out', str(out)],
                               capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'SCOURT_HOME': d}, timeout=60)
            self.assertEqual(r.returncode, 2, r.stderr.decode('utf-8', 'replace'))
            self.assertIn('--out 은 폴더 이름이다', r.stderr.decode('utf-8', 'replace'))
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
