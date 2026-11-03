"""넘기기 전 마지막 관문(공통/scripts/final_check.py)을 확인한다.

서면은 전 면 읽기 기록·쟁점 낱말 판단·상대 서면 맞대기·증거 인용 판정이 비거나 초안보다 낡으면 막는지, 판결문 '사람 판정'과
찾은 판례 다시 훑기의 빈 곳을 잡는지, 검토의견은 의뢰인 자료 읽기 기록과 낙관 표현을 잡고 우리 산출물을 자료로 세지 않는지 본다.
문체·호증 번호·판결문 PDF 대조 스크립트는 따로 시험하므로 여기서는 통과로 둔다. 문자인식은 돌리지 않는다.
"""
import importlib.util
import io
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
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
글 = ('공지 문자 안내입니다 오늘도 안전한 하루 되십시오\n'       # 글자층이 넉넉한 면(80자 넘게)
     '현장의 모든 구성원은 안전 수칙을 지켜 주시기 바랍니다\n'
     '작업 전후 점검표를 확인하고 이상이 있으면 즉시 보고합니다\n'
     '보호구를 갖추고 정해진 통로로만 다닙니다\n')


def make_pdf(path: Path, pages):
    d = pymupdf.open()
    for t in pages:
        d.new_page().insert_text((40, 72), t, fontsize=7, fontname='korea')
    d.save(path)


def make_docx(path: Path, 문단들, 각주들=()):
    """글자만 갖춘 병합본. 앞은 프레임(표지·목차·'다 음'), 뒤는 제출일·대리인 블록을 흉내 내어 넘긴다."""
    본 = ''.join(f'<w:p><w:r><w:t>{x}</w:t></w:r></w:p>' for x in 문단들)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('word/document.xml', f'<w:document><w:body>{본}</w:body></w:document>')
        if 각주들:
            z.writestr('word/footnotes.xml', ''.join(f'<w:footnote><w:p><w:r><w:t>{x}</w:t></w:r></w:p></w:footnote>' for x in 각주들))


