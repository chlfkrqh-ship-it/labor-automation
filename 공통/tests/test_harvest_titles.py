"""수확 목록 다시 훑기(공통/scripts/harvest_titles.py scan)를 확인한다.

나눈 LBOX 목록(`LBOX_목록_2차.tsv`)도 읽는지, 주소 그대로 저장된 id('%EA%B5%AD…')를 글자로 풀어 기록과 맞대는지 본다.
2026. 11. 2. 첫 밤 점검에서 최종 관문이 같은 낱말로 다시 훑을 때 2차·3차 목록을 빠뜨리고, 주소 꼴 id 를 모두 '기록에 없음'으로 세었다.
"""
import json
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
        t = re.sub(r'(\| 대법원-2020두1 \|.*\| 없음 \| — \|)[ \t]*\|', r'\1 사안 다름: 민간 병원 |', t)
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

    def test_lines_of_a_narrow_query_are_screened_without_any_word(self):
        """목록에 걸린 줄이 3줄 이하인 검색어의 줄은 낱말에 걸리지 않아도 뽑아 줄마다 처리를 적게 한다. 2026. 11. 11. `/하자보완`:
        최문희 강등 사건 첫 검색의 '"강등" "3개월간 정직"'(3줄)에 걸린 불리한 판결을 목록에서 버리고도 다시 훑기와 관문을 지났다."""
        좁은 = '"강등" "3개월간 정직"'
        줄 = [f'창원지방법원-2016구합51144\t지방법원\t16-10-18\t징계처분무효확인\t{좁은} / "강등" "이중징계"\t정직 3개월은 강등처분에 부수되는 효과',
              f'서울고등법원-2021누40722\t고등법원\t21-09-01\t강등처분취소\t{좁은}\t하나의 징계',
              '대법원-2019두1\t대법원\t19-01-01\t해임처분취소\t"강등" "이중징계"\t징계 일반']
        넓은 = [f'서울행정법원-2020구합{n}\t지방법원\t20-01-01\t정직처분취소\t"강등" "이중징계"\t징계 양정' for n in range(10, 14)]
        (self.case / '작업' / 'LBOX_목록.tsv').write_text(HEAD + '\n'.join(줄 + 넓은) + '\n', encoding='utf-8')
        (self.case / '작업' / '검색기록.md').write_text('서울고법 2021누40722 정독\n', encoding='utf-8')
        법제처 = self.case / '작업' / '법제처'                      # 같은 글의 검색어라도 법제처에서 1줄이면 LBOX 줄까지 좁은 것으로 보지 않는다
        법제처.mkdir()
        (법제처 / '법제처_목록.json').write_text(json.dumps({'판례': {'rows': [
            {'종류': '판례', '사건번호': '2012구합999', '기관': '서울행정법원', '일자': '2013.01.01', '제목': '강등처분취소', '검색어': '"강등" "이중징계"', 'id': '1'}]}},
            ensure_ascii=False), encoding='utf-8')
        out = self.case / '작업' / '수확목록_재확인.md'
        t = self.run_scan(out)                                  # 낱말 '요양원'은 어느 줄에도 걸리지 않는다
        self.assertIn('좁은 검색어(목록에 걸린 줄이 3줄 이하인 검색어) 2개', t)
        self.assertIn('걸린 줄 3건 — 기록에 있음 1건, 없음 2건', t)
        없는 = t.split('## 기록에 있는 줄')[0]
        self.assertIn('| 창원지방법원-2016구합51144 |', 없는)
        self.assertIn('좁은 검색어 "강등" "3개월간 정직"', 없는)
        self.assertIn('| 2012구합999 |', 없는)
        self.assertIn('처리 칸이 빈 줄 2건', t)
        self.assertNotIn('2019두1', t)                           # 줄이 많은 검색어에만 걸린 줄은 낱말로 가린다
        self.assertNotIn('2020구합10', t)

    def test_court_site_list_is_read_like_the_lawgo_list(self):
        """법원 누리집 목록(scourt.py harvest 의 법원_목록.json)도 읽는다. 2026. 11. 11. LBOX 를 멈추며 하급심을 보태는 경로로 넣었다.
        게시물을 열지 않은 줄은 번호가 없어 '번호 없음'으로, 법원/ 폴더 안의 받은 본문(법원_본문_*.md)은 기록이 아니라 '본문'으로 센다."""
        법원 = self.case / '작업' / '법원'
        법원.mkdir()
        (법원 / '법원_목록.json').write_text(json.dumps({
            '주요판결': {'rows': [
                {'종류': '주요판결', 'id': '44-300', '사건번호': '2025구합300', '기관': '서울행정법원', '일자': '2026-06-01',
                 '제목': '[노동] 요양원 원장 징계해고 사안', '검색어': '요양원'},
                {'종류': '주요판결', 'id': '44-100', '사건번호': '', '기관': '서울행정법원', '일자': '',
                 '제목': '[노동] 요양원 해고 사안 ...', '검색어': '요양원'}]},
            '공보': {'rows': [
                {'종류': '공보', 'id': 'gongbo-2025가합200819', '사건번호': '2025가합200819', '기관': '대전지법', '일자': '2026-09-03',
                 '제목': '요양원징계무효확인의소', '확정': '확정', '검색어': '요양원'}]}}, ensure_ascii=False), encoding='utf-8')
        (법원 / '법원_본문_주요판결.md').write_text('## [주요판결] 서울행정법원 2026-06-01 2025구합300 요양원\n', encoding='utf-8')
        (self.case / '작업' / '검색기록.md').write_text('유사 사례: 2025가합200819 미반영(사안이 다름)\n', encoding='utf-8')
        t = self.scan('요양원')
        self.assertIn('법원 누리집 목록 1개 파일 · 3줄', t)
        self.assertIn('걸린 줄 3건 — 기록에 있음 1건, 없음 1건(그 가운데 법제처·법원 본문을 받은 것 1건), 번호가 없어 가리지 못한 것 1건', t)
        없는 = t.split('## 기록에 있는 줄')[0]
        self.assertIn('| 법원-주요판결 | 2025구합300 |', 없는)       # 받은 본문에 번호가 있어도 기록은 아니다
        self.assertIn('| 받음 |', 없는)
        self.assertIn('| 법원-공보 | 2025가합200819 |', t.split('## 기록에 있는 줄')[1])
        # 법고을은 법제처와 같은 판례 자료이다. 법제처 줄과 사건번호가 같은 법고을 줄은 한 줄로 둔다
        법제처 = self.case / '작업' / '법제처'
        법제처.mkdir()
        (법제처 / '법제처_목록.json').write_text(json.dumps({'판례': {'rows': [
            {'종류': '판례', '사건번호': '2021누63022', '기관': '서울고등법원', '일자': '2023.01.20', '제목': '요양원 신분보장등조치결정취소', '검색어': '요양원', 'id': '9'}]}},
            ensure_ascii=False), encoding='utf-8')
        d = json.loads((법원 / '법원_목록.json').read_text(encoding='utf-8'))
        d['법고을'] = {'rows': [{'종류': '법고을', 'id': 'lx-3303168', '사건번호': '2021누63022', '기관': '서울고등법원', '일자': '2023-01-20',
                                '제목': '요양원 신분보장등조치결정취소', '검색어': '요양원'}]}
        (법원 / '법원_목록.json').write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        t = self.scan('요양원')
        self.assertEqual(t.count('2021누63022'), 1)
        self.assertIn('| 법제처-판례 | 2021누63022 |', t)

    def test_folder_named_like_a_markdown_file_is_skipped(self):
        """이름이 .md 로 끝나는 폴더가 있어도 멈추지 않는다. 2026. 11. 10. OES 근골격계: comwel.py --out '…/2018누40180_심급.md' 로 생긴
        폴더를 열다 Windows 가 '권한 없음'(PermissionError)을 내어 scan 이 멈췄다."""
        (self.case / '작업' / 'LBOX_목록.tsv').write_text(
            HEAD + '대법원-2020두1\t대법원\t20-01-01\t해고무효\tq\t요양원 사건\n', encoding='utf-8')
        폴더 = self.case / '작업' / '공단산재판례' / '2018누40180_심급.md'
        폴더.mkdir(parents=True)
        (폴더 / '2018누40180_서울고등법원.md').write_text('# 판결\n2020두1 요양원\n', encoding='utf-8')
        (self.case / '작업' / '검색기록.md').write_text('본문 읽음: 2020두1\n', encoding='utf-8')
        t = self.scan('요양원')
        self.assertIn('걸린 줄 1건 — 기록에 있음 1건, 없음 0건', t)       # 폴더 안의 md 는 그대로 읽는다


if __name__ == '__main__':
    unittest.main()
