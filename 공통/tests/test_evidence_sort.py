"""우리·상대 증거 나누기(4_서면작성/scripts/evidence_sort.py)를 확인한다.

제출자·호증 표시로 나누는지, 이름이 잘린 파일도 호증 표시로 가리는지, 표시가 없는 파일은 그대로 두는지,
옮기면서 호증읽기 기록의 경로를 고치는지, 같은 이름이 있으면 덮어쓰지 않는지를 본다.
"""
import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('evidence_sort', ROOT / '4_서면작성/scripts/evidence_sort.py')
es = importlib.util.module_from_spec(spec)
spec.loader.exec_module(es)

우리서면 = '광주고등법원_2025나21206_168001_2026.06.19_준비서면_(준비서면)_원고 대리인_법무법인 평안.pdf'
우리서증 = '광주고등법원_2025나21206_003015_2024.02.02_소장_서증_징계처분장_(갑15-1_징계처분장)_원고 대리인_법무법인 평안.pdf'
피고서면 = '광주고등법원_2025나21206_087001_2026.10.08_준비서면_(준비서면)_피고 대리인_법무법인(유한)바른.pdf'
피고서증 = '광주고등법원_2025나21206_088137_2026.10.08_준비서면_서증_계좌거래내역_(을109-5_계좌거래내역)_피고 대리인_법무법인(유한)바른.pdf'
잘린서증 = '광주고등법원_2025나21206_015017_2024.07.17_준비서면_서증_긴 표제_(을17_긴 표제)_피'
잘린우리 = '광주고등법원_2025나21206_003050_2024.02.02_소장_서증_긴 표제_(갑50-2_긴 표제)_원고 대리'
법원1 = '광주고등법원_2025나21206_006001_2024.02.13_참여관용 보정명령(인지대송달료)_(참여관용 보정명령(인지대송달료)).pdf'
법원2 = '광주고등법원_2025나21206_009001_2025.04.24_변론조서 (3회)_(변론조서)_참여_임낙주.pdf'
제3자 = '광주고등법원_2025나21206_046001_2026.08.27_금융거래정보제공요구에 대한 회신_(금융거래정보제공요구에 대한 회신)_기타_국민은행 업무지원센터.pdf'
의뢰인 = '손영애 소명자료.hwp'


class SortTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / '4_서면작성' / '사건' / '한전'
        self.r = self.case / '라운드1'
        for d in ('우리증거', '상대증거'):
            (self.r / d).mkdir(parents=True)
        for n in (우리서면, 우리서증, 피고서면, 피고서증, 잘린서증, 잘린우리, 법원1, 법원2, 제3자, 의뢰인):
            (self.r / '우리증거' / n).write_bytes(b'x')

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args):
        with redirect_stdout(io.StringIO()) as o:
            code = es.main([str(self.case), *args])
        return code, o.getvalue()

    def test_plan_puts_each_file_on_its_side(self):
        안 = es.계획(self.case, self.r)
        새자리 = {n: 새 for _, 새, n, _ in 안['옮김']}
        self.assertEqual(새자리[피고서면], es.상대)
        self.assertEqual(새자리[피고서증], es.상대)
        self.assertEqual(새자리[잘린서증], es.상대)      # 제출자가 잘려도 호증 표시로 가린다
        self.assertEqual(새자리[법원1], es.참고)
        self.assertEqual(새자리[법원2], es.참고)
        self.assertEqual(새자리[제3자], es.참고)
        for n in (우리서면, 우리서증, 잘린우리):
            self.assertNotIn(n, 새자리)
        self.assertEqual([n for _, n, _ in 안['그대로']], [의뢰인])     # 표시가 없으면 옮기지 않고 보인다

    def test_list_of_exhibits_decides_the_side_of_a_prefix(self):
        (self.case / '증거관리').mkdir()
        (self.case / '증거관리' / '우리호증목록.md').write_text('| 호증 |\n|---|\n| 사 제1호증 | a |\n', encoding='utf-8')
        (self.case / '증거관리' / '상대호증목록.md').write_text('| 호증 |\n|---|\n| 노 제1호증 | a |\n', encoding='utf-8')
        (self.r / '우리증거' / '노제1호증_취업규칙.pdf').write_bytes(b'x')
        (self.r / '상대증거' / '사제2호증_문자.pdf').write_bytes(b'x')
        안 = es.계획(self.case, self.r)
        새자리 = {n: (옛, 새) for 옛, 새, n, _ in 안['옮김']}
        self.assertEqual(새자리['노제1호증_취업규칙.pdf'], (es.우리, es.상대))
        self.assertEqual(새자리['사제2호증_문자.pdf'], (es.상대, es.우리))      # 반대쪽에 잘못 든 것도 옮긴다

    def test_apply_moves_and_fixes_paths_and_is_idempotent(self):
        기록 = self.case / '증거관리' / '호증읽기'
        기록.mkdir(parents=True)
        (기록 / '을109-5.md').write_text(f'# 기록\n\n파일: 라운드1/우리증거/{피고서증}\n해시: abc\n', encoding='utf-8')
        (self.r / '작업').mkdir()
        (self.r / '작업' / '메모.md').write_text(f'피고 서면은 우리증거/{피고서면} 에 있다.\n', encoding='utf-8')
        code, _ = self.run_main('--apply')
        self.assertEqual(code, 0)
        self.assertTrue((self.r / '상대증거' / 피고서면).is_file())
        self.assertFalse((self.r / '우리증거' / 피고서면).exists())
        self.assertTrue((self.r / '참고자료' / 법원1).is_file())
        self.assertTrue((self.r / '우리증거' / 의뢰인).is_file())
        self.assertIn(f'파일: 라운드1/상대증거/{피고서증}', (기록 / '을109-5.md').read_text(encoding='utf-8'))
        self.assertIn(f'상대증거/{피고서면}', (self.r / '작업' / '메모.md').read_text(encoding='utf-8'))
        code, 글 = self.run_main('--확인')
        self.assertEqual(code, 0, 글)
        code, 글 = self.run_main('--apply')
        self.assertIn('옮김 0건', 글)

    def test_check_reports_mixed_folder(self):
        code, 글 = self.run_main('--확인')
        self.assertEqual(code, 1)
        self.assertTrue((self.r / '우리증거' / 피고서면).is_file())     # --확인 은 옮기지 않는다

    def test_same_name_is_not_overwritten(self):
        (self.r / '상대증거' / 피고서면).write_bytes(b'other')
        code, 글 = self.run_main('--apply')
        self.assertEqual(code, 1)
        self.assertEqual((self.r / '상대증거' / 피고서면).read_bytes(), b'other')
        self.assertTrue((self.r / '우리증거' / 피고서면).is_file())
        self.assertIn('막힘', 글)

    def test_subfolders_stay(self):
        d = self.r / '우리증거' / '노정일 회신 자료(2026.11.2.)'
        d.mkdir()
        (d / 피고서증).write_bytes(b'x')
        self.run_main('--apply')
        self.assertTrue((d / 피고서증).is_file())

    def test_unknown_side_is_left_alone(self):
        for n in os.listdir(self.r / '우리증거'):
            (self.r / '우리증거' / n).unlink()
        (self.r / '우리증거' / 피고서면).write_bytes(b'x')      # 평안이 낸 파일이 없어 어느 쪽이 우리인지 모른다
        안 = es.계획(self.case, self.r)
        self.assertEqual(안['옮김'], [])
        self.assertEqual(안['그대로'][0][1], 피고서면)


if __name__ == '__main__':
    unittest.main()
