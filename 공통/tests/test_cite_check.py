# -*- coding: utf-8 -*-
"""cite_check.py: 인용 대조표를 원문 파일·산출물과 맞대는 기계 검사(공통/자체검토.md 4절)."""
import importlib.util
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location("cite_check", os.path.join(ROOT, "공통", "scripts", "cite_check.py"))
cite_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cite_check)

SRC = """## [판례] 대법원 2025-07-17 2021도11886 근로기준법위반

### 판결요지
사용자는 '근로자가 청구한 시기에 휴가를 주는 것이 사업 운영에 막대한 지장이 있는 경우'에 한하여
적법하게 시기변경권을 행사할 수 있다. 그 밖의 문장.
"""
HEAD = "| 번호 | 사건 표시 | 본문 문장 | 원문 문장 | 자리 | 주문·결론 | 다른 사유·전제 | 확정 | 원문 |\n|---|---|---|---|---|---|---|---|---|\n"
ROW = ("| 1 | 대법원 2025. 7. 17. 선고 2021도11886 판결 | 대법원은 막대한 지장이 있는 경우에 한하여 시기를 변경할 수 있다고 판시하였습니다 "
       "| 사용자는 ‘근로자가 청구한 시기에 휴가를 주는 것이 사업 운영에 막대한 지장이 있는 경우’에 한하여 … 시기변경권을 행사할 수 있다 "
       "| 판결요지 | 파기환송 | 없음 | 대법원 판결 | `원문.md` |\n")
TARGET = "연차는 청구한 시기에 주어야 하고, 대법원은 막대한 지장이 있는 경우에 한하여 시기를 변경할 수 있다고 판시하였습니다(대법원 2025. 7. 17. 선고 2021도11886 판결).\n\n## 보완 메모\n대법원 2099다1 은 본문이 아니다.\n"


class CiteCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.p = lambda name: os.path.join(self.dir.name, name)
        self.write("원문.md", SRC)
        self.write("대조표.md", HEAD + ROW)
        self.write("산출물.md", TARGET)

    def tearDown(self):
        self.dir.cleanup()

    def write(self, name, text):
        with open(self.p(name), "w", encoding="utf-8") as f:
            f.write(text)

    def run_check(self):
        return cite_check.check(self.p("대조표.md"), [self.p("산출물.md")])

    def test_match(self):
        res = self.run_check()
        self.assertEqual((res["줄"], res["불일치"], res["원문미확인"]), (1, 0, 0), res["내용"])

    def test_quote_not_in_source(self):
        self.write("대조표.md", HEAD + ROW.replace("막대한 지장이 있는 경우’에 한하여", "상당한 지장이 있는 경우’에 한하여"))
        res = self.run_check()
        self.assertEqual(res["불일치"], 1, res["내용"])

    def test_wrong_date_and_number_in_target(self):
        self.write("산출물.md", TARGET.replace("2025. 7. 17.", "2025. 7. 16.").replace("2021도11886", "2021도11868"))
        res = self.run_check()
        # 날짜 없음, 사건번호 없음, 대조표에 없는 사건번호(2021도11868)
        self.assertEqual(res["불일치"], 3, res["내용"])

    def test_body_sentence_changed(self):
        self.write("산출물.md", TARGET.replace("한하여 시기를 변경할 수 있다고", "한하여만 변경할 수 있다고"))
        self.assertEqual(self.run_check()["불일치"], 1)

    def test_cache_only_source_and_unseen(self):
        self.write("대조표.md", HEAD + ROW.replace("`원문.md`", "https://lbox.kr/case/대법원/2021도11886 보관함 일치(10. 12.)"))
        res = self.run_check()
        self.assertEqual((res["불일치"], res["원문미확인"]), (0, 0), res["내용"])
        self.write("대조표.md", HEAD + ROW.replace("`원문.md`", "https://lbox.kr/case/대법원/2021도11886"))
        res = self.run_check()
        self.assertEqual((res["불일치"], res["원문미확인"]), (0, 1), res["내용"])

    def test_pointer_rows_are_not_counted_as_unseen(self):
        """표지의 사건번호처럼 가리키기만 하는 줄은 '대조표에 없다'를 막을 뿐이고 원문 미확인으로 세지 않는다(공통/자체검토.md 3절)."""
        own = "| 참고(이 사건) | 광주지방법원 2025구합33333 | 표지의 사건 표시 | — | — | — | — | — | — |\n"
        self.write("산출물.md", "사 건 2025구합33333 부당해고구제재심판정취소\n\n" + TARGET)
        self.assertEqual(self.run_check()["불일치"], 1)      # 줄이 없으면 대조표에 없는 사건번호로 잡힌다
        for label in ("참고(이 사건)", "참고(대상 서면)"):
            self.write("대조표.md", HEAD + ROW + own.replace("참고(이 사건)", label))
            res = self.run_check()
            self.assertEqual((res["줄"], res["불일치"], res["원문미확인"], res["사건표시만"]), (2, 0, 0, 1), res["내용"])
        # 원문 문장을 적었는데 원문이 없으면 가리킴 줄이 아니다. 종전대로 원문 미확인으로 센다
        self.write("대조표.md", HEAD + ROW + own.replace("| — | — | — | — | — | — |", "| 해고는 정당하다고 판단하였다 | 이유 2. | 기각 | 없음 | 확정 | — |"))
        res = self.run_check()
        self.assertEqual((res["불일치"], res["원문미확인"], res["사건표시만"]), (0, 1, 0), res["내용"])
        # 다른 심급의 참고 줄처럼 '이 사건'·'대상 서면'이라고 적지 않은 줄도 원문이 없으면 종전대로 원문 미확인이다
        self.write("대조표.md", HEAD + ROW + own.replace("참고(이 사건)", "참고"))
        res = self.run_check()
        self.assertEqual((res["불일치"], res["원문미확인"], res["사건표시만"]), (0, 1, 0), res["내용"])
        # 원문 칸에 파일을 적은 가리킴 줄은 그 파일과 맞댄다. 원문 문장이 비었으면 불일치이다
        self.write("대조표.md", HEAD + ROW + own.replace("| — |\n", "| `원문.md` |\n"))
        self.assertGreaterEqual(self.run_check()["불일치"], 1)

    def test_statute_and_dates_are_not_case_numbers(self):
        self.assertEqual(cite_check.cases("근로기준법 제60조제5항, 제76조의3, 2026년10월31일, 11일분, 99두202, 2022가단23572"), {"99두202", "2022가단23572"})


if __name__ == "__main__":
    unittest.main()
