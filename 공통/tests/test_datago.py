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
                           'method': request.get_method()})
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

    def test_cli_reports_error_with_exit_code(self):
        with mock.patch.object(sys, 'argv', ['datago.py', '사업자', '1234567891']), \
             mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(datago.main(), 1)
        self.assertIn('인증키가 없습니다', err.getvalue())


if __name__ == '__main__':
    unittest.main()
