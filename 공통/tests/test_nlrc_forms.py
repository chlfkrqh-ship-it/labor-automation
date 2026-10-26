"""4_서면작성/scripts/nlrc_forms.py(`/노동위서류`)의 지시표 해석을 확인한다.

한글 자동화는 한글이 깔린 Windows PC에서만 돌므로 여기서는 양식을 열지 않는다. 지시표에서 '양식에 할 일'을
짓는 부분만 본다. 2026. 10. 14. 근로자 쪽 지시표로 처음 돌렸을 때 서류는 오류 없이 나왔는데 지정서 본문이
'이 사건 사용자의 대리인'으로, 선임신고서의 √가 사용자에 남아 있었다(그 글이 누름틀과 조판 부호로 나뉘어 있어
낱말로는 바뀌지 않았다). 그래서 대리하는 쪽에 따라 달라지는 글은 문단을 통째로 바꾸고, 만든 문서에 그 글이
들어 있는지를 확인 목록에 넣었다.

- 리눅스·클라우드 세션에서도 가져올 수 있어야 한다(pywin32 는 한글을 띄울 때에만 가져온다).
- 직인 그림이 든 한글 양식은 git 에 올라가지 않고, 지시표 본보기와 스크립트는 올라간다.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '4_서면작성' / 'scripts' / 'nlrc_forms.py'
spec = importlib.util.spec_from_file_location('nlrc_forms', SCRIPT)
nlrc_forms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nlrc_forms)
FormError = nlrc_forms.FormError


def sample(**change):
    """가공값 지시표. 사건 자료를 쓰지 않는다."""
    data = {
        '의뢰인': '가나다', '판': '초안', '노동위원회': '서울지방노동위원회',
        '사건': '서울2026부해0000 부당해고 구제신청', '우리쪽': '사용자',
        '당사자': {'이름': '주식회사 가나다', '대표자': '대표이사 홍길동', '주소': '서울 서초구 서초대로 1', '전화': ''},
        '참석자명단': {'일시': '2026년 12월 1일(화요일), 14시 00분', '참석자': [], '제출일': '', '제출자': '최 락 보'},
        '지정서': {'구분': '담당노무사', '성명': '최락보', '날짜': ''},
        '선임신고서': {'사건표기': '', '담당': '변호사 라마바, 노무사 최락보', '신고인': '법무법인 평안', '날짜': ''},
    }
    data.update(change)
    return data


def kinds_of(ops):
    return [(kind, old) for kind, old, _ in ops]


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.round = Path(self.tmp.name) / '라운드1'
        (self.round / '작업').mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data, encoding='utf-8'):
        (self.round / '작업' / nlrc_forms.SPEC_NAME).write_text(json.dumps(data, ensure_ascii=False), encoding=encoding)

    def test_missing_spec_tells_to_run_init(self):
        with self.assertRaisesRegex(FormError, 'init'):
            nlrc_forms.load_spec(self.round)

    def test_spec_saved_with_bom_is_read(self):
        self.write(sample(), encoding='utf-8-sig')      # 메모장으로 고쳐 저장하면 BOM 이 붙는다
        self.assertEqual(nlrc_forms.load_spec(self.round)['의뢰인'], '가나다')

    def test_side_must_be_one_of_three(self):
        self.write(sample(우리쪽='피신청인'))
        with self.assertRaisesRegex(FormError, '우리쪽'):
            nlrc_forms.load_spec(self.round)

    def test_empty_required_value_is_named(self):
        self.write(sample(사건=''))
        with self.assertRaisesRegex(FormError, '사건'):
            nlrc_forms.load_spec(self.round)
        self.write(sample(당사자={'이름': ' ', '주소': ''}))
        with self.assertRaisesRegex(FormError, '이름'):
            nlrc_forms.load_spec(self.round)

    def test_init_copies_sample_and_keeps_existing_spec(self):
        source = ROOT / '4_서면작성' / 'templates' / '노동위원회' / nlrc_forms.SAMPLE_SPEC
        self.assertTrue(source.is_file(), '지시표 본보기는 git 으로 추적하는 파일이다')
        target = self.round / '작업' / nlrc_forms.SPEC_NAME
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            self.assertEqual(nlrc_forms.cmd_init(self.round), 0)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.write(sample(의뢰인='이미 채운 지시표'))
            self.assertEqual(nlrc_forms.cmd_init(self.round), 0)
        self.assertIn('이미 채운 지시표', target.read_text(encoding='utf-8'))
        self.assertIn('이미 있습니다', said.getvalue())

    def test_sample_spec_has_every_part_and_no_case_data(self):
        data = json.loads((ROOT / '4_서면작성' / 'templates' / '노동위원회' / nlrc_forms.SAMPLE_SPEC).read_text(encoding='utf-8'))
        for kind in nlrc_forms.KINDS:
            self.assertIn(kind, data)
        self.assertIn(data['우리쪽'], nlrc_forms.SIDES)
        self.assertEqual(data['선임신고서']['신고인'], '법무법인 평안')   # 새로 더하는 담당자가 아니라 이미 선임된 대리인
        self.assertEqual(data['참석자명단']['참석자'], [])
        self.assertIn('○', data['사건'])                                 # 본보기에는 실제 사건번호를 적지 않는다
        seal = data['참석자명단']['도장']                                  # 그림 자체는 PC마다 따로 둔다. 본보기에는 이름만
        self.assertEqual(Path(seal).name, seal)
        self.assertIn(data['참석자명단']['제출자'].replace(' ', ''), Path(seal).stem)

    def test_build_without_any_part_fails(self):
        data = sample()
        for kind in nlrc_forms.KINDS:
            del data[kind]
        self.write(data)
        with self.assertRaisesRegex(FormError, '만들 서류'):
            nlrc_forms.cmd_build(self.round, None)
        with self.assertRaisesRegex(FormError, '지정서'):
            nlrc_forms.cmd_build(self.round, ['지정서'])

    def test_missing_template_points_to_onedrive(self):
        original = nlrc_forms.TEMPLATES
        nlrc_forms.TEMPLATES = Path(self.tmp.name) / '없는 폴더'
        try:
            with self.assertRaisesRegex(FormError, 'OneDrive'):
                nlrc_forms.template_path('지정서')
        finally:
            nlrc_forms.TEMPLATES = original

    def test_command_line_reports_error_without_traceback(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'build', str(self.round)], capture_output=True)
        text = result.stdout.decode('utf-8', 'replace')
        self.assertEqual(result.returncode, 1)
        self.assertIn('오류: 지시표가 없습니다', text)
        self.assertNotIn(b'Traceback', result.stderr)
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'look', str(self.round / '없는 문서.hwp')], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('파일이 없습니다', result.stdout.decode('utf-8', 'replace'))


class NameTests(unittest.TestCase):
    def test_output_names_follow_brief_naming_rule(self):
        data = sample()
        self.assertEqual(nlrc_forms.output_stem(data, '참석자명단'), '(가나다) 심문회의 참석자 명단_초안')
        self.assertEqual(nlrc_forms.output_stem(data, '지정서'), '(가나다) 담당노무사 추가 지정서_초안')
        self.assertEqual(nlrc_forms.output_stem(data, '선임신고서'), '(가나다) 대리인 선임신고서_초안')

    def test_role_and_stage_change_the_name(self):
        data = sample(판='1차 수정안', 지정서={'구분': '담당변호사', '성명': '라마바'})
        self.assertEqual(nlrc_forms.output_stem(data, '지정서'), '(가나다) 담당변호사 추가 지정서_1차 수정안')
        self.assertEqual(nlrc_forms.output_stem(sample(판=''), '선임신고서'), '(가나다) 대리인 선임신고서')


class DesignationTests(unittest.TestCase):
    def test_employer_side_keeps_row_labels(self):
        ops = nlrc_forms.designation_ops(sample())
        self.assertNotIn(('para', '근로자'), kinds_of(ops))
        self.assertEqual(ops[0], ('para', '위 사건에 관하여',
                                  '위 사건에 관하여 이 사건 사용자의 대리인인 당 법무법인은 아래 담당노무사를 추가 지정합니다.'))
        self.assertEqual(ops[-1][0], 'fit')                 # 사건 글이 두 줄이 되면 장평을 줄여 한 면에 맞춘다
        filled = {old: new for kind, old, new in ops if kind == 'replace'}
        self.assertEqual(filled['〔사건〕'], '서울2026부해0000 부당해고 구제신청')
        self.assertEqual(filled['〔사용자〕'], '주식회사 가나다')
        self.assertEqual(filled['〔성명〕'], '최락보')
        self.assertEqual(filled['〔노동위원회〕'], '서울지방노동위원회')
        self.assertEqual(filled['〔날짜〕'].replace(' ', ''), '...')   # 날짜를 모르면 빈 날짜로 둔다
        self.assertNotIn('담당노무사', filled)

    def test_worker_side_swaps_labels_before_filling_blanks(self):
        """✓가 있는 줄의 이름표를 바꾼다. 사건 글에 '근로자'·'사용자'가 들어 있을 수 있어 채우기보다 먼저 한다."""
        data = sample(우리쪽='근로자', 사건='서울2026부해0000 사용자 가나다의 근로자 부당해고 구제신청',
                      당사자={'이름': '홍길동', '주소': '서울 서초구 서초대로 1'})
        ops = nlrc_forms.designation_ops(data)
        order = kinds_of(ops)
        self.assertEqual(order[:3], [('para', '근로자'), ('para', '사용자'), ('replace', '〔다른쪽〕')])
        self.assertEqual(ops[1][2], '근로자')
        self.assertEqual(ops[2][2], '사용자')
        self.assertLess(order.index(('para', '사용자')), order.index(('replace', '〔사건〕')))
        sentence = [new for kind, old, new in ops if old == '위 사건에 관하여'][0]
        self.assertIn('이 사건 근로자의 대리인인', sentence)
        self.assertNotIn('사용자', sentence)

    def test_union_side_and_lawyer_role(self):
        data = sample(우리쪽='노동조합', 지정서={'구분': '담당변호사', '성명': '라마바', '날짜': '2026.   11.   30.'})
        ops = nlrc_forms.designation_ops(data)
        self.assertIn(('replace', '담당노무사', '담당변호사'), ops)
        self.assertIn(('replace', '〔날짜〕', '2026.   11.   30.'), ops)
        self.assertEqual(nlrc_forms.designation_sentence(data),
                         '위 사건에 관하여 이 사건 노동조합의 대리인인 당 법무법인은 아래 담당변호사를 추가 지정합니다.')
        # 만든 문서에 대리하는 쪽에 맞는 문장이 들어 있는지를 확인 목록이 본다
        self.assertIn(nlrc_forms.designation_sentence(data), nlrc_forms.expected_texts(data, '지정서'))

    def test_bad_role_or_missing_name_fails(self):
        with self.assertRaisesRegex(FormError, '구분'):
            nlrc_forms.designation_ops(sample(지정서={'구분': '담당자', '성명': '최락보'}))
        with self.assertRaisesRegex(FormError, '성명'):
            nlrc_forms.designation_ops(sample(지정서={'구분': '담당노무사', '성명': ''}))


class AppointmentTests(unittest.TestCase):
    def test_side_line_checks_exactly_one_side(self):
        lines = {side: nlrc_forms.appointment_side_line(side) for side in nlrc_forms.SIDES}
        for side, line in lines.items():
            self.assertEqual(line.count('[√]'), 1, side)
            self.assertEqual(line.count('[  ]'), 2, side)
            self.assertIn('[√]' + (' 노동조합' if side == '노동조합' else side), line)
        # √ 자리만 다르고 나머지 글자와 빈칸은 양식 그대로이다
        self.assertEqual(len({line.replace('[√]', '[  ]') for line in lines.values()}), 1)

    def test_employer_side_leaves_side_line_as_template(self):
        ops = nlrc_forms.appointment_ops(sample())
        self.assertNotIn(('para', '해당란에'), kinds_of(ops))
        filled = {old: new for kind, old, new in ops}
        self.assertEqual(filled['〔위임인〕'], '주식회사 가나다 대표이사 홍길동')
        self.assertEqual(filled['〔신고인〕'], '법무법인 평안')
        self.assertEqual(filled['〔담당〕'], '변호사 라마바, 노무사 최락보')

    def test_worker_side_rewrites_side_line(self):
        data = sample(우리쪽='근로자', 당사자={'이름': '홍길동', '주소': '서울 서초구 서초대로 1', '전화': '010-0000-0000'})
        ops = nlrc_forms.appointment_ops(data)
        self.assertIn(('para', '해당란에', nlrc_forms.appointment_side_line('근로자')), ops)
        self.assertIn(nlrc_forms.appointment_side_line('근로자').strip(), nlrc_forms.expected_texts(data, '선임신고서'))
        self.assertIn(('replace', '〔위임인〕', '홍길동'), ops)       # 대표자가 없으면 이름만 적는다

    def test_phone_decides_how_address_is_written(self):
        without = nlrc_forms.appointment_ops(sample())
        self.assertIn(('para', '〔위임인 주소〕', ' 서울 서초구 서초대로 1'), without)   # 전화 칸까지 문단째 바꾼다
        self.assertNotIn('〔위임인 전화〕', [old for _, old, _ in without])
        data = sample(당사자={'이름': '주식회사 가나다', '주소': '서울 서초구 서초대로 1', '전화': '02-000-0000'})
        with_phone = nlrc_forms.appointment_ops(data)
        self.assertIn(('replace', '〔위임인 주소〕', '서울 서초구 서초대로 1'), with_phone)
        self.assertIn(('replace', '〔위임인 전화〕', '02-000-0000'), with_phone)

    def test_case_label_for_this_form_only(self):
        data = sample(선임신고서={'사건표기': '서울2026부해0000 · 부당해고 구제신청', '담당': '노무사 최락보', '신고인': '법무법인 평안'})
        self.assertIn(('replace', '〔사건〕', '서울2026부해0000 · 부당해고 구제신청'), nlrc_forms.appointment_ops(data))
        self.assertIn('서울2026부해0000 · 부당해고 구제신청', nlrc_forms.expected_texts(data, '선임신고서'))
        self.assertIn(('replace', '〔사건〕', '서울2026부해0000 부당해고 구제신청'), nlrc_forms.designation_ops(data))

    def test_missing_address_or_filer_fails(self):
        with self.assertRaisesRegex(FormError, '주소'):
            nlrc_forms.appointment_ops(sample(당사자={'이름': '주식회사 가나다', '주소': ''}))
        with self.assertRaisesRegex(FormError, '신고인'):
            nlrc_forms.appointment_ops(sample(선임신고서={'담당': '노무사 최락보', '신고인': ''}))


class SealTests(unittest.TestCase):
    """참석자 명단 제출자의 도장. 그림은 사람의 도장이어서 저장소·OneDrive 밖(PC마다 %LOCALAPPDATA%)에 둔다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = nlrc_forms.SEAL_DIR
        nlrc_forms.SEAL_DIR = Path(self.tmp.name)

    def tearDown(self):
        nlrc_forms.SEAL_DIR = self.original
        self.tmp.cleanup()

    def test_seal_is_optional(self):
        self.assertIsNone(nlrc_forms.seal_file({'제출자': '최 락 보'}))
        self.assertIsNone(nlrc_forms.seal_file({'제출자': '최 락 보', '도장': ' '}))

    def test_missing_seal_names_where_to_put_it(self):
        part = {'제출자': '최 락 보', '도장': '최락보_인.png'}
        with self.assertRaisesRegex(FormError, '도장 그림이 이 PC 에 없습니다'):
            nlrc_forms.seal_file(part)
        (Path(self.tmp.name) / '최락보_인.png').write_bytes(b'\x89PNG')
        self.assertEqual(nlrc_forms.seal_file(part), Path(self.tmp.name) / '최락보_인.png')

    def test_seal_must_belong_to_the_filer_and_be_a_bare_name(self):
        (Path(self.tmp.name) / '최락보_인.png').write_bytes(b'\x89PNG')
        with self.assertRaisesRegex(FormError, '제출자'):
            nlrc_forms.seal_file({'제출자': '강 민 석', '도장': '최락보_인.png'})
        for path in (r'C:\도장\최락보_인.png', '도장/최락보_인.png'):
            with self.assertRaisesRegex(FormError, '파일 이름만'):
                nlrc_forms.seal_file({'제출자': '최 락 보', '도장': path})

    def test_seal_folder_is_outside_the_repository(self):
        self.assertNotIn(str(ROOT), str(self.original))


