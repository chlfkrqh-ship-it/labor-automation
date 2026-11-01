import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest import mock
from xml.sax.saxutils import escape

spec = importlib.util.spec_from_file_location('datago', Path(__file__).parents[1] / 'scripts' / 'datago.py')
datago = importlib.util.module_from_spec(spec)
spec.loader.exec_module(datago)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def 검증번호(prefix9):
    d = [int(c) for c in prefix9]
    s = sum(a * b for a, b in zip(d, (1, 3, 7, 1, 3, 7, 1, 3, 5))) + (d[8] * 5) // 10
    return str((10 - s % 10) % 10)


class DataGoTests(unittest.TestCase):
    """네트워크 없이 가짜 응답으로 시험한다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: os.environ.get(k) for k in ('DATAGO_HOME', 'DATAGO_KEY')}
        os.environ['DATAGO_HOME'] = self.tmp.name
        os.environ.pop('DATAGO_KEY', None)
        self.calls, self.payloads, self.nps = [], [], []
        datago.CALLS['n'] = 0
        self.patches = [mock.patch.object(datago, 'OPENER', self.opener), mock.patch.object(datago, 'DELAY', 0)]
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
        self.calls.append({**dict(urllib.parse.parse_qsl(url.query)), 'path': url.path,
                           'url': f'{url.scheme}://{url.netloc}{url.path}', 'method': request.get_method()})
        if request.data is None:                     # 국민연금은 GET 이다
            payload = self.nps.pop(0)
            text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
            return Response(text.encode('utf-8'))
        body = json.loads(request.data.decode('utf-8'))
        self.payloads.append(body)
        # 시험마다 self.폐업·self.미등록에 번호를 넣어 국세청 응답을 흉내 낸다
        폐업, 미등록 = getattr(self, '폐업', set()), getattr(self, '미등록', set())
        data = [{'b_no': no, 'b_stt': '폐업자' if no in 폐업 else '계속사업자',
                 'b_stt_cd': '03' if no in 폐업 else '01',
                 'tax_type': '부가가치세 일반과세자', 'end_dt': '20240131' if no in 폐업 else '',
                 'tax_type_change_dt': '', 'invoice_apply_dt': ''} for no in body['b_no'] if no not in 미등록]
        data += [{'b_no': no, 'tax_type': '국세청에 등록되지 않은 사업자등록번호입니다.'}
                 for no in body['b_no'] if no in 미등록]
        return Response(json.dumps({'status_code': 'OK', 'request_cnt': len(body['b_no']),
                                    'match_cnt': len(data), 'data': data}, ensure_ascii=False).encode('utf-8'))

    def test_key_is_saved_and_read_back(self):
        datago.set_key(' 인증키값 ')
        self.assertEqual(datago.key_value(), '인증키값')
        os.environ['DATAGO_KEY'] = '환경값'
        self.assertEqual(datago.key_value(), '환경값')
        self.assertEqual(datago.key_value('직접'), '직접')

    def test_missing_key_is_reported(self):
        with self.assertRaises(datago.DataGoError) as caught:
            datago.key_value()
        self.assertIn('set-key', str(caught.exception))

    def test_status_normalizes_numbers_and_rows(self):
        datago.set_key('키')
        self.폐업 = {'2222222227'}
        result = datago.status(['123-45-67891', '2222222227'])
        self.assertEqual(self.payloads[0], {'b_no': ['1234567891', '2222222227']})
        self.assertEqual(self.calls[0]['method'], 'POST')
        self.assertEqual(self.calls[0]['path'], '/api/nts-businessman/v1/status')
        폐업 = result['rows'][1]
        self.assertEqual((폐업['상태'], 폐업['상태코드'], 폐업['폐업일자']), ('폐업자', '03', '2024-01-31'))
        self.assertEqual(result['rows'][0]['폐업일자'], '')
        self.assertEqual(result['조회안됨'], [])

    def test_unregistered_number_is_listed_not_dropped(self):
        datago.set_key('키')
        self.미등록 = {'0000000000'}
        result = datago.status(['0000000000', '1234567891'])
        self.assertEqual(result['조회안됨'], ['0000000000'])
        self.assertEqual(result['rows'][0]['상태'], '국세청에 등록되지 않은 번호')
        self.assertEqual(result['받은건수'], 1)

    def test_batches_of_hundred(self):
        datago.set_key('키')
        datago.status([f'{n:09d}' + 검증번호(f'{n:09d}') for n in range(1, 151)])
        self.assertEqual([len(p['b_no']) for p in self.payloads], [100, 50])

    def test_check_digit_is_verified_before_calling(self):
        """검증번호가 틀린 번호는 국세청에 묻지 않고 '형식 오류'로 가른다.

        국세청은 잘못된 번호에도 '등록되지 않은 번호'로 답하므로, 그대로 두면
        '상대방이 국세청에 없다'로 잘못 읽게 된다(2026. 9. 20. 106-87-04597 조회에서 드러났다).
        """
        self.assertTrue(datago.check_digit_ok('1248100998'))
        self.assertFalse(datago.check_digit_ok('1068704597'))
        self.assertTrue(datago.check_digit_ok('1068704590'))
        datago.set_key('키')
        result = datago.status(['106-87-04597', '1234567891'])
        self.assertEqual(result['형식오류'], ['1068704597'])
        self.assertEqual(self.payloads, [{'b_no': ['1234567891']}])      # 틀린 번호는 보내지 않는다
        오류줄 = [r for r in result['rows'] if r['사업자등록번호'] == '1068704597'][0]
        self.assertIn('검증번호 불일치', 오류줄['상태'])
        self.assertEqual(result['조회건수'], 2)

    def test_bad_number_is_rejected_before_calling(self):
        datago.set_key('키')
        with self.assertRaises(datago.DataGoError):
            datago.status(['12345'])
        self.assertEqual(self.calls, [])

    def test_encoded_key_is_not_double_encoded(self):
        datago.set_key('a%2Bb%2Fc')
        datago.status(['1234567891'])
        self.assertEqual(self.calls[0]['serviceKey'], 'a+b/c')

    def test_auth_error_tells_what_to_check(self):
        datago.set_key('키')

        def fail(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 401, 'Unauthorized', {}, io.BytesIO(b'no key'))

        with mock.patch.object(datago, 'OPENER', fail), self.assertRaises(datago.DataGoError) as caught:
            datago.status(['1234567891'])
        self.assertIn('인증키나 신청 상태', str(caught.exception))

    def test_check_reports_ok_and_cli_exit_code(self):
        datago.set_key('키')
        self.assertTrue(datago.check()['ok'])
        self.폐업 = {'2222222227'}
        with mock.patch.object(sys, 'argv', ['datago.py', '사업자', '2222222227']), \
             mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(datago.main(), 0)
        self.assertIn('폐업자', out.getvalue())

    # --- 국민연금 가입 사업장 ---

    @staticmethod
    def 목록(items, total=None):
        return {'response': {'header': {'resultCode': '00', 'resultMsg': 'NORMAL SERVICE.'},
                             'body': {'items': {'item': items}, 'totalCount': total if total is not None else len(items),
                                      'numOfRows': 100, 'pageNo': 1}}}

    def test_workplace_search_names_fields_and_derives_type(self):
        datago.set_key('키')
        self.nps = [self.목록([
            {'seq': '12345', 'wkplNm': '법무법인 평안', 'bzowrRgstNo': '123456',
             'wkplRoadNmDtlAddr': '서울 서초구', 'wkplStylDvcd': '1', 'wkplJnngStcd': '1', 'dataCrtYm': '202608'},
            {'seq': '12346', 'wkplNm': '평안 법률사무소', 'bzowrRgstNo': '123457',
             'wkplRoadNmDtlAddr': '서울 강남구', 'wkplStylDvcd': '2', 'wkplJnngStcd': '2'}], total=2)]
        result = datago.workplaces(name='평안')
        self.assertEqual(self.calls[0]['path'], '/B552015/NpsBplcInfoInqireServiceV2/getBassInfoSearchV2')
        self.assertEqual((self.calls[0]["wkplNm"], self.calls[0]['method']), ('평안', 'GET'))
        첫, 둘 = result['rows']
        self.assertEqual((첫['사업장명'], 첫['사업자번호앞6'], 첫['사업장유형'], 첫['가입상태']),
                         ('법무법인 평안', '123456', '법인', '등록'))
        self.assertEqual((둘['사업장유형'], 둘['가입상태']), ('개인', '탈퇴'))
        self.assertEqual(result['전체'], 2)

    def test_workplace_detail_merges_counts(self):
        datago.set_key('키')
        self.nps = [self.목록([{'seq': '12345', 'wkplNm': '법무법인 평안', 'wkplStylDvcd': '1', 'wkplJnngStcd': '1'}]),
                    self.목록([{'seq': '12345', 'jnngpCnt': '7', 'crrmmNtcAmt': '3,150,000',
                              'vldtVlKrnNm': '법무 관련 서비스업', 'adptDt': '20190301', 'scsnDt': '',
                              'wkplStylDvcd': '1', 'wkplJnngStcd': '1'}])]
        row = datago.workplaces(name='평안', detail=True)['rows'][0]
        self.assertEqual(self.calls[1]['path'], '/B552015/NpsBplcInfoInqireServiceV2/getDetailInfoSearchV2')
        self.assertEqual(self.calls[1]['seq'], '12345')
        self.assertEqual((row['가입자수'], row['당월고지금액'], row['업종'], row['등록일']),
                         (7, 3150000, '법무 관련 서비스업', '2019-03-01'))
        self.assertEqual(row['사업장명'], '법무법인 평안')        # 목록에서 받은 값이 지워지지 않는다

    def test_workplace_masks_and_empty_leave_date(self):
        """응답은 사업자번호 뒤를 가리고, 탈퇴하지 않은 사업장의 탈퇴일을 '00010101'로 준다(2026. 9. 20. 실측)."""
        datago.set_key('키')
        self.nps = [self.목록([{'seq': '7101151', 'wkplNm': '법무법인 정격', 'bzowrRgstNo': '871870****',
                              'wkplStylDvcd': '1', 'wkplJnngStcd': '1', 'adptDt': '20260701', 'scsnDt': '00010101',
                              'jnngpCnt': '4', 'crrmmNtcAmt': '881600', 'vldtVlKrnNm': '변호사업'}])]
        row = datago.workplaces(name='법무법인 정격')['rows'][0]
        self.assertEqual((row['사업자번호앞6'], row['등록일'], row['탈퇴일']), ('871870', '2026-07-01', ''))
        self.assertEqual((row['가입자수'], row['업종']), (4, '변호사업'))

    def test_rows_are_monthly_and_latest_only_dedupes_before_detail(self):
        """한 사업장이 자료기준월마다 한 줄씩 온다. --최신만은 상세를 받기 전에 줄여 호출을 아낀다."""
        datago.set_key('키')
        달 = [{'seq': f'{i}', 'wkplNm': '법무법인 평안', 'wkplRoadNmDtlAddr': '서울 서초구',
              'bzowrRgstNo': '106870****', 'wkplStylDvcd': '1', 'wkplJnngStcd': '1', 'dataCrtYm': f'20260{i}'}
             for i in (5, 6, 7)]
        self.nps = [self.목록(달, total=3)]
        전체 = datago.workplaces(name='법무법인 평안')
        self.assertEqual((전체['전체'], 전체['받은건수'], 전체['사업장수']), (3, 3, 1))
        self.assertEqual([r['자료기준월'] for r in 전체['rows']], ['202607', '202606', '202605'])
        self.assertEqual(전체['요약'][0]['받은달수'], 3)
        self.assertEqual(전체['요약'][0]['자료기준월'], '202607')

        self.calls.clear()
        self.nps = [self.목록(달, total=3),
                    self.목록([{'seq': '7', 'jnngpCnt': '54', 'wkplStylDvcd': '1', 'wkplJnngStcd': '1'}])]
        하나 = datago.workplaces(name='법무법인 평안', detail=True, latest_only=True)
        self.assertEqual(len(하나['rows']), 1)
        self.assertEqual(하나['rows'][0]['가입자수'], 54)
        self.assertEqual(len(self.calls), 2)        # 목록 1 + 상세 1. 최신만이 아니면 상세가 3회였다

    def test_workplace_reads_xml_response(self):
        datago.set_key('키')
        self.nps = ['<?xml version="1.0"?><response><header><resultCode>00</resultCode></header>'
                    '<body><items><item><seq>9</seq><wkplNm>가</wkplNm><wkplStylDvcd>1</wkplStylDvcd>'
                    '<wkplJnngStcd>1</wkplJnngStcd></item><item><seq>10</seq><wkplNm>나</wkplNm>'
                    '<wkplStylDvcd>1</wkplStylDvcd><wkplJnngStcd>1</wkplJnngStcd></item></items>'
                    '<totalCount>2</totalCount></body></response>']
        result = datago.workplaces(name='가')
        self.assertEqual([r['사업장명'] for r in result['rows']], ['가', '나'])

    def test_unregistered_service_key_tells_to_apply(self):
        datago.set_key('키')
        self.nps = ['{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"errMsg":"SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}}']
        with self.assertRaises(datago.DataGoError) as caught:
            datago.workplaces(name='평안')
        self.assertIn('활용신청', str(caught.exception))

    def test_workplace_needs_a_condition_and_six_digits(self):
        datago.set_key('키')
        with self.assertRaises(datago.DataGoError):
            datago.workplaces()
        with self.assertRaises(datago.DataGoError):
            datago.workplaces(bno='123')
        self.assertEqual(self.calls, [])

    def test_workplace_empty_items_is_not_an_error(self):
        datago.set_key('키')
        self.nps = [{'response': {'header': {'resultCode': '00'}, 'body': {'items': '', 'totalCount': '0'}}}]
        result = datago.workplaces(name='없는사업장')
        self.assertEqual((result['전체'], result['rows']), (0, []))

    # --- 한국산업안전보건공단 MSDS ---

    @staticmethod
    def msds_xml(items, total=None, code='00', paged=True):
        """포털 명세 꼴의 XML 응답. 값은 XML 로 이스케이프한다. 상세(paged=False)에는 쪽 칸과 totalCount 가 없다."""
        body = ''.join('<item>' + ''.join(f'<{k}>{escape(str(v))}</{k}>' for k, v in it.items()) + '</item>'
                       for it in items)
        counts = (f'<totalCount>{len(items) if total is None else total}</totalCount>'
                  '<pageNo>1</pageNo><numOfRows>100</numOfRows>') if paged else ''
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><response><header>'
                f'<resultCode>{code}</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>'
                f'<body><items>{body}</items>{counts}</body></response>')

    def test_msds_kind_reads_the_shape_of_the_term(self):
        for term, kind in (('71-43-2', 'CAS'), ('7440-43-9', 'CAS'), (' 71-43-2 ', 'CAS'), ('UN1114', 'UN'),
                           ('un 1114', 'UN'), ('1114', 'UN'), ('KE-02380', 'KE'), ('ke02380', 'KE'),
                           ('200-753-7', 'EN'), ('벤젠', '국문명'), ('트리클로로에틸렌', '국문명'), ('n-헥산', '국문명')):
            self.assertEqual(datago.msds_kind(term), kind, term)

    def test_msds_search_sends_condition_and_names_fields(self):
        datago.set_key('키')
        self.nps = [self.msds_xml([                    # 2026. 11. 1. 실측 응답의 칸
            {'casNo': '71-43-2', 'chemId': '001008', 'chemNameKor': '벤젠', 'enNo': '200-753-7', 'keNo': 'KE-02150',
             'koshaConfirm': '', 'lastDate': '2025-09-17', 'openYn': '', 'unNo': '1114', 'newField': '그대로'},
            {'chemId': '001089', 'chemNameKor': '에틸벤젠', 'casNo': '100-41-4', 'lastDate': '20250808'}], total=2)]
        result = datago.msds_search('벤젠')
        call = self.calls[0]
        # 옛 주소(msds.kosha.or.kr/openapi)는 Accept JSON 에 406, http 에 '등록되지 않은 키'를 냈다(2026. 11. 1. 실측)
        self.assertEqual((call['url'], call['method']), ('https://apis.data.go.kr/B552468/msdschem1/getChemList001', 'GET'))
        self.assertEqual((call['searchWrd'], call['searchCnd'], call['numOfRows'], call['pageNo']), ('벤젠', '0', '20', '1'))
        self.assertEqual((result['검색방식'], result['전체'], result['받은건수']), ('국문명', 2, 2))
        첫, 둘 = result['rows']
        self.assertEqual((첫['chemId'], 첫['물질명'], 첫['CAS'], 첫['UN'], 첫['KE'], 첫['EN'], 첫['갱신일']),
                         ('001008', '벤젠', '71-43-2', '1114', 'KE-02150', '200-753-7', '2025-09-17'))
        self.assertEqual(첫['newField'], '그대로')             # 명세에 없는 칸도 버리지 않는다
        self.assertEqual(둘['갱신일'], '2025-08-08')

    def test_msds_numbers_are_sent_without_prefix_or_spaces(self):
        datago.set_key('키')
        self.nps = [self.msds_xml([]), self.msds_xml([]), self.msds_xml([])]
        datago.msds_search('un 1114')
        datago.msds_search(' 71-43-2 ')
        datago.msds_search('ke-02150')
        self.assertEqual([(c['searchWrd'], c['searchCnd']) for c in self.calls],
                         [('1114', '2'), ('71-43-2', '1'), ('KE-02150', '3')])

    def test_msds_search_empty_result_is_not_an_error(self):
        datago.set_key('키')
        self.nps = [self.msds_xml([])]
        result = datago.msds_search('없는물질')
        self.assertEqual((result['전체'], result['rows']), (0, []))

    def test_msds_detail_calls_each_section_once_and_keeps_unknown_fields(self):
        """절마다 한 번 부르면 다 온다. 쪽 칸을 보내지 않고 totalCount 도 오지 않는다(2026. 11. 1. 실측)."""
        datago.set_key('키')
        줄 = lambda n, 이름, 내용: {'itemDetail': 내용, 'lev': '2', 'msdsItemCode': f'B{n:02d}', 'msdsItemNameKor': 이름,
                                   'ordrIdx': str(n), 'upMsdsItemCode': 'B'}
        제목줄 = {'lev': '1', 'msdsItemCode': 'B', 'msdsItemNameKor': '유해성·위험성 분류', 'ordrIdx': '0', 'upMsdsItemCode': 'A'}
        self.nps = [self.msds_xml([제목줄, 줄(1, '발암성', '구분1A'), 줄(2, '유해·위험문구', 'H350 암을 일으킬 수 있음 & 노출 < 1 ppm')],
                                  paged=False),
                    self.msds_xml([줄(4, '국내규정', 'TWA 0.5 ppm')], paged=False),
                    self.msds_xml([줄(5, '발암성', 'IARC 1'), 줄(7, '경구', 'LD50 &gt;2000 ㎎/㎏')], paged=False),
                    self.msds_xml([줄(6, '산업안전보건법에 의한 규제', '특수건강진단대상물질')], paged=False)]
        result = datago.msds_detail('001008')
        self.assertEqual([c['path'] for c in self.calls],
                         [f'/B552468/msdschem1/getChemDetail{n}1' for n in ('02', '08', '11', '15')])
        self.assertTrue(all(c['chemId'] == '001008' and 'numOfRows' not in c and 'pageNo' not in c for c in self.calls))
        self.assertEqual(list(result['내용']), ['2. 유해성·위험성', '8. 노출방지 및 개인보호구', '11. 독성에 관한 정보', '15. 법적 규제현황'])
        유해성 = result['내용']['2. 유해성·위험성']
        self.assertEqual(len(유해성), 3)
        self.assertNotIn('내용', 유해성[0])                     # 위 단계의 줄에는 itemDetail 이 없다
        self.assertEqual((유해성[1]['단계'], 유해성[1]['항목코드'], 유해성[1]['항목'], 유해성[1]['내용']),
                         ('2', 'B01', '발암성', '구분1A'))
        self.assertEqual(유해성[2]['내용'], 'H350 암을 일으킬 수 있음 & 노출 < 1 ppm')
        self.assertEqual((유해성[1]['upMsdsItemCode'], 유해성[1]['ordrIdx']), ('B', '1'))
        self.assertEqual(result['내용']['11. 독성에 관한 정보'][1]['내용'], 'LD50 >2000 ㎎/㎏')   # 한 번 더 이스케이프되어 온다
        self.assertEqual(result['내용']['15. 법적 규제현황'][0]['내용'], '특수건강진단대상물질')
        self.assertIn('작업환경측정', result['안내'])

    def test_msds_detail_with_no_content_is_an_error_not_an_empty_result(self):
        """없는 번호나 앞의 0을 뺀 번호(1008)도 정상 코드와 빈 목록으로 온다(2026. 11. 1. 실측)."""
        datago.set_key('키')
        self.nps = [self.msds_xml([], paged=False) for _ in range(4)]
        with self.assertRaisesRegex(datago.DataGoError, '앞의 0까지'):
            datago.msds_detail('1008')
        # 내용이 없는 절이 일부면 오류가 아니다
        self.nps = [self.msds_xml([], paged=False), self.msds_xml([{'lev': '1', 'itemDetail': '자료없음'}], paged=False)]
        self.assertEqual(datago.msds_detail('001008', sections=[3, 8])['내용']['3. 구성성분의 명칭 및 함유량'], [])

    def test_msds_detail_all_sections_and_bad_input(self):
        datago.set_key('키')
        한줄 = self.msds_xml([{'lev': '1', 'itemDetail': '자료없음'}], paged=False)
        self.nps = [한줄 for _ in range(16)]
        result = datago.msds_detail('001008', sections=['ALL'])
        self.assertEqual(result['절'], list(range(1, 17)))
        self.assertEqual(self.calls[0]['path'], '/B552468/msdschem1/getChemDetail011')
        self.assertEqual(self.calls[-1]['path'], '/B552468/msdschem1/getChemDetail161')
        self.calls.clear()
        self.nps = [한줄, 한줄]
        self.assertEqual(datago.msds_detail('001008', sections=['8', '2', '8'])['절'], [8, 2])
        self.assertEqual(len(self.calls), 2)
        self.calls.clear()
        for bad in ([17], ['x'], [0]):
            with self.assertRaises(datago.DataGoError):
                datago.msds_detail('001008', sections=bad)
        with self.assertRaises(datago.DataGoError):
            datago.msds_detail(' ')
        self.assertEqual(self.calls, [])

    def test_msds_unregistered_key_names_the_msds_service(self):
        datago.set_key('키')
        self.nps = ['<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg>'
                    '<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>'
                    '<returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>']
        with self.assertRaises(datago.DataGoError) as caught:
            datago.msds_search('벤젠')
        message = str(caught.exception)
        self.assertIn('활용신청', message)
        self.assertIn('물질안전보건자료 조회 서비스', message)
        self.assertNotIn('국민연금', message)
        # 새 꼴의 봉투는 밑줄 대신 띄어 쓴다
        self.nps = [self.msds_xml([], code='30').replace('NORMAL SERVICE.', 'SERVICE KEY IS NOT REGISTERED ERROR.')]
        with self.assertRaisesRegex(datago.DataGoError, '활용신청'):
            datago.msds_search('벤젠')

    def test_msds_result_code_error_is_reported(self):
        datago.set_key('키')
        self.nps = [self.msds_xml([], code='99')]
        with self.assertRaises(datago.DataGoError) as caught:
            datago.msds_search('벤젠')
        self.assertIn('MSDS 응답 오류: 99', str(caught.exception))

    def test_msds_cli_writes_detail_and_prints_counts(self):
        datago.set_key('키')
        self.nps = [self.msds_xml([{'lev': '1', 'msdsItemNameKor': '국내규정', 'itemDetail': 'TWA 0.5 ppm'}], paged=False)]
        out = Path(self.tmp.name) / '사건' / 'msds.json'
        with mock.patch.object(sys, 'argv', ['datago.py', 'msds-detail', '001008', '--절', '8', '--out', str(out)]), \
             mock.patch('sys.stdout', new_callable=io.StringIO) as printed:
            self.assertEqual(datago.main(), 0)
        saved = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(saved['내용']['8. 노출방지 및 개인보호구'][0]['내용'], 'TWA 0.5 ppm')
        shown = json.loads(printed.getvalue())
        self.assertEqual(shown['항목 수'], {'8. 노출방지 및 개인보호구': 1})
        self.assertNotIn('내용', shown)

        self.nps = [self.msds_xml([{'chemId': '001008', 'chemNameKor': '벤젠', 'casNo': '71-43-2'}])]
        with mock.patch.object(sys, 'argv', ['datago.py', 'msds', '71-43-2']), \
             mock.patch('sys.stdout', new_callable=io.StringIO) as printed:
            self.assertEqual(datago.main(), 0)
        self.assertEqual(json.loads(printed.getvalue())['rows'][0]['물질명'], '벤젠')

    def test_cli_reports_error_with_exit_code(self):
        with mock.patch.object(sys, 'argv', ['datago.py', '사업자', '1234567891']), \
             mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(datago.main(), 1)
        self.assertIn('인증키가 없습니다', err.getvalue())


if __name__ == '__main__':
    unittest.main()
