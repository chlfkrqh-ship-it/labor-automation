import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest import mock

spec = importlib.util.spec_from_file_location('papers', Path(__file__).parents[1] / 'scripts' / 'papers.py')
papers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(papers)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def epmc_item(n, oa='Y'):
    return {'id': str(n), 'source': 'MED', 'pmid': str(n), 'pmcid': f'PMC{n}', 'doi': f'10.1/x{n}',
            'title': f'논문 {n}', 'authorString': '홍길동, 김담당.', 'pubYear': '2021', 'pageInfo': '1-9',
            'journalInfo': {'volume': '47', 'issue': '7', 'journal': {'title': '가상 학술지'}},
            'pubTypeList': {'pubType': ['Journal Article']}, 'isOpenAccess': oa,
            'abstractText': '<h4>목적</h4>장시간 노동과 뇌졸중의 관계를 본다.'}


JATS = '''<?xml version="1.0"?>
<article><front><article-meta>
<title-group><article-title>장시간 노동과 뇌졸중</article-title></title-group>
<abstract><p>초록 첫 문단.</p></abstract>
</article-meta></front>
<body>
<sec><title>방법</title><p>코호트 연구이다.</p>
  <sec><title>노출</title><p>주 55시간 이상.</p></sec>
</sec>
<sec><title>결과</title>
  <table-wrap><label>Table 1</label><caption><p>위험비</p></caption>
    <table><tr><th>노출</th><th>RR</th></tr><tr><td>55시간 이상</td><td>1.33</td></tr></table>
  </table-wrap>
</sec>
</body>
<back><ref-list><ref>참고문헌은 뺀다</ref></ref-list></back></article>'''.encode('utf-8')