def fake_run(args):
    name = Path(str(args[0])).name
    if name in ('style_check.py', 'citation_check.py', 'cite_pdf_check.py', 'evidence_zip.py', 'cite_check.py', 'qna_check.py'):
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
        make_pdf(self.r / '우리증거' / '사 제6호증 문자.pdf', [글 + '1면', 글 + '2면', 글 + '작업 중 시험 기기 사용 금지'])
        make_pdf(self.r / '상대증거' / '신청이유서(2).pdf', ['사 제6호증에는 시험 기기 사용을 제한한다는 내용은 찾아볼 수 없습니다'])
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
        확인 = dict(re.findall(r'\[(\d+)면 끝 · 확인표 ([A-Z0-9]{4})\]',
                              (self.case / '증거관리' / '호증글자' / '사6.txt').read_text(encoding='utf-8')))   # 면마다 끝까지 열어 본 증표
        t = t.replace('읽은 방식: \n', '읽은 방식: 글자층 전 면\n').replace('- 1면: ', f'- 1면: 안전 문자 확인표 {확인["1"]}')
        t = t.replace('- 2면: ', f'- 2면: 안전 문자 확인표 {확인["2"]}').replace('- 3면: ', f'- 3면: 시험 기기 사용 금지 확인표 {확인["3"]}')
        t = t.replace('면)\n\n- \n', '면)\n\n- 3면 "작업 중 시험 기기 사용 금지"\n')
        rec.write_text(t, encoding='utf-8')
        er.실측_적기(rec, f"실측: 시험 · 글 {er.해시(self.case / '증거관리' / '호증글자' / '사6.txt')}")      # 재는 일은 test_evidence_read 가 본다
        self.상대서면_읽음()
        REAL_RUN([ROOT / '4_서면작성/scripts/evidence_words.py', self.case, '--낱말', '시험', '--no-ocr'])
        표 = self.r / '작업' / '쟁점낱말_대조.md'
        표.write_text(re.sub(r'(?m)^(\| 사 제6호증 .*\|) +\|$', r'\1 본문 1항에 씀 |', 표.read_text(encoding='utf-8')), encoding='utf-8')
        맞대기 = self.r / '작업' / '상대주장_맞대기.md'
        맞대기.write_text('| 서면 위치 | 우리 문장 | 상대 서면 면과 원문 | 판정 |\n|---|---|---|---|\n| 1항 | 사 제6호증 3면에 있다 | 1면 찾아볼 수 없습니다 | 답이 됨 |\n',
                          encoding='utf-8')
        검토 = self.r / '작업' / '증거인용검토'
        검토.mkdir()
        (검토 / 'review.json').write_text(json.dumps([{'n': 1}, {'n': 2}]), encoding='utf-8')
        (검토 / 'notes.json').write_text(json.dumps({'1': ['일치', '…'], '2': ['일치', '…']}, ensure_ascii=False), encoding='utf-8')
        later(맞대기, 검토 / 'review.json')

    def 상대서면_읽음(self):
        """호증 번호가 없는 상대방 서면도 전 면 읽기 기록이 있어야 한다(2026. 11. 3. 완결성 원칙의 전면 적용)."""
        k, p = '라운드1 상대 신청이유서(2).pdf', self.r / '상대증거' / '신청이유서(2).pdf'
        자 = er.자리(self.case, False)
        rec = 자.기록_파일(k)
        표 = er.기대_확인표(자, k, p)
        t = rec.read_text(encoding='utf-8').replace('읽은 방식: \n', '읽은 방식: 글자층 전 면, 그림 전 면\n')
        t = t.replace('- 1면: ', f'- 1면: 사 제6호증에 문구가 없다는 주장 확인표 {" ".join(표[1])}').replace('면)\n\n- \n', '면)\n\n- 1면 "찾아볼 수 없습니다"\n', 1)
        rec.write_text(t, encoding='utf-8')
        er.실측_적기(rec, f"실측: 시험 · 글 {er.해시(자.글_파일(k))}")

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

    def test_memo_only_edit_does_not_make_the_docx_stale(self):
        """초안의 하단 메모만 고치면 병합본은 그대로이다(2026. 11. 2. 첫 밤 점검). 본문을 고치면 막는다."""
        본문 = '- 다 음 -\n\n가. 정직 사유에 관하여 살펴봅니다\n\n안전 수칙을 모든 근로자에게 알렸습니다(사 제6호증 1면).[[각주: 판결 원문]]\n\n---\n\n① 메모\n'
        self.draft.write_text(본문, encoding='utf-8')
        merged = self.r / '출력' / '(GGM) 답변서_초안.docx'
        make_docx(merged, ['정직 사유에 관하여 살펴봅니다', '안전 수칙을 모든 근로자에게 알렸습니다(사 제6호증 1면).'], ['판결 원문'])
        os.utime(merged, (time.time() - 100, time.time() - 100))
        self.assertEqual(status(fc.서면(self.case, 초안없음_허용=True), 'DOCX'), '통과')
        self.draft.write_text(본문.replace('모든 근로자에게', '전 직원에게'), encoding='utf-8')
        self.assertEqual(status(fc.서면(self.case, 초안없음_허용=True), 'DOCX'), '막힘')

    def test_body_compare_catches_every_kind_of_edit(self):
        """메모만 고친 초안은 같고, 각주·표·짧은 제목을 고치거나 문단을 지우면 다르다. 2026. 11. 3. 스무 글자 넘는 문단만 보다가 모두 통과시켰다."""
        기준 = ('- 다 음 -\n\n## 가. 징계사유\n\n**근로자는** 구제를 신청하였습니다.[[각주: 대법원 2020. 1. 1. 선고 2019다1 판결]]\n\n'
              '병합한 뒤에 지울 문단이며 병합본에는 그대로 남습니다.\n\n[사 제1호증 문자]\n![](사1.png)\n\n'
              '| 항목 | 금액 |\n|---|---|\n| 임금 | 100원 |\n\n입 증 방 법\n\n    사 제1호증  문자\n\n---\n\n① 메모\n')
        merged = self.r / '출력' / '(GGM) 답변서_초안.docx'
        make_docx(merged, ['답변서', '목 차', '가. 징계사유 2', '다 음', '징계사유', '근로자는 구제를 신청하였습니다.',
                           '병합한 뒤에 지울 문단이며 병합본에는 그대로 남습니다.', '[사 제1호증 문자]', '항목', '금액', '임금', '100원', '입 증 방 법', '사 제1호증  문자',
                           '2026. 11.   .', '대리인'], ['대법원 2020. 1. 1. 선고 2019다1 판결'])

        def 같나(글자):
            self.draft.write_text(글자, encoding='utf-8')
            return fc.본문이_같은가(self.draft, merged)

        self.assertTrue(같나(기준))
        self.assertTrue(같나(기준.replace('① 메모', '① 메모를 고쳤다')))
        self.assertFalse(같나(기준.replace('2019다1', '2020다2')))                               # 각주의 판결 번호
        self.assertFalse(같나(기준.replace('100원', '900원')))                                   # 표의 금액
        self.assertFalse(같나(기준.replace('징계사유', '징계양정')))                              # 짧은 제목
        self.assertFalse(같나(기준.replace('병합한 뒤에 지울 문단이며 병합본에는 그대로 남습니다.\n\n', '')))   # 지운 문단
        self.assertFalse(같나(기준.replace('    사 제1호증  문자\n\n', '')))                     # 끝에서 지운 줄
        self.assertFalse(같나(기준.replace('[[각주: 대법원 2020. 1. 1. 선고 2019다1 판결]]', ''))) # 지운 각주
        첫문단 = 기준.replace('## 가. 징계사유\n\n', '')
        self.assertFalse(같나(첫문단))                                                          # 지운 첫 문단
        self.assertFalse(같나(기준.replace('**근로자는** 구제를', '근로자는 다시 구제를')))        # 고친 문단

    def test_merged_body_without_new_exhibits_has_no_exhibit_title(self):
        """새로 내는 호증이 없으면 병합이 입증방법 제목을 넣지 않는다."""
        self.draft.write_text('- 다 음 -\n\n결론 문장입니다.\n\n입 증 방 법\n\n---\n\n① 메모\n', encoding='utf-8')
        merged = self.r / '출력' / '(GGM) 답변서_초안.docx'
        make_docx(merged, ['다 음', '결론 문장입니다.', '', '2026. 11.   .'])
        self.assertTrue(fc.본문이_같은가(self.draft, merged))

    def test_evidence_review_stays_valid_while_citations_are_the_same(self):
        """2026. 11. 3. 하단 메모만 고쳐도 '초안을 고친 뒤 대조를 다시 하지 않았다'로 막았다. 인용이 달라지면 그대로 막는다."""
        self.complete()
        ecr = fc.증거검토()
        본문 = '- 다 음 -\n\n1. 가\n\n안전 수칙을 알렸습니다(사 제6호증 1면).\n\n---\n\n① 메모\n'
        self.draft.write_text(본문, encoding='utf-8')
        검토 = self.r / '작업' / '증거인용검토'
        items = [{'n': n, 'key': c['key'], 'pages': c['pages'], 'sentence': c['sentence']} for n, c in enumerate(ecr.parse_citations(본문), 1)]
        (검토 / 'review.json').write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')
        (검토 / 'notes.json').write_text(json.dumps({'1': ['일치', '…']}, ensure_ascii=False), encoding='utf-8')
        옛 = time.time() - 100
        os.utime(검토 / 'review.json', (옛, 옛))

        def 증거인용(글자):
            self.draft.write_text(글자, encoding='utf-8')
            res = fc.서면(self.case)
            return status(res, '증거 인용'), next(m for n, _, m in res.줄 if n == '증거 인용')

        self.assertEqual(증거인용(본문.replace('① 메모', '① 메모를 고쳤다'))[0], '통과')
        상태, 말 = 증거인용(본문.replace('(사 제6호증 1면).', '(사 제6호증 1면).\n\n시험 기기를 금지하였습니다(사 제6호증 3면).'))
        self.assertEqual(상태, '막힘')
        self.assertIn('새로 생긴 인용 1건', 말)
        상태, 말 = 증거인용(본문.replace('(사 제6호증 1면)', '(사 제6호증 2면)'))
        self.assertEqual(상태, '막힘')                                         # 면을 바꾼 인용은 다시 맞댄다
        상태, 말 = 증거인용(본문.replace('안전 수칙을', '보호구 수칙을'))
        self.assertEqual(상태, '막힘')                                         # 문장을 고친 인용도 다시 맞댄다

    def test_split_drafts_have_their_own_evidence_review(self):
        """서면을 나눈 라운드는 증거 인용 검토도 서면마다 있어야 한다. 2026. 11. 3. 어느 서면의 것도 아닌 review.json 하나를 그 서면의 것으로 보았다."""
        self.draft.unlink()
        a = self.r / '출력' / '서면초안_림프종.md'
        a.write_text('- 다 음 -\n\n1. 가\n\n사실입니다(사 제6호증 1면).\n', encoding='utf-8')
        (self.r / '작업' / '증거인용검토').mkdir()
        (self.r / '작업' / '증거인용검토' / 'review.json').write_text('[]', encoding='utf-8')
        res = fc.서면(self.case, 초안없음_허용=True, 초안=a)
        self.assertEqual(status(res, '증거 인용'), '막힘')
        self.assertIn('증거인용검토_림프종', next(m for n, _, m in res.줄 if n == '증거 인용'))
        검토 = self.r / '작업' / '증거인용검토_림프종'
        검토.mkdir()
        (검토 / 'review.json').write_text('[]', encoding='utf-8')
        later(검토 / 'review.json')
        self.assertEqual(status(fc.서면(self.case, 초안없음_허용=True, 초안=a), '증거 인용'), '통과')

    def test_case_without_exhibits_skips_evidence_checks(self):
        (self.r / '우리증거' / '사 제6호증 문자.pdf').unlink()
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 파악(전 면 읽기)'), '막힘')        # 호증이 없어도 상대방 서면은 읽는다
        (self.r / '상대증거' / '신청이유서(2).pdf').unlink()
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 파악(전 면 읽기)'), '해당 없음')
        self.assertEqual(status(res, '빠진 문구(쟁점 낱말)'), '해당 없음')

    def test_side_documents_are_not_the_merged_brief(self):
        """같은 이름 꼴의 예상 질의답변을 병합본으로 읽어 낡은 서면을 통과시키지 않는다(2026. 11. 2. 첫 밤 점검). 그 문서는 따로 본다."""
        self.complete()
        merged = self.r / '출력' / '(GGM) 답변서_초안.docx'
        merged.write_bytes(b'PK')
        os.utime(merged, (time.time() - 100, time.time() - 100))
        side = self.r / '출력' / '(GGM) 심문회의 예상 질의답변_초안.docx'
        side.write_bytes(b'PK')
        later(side)
        res = fc.서면(self.case, 초안없음_허용=True)
        self.assertEqual(status(res, 'DOCX'), '막힘')
        self.assertIn('답변서_초안', next(m for n, _, m in res.줄 if n == 'DOCX'))
        self.assertEqual(status(res, '예상 질의답변 모양'), '통과')
        self.assertEqual(status(res, '예상 질의답변 문체'), '통과')

    def test_split_drafts_are_each_checked_with_their_own_table(self):
        """상병별로 나눈 서면(서면초안_{이름}.md)을 '초안 없음'으로 넘기지 않는다(2026. 11. 2. 첫 밤 점검)."""
        self.draft.unlink()
        a = self.r / '출력' / '서면초안_림프종.md'
        b = self.r / '출력' / '서면초안_적응장애우울증.md'
        for p in (a, b):
            p.write_text('- 다 음 -\n\n1. 가\n\n사실입니다(증 제1호증).\n', encoding='utf-8')
        (self.r / '출력' / '서면초안_본문.md').write_text('x', encoding='utf-8')
        표 = self.case / '작업' / '인용대조표_심사청구_림프종.md'
        표.parent.mkdir()
        표.write_text('x', encoding='utf-8')
        결과들 = fc.돌리기(self.case, 밤=True)
        self.assertEqual([t for t, _ in 결과들], [a.name, b.name])
        self.assertEqual(status(결과들[0][1], '문체'), '통과')
        self.assertEqual(fc.대조표_자리(self.case, self.r, a), (표, 표.parent / '판결원문_PDF대조_림프종.md'))
        self.assertEqual(fc.대조표_자리(self.case, self.r, b)[0].name, '인용대조표_적응장애우울증.md')
        docx = self.r / '출력' / '(이승민) 심사청구 취지 및 이유(적응장애·우울증)_초안.docx'
        docx.write_bytes(b'PK')
        later(docx)
        self.assertEqual(status(fc.서면(self.case, 초안없음_허용=True, 초안=a), 'DOCX'), '해당 없음')     # 다른 서면의 병합본이다
        self.assertEqual(status(fc.서면(self.case, 초안없음_허용=True, 초안=b), 'DOCX'), '통과')


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
        self.assertEqual(fc.사람판정_빈(table, report), ['1(사안 비교)', '2(판단 부분인지, 사안 비교)'])
        report.write_text('# 대조\n\n## 사람 판정\n\n| 줄 | 판결 | PDF 의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
                          '| 1 | 2019두1 | 본문 · 2. 원고의 주장 — 주의: 앞 글에 주장 | 판단 | 같음 | 양정 다툼 같음 | |\n'
                          '| 2 | 2020누1 | 이유 3. | 판단 | 같음 | 공무원 사건이어서 다름 | |\n', encoding='utf-8')
        self.assertEqual(fc.사람판정_빈(table, report), ['1(비고(주의 줄))'])   # 주장 대목 곁의 문장은 까닭을 적는다
        report.write_text(report.read_text(encoding='utf-8').replace('| 양정 다툼 같음 | |', '| 양정 다툼 같음 | 배척한 주장 뒤의 법원 판단 |'),
                          encoding='utf-8')
        self.assertEqual(fc.사람판정_빈(table, report), [])

    def test_citation_table_cells_existence_and_finality(self):
        import datetime as dt
        (self.d / '원문').mkdir()
        (self.d / '원문' / '중노위.md').write_text('중앙노동위원회 2024부해100 …', encoding='utf-8')
        table = self.d / '인용대조표.md'
        table.write_text(
            '| 번호 | 사건 표시 | 본문 문장 | 원문 문장 | 자리 | 주문·결론 | 다른 사유·전제 | 확정 | 원문 |\n|---|---|---|---|---|---|---|---|---|\n'
            '| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 가 | 가 | 이유 2. | 상고기각 | 없음 | 확정 | 화면 확인(2026. 11. 2.) |\n'
            '| 2 | 서울고등법원 2021. 1. 1. 선고 2020누1 판결 | 나 | 나 | 이유 3. | 항소기각 |  | 확정 여부 미확인(2026. 10. 1. 봄) | `원문/없는파일.md` |\n'
            '| 3 | 중앙노동위원회 2024. 3. 1. 2024부해100 | 다 | 다 | 판정요지 | 기각 | 없음 | 확정 | 화면 확인(2026. 11. 2.) |\n'
            '| 4 | 중앙노동위원회 2024. 3. 1. 2024부해100 | 라 | 라 | 판정요지 | 기각 | 없음 | 확정 | `원문/중노위.md` |\n'
            '| 참고(하단 ②) | 대법원 2021. 1. 1. 선고 2020다1 판결 | 마 | 마 |  |  |  |  |  |\n', encoding='utf-8')
        막, 미확정 = fc.대조표_칸(table, 오늘=dt.date(2026, 11, 2))
        글 = '\n'.join(막)
        self.assertIn('2: 다른 사유·전제 칸이 비었다', 글)
        self.assertIn('2: 확정되지 않았거나 확인하지 못한 판결은 넘기기 전에 다시 보고', 글)   # 한 달 전에 본 미확인은 다시 본다
        self.assertIn('3: 원문 파일이 없다', 글)                                        # 결정례를 화면으로만 본 줄
        self.assertNotIn('4:', 글)
        self.assertNotIn('1:', 글)                                                      # 판결은 PDF 로 맞댄다
        self.assertNotIn('참고', 글)                                                    # 하단 ② 참고 줄은 보지 않는다
        self.assertEqual(len(미확정), 1)
        table.write_text(table.read_text(encoding='utf-8').replace('미확인(2026. 10. 1. 봄)', '미확인(2026. 11. 1. 다시 봄)'), encoding='utf-8')
        막, _ = fc.대조표_칸(table, 오늘=dt.date(2026, 11, 2))
        self.assertFalse(any(x.startswith('2: 확정되지') for x in 막))

    def test_grouped_judgement_rows_cover_every_line_of_that_judgment(self):
        """표는 한 판결의 여러 줄을 묶어 적기도 하고 재인용 줄을 따로 두지 않는다(2026. 11. 2. 첫 밤 점검)."""
        table = self.d / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 |\n|---|---|---|\n'
                         '| 2.가.(3) | 서울행정법원 2026. 8. 14. 선고 2025구합1 판결 | 가 |\n| 4.가. | 서울행정법원 2026. 8. 14. 선고 2025구합1 판결 | 나 |\n'
                         '| 7(재인용) | 광주고등법원 2023. 1. 18. 선고 2021나2 판결 | 다 |\n| 9 | 대법원 2020. 1. 1. 선고 2019두3 판결 | 라 |\n', encoding='utf-8')
        report = self.d / '판결원문_PDF대조.md'
        report.write_text('# 대조\n\n## 사람 판정\n\n| 줄 | 판결 | PDF 의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
                          '| 2.가.(3), 4.가.(2줄) | 서울행정법원 2025구합1 | 이유 2. | 판단 | 같음 | 같음 | |\n| 7 | 광주고등법원 2021나2 | 이유 5. | 판단 | 같음 | 다름 | |\n', encoding='utf-8')
        self.assertEqual(fc.사람판정_빈(table, report), ['9(줄 없음)'])
        report.write_text(report.read_text(encoding='utf-8').replace('| 판단 | 같음 | 다름 | |', '| 판단 | 같음 |  | |'), encoding='utf-8')
        self.assertEqual(fc.사람판정_빈(table, report), ['7(재인용)(사안 비교)', '9(줄 없음)'])   # 묶어 적은 줄이 비면 그 칸을 짚는다

    def judge(self, 줄들, 표줄들):
        table = self.d / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 |\n|---|---|---|\n' + ''.join(f'| {n} | {사건} | 가 |\n' for n, 사건 in 줄들), encoding='utf-8')
        report = self.d / '판결원문_PDF대조.md'
        report.write_text('# 대조\n\n## 사람 판정\n\n| 줄 | 판결 | PDF 의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n' +
                          ''.join(f'| {n} | {판결} | 이유 | {판단} | 같음 | 같음 | |\n' for n, 판결, 판단 in 표줄들), encoding='utf-8')
        return fc.사람판정_빈(table, report)

    def test_judgement_of_another_section_does_not_cover_a_line(self):
        """2026. 11. 3. 같은 판결의 표 줄 하나만 차면 그 판결을 다른 목에서 인용한 줄까지 통과하였다."""
        판결 = '대법원 2020. 1. 1. 선고 2019두1 판결'
        self.assertEqual(self.judge([('2.가.', 판결), ('5.나.', 판결)], [('2.가.', '2019두1', '판단')]), ['5.나.(줄 없음)'])
        # 번호가 겹치게 줄여 적거나 묶어 적은 것은 그 줄이다
        self.assertEqual(self.judge([('2.가.(1) 각주', 판결), ('2.가.(1) 둘째', 판결), ('5.나. 셋째 문단', 판결), ('4-2 (나.(4))', 판결), ('7(재인용)', 판결)],
                                    [('2.가.(1) 각주·둘째(2줄)', '2019두1', '판단'), ('5.나. 셋째', '2019두1', '판단'), ('4-2', '2019두1', '판단'), ('7', '2019두1', '판단')]), [])
        self.assertEqual(self.judge([('1', 판결), ('11', 판결), ('1-2', 판결)], [('1', '2019두1', '판단')]), ['11(줄 없음)', '1-2(줄 없음)'])     # 1 은 11·1-2 가 아니다

    def test_blank_row_is_not_hidden_by_a_filled_row(self):
        """같은 목에서 다른 판결을 인용하면 표 줄 이름이 같다. 2026. 11. 3. 뒤의 찬 줄이 앞의 빈 줄을 가렸다. 묶어 적은 줄이 여럿 걸리면 하나라도 비었을 때 막는다."""
        가, 나 = '대법원 2020. 1. 1. 선고 2019두1 판결', '서울고등법원 2021. 1. 1. 선고 2020누1 판결'
        self.assertEqual(self.judge([('2.가.(2)', 가), ('2.가.(2)', 나)], [('2.가.(2)', '2019두1', ''), ('2.가.(2)', '2020누1', '판단')]), ['2.가.(2)(판단 부분인지)'])
        self.assertEqual(self.judge([('3. 라. 둘째', 가)], [('3. 라.(2줄)', '2019두1', '판단'), ('3. 라.', '2019두1', '')]), ['3. 라. 둘째(판단 부분인지)'])

    def test_row_with_blank_judgment_cell_covers_only_its_own_line(self):
        """2026. 11. 3. 점검: '판결' 칸이 빈 표 줄 하나가 번호가 겹치는 다른 판결의 인용 줄('2.가.(1) 각주')까지 통과시켰다.
        판결 칸이 비었으면 이름이 꼭 같고 그 이름으로 인용한 판결이 하나일 때만 그 줄로 본다."""
        가, 나 = '대법원 2020. 1. 1. 선고 2019두1 판결', '대법원 2021. 1. 1. 선고 2020두2 판결'
        self.assertEqual(self.judge([('2.가.(1)', 가), ('2.가.(1) 각주', 나)], [('2.가.(1)', '', '판단')]), ['2.가.(1) 각주(줄 없음)'])
        self.assertEqual(self.judge([('2.가.(1)', 가), ('2.가.(1)', 나)], [('2.가.(1)', '', '판단')]), ['2.가.(1)(줄 없음)', '2.가.(1)(줄 없음)'])
        self.assertEqual(self.judge([('2.가.(1)', 가)], [('2.가.(1)', '', '판단')]), [])
        self.assertEqual(self.judge([('2.가.(1)', 가), ('2.가.(1) 각주', 나)], [('2.가.(1)', '2019두1', '판단'), ('2.가.(1) 각주', '2020두2', '판단')]), [])

    def test_source_file_may_be_written_from_any_level_of_the_case(self):
        """2026. 11. 3. 첫 점검에서 원문 칸의 파일이 있는데도 98줄을 '원문 파일이 없다'로 막았다(라운드·사건 폴더 기준 경로, 백틱 없는 경로)."""
        작업 = self.d / '사건1' / '라운드1' / '작업'
        (작업 / '원문').mkdir(parents=True)
        (작업 / '원문' / 'a.md').write_text('글', encoding='utf-8')
        table = 작업 / '인용대조표.md'
        머리 = '| 번호 | 사건 표시 | 본문 문장 | 원문 문장 | 자리 | 주문·결론 | 다른 사유·전제 | 확정 | 원문 |\n|---|---|---|---|---|---|---|---|---|\n'
        줄 = '| {} | 근로기준정책과-1, 2020. 1. 1. | 가 | 가 | 회시 | 회시 | 없음 | 회시 | {} |\n'
        table.write_text(머리 + 줄.format(1, '`원문/a.md`') + 줄.format(2, '`작업/원문/a.md`') + 줄.format(3, '`라운드1/작업/원문/a.md`') + 줄.format(4, '작업/원문/a.md') +
                         줄.format(5, '`없는폴더/a.md`') + 줄.format(6, '화면 확인(2026. 11. 2.)'), encoding='utf-8')
        막, _ = fc.대조표_칸(table)
        self.assertEqual([x.split(':')[0] for x in 막], ['5', '6'])

    def test_bottom_list_lines_are_not_body_citations(self):
        """서면 하단 ②의 줄은 '참고(하단 ②)'로 적든 '② 2.'로 적든 본문 인용이 아니다(2026. 11. 3.). 본문 줄은 그대로 본다.
        하단 세 목록은 서면 초안에만 있다. 검토의견은 질의 번호를 ①②로 적기도 하므로 그 대조표의 ①② 줄은 본문 인용이다."""
        표 = ('| 번호 | 사건 표시 | 원문 문장 | 본문 문장 |\n|---|---|---|---|\n| 3. 가. | 대법원 2020. 1. 1. 선고 2019두1 판결 | 가 | 가 |\n'
             '| ② 2. | 대법원 2021. 1. 1. 선고 2020두2 판결 | 나 | 나 |\n| 참고(하단 ②) | 대법원 2022. 1. 1. 선고 2021두3 판결 | 다 | 다 |\n'
             '| ② 1. 뺌 | 대법원 2023. 1. 1. 선고 2022두4 판결 | 라 | 라 |\n| 4. | 대법원 2024. 1. 1. 선고 2023두5 판결 | 마 | 뺌(고친 판에서 뺐다) |\n')
        서면 = self.d / '사건' / '라운드1' / '작업' / '인용대조표.md'
        검토 = self.d / '자문' / '작업' / '인용대조표.md'
        for table in (서면, 검토):
            table.parent.mkdir(parents=True)
            table.write_text(표, encoding='utf-8')
        self.assertEqual([r['번호'] for r in fc.본문_줄(서면)], ['3. 가.'])
        self.assertEqual([r['번호'] for r in fc.본문_줄(검토)], ['3. 가.', '② 2.'])

    def test_same_reason_is_grouped_so_other_reasons_are_not_cut(self):
        self.assertEqual(fc.까닭별로(['2.가.: 원문 파일이 없다', '2.가.: 원문 파일이 없다', '4.가.: 원문 파일이 없다', '4.가.: 확정 칸을 다시 본다']),
                         '원문 파일이 없다 — 2.가., 4.가.; 확정 칸을 다시 본다 — 4.가.')

    def test_report_does_not_point_at_the_deleted_temp_file(self):
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        (폴더 / 'PDF').mkdir()
        table = 폴더 / '작업' / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 |\n|---|---|---|\n| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 가 |\n', encoding='utf-8')
        대상 = 폴더 / '서면초안.md'
        대상.write_text('본문\n', encoding='utf-8')

        def run(args):
            args = [str(a) for a in args]
            if args[0].endswith('cite_pdf_check.py'):
                return 1, f"1 — PDF 없음\n본문 인용 1줄 · 판결 1건 · 문제 1건 → {args[args.index('--out') + 1]}"
            return 0, 'ok'

        res = fc.결과()
        with mock.patch.object(fc, 'RUN', run):
            fc.판례(res, 대상, table, 폴더 / 'PDF', 폴더)
        말 = next(m for n, _, m in res.줄 if n == '판결문 PDF')
        self.assertIn('문제 1건', 말)
        self.assertNotIn('대조.md', 말)

    def test_pointer_or_one_grouped_sentence_is_not_the_handling_of_each_row(self):
        """2026. 11. 3. '수확 목록'이라는 말이 사건상태의 파일 안내에 한 번만 있어도 기록에 없는 줄 전부를 가린 것으로 보았고,
        고친 뒤에도 '나머지는 사안이 다름' 한 문장으로 161건이 지나갔다. 처리는 보고서의 줄마다 적는다."""
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        for f in ('작업/LBOX_목록.tsv', '작업/법제처_목록.json'):
            (폴더 / f).write_text('x', encoding='utf-8')
        (폴더 / '작업' / '검색기록.md').write_text('수확 목록 재확인: 걸린 169건 중 기록에 없던 161건 — 관련 8건 본문 확인, 나머지는 사안이 다름\n',
                                               encoding='utf-8')
        (폴더 / '작업' / '사건상태.md').write_text('- 수확 목록 재확인 `작업/수확목록_재확인.md`\n', encoding='utf-8')
        res = self.scan_with(폴더, self.report(1), 1)
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '막힘')
        self.assertIn("'처리' 칸이 빈 줄 1건: 2023구합1", res.줄[-1][2])

    def test_gate_does_not_rewrite_the_case_report(self):
        """밤 점검이 판결원문_PDF대조.md 를 고치면 다음 밤에 또 손댄 사건으로 잡힌다(2026. 11. 2. 첫 밤 점검)."""
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        (폴더 / 'PDF').mkdir()
        table = 폴더 / '작업' / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 |\n|---|---|---|\n| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 가 |\n', encoding='utf-8')
        대상 = 폴더 / '서면초안.md'
        대상.write_text('본문\n', encoding='utf-8')
        seen = []

        def run(args):
            seen.append([str(a) for a in args])
            return 0, 'ok'

        with mock.patch.object(fc, 'RUN', run):
            fc.판례(fc.결과(), 대상, table, 폴더 / 'PDF', 폴더)
        cmd = next(a for a in seen if a[0].endswith('cite_pdf_check.py'))
        self.assertNotIn(str(폴더), cmd[cmd.index('--out') + 1])

    def scan_with(self, 폴더, 재확인, 없음, 번호='2023구합1', 목록='', 처리=''):
        """저장한 재확인 보고서와, 다시 훑으면 나올 보고서(처리는 harvest_titles.py 가 앞 보고서에서 이어 적은 것)를 주고 검색_완결을 돌린다."""
        (폴더 / '작업' / '수확목록_재확인.md').write_text(재확인, encoding='utf-8')

        def run(args):
            args = [str(a) for a in args]
            self.assertIn('--잇기', args)                       # 앞 보고서의 처리를 이어 오게 한다
            Path(args[args.index('--out') + 1]).write_text(self.report(없음, 번호, 목록, 처리), encoding='utf-8')
            return 0, ''

        res = fc.결과()
        with mock.patch.object(fc, 'RUN', run):
            fc.검색_완결(res, 폴더)
        return res

    @staticmethod
    def report(없음, 번호='2023구합1', 목록='', 처리=''):
        return ('# 수확 목록 제목 다시 훑기 — 라운드1\n\n낱말: 시험기기\n법제처 목록 1개 파일 · 3줄' + 목록 + '\n'
                '걸린 줄 3건 — 기록에 있음 1건, 없음 %d건(그 가운데 법제처 본문을 받은 것 0건), 번호가 없어 가리지 못한 것 0건\n'
                '처리 칸이 빈 줄 %d건\n\n'
                '## 기록에 없는 줄(본문을 읽고 반영하거나 유사 사례 표에 미반영 이유를 적고, 줄마다 \'처리\' 칸에 적는다)\n\n'
                '| 출처 | 사건번호·문서번호 | 일자 | 기관·법원 | 제목 | 걸린 낱말 | 기록 | 본문 | 처리 |\n|---|---|---|---|---|---|---|---|---|\n'
                % (없음, 0 if 처리 else 없음)
                + ''.join('| LBOX | %s | 2024 | 서울행정법원 | 정직 | 시험기기 | 없음 | — | %s |\n' % (번호, 처리) for _ in range(min(없음, 1))))

    def test_rows_not_in_the_record_pass_once_each_row_has_its_handling(self):
        """기록에 번호가 없는 줄은 보고서의 '처리' 칸에 줄마다 무엇을 하였는지 적어야 지나간다. 사안이 전혀 다른 줄도 묶지 않는다."""
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        for f in ('작업/LBOX_목록.tsv', '작업/법제처_목록.json'):
            (폴더 / f).write_text('x', encoding='utf-8')
        (폴더 / '작업' / '검색기록.md').write_text('검색어 표\n', encoding='utf-8')
        res = self.scan_with(폴더, self.report(1), 1)
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '막힘')           # 처리를 적지 않았다
        self.assertIn("'처리' 칸이 빈 줄 1건", res.줄[-1][2])
        res = self.scan_with(폴더, self.report(1), 1, 처리='사안 다름: 공무원 징계')
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '통과')
        self.assertIn('줄마다 처리를 적음', res.줄[-1][2])
        res = self.scan_with(폴더, self.report(1), 1, '2024구합9')           # 보고서 뒤에 새로 걸린 줄은 처리가 이어지지 않아 막는다
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '막힘')
        self.assertIn('2024구합9', res.줄[-1][2])
        res = self.scan_with(폴더, self.report(0), 0, 목록=' / LBOX 목록 0개 파일 · 0줄(같은 줄 합친 뒤 0줄)')
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '막힘')           # 훑을 목록이 없으면 '없음 0건'은 통과가 아니다

    def test_handling_written_in_the_report_carries_over_on_rescan(self):
        """작성 세션이 보고서에 적은 처리를 최종 관문이 다시 훑을 때 이어 오는지 실제 harvest_titles.py 로 본다(묶은 한 문장은 처리가 아니다)."""
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        (폴더 / '작업' / '법제처_목록.json').write_text('{}', encoding='utf-8')
        (폴더 / '작업' / '검색기록.md').write_text('수확 목록 재확인: 나머지는 사안이 다름\n', encoding='utf-8')
        (폴더 / '작업' / 'LBOX_목록.tsv').write_text('id\t법원\t선고일\t사건\t출처\t스니펫\n' + ''.join(
            f'서울행정법원-2023구합{i}\t서울행정법원\t24-01-01\t정직처분취소\tq\t시험기기 관련\n' for i in (1, 2, 3)), encoding='utf-8')
        보고서 = 폴더 / '작업' / '수확목록_재확인.md'
        훑기 = [sys.executable, '-B', str(fc.SC / 'harvest_titles.py'), 'scan', str(폴더), '--낱말', '시험기기', '--out', str(보고서)]
        subprocess.run(훑기, capture_output=True, check=True)
        res = fc.결과()
        fc.검색_완결(res, 폴더)
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '막힘')
        self.assertIn("'처리' 칸이 빈 줄 3건", res.줄[-1][2])
        글 = 보고서.read_text(encoding='utf-8')
        for i, 처리 in ((1, '본문 반영(3.가.)'), (2, '사안 다름: 공무원 징계'), (3, '같음')):     # '같음'만 적은 칸은 빈 칸이다
            글 = re.sub(r'(\| 서울행정법원-2023구합%d \|.*\| 없음 \| — \|)[ \t]*\|' % i, lambda m: m.group(1) + f' {처리} |', 글)
        보고서.write_text(글, encoding='utf-8')
        res = fc.결과()
        fc.검색_완결(res, 폴더)
        self.assertIn("'처리' 칸이 빈 줄 1건: 서울행정법원-2023구합3", res.줄[-1][2])
        subprocess.run(훑기, capture_output=True, check=True)              # 같은 --out 으로 다시 돌려도 적어 둔 처리는 남는다
        self.assertIn('| 사안 다름: 공무원 징계 |', 보고서.read_text(encoding='utf-8'))
        글 = 보고서.read_text(encoding='utf-8').replace('| 없음 | — |  |', '| 없음 | — | 사안 다름: 민사 대여금 |')
        보고서.write_text(글, encoding='utf-8')
        res = fc.결과()
        fc.검색_완결(res, 폴더)
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '통과')

    def test_search_records_of_earlier_rounds_count_and_the_report_round_is_rescanned(self):
        """뒤 라운드의 판례는 앞 라운드 검색에서 나오기도 한다. 앞 라운드 목록을 훑은 보고서이면 그 라운드를 다시 훑는다."""
        앞, 뒤 = self.d / '라운드1', self.d / '라운드2'
        (앞 / '작업').mkdir(parents=True)
        (뒤 / '작업').mkdir(parents=True)
        for f in ('작업/LBOX_목록_2차.tsv', '작업/법제처_목록.json', '작업/검색기록.md'):
            (앞 / f).write_text('x', encoding='utf-8')
        (뒤 / '작업' / '수확목록_재확인.md').write_text('# 수확 목록 제목 다시 훑기 — 라운드1\n\n낱말: 시험기기\n', encoding='utf-8')
        seen = {}

        def run(args):
            args = [str(a) for a in args]
            seen['폴더'] = args[2]
            Path(args[args.index('--out') + 1]).write_text(self.report(0), encoding='utf-8')
            return 0, ''

        res = fc.결과()
        with mock.patch.object(fc, 'RUN', run):
            fc.검색_완결(res, 뒤)
        self.assertEqual(status(res, '판례 검색 기록'), '통과')
        self.assertEqual(seen['폴더'], str(앞))
        self.assertEqual(status(res, '찾은 판례 다시 훑기'), '통과')

    def test_rescan_of_harvested_lists_must_find_nothing_unrecorded(self):
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        for f in ('작업/LBOX_목록.tsv', '작업/법제처_목록.json', '작업/검색기록.md'):
            (폴더 / f).write_text('x', encoding='utf-8')
        (폴더 / '작업' / '수확목록_재확인.md').write_text('# 재확인\n\n낱말: 시험기기, 기계적+징계\n', encoding='utf-8')
        seen = {}

        def run(args, 없음):
            seen['args'] = [str(a) for a in args]
            out = Path(seen['args'][seen['args'].index('--out') + 1])
            out.write_text('# 수확\n\n낱말: 시험기기\n법제처 목록\n걸린 줄 3건 — 기록에 있음 1건, 없음 %d건(그 가운데 법제처 본문을 받은 것 0건), 번호가 없어 가리지 못한 것 0건\n\n'
                           '## 기록에 없는 줄(본문을 읽고 반영하거나 유사 사례 표에 미반영 이유를 적고, 줄마다 \'처리\' 칸에 적는다)\n\n'
                           '| 출처 | 사건번호·문서번호 | 일자 | 기관·법원 | 제목 | 걸린 낱말 | 기록 | 본문 | 처리 |\n|---|---|---|---|---|---|---|---|---|\n' % 없음
                           + '| LBOX | 2023구합1 | 2024 | 서울행정법원 | 정직 | 시험기기 | 없음 | — |  |\n' * min(없음, 1), encoding='utf-8')
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

    def test_memo_and_other_words_are_not_style_hits(self):
        """보완 메모는 의뢰인에게 가는 글이 아니고, '목적은 바람직' 같은 말은 '적다'가 아니다(2026. 11. 2. 첫 밤 점검)."""
        self.reply.write_text('1. 검토 요지\n\n개정의 목적은 바람직해 보입니다.\n\n## 보완 메모\n\n`작업/검색기록.md` 에 적었다.\n', encoding='utf-8')
        os.utime(self.reply, (time.time() + 10, time.time() + 10))
        self.assertEqual(status(fc.검토의견(self.case), '문체(낙관 표현·적다)'), '통과')

    def test_highest_revision_is_the_target_even_if_an_older_one_was_touched_later(self):
        """_Rev_1 을 만든 뒤 _초안 이나 회신초안의 수정 시각이 뒤로 가도 맞댈 판은 _Rev_1 이다(2026. 11. 2. 첫 밤 점검)."""
        rev = self.case / '(HPS) 근로시간면제 관련 검토_Rev_1.docx'
        rev.write_bytes(b'PK')
        os.utime(rev, (time.time() - 100, time.time() - 100))
        res = fc.검토의견(self.case)
        self.assertEqual(res.대상, rev.name)
        self.assertTrue(res.넘긴판)


