"""공단 산재판례 도구(공통/scripts/comwel.py)와 판결 PDF 되살리기(lbox_b64_save.py)의 --out 을 확인한다.

2026. 11. 10. OES 근골격계: `comwel.py 판례 … --심급 --out "…/2018누40180_심급.md"` 로 그 이름의 폴더가 생겨, 그 '파일'을 읽던
세션과 `harvest_titles.py scan` 이 Windows 의 '권한 없음'으로 멈췄다. 그 세션은 `공통/공공기관자료.md` 에 글로만 적었다.
--out 이 파일 이름이면 아무것도 만들기 전에(누리집에 요청하기 전에) 멈춘다.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[2]


def run(script, *args):
    return subprocess.run([sys.executable, '-B', str(ROOT / '공통/scripts' / script), *map(str, args)], capture_output=True,
                          env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, timeout=60)


class OutIsAFolderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_comwel_refuses_a_file_name_before_making_anything(self):
        for cmd in (['판례', '2018누40180_서울고등법원', '--심급'], ['판례찾기', '척추관협착증'], ['심사', '12345']):
            out = self.dir / '2018누40180_심급.md'
            r = run('comwel.py', *cmd, '--out', out)
            self.assertEqual(r.returncode, 2, r.stderr.decode('utf-8', 'replace'))
            self.assertIn('--out 은 폴더 이름이다', r.stderr.decode('utf-8', 'replace'))
            self.assertFalse(out.exists())                   # 폴더도 파일도 만들지 않는다

    def test_lbox_b64_save_refuses_a_file_name(self):
        res = self.dir / 'result.json'
        res.write_text('{}', encoding='utf-8')
        out = self.dir / '판결.pdf'
        r = run('lbox_b64_save.py', res, '--out', out)
        self.assertEqual(r.returncode, 2)
        self.assertIn('--out 은 저장할 폴더이다', r.stderr.decode('utf-8', 'replace'))
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
