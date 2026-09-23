import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile

spec = importlib.util.spec_from_file_location('workflow_system', Path(__file__).parents[1] / 'scripts' / 'system.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
REPO = Path(__file__).parents[2]
W = module.NS['w']


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

    def docx(self, name, document, footnotes=None):
        p = self.root / self.case / name
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('word/document.xml', document)
            if footnotes is not None:
                z.writestr('word/footnotes.xml', footnotes)
        return p

    def test_docx_tables_and_footnotes(self):
        p = self.docx('문서.docx',
                      f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>본문</w:t></w:r>'
                      '<w:ins><w:r><w:t>삽입한 글</w:t></w:r></w:ins></w:p>'
                      '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>표 칸</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>',
                      f'<w:footnotes xmlns:w="{W}"><w:footnote><w:p><w:r><w:t>각주</w:t></w:r></w:p></w:footnote></w:footnotes>')
        result = self.system.extract(p)
        self.assertEqual(result['text'].split('\n'),
                         ['[word/document.xml]', '본문삽입한 글', '표 칸', '[word/footnotes.xml]', '각주'])
        self.assertTrue(any(w.startswith('변경 추적 있음') for w in result['warnings']))

    def test_docx_text_box_is_extracted_once(self):
        """글상자는 mc:Choice 와 mc:Fallback 두 벌로 저장된다. 바깥 문단에 붙이지 않고 한 번만 뽑는다."""
        mc = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
        box = '<w:txbxContent><w:p><w:r><w:t>취업규칙 제10조 글상자 문장</w:t></w:r></w:p></w:txbxContent>'
        p = self.docx('글상자.docx',
                      f'<w:document xmlns:w="{W}" xmlns:mc="{mc}"><w:body>'
                      '<w:p><w:r><w:t>본문 앞</w:t></w:r><w:r><mc:AlternateContent>'
                      f'<mc:Choice Requires="wps"><w:drawing>{box}</w:drawing></mc:Choice>'
                      f'<mc:Fallback><w:pict>{box}</w:pict></mc:Fallback>'
                      '</mc:AlternateContent></w:r></w:p><w:p><w:r><w:t>다음 문단</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(self.system.extract(p)['text'].split('\n'),
                         ['[word/document.xml]', '본문 앞', '취업규칙 제10조 글상자 문장', '다음 문단'])

    def test_pdf_pages_are_numbered_and_blank_pages_flagged(self):
        objects = {1: '<< /Type /Catalog /Pages 2 0 R >>',
                   2: '<< /Type /Pages /Kids [4 0 R 6 0 R] /Count 2 >>',
                   3: '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'}
        for page, text in ((4, 'Rules of Employment Article 10'), (6, '')):
            stream = 'BT /F1 12 Tf 72 720 Td (%s) Tj ET' % text if text else ''
            objects[page] = ('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
                             '/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>' % (page + 1))
            objects[page + 1] = '<< /Length %d >>\nstream\n%s\nendstream' % (len(stream), stream)
        data, offsets = b'%PDF-1.4\n', []
        for number in sorted(objects):
            offsets.append(len(data))
            data += ('%d 0 obj\n%s\nendobj\n' % (number, objects[number])).encode('latin-1')
        xref = len(data)
        data += ('xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1)).encode()
        data += b''.join(b'%010d 00000 n \n' % o for o in offsets)
        data += ('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)).encode()
        p = self.root / self.case / '라운드1/우리증거/취업규칙.pdf'
        p.write_bytes(data)
        result = self.system.extract(p)
        self.assertIn('[PDF 순번 1]\nRules of Employment Article 10', result['text'])
        self.assertIn('[PDF 순번 2]', result['text'])
        self.assertIn('PDF 순번 2: 추출 텍스트 없음, 스캔/OCR 확인 필요', result['warnings'])
        self.assertNotIn('PDF 순번 1: 추출 텍스트 없음, 스캔/OCR 확인 필요', result['warnings'])

    def test_cp949_text_is_decoded_with_warning(self):
        p = self.root / self.case / '라운드1/우리증거/옛문서.txt'
        p.write_bytes('취업규칙 제10조'.encode('cp949'))
        result = self.system.extract(p)
        self.assertEqual(result['text'], '취업규칙 제10조')
        self.assertIn('CP949 디코딩 적용: 원문 문자 확인 필요', result['warnings'])

    def test_large_files_are_hashed_in_chunks(self):
        """녹음·영상 원본을 통째로 메모리에 올리지 않는다."""
        data = bytes(range(256)) * (3 * 4096 + 7)          # 1MB 단위를 넘는 3MB 남짓
        video = self.case + '/라운드1/우리증거/cctv.mp4'
        (self.root / video).write_bytes(data)
        with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('read_bytes')):
            current = self.system.scan(self.case, True)
            self.assertIn(video, current['added'])
            self.assertTrue(self.system.extract(self.input)['text'])
        listing = json.loads((self.root / self.case / '작업/자료목록.json').read_text(encoding='utf-8'))
        self.assertEqual(listing['files'][video], {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})

    def test_unsupported_format_is_rejected_before_hashing(self):
        extra = self.case + '/라운드1/우리증거/cctv.mp4'
        self.put(extra, '영상')
        with mock.patch.object(module, 'digest_file', side_effect=AssertionError('hashed')):
            with self.assertRaises(ValueError):
                self.system.extract(extra)

    def test_scan_keeps_folder_named_comparison_and_reports_skipped_dirs(self):
        """결과비교 기능은 지웠다. '비교' 폴더의 증거도 목록에 들어가고, 이름 규칙으로 뺀 폴더는 드러낸다."""
        compared = self.case + '/라운드1/우리증거/비교/취업규칙_개정전후.pdf'
        backup = self.case + '/라운드1/우리증거/백업/근로계약서_옛본.pdf'
        cache = self.case + '/작업/추출캐시/abc.json'
        for rel in (compared, backup, cache):
            self.put(rel, '자료')
        result = self.system.scan(self.case)
        self.assertIn(compared, result['added'])
        self.assertNotIn(backup, result['added'])
        self.assertNotIn(cache, result['added'])
        self.assertEqual(result['skipped_dirs'], [self.case + '/라운드1/우리증거/백업'])

    def test_case_number_reads_every_court_record_file_name(self):
        """공통/판례기록 의 법원·노동위원회 결정 파일명은 모두 사건번호로 읽혀야 한다."""
        names = [p.stem.split('_', 1) for p in (REPO / '공통/판례기록').glob('*_*.md')]
        courts = [(org, number) for org, number in names if '법원' in org or org.endswith('노동위원회')]
        if not courts:
            self.skipTest('판례기록 파일이 없다')
        missed = [org + '_' + number for org, number in courts if not re.fullmatch(module.CASE_NUMBER, number)]
        self.assertEqual(missed, [])

    def test_case_types_match_lbox_js_copy(self):
        """lbox-검색 스킬의 JS 사건부호는 import 할 수 없는 사본이다. 목록이 같은지 본다."""
        skill = REPO / '.claude/skills/lbox-검색/SKILL.md'
        found = re.search(r"const 사건부호 = ((?:'[^']*'\s*\+?\s*)+);",
                          skill.read_text(encoding='utf-8') if skill.is_file() else '')
        if not found:
            self.skipTest('lbox-검색 스킬에 JS 사건부호가 없다')
        self.assertEqual(''.join(re.findall(r"'([^']*)'", found[1])), module.CASE_TYPES)

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

    def test_style_scoring_does_not_read_review_opinion_guide(self):
        """문체검증은 소송 서면 기준으로 채점한다. 검토의견서용 문체가이드는 '생각건대'를 권하는 등 반대다."""
        self.assertNotIn('1_검토의견/문체가이드-서면.md', module.GUIDE_SETS['문체검증'])
        self.assertIn(module.STYLE + 'references/문체-용례.md', module.GUIDE_SETS['문체검증'])

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