class SavedTableTests(unittest.TestCase):
    """참석자 명단은 저장한 hwpx 를 다시 읽어 칸마다 맞댄다. 그 읽기를 지어 만든 표로 본다."""

    def test_cells_are_read_by_row_and_column(self):
        try:
            import lxml  # noqa: F401
        except ImportError:
            self.skipTest('lxml 이 없다')
        hp = nlrc_forms.HP

        def cell(row, col, *paragraphs):
            body = ''.join('<hp:p><hp:run><hp:t>%s</hp:t></hp:run></hp:p>' % p for p in paragraphs)
            return '<hp:tc><hp:subList>%s</hp:subList><hp:cellAddr colAddr="%d" rowAddr="%d"/></hp:tc>' % (body, col, row)

        xml = ('<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:hp="%s"><hp:p><hp:run>'
               '<hp:tbl rowCnt="2" colCnt="2"><hp:tr>%s%s</hp:tr><hp:tr>%s%s</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>') % (
                   hp, cell(0, 0, '사건'), cell(0, 1, ' 서울2026부해0000<hp:fwSpace/>부당해고'),
                   cell(1, 0, '[√] 사 용 자'), cell(1, 1, '첫 줄', '둘째 줄'))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'out.hwpx'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('Contents/section0.xml', xml)
            cells, rows = nlrc_forms.read_saved_cells(path)
        self.assertEqual(rows, 2)
        self.assertEqual(cells[(0, 1)], ' 서울2026부해0000부당해고')     # 조판 부호 뒤의 글도 이어 읽는다
        self.assertEqual(cells[(1, 0)], '[√] 사 용 자')
        self.assertEqual(cells[(1, 1)], '첫 줄\n둘째 줄')


