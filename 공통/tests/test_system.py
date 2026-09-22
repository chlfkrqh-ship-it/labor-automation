import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('workflow_system', Path(__file__).parents[1] / 'scripts' / 'system.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.system = module.System(self.root)
        self.put('AGENTS.md', '공통 규칙')
        self.put('4_서면작성/CLAUDE.md', '업무 규칙')
        self.put('공통/명령어/서면.md', '---\ndescription: 서면\n---\n절차')
        self.put('공통/스킬/labor-workflow/SKILL.md', '---\nname: labor-workflow\ndescription: test\n---\n절차')
        self.case = '4_서면작성/사건/테스트'
        self.input = self.case + '/라운드1/우리증거/증거.txt'
        self.put(self.input, '검증용 가상 자료')

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, text):
        module.write(self.root / path, text)

    def bundle(self):
        return self.system.prepare(self.case, '가상 자료로 독립 작성', [self.input])['bundle']

    def test_escape_rejected(self):
        with self.assertRaises(ValueError):
            self.system.path('../outside.txt')

    def test_sync_idempotent_and_preserves_local_edit(self):
        self.system.sync(True)
        self.assertEqual(self.system.sync()['changed'], [])
        self.put('CLAUDE.md', '사용자 직접 수정')
        self.put('공통/명령어/서면.md', '---\ndescription: 새 절차\n---\n절차')
        before = (self.root / '.claude/commands/서면.md').read_bytes()
        with self.assertRaises(ValueError):
            self.system.sync(True)
        self.assertEqual(before, (self.root / '.claude/commands/서면.md').read_bytes())
        self.assertEqual((self.root / 'CLAUDE.md').read_text(encoding='utf-8'), '사용자 직접 수정')

    def test_source_update_propagates(self):
        self.system.sync(True)
        self.put('AGENTS.md', '수정된 공통 규칙')
        self.system.sync(True)
        self.assertEqual((self.root / 'CLAUDE.md').read_text(encoding='utf-8'), '수정된 공통 규칙')

    def test_scan_changes_and_ignores_generated(self):
        self.assertTrue(self.system.scan(self.case)['first_scan'])
        self.system.scan(self.case, True)
        self.put(self.case + '/작업/사건상태.md', '파생 상태')
        self.assertEqual(self.system.scan(self.case)['added'], [])
        self.put(self.case + '/라운드1/작업/사실관계_정리.md', '담당자가 수정한 사실관계')
        self.assertIn(self.case + '/라운드1/작업/사실관계_정리.md', self.system.scan(self.case)['added'])
        self.put(self.input, '변경된 원자료')
        self.assertEqual(self.system.scan(self.case)['changed'], [self.input])
        # A deleted source invalidates the baseline and is not silently forgotten.
        (self.root / self.input).unlink()
        self.assertEqual(self.system.scan(self.case)['deleted'], [self.input])

    def test_cache_reuse_and_invalidation(self):
        a = self.system.extract(self.input)
        self.assertFalse(a['cache_hit'])
        self.assertTrue(self.system.extract(self.input)['cache_hit'])
        self.put(self.input, '달라진 자료')
        b = self.system.extract(self.input)
        self.assertFalse(b['cache_hit'])
        self.assertNotEqual(a['source_sha256'], b['source_sha256'])

    def test_unsupported_source_is_in_inventory(self):
        extra = self.case + '/라운드1/우리증거/읽기필요.hwp'
        self.put(extra, '추출 미지원 원자료도 목록에는 표시')
        self.assertIn(extra, self.system.scan(self.case)['added'])
        with self.assertRaises(ValueError):
            self.system.extract(extra)

    def test_docx_tables_and_footnotes(self):
        p = self.root / self.case / '문서.docx'
        with zipfile.ZipFile(p, 'w') as z:
            for part, text in [('document', '본문과 표'), ('footnotes', '각주')]:
                z.writestr('word/' + part + '.xml', '<w:document xmlns:w="' + module.NS['w']
                           + '"><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:document>')
        result = self.system.extract(p)
        self.assertIn('본문과 표', result['text'])
        self.assertIn('각주', result['text'])
        self.assertTrue(result['warnings'])

    def test_frozen_input_unchanged_when_live_source_changes(self):
        b = self.bundle()
        self.put(self.input, '라이브 자료 변경')
        self.system.verify(b)
        self.assertEqual((self.root / b / '기준' / self.input).read_text(encoding='utf-8'), '검증용 가상 자료')

    def test_frozen_input_tamper_rejected(self):
        b = self.bundle()
        self.put(b + '/기준/' + self.input, '변경')
        with self.assertRaises(ValueError):
            self.system.verify(b)

    def test_prompt_tamper_and_extra_input_rejected(self):
        b = self.bundle()
        self.put(b + '/gpt/요청.md', '다른 과제')
        with self.assertRaises(ValueError):
            self.system.verify(b)
        b = self.bundle()
        self.put(b + '/기준/추가.txt', '추가 자료')
        with self.assertRaises(ValueError):
            self.system.verify(b)

    def test_complete_comparison_and_no_false_usage(self):
        b = self.bundle()
        self.put(self.case + '/gpt.md', '갑 제1호증. 2020두12345 판결. 가상 예시')
        self.put(self.case + '/claude.md', '을나 제2호증. 2021다12345 판결. 가상 예시')
        for provider in ('gpt', 'claude'):
            self.system.capture(b, provider, self.case + '/' + provider + '.md', 'test-only')
        with self.assertRaises(ValueError):
            self.system.capture(b, 'gpt', self.case + '/gpt.md', 'test-only')
        result = self.system.compare(b)
        text = (self.root / result['report']).read_text(encoding='utf-8')
        self.assertIn('미확인', text)
        self.assertIn('2020두12345', text)
        self.assertIn('을나 제2호증', text)
        self.assertEqual(result['legal_evaluation'], '미평가')
        self.put(b + '/gpt/결과원본.md', '등록 후 변경')
        with self.assertRaises(ValueError):
            self.system.compare(b)

    def test_budget_reports_without_capping_guides(self):
        self.put('CLAUDE.md', '가' * 10)
        self.put('공통/운영.md', '나' * 10)
        result = self.system.budget(only='결과비교')
        self.assertIn('공통/명령어/결과비교.md', result['missing'])
        self.assertFalse(result['ok'])          # 지침 파일이 없는 것만 실패다
        self.put('공통/명령어/결과비교.md', '다' * 10)
        self.put('공통/결과비교.md', '라' * 10)
        result = self.system.budget(only='결과비교', record=True)
        self.assertEqual(result['missing'], [])
        self.assertEqual(result['commands']['결과비교'], 40)
        self.assertTrue(result['ok'])
        # 지침이 아무리 커져도 실패로 만들지 않는다. 증감만 보고한다.
        self.put('공통/결과비교.md', '마' * 500000)
        result = self.system.budget(only='결과비교')
        self.assertTrue(result['ok'])
        self.assertNotIn('over_limit', result)
        self.assertEqual(result['changed_since_record']['결과비교'], 500000 - 10)

    def test_budget_finds_duplicated_and_orphan_guides(self):
        line = '같은 규칙을 두 곳에 나누어 적으면 한쪽만 고치게 되므로 중복된 문장을 찾아 알린다.'
        self.put('공통/운영.md', line)
        self.put('공통/명령어/결과비교.md', line)
        self.put('CLAUDE.md', '루트')
        self.put('공통/결과비교.md', '비교')
        self.put('공통/아무도안읽는지침.md', '어디에서도 읽지 않는 문서')
        result = self.system.budget()
        pair = [d for d in result['duplicated'] if line[:20] in d['text']]
        self.assertEqual(len(pair), 1)
        self.assertEqual(pair[0]['files'], ['공통/명령어/결과비교.md', '공통/운영.md'])
        self.assertIn('공통/아무도안읽는지침.md', result['orphans'])


if __name__ == '__main__':
    unittest.main()
