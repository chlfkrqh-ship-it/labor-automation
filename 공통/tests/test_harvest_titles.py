"""수확 목록 다시 훑기(공통/scripts/harvest_titles.py scan)를 확인한다.

나눈 LBOX 목록(`LBOX_목록_2차.tsv`)도 읽는지, 주소 그대로 저장된 id('%EA%B5%AD…')를 글자로 풀어 기록과 맞대는지 본다.
2026. 11. 2. 첫 밤 점검에서 최종 관문이 같은 낱말로 다시 훑을 때 2차·3차 목록을 빠뜨리고, 주소 꼴 id 를 모두 '기록에 없음'으로 세었다.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import quote

ROOT = Path(__file__).parents[2]
HEAD = 'id\t법원\t선고일\t사건\t출처\t스니펫\n'


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / '사건'
        (self.case / '작업').mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self, *words):
        out = self.case / '결과.md'
        r = subprocess.run([sys.executable, '-B', str(ROOT / '공통/scripts/harvest_titles.py'), 'scan', str(self.case),
                            '--낱말', *words, '--out', str(out)], capture_output=True,
                           env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(r.returncode, 0, r.stderr.decode('utf-8', 'replace'))
        text = out.read_text(encoding='utf-8')
        out.unlink()
        return text

    def test_split_lists_are_read_and_quoted_ids_are_decoded(self):
        (self.case / '작업' / 'LBOX_목록.tsv').write_text(
            HEAD + '대법원-2020두1\t대법원\t20-01-01\t해고무효\tq\t요양원 사건\n', encoding='utf-8')
        encoded = quote('서울행정법원-2021구합7', safe='-')
        (self.case / '작업' / 'LBOX_목록_2차.tsv').write_text(
            HEAD + encoded + '\t서울행정법원\t21-01-01\t정직\tq\t요양원 원장\n', encoding='utf-8')
        (self.case / '작업' / '검색기록.md').write_text('유사 사례: 2021구합7 미반영(사안이 다름)\n', encoding='utf-8')
        t = self.scan('요양원')
        self.assertIn('LBOX 목록 2개 파일 · 2줄', t)
        self.assertIn('걸린 줄 2건 — 기록에 있음 1건, 없음 1건', t)      # 2차 목록의 줄도 걸리고, 푼 번호로 기록을 찾는다
        self.assertIn('서울행정법원-2021구합7', t)
        self.assertNotIn('%EC', t)
        self.assertIn('| 대법원-2020두1 |', t.split('## 기록에 있는 줄')[0])


if __name__ == '__main__':
    unittest.main()