@unittest.skipIf(shutil.which('git') is None, 'git 이 없다')
class GitignoreTests(unittest.TestCase):
    """지정서·선임신고서 양식에는 사무소 직인 그림이 들어 있다. git 에 올라가면 안 된다."""

    def test_form_templates_stay_out_of_git_and_system_files_stay_in(self):
        folder = '4_서면작성/templates/노동위원회/'
        forms = [folder + name for name in nlrc_forms.TEMPLATE_FILES.values()]
        outputs = ['4_서면작성/사건/가나다_부당해고/라운드1/작업/' + nlrc_forms.SPEC_NAME,
                   '4_서면작성/사건/가나다_부당해고/라운드1/작업/노동위서류_확인/지정서.png',
                   '(가나다) 대리인 선임신고서_초안.hwp', '(가나다) 대리인 선임신고서_초안.pdf']
        tracked = [folder + nlrc_forms.SAMPLE_SPEC, '4_서면작성/scripts/nlrc_forms.py',
                   '공통/tests/test_nlrc_forms.py', '.claude/commands/노동위서류.md']
        with tempfile.TemporaryDirectory() as repo:
            subprocess.run(['git', 'init', '-q'], cwd=repo, check=True, capture_output=True)
            shutil.copyfile(ROOT / '.gitignore', Path(repo) / '.gitignore')
            paths = forms + outputs + tracked
            result = subprocess.run(['git', 'check-ignore', '--no-index', '--stdin', '-z'],
                                    input='\0'.join(paths).encode('utf-8'), cwd=repo, capture_output=True)
            self.assertIn(result.returncode, (0, 1), result.stderr.decode('utf-8', 'replace'))
            ignored = {p for p in result.stdout.decode('utf-8').split('\0') if p}
        self.assertEqual(sorted(set(forms + outputs) - ignored), [])
        self.assertEqual(sorted(ignored & set(tracked)), [])


if __name__ == '__main__':
    unittest.main()
