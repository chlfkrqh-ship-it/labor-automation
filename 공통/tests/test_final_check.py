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


def make_opinion_docx(path: Path, 문단들):
    """review_text.py 가 읽는 검토의견서 docx(이름공간을 갖춘 본문). 관문의 문체 검사가 docx 의 글을 본다."""
    본 = ''.join(f'<w:p><w:r><w:t>{x}</w:t></w:r></w:p>' for x in 문단들)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                                        f'<w:body>{본}</w:body></w:document>')


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
        self.대조_적기(검토, self.draft)
        later(맞대기, 검토 / 'review.json')

    def 대조_적기(self, 검토: Path, 초안: Path):
        """지금 초안의 인용으로 대조(review.json)와 판정(notes.json)을 적는다. 관문은 대조해 둔 인용이 지금 인용과 같은지 늘 본다."""
        cites = fc.증거검토().parse_citations(초안.read_text(encoding='utf-8'))
        items = [{'n': n, 'key': c['key'], 'pages': c['pages'], 'sentence': c['sentence']} for n, c in enumerate(cites, 1)]
        (검토 / 'review.json').write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')
        (검토 / 'notes.json').write_text(json.dumps({str(r['n']): ['일치', '…'] for r in items}, ensure_ascii=False), encoding='utf-8')

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
        self.assertEqual(status(res, '증거 인용'), '통과')                  # 인용이 그대로이면 대조는 낡지 않았다
        self.draft.write_text(self.draft.read_text(encoding='utf-8') + '\n시험 기기를 금지하였습니다(사 제6호증 3면).\n', encoding='utf-8')
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 인용'), '막힘')                  # 인용이 늘면 다시 대조한다

    def test_opponent_brief_in_our_folder_blocks_instead_of_skipping_the_table(self):
        # 2026. 11. 3. 한전 태양광: 전자소송 기록을 한꺼번에 받아 피고 서면이 우리증거/ 에 있자 '상대 서면 맞대기'가 해당 없음으로 넘어갔다
        (self.r / '상대증거' / '신청이유서(2).pdf').unlink()
        make_pdf(self.r / '우리증거' / '광주고등법원_2025나1_087001_2026.10.08_준비서면_(준비서면)_피고 대리인_법무법인(유한)바른.pdf', ['피고 주장'])
        make_pdf(self.r / '우리증거' / '광주고등법원_2025나1_001001_2024.02.02_소장_(소장)_원고 대리인_법무법인 평안.pdf', ['우리 소장'])
        with mock.patch.object(fc, 'RUN', REAL_RUN):
            res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 나누기'), '막힘', res.줄)

    def test_unjudged_citation_and_client_table(self):
        self.complete()
        (self.r / '작업' / '증거인용검토' / 'notes.json').write_text(json.dumps({'_요약': ['판정 전']}), encoding='utf-8')
        (self.r / '작업' / '의뢰인주장_대조.md').write_text(
            '| 문서·위치 | 주장·사실 원문 | 넣을 목차 | 반영 여부 |\n|---|---|---|---|\n| 소명서 1 | 가 | 1항 | 반영 |\n| 소명서 2 | 나 | 2항 |  |\n',
            encoding='utf-8')
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 인용'), '막힘')
        self.assertEqual(status(res, '의뢰인 주장'), '막힘')

    def test_opponent_table_with_body_hash_survives_a_bottom_only_edit(self):
        """2026. 11. 3. 남은 하자: 맞대기 검사가 초안의 수정 시각만 보아 하단 메모만 고쳐도 막았다. 표 머리의 '초안 본문' 해시가 지금 본문과
        같으면 지나가고, 본문을 고치면 해시가 달라 다시 막는다. 해시가 없으면 종전대로 수정 시각으로 막는다."""
        self.complete()
        맞대기 = self.r / '작업' / '상대주장_맞대기.md'
        표 = 맞대기.read_text(encoding='utf-8')
        with redirect_stdout(io.StringIO()) as out:
            fc.main(['--본문해시', str(self.draft)])
        맞대기.write_text(out.getvalue().strip() + '\n\n' + 표, encoding='utf-8')
        self.draft.write_text(self.draft.read_text(encoding='utf-8') + '\n---\n\n① 1. 확인할 것.\n', encoding='utf-8')
        os.utime(self.draft, (time.time() + 20, time.time() + 20))
        self.assertEqual(status(fc.서면(self.case), '상대 서면 맞대기'), '통과')
        self.draft.write_text(self.draft.read_text(encoding='utf-8').replace('안전 수칙을', '안전 규칙을'), encoding='utf-8')
        os.utime(self.draft, (time.time() + 30, time.time() + 30))
        res = fc.서면(self.case)
        self.assertEqual(status(res, '상대 서면 맞대기'), '막힘')
        self.assertIn('해시가 지금 본문과 다르다', next(m for n, _, m in res.줄 if n == '상대 서면 맞대기'))
        맞대기.write_text(표, encoding='utf-8')
        os.utime(맞대기, (time.time() - 100, time.time() - 100))
        self.assertEqual(status(fc.서면(self.case), '상대 서면 맞대기'), '막힘')

    def test_client_admission_table_must_match_the_current_draft(self):
        """2026. 11. 4. `/하자보완`: 10. 31. 에 만든 인정 표가 11. 2.·3. 고친 판의 바뀐 인정 문장을 담지 않았는데도 '반영' 칸이 찼다는 것만 보고
        통과하였다(GGM 답변서(2) Rev_2). 인정 표의 '본문 문장' 칸에 따옴표로 옮긴 문장은 지금 초안 본문에 그대로 있어야 한다."""
        self.complete()
        (self.r / '작업' / '의뢰인주장_대조.md').write_text(
            '| 문서·위치 | 주장·사실(원문) | 넣을 목차 | 반영 |\n|---|---|---|---|\n| 소명서 1 | 알렸다 | 1항 | 넣음 |\n\n'
            '## 2. 의뢰인의 인정\n\n| 문서·위치 | 인정한 말 | 본문 문장 |\n|---|---|---|\n'
            '| 소명서 2 | 알렸다 | 1항 "안전 수칙을 알렸습니다" |\n| 소명서 3 | 회신 뒤 대응 없음 | 2항 회신까지만 적음 |\n', encoding='utf-8')
        res = fc.서면(self.case)
        self.assertEqual(status(res, '의뢰인 주장'), '통과', res.줄)
        self.draft.write_text(self.draft.read_text(encoding='utf-8').replace('안전 수칙을 알렸습니다', '안전 수칙과 그 뒤의 경과를 알렸습니다'),
                              encoding='utf-8')
        res = fc.서면(self.case)
        self.assertEqual(status(res, '의뢰인 주장'), '막힘')
        self.assertIn("'안전 수칙을 알렸습니다…'", next(m for n, _, m in res.줄 if n == '의뢰인 주장'))
        self.draft.write_text(self.draft.read_text(encoding='utf-8') + '\n---\n\n① 1. 안전 수칙을 알렸습니다.\n', encoding='utf-8')
        self.assertEqual(status(fc.서면(self.case), '의뢰인 주장'), '막힘')        # 하단 목록에만 남은 문장은 본문의 인정 문장이 아니다

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

    def test_submission_copy_must_match_the_handed_over_docx(self):
        """제출/ 의 _제출본 은 넘길 판과 같아야 한다(2026. 11. 3. 한전 "서면도 그때그때 바꿔주면 좋겠고 (_제출본)으로"). 옛 이름 사본만 있으면 참고."""
        self.complete()
        docx = self.r / '출력' / '(GGM) 답변서_Rev_1.docx'
        docx.write_bytes(b'PK-new')
        os.utime(docx, (time.time() + 100, time.time() + 100))
        제출 = self.r / '출력' / '제출'
        제출.mkdir(parents=True, exist_ok=True)
        self.assertEqual(status(fc.서면(self.case, 대상=docx), '제출본'), '해당 없음')
        (제출 / '(GGM) 답변서_초안.docx').write_bytes(b'PK-old')
        self.assertEqual(status(fc.서면(self.case, 대상=docx), '제출본'), '참고')
        사본 = 제출 / '(GGM) 답변서_제출본.docx'
        사본.write_bytes(b'PK-old')
        self.assertEqual(status(fc.서면(self.case, 대상=docx), '제출본'), '막힘')
        사본.write_bytes(b'PK-new')
        self.assertEqual(status(fc.서면(self.case, 대상=docx), '제출본'), '통과')
        (self.r / '출력' / '(GGM) 답변서_Rev_1.pdf').write_bytes(b'%PDF-new')
        (제출 / '(GGM) 답변서_제출본.pdf').write_bytes(b'%PDF-old')
        self.assertEqual(status(fc.서면(self.case, 대상=docx), '제출본'), '막힘')
        (제출 / '(GGM) 답변서_제출본.pdf').write_bytes(b'%PDF-new')
        self.assertEqual(status(fc.서면(self.case, 대상=docx), '제출본'), '통과')

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
        # 대조가 초안보다 새것이어도, 옛 인용 읽기가 '1·3면'의 1면을 버리고 대조해 두었으면 낡은 것이다(2026. 11. 3.)
        본문2 = 본문.replace('(사 제6호증 1면)', '(사 제6호증 1·3면)')
        self.draft.write_text(본문2, encoding='utf-8')
        옛표 = [{'n': 1, 'key': '사6', 'pages': ['3'], 'sentence': ecr.parse_citations(본문2)[0]['sentence']}]
        (검토 / 'review.json').write_text(json.dumps(옛표, ensure_ascii=False), encoding='utf-8')
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 인용'), '막힘')
        self.assertIn('인용 읽기가 바뀌었다', next(m for n, _, m in res.줄 if n == '증거 인용'))

    def test_evidence_review_is_stale_when_an_exhibit_file_changed(self):
        """판정한 뒤 호증 파일을 바꾸면 다시 대조할 때 그 인용의 판정이 비워진다. 관문도 막는다(2026. 11. 5. `/하자보완`: 호증·면·문장만 맞대어 통과시켰다)."""
        self.complete()
        검토 = self.r / '작업' / '증거인용검토'
        사6 = self.r / '우리증거' / '사 제6호증 문자.pdf'
        items = json.loads((검토 / 'review.json').read_text(encoding='utf-8'))
        for r in items:
            r['file_hash'] = fc.증거검토().file_hash(사6)
        (검토 / 'review.json').write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')
        later(검토 / 'review.json')
        self.assertEqual(status(fc.서면(self.case), '증거 인용'), '통과')
        make_pdf(사6, [글 + '1면', 글 + '2면', 글 + '작업 중 시험 기기 사용 금지', 글 + '4면'])
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 인용'), '막힘')
        self.assertIn('대조한 뒤 호증 파일이 바뀌었다(사6)', next(m for n, s, m in res.줄 if n == '증거 인용'))

    def test_grouped_exhibit_citation_needs_evidence_review(self):
        """'사 제6 내지 7호증'처럼 묶어 적은 인용만 있는 서면도 증거 인용 대조를 거친다(2026. 11. 3. '제N호증' 꼴만 인용으로 보았다)."""
        self.complete()
        self.draft.write_text('- 다 음 -\n\n1. 가\n\n안전 수칙을 알렸습니다(사 제6 내지 7호증).\n', encoding='utf-8')
        for f in (self.r / '작업' / '증거인용검토').glob('*.json'):
            f.unlink()
        res = fc.서면(self.case)
        self.assertEqual(status(res, '증거 인용'), '막힘')
        self.assertIn('증거 인용 대조를 하지 않았다', next(m for n, _, m in res.줄 if n == '증거 인용'))

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
        self.assertEqual(status(fc.서면(self.case, 초안없음_허용=True, 초안=a), '증거 인용'), '막힘')     # 빈 대조는 지금 인용과 다르다
        self.대조_적기(검토, a)
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

    def test_split_drafts_use_their_own_submission_folder(self):
        """서면을 나눈 라운드의 제출 묶음은 `출력/제출/{이름}/` 이다. 맨 위만 보아 서증 압축·제출본을 '해당 없음'으로 넘기지 않고, 호증 번호
        검사에는 어느 서면인지 넘긴다(2026. 11. 8. `/하자보완`: 상병별로 나눈 심사청구의 두 묶음을 보지 않았다)."""
        self.draft.unlink()
        a = self.r / '출력' / '서면초안_림프종.md'
        b = self.r / '출력' / '서면초안_적응장애우울증.md'
        for p in (a, b):
            p.write_text('- 다 음 -\n\n1. 가\n\n사실입니다(증 제1호증).\n', encoding='utf-8')
        for 폴더 in ('림프종', '적응장애·우울증'):
            d = self.r / '출력' / '제출' / 폴더
            (d / '증거').mkdir(parents=True)
            (d / f'(갑) 심사청구 취지 및 이유({폴더})_서증.zip').write_bytes(b'PK')
        self.assertEqual(fc.제출_자리(self.r, a).name, '림프종')
        self.assertEqual(fc.제출_자리(self.r, b).name, '적응장애·우울증')
        불린 = []

        def 적기(args):
            불린.append([str(x) for x in args])
            return fake_run(args)

        with mock.patch.object(fc, 'RUN', 적기):
            res = fc.서면(self.case, 초안없음_허용=True, 초안=b)
        self.assertEqual(status(res, '서증 압축'), '통과')
        압축 = next(x for x in 불린 if Path(x[0]).name == 'evidence_zip.py')
        self.assertEqual(Path(압축[1]).name, '적응장애·우울증')
        호증 = next(x for x in 불린 if Path(x[0]).name == 'citation_check.py')
        self.assertEqual(호증[-2:], ['--서면', str(b)])
        b.unlink()                                                    # 서면이 하나면 제출/ 맨 위이다
        self.assertEqual(fc.제출_자리(self.r, a), self.r / '출력' / '제출')

    def 나눈_초안(self):
        """상병별로 나눈 두 서면의 초안. (림프종, 적응장애우울증)."""
        self.draft.unlink()
        a = self.r / '출력' / '서면초안_림프종.md'
        b = self.r / '출력' / '서면초안_적응장애우울증.md'
        a.write_text('- 다 음 -\n\n1. 가\n\n혈액암 진단을 받았습니다.\n', encoding='utf-8')
        b.write_text('- 다 음 -\n\n1. 가\n\n우울증 진단을 받았습니다.\n', encoding='utf-8')
        return a, b

    def test_split_docx_target_pairs_with_its_own_draft(self):
        """서면을 나눈 라운드의 docx 대상은 그 서면의 초안과 짝짓는다. 2026. 11. 9. 이승민 심사청구: 적응장애·우울증 docx 를 대상으로 주자
        초안 목록의 첫째(림프종)와 짝지어 호증 번호·판례 대조·DOCX·제출본을 림프종 서면의 것과 맞대었다."""
        a, b = self.나눈_초안()
        docx = self.r / '출력' / '(이승민) 심사청구 취지 및 이유(적응장애·우울증)_초안.docx'
        make_docx(docx, ['다 음', '가', '우울증 진단을 받았습니다.', '2026. 11.   .'])
        later(docx)
        불린 = []

        def 적기(args):
            불린.append([str(x) for x in args])
            return fake_run(args)

        with mock.patch.object(fc, 'RUN', 적기):
            res = fc.서면(self.case, 대상=docx)
        self.assertEqual(res.대상, f'라운드1/출력/{b.name} ← {docx.name}')
        self.assertEqual(next(x for x in 불린 if Path(x[0]).name == 'citation_check.py')[-2:], ['--서면', str(b)])
        self.assertEqual(next(x for x in 불린 if Path(x[0]).name == 'evidence_read.py')[-2:], ['--서면', '적응장애우울증'])
        self.assertEqual(next(x for x in 불린 if Path(x[0]).name == 'evidence_words.py')[-2:], ['--서면', '적응장애우울증'])
        self.assertEqual(status(res, 'DOCX'), '통과')
        # 이름이 없는 제출본 사본은 제출/{이름}/ 자리로 가린다
        사본 = self.r / '출력' / '제출' / '림프종' / '(이승민) 심사청구 취지 및 이유_제출본.docx'
        사본.parent.mkdir(parents=True)
        사본.write_bytes(b'PK')
        self.assertEqual(fc.짝_초안(self.r, 사본), (a, ''))
        # 가리지 못하면 첫 초안과 짝짓지 않고 막는다
        모름 = self.r / '출력' / '(이승민) 심사청구 취지 및 이유_초안.docx'
        make_docx(모름, ['우울증 진단을 받았습니다.'])
        res = fc.서면(self.case, 대상=모름)
        self.assertEqual(status(res, '초안'), '막힘')
        self.assertIn('어느 서면의 것인지', next(m for n, _, m in res.줄 if n == '초안'))
        self.assertNotIn('문체', [n for n, _, _ in res.줄])
        b.unlink()                                                    # 나누지 않은 라운드는 예전처럼 하나뿐인 초안과 짝짓는다
        self.assertEqual(fc.짝_초안(self.r, 모름), (None, ''))

    def 기록_채우기(self, k: str):
        """호증 하나의 전 면 읽기 기록을 채운다(면마다 확인표, 읽은 방식, 쟁점 문구, 실측 줄). 재는 일은 test_evidence_read 가 본다."""
        자 = er.자리(self.case, False)
        rec, 글파일 = 자.기록_파일(k), 자.글_파일(k)
        t = rec.read_text(encoding='utf-8').replace('읽은 방식: \n', '읽은 방식: 글자층 전 면\n').replace('면)\n\n- \n', '면)\n\n- 1면 "진단"\n', 1)
        for n, 표 in re.findall(r'\[(\d+)면 끝 · 확인표 ([A-Z0-9]{4})\]', 글파일.read_text(encoding='utf-8')):
            t = t.replace(f'- {n}면: \n', f'- {n}면: 진단 내용 확인표 {표}\n')
        rec.write_text(t, encoding='utf-8')
        er.실측_적기(rec, f'실측: 시험 · 글 {er.해시(글파일)}')

    def test_split_round_reading_gate_sees_only_its_own_share(self):
        """서면을 나눈 라운드의 전 면 읽기는 그 서면의 호증과 공통 자료만 막는다. 2026. 11. 9. 이승민 심사청구: 림프종 서면 관문의 막힘
        119건 가운데 85건이 적응장애·우울증 서면의 호증 27건과 그 서면만 인용한 참고자료, 우리 서면 사본이었다."""
        a, b = self.나눈_초안()
        (self.r / '우리증거' / '사 제6호증 문자.pdf').unlink()
        (self.r / '상대증거' / '신청이유서(2).pdf').unlink()
        for 폴더, 글자 in (('림프종', '혈액암'), ('적응장애·우울증', '우울증')):
            (self.r / '출력' / '제출' / 폴더 / '증거').mkdir(parents=True)
            make_pdf(self.r / '출력' / '제출' / 폴더 / '증거' / '증 제1호증_진단서.pdf', [글 + 글자 + ' 진단'])
        (self.r / '참고자료' / '강 변호사 송부본').mkdir(parents=True)
        make_docx(self.r / '참고자료' / '강 변호사 송부본' / '(이승민) 심사청구 취지 및 이유(림프종)_초안.docx', ['혈액암 진단을 받았습니다.'])  # 우리 서면 사본
        with redirect_stdout(io.StringIO()):
            er.main(['make', str(self.case), '--no-ocr'])
        self.기록_채우기('증1@림프종')
        res = fc.서면(self.case, 초안없음_허용=True, 초안=a)
        self.assertEqual(status(res, '증거 파악(전 면 읽기)'), '통과', res.줄)
        말 = next(m for n, _, m in res.줄 if n == '증거 파악(전 면 읽기)')
        self.assertIn("범위: 서면 '림프종' 몫", 말)
        self.assertIn('다른 서면의 호증 1건', 말)
        self.assertIn('우리 산출물 사본 1건', 말)
        res = fc.서면(self.case, 초안없음_허용=True, 초안=b)
        self.assertEqual(status(res, '증거 파악(전 면 읽기)'), '막힘')
        self.assertIn('증 제1호증(적응장애우울증)', next(m for n, _, m in res.줄 if n == '증거 파악(전 면 읽기)'))
        self.기록_채우기('증1@적응장애우울증')
        self.assertEqual(status(fc.서면(self.case, 초안없음_허용=True, 초안=b), '증거 파악(전 면 읽기)'), '통과')

    def test_split_docx_target_finds_other_briefs_admissions_in_their_drafts(self):
        """의뢰인 인정 표는 라운드에 하나이다. docx 를 볼 때 다른 서면의 인정 문장은 그 서면의 초안에서 찾는다(docx 하나만 보아 막지 않는다)."""
        a, b = self.나눈_초안()
        (self.r / '작업' / '의뢰인주장_대조.md').write_text(
            '| 문서·위치 | 주장·사실(원문) | 넣을 목차 | 반영 |\n|---|---|---|---|\n| 문답서 1 | 진단 | 1항 | 넣음 |\n\n'
            '## 2. 의뢰인의 인정\n\n| 문서·위치 | 인정한 말 | 본문 문장 |\n|---|---|---|\n'
            '| 문답서 2 | 혈액암 | 림프종 1항 "혈액암 진단을 받았습니다" |\n| 문답서 3 | 우울증 | 적응장애 1항 "우울증 진단을 받았습니다" |\n',
            encoding='utf-8')
        docx = self.r / '출력' / '(이승민) 심사청구 취지 및 이유(적응장애·우울증)_초안.docx'
        make_docx(docx, ['다 음', '가', '우울증 진단을 받았습니다.'])
        later(docx)
        self.assertEqual(status(fc.서면(self.case, 대상=docx), '의뢰인 주장'), '통과')
        a.write_text(a.read_text(encoding='utf-8').replace('혈액암 진단을', '혈액암 판정을'), encoding='utf-8')
        res = fc.서면(self.case, 대상=docx)
        self.assertEqual(status(res, '의뢰인 주장'), '막힘')
        self.assertIn("'혈액암 진단을 받았습니다…'", next(m for n, _, m in res.줄 if n == '의뢰인 주장'))


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
                          '| 1 | 2019두1 | 본문 · 2. 원고의 주장 — 주의: 앞 글에 주장 | 판단 | 같음 | 판시 쟁점: 양정 다툼 / 같은 점: 양정 다툼 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n'
                          '| 2 | 2020누1 | 이유 3. | 판단 | 같음 | 판시 쟁점: 징계양정 / 같은 점: 근태 비위 / 다른 점: 공무원 사건 / 원용 까닭: 양정 판단 기준 | |\n', encoding='utf-8')
        self.assertEqual(fc.사람판정_빈(table, report), ['1(비고(주의 줄))'])   # 주장 대목 곁의 문장은 까닭을 적는다
        report.write_text(report.read_text(encoding='utf-8').replace('원용 까닭: 양정 판단 기준 | |', '원용 까닭: 양정 판단 기준 | 배척한 주장 뒤의 법원 판단 |'),
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
                          '| 2.가.(3), 4.가.(2줄) | 서울행정법원 2025구합1 | 이유 2. | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n| 7 | 광주고등법원 2021나2 | 이유 5. | 판단 | 같음 | 판시 쟁점: 징계양정 / 같은 점: 근태 비위 / 다른 점: 공무원 사건 / 원용 까닭: 양정 판단 기준 | |\n', encoding='utf-8')
        self.assertEqual(fc.사람판정_빈(table, report), ['9(줄 없음)'])
        report.write_text(report.read_text(encoding='utf-8').replace('| 판단 | 같음 | 판시 쟁점: 징계양정 / 같은 점: 근태 비위 / 다른 점: 공무원 사건 / 원용 까닭: 양정 판단 기준 | |', '| 판단 | 같음 |  | |'), encoding='utf-8')
        self.assertEqual(fc.사람판정_빈(table, report), ['7(재인용)(사안 비교)', '9(줄 없음)'])   # 묶어 적은 줄이 비면 그 칸을 짚는다

    def judge(self, 줄들, 표줄들):
        table = self.d / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 |\n|---|---|---|\n' + ''.join(f'| {n} | {사건} | 가 |\n' for n, 사건 in 줄들), encoding='utf-8')
        report = self.d / '판결원문_PDF대조.md'
        report.write_text('# 대조\n\n## 사람 판정\n\n| 줄 | 판결 | PDF 의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n' +
                          ''.join(f'| {n} | {판결} | 이유 | {판단} | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n' for n, 판결, 판단 in 표줄들), encoding='utf-8')
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

    def test_case_comparison_needs_four_parts_and_the_difference_in_disposition(self):
        """2026. 11. 9. 담당 노무사 "응 그렇게 보강해줘": '사안 비교'가 찼는지만 보아 '같은 징계 사건' 한 줄로도 지나갔다(11. 6. 안산 판결은
        강등에 대한 판단만 있어 원용하기 어려웠다). 판시 쟁점·같은 점·다른 점·원용 까닭 네 부분이어야 하고, 판결이 판단한 처분이
        본문 명제의 처분(그 문장에 없으면 산출물이 주로 다투는 처분)과 다르면 다른 점에 그 차이를 적어야 지나간다."""
        table = self.d / '인용대조표.md'
        report = self.d / '판결원문_열람대조.md'
        머리 = '| 번호 | 사건 표시 | 본문 문장 | 원문 문장 | 주문·결론 |\n|---|---|---|---|---|\n'

        def 판정(사안, 본문='정직 3월은 비위의 정도에 비하여 지나치게 무겁습니다', 글=''):
            table.write_text(머리 + f'| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | {본문} | 재량권을 일탈·남용하였다고 볼 수 없다 | '
                             '강등처분 취소 청구 기각 |\n', encoding='utf-8')
            report.write_text('# 판결 원문 열람 대조\n\n## 사람 판정\n\n| 줄 | 판결 | 원문의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
                              f'| 1 | 2019두1 | 이유 2. | 판단 | 같음 | {사안} | |\n', encoding='utf-8')
            return fc.사람판정_빈(table, report, 글=글)
        self.assertIn('판시 쟁점: / 같은 점: / 다른 점: / 원용 까닭: 으로 나누어 적는다', 판정('같은 징계 사건')[0])
        self.assertIn('사안 비교의 원용 까닭', 판정('판시 쟁점: 강등의 양정 / 같은 점: 근태 비위 / 다른 점: 처분이 강등')[0])
        self.assertIn('사안 비교의 같은 점·다른 점', 판정('판시 쟁점: 강등의 양정 / 같은 점: 유사 / 다른 점: - / 원용 까닭: 양정 기준')[0])
        self.assertIn('모두 없음', 판정('판시 쟁점: 강등의 양정 / 같은 점: 없음 / 다른 점: 없음 / 원용 까닭: 양정 기준')[0])
        # 판시 쟁점에 처분을 적지 않아도 대조표의 주문·결론(강등)으로 판결의 처분을 본다
        막 = 판정('판시 쟁점: 징계양정의 재량 / 같은 점: 근태 비위 / 다른 점: 직급이 다르다 / 원용 까닭: 양정 판단 기준')
        self.assertIn('판결은 강등 사안이고 본문 명제는 정직인데', 막[0])
        self.assertEqual(판정('판시 쟁점: 강등의 양정 / 같은 점: 근태 비위 / 다른 점: 처분이 강등이다(우리는 정직) / '
                            '원용 까닭: 양정 판단 기준만 옮긴다'), [])
        # 본문 문장에 처분이 없으면 산출물이 주로 다투는 처분과 견준다
        사안 = '판시 쟁점: 징계양정의 재량 / 같은 점: 근태 비위 / 다른 점: 직급이 다르다 / 원용 까닭: 양정 판단 기준'
        self.assertIn('본문 명제는 정직인데', 판정(사안, 본문='징계양정이 지나치게 무겁습니다', 글='정직 3월 처분 … 정직 … 정직\n---\n해고')[0])
        self.assertEqual(판정(사안, 본문='징계양정이 지나치게 무겁습니다', 글='강등 처분 … 강등 … 강등'), [])
        self.assertEqual(판정(사안, 본문='징계양정이 지나치게 무겁습니다'), [])      # 산출물에서도 처분을 알 수 없으면 견주지 않는다

    def test_without_pdf_folder_the_viewing_record_is_checked(self):
        """2026. 11. 6. 담당자 지시로 대조용 판결문 PDF 를 받지 않고 법제처 본문·LBOX 화면 글을 열람해 맞댄다.
        PDF 폴더가 없으면 판결원문_열람대조.md 의 '사람 판정' 표를 보고, 그 기록도 없으면 막는다."""
        폴더 = self.d / '자문'
        (폴더 / '작업').mkdir(parents=True)
        table = 폴더 / '작업' / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 |\n|---|---|---|\n| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 가 |\n', encoding='utf-8')
        대상 = 폴더 / '회신초안.md'
        대상.write_text('본문\n', encoding='utf-8')
        머리 = ('# 판결 원문 열람 대조\n\n## 사람 판정\n\n'
              '| 줄 | 판결 | 원문의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n')
        with mock.patch.object(fc, 'RUN', lambda args: (0, 'ok')):
            res = fc.결과()
            fc.판례(res, 대상, table, 폴더 / '작업' / '인용판결_PDF', 폴더)
            self.assertEqual(status(res, '판결 원문 대조'), '막힘')
            (폴더 / '작업' / '판결원문_열람대조.md').write_text(
                머리 + '| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 판결요지(주의: 앞 글이 원심 판단) | 판단 부분 | 같은 방향 |  |  |\n', encoding='utf-8')
            res = fc.결과()
            fc.판례(res, 대상, table, 폴더 / '작업' / '인용판결_PDF', 폴더)
            self.assertEqual(status(res, '판결 판단 부분·방향·사안 비교'), '막힘')
            self.assertIn('1(사안 비교, 비고(주의 줄))', res.줄[-1][2])
            (폴더 / '작업' / '판결원문_열람대조.md').write_text(
                머리 + '| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 판결요지(주의: 앞 글이 원심 판단) | 판단 부분 | 같은 방향 | 판시 쟁점: 징계양정 / 같은 점: 근태 비위 / 다른 점: 사업장 규모 / 원용 까닭: 양정 판단 기준 | 원심 판단은 인용하지 않음 |\n',
                encoding='utf-8')
            res = fc.결과()
            fc.판례(res, 대상, table, 폴더 / '작업' / '인용판결_PDF', 폴더)
            self.assertEqual(status(res, '판결 판단 부분·방향·사안 비교'), '통과')
            self.assertNotIn('판결문 PDF', [n for n, _, _ in res.줄])

    def test_supreme_court_disposition_is_checked_in_the_viewing_record(self):
        """2026. 11. 7. `/하자보완`: 열람 대조로 바꾼 뒤(11. 6.) 관문이 산출물에 적은 상급심의 처리를 판결문으로 보았는지 보지 않았다
        (PDF 대조의 상급심 검사가 하던 일, 2026. 11. 2. 이케아 각주 16). '확정' 칸의 대법원 번호가 산출물에 나오고 심리불속행·문서 없음 표기가
        없으면 열람 대조 기록의 '상급심' 절에 그 번호가 있어야 한다. 산출물에 상급심을 적지 않은 글은 보지 않는다."""
        폴더 = self.d / '자문'
        (폴더 / '작업').mkdir(parents=True)
        table = 폴더 / '작업' / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 | 확정 |\n|---|---|---|---|\n'
                         '| 1 | 서울고등법원 2021. 1. 1. 선고 2020누1 판결 | 가 | 대법원 2021두9 판결로 확정 |\n'
                         '| 2 | 서울고등법원 2022. 1. 1. 선고 2021누2 판결 | 나 | 대법원 2022두8 심리불속행 기각으로 확정 |\n', encoding='utf-8')
        대상 = 폴더 / '회신초안.md'
        대상.write_text('서울고등법원 2020누1 판결(대법원 2021두9 판결로 확정), 서울고등법원 2021누2 판결(대법원 2022두8 심리불속행 기각으로 확정)\n',
                      encoding='utf-8')
        판정 = ('# 판결 원문 열람 대조\n\n## 사람 판정\n\n| 줄 | 판결 | 원문의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
              '| 1 | 2020누1 | 이유 2. | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n| 2 | 2021누2 | 이유 3. | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n')
        열람 = 폴더 / '작업' / '판결원문_열람대조.md'
        열람.write_text(판정, encoding='utf-8')

        def 돌림():
            res = fc.결과()
            fc.판례(res, 대상, table, 폴더 / '작업' / '인용판결_PDF', 폴더)
            return res
        with mock.patch.object(fc, 'RUN', lambda args: (0, 'ok')):
            res = 돌림()
            self.assertEqual(status(res, '상급심 처리'), '막힘')
            말 = next(m for n, _, m in res.줄 if n == '상급심 처리')
            self.assertIn('1 대법원 2021두9', 말)
            self.assertNotIn('2022두8', 말)                 # 심리불속행 표기는 판결문이 없어도 칸의 표기대로 넘어간다
            열람.write_text(판정 + '\n## 상급심의 처리\n\n| 줄 | 산출물의 표기 | 확인한 것 |\n|---|---|---|\n'
                          '| 1 | 대법원 2021두9 판결로 확정 | 2021두9 화면 글(상고이유를 판단한 뒤 상고기각) |\n', encoding='utf-8')
            self.assertEqual(status(돌림(), '상급심 처리'), '통과')
            열람.write_text(판정 + '\n## 원문 자리\n\n대법원 2021두9 는 다음에 본다.\n', encoding='utf-8')     # 다른 절에 번호만 있으면 본 것이 아니다
            self.assertEqual(status(돌림(), '상급심 처리'), '막힘')
            대상.write_text('서울고등법원 2020누1 판결, 서울고등법원 2021누2 판결\n', encoding='utf-8')     # 상급심을 적지 않은 글
            self.assertNotIn('상급심 처리', [n for n, _, _ in 돌림().줄])

    def test_viewing_record_disposition_must_match_the_finality_cell(self):
        """2026. 11. 10. `/하자보완`: 상급심 절에 번호가 있는지만 보아, 기록에는 심리불속행 기각이라고 적고 '확정' 칸·산출물은 '판결로 확정'인
        줄이 지나갔다(PDF 대조는 판결문 글과 칸의 표기를 맞대었다). 칸이 심리불속행인데 기록이 '심리불속행 기각이 아님'이라고 적은 줄도 막는다.
        한 줄에 다른 상급심의 처리를 함께 적었으면 그 번호의 몫만 본다."""
        폴더 = self.d / '자문2'
        (폴더 / '작업').mkdir(parents=True)
        table = 폴더 / '작업' / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 | 확정 |\n|---|---|---|---|\n'
                         '| 1 | 서울고등법원 2021. 1. 1. 선고 2020누1 판결 | 가 | 대법원 2021두9 판결로 확정 |\n'
                         '| 2 | 서울고등법원 2022. 1. 1. 선고 2021누2 판결 | 나 | 대법원 2022두8 심리불속행 기각으로 확정 |\n', encoding='utf-8')
        대상 = 폴더 / '회신초안.md'
        대상.write_text('서울고등법원 2020누1 판결(대법원 2021두9 판결로 확정), 서울고등법원 2021누2 판결(대법원 2022두8 심리불속행 기각으로 확정)\n',
                      encoding='utf-8')
        판정 = ('# 판결 원문 열람 대조\n\n## 사람 판정\n\n| 줄 | 판결 | 원문의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
              '| 1 | 2020누1 | 이유 2. | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n'
              '| 2 | 2021누2 | 이유 3. | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n'
              '\n## 상급심의 처리\n\n')
        열람 = 폴더 / '작업' / '판결원문_열람대조.md'

        def 돌림(상급):
            열람.write_text(판정 + 상급, encoding='utf-8')
            res = fc.결과()
            fc.판례(res, 대상, table, 폴더 / '작업' / '인용판결_PDF', 폴더)
            return status(res, '상급심 처리'), next(m for n, _, m in res.줄 if n == '상급심 처리')
        with mock.patch.object(fc, 'RUN', lambda args: (0, 'ok')):
            self.assertEqual(돌림('- 대법원 2021두9: 상고이유를 판단해 상고기각(심리불속행 기각이 아님).\n'
                                 '- 대법원 2022두8: 판결문 화면, 특례법 제5조에 따른 심리불속행 기각.\n')[0], '통과')
            상태, 말 = 돌림('- 대법원 2021두9: 판결문 화면, 특례법 제5조에 따른 심리불속행 기각.\n')
            self.assertEqual(상태, '막힘')
            self.assertIn("1 대법원 2021두9(열람 기록은 심리불속행 기각인데 '확정' 칸에 심리불속행이 없다)", 말)
            상태, 말 = 돌림('- 대법원 2021두9: 상고이유를 판단(심리불속행 기각이 아님).\n- 대법원 2022두8: 상고이유를 판단해 기각, 심리불속행이 아니다.\n')
            self.assertEqual(상태, '막힘')
            self.assertIn("2 대법원 2022두8(열람 기록은 심리불속행 기각이 아니라고 적었는데 '확정' 칸은 심리불속행)", 말)
            self.assertNotIn('2021두9', 말)
            self.assertEqual(돌림('- 대법원 2021두9: 상고이유를 판단해 상고기각. 같은 날 대법원 2022두8 은 심리불속행 기각.\n')[0], '통과')
            for 말 in ('심리불속행 기각이 아닌 판결', '심리불속행 사유가 아니라고 보고 상고이유를 판단', '심리불속행으로 기각하지 않고 판단'):
                self.assertEqual(돌림(f'- 대법원 2021두9: {말}.\n')[0], '통과', 말)       # 부정으로 적은 꼴
            self.assertEqual(돌림('| 줄 | 산출물의 표기 | 확인한 것 |\n|---|---|---|\n| 1 | 대법원 2021두9 판결로 확정 | 2021두9 화면 글(상고이유 판단) |\n')[0],
                             '통과')                                       # 처리를 어느 쪽으로도 적지 않은 줄은 번호만 본다(종전대로)

    def test_pdf_folder_case_takes_the_viewing_record_for_rows_without_pdf(self):
        """2026. 11. 7. `/하자보완`: 판결문 PDF 를 받아 둔 사건(PDF 폴더 있음)에서 고친 판에 더한 판결·상급심은 11. 6. 지시로 PDF 를 받지 않는데,
        관문이 PDF 를 더 받으라고 막았다(이승민 심사청구 상급심 2건). 문제가 모두 'PDF 없음'이고 그 줄·상급심을 열람 대조 기록이 다루면 지나간다.
        PDF 로 맞댄 줄에 다른 문제가 있으면 그대로 막는다."""
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        pdfdir = 폴더 / '참고자료' / '인용판결_PDF'
        pdfdir.mkdir(parents=True)
        make_pdf(pdfdir / '대법원 2019두1 판결.pdf', ['대법원 2020. 1. 1. 선고 2019두1 판결\n가나다라마바사 판단이다.'])
        table = 폴더 / '작업' / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 | 확정 |\n|---|---|---|---|\n'
                         '| 1 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 가나다라마바사 판단이다 | 확정 |\n'
                         '| 2 | 서울고등법원 2021. 1. 1. 선고 2020누1 판결 | 아자차카타 | 대법원 2021두9 판결로 확정 |\n'
                         '| 3 | 대법원 2020. 1. 1. 선고 2019두1 판결 | 가나다라마바사 | 확정(환송 뒤 대법원 2020두5 판결로 확정) |\n', encoding='utf-8')
        대상 = 폴더 / '서면초안.md'
        대상.write_text('대법원 2019두1 판결(환송 뒤 대법원 2020두5 판결로 확정)과 서울고등법원 2020누1 판결(대법원 2021두9 판결로 확정)\n',
                      encoding='utf-8')
        (폴더 / '작업' / '판결원문_PDF대조.md').write_text(
            '# 대조\n\n## 사람 판정\n\n| 줄 | 판결 | PDF 의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
            '| 1 | 2019두1 | 본문 · 이유 | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n| 2 | 2020누1 |  |  |  |  | |\n| 3 | 2019두1 | 본문 · 이유 | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n',
            encoding='utf-8')
        판정 = ('# 판결 원문 열람 대조\n\n## 사람 판정\n\n| 줄 | 판결 | 원문의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
              '| 2 | 2020누1 | 이유 3. | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n')
        한줄 = '\n## 상급심의 처리\n\n| 줄 | 산출물의 표기 | 확인한 것 |\n|---|---|---|\n| 2 | 대법원 2021두9 판결로 확정 | 2021두9 화면 글(상고기각) |\n'
        상급 = 한줄 + '| 3 | 대법원 2020두5 판결로 확정 | 2020두5 화면 글(상고기각) |\n'
        열람 = 폴더 / '작업' / '판결원문_열람대조.md'

        def 돌림():
            res = fc.결과()
            with mock.patch.object(fc, '검색_완결', lambda *a: None):
                fc.판례(res, 대상, table, pdfdir, 폴더)
            return res
        res = 돌림()                                           # 열람 기록이 없으면 종전대로 PDF 를 요구한다
        self.assertEqual(status(res, '판결문 PDF'), '막힘')
        열람.write_text(판정, encoding='utf-8')
        res = 돌림()                                           # 본문 줄은 열람 기록에 있으나 상급심이 없다
        self.assertEqual(status(res, '판결문 PDF'), '막힘')
        말 = next(m for n, _, m in res.줄 if n == '판결문 PDF')
        self.assertIn('2 대법원 2021두9', 말)                  # PDF 가 없는 줄의 상급심
        self.assertIn('3 대법원 2020두5', 말)                  # PDF 가 있는 줄의 상급심(PDF 대조가 'PDF 없음'으로 짚은 것)
        열람.write_text(판정 + 한줄, encoding='utf-8')
        self.assertEqual(status(돌림(), '판결문 PDF'), '막힘')
        열람.write_text(판정 + 상급, encoding='utf-8')
        res = 돌림()
        self.assertEqual(status(res, '판결문 PDF'), '통과')
        self.assertEqual(status(res, '판결 판단 부분·방향·사안 비교'), '통과')     # 2 의 빈 PDF 판정 줄은 열람 기록의 판정으로 갈음한다
        열람.write_text(판정.replace('| 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 |', '| 판단 | 같음 |  |') + 상급, encoding='utf-8')
        res = 돌림()
        self.assertEqual(status(res, '판결 판단 부분·방향·사안 비교'), '막힘')
        self.assertIn('2(사안 비교)', next(m for n, _, m in res.줄 if n == '판결 판단 부분·방향·사안 비교'))
        열람.write_text(판정 + 상급, encoding='utf-8')
        table.write_text(table.read_text(encoding='utf-8').replace('가나다라마바사 판단이다', '없는 문장입니다'), encoding='utf-8')
        res = 돌림()                                           # PDF 로 맞댄 줄의 다른 문제는 열람 기록으로 갈음하지 않는다
        self.assertEqual(status(res, '판결문 PDF'), '막힘')

    def test_supreme_court_only_in_brief_bottom_notes_is_not_asked_for(self):
        """2026. 11. 10. `/하자보완`: 서면 초안 MD 의 하단 세 목록('---' 아래)은 담당자에게 남기는 메모이고 docx 에 들어가지 않는다.
        11. 9. 이승민 적응장애·우울증 서면이 하단 ② 에만 적은 상급심 둘의 판결문을 밤 관문(대상 MD)은 요구해 막고, 사건 세션의
        관문(대상 docx)은 막힘 0 이어서 같은 판의 결과가 대상에 따라 갈렸다. 상급심은 본문에 적었을 때 보고(PDF 대조·열람 대조 모두),
        서면 초안이 아닌 글(회신초안 등)의 '---' 아래는 그대로 본다."""
        폴더 = self.d / '라운드1'
        (폴더 / '작업').mkdir(parents=True)
        pdfdir = 폴더 / '참고자료' / '인용판결_PDF'
        pdfdir.mkdir(parents=True)
        make_pdf(pdfdir / '서울고등법원 2020누1 판결.pdf', ['서울고등법원 2021. 1. 1. 선고 2020누1 판결\n가나다라마바사 판단이다.'])
        table = 폴더 / '작업' / '인용대조표.md'
        table.write_text('| 번호 | 사건 표시 | 원문 문장 | 확정 |\n|---|---|---|---|\n'
                         '| 1 | 서울고등법원 2021. 1. 1. 선고 2020누1 판결 | 가나다라마바사 판단이다 | 대법원 2021두9 판결로 확정 |\n', encoding='utf-8')
        (폴더 / '작업' / '판결원문_PDF대조.md').write_text(
            '# 대조\n\n## 사람 판정\n\n| 줄 | 판결 | PDF 의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
            '| 1 | 2020누1 | 본문 · 이유 | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n',
            encoding='utf-8')
        본문 = '서울고등법원 2021. 1. 1. 선고 2020누1 판결은 가나다라마바사 판단이다라고 보았습니다.\n'
        하단 = '\n---\n\n② 1. 그 판결은 대법원 2021두9 판결로 확정되었다.\n'

        def 돌림(대상, pdf=pdfdir):
            res = fc.결과()
            with mock.patch.object(fc, '검색_완결', lambda *a: None):
                fc.판례(res, 대상, table, pdf, 폴더)
            return res
        초안 = 폴더 / '서면초안_림프종.md'
        초안.write_text(본문 + 하단, encoding='utf-8')
        self.assertEqual(status(돌림(초안), '판결문 PDF'), '통과')                     # 하단 메모에만 적은 상급심은 열지 않는다
        회신 = 폴더 / '회신초안.md'
        회신.write_text(본문 + 하단, encoding='utf-8')
        self.assertEqual(status(돌림(회신), '판결문 PDF'), '막힘')                     # 서면 초안이 아닌 글은 '---' 아래도 산출물이다
        초안.write_text(본문.replace('보았습니다.', '보았습니다(대법원 2021두9 판결로 확정).') + 하단, encoding='utf-8')
        self.assertEqual(status(돌림(초안), '판결문 PDF'), '막힘')                     # 본문에 적으면 판결문을 본다
        # PDF 폴더가 없는 사건(열람 대조 기록)도 같다
        (폴더 / '작업' / '판결원문_열람대조.md').write_text(
            '# 판결 원문 열람 대조\n\n## 사람 판정\n\n| 줄 | 판결 | 원문의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
            '| 1 | 2020누1 | 이유 3. | 판단 | 같음 | 판시 쟁점: 징계양정의 재량 / 같은 점: 사무직의 비위 / 다른 점: 없음 / 원용 까닭: 양정 판단 기준 | |\n',
            encoding='utf-8')
        없는폴더 = 폴더 / '참고자료' / '없음'
        self.assertEqual(status(돌림(초안, 없는폴더), '상급심 처리'), '막힘')
        초안.write_text(본문 + 하단, encoding='utf-8')
        self.assertNotIn('상급심 처리', [n for n, _, _ in 돌림(초안, 없는폴더).줄])

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
        # LBOX 를 멈춘 동안(2026. 11. 11.~)에는 검색기록의 'LBOX 중지' 줄이 LBOX 목록을 갈음한다. 줄이 없으면 그 방법을 알려 주며 막는다
        글 = [x for x in res.줄 if x[0] == '판례 검색 기록'][0][2]
        self.assertIn('LBOX 중지', 글)
        (폴더 / '작업' / '검색기록.md').write_text('# 검색기록\n\nLBOX 중지(2026. 11. 11.~): 하급심 검색어 "시험기기 징계"는 담당자에게 맡김\n',
                                              encoding='utf-8')
        res = fc.결과()
        with mock.patch.object(fc, 'RUN', lambda a: run(a, 0)):
            fc.검색_완결(res, 폴더)
        self.assertEqual(status(res, '판례 검색 기록'), '통과')
        self.assertIn('LBOX 중지 기간', [x for x in res.줄 if x[0] == '판례 검색 기록'][0][2])
        res = fc.결과()
        with mock.patch.object(fc._system, 'LBOX_중지', ''), mock.patch.object(fc, 'RUN', lambda a: run(a, 0)):
            fc.검색_완결(res, 폴더)
        self.assertEqual(status(res, '판례 검색 기록'), '막힘')


