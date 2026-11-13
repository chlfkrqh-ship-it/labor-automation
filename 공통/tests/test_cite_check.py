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


class SourcePathTest(unittest.TestCase):
    def test_source_written_from_any_level_of_the_case_is_found(self):
        """2026. 11. 3. 라운드·사건 폴더 기준으로 적은 경로를 찾지 못해 글자 대조가 '원문 미확인'으로 넘어갔다."""
        with tempfile.TemporaryDirectory() as d:
            work = os.path.join(d, "사건1", "라운드1", "작업")
            os.makedirs(os.path.join(work, "원문"))
            with open(os.path.join(work, "원문", "a.md"), "w", encoding="utf-8") as f:
                f.write("글")
            table = os.path.join(work, "인용대조표.md")
            for cell in ("`원문/a.md`", "`작업/원문/a.md`", "`라운드1/작업/원문/a.md`", "작업/원문/a.md", "보관함 일치 작업/원문/a.md"):
                self.assertEqual(cite_check.source_text(cell, table, ""), "글", cell)
            self.assertEqual(cite_check.source_files("`없는폴더/a.md`", table), [])
            self.assertIsNone(cite_check.source_text("화면 확인(2026. 11. 2.)", table, ""))


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

    def test_shimri_in_table_but_not_in_target(self):
        """확정 칸이 심리불속행인 상급심을 산출물이 '판결로 확정'으로 적으면 잡는다(2026. 11. 2. 이케아 각주 16번)."""
        row = ROW.replace("| 대법원 판결 |", "| 대법원 2022다1234 심리불속행 기각으로 확정 |")
        self.write("대조표.md", HEAD + row)
        self.write("산출물.md", "서울고등법원 판결(대법원 2022다1234 판결로 확정). " + TARGET)
        res = cite_check.check(self.p("대조표.md"), [self.p("산출물.md")])
        self.assertEqual(res["불일치"], 1)
        self.assertIn("심리불속행이 없다", res["내용"][0])
        self.write("산출물.md", "서울고등법원 판결(대법원 2022다1234 심리불속행 기각으로 확정). " + TARGET)
        self.assertEqual(cite_check.check(self.p("대조표.md"), [self.p("산출물.md")])["불일치"], 0)
        self.write("산출물.md", TARGET)      # 상급심을 적지 않은 글(서면 등)은 건드리지 않는다
        self.assertEqual(cite_check.check(self.p("대조표.md"), [self.p("산출물.md")])["불일치"], 0)

    def test_body_number_needs_a_body_row_not_only_a_bottom_or_dropped_row(self):
        """2026. 11. 3. 점검: 본문에 남은 판결이 대조표에 하단 목록 줄('② 1.')이나 뺀 줄로만 있으면 그 본문 문장이 대조 없이 지나갔다.
        하단 세 목록은 서면 초안('---' 아래)에만 있다. 검토의견 대조표의 ①② 줄은 본문 인용으로 본다."""
        rows = ("| ② 1. | 대법원 2020. 1. 1. 선고 2019두1 판결 | 반대 판결로 사안이 다르다 | 가나다라마바사아자 | 판결요지 | 기각 | 없음 | 확정 | 보관함 일치 |\n"
                "| 뺌 | 대법원 2021. 1. 1. 선고 2020두2 판결 | 뺌 | 차카타파하가나다라 | 판결요지 | 기각 | 없음 | 확정 | 보관함 일치 |\n")
        bottom = "\n\n---\n\n② 반대 판결로 사안이 다르다(대법원 2020. 1. 1. 선고 2019두1 판결).\n"
        for folder in ("사건/라운드1/작업", "자문/작업"):
            os.makedirs(self.p(folder), exist_ok=True)
            table = os.path.join(self.p(folder), "인용대조표.md")
            with open(table, "w", encoding="utf-8") as f:
                f.write(HEAD + ROW + rows)
            brief = folder.startswith("사건")
            # 하단에만 둔 반대 판결은 통과한다
            self.write("산출물.md", TARGET.split("\n\n## 보완 메모")[0] + bottom)
            res = cite_check.check(table, [self.p("산출물.md")])
            self.assertEqual(res["불일치"], 0, (folder, res["내용"]))
            # 본문에 남은 하단 줄 판결과 뺀 판결
            self.write("산출물.md", "대법원 2020. 1. 1. 선고 2019두1 판결은 본문에서도 들었다. 대법원 2021. 1. 1. 선고 2020두2 판결도 남았다. "
                       + TARGET.split("\n\n## 보완 메모")[0] + bottom)
            res = cite_check.check(table, [self.p("산출물.md")])
            글 = "\n".join(res["내용"])
            self.assertIn("뺀 인용의 2020두2 가 산출물에 남아 있다", 글, folder)
            if brief:
                self.assertIn("산출물 본문의 2019두1 가 대조표에 하단 목록 줄로만 있다", 글)
                self.assertEqual(res["불일치"], 2, 글)
            else:      # 검토의견의 ①② 줄은 본문 인용 줄이어서 3)으로 본문 문장을 맞댄다
                self.assertNotIn("하단 목록 줄로만", 글)
                self.assertEqual(res["불일치"], 1, 글)
        # DOCX 에는 하단 목록이 없으므로 DOCX 의 번호는 모두 본문이다
        self.assertEqual(cite_check.body_and_bottom("a.docx", "본문\n---\n하단"), ("본문\n---\n하단", ""))
        self.assertEqual(cite_check.body_and_bottom("a.md", "---\n머리\n본문\n---\n하단"), ("---\n머리\n본문", "하단"))

    def test_bottom_list_may_name_a_dropped_citation(self):
        """2026. 11. 4. `/하자보완`: 하단 ① 메모가 '이번 판에서 … 뺐습니다'라고 적으며 뺀 판결 번호를 들자 '본문 인용 줄을 두라'고 막았다.
        뺀 줄도 원문과 맞대므로 하단 목록의 번호는 받친다. 본문에 남은 뺀 번호와 대조표에 없는 하단 번호는 그대로 막는다."""
        rows = "| 뺌 | 대법원 2021. 1. 1. 선고 2020두2 판결 | 뺌 | 차카타파하가나다라 | 판결요지 | 기각 | 없음 | 확정 | 보관함 일치 |\n"
        os.makedirs(self.p("사건/라운드1/작업"), exist_ok=True)
        table = os.path.join(self.p("사건/라운드1/작업"), "인용대조표.md")
        with open(table, "w", encoding="utf-8") as f:
            f.write(HEAD + ROW + rows)
        body = TARGET.split("\n\n## 보완 메모")[0]
        bottom = "\n\n---\n\n① 1. 대법원 2020두2 판결은 이번 판에서 뺐습니다.\n"
        self.write("산출물.md", body + bottom)
        res = cite_check.check(table, [self.p("산출물.md")])
        self.assertEqual(res["불일치"], 0, res["내용"])
        self.write("산출물.md", "대법원 2021. 1. 1. 선고 2020두2 판결도 남았다. " + body + bottom)
        res = cite_check.check(table, [self.p("산출물.md")])
        self.assertIn("뺀 인용의 2020두2 가 산출물에 남아 있다", "\n".join(res["내용"]))
        self.assertEqual(res["불일치"], 1, res["내용"])
        self.write("산출물.md", body + bottom + "② 1. 대법원 2003다8862 판결은 다시 들지 않았습니다.\n")
        res = cite_check.check(table, [self.p("산출물.md")])
        self.assertIn("산출물의 2003다8862 가 대조표에 없다", "\n".join(res["내용"]))

    def test_bottom_number_without_a_row_names_what_to_do(self):
        """2026. 11. 14. `/하자보완`: 11. 13. GGM 항소심 두 서면이 유관 사건을 하단 ①에 적으며 넣은 관련 사건·사무소 다른 사건 번호에 줄이 없었다.
        하단 목록에만 나오는 번호는 할 일('참고(하단 ②)'·'참고(이 사건)')을 함께 알리고, 넘길 DOCX 로 돌린 관문은 짝 초안의 하단 목록을
        bottom_unlisted 로 본다(DOCX 에는 하단 목록이 없다)."""
        os.makedirs(self.p("사건/라운드1/작업"), exist_ok=True)
        table = os.path.join(self.p("사건/라운드1/작업"), "인용대조표.md")
        own = "| 참고(이 사건) | 서울고등법원 2026누1001 | | | | | | | |\n"
        with open(table, "w", encoding="utf-8") as f:
            f.write(HEAD + ROW + own)
        body = TARGET.split("\n\n## 보완 메모")[0]
        self.write("산출물.md", body + "\n\n---\n\n① 1. 같은 의뢰인의 유관 사건은 2026누1002, 2026누1001(이 사건)입니다.\n")
        res = cite_check.check(table, [self.p("산출물.md")])
        글 = "\n".join(res["내용"])
        self.assertEqual(res["불일치"], 1, 글)
        self.assertIn("산출물의 2026누1002 가 대조표에 없다", 글)
        self.assertIn("'참고(이 사건)' 줄에 사건 표시만", 글)
        self.assertEqual(cite_check.bottom_unlisted(table, self.p("산출물.md")), ["2026누1002"])
        self.write("산출물.md", "2026누1002 를 본문에 적었다. " + body)      # 본문의 번호에는 하단 안내를 붙이지 않는다
        글 = "\n".join(cite_check.check(table, [self.p("산출물.md")])["내용"])
        self.assertIn("산출물의 2026누1002 가 대조표에 없다", 글)
        self.assertNotIn("하단 목록의 번호이다", 글)
        self.assertEqual(cite_check.bottom_unlisted(table, self.p("산출물.md")), [])

    def test_each_place_of_a_case_mark_matches_the_table(self):
        """2026. 11. 9. `/하자보완`: 3)은 산출물 어딘가에 그 날짜가 있는지만 보아, 같은 판결을 두 번 적은 산출물의 둘째 자리 날짜가 틀려도
        지나갔고 법원 이름은 어디서도 맞대지 않았다(실제 산출물 사본으로 날짜 302곳 가운데 122곳, 법원 301곳 가운데 246곳이 지나감)."""
        again = "같은 취지에서 대법원 2025. 7. 17. 선고 2021도11886 판결은 다시 들었습니다. 위 2021도11886 판결도 같다. "
        body = TARGET.split("\n\n## 보완 메모")[0]
        self.write("산출물.md", again + body)
        self.assertEqual(self.run_check()["불일치"], 0, self.run_check()["내용"])
        # 둘째 자리의 날짜가 틀림 — 다른 자리에 맞는 날짜가 있어도 잡는다
        self.write("산출물.md", again.replace("2025. 7. 17.", "2025. 7. 7.") + body)
        res = self.run_check()
        self.assertEqual(res["불일치"], 1, res["내용"])
        self.assertIn("'대법원 2025. 7. 7. 선고 2021도11886' 가 대조표의 사건 표시(대법원 2025. 7. 17.)와 다르다", "\n".join(res["내용"]))
        # 둘째 자리의 법원이 틀림
        self.write("산출물.md", again.replace("대법원", "서울고등법원", 1) + body)
        res = self.run_check()
        self.assertEqual(res["불일치"], 1, res["내용"])
        self.assertIn("서울고등법원 2025. 7. 17. 선고 2021도11886", "\n".join(res["내용"]))
        # 같은 꼴로 두 번 틀리면 곳 수를 센다
        self.write("산출물.md", again.replace("2025. 7. 17.", "2025. 7. 7.") * 2 + body)
        res = self.run_check()
        self.assertEqual(res["불일치"], 2, res["내용"])
        self.assertIn("(2곳)", "\n".join(res["내용"]))
        # 날짜 없이 적은 번호, '선고된' 같은 다른 글은 표시로 보지 않는다
        self.write("산출물.md", "2025. 7. 18. 선고된 2021도11886 판결의 취지는 위와 같다. " + body)
        self.assertEqual(self.run_check()["불일치"], 0)

    def test_court_short_forms_and_branch_courts(self):
        """줄임말('서울고법')은 같게 보고, 본원과 지원은 다르게 본다. 법원 이름 없이 날짜만 적은 자리는 날짜만 맞댄다."""
        src = "## [판례] 수원지법 안산지원 2025-01-09 2024가합9386 해고무효확인\n\n### 이유\n해고는 정당한 이유가 없어 무효이다.\n"
        self.write("원문2.md", src)
        row = ("| 2 | 수원지방법원 안산지원 2025. 1. 9. 선고 2024가합9386 판결 | 해고는 정당한 이유가 없어 무효라고 판단하였습니다 "
               "| 해고는 정당한 이유가 없어 무효이다 | 이유 | 원고 승 | 없음 | 확정 | `원문2.md` |\n")
        self.write("대조표.md", HEAD + ROW + row)
        body = TARGET.split("\n\n## 보완 메모")[0]
        tail = " 해고는 정당한 이유가 없어 무효라고 판단하였습니다(%s 2025. 1. 9. 선고 2024가합9386 판결)."
        for court, bad in (("수원지방법원 안산지원", 0), ("수원지법 안산지원", 0), ("안산지원", 0), ("수원지방법원", 1), ("서울중앙지방법원", 1)):
            self.write("산출물.md", body + tail % court)
            res = self.run_check()
            self.assertEqual(res["불일치"], bad, (court, res["내용"]))
        self.write("산출물.md", body + " 해고는 정당한 이유가 없어 무효라고 판단하였습니다(2025. 1. 9. 선고 2024가합9386 판결).")
        self.assertEqual(self.run_check()["불일치"], 0)
        self.write("산출물.md", body + " 해고는 정당한 이유가 없어 무효라고 판단하였습니다(2025. 1. 8. 선고 2024가합9386 판결).")
        self.assertEqual(self.run_check()["불일치"], 2)      # 3) 날짜 없음과 6) 그 자리의 날짜

    def test_table_court_must_be_in_the_source(self):
        """2026. 11. 9. `/하자보완`: 판결문 PDF 를 받지 않게 된 뒤(11. 6.) 사건 표시의 법원은 원문과 맞대는 곳이 없었다.
        법제처 본문 머리는 '서울고법 2022-05-12' 꼴이어서 줄임말로 맞대어 본다."""
        self.write("대조표.md", HEAD + ROW.replace("대법원 2025. 7. 17.", "서울고등법원 2025. 7. 17."))
        self.write("산출물.md", TARGET.replace("대법원 2025. 7. 17.", "서울고등법원 2025. 7. 17."))
        res = self.run_check()
        self.assertEqual(res["불일치"], 1, res["내용"])
        self.assertIn("원문 파일에 법원 서울고등법원 없음", "\n".join(res["내용"]))
        self.write("원문.md", SRC.replace("대법원 2025-07-17", "서울고법 2025-07-17"))
        res = self.run_check()
        self.assertEqual(res["불일치"], 0, res["내용"])

    def test_statute_and_dates_are_not_case_numbers(self):
        self.assertEqual(cite_check.cases("근로기준법 제60조제5항, 제76조의3, 2026년10월31일, 11일분, 99두202, 2022가단23572"), {"99두202", "2022가단23572"})


if __name__ == "__main__":
    unittest.main()
