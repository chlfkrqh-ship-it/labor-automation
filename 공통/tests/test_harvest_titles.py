"""수확 목록 다시 훑기(공통/scripts/harvest_titles.py scan)를 확인한다.

나눈 LBOX 목록(`LBOX_목록_2차.tsv`)도 읽는지, 주소 그대로 저장된 id('%EA%B5%AD…')를 글자로 풀어 기록과 맞대는지 본다.
2026. 11. 2. 첫 밤 점검에서 최종 관문이 같은 낱말로 다시 훑을 때 2차·3차 목록을 빠뜨리고, 주소 꼴 id 를 모두 '기록에 없음'으로 세었다.
"""
import os
from pathlib import Path
import re
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

    def run_scan(self, out, *extra):
        r = subprocess.run([sys.executable, '-B', str(ROOT / '공통/scripts/harvest_titles.py'), 'scan', str(self.case),
                            '--낱말', '요양원', '--out', str(out), *extra], capture_output=True,
                           env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(r.returncode, 0, r.stderr.decode('utf-8', 'replace'))
        return out.read_text(encoding='utf-8')

    def test_handling_is_written_per_row_and_carried_over(self):
        """기록에 없는 줄과 번호가 없는 줄은 '처리' 칸에 줄마다 적고, 같은 --out 이나 --잇기 로 다시 돌려도 이어진다.
        2026. 11. 3. 점검: 묶은 한 문장으로 기록에 없는 줄 161건을 가렸다. '같음'만 적은 칸은 빈 칸이다."""
        (self.case / '작업' / 'LBOX_목록.tsv').write_text(
            HEAD + '대법원-2020두1\t대법원\t20-01-01\t해고무효\tq\t요양원 사건\n'
            + '서울행정법원-2021구합7\t서울행정법원\t21-01-01\t정직\tq\t요양원 원장\n'
            + '서울행정법원-2019구합OOO\t서울행정법원\t19-01-01\t해임처분취소\tq\t요양원 직원\n', encoding='utf-8')
        out = self.case / '작업' / '수확목록_재확인.md'
        t = self.run_scan(out)
        self.assertIn('처리 칸이 빈 줄 3건', t)
        self.assertIn('| 기록 | 본문 | 처리 |', t.split('## 기록에 있는 줄')[0])
        t = t.replace('| 대법원-2020두1 | 20-01-01 | 대법원 | 해고무효 | 요양원 | 없음 | — |  |', '| 대법원-2020두1 | 20-01-01 | 대법원 | 해고무효 | 요양원 | 없음 | — | 사안 다름: 민간 병원 |')
        t = re.sub(r'(\| 서울행정법원-2019구합OOO \|.*\| 번호 없음 \| — \|)[ \t]*\|', r'\1 본문 읽음: 해임 양정 다툼, 하단 ② |', t)
        t = re.sub(r'(\| 서울행정법원-2021구합7 \|.*\| 없음 \| — \|)[ \t]*\|', r'\1 같음 |', t)
        out.write_text(t, encoding='utf-8')
        t = self.run_scan(out)
        self.assertIn('처리 칸이 빈 줄 1건', t)                          # '같음'만 적은 줄은 빈 칸으로 남는다
        self.assertIn('| 사안 다름: 민간 병원 |', t)
        self.assertIn('| 본문 읽음: 해임 양정 다툼, 하단 ② |', t)        # 번호가 가려진 줄은 id 와 제목으로 잇는다
        other = self.case / '작업' / '다른곳.md'
        self.run_scan(other, '--잇기', str(out))
        self.assertIn('처리 칸이 빈 줄 1건', other.read_text(encoding='utf-8'))   # 최종 관문처럼 다른 곳에 써도 이어 온다
        other.unlink()


if __name__ == '__main__':
    unittest.main()
