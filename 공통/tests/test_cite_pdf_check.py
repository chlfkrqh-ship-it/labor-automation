# -*- coding: utf-8 -*-
"""cite_pdf_check.py: '확정' 칸의 대법원 상급심을 판결문과 맞대는 검사(공통/자체검토.md 3절, 2026. 11. 2. 이케아 각주 16번)."""
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "공통", "scripts"))
spec = importlib.util.spec_from_file_location("cite_pdf_check", os.path.join(ROOT, "공통", "scripts", "cite_pdf_check.py"))
cite_pdf_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cite_pdf_check)

HEAD = "| 번호 | 사건 표시 | 본문 문장 | 원문 문장 | 자리 | 주문·결론 | 다른 사유·전제 | 확정 | 원문 |\n|---|---|---|---|---|---|---|---|---|\n"
ROW = "| 1 | 서울고등법원 2016. 9. 2. 선고 2015나2070783 판결 | 본문 | 사용 촉진 조치를 취한 이상 같은 조치가 취해졌을 것이다 | 판단 | 일부 인용 | 없음 | %s | 화면 확인 |\n"
BELOW = "서울고등법원 2016. 9. 2. 선고 2015나2070783 판결\n사용 촉진 조치를 취한 이상 같은 조치가 취해졌을 것이다\n"
SHIMRI = "대법원 2017. 1. 18. 선고 2016다253914 판결\n상고심절차에 관한 특례법 제4조 제1항 각 호에 정한 사유를 포함하지 아니하거나 이유가 없다고 인정되므로, 같은 법 제5조에 의하여 상고를 기각하기로 하여 주문과 같이 판결한다.\n"
REASONED = "대법원 2017. 1. 18. 선고 2016다253914 판결\n원심의 판단은 정당하고, 상고이유 주장과 같은 법리오해의 잘못이 없다. 그러므로 상고를 기각한다.\n"


class UpperCourtTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.pdf = {"서울고등법원 2015나2070783 판결.pdf": BELOW}
        cite_pdf_check.pdf_texts = lambda path: [self.pdf[os.path.basename(path)]]

    def tearDown(self):
        self.dir.cleanup()

    def run_check(self, cell, upper=None, target=None):
        if upper:
            self.pdf["대법원 2016다253914 판결.pdf"] = upper
        for n in self.pdf:
            open(os.path.join(self.dir.name, n), "wb").close()
        table = os.path.join(self.dir.name, "대조표.md")
        with open(table, "w", encoding="utf-8") as f:
            f.write(HEAD + ROW % cell)
        targets = None
        if target is not None:
            t = os.path.join(self.dir.name, "산출물.md")
            with open(t, "w", encoding="utf-8") as f:
                f.write(target)
            targets = [t]
        return cite_pdf_check.check(table, self.dir.name, targets)

    def test_label_only_without_pdf_is_a_problem(self):
        """판결란의 '상고기각' 표시만 적고 판결문을 받지 않은 경우(각주 16번)."""
        res = self.run_check("대법원 2016다253914 상고기각으로 확정")
        self.assertEqual(res["문제"], 1)
        self.assertIn("판결문 PDF 없음", res["내용"][0])

    def test_shimri_written_as_plain_dismissal(self):
        res = self.run_check("대법원 2016다253914 상고기각으로 확정", SHIMRI)
        self.assertEqual(res["문제"], 1)
        self.assertIn("판결문과 다름", res["내용"][0])

    def test_shimri_written_as_shimri(self):
        res = self.run_check("대법원 2016다253914 심리불속행 기각으로 확정", SHIMRI)
        self.assertEqual(res["문제"], 0)
        self.assertEqual(res["판결"], 2)      # 상급심 PDF 도 센다. '가리키지 않는 PDF'가 아니다
        self.assertFalse(any("가리키지 않는" in x for x in res["보고서"]))

    def test_reasoned_judgment_written_as_shimri(self):
        res = self.run_check("대법원 2016다253914 심리불속행 기각으로 확정", REASONED)
        self.assertEqual(res["문제"], 1)

    def test_reasoned_judgment_written_as_judgment(self):
        self.assertEqual(self.run_check("대법원 2016다253914 판결로 확정", REASONED)["문제"], 0)
        self.assertEqual(self.run_check("대법원 2017. 1. 18. 선고 2016다253914 판결로 확정", REASONED)["문제"], 0)

    def test_lbox_label_order(self):
        """LBOX 머리 글 그대로('심리불속행기각 대법원 …')도 심리불속행 표기로 읽는다."""
        self.assertEqual(self.run_check("심리불속행기각 대법원 2016다253914", SHIMRI)["문제"], 0)

    def test_no_document_marks(self):
        self.assertEqual(self.run_check("대법원 2016다253914 심리불속행 기각으로 확정(상·하위 판결란)")["문제"], 0)
        self.assertEqual(self.run_check("대법원 2016다253914 상고기각으로 확정(상·하위 판결란, 문서 없음)")["문제"], 0)

    def test_target_limits_to_numbers_in_the_output(self):
        """서면처럼 상급심을 본문에 적지 않은 글은 PDF 를 더 받지 않아도 된다."""
        self.assertEqual(self.run_check("대법원 2016다253914 상고기각으로 확정", target="서울고등법원 2015나2070783 판결")["문제"], 0)
        self.assertEqual(self.run_check("대법원 2016다253914 상고기각으로 확정", target="(대법원 2016다253914 판결로 확정)")["문제"], 1)

    def test_shimri_regex_variants(self):
        norm = cite_pdf_check.norm
        for s in ("같은 법 제5조에 의하여 상고를 기각하기로 하여", "같은 법 제5조 제1항에 의하여 상고를 모두 기각하기로", "특례법 제5조에 따라 상고를 기각"):
            self.assertTrue(cite_pdf_check.SHIMRI.search(norm(s)), s)
        self.assertFalse(cite_pdf_check.SHIMRI.search(norm("그러므로 상고를 기각한다")))


if __name__ == "__main__":
    unittest.main()