class BriefCaseOtherOutputTest(unittest.TestCase):
    """2026. 11. 7. `/하자보완`: 서면 사건의 서면이 아닌 인용 산출물(리서치·검토 메모·회신 메일)을 관문이 찾지 못해 판례 검사를 하나도 돌리지
    않았다(11. 6. 최문희 중노위 재심 가능성 검토). 대조표 이름의 `_{산출물}` 이나 머리 제목으로 산출물을 찾아 검토의견처럼 본다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / '4_서면작성' / '사건' / '홍길동_부당강등'
        self.작업 = self.case / '라운드1' / '작업'
        self.작업.mkdir(parents=True)
        (self.case / '라운드1' / '출력').mkdir()
        (self.case / '작업').mkdir()
        self.메모 = self.작업 / '재심_가능성_검토.md'
        self.메모.write_text('# 검토\n\n대법원 2022. 9. 29. 선고 2018다301527 판결은 취업규칙 해석을 다루었습니다.\n', encoding='utf-8')
        self.표 = self.작업 / '인용대조표.md'
        self.표.write_text('# 인용 대조표 — 재심_가능성_검토.md (2026. 11. 6.)\n\n| 번호 | 사건 표시 | 원문 문장 |\n|---|---|---|\n'
                          '| 1 | 대법원 2022. 9. 29. 선고 2018다301527 판결 | 가 |\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_target_memo_is_checked_with_its_table(self):
        with mock.patch.object(fc, 'RUN', lambda args: (0, 'ok')):
            [(표제, res)] = fc.돌리기(self.case, None, str(self.메모))
        이름들 = [n for n, _, _ in res.줄]
        self.assertNotIn('초안', 이름들)                              # 전에는 '초안이 없다'로 막혔다
        self.assertEqual(status(res, '판결 원문 대조'), '막힘')        # 열람 대조 기록(사안 비교)이 없다
        self.assertIn('문체(낙관 표현·적다)', 이름들)
        (self.작업 / '판결원문_열람대조.md').write_text(
            '## 사람 판정\n\n| 줄 | 판결 | 원문의 자리 | 판단 부분인지 | 방향 | 사안 비교 | 비고 |\n|---|---|---|---|---|---|---|\n'
            '| 1 | 2018다301527 | 판결요지 [2] | 판단 | 같음 |  | |\n', encoding='utf-8')
        with mock.patch.object(fc, 'RUN', lambda args: (0, 'ok')):
            [(_, res)] = fc.돌리기(self.case, None, str(self.메모))
        self.assertEqual(status(res, '판결 판단 부분·방향·사안 비교'), '막힘')   # 사실관계가 다른 판결을 가려내는 칸

    def test_night_check_finds_other_outputs_changed_in_range(self):
        끝 = time.time() - 3600
        with mock.patch.object(fc, 'RUN', lambda args: (0, 'ok')):
            out = fc.서면_다른_산출물들(self.case, 끝)
            self.assertEqual([t for t, _ in out], ['다른 산출물 재심_가능성_검토.md'])
            self.assertEqual(fc.서면_다른_산출물들(self.case, time.time() + 60), [])      # 범위 밖이면 보지 않는다

    def test_draft_tables_are_not_other_outputs_and_tail_name_finds_the_file(self):
        (self.case / '라운드1' / '출력' / '서면초안_림프종.md').write_text('본문\n', encoding='utf-8')
        (self.case / '작업' / '인용대조표_심사청구_림프종.md').write_text('# 인용 대조표 — 서면초안_림프종.md\n', encoding='utf-8')
        (self.작업 / '강변호사_회신메일_초안.md').write_text('대법원 2018다301527\n', encoding='utf-8')
        (self.작업 / '인용대조표_회신메일.md').write_text('# 인용 대조표 — 강 변호사님 회신 메일 초안(2026. 10. 27.)\n', encoding='utf-8')
        (self.작업 / '인용대조표_보강검색.md').write_text('# 인용 대조표 — 보강 검색(제조인지 건설인지)\n', encoding='utf-8')
        짝 = {표.name: (p.name if p else None) for 표, p, _ in fc.서면_다른_대조표(self.case)}
        self.assertNotIn('인용대조표_심사청구_림프종.md', 짝)              # 서면 초안의 대조표
        self.assertEqual(짝['인용대조표.md'], '재심_가능성_검토.md')        # 머리 제목
        self.assertEqual(짝['인용대조표_회신메일.md'], '강변호사_회신메일_초안.md')   # 이름 꼬리
        self.assertIsNone(짝['인용대조표_보강검색.md'])
        with mock.patch.object(fc, 'RUN', lambda args: (0, 'ok')):
            out = dict(fc.서면_다른_산출물들(self.case, time.time() - 3600))
        self.assertIn('인용대조표_보강검색.md', out['다른 산출물(찾지 못함)'].줄[0][2])       # 산출물을 찾지 못한 표는 참고로 알린다
        self.assertEqual(out['다른 산출물(찾지 못함)'].줄[0][1], '참고')

    def test_docx_is_chosen_over_its_newer_text_copy(self):
        """2026. 11. 10.: research_docx.py 가 docx 다음에 같은 이름의 글사본(md)을 써서 md 가 늘 더 새것이라, 가장 새것만 고르면
        `--대상 {docx}` 가 짝을 찾지 못해 막혔다(최문희 미팅 자료)."""
        docx = self.작업 / '(리서치) 홍길동 미팅 관련.docx'
        docx.write_bytes(b'')
        os.utime(docx, (time.time() - 60, time.time() - 60))
        (self.작업 / '(리서치) 홍길동 미팅 관련.md').write_text('서울2026부해645\n', encoding='utf-8')
        (self.작업 / '인용대조표_미팅자료.md').write_text('# 인용 대조표 — (리서치) 홍길동 미팅 관련.docx (2026. 11. 10.)\n', encoding='utf-8')
        짝 = {표.name: (p.name if p else None) for 표, p, _ in fc.서면_다른_대조표(self.case)}
        self.assertEqual(짝['인용대조표_미팅자료.md'], '(리서치) 홍길동 미팅 관련.docx')

    def test_brief_draft_target_still_goes_to_the_brief_check(self):
        초안 = self.case / '라운드1' / '출력' / '서면초안.md'
        초안.write_text('본문\n', encoding='utf-8')
        with mock.patch.object(fc, '서면', lambda *a, **k: '서면 검사') as _:
            self.assertEqual(fc.돌리기(self.case, None, str(초안)), [('', '서면 검사')])
        표없는 = self.작업 / '다른_메모.md'
        표없는.write_text('대법원 2018다301527 판결\n', encoding='utf-8')
        [(_, res)] = fc.돌리기(self.case, None, str(표없는))
        self.assertEqual(status(res, '판례 대조'), '막힘')                 # 가리키는 대조표가 없으면 막는다


class FinalCopyTest(unittest.TestCase):
    """2026. 11. 7. `/하자보완`: 의뢰인 송부판(`_최종`)의 확인(변경 추적·메모 없음, 작성자 '법무법인 평안', Word 로 내보낸 PDF)이 글로만 있었다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.docx = Path(self.tmp.name) / '(가나) 휴가 관련 검토_최종.docx'

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, 본문='<w:p><w:r><w:t>본문</w:t></w:r></w:p>', 메모='', 작성자='법무법인 평안', 수정자='법무법인 평안'):
        with zipfile.ZipFile(self.docx, 'w') as z:
            z.writestr('word/document.xml', f'<w:document><w:body>{본문}</w:body></w:document>')
            if 메모:
                z.writestr('word/comments.xml', f'<w:comments>{메모}</w:comments>')
            z.writestr('docProps/core.xml', f'<cp:coreProperties><dc:creator>{작성자}</dc:creator><cp:lastModifiedBy>{수정자}</cp:lastModifiedBy></cp:coreProperties>')

    def test_final_copy_is_clean_named_and_exported(self):
        self.make()
        self.assertEqual(fc.최종판_검사(self.docx)[0], '막힘')                       # PDF 가 없다
        self.docx.with_suffix('.pdf').write_bytes(b'%PDF')
        later(self.docx.with_suffix('.pdf'))
        self.assertEqual(fc.최종판_검사(self.docx), ('통과', f'{self.docx.name} 변경 추적·메모 없음, 작성자 법무법인 평안, PDF 있음'))
        self.make(본문='<w:ins w:author="최락보"><w:r><w:t>더함</w:t></w:r></w:ins>', 메모='<w:comment w:id="0"/>', 수정자='최락보 노무사')
        later(self.docx.with_suffix('.pdf'))
        상태, 말 = fc.최종판_검사(self.docx)
        self.assertEqual(상태, '막힘')
        for 낱말 in ('변경 추적 1곳', '메모 1개', "마지막으로 수정한 사람 '최락보 노무사'"):
            self.assertIn(낱말, 말)
        self.make(작성자='법무법인 평안 강민석 변호사')                               # 개인 이름을 붙인 작성자도 고친다
        later(self.docx.with_suffix('.pdf'))
        self.assertIn("작성자 '법무법인 평안 강민석 변호사'", fc.최종판_검사(self.docx)[1])


class OpinionGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / '1_검토의견' / '사건' / 'HPS_근로시간면제'
        self.case.mkdir(parents=True)
        make_pdf(self.case / 'HPS 단체협약.pdf', [글 + '제1조', 글 + '제2조'])
        self.docx = self.case / '(HPS) 근로시간면제 관련 검토_초안.docx'      # 원고(회신초안)로 만든 검토의견서. 관문은 docx 를 본다
        make_opinion_docx(self.docx, ['1. 검토 요지', '다툴 실익이 충분합니다. 단체협약에 적혀 있습니다.'])
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
        """보완 메모는 의뢰인에게 가는 글이 아니고, '목적은 바람직' 같은 말은 '적다'가 아니다(2026. 11. 2. 첫 밤 점검).
        메일 회신만 낸 사건이다(검토의견서 docx 가 있으면 관문은 docx 를 본다)."""
        self.docx.unlink()
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

    def 표_자리(self):
        """검토의견()이 판례 검사에 넘긴 (대상, 대조표) 이름."""
        본 = []
        with mock.patch.object(fc, '판례', lambda res, 대상, table, *a, **k: 본.append((대상.name, table.name))):
            res = fc.검토의견(self.case, 초안없음_허용=True)
        return res, 본

    def test_manuscript_named_after_case_is_an_output(self):
        """의뢰인 명의 의견서의 원고(`{사건}-의견서원고.md`)도 우리 산출물이다(2026. 11. 6. `/하자보완`: 11. 5. SR노조 제3자 의견서를
        밤 점검이 '검토의견서·회신초안이 없다'로 넘겨 판례 검사를 하나도 돌리지 않았다)."""
        for p in list(self.case.iterdir()):
            if p.suffix in ('.docx', '.md'):
                p.unlink()
        원고 = self.case / 'HPS_근로시간면제-의견서원고.md'
        원고.write_text('1. 의견\n\n비공개대상정보에 해당합니다.\n', encoding='utf-8')
        (self.case / '검색기록.md').write_text('검색 기록\n', encoding='utf-8')      # 사건 이름으로 시작하지 않는 md 는 산출물이 아니다
        later(self.case / '검색기록.md')
        res, 본 = self.표_자리()
        self.assertEqual(res.대상, 원고.name)
        self.assertEqual(본, [(원고.name, '인용대조표.md')])
        self.assertNotIn('산출물', [n for n, _, _ in res.줄])

    def test_other_manuscript_is_seen_at_night_with_its_own_table(self):
        """검토의견서·회신초안이 있으면 다른 원고(`-추가질의 회신초안.md`)가 더 새것이어도 기본 대상은 바뀌지 않는다(회신 둘이 대조표
        하나를 쓰는 옛 사건을 잘못 막지 않게). 밤 점검은 그날 고친 다른 원고를 그 이름의 대조표가 있으면 따로 보고, 없으면 참고로 적는다."""
        기본 = fc.검토의견(self.case).대상           # 다른 원고를 만들기 전의 기본 대상(검토의견서 docx)
        추가 = self.case / 'HPS_근로시간면제-추가질의 회신초안.md'
        추가.write_text('1. 추가 질의\n\n대법원 판결이 있습니다.\n', encoding='utf-8')
        os.utime(추가, (time.time() + 30, time.time() + 30))
        (self.case / '작업').mkdir(exist_ok=True)
        본 = []
        with mock.patch.object(fc, '판례', lambda res, 대상, table, *a, **k: 본.append((대상.name, table.name))):
            결과들 = fc.돌리기(self.case, 밤=True, 끝=time.time() - 60)
            self.assertEqual([표제 for 표제, _ in 결과들], [''])
            self.assertEqual(결과들[0][1].대상, 기본)
            self.assertEqual(status(결과들[0][1], '다른 원고'), '참고')
            self.assertIn('인용대조표_추가질의 회신초안.md', next(m for n, s, m in 결과들[0][1].줄 if n == '다른 원고'))
            (self.case / '작업' / '인용대조표_추가질의 회신초안.md').write_text('| 본문 문장 |\n', encoding='utf-8')
            본.clear()
            결과들 = fc.돌리기(self.case, 밤=True, 끝=time.time() - 60)
            self.assertEqual([표제 for 표제, _ in 결과들], ['', 추가.name])
            self.assertEqual(본, [(기본, '인용대조표.md'), (추가.name, '인용대조표_추가질의 회신초안.md')])
            self.assertNotIn('다른 원고', [n for n, _, _ in 결과들[0][1].줄])
            결과들 = fc.돌리기(self.case, 밤=True, 끝=time.time() + 3600)      # 범위 밖에 고친 원고는 보지 않는다
            self.assertEqual([표제 for 표제, _ in 결과들], [''])
            결과들 = fc.돌리기(self.case, 밤=False)                              # 사건 세션의 관문은 --대상 으로 고른다
            self.assertEqual(len(결과들), 1)

    def test_review_copy_with_tracked_changes_is_not_the_target(self):
        """같은 판의 검토용 변경 표시본은 고르지 않는다. 판 이름 'N차 수정안'의 N 으로 대조표를 나누지 않는다."""
        깨끗 = self.case / '(HPS) 근로시간면제 관련 검토_1차 수정안.docx'
        표시 = self.case / '(HPS) 근로시간면제 관련 검토_1차 수정안_검토용(변경분 표시).docx'
        깨끗.write_bytes(b'PK')
        표시.write_bytes(b'PK')
        os.utime(표시, (time.time() + 40, time.time() + 40))
        (self.case / '작업').mkdir(exist_ok=True)
        (self.case / '작업' / '인용대조표_1차.md').write_text('| 본문 문장 |\n', encoding='utf-8')
        res, 본 = self.표_자리()
        self.assertEqual(본, [(깨끗.name, '인용대조표.md')])

    def test_docx_is_the_target_even_if_the_manuscript_was_touched_later(self):
        """2026. 11. 10. `/하자보완`: 원고 md 는 검토의견서 docx 를 만든 글이고 메일 초안을 덧붙이느라 docx 뒤에 고쳐진다. 수정 시각으로
        md 를 고르면 빌드가 각주로 옮긴 문장을 md 본문에서 찾지 못해 막았다(11. 9. HPS TBM 일지 검토 각주 8·9, 10. 22. 이승민 휴직 검토 각주 4.
        사건 세션은 `--대상 docx` 로 막힘 0). docx 가 있으면 docx 를 보고, 같은 판의 `_최종` 사본이 더 새것이면 그것을 본다."""
        self.assertGreater(self.reply.stat().st_mtime, self.docx.stat().st_mtime)
        res, 본 = self.표_자리()
        self.assertEqual(res.대상, self.docx.name)
        self.assertEqual(본, [(self.docx.name, '인용대조표.md')])
        self.assertEqual(status(fc.검토의견(self.case), '문체(낙관 표현·적다)'), '막힘')     # 문체도 docx 의 글로 본다
        최종 = self.case / '(HPS) 근로시간면제 관련 검토_최종.docx'
        최종.write_bytes(self.docx.read_bytes())
        os.utime(최종, (time.time() + 20, time.time() + 20))
        self.assertEqual(self.표_자리()[0].대상, 최종.name)
        self.docx.unlink()
        최종.unlink()
        self.assertEqual(self.표_자리()[0].대상, self.reply.name)                          # 메일 회신만 낸 사건은 회신초안을 본다

    def test_two_opinion_documents_compare_revisions_only_within_a_document(self):
        """2026. 11. 10. `/하자보완`: 한 사건 폴더에 검토의견서가 둘이면 판 이름은 같은 문서 안에서만 견준다. 제이인츠바이오 해고 가능성 검토는
        10. 8. 문서의 `_7차 수정안` 이 10. 12. 에 만든 다른 문서의 `_1차 수정안` 보다 판 이름이 높아 대상이 되어 대조표(뒤 문서의 것)와
        51건 어긋났다. 검토의견서에 딸린 `_별지(…)` docx 는 더 새것이어도 대상이 아니다."""
        앞 = self.case / '(HPS) 타임오프 한도 관련 검토_7차 수정안.docx'
        앞.write_bytes(b'PK')
        os.utime(앞, (time.time() - 100, time.time() - 100))
        뒤 = self.case / '(HPS) 근로시간면제 관련 검토_1차 수정안.docx'
        뒤.write_bytes(b'PK')
        os.utime(뒤, (time.time() + 20, time.time() + 20))
        별지 = self.case / '(HPS) 근로시간면제 관련 검토_별지(직원 회신 문안).docx'
        별지.write_bytes(b'PK')
        os.utime(별지, (time.time() + 60, time.time() + 60))
        self.assertEqual(self.표_자리()[0].대상, 뒤.name)
        os.utime(앞, (time.time() + 90, time.time() + 90))                                # 앞 문서를 다시 고쳤으면 그 문서를 본다
        self.assertEqual(self.표_자리()[0].대상, 앞.name)

    def test_no_output_still_blocks_outside_night_check(self):
        for p in list(self.case.iterdir()):
            if p.suffix in ('.docx', '.md'):
                p.unlink()
        self.assertEqual(status(fc.검토의견(self.case), '산출물'), '막힘')
        self.assertEqual(status(fc.검토의견(self.case, 초안없음_허용=True), '산출물'), '해당 없음')


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

    def test_night_checks_each_round_changed_in_range(self):
        """새 라운드 폴더가 생긴 날 앞 라운드에서 고친 판도 본다(2026. 11. 5. `/하자보완`: GGM 라운드2 의 Rev_3 를 라운드3(초안 없음)만 보고 넘겼다).
        사건 전체를 보는 검사는 한 번만 센다."""
        with tempfile.TemporaryDirectory() as d:
            사건 = Path(d) / '4_서면작성' / '사건' / '가사건'
            for n in (1, 2, 3):
                (사건 / f'라운드{n}' / '출력').mkdir(parents=True)
                (사건 / f'라운드{n}' / '출력' / '서면초안.md').write_text('본문', encoding='utf-8')
            옛 = time.time() - 86400 * 3
            os.utime(사건 / '라운드1' / '출력' / '서면초안.md', (옛, 옛))
            불린 = []

            def 가짜(c, 라운드, 대상, 밤, 끝=None):
                불린.append(라운드)
                res = fc.결과()
                res.add('증거 파악(전 면 읽기)', '막힘', '호증 2건이 덜 되었다')
                res.add('문체', '막힘', f'라운드{라운드} 위반')
                return [('', res)]
            out = Path(d) / '관문.md'
            화면 = io.StringIO()
            with mock.patch.object(fc, '최근_사건', return_value=[사건]), mock.patch.object(fc, '돌리기', side_effect=가짜), redirect_stdout(화면):
                self.assertEqual(fc.main(['--최근', '24', '--out', str(out)]), 1)
            self.assertEqual(불린, [2, 3])                                        # 범위 밖인 라운드1 은 보지 않는다
            self.assertIn('| 증거 파악(전 면 읽기) | 1 |', 화면.getvalue())
            self.assertIn('| 문체 | 2 |', 화면.getvalue())
            글자 = out.read_text(encoding='utf-8')
            self.assertIn('## 가사건 · 라운드2 (서면) — 막힘 2', 글자)
            self.assertIn('## 가사건 · 라운드3 (서면) — 막힘 1', 글자)
            self.assertIn('앞 라운드의 줄과 같다', 글자)
            self.assertIn('사건 1건, 막힘 3건', 글자)
            for n in (2, 3):                                                     # 라운드 밖(증거관리/)만 바뀌었으면 마지막 라운드를 본다
                os.utime(사건 / f'라운드{n}' / '출력' / '서면초안.md', (옛, 옛))
            (사건 / '증거관리').mkdir()
            (사건 / '증거관리' / '우리호증목록.md').write_text('목록', encoding='utf-8')
            불린.clear()
            with mock.patch.object(fc, '최근_사건', return_value=[사건]), mock.patch.object(fc, '돌리기', side_effect=가짜), \
                    redirect_stdout(io.StringIO()):
                fc.main(['--최근', '24'])
            self.assertEqual(불린, [None])


if __name__ == '__main__':
    unittest.main()
