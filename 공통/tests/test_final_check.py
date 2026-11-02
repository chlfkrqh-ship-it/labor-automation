"""넘기기 전 마지막 관문(공통/scripts/final_check.py)을 확인한다.

서면은 전 면 읽기 기록·쟁점 낱말 판단·상대 서면 맞대기·증거 인용 판정이 비거나 초안보다 낡으면 막는지, 판결문 '사람 판정'과
찾은 판례 다시 훑기의 빈 곳을 잡는지, 검토의견은 의뢰인 자료 읽기 기록과 낙관 표현을 잡고 우리 산출물을 자료로 세지 않는지 본다.
문체·호증 번호·판결문 PDF 대조 스크립트는 따로 시험하므로 여기서는 통과로 둔다. 문자인식은 돌리지 않는다.
"""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

import pymupdf

ROOT = Path(__file__).parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


fc = load('final_check', '공통/scripts/final_check.py')
er = load('evidence_read_for_fc', '4_서면작성/scripts/evidence_read.py')
REAL_RUN = fc.RUN
글 = '대표이사 상생안전 문자 안내입니다 '


def make_pdf(path: Path, pages):
    d = pymupdf.open()
    for t in pages:
        d.new_page().insert_text((40, 72), t, fontsize=7, fontname='korea')
    d.save(path)


def fake_run(args):
    name = Path(str(args[0])).name
    if name in ('style_check.py', 'citation_check.py', 'cite_pdf_check.py', 'evidence_zip.py', 'cite_check.py'):
        return 0, 'ok'
    args = [str(a) for a in args]
    if name in ('evidence_read.py', 'evidence_words.py') and '--no-ocr' not in args and 'check' not in args and '--확인' not in args:
        args.append('--no-ocr')
    return REAL_RUN(args)


def status(res, 이름):
    return next(s for n, s, _ in res.줄 if n == 이름)


def later(*paths):
    t = time.time() + 5
    for p in paths:
        os.utime(p, (t, t))


class BriefGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / '4_서면작성' / '사건' / 'GGM_정직'
        self.r = self.case / '라운드1'
        for d in ('우리증거', '상대증거', '출력', '작업'):
            (self.r / d).mkdir(parents=True)
        make_pdf(self.r / '우리증거' / '사 제6호증 문자.pdf', [글 + '1면', 글 + '2면', 글 + '작업 중 스피커 등 전자기기 사용 금지'])
        make_pdf(self.r / '상대증거' / '신청이유서(2).pdf', ['사 제6호증에는 스피커 사용을 제한한다는 내용은 찾아볼 수 없습니다'])
        self.draft = self.r / '출력' / '서면초안.md'
        self.draft.write_text('- 다 음 -\n\n1. 가\n\n안전 수칙을 알렸습니다(사 제6호증 1면).\n', encoding='utf-8')
        self.patch = mock.patch.object(fc, 'RUN', fake_run)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def complete(self):
        with redirect_stdout(io.StringIO()):
            er.main(['make', str(self.case), '--no-ocr'])
        rec = self.case / '증거관리' / '호증읽기' / '사6.md'
        t = rec.read_text(encoding='utf-8')
        t = t.replace('읽은 방식: \n', '읽은 방식: 글자층 전 면\n').replace('- 1면: ', '- 1면: 안전 문자').replace('- 2면: ', '- 2면: 안전 문자')
        t = t.replace('- 3면: ', '- 3면: 전자기기 사용 금지').replace('면)\n\n- \n', '면)\n\n- 3면 "작업 중 스피커 등 전자기기 사용 금지"\n')
        rec.write_text(t, encoding='utf-8')
        REAL_RUN([ROOT / '4_서면작성/scripts/evidence_words.py', self.case, '--낱말', '스피', '--no-ocr'])
        표 = self.r / '작업' / '쟁점낱말_대조.md'
        표.write_text(표.read_text(encoding='utf-8').replace('| 글자층(적음) |  |', '| 글자층(적음) | 본문 1항에 씀 |'), encoding='utf-8')
        맞대기 = self.r / '작업' / '상대주장_맞대기.md'
        맞대기.write_text('| 서면 위치 | 우리 문장 | 상대 서면 면과 원문 | 판정 |\n|---|---|---|---|\n| 1항 | 사 제6호증 3면에 있다 | 1면 찾아볼 수 없습니다 | 답이 됨 |\n',
                          encoding='utf-8')
        검토 = self.r / '작업' / '증거인용검토'
        검토.mkdir()
        (검토 / 'review.json').write_text(json.dumps([{'n': 1}, {'n': 2}]), encoding='utf-8')
        (검토 / 'notes.json').write_text(json.dumps({'1': ['일치', '…'], '2': ['일치', '…']}, ensure_ascii=False), encoding='utf-8')
        later(맞대기, 검토 / 'review.json')

    def test_missing_evidence_work_blocks_handoff(self):
        res = fc.서면(self.case)
        for 이름 in ('증거 파악(전 면 읽기)', '빠진 문구(쟁점 낱말)', '상대 서면 맞대기', '증거 인용'):
            self.assertEqual(status(res, 이름), '막힘', 이름)
        self.assertEqual(status(res, '판례 대조'), '해당 없음')

    def test_complete_work_passes_and_editing_the_draft_reopens_the_gates(self):
        self.complete()
        res = fc.서면(self.case)
        self.assertEqual(res.막힘, [], res.줄)
        later(self.draft)
        time.sleep(0)
        os.utime(self.draft, (time.time() + 20, time.time() + 20))
        res = fc.서면(self.case)
        self.assertEqual(status(res, '상대 서면 맞대기'), '막힘')
        self.assertEqual(status(res, '증거 인용'), '막힘')

    def test_unjudged_citation_and_client_table(self):
        self.complete()
        (self.r / '작업' / '증거인용검토' / 'notes.json').write_text(json.dumps({'1': ['일치', '…']}), encoding='utf-8')
        (self.r / '작업' / '의뢰인주장_대조.md').write_text(
            '| 문서·위치 | 주장·사실 원문 | 넣을 목차 | 반영 여부 |\n|---|---|---|---|\n| 소명서 1 | 가 | 1항 | 반영 |\n| 소명서 2 | 나 | 2항 |  |\n',
            encoding='utf-8')
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 인용'), '막힘')
        self.assertEqual(status(res, '의뢰인 주장'), '막힘')

    def test_stale_docx_blocks_after_merge_but_not_before(self):
        self.complete()
        frame = self.r / '출력' / '서면_프레임.docx'
        frame.write_bytes(b'PK')
        os.utime(frame, (time.time() - 100, time.time() - 100))
        self.assertEqual(status(fc.서면(self.case), 'DOCX'), '해당 없음')          # 프레임은 병합본이 아니다
        docx = self.r / '출력' / '(GGM) 답변서_초안.docx'
        docx.write_bytes(b'PK')
        os.utime(docx, (time.time() - 100, time.time() - 100))
        self.assertEqual(status(fc.서면(self.case), 'DOCX'), '해당 없음')          # 8-1단계: 병합 전이라 보지 않는다
        self.assertEqual(status(fc.서면(self.case, 대상=docx), 'DOCX'), '막힘')    # 9-2단계: 초안을 고친 뒤 병합하지 않았다
        self.assertEqual(status(fc.서면(self.case, 초안없음_허용=True), 'DOCX'), '막힘')
        os.utime(docx, (time.time() + 100, time.time() + 100))
        self.assertEqual(status(fc.서면(self.case, 대상=docx), 'DOCX'), '통과')

    def test_case_without_exhibits_skips_evidence_checks(self):
        (self.r / '우리증거' / '사 제6호증 문자.pdf').unlink()
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 파악(전 면 읽기)'), '해당 없음')
        self.assertEqual(status(res, '빠진 문구(쟁점 낱말)'), '해당 없음')


class CaseLawGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_people_judgement_rows_must_cover_every_body_citation(self):
        table = self.d / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 |\n|---|---|---|\n| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 가 |\n'
                         '| 2 | 서울고등법원 2021. 1. 1. 선고 2020누1 판결 | 나 |\n| 참고(이 사건) | 전남지방노동위원회 2026부해1 | |\n',
                         encoding='utf-8')
        report = self.d / '판결원문_PDF대조.md'
        report.write_text('# 대조\n\n## 사람 판정\n\n| 줄 | 판결 | PDF 의 자리 | 판단 부분인지 | 방향 | 비고 |\n|---|---|---|---|---|---|\n'
                          '| 1 | 2019두1 | 이유 2. | 판단 | 같음 | |\n| 2 | 2020누1 | 이유 3. |  | 같음 | |\n', encoding='utf-8')
        self.assertEqual(fc.사람판정_빈(table, report), ['2'])

    def test_rescan_of_harvested_lists_must_find_nothing_unrecorded(self):
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        for f in ('작업/LBOX_목록.tsv', '작업/법제처_목록.json', '작업/검색기록.md'):
            (폴더 / f).write_text('x', encoding='utf-8')
        (폴더 / '작업' / '수확목록_재확인.md').write_text('# 재확인\n\n낱말: 스피커, 기계적+징계\n', encoding='utf-8')
        seen = {}

        def run(args, 없음):
            seen['args'] = [str(a) for a in args]
            out = Path(seen['args'][seen['args'].index('--out') + 1])
            out.write_text('# 수확\n\n낱말: 스피커\n법제처 목록\n걸린 줄 3건 — 기록에 있음 1건, 없음 %d건(그 가운데 법제처 본문을 받은 것 0건), 번호가 없어 가리지 못한 것 0건\n\n'
                           '## 기록에 없는 줄(본문을 읽고 반영하거나 유사 사례 표에 미반영 이유를 적는다)\n\n'
                           '| 출처 | 사건번호·문서번호 | 일자 | 기관·법원 | 제목 | 걸린 낱말 | 기록 | 본문 |\n|---|---|---|---|---|---|---|---|\n'
                           '| LBOX | 2023구합1 | 2024 | 서울행정법원 | 정직 | 스피커 | 없음 | — |\n' % 없음, encoding='utf-8')
            return 0, ''

        res = fc.결과()
        with mock.patch.object(fc, 'RUN', lambda a: run(a, 2)):
            fc.검색_완결(res, 폴더)
        self.assertIn('기계적+징계', seen['args'])
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '막힘')
        self.assertIn('2023구합1', res.줄[-1][2])
        res = fc.결과()
        with mock.patch.object(fc, 'RUN', lambda a: run(a, 0)):
            fc.검색_완결(res, 폴더)
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '통과')
        self.assertEqual(status(res, '판례 검색 기록'), '통과')
        (폴더 / '작업' / 'LBOX_목록.tsv').unlink()
        res = fc.결과()
        with mock.patch.object(fc, 'RUN', lambda a: run(a, 0)):
            fc.검색_완결(res, 폴더)
        self.assertEqual(status(res, '판례 검색 기록'), '막힘')


class OpinionGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / '1_검토의견' / '사건' / 'HPS_근로시간면제'
        self.case.mkdir(parents=True)
        make_pdf(self.case / 'HPS 단체협약.pdf', [글 + '제1조', 글 + '제2조'])
        (self.case / '(HPS) 근로시간면제 관련 검토_초안.docx').write_bytes(b'PK')
        self.reply = self.case / 'HPS_근로시간면제-회신초안.md'
        self.reply.write_text('1. 검토 요지\n\n다툴 실익이 충분합니다. 단체협약에 적혀 있습니다.\n', encoding='utf-8')
        os.utime(self.reply, (time.time() + 10, time.time() + 10))
        self.patch = mock.patch.object(fc, 'RUN', fake_run)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_client_material_and_banned_phrases(self):
        res = fc.검토의견(self.case)
        self.assertEqual(status(res, '자료 파악(전 면 읽기)'), '막힘')
        self.assertEqual(status(res, '문체(낙관 표현·적다)'), '막힘')
        detail = next(m for n, s, m in res.줄 if n == '문체(낙관 표현·적다)')
        self.assertIn('다툴 실익이 충분', detail)
        self.assertIn('적혀 있', detail)
        with redirect_stdout(io.StringIO()):
            er.main(['make', str(self.case), '--자료', str(self.case), '--no-ocr'])
        recs = sorted(p.name for p in (self.case / '작업' / '자료읽기').glob('*.md'))
        self.assertEqual(recs, ['HPS 단체협약.pdf.md'])          # 우리가 만든 검토의견서는 자료로 세지 않는다


if __name__ == '__main__':
    unittest.main()
