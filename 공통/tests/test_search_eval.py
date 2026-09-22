import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('search_eval', Path(__file__).parents[1] / 'scripts' / 'search_eval.py')
search_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_eval)
lawgo = search_eval.lawgo


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def empty_harvest(*args, **kwargs):
    return {'목록': {'판례': {'rows': [], '인용순위': []}}}


class SearchEvalTests(unittest.TestCase):
    """네트워크 없이 lawgo 함수를 바꿔 끼워 시험한다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.oc = mock.patch.object(lawgo, 'oc_value', lambda given=None: 'tester')
        self.oc.start()

    def tearDown(self):
        self.oc.stop()
        self.tmp.cleanup()

    def answers(self, *cases):
        write_json(self.dir / search_eval.ANSWERS, [{'번호': n, '사건번호': f'2020다{100 + n}', '정답': ['2010다1']} for n in cases])
        write_json(self.dir / search_eval.QUERIES, {str(n): ['"구절"'] for n in cases})

    def test_measure_separates_list_ranking_and_combined(self):
        listed = [f'2000다{i}' for i in range(1, 61)]
        listed[4], listed[44] = 'A', 'B'                                        # 목록 5위·45위
        ranking = ['x1', 'C'] + [f'y{i}' for i in range(9)] + ['D']             # 인용 순위 2위·12위
        r = search_eval.measure({'A', 'B', 'C', 'D', 'E'}, listed, ranking)
        self.assertEqual((r['목록_전체'], r['목록_상위20'], r['목록_상위50']), (2, 1, 2))
        self.assertEqual((r['인용_전체'], r['인용_상위10'], r['인용_상위20']), (2, 1, 2))
        self.assertEqual((r['합계'], r['합친상위40']), (4, 3))
        self.assertEqual(r['놓친정답'], ['E'])

    def test_aggregate_reports_percent_and_error_cases(self):
        rows = [dict(번호=1, 정답수=3, 후보수=10, **{k: 3 for k in search_eval.KEYS}),
                dict(번호=2, 정답수=1, 후보수=30, 오류='검색 실패', **{k: 0 for k in search_eval.KEYS})]
        out = search_eval.aggregate(rows)
        self.assertEqual((out['사례'], out['정답'], out['목록_전체']), (2, 4, '3/4 (75%)'))
        self.assertEqual((out['평균후보수'], out['오류사례']), (20, [2]))

    def test_run_measures_harvest_output_and_excludes_the_case_itself(self):
        write_json(self.dir / search_eval.ANSWERS, [{'번호': 1, '사건번호': '2020다100', '정답': ['2010다1', '2011다2', '2012다3']}])
        write_json(self.dir / search_eval.QUERIES, {'1': ['"구절 하나"', '구절 둘']})
        calls = []

        def harvest(kinds, queries, **kwargs):
            calls.append((kinds, queries, kwargs))
            rows = [{'기관': '대법원', '사건번호': '2020다100'}, {'기관': '대법원', '사건번호': '2010다1, 2010다9'}]
            ranking = [{'법원': '대법원', '사건번호': '2020다100'}, {'법원': '서울고등법원', '사건번호': '2012다3'},
                       {'법원': '대법원', '사건번호': '2011다2'}]
            return {'목록': {'판례': {'rows': rows, '인용순위': ranking}}}

        with mock.patch.object(lawgo, 'harvest', harvest):
            out = search_eval.run(self.dir)
        kinds, queries, kwargs = calls[0]
        self.assertEqual((kinds, queries), (['판례'], ['"구절 하나"', '구절 둘']))
        self.assertEqual({k: kwargs[k] for k in ('body', 'court', 'limit', 'texts', 'exclude')},
                         {'body': True, 'court': '대법원', 'limit': 300, 'texts': 20, 'exclude': {'2020다100'}})
        saved = json.loads((self.dir / out['파일']).read_text(encoding='utf-8'))
        case = saved['사례'][0]
        self.assertEqual((case['후보수'], case['목록_전체'], case['인용_전체'], case['합계']), (2, 1, 1, 2))
        self.assertEqual(case['놓친정답'], ['2012다3'])                 # 법원이 다른 같은 번호는 정답이 아니다
        self.assertEqual((saved['검색어파일'], saved['본문수'], saved['검색건수']), (search_eval.QUERIES, 20, 300))
        self.assertNotIn('기준', out)

    def test_run_shows_earliest_result_with_same_settings_as_baseline(self):
        self.answers(1)
        same = {'검색어파일': search_eval.QUERIES, '본문수': 20, '검색건수': 300}
        write_json(self.dir / '결과_2025-11-01_판례기록.json', {'법제처수록': {}})
        write_json(self.dir / '결과_2025-12-01_본문10.json', {**same, '본문수': 10, '요약': {'합계': '0/1 (0%)'}})
        write_json(self.dir / '결과_2026-01-01_본문20.json', {**same, '요약': {'합계': '1/1 (100%)'}})
        write_json(self.dir / '결과_2026-02-01_본문20.json', {**same, '요약': {'합계': '0/1 (0%)'}})
        with mock.patch.object(lawgo, 'harvest', empty_harvest):
            out = search_eval.run(self.dir)
        self.assertEqual(out['기준'], {'파일': '결과_2026-01-01_본문20.json', '합계': '1/1 (100%)'})

    def test_run_records_query_errors_but_stops_on_auth_error(self):
        self.answers(1, 2)

        def broken(*args, **kwargs):
            raise lawgo.LawGoError('검색어를 처리하지 못했습니다')

        with mock.patch.object(lawgo, 'harvest', broken):
            out = search_eval.run(self.dir)
        self.assertEqual(out['요약']['오류사례'], [1, 2])

        def auth(*args, **kwargs):
            raise lawgo.LawGoError('사용자 정보 검증에 실패하였습니다.')

        with mock.patch.object(lawgo, 'harvest', auth), self.assertRaises(lawgo.LawGoError):
            search_eval.run(self.dir)

    def test_build_keeps_existing_answers_without_force(self):
        write_json(self.dir / search_eval.ANSWERS, [])
        with mock.patch.object(lawgo, 'search') as search, self.assertRaises(lawgo.LawGoError):
            search_eval.build(self.dir)
        search.assert_not_called()

    def test_build_keeps_cases_citing_two_or_more_supreme_court_decisions(self):
        rows = [{'id': '1', '사건번호': '2020다1', '일자': '2020-01-01'}, {'id': '2', '사건번호': '2020다2', '일자': '2020-02-02'}]
        bodies = {'1': {'판시사항': '가' * 40, '참조판례': '대법원 2010. 1. 1. 선고 2009다1 판결, 대법원 2011. 1. 1. 선고 2010다2 판결'},
                  '2': {'판시사항': '나' * 40, '참조판례': '대법원 2010. 1. 1. 선고 2009다1 판결, 서울고법 2011. 1. 1. 선고 2010나2 판결'}}
        with mock.patch.object(lawgo, 'search', lambda *a, **k: {'rows': [dict(r) for r in rows]}), \
                mock.patch.object(lawgo, 'show', lambda kind, ident, oc=None: {'본문': bodies[ident]}):
            out = search_eval.build(self.dir, plan=[('근로기준법', 5)])
        cases = json.loads((self.dir / search_eval.ANSWERS).read_text(encoding='utf-8'))
        self.assertEqual(([c['사건번호'] for c in cases], cases[0]['정답'], out['정답']), (['2020다1'], ['2009다1', '2010다2'], 2))

    def test_issues_shows_holdings_without_answers_or_case_numbers(self):
        write_json(self.dir / search_eval.ANSWERS, [{'번호': 1, '법': '근로기준법', '사건번호': '2020다100', '선고': '2020-01-01',
                                                     '판시사항': '[1] 재직조건이 붙은 임금이 통상임금인지', '정답': ['2010다1']}])
        text = search_eval.issues(self.dir)
        self.assertIn('[1] 재직조건이 붙은 임금이 통상임금인지', text)
        for hidden in ('2020다100', '2010다1', '2020-01-01'):
            self.assertNotIn(hidden, text)

    def test_records_counts_by_level_and_skips_non_court_files(self):
        folder = self.dir / '판례기록'
        folder.mkdir()
        for name in ('README.md', '대법원_2020다1.md', '대법원_2020다2.md', '서울고등법원_2021나3.md', '중앙노동위원회_2022부해4.md'):
            (folder / name).write_text('x', encoding='utf-8')
        asked = []

        def search(kind, query='', **kwargs):
            asked.append((kwargs['number'], kwargs['court']))
            found = {'2020다1': [{'기관': '대법원', '사건번호': '2020다1'}],
                     '2021나3': [{'기관': '서울 고등법원', '사건번호': '2021나3'}]}
            return {'rows': found.get(kwargs['number'], [{'기관': '대법원', '사건번호': '2020다21'}])}     # 비슷한 번호는 다른 판결이다

        with mock.patch.object(lawgo, 'search', search):
            out = search_eval.records(folder, out=self.dir)
        self.assertEqual(sorted(asked), [('2020다1', '대법원'), ('2020다2', '대법원'), ('2021나3', '하급심')])
        self.assertEqual((out['법제처수록'], out['법제처에없는대법원']), ({'대법원': '1/2', '하급심': '1/1'}, ['2020다2']))
        self.assertTrue((self.dir / out['파일']).is_file())

    def test_lbox_script_embeds_targets_and_sends_list_searches_only(self):
        write_json(self.dir / search_eval.LOWER, {'대상': [{'판결': '서울행정법원-2021구합1', '검색어': ['"일괄적용" "사업종류"']}],
                                                  '기준': {'날짜': '2026-09-17', '결과': []}})
        script = search_eval.lbox_script(self.dir)
        self.assertIn('[["서울행정법원-2021구합1", ["\\"일괄적용\\" \\"사업종류\\""]]]', script)
        for needed in ('lboxGuard();', 'lboxLock(', 'lboxCall(', "'lbox경고'"):
            self.assertIn(needed, script)
        for absent in ('__대상__', 'lboxText', '/case/'):
            self.assertNotIn(absent, script)

    def test_lbox_score_compares_best_rank_with_baseline(self):
        base = [{'판결': 'A', '검색': [{'관련도순위': 3}, {'관련도순위': None}]}, {'판결': 'B', '검색': [{'관련도순위': 22}]}]
        now = [{'판결': 'A', '검색': [{'관련도순위': None}, {'관련도순위': 1}]}, {'판결': 'B', '검색': [{'관련도순위': None}]}]
        write_json(self.dir / search_eval.LOWER, {'대상': [], '기준': {'날짜': '2026-09-17', '결과': base}})
        write_json(self.dir / 'r.json', {'날짜': '2026-10-01', '끝': True, '요청': 12, '결과': now})
        out = search_eval.lbox_score(self.dir / 'r.json', self.dir)
        self.assertEqual((out['기준']['관련도90위안'], out['기준']['최고순위5위안']), (2, 1))
        self.assertEqual((out['이번']['관련도90위안'], out['이번']['검색어별놓침']), (1, '2/3'))
        self.assertEqual(out['판결별_최고순위'], [{'판결': 'A', '이번': 1, '기준': 3}, {'판결': 'B', '이번': None, '기준': 22}])
        self.assertNotIn('중단', out)
        write_json(self.dir / 'r.json', {'끝': True, '오류': 'status 403', '결과': now[:1]})
        self.assertEqual(search_eval.lbox_score(self.dir / 'r.json', self.dir)['중단'], 'status 403')

    def test_repository_data_is_consistent(self):
        # 공통/검증/ 은 실제 사건으로 시험한 자료라 git 에 올리지 않는다(공통/git-분리-검토.md).
        # 새로 clone 한 PC·클라우드에는 없는 것이 정상이므로, 있을 때만 대조한다.
        missing = [n for n in (search_eval.ANSWERS, search_eval.QUERIES, search_eval.LOWER)
                   if not (search_eval.DATA / n).exists()]
        if missing:
            raise unittest.SkipTest(
                '검증 자료가 없어 건너뜁니다(git 제외 대상): ' + ', '.join(missing))
        cases = search_eval.load(search_eval.DATA / search_eval.ANSWERS)
        queries = search_eval.load(search_eval.DATA / search_eval.QUERIES)
        self.assertEqual({str(c['번호']) for c in cases}, set(queries))
        for c in cases:
            self.assertTrue(c['정답'] and queries[str(c['번호'])], c['번호'])
            self.assertFalse(set(c['정답']) & set(search_eval.numbers(c['사건번호'])), c['번호'])
        lower = search_eval.load(search_eval.DATA / search_eval.LOWER)
        self.assertEqual([(t['판결'], t['검색어']) for t in lower['대상']],
                         [(r['판결'], [s['검색어'] for s in r['검색']]) for r in lower['기준']['결과']])


if __name__ == '__main__':
    unittest.main()
