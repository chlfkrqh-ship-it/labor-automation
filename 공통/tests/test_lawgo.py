import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.parse
from unittest import mock

spec = importlib.util.spec_from_file_location('lawgo', Path(__file__).parents[1] / 'scripts' / 'lawgo.py')
lawgo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lawgo)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def prec(n, court='대법원', number=None, source='대법원', date='2021.11.25', ident=None):
    return {'id': str(n), '판례일련번호': str(ident or 1000 + n), '사건명': f'사건{n}', '사건번호': number or f'2020다{n}',
            '선고일자': date, '법원명': court, '데이터출처명': source, '판결유형': '판결'}


class LawGoTests(unittest.TestCase):
    """네트워크 없이 가짜 응답으로 시험한다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: os.environ.get(k) for k in ('LAWGO_HOME', 'LAWGO_OC')}
        os.environ['LAWGO_HOME'] = self.tmp.name
        os.environ['LAWGO_OC'] = 'tester'
        self.calls, self.routes = [], {}
        self.patches = [mock.patch.object(lawgo, 'OPENER', self.opener), mock.patch.object(lawgo, 'DELAY', 0)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def opener(self, request, timeout=None):
        url = urllib.parse.urlsplit(request.full_url)
        q = dict(urllib.parse.parse_qsl(url.query))
        path = url.path.rsplit('/', 1)[-1]
        self.calls.append(dict(q, path=path))
        if path == 'lawSearch.do':
            key = ('list', q['target'], q.get('query', ''), q.get('page', '1'))
        else:
            key = ('info', q['target'], q.get('ID') or q.get('MST'), q['type'])
        payload = self.routes[key]
        return Response((payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)).encode('utf-8'))

    def test_search_pages_until_total_and_normalizes(self):
        self.routes[('list', 'prec', '해고', '1')] = {'PrecSearch': {'totalCnt': '150', 'prec': [prec(n) for n in range(1, 101)]}}
        self.routes[('list', 'prec', '해고', '2')] = {'PrecSearch': {'totalCnt': '150', 'prec': [prec(n) for n in range(101, 151)]}}
        result = lawgo.search('판례', '해고', body=True, court='대법원', limit=300)
        self.assertEqual((result['전체'], result['받은건수']), (150, 150))
        self.assertEqual(len(self.calls), 2)
        first = self.calls[0]
        self.assertEqual((first['search'], first['org'], first['display'], first['sort'], first['OC'], first['type']),
                         ('2', '400201', '100', 'ddes', 'tester', 'JSON'))
        row = result['rows'][0]
        self.assertEqual((row['id'], row['일자'], row['기관']), ('1001', '2021-11-25', '대법원'))
        self.assertEqual(row['lbox'], 'https://lbox.kr/case/대법원/2020다1')

    def test_limit_stops_paging(self):
        self.routes[('list', 'prec', '해고', '1')] = {'PrecSearch': {'totalCnt': '500', 'prec': [prec(n) for n in range(1, 31)]}}
        result = lawgo.search('판례', '해고', limit=30)
        self.assertEqual((result['받은건수'], len(self.calls), self.calls[0]['display']), (30, 1, '30'))

    def test_single_result_comes_as_object(self):
        self.routes[('list', 'nlrc', '부당해고', '1')] = {'Nlrc': {'totalCnt': '1', 'nlrc': {
            'id': '1', '결정문일련번호': '32911', '제목': '부당해고 구제 재심신청', '사건번호': '중앙2018부해OOO', '등록일': '2018.11.16'}}}
        result = lawgo.search('nlrc', '부당해고')
        self.assertEqual(result['종류'], '노동위')
        self.assertEqual([(r['id'], r['일자']) for r in result['rows']], [('32911', '2018-11-16')])

    def test_no_result_and_auth_error(self):
        self.routes[('list', 'eiac', '없는말', '1')] = {'Eiac': {'totalCnt': '0', 'section': 'evtNm'}}
        self.assertEqual(lawgo.search('고용보험심사', '없는말')['rows'], [])
        self.routes[('list', 'prec', '해고', '1')] = {'result': '사용자 정보 검증에 실패하였습니다.',
                                                     'msg': 'OPEN API 호출 시 사용자 검증을 위하여 정확한 서버장비의 IP주소 및 도메인주소를 등록해 주세요.'}
        with self.assertRaises(lawgo.LawGoError) as caught:
            lawgo.search('판례', '해고')
        self.assertIn('IP주소', str(caught.exception))

    def test_show_converts_html_caches_and_reports_not_found(self):
        self.routes[('info', 'prec', '228521', 'JSON')] = {'PrecService': {
            '판례정보일련번호': '228521', '사건명': '손해배상(기)', '사건번호': '2020다270503', '선고일자': '20211125',
            '법원명': '대법원', '판결요지': '가.<br/>나. &lt;인용&gt;', '판례내용': '【주 문】<br/><br/><br/>상고를 기각한다.', '참조판례': ''}}
        doc = lawgo.show('판례', '228521')
        self.assertEqual(doc['본문']['판결요지'], '가.\n나. <인용>')
        self.assertEqual(doc['본문']['판례내용'], '【주 문】\n\n상고를 기각한다.')
        self.assertNotIn('참조판례', doc['본문'])
        self.assertEqual((doc['id'], doc['일자'], doc['lbox']), ('228521', '2021-11-25', 'https://lbox.kr/case/대법원/2020다270503'))
        lawgo.show('판례', '228521')
        self.assertEqual(len(self.calls), 1, 'cached body was requested again')
        lawgo.show('판례', '228521', refresh=True)
        self.assertEqual(len(self.calls), 2)
        self.routes[('info', 'prec', '999', 'JSON')] = {'Law': '일치하는 판례가 없습니다.  판례명을 확인하여 주십시오.'}
        self.routes[('info', 'prec', '999', 'HTML')] = '<html><body>국가법령통합관리시스템 일치하는 판례가 없습니다.</body></html>'
        with self.assertRaises(lawgo.LawGoError) as caught:
            lawgo.show('판례', '999')
        self.assertIn('일치하는 판례가 없습니다', str(caught.exception))
        self.assertFalse((Path(self.tmp.name) / '캐시' / 'lawgo' / 'prec' / '999.json').exists())

    IFRAME = ('<html><head><script>$(document).ready(function(){ var url = "mobilePrecInfoR.do"; ' + 'x' * 400 + ' });</script>'
              '</head><body><iframe src="https://www.law.go.kr/LSW/precInfoP.do?precSeq=555&mode=0"></iframe></body></html>')

    def test_precedent_without_api_body_is_reported_not_cached(self):
        self.routes[('info', 'prec', '555', 'JSON')] = {'Law': '일치하는 판례가 없습니다.  판례명을 확인하여 주십시오.'}
        self.routes[('info', 'prec', '555', 'HTML')] = self.IFRAME
        with self.assertRaises(lawgo.LawGoError) as caught:
            lawgo.show('판례', '555')
        self.assertIn('API로 본문이 제공되지 않는 판례', str(caught.exception))
        self.assertFalse((Path(self.tmp.name) / '캐시' / 'lawgo' / 'prec' / '555.json').exists())
        self.routes[('info', 'prec', '557', 'JSON')] = '<html>JSON 아님</html>'
        self.routes[('info', 'prec', '557', 'HTML')] = '<html><body>' + '판결 본문입니다. ' * 40 + '</body></html>'
        self.assertGreater(len(lawgo.show('판례', '557')['본문']['판례내용']), 200)
        self.routes[('info', 'prec', '556', 'JSON')] = {'result': '사용자 정보 검증에 실패하였습니다.', 'msg': 'IP를 등록해 주세요.'}
        with self.assertRaises(lawgo.LawGoError):
            lawgo.show('판례', '556')
        self.assertFalse(any(c.get('ID') == '556' and c['type'] == 'HTML' for c in self.calls))

    def test_to_text_keeps_article_annotations(self):
        self.assertEqual(lawgo.to_text('① 뜻은 다음과 같다. <개정 2018.3.20><br/>부칙 <제8372호,2007.4.11> <span class="x">본문</span>'),
                         '① 뜻은 다음과 같다. <개정 2018.3.20>\n부칙 <제8372호,2007.4.11> 본문')

    def test_cited_cases_extracts_court_and_numbers(self):
        text = ('대법원 2012. 3. 29. 선고 2011두2132, 2011두2149 판결(공2012상, 123), 서울고등법원 2019. 10. 10. 선고 2019누1234 판결 참조. '
                '같은 날 선고 2019누1235 판결. 2019년3월 사건이다. 헌법재판소 2015. 3. 26. 선고 2014헌바202 결정, 대법원 1991. 3. 27. 선고 90다카25420 판결')
        self.assertEqual(lawgo.cited_cases(text), [('대법원', '2011두2132'), ('대법원', '2011두2149'), ('서울고등법원', '2019누1234'),
                                                   ('서울고등법원', '2019누1235'), ('헌법재판소', '2014헌바202'), ('대법원', '90다카25420')])
        self.assertEqual(lawgo.cited_cases('2019년 3월 12일 근로계약 제3조 제2항'), [])

    def test_case_number_comes_from_system(self):
        """사건번호 정규식은 공통/scripts/system.py 한 곳에 둔다(citation_check 와 같은 정의)."""
        spec = importlib.util.spec_from_file_location('workflow_system', Path(__file__).parents[1] / 'scripts' / 'system.py')
        system = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(system)
        self.assertEqual((lawgo.CASE_NUMBER.pattern, lawgo.CASE_TYPES), (system.CASE_NUMBER, system.CASE_TYPES))
        # 부호 앞뒤 공백은 지워서 돌려준다
        self.assertEqual(lawgo.cited_cases('수원지방법원 2019. 1. 1. 선고 2018노 3955 판결, 대법원 1990. 1. 1. 선고 87다카2132 판결'),
                         [('수원지방법원', '2018노3955'), ('대법원', '87다카2132')])

    def test_call_retries_dropped_connection(self):
        """응답 도중 끊긴 연결(RemoteDisconnected·IncompleteRead)도 다시 시도한다."""
        class Broken(Response):
            def read(self, *args):
                raise http.client.IncompleteRead(b'{"Prec')

        payload = json.dumps({'PrecSearch': {'totalCnt': '1', 'prec': [prec(1)]}}).encode('utf-8')
        for failure in (http.client.RemoteDisconnected('Remote end closed connection without response'),
                        ConnectionResetError(104, 'Connection reset by peer'), Broken(b'')):
            attempts = []

            def flaky(request, timeout=None):
                attempts.append(request.full_url)
                if len(attempts) == 1:
                    if isinstance(failure, Exception):
                        raise failure
                    return failure
                return Response(payload)

            with self.subTest(failure=type(failure).__name__), mock.patch.object(lawgo, 'OPENER', flaky), \
                    mock.patch.object(lawgo.time, 'sleep'):
                result = lawgo.search('판례', '통상임금')
                self.assertEqual((len(attempts), result['받은건수']), (2, 1))

    def test_call_gives_up_as_connection_failure(self):
        def dropped(request, timeout=None):
            raise http.client.RemoteDisconnected('Remote end closed connection without response')

        with mock.patch.object(lawgo, 'OPENER', dropped), mock.patch.object(lawgo.time, 'sleep'):
            with self.assertRaises(lawgo.LawGoError) as caught:
                lawgo.search('판례', '통상임금')
        self.assertTrue(str(caught.exception).startswith('연결 실패'))

    def test_cited_cases_ignores_lbox_header_and_uncited_numbers(self):
        # 2026. 9. 17. LBOX 보관 본문의 머리 모양: 화면 글자가 법원명에 붙고, 상·하위 판결 목록에는 '선고'가 없다
        text = ('판례새 작업락보서울남부지방법원 2020. 11. 25. 선고 2018가단249593 판결[약정금]1상•하위 판결1확정원고패서울남부지방법원 '
                '2018가단249593인용된 판례2항소기각서울고등법원 2023나2017596 … 해석하여야 한다(대법원 2000. 11. 10. 선고 98다31493 판결, '
                '대법원 2001. 3. 23. 선고 2000다40858 판결 등 참조). 【원심판결】 의정부지법 2021. 2. 15. 선고 2019노3688 판결. '
                '대법원 1992. 2. 28.자 91마123 결정, 사건 2023가합1234 참고')
        self.assertEqual(lawgo.cited_cases(text), [('서울남부지방법원', '2018가단249593'), ('대법원', '98다31493'), ('대법원', '2000다40858'),
                                                   ('의정부지방법원', '2019노3688'), ('대법원', '91마123')])

    def test_citation_ranking_counts_citing_decisions_once(self):
        docs = [{'기관': '대법원', '사건번호': '2020다1', '본문': {'판례내용': '대법원 2012. 3. 29. 선고 2011두2132 판결, 대법원 2010. 1. 1. 선고 2010다100 판결 참조. 다시 대법원 2012. 3. 29. 선고 2011두2132 판결'}},
                {'기관': '대법원', '사건번호': '2021다2', '본문': {'참조판례': '대법원 2012. 3. 29. 선고 2011두2132 판결', '판례내용': '대법원 2020. 5. 5. 선고 2020다1 판결'}},
                {'기관': '대법원', '사건번호': '2011두2132', '본문': {'판례내용': '대법원 2012. 3. 29. 선고 2011두2132 판결(자기 사건)'}}]
        ranking = lawgo.citation_ranking(docs, [{'기관': '대법원', '사건번호': '2010다100'}])
        self.assertEqual([(r['사건번호'], r['인용건수'], r['목록에있음']) for r in ranking],
                         [('2011두2132', 2, False), ('2010다100', 1, True), ('2020다1', 1, False)])
        self.assertEqual((ranking[0]['인용한판결'], ranking[0]['lbox']), (['대법원 2020다1', '대법원 2021다2'], 'https://lbox.kr/case/대법원/2011두2132'))
        # 건수가 같으면 사건번호 순이 아니라 앞쪽 본문이 먼저 인용한 순서, 다만 대법원이 먼저
        docs = [{'기관': '대법원', '사건번호': '2022다1', '본문': {'판례내용': '서울고법 2019. 1. 1. 선고 2018나7 판결, 대법원 2015. 1. 1. 선고 2015다9 판결'}},
                {'기관': '대법원', '사건번호': '2022다2', '본문': {'판례내용': '대법원 2001. 1. 1. 선고 2000다3 판결'}}]
        self.assertEqual([(r['법원'], r['사건번호']) for r in lawgo.citation_ranking(docs)],
                         [('대법원', '2015다9'), ('대법원', '2000다3'), ('서울고등법원', '2018나7')])

    def test_dates_are_normalized(self):
        self.assertEqual([lawgo.ymd(x) for x in ('2021.11.25', '20211125', '2026.8.4.', '2018.11.16.', '', '미상', '0001.01.01')],
                         ['2021-11-25', '2021-11-25', '2026-08-04', '2018-11-16', '', '미상', ''])

    def test_harvest_skips_tax_bodies_and_records_failures(self):
        tax = prec(3, court='', number='서울행정법원-2025-구합-3', source='국세법령정보시스템', date='2026.01.01', ident=3003)
        self.routes[('list', 'prec', 'A', '1')] = {'PrecSearch': {'totalCnt': '3', 'prec': [tax, prec(1, date='2025.01.01'), prec(2, date='2024.01.01')]}}
        self.routes[('info', 'prec', '1001', 'JSON')] = {'Law': '일치하는 판례가 없습니다.'}
        self.routes[('info', 'prec', '1001', 'HTML')] = self.IFRAME
        self.routes[('info', 'prec', '1002', 'JSON')] = {'PrecService': {'판례정보일련번호': '1002', '사건번호': '2020다2', '법원명': '대법원', '판결요지': '요지'}}
        result = lawgo.harvest(['판례'], ['A'], texts=5)
        summary = result['종류별']['판례']
        self.assertEqual((summary['본문'], summary['국세판례_본문미제공']), (1, 1))
        self.assertEqual([f['id'] for f in summary['본문실패']], ['1001'])
        self.assertFalse(any(c.get('ID') == '3003' for c in self.calls))

    def test_harvest_orders_by_query_count_then_narrow_query_then_date(self):
        broad = [prec(n, date='2026.01.0' + str(n)) for n in range(1, 4)]                  # 넓은 검색어: 최신 판결 3건
        self.routes[('list', 'prec', '넓은', '1')] = {'PrecSearch': {'totalCnt': '250', 'prec': broad + [prec(9, date='2000.01.01')]}}
        self.routes[('list', 'prec', '좁은', '1')] = {'PrecSearch': {'totalCnt': '2', 'prec': [prec(7, date='2001.01.01'), prec(9, date='2000.01.01')]}}
        self.routes[('info', 'prec', '1009', 'JSON')] = {'PrecService': {'판례정보일련번호': '1009', '사건번호': '2020다9', '사건명': '보험료', '법원명': '대법원'}}
        result = lawgo.harvest(['판례'], ['넓은', '좁은'], limit=4, texts=1)
        rows = result['목록']['판례']['rows']
        self.assertEqual([r['사건번호'] for r in rows], ['2020다9', '2020다7', '2020다3', '2020다2', '2020다1'])
        self.assertEqual(result['종류별']['판례']['본문목록'], ['대법원 2020다9 보험료'])

    def test_harvest_texts_title_picks_bodies_by_case_name(self):
        rows = [prec(1, date='2026.01.01'), prec(2, date='2025.01.01'), prec(3, date='2024.01.01')]
        for row, name in zip(rows, ('사기', '산재보험료 부과처분 취소', '근로자지위확인')):
            row['사건명'] = name
        self.routes[('list', 'prec', 'A', '1')] = {'PrecSearch': {'totalCnt': '3', 'prec': rows}}
        self.routes[('info', 'prec', '1002', 'JSON')] = {'PrecService': {'판례정보일련번호': '1002', '사건번호': '2020다2', '사건명': '산재보험료 부과처분 취소', '법원명': '대법원'}}
        result = lawgo.harvest(['판례'], ['A'], texts=5, texts_title=['보험료부과', '사업종류'])
        summary = result['종류별']['판례']
        self.assertEqual((summary['본문'], summary['본문후보']), (1, '사건명에 보험료부과·사업종류 가운데 하나가 든 1건'))
        self.assertEqual([c.get('ID') for c in self.calls if c['path'] == 'lawService.do'], ['1002'])
        self.assertEqual(len(result['목록']['판례']['rows']), 3)          # 목록은 거르지 않는다

    def test_harvest_exclude_drops_case_from_list_bodies_and_ranking(self):
        self.routes[('list', 'prec', 'A', '1')] = {'PrecSearch': {'totalCnt': '2', 'prec': [
            prec(1, number='2020다1, 2020다9', date='2025.01.01'), prec(2, date='2024.01.01')]}}
        self.routes[('info', 'prec', '1002', 'JSON')] = {'PrecService': {
            '판례정보일련번호': '1002', '사건번호': '2020다2', '법원명': '대법원',
            '판례내용': '대법원 2020. 1. 1. 선고 2020다1 판결, 대법원 2010. 1. 1. 선고 2010다5 판결'}}
        result = lawgo.harvest(['판례'], ['A'], texts=5, exclude={'2020다9'})
        listing = result['목록']['판례']
        self.assertEqual([r['사건번호'] for r in listing['rows']], ['2020다2'])
        self.assertFalse(any(c.get('ID') == '1001' for c in self.calls))
        self.assertEqual([r['사건번호'] for r in listing['인용순위']], ['2020다1', '2010다5'])
        result = lawgo.harvest(['판례'], ['A'], texts=5, exclude={'2020다1'})
        self.assertEqual([r['사건번호'] for r in result['목록']['판례']['인용순위']], ['2010다5'])

    def test_case_number_and_lbox_url(self):
        row = lawgo.normalize('판례', {'판례일련번호': '7', '사건번호': '서울행정법원-2025-구합-53785', '법원명': '',
                                     '데이터출처명': '국세법령정보시스템', '선고일자': '2026.01.15'})
        self.assertEqual((row['기관'], row['사건번호'], row['lbox']),
                         ('서울행정법원', '2025구합53785', 'https://lbox.kr/case/서울행정법원/2025구합53785'))
        self.assertEqual(lawgo.lbox_url('대전고등법원 청주재판부', '2024누123,2024누124'),
                         'https://lbox.kr/case/대전고등법원청주재판부/2024누123')
        self.assertEqual(lawgo.lbox_url('', '2020다1'), '')

    def test_oc_resolution(self):
        self.assertEqual(lawgo.oc_value(), 'tester')
        self.assertEqual(lawgo.oc_value('given'), 'given')
        os.environ.pop('LAWGO_OC')
        with self.assertRaises(lawgo.LawGoError) as caught:
            lawgo.oc_value()
        self.assertIn('set-oc', str(caught.exception))
        lawgo.set_oc('saved')
        self.assertEqual(lawgo.oc_value(), 'saved')

    def test_period_number_and_filter_mapping(self):
        self.routes[('list', 'moelCgmExpc', '연차', '1')] = {'CgmExpc': {'totalCnt': '0'}}
        lawgo.search('노동부해석', '연차', period='20200101~20221231')
        self.assertEqual(self.calls[-1]['explYd'], '20200101~20221231')
        self.routes[('list', 'prec', '', '1')] = {'PrecSearch': {'totalCnt': '1', 'prec': prec(1, number='2020다270503')}}
        lawgo.search('판례', number='2020다270503')
        self.assertEqual(self.calls[-1]['nb'], '2020다270503')
        for bad in (dict(kind='노동위', period='20200101~20221231'), dict(kind='노동위', number='1'),
                    dict(kind='노동부해석', court='대법원'), dict(kind='판례', court='지방법원')):
            with self.assertRaises(lawgo.LawGoError):
                lawgo.search(bad.pop('kind'), '연차', **bad)
        with self.assertRaises(lawgo.LawGoError):
            lawgo.search('없는종류', '연차')

    def test_harvest_merges_duplicates_and_writes_files(self):
        tax = prec(5, court='', number='서울행정법원-2023-구합-5', source='국세법령정보시스템', date='2024.01.01', ident=2005)
        same = prec(5, court='서울행정법원', number='2023구합5', source='대법원', date='2024.01.01', ident=3005)
        self.routes[('list', 'prec', 'A', '1')] = {'PrecSearch': {'totalCnt': '3', 'prec': [prec(1), tax, prec(2, date='2021.01.01')]}}
        self.routes[('list', 'prec', 'B', '1')] = {'PrecSearch': {'totalCnt': '2', 'prec': [prec(2, date='2021.01.01'), same]}}
        self.routes[('info', 'prec', '3005', 'JSON')] = {'PrecService': {
            '판례정보일련번호': '3005', '사건명': '사건5', '사건번호': '2023구합5', '선고일자': '20240101', '법원명': '서울행정법원',
            '판결요지': '요지'}}
        out = Path(self.tmp.name) / '작업' / '법제처'
        result = lawgo.harvest(['판례'], ['A', 'B'], texts=1, out=str(out))
        self.assertEqual(result['호출'], 3)
        self.assertEqual(result['종류별']['판례']['합친건수'], 3)
        rows = json.loads((out / '법제처_목록.json').read_text(encoding='utf-8'))['판례']['rows']
        self.assertEqual([(r['id'], r['검색어']) for r in rows[:2]], [('3005', 'A / B'), ('1002', 'A / B')])
        self.assertEqual(rows[2]['검색어'], 'A')
        text = (out / '법제처_본문_판례.md').read_text(encoding='utf-8')
        self.assertIn('## [판례] 서울행정법원 2024-01-01 2023구합5 사건5', text)
        self.assertIn('- 검색어: A / B', text)

    LAWS = {'LawSearch': {'totalCnt': '2', 'law': [
        {'id': '1', '법령일련번호': '283457', '법령ID': '001872', '법령명한글': '근로기준법', '시행일자': '20260820',
         '공포일자': '20260219', '공포번호': '21065', '현행연혁코드': '현행', '소관부처명': '고용노동부', '법령구분명': '법률'},
        {'id': '2', '법령일련번호': '270551', '법령ID': '003058', '법령명한글': '근로기준법 시행령', '시행일자': '20251023'}]}}
    ARTICLE = {'법령': {'기본정보': {'법령명_한글': '근로기준법'}, '조문': {'조문단위': [
        {'조문여부': '전문', '조문내용': '          제6장의2 직장 내 괴롭힘의 금지 <신설 2019.1.15>'},
        {'조문여부': '조문', '조문내용': '제76조의2(직장 내 괴롭힘의 금지) 사용자 또는 근로자는 괴롭힘을 하여서는 아니 된다.',
         '조문참고자료': '[본조신설 2019.1.15]'}]}}}

    def test_jo_code_and_label(self):
        self.assertEqual([lawgo.jo_code(x) for x in ('76의2', '제76조의2', '제76조의 2', '23', '제2조')],
                         ['007602', '007602', '007602', '002300', '000200'])
        self.assertEqual((lawgo.jo_label('007602'), lawgo.jo_label('002300')), ('제76조의2', '제23조'))
        with self.assertRaises(lawgo.LawGoError):
            lawgo.jo_code('칠십육')

    def test_article_current_is_cached_by_version(self):
        self.routes[('list', 'law', '근로기준법', '1')] = self.LAWS
        self.routes[('info', 'lawjosub', '283457', 'JSON')] = self.ARTICLE
        doc = lawgo.article('근로기준법', '76의2')
        self.assertTrue(doc['조문'].startswith('제76조의2(직장 내 괴롭힘의 금지)'))
        self.assertIn('[본조신설 2019.1.15]', doc['조문'])
        self.assertNotIn('제6장의2', doc['조문'])
        self.assertEqual((doc['기준'], doc['시행일자'], doc['공포'], doc['링크']),
                         ('현행', '2026-08-20', '2026-02-19 제21065호', 'https://www.law.go.kr/법령/근로기준법/제76조의2'))
        self.assertEqual(self.calls[-1]['JO'], '007602')
        lawgo.article('근로기준법', '제76조의2')
        self.assertEqual([c['target'] for c in self.calls], ['law', 'lawjosub', 'law'])   # 조문은 보관함에서
        self.routes[('list', 'law', '근로기준법 시행규칙', '1')] = self.LAWS
        with self.assertRaises(lawgo.LawGoError) as caught:
            lawgo.article('근로기준법 시행규칙', '1')
        self.assertIn('후보: 근로기준법, 근로기준법 시행령', str(caught.exception))

    def test_article_as_of_date_picks_version(self):
        self.routes[('list', 'law', '근로기준법', '1')] = self.LAWS
        self.routes[('list', 'eflaw', '', '1')] = {'LawSearch': {'totalCnt': '4', 'law': [
            {'id': '1', '법령ID': '001872', '법령일련번호': '283457', '시행일자': '20260820', '법령명한글': '근로기준법'},
            {'id': '2', '법령ID': '001872', '법령일련번호': '206000', '시행일자': '20190716', '법령명한글': '근로기준법', '공포일자': '20190115', '공포번호': '16270'},
            {'id': '3', '법령ID': '001872', '법령일련번호': '205000', '시행일자': '20180529', '법령명한글': '근로기준법'},
            {'id': '4', '법령ID': '999999', '법령일련번호': '1', '시행일자': '20190801', '법령명한글': '다른법'}]}}
        self.routes[('info', 'eflawjosub', '206000', 'JSON')] = self.ARTICLE
        self.routes[('info', 'eflawjosub', '205000', 'JSON')] = {'법령': {'기본정보': {'법령명_한글': '근로기준법'}}}
        doc = lawgo.article('근로기준법', '76의2', date='2019-08-01')
        self.assertEqual((doc['기준'], doc['시행일자'], doc['공포']), ('2019-08-01', '2019-07-16', '2019-01-15 제16270호'))
        self.assertEqual((self.calls[-1]['efYd'], self.calls[-1]['JO'], self.calls[-2]['LID']), ('20190716', '007602', '001872'))
        with self.assertRaises(lawgo.LawGoError) as caught:
            lawgo.article('근로기준법', '76의2', date='20190101')
        self.assertIn('2019-01-01 당시 판본(시행 2018-05-29)에 없는 조문입니다', str(caught.exception))
        with self.assertRaises(lawgo.LawGoError):
            lawgo.article('근로기준법', '76의2', date='2019')

    def test_render_law_nested_units(self):
        out = lawgo.render_law({'조문': {'조문단위': [
            {'조문여부': '조문', '조문내용': '제2조(정의)', '항': [{'항내용': '① 뜻은 다음과 같다.', '호': [
                {'호내용': '1. "근로자"란 사람을 말한다.'},
                {'호내용': '2. 목이 있는 호', '목': [{'목내용': ['가. 첫째']}, {'목내용': '나. 둘째'}]}]}]},
            {'조문여부': '조문', '조문내용': '제3조(단일항)', '항': {'항내용': '② 단일 항'}}]},
            '부칙': {'부칙단위': [{'부칙내용': [['부칙 <제1호>', '제1조 시행']]}]},
            '별표': {'별표단위': {'별표구분': '별표', '별표제목': '표 제목', '별표서식PDF파일링크': '/LSW/flDownload.do?flSeq=1',
                               '별표내용': [['표 내용']]}}})
        self.assertEqual(out['조문'], '제2조(정의)\n① 뜻은 다음과 같다.\n1. "근로자"란 사람을 말한다.\n2. 목이 있는 호\n가. 첫째\n나. 둘째'
                                      '\n\n제3조(단일항)\n② 단일 항')
        self.assertEqual(out['부칙'], '부칙 <제1호>\n제1조 시행')
        self.assertEqual(out['별표'], '별표 표 제목 https://www.law.go.kr/LSW/flDownload.do?flSeq=1\n표 내용')

    def test_admin_rule_search_and_show_keep_attachments_without_oc(self):
        self.routes[('list', 'admrul', '통상임금', '1')] = {'AdmRulSearch': {'totalCnt': '1', 'admrul': {
            'id': '1', '행정규칙일련번호': '2100000028287', '행정규칙명': '통상임금 산정지침', '행정규칙종류': '예규',
            '발령일자': '20150917', '발령번호': '59', '소관부처명': '고용노동부', '현행연혁구분': '현행', '시행일자': '20150917',
            '행정규칙ID': '29783', '행정규칙상세링크': '/DRF/lawService.do?OC=secretoc&target=admrul&ID=2100000028287&type=HTML'}}}
        result = lawgo.search('행정규칙', '통상임금', org='고용노동부', rule_kind='예규')
        self.assertEqual((self.calls[-1]['org'], self.calls[-1]['knd']), ('1492000', '2'))
        row = result['rows'][0]
        self.assertNotIn('secretoc', json.dumps(result, ensure_ascii=False))
        self.assertEqual((row['규칙종류'], row['일자'], row['시행일자'], row['링크']),
                         ('예규', '2015-09-17', '2015-09-17', 'https://www.law.go.kr/행정규칙/통상임금산정지침'))
        self.routes[('info', 'admrul', '2100000028287', 'JSON')] = {'AdmRulService': {
            '행정규칙기본정보': {'행정규칙일련번호': '2100000028287', '행정규칙명': '통상임금 산정지침', '발령일자': '20150917',
                         '발령번호': '59', '소관부처명': '고용노동부', '행정규칙종류': '예규', '현행여부': 'Y'},
            '조문내용': ['제1조(목적) 목적이다.', '제2조(정의) 정의다.'], '부칙': {'부칙내용': ['"부칙 <제6호,2008. 5. 2.>"']},
            '첨부파일': {'첨부파일명': ['지침.hwp', '개정안.hwp'], '첨부파일링크': ['http://law.go.kr/flDownload.do?flSeq=1', 'http://law.go.kr/flDownload.do?flSeq=2']}}}
        doc = lawgo.show('행정규칙', '2100000028287')
        self.assertEqual((doc['제목'], doc['기관'], doc['사건번호']), ('통상임금 산정지침', '고용노동부', '59'))
        self.assertEqual(doc['본문']['조문'], '제1조(목적) 목적이다.\n\n제2조(정의) 정의다.')
        self.assertEqual(doc['본문']['첨부파일'], '지침.hwp http://law.go.kr/flDownload.do?flSeq=1\n개정안.hwp http://law.go.kr/flDownload.do?flSeq=2')
        self.assertIn('### 첨부파일', lawgo.markdown(doc))

    def test_law_show_uses_mst_and_history_filters(self):
        self.routes[('info', 'law', '283457', 'JSON')] = {'법령': {'기본정보': {
            '법령명_한글': '근로기준법', '시행일자': '20260820', '공포번호': '21065', '소관부처': {'content': '고용노동부', '소관부처코드': '1492000'},
            '법종구분': {'content': '법률'}}, '조문': self.ARTICLE['법령']['조문']}}
        doc = lawgo.show('법령', '283457')
        self.assertEqual(self.calls[-1]['MST'], '283457')
        self.assertEqual((doc['제목'], doc['기관'], doc['구분'], doc['링크']), ('근로기준법', '고용노동부', '법률', 'https://www.law.go.kr/법령/근로기준법'))
        self.assertIn('제6장의2 직장 내 괴롭힘의 금지', doc['본문']['조문'])
        self.routes[('list', 'eflaw', '근로기준법', '1')] = {'LawSearch': {'totalCnt': '0'}}
        lawgo.search('법령', '근로기준법', history=True)
        self.assertEqual((self.calls[-1]['target'], self.calls[-1]['nw']), ('eflaw', '1,2,3'))
        self.routes[('list', 'admrul', '', '1')] = {'AdmRulSearch': {'totalCnt': '0'}}
        lawgo.search('행정규칙', history=True)
        self.assertEqual(self.calls[-1]['nw'], '2')
        for kind, extra in (('판례', dict(org='고용노동부')), ('법령', dict(rule_kind='예규')), ('노동위', dict(history=True))):
            with self.assertRaises(lawgo.LawGoError):
                lawgo.search(kind, 'x', **extra)

    def test_byl_search_makes_file_links_and_show_is_blocked(self):
        """별표·서식은 목록의 파일 링크로 쓴다. 본문(lawService.do)은 뷰어 HTML만 오므로 show를 막는다."""
        self.routes[('list', 'licbyl', '장해등급', '1')] = {'licBylSearch': {'totalCnt': '2', 'licbyl': [
            {'id': '1', '별표일련번호': '18196057', '별표명': '신체장해의 등급과 노동력상실률표(제2조 관련)',
             '별표종류': '별표', '별표번호': '000200', '공포일자': '20260623', '소관부처명': '법무부',
             '관련법령명': '국가배상법 시행령', '별표서식파일링크': '/LSW/flDownload.do?flSeq=1',
             '별표서식PDF파일링크': '/LSW/flDownload.do?flSeq=2'},
            {'id': '2', '별표일련번호': '18196058', '별표명': '가지번호 별표', '별표종류': '별표', '별표번호': '000302',
             '공포일자': '20260623', '소관부처명': '법무부', '관련법령명': '국가배상법 시행령',
             '별표서식파일링크': '', '별표서식PDF파일링크': ''}]}}
        result = lawgo.search('별표', '장해등급')
        first, second = result['rows']
        self.assertEqual((first['사건번호'], first['근거'], first['기관'], first['일자']),
                         ('별표 2', '국가배상법 시행령', '법무부', '2026-06-23'))
        self.assertEqual(first['한글파일'], 'https://www.law.go.kr/LSW/flDownload.do?flSeq=1')
        self.assertEqual(first['PDF파일'], 'https://www.law.go.kr/LSW/flDownload.do?flSeq=2')
        self.assertEqual(second['사건번호'], '별표 3의2')      # 뒤 두 자리는 가지번호
        with self.assertRaises(lawgo.LawGoError) as caught:
            lawgo.show('별표', '18196057')
        self.assertIn('본문이 API로 오지 않습니다', str(caught.exception))

    def test_nhrck_search_and_show(self):
        self.routes[('list', 'nhrck', '괴롭힘', '1')] = {'Nhrck': {'totalCnt': '1', 'nhrck': [
            {'id': '1', '결정문일련번호': '307', '사건명': '공공기관 상급자의 직장내 괴롭힘', '사건번호': '19진정0413200',
             '의결일자': '2019.10.17', '위원회명': '국가인권위원회 침해구제제2위원회'}]}}
        row = lawgo.search('인권위', '괴롭힘')['rows'][0]
        self.assertEqual((row['종류'], row['id'], row['일자'], row['기관']),
                         ('인권위', '307', '2019-10-17', '국가인권위원회 침해구제제2위원회'))
        self.routes[('info', 'nhrck', '307', 'JSON')] = {'Nhrck': {
            '결정문일련번호': '307', '사건명': '공공기관 상급자의 직장내 괴롭힘', '사건번호': '19진정0413200',
            '의결일자': '20191017', '위원회명': '국가인권위원회 침해구제제2위원회', '분류명': '언어적 폭력-폭언',
            '바로보기URL': 'https://case.humanrights.go.kr/a', '원본다운로드URL': 'https://case.humanrights.go.kr/b',
            '결정요지': '징계 등의 조치를 하기 바람', '판단요지': '괴롭힘에 해당한다', '주문': '권고한다', '이유': '진정요지'}}
        doc = lawgo.show('인권위', '307')
        self.assertEqual(doc['분류'], '언어적 폭력-폭언')
        self.assertEqual(list(doc['본문']), ['결정요지', '판단요지', '주문', '이유'])
        self.assertIn('- 원본: https://case.humanrights.go.kr/b', lawgo.markdown(doc))

    def test_fetch_file_saves_and_rejects_other_hosts(self):
        self.routes[('file',)] = None
        with mock.patch.object(lawgo, 'OPENER', lambda request, timeout=None: Response(b'HWPBYTES')):
            out = Path(self.tmp.name) / '별표.hwp'
            result = lawgo.fetch_file('https://www.law.go.kr/LSW/flDownload.do?flSeq=1', out)
        self.assertEqual((result['바이트'], out.read_bytes()), (8, b'HWPBYTES'))
        with self.assertRaises(lawgo.LawGoError):
            lawgo.fetch_file('https://example.com/x.hwp', out)

    def test_cli_reports_error_with_exit_code(self):
        self.routes[('list', 'prec', '', '1')] = {'result': '사용자 정보 검증에 실패하였습니다.', 'msg': 'IP를 등록해 주세요.'}
        with mock.patch.object(sys, 'argv', ['lawgo.py', 'check']), mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(lawgo.main(), 2)
        self.assertIn('사용자 정보 검증에 실패', err.getvalue())


if __name__ == '__main__':
    unittest.main()
