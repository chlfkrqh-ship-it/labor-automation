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
        self.put('CLAUDE.md', '공통 규칙')
        self.put('4_서면작성/CLAUDE.md', '업무 규칙')
        self.put('.claude/commands/서면.md', '---\ndescription: 서면\n---\n절차')
        self.put('.claude/skills/lbox-검색/SKILL.md', '---\nname: lbox-검색\ndescription: test\n---\n절차')
        self.case = '4_서면작성/사건/테스트'
        self.input = self.case + '/라운드1/우리증거/증거.txt'
        self.put(self.input, '검증용 가상 자료')

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, text):
        module.write(self.root / path, text)

    def test_escape_rejected(self):
        with self.assertRaises(ValueError):
            self.system.path('../outside.txt')

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

    def test_check_reports_missing_commands_and_bad_skills(self):
        result = self.system.check()
        self.assertFalse(result['ok'])
        self.assertIn('.claude/commands/판례검색.md', result['missing'])
        self.assertIn('공통/운영.md', result['missing'])
        for n in ('검토의견', '판례검색', '서면보강', '서면', '증거정리',
                  '증거발췌', '문체검증', '녹취', '손배계산', '손배검산'):
            self.put('.claude/commands/' + n + '.md', '---\ndescription: 절차\n---\n절차')
        for f in ('공통/운영.md', '공통/사건상태.md', '공통/브라우저.md'):
            self.put(f, '지침')
        self.assertTrue(self.system.check()['ok'])
        # 폴더 이름과 name 이 다르면 Claude 가 스킬을 찾지 못한다
        self.put('.claude/skills/잘못/SKILL.md', '---\nname: 다른이름\ndescription: 절차\n---\n')
        self.assertEqual(self.system.check()['skill_errors'], ['.claude/skills/잘못/SKILL.md'])

    def test_budget_reports_without_capping_guides(self):
        self.put('CLAUDE.md', '가' * 10)
        self.put('공통/운영.md', '나' * 10)
        result = self.system.budget(only='판례검색')
        self.assertIn('.claude/commands/판례검색.md', result['missing'])
        self.assertFalse(result['ok'])          # 지침 파일이 없는 것만 실패다
        for rel in ('2_판례검색/CLAUDE.md', '.claude/commands/판례검색.md', *module.LBOX):
            self.put(rel, '다' * 10)
        result = self.system.budget(only='판례검색', record=True)
        self.assertEqual(result['missing'], [])
        self.assertEqual(result['commands']['판례검색'], 70)   # 지침 7개 × 10자
        self.assertTrue(result['ok'])
        # 지침이 아무리 커져도 실패로 만들지 않는다. 증감만 보고한다.
        self.put('2_판례검색/CLAUDE.md', '마' * 500000)
        result = self.system.budget(only='판례검색')
        self.assertTrue(result['ok'])
        self.assertNotIn('over_limit', result)
        self.assertEqual(result['changed_since_record']['판례검색'], 500000 - 10)

    def test_budget_finds_duplicated_and_orphan_guides(self):
        line = '같은 규칙을 두 곳에 나누어 적으면 한쪽만 고치게 되므로 중복된 문장을 찾아 알린다.'
        self.put('공통/운영.md', line)
        self.put('.claude/commands/판례검색.md', line)
        self.put('CLAUDE.md', '루트')
        self.put('공통/아무도안읽는지침.md', '어디에서도 읽지 않는 문서')
        result = self.system.budget()
        pair = [d for d in result['duplicated'] if line[:20] in d['text']]
        self.assertEqual(len(pair), 1)
        self.assertEqual(pair[0]['files'], ['.claude/commands/판례검색.md', '공통/운영.md'])
        self.assertIn('공통/아무도안읽는지침.md', result['orphans'])


if __name__ == '__main__':
    unittest.main()