class PapersTests(unittest.TestCase):
    """네트워크 없이 가짜 응답으로 시험한다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: os.environ.get(k) for k in ('PAPERS_HOME', 'OPENALEX_KEY')}
        os.environ['PAPERS_HOME'] = self.tmp.name
        os.environ.pop('OPENALEX_KEY', None)
        self.calls, self.replies = [], []
        papers.CALLS['n'] = 0
        self.patches = [mock.patch.object(papers, 'OPENER', self.opener), mock.patch.object(papers, 'DELAY', 0),
                        mock.patch.object(papers.time, 'sleep', lambda s: None)]
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
        self.calls.append({**dict(urllib.parse.parse_qsl(url.query)), 'path': url.path, 'host': url.netloc})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return Response(reply if isinstance(reply, bytes) else json.dumps(reply).encode('utf-8'))

    # Europe PMC

    def test_epmc_search_pages_with_cursor_and_reads_rows(self):
        self.replies = [{'hitCount': 3, 'nextCursorMark': 'C1', 'resultList': {'result': [epmc_item(1), epmc_item(2, 'N')]}},
                        {'hitCount': 3, 'nextCursorMark': 'C2', 'resultList': {'result': [epmc_item(3)]}}]
        result = papers.epmc_search('long working hours AND stroke', limit=3)
        self.assertEqual(result['전체'], 3)
        self.assertEqual(result['받은건수'], 3)
        self.assertEqual([c['cursorMark'] for c in self.calls], ['*', 'C1'])
        self.assertEqual(self.calls[0]['resultType'], 'core')
        self.assertEqual(self.calls[0]['format'], 'json')
        first = result['rows'][0]
        self.assertEqual(first['pmcid'], 'PMC1')
        self.assertEqual(first['학술지'], '가상 학술지')
        self.assertEqual(first['권호면'], '47·7, 1-9')
        self.assertTrue(first['무료공개'])
        self.assertFalse(result['rows'][1]['무료공개'])
        self.assertEqual(first['초록'], '목적 장시간 노동과 뇌졸중의 관계를 본다.')   # 소제목 태그는 띄어 쓴다
        self.assertEqual(first['주소'], 'https://europepmc.org/article/MED/1')

    def test_epmc_abstract_keeps_text_after_a_less_than_sign(self):
        item = epmc_item(1)
        item['abstractText'] = ('<h4>Results</h4>Sick leave rose (p < 0.001, RR<2) and a<b and c>d, '
                                'R<sup>2</sup> 0.4.<h4 class="x">Conclusions</h4>One in ten.')
        self.replies = [{'hitCount': 1, 'resultList': {'result': [item]}}]
        abstract = papers.epmc_search('x', limit=1)['rows'][0]['초록']
        self.assertEqual(abstract, 'Results Sick leave rose (p < 0.001, RR<2) and a<b and c>d, '
                                   'R 2 0.4. Conclusions One in ten.')

    def test_epmc_search_stops_when_cursor_repeats_or_page_is_empty(self):
        self.replies = [{'hitCount': 1, 'nextCursorMark': '*', 'resultList': {'result': [epmc_item(1)]}}]
        result = papers.epmc_search('x', limit=20)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result['받은건수'], 1)

    def test_epmc_open_access_and_since_go_into_the_query(self):
        self.replies = [{'hitCount': 0, 'resultList': {'result': []}}]
        papers.epmc_search('rotator cuff', open_access=True, since=2010)
        self.assertEqual(self.calls[0]['query'], '((rotator cuff) AND OPEN_ACCESS:y) AND PUB_YEAR:[2010 TO 3000]')

    def test_epmc_fulltext_keeps_sections_tables_and_drops_references(self):
        self.replies = [JATS]
        result = papers.epmc_fulltext('8504166')
        self.assertEqual(result['pmcid'], 'PMC8504166')
        self.assertEqual(self.calls[0]['path'], '/europepmc/webservices/rest/PMC8504166/fullTextXML')
        text = result['text']
        for line in ('# 장시간 노동과 뇌졸중', '## 초록', '초록 첫 문단.', '## 방법', '### 노출', '주 55시간 이상.',
                     '[Table 1] 위험비', '노출 | RR', '55시간 이상 | 1.33'):
            self.assertIn(line, text)
        self.assertNotIn('참고문헌은 뺀다', text)
        self.assertLess(text.index('## 방법'), text.index('## 결과'))

    def test_epmc_fulltext_not_found_says_so(self):
        self.replies = [urllib.error.HTTPError('u', 404, 'Not Found', {}, io.BytesIO(b''))]
        with self.assertRaisesRegex(papers.PapersError, '찾는 자료가 없습니다'):
            papers.epmc_fulltext('PMC1')

    # OpenAlex

    def test_openalex_needs_a_key_and_reads_env_before_file(self):
        with self.assertRaisesRegex(papers.PapersError, '인증키가 없습니다'):
            papers.openalex_key()
        papers.set_openalex_key(' 파일키 ')
        self.assertEqual(papers.openalex_key(), '파일키')
        self.assertTrue((Path(self.tmp.name) / 'openalex.json').is_file())
        os.environ['OPENALEX_KEY'] = '환경키'
        self.assertEqual(papers.openalex_key(), '환경키')
        self.assertEqual(papers.openalex_key('직접'), '직접')

    def test_openalex_search_sends_key_and_filters_and_rebuilds_abstract(self):
        os.environ['OPENALEX_KEY'] = 'K'
        work = {'id': 'https://openalex.org/W1', 'doi': 'https://doi.org/10.5/abc', 'display_name': '조선업 근골격계',
                'publication_year': 2019, 'language': 'ko', 'type': 'article', 'cited_by_count': 4,
                'authorships': [{'author': {'display_name': f'저자{i}'}} for i in range(7)],
                'primary_location': {'source': {'display_name': '가상학회지'}},
                'open_access': {'is_oa': True, 'oa_url': 'https://example.org/a.pdf'},
                'abstract_inverted_index': {'반복': [1], '작업과': [0], '질환': [2]}}
        self.replies = [{'meta': {'count': 1}, 'results': [work]}]
        result = papers.openalex_search('근골격계 조선업', limit=5, language='ko', since=2010)
        call = self.calls[0]
        self.assertEqual(call['host'], 'api.openalex.org')
        self.assertEqual(call['api_key'], 'K')
        self.assertEqual(call['filter'], 'language:ko,publication_year:>2009')
        self.assertEqual(call['per-page'], '5')
        row = result['rows'][0]
        self.assertEqual(row['doi'], '10.5/abc')
        self.assertEqual(row['초록'], '작업과 반복 질환')
        self.assertEqual(row['저자'], '저자0, 저자1, 저자2, 저자3, 저자4 외')
        self.assertTrue(row['무료공개'])
        self.assertEqual(len(self.calls), 1)          # 한 쪽이 per-page 보다 적으면 더 넘기지 않는다

    def test_openalex_refusal_points_to_the_key(self):
        os.environ['OPENALEX_KEY'] = 'K'
        self.replies = [urllib.error.HTTPError('u', 401, 'Unauthorized', {}, io.BytesIO(b'bad key'))]
        result = papers.openalex_check()
        self.assertFalse(result['ok'])
        self.assertIn('인증키', result['사유'])

    # 명령

    def test_cli_writes_json_to_out(self):
        self.replies = [{'hitCount': 1, 'resultList': {'result': [epmc_item(1)]}}]
        out = Path(self.tmp.name) / '사건' / '검색.json'
        with mock.patch('sys.stdout', new_callable=io.StringIO) as printed:
            code = papers.main(['epmc', 'stroke', '--out', str(out)])
        self.assertEqual(code, 0)
        saved = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(saved['rows'][0]['pmid'], '1')
        self.assertIn('파일', json.loads(printed.getvalue()))

    def test_cli_reports_errors_with_exit_code_1(self):
        with mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            code = papers.main(['openalex', 'stroke'])
        self.assertEqual(code, 1)
        self.assertIn('인증키가 없습니다', err.getvalue())


if __name__ == '__main__':
    unittest.main()