class CalcGateTest(unittest.TestCase):
    def test_calculation_case_checks_material_reading_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / '6_손해배상계산' / '사건' / '가나_임금'
            case.mkdir(parents=True)
            self.assertEqual(fc.사건_종류(case), '계산')
            make_pdf(case / '급여대장.pdf', [글])
            (case / '가나_임금_계산표.xlsx').write_bytes(b'x')
            with mock.patch.object(fc, 'RUN', fake_run):
                결과들 = fc.돌리기(case, 밤=True)
            self.assertEqual(status(결과들[0][1], '자료 파악(전 면 읽기)'), '막힘')
            self.assertIn('급여대장.pdf', 결과들[0][1].줄[0][2])
            self.assertNotIn('계산표', 결과들[0][1].줄[0][2])


class NightReportTest(unittest.TestCase):
    """`/하자보완` 의 날짜별 보고 파일(--out). 2026. 11. 3. 손댄 사건이 없는 밤에 0바이트 파일이 생겼다."""

    def 돌리기(self, out, 사건들, 결과들=()):
        with mock.patch.object(fc, '최근_사건', return_value=사건들), mock.patch.object(fc, '돌리기', return_value=list(결과들)), \
                redirect_stdout(io.StringIO()):
            return fc.main(['--최근', '2.8', '--out', str(out)])

    def test_empty_night_leaves_a_line(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / '_하자보완' / '2026-11-03_관문.md'
            self.assertEqual(self.돌리기(out, []), 0)
            self.assertIn('최근 2.8시간 · 사건 0건, 막힘 0건', out.read_text(encoding='utf-8'))

    def test_rerun_keeps_earlier_report(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / '2026-11-03_관문.md'
            res = fc.결과()
            res.add('문체', '막힘', '위반 1건')
            self.assertEqual(self.돌리기(out, [Path(d) / '라운드있는사건'], [('', res)]), 1)
            self.assertEqual(self.돌리기(out, []), 0)
            글자 = out.read_text(encoding='utf-8')
            self.assertIn('사건 1건, 막힘 1건', 글자)
            self.assertIn('위반 1건', 글자)
            self.assertIn('사건 0건, 막힘 0건', 글자)

    def test_night_screen_groups_by_check_not_by_case(self):
        """`/하자보완` 은 사건이 아니라 시스템을 본다(2026. 11. 3.). 화면에는 검사별 모음을, 파일에는 사건별 전문까지 쓴다."""
        새판, 옛판 = fc.결과(), fc.결과()
        새판.대상시각, 옛판.대상시각 = time.time(), time.time() - 86400 * 9
        새판.add('문체', '막힘', '위반 1건')
        새판.add('판례 대조', '통과', '불일치 0')
        옛판.add('문체', '막힘', '위반 2건')
        옛판.add('호증 번호', '해당 없음', '')
        with tempfile.TemporaryDirectory() as d:
            가, 나 = Path(d) / '가사건', Path(d) / '나사건'
            out = Path(d) / '관문.md'
            화면 = io.StringIO()
            with mock.patch.object(fc, '최근_사건', return_value=[가, 나]), redirect_stdout(화면), \
                    mock.patch.object(fc, '돌리기', side_effect=[[('', 새판)], [('', 옛판)]]), mock.patch.object(fc, '사건_종류', return_value='서면'):
                fc.main(['--최근', '24', '--out', str(out)])
            self.assertIn('| 문체 | 2 | 0 | 가사건*, 나사건 | 위반 1건 |', 화면.getvalue())      # *는 이번 범위에 고친 판이다
            self.assertIn('| 판례 대조 | 0 | 1 |  |  |', 화면.getvalue())
            self.assertNotIn('## 가사건', 화면.getvalue())
            글자 = out.read_text(encoding='utf-8')
            self.assertIn('## 검사별 모음', 글자)
            self.assertIn('## 가사건', 글자)
            self.assertIn('위반 2건', 글자)


if __name__ == '__main__':
    unittest.main()
