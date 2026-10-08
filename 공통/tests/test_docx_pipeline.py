"""서면 docx 파이프라인(docx_merge → docx_restyle → docx_footnotes → docx_normalize)을 확인한다.

프레임은 추적되는 4_서면작성/templates/표준양식.docx 를 임시 폴더에서 고쳐 만든다. 입증방법 항목은
실제 사건 프레임처럼 '(가)번호매기기_내용' 스타일로 바꾸고, 목차가 필요한 시험은 '다음' 아래에
'1.번호매기기' 대제목을 넣는다. 사건 자료나 OneDrive 폴더에는 아무것도 쓰지 않는다.
"""
import contextlib
import copy
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest import mock

import docx
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.text.paragraph import Paragraph
from lxml import etree
from PIL import Image

ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / '4_서면작성' / 'scripts'
TEMPLATE = ROOT / '4_서면작성' / 'templates' / '표준양식.docx'
sys.path.insert(0, str(SCRIPTS))
import docx_footnotes  # noqa: E402
import docx_merge  # noqa: E402
import docx_normalize  # noqa: E402
import docx_restyle  # noqa: E402

TOC = ('이 사건의 경위', '징계사유의 존재', '결론')
CP949 = dict(os.environ, PYTHONIOENCODING='cp949')
EVIDENCE = '\n입 증 방 법\n\n    을나 제1호증  징계위원회 회의록\n    을나 제2호증  회의록\n\n---\n① [확인 필요 사항]\n- 없음\n'


def make_frame(path, toc=(), title_style=None):
    """표준양식.docx 로 서면_프레임.docx 를 만든다. title_style 을 주면 본문 첫 서면명 제목의 스타일을 바꾼다."""
    d = docx.Document(str(TEMPLATE))
    paras = d.paragraphs
    i = next(i for i, p in enumerate(paras) if p.text.replace(' ', '') == '다음')
    cur = paras[i + 1]._p
    blank = copy.deepcopy(cur)
    for title in toc:
        head = copy.deepcopy(blank); cur.addnext(head); cur = head
        par = Paragraph(head, paras[0]._parent)
        par.style = d.styles['1.번호매기기']
        par.add_run(title)
        gap = copy.deepcopy(blank); cur.addnext(gap); cur = gap
    for p in d.paragraphs:
        if p.text.startswith('을나 제23호증'):
            p.style = d.styles['(가)번호매기기_내용']
            ppr = p._p.find(qn('w:pPr'))
            for el in ppr.findall(qn('w:numPr')) + ppr.findall(qn('w:ind')):
                ppr.remove(el)
        if title_style and p.style.name == '본문_대제목' and p.text.strip():
            p.style = d.styles[title_style]
    d.save(str(path))


def png(path, width, height, color):
    Image.new('RGB', (width, height), color).save(str(path))


def sha(data):
    return hashlib.sha1(data).hexdigest()


def rows(path):
    """본문 문단: (스타일, 글자, keepNext, keepLines, 그림 여부)"""
    out = []
    for p in docx.Document(str(path)).paragraphs:
        ppr = p._p.find(qn('w:pPr'))
        out.append((p.style.name, p.text,
                    ppr is not None and ppr.find(qn('w:keepNext')) is not None,
                    ppr is not None and ppr.find(qn('w:keepLines')) is not None,
                    p._p.find('.//' + qn('w:drawing')) is not None))
    return out


def captions_and_pictures(path):
    """[(캡션 글자, 바로 뒤 그림 문단들의 그림 sha1 목록)]"""
    d = docx.Document(str(path))
    ps = d.paragraphs
    found = []
    for i, p in enumerate(ps):
        if p.style.name != '표의첫행제목':
            continue
        pics = []
        for q in ps[i + 1:]:
            blip = q._p.find('.//' + qn('a:blip'))
            if blip is None:
                break
            pics.append(sha(d.part.related_parts[blip.get(qn('r:embed'))].blob))
        found.append((p.text, pics))
    return found


def run(func, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = func(*args, **kwargs)
    return result, buf.getvalue()


class CaseDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.round = Path(self.tmp.name) / '라운드1'
        self.outdir = self.round / '출력'
        self.excerpts = self.round / '발췌'
        self.outdir.mkdir(parents=True)
        self.excerpts.mkdir()
        self.frame = self.outdir / '서면_프레임.docx'
        self.md = self.outdir / '서면초안.md'
        self.out = self.outdir / '(테스트) 준비서면_초안.docx'

    def tearDown(self):
        self.tmp.cleanup()

    def merge(self, draft, toc=(), encoding='utf-8', title_style=None):
        make_frame(self.frame, toc, title_style)
        self.md.write_text(draft, encoding=encoding)
        return run(docx_merge.merge, str(self.frame), str(self.md), str(self.out))

    def leftovers(self):
        return sorted(p.name for p in self.outdir.iterdir() if p.name.startswith('.docx_merge_'))

    def backups(self):
        return sorted(p for p in self.outdir.iterdir() if '.bak_merge_' in p.name)


class HeadingTests(CaseDir):
    """대제목이 조용히 본문으로 떨어지지 않는다(프레임 목차와 다른 제목, 목차 없는 프레임, BOM)."""

    DRAFT = ('1. 이 사건의 경위\n\n가. 징계의 경위\n\n피고는 원고에게 정직 3월의 징계를 하였습니다(을나 제1호증).\n\n'
             '2. 징계사유는 존재합니다\n\n가. 판단 기준\n\n원고는 3년 이상 근무하였습니다.\n\n'
             '3. 결론\n\n원고의 청구는 기각되어야 합니다.\n' + EVIDENCE)
    MATCHING = DRAFT.replace('징계사유는 존재합니다', '징계사유의 존재')   # 프레임 목차(TOC)와 같은 항목명

    def heads(self):
        return [text for style, text, *_ in rows(self.out) if style == '1.번호매기기']

    def test_heading_that_differs_from_frame_toc_stays_a_heading(self):
        code, log = self.merge(self.DRAFT, toc=TOC)
        self.assertEqual(code, 1, log)          # 프레임 목차와 어긋나면 알리고 종료 코드 1
        self.assertEqual(self.heads(), ['이 사건의 경위', '징계사유는 존재합니다', '결론'])
        self.assertIn('프레임 목차에 없는 대제목', log)
        self.assertIn('초안에 없어 빠진 프레임 목차: 징계사유의 존재', log)
        self.assertIn('계층 스타일 비정합 0건', log)
        self.assertNotIn('2. 징계사유는 존재합니다', [text for _, text, *_ in rows(self.out)])

    def test_matching_toc_is_clean(self):
        code, log = self.merge(self.MATCHING.replace('징계사유의 존재', '징계사유의  존재'), toc=TOC)
        self.assertEqual(code, 0, log)          # 공백 차이는 같은 항목으로 본다
        self.assertEqual(self.heads(), list(TOC))
        self.assertNotIn('경고', log)

    def test_frame_without_toc_gets_numbered_headings(self):
        code, log = self.merge(self.DRAFT, toc=())
        self.assertEqual(code, 0, log)
        self.assertEqual(self.heads(), ['이 사건의 경위', '징계사유는 존재합니다', '결론'])
        subs = [text for style, text, *_ in rows(self.out) if style == '가.번호매기기']
        self.assertEqual(subs, ['징계의 경위', '판단 기준'])
        self.assertIn('프레임에 목차가 없어', log)

    def test_draft_saved_with_bom(self):
        code, log = self.merge(self.MATCHING, toc=TOC, encoding='utf-8-sig')
        self.assertEqual(code, 0, log)
        self.assertEqual(self.heads()[0], '이 사건의 경위')
        self.assertFalse(any('\ufeff' in text for _, text, *_ in rows(self.out)))

    def test_out_of_sequence_number_is_reported(self):
        draft = self.DRAFT.replace('2. 징계사유는 존재합니다', '5. 징계사유는 존재합니다')
        code, log = self.merge(draft, toc=TOC)
        self.assertEqual(code, 1, log)          # 병합 뒤 점검이 '대제목 누락 의심'으로 잡는다
        self.assertIn('본문으로 둔 줄: 5. 징계사유는 존재합니다', log)
        self.assertIn('대제목 누락 의심 1건', log)

    def test_title_in_evidence_title_style_before_daum(self):
        """서면명 제목에 별지제목을 쓰는 프레임에서도 restyle 범위가 '다음' 뒤 입증방법까지다."""
        code, log = self.merge(self.MATCHING, toc=TOC, title_style='별지제목')
        self.assertEqual(code, 0, log)
        self.assertNotIn('대상 문단 0건', log)
        self.assertEqual([s for s, text, *_ in rows(self.out) if text == '피고는 원고에게 정직 3월의 징계를 하였습니다(을나 제1호증).'],
                         ['가.번호매기기_내용'])

    def test_heading_candidate_rules(self):
        self.assertEqual(docx_restyle.h1_candidate('2. 징계사유는 존재합니다'), (2, '징계사유는 존재합니다'))
        self.assertEqual(docx_restyle.h1_candidate('\ufeff1. 이 사건의 경위'), (1, '이 사건의 경위'))
        self.assertEqual(docx_restyle.h1_candidate('3. 파면과 해임은 관련이 없습니다.'), (3, '파면과 해임은 관련이 없습니다.'))
        self.assertIsNone(docx_restyle.h1_candidate('2025. 3. 1. 참가인은 원고를 해고하였습니다.'))
        self.assertIsNone(docx_restyle.h1_candidate('1. 피고는 원고에게 10,000,000원을 지급하라.'))
        self.assertIsNone(docx_restyle.h1_candidate('2. 소송비용은 피고가 부담한다.'))


class RestyleCheckTests(CaseDir):
    """--check 가 구조 붕괴를 0건으로 넘기지 않는다."""

    def merged(self):
        draft = ('1. 이 사건의 경위\n\n피고는 원고를 징계하였습니다.\n\n[을나 제1호증 회의록]\n\n'
                 '2. 결론\n\n원고의 청구는 기각되어야 합니다.\n' + EVIDENCE)
        png(self.excerpts / '을나1.png', 600, 300, 'white')
        code, log = self.merge(draft, toc=('이 사건의 경위', '결론'))
        self.assertEqual(code, 0, log)
        return docx.Document(str(self.out))

    def check(self, d):
        d.save(str(self.out))
        return run(docx_restyle.main, str(self.out), check=True)

    def test_clean_merge_passes(self):
        code, log = self.check(self.merged())
        self.assertEqual(code, 0, log)

    def test_heading_left_as_body_is_flagged(self):
        d = self.merged()
        head = next(p for p in d.paragraphs if p.text == '결론')
        head.style = d.styles['1.번호매기기_내용']
        head.runs[0].text = '2. 결론'
        code, log = self.check(d)
        self.assertEqual(code, 1)
        self.assertIn('대제목 누락 의심 1건', log)

    def test_no_heading_at_all_is_flagged(self):
        d = self.merged()
        for p in d.paragraphs:
            if p.style.name == '1.번호매기기':
                p.style = d.styles['Normal']
        code, log = self.check(d)
        self.assertEqual(code, 1)
        self.assertIn("대제목('1.번호매기기') 문단이 하나도 없습니다", log)

    def test_caption_without_keep_next_is_flagged(self):
        d = self.merged()
        cap = next(p for p in d.paragraphs if p.style.name == '표의첫행제목')
        cap.paragraph_format.keep_with_next = None
        code, log = self.check(d)
        self.assertEqual(code, 1)
        self.assertIn('캡션 붙임(keepNext) 없음 1건', log)


class ExcerptImageTests(CaseDir):
    """발췌 그림 이름: 가지번호('의')와 같은 호증의 두 번째 발췌('-2')가 겹치지 않는다."""

    DRAFT = ('1. 이 사건의 경위\n\n첫 문단입니다.\n\n[을나 제2호증 회의록]\n\n두 번째 문단입니다.\n\n'
             '[을나 제2호증 회의록]\n\n세 번째 문단입니다.\n\n[을나 제2호증의 2 회의록]\n' + EVIDENCE)

    def files(self, **names):
        colors = iter(['red', 'green', 'blue', 'yellow', 'gray'])
        made = {}
        for name, size in names.items():
            path = self.excerpts / (name + '.png')
            png(path, size[0], size[1], next(colors))
            made[name] = sha(path.read_bytes())
        return made

    def test_branch_number_and_second_excerpt_get_their_own_images(self):
        made = self.files(**{'을나2': (600, 300), '을나2-2': (600, 700), '을나2의2': (600, 200)})
        code, log = self.merge(self.DRAFT)
        self.assertEqual(code, 0, log)
        got = captions_and_pictures(self.out)
        self.assertEqual(got[0], ('[을나 제2호증 회의록]', [made['을나2']]))
        self.assertEqual(got[1], ('[을나 제2호증 회의록]', [made['을나2-2']] * 2))   # 세로 14cm 초과 → 두 장 분할
        self.assertEqual(got[2], ('[을나 제2호증의 2 회의록]', [made['을나2의2']]))

    def test_old_name_that_could_be_either_stops(self):
        self.files(**{'을나2': (600, 300), '을나2-2': (600, 300)})
        with self.assertRaises(SystemExit) as cm:
            self.merge(self.DRAFT)
        self.assertIn('을나2의2.png', str(cm.exception.code))
        self.assertFalse(self.out.exists())
        self.assertEqual(self.leftovers(), [])

    def test_old_branch_name_is_read_when_unambiguous(self):
        made = self.files(**{'을나2': (600, 300), '을나2-2': (600, 200)})
        draft = self.DRAFT.replace('[을나 제2호증 회의록]\n\n세 번째', '세 번째')
        code, log = self.merge(draft)
        self.assertEqual(code, 0, log)
        self.assertIn('옛 이름', log)
        self.assertEqual(captions_and_pictures(self.out)[-1], ('[을나 제2호증의 2 회의록]', [made['을나2-2']]))

    def test_explicit_image_counts_toward_sequence(self):
        made = self.files(**{'갑4': (600, 300), '갑4-2': (600, 200)})
        draft = ('1. 이 사건의 경위\n\n첫 문단입니다.\n\n[갑 제4호증 회의록]\n![](갑4.png)\n\n'
                 '두 번째 문단입니다.\n\n[갑 제4호증 회의록]\n' + EVIDENCE)
        code, log = self.merge(draft)
        self.assertEqual(code, 0, log)
        self.assertEqual([pics for _, pics in captions_and_pictures(self.out)], [[made['갑4']], [made['갑4-2']]])

    def test_same_image_under_two_captions_stops(self):
        self.files(**{'갑4': (600, 300)})
        draft = ('1. 이 사건의 경위\n\n[갑 제4호증 회의록]\n![](갑4.png)\n\n문단입니다.\n\n'
                 '[갑 제5호증 확인서]\n![](갑4.png)\n' + EVIDENCE)
        with self.assertRaises(SystemExit) as cm:
            self.merge(draft)
        self.assertIn('두 캡션', str(cm.exception.code))
        self.assertFalse(self.out.exists())

    def test_caption_and_pictures_keep_together(self):
        self.files(**{'을나2': (600, 300), '을나2-2': (600, 700), '을나2의2': (600, 200)})
        code, log = self.merge(self.DRAFT)
        self.assertEqual(code, 0, log)
        table = rows(self.out)
        caps = [r for r in table if r[0] == '표의첫행제목']
        pics = [r for r in table if r[4]]
        self.assertEqual(len(caps), 3)
        self.assertEqual(len(pics), 4)
        self.assertTrue(all(r[2] and r[3] for r in caps + pics), table)


class SafetyTests(CaseDir):
    """보관본을 덮어쓰지 않고, 실패하면 기존 출력을 건드리지 않는다."""

    DRAFT = ('1. 이 사건의 경위\n\n피고는 원고를 징계하였습니다[[각주: 대법원 판결 설시.]].\n\n'
             '2. 결론\n\n원고의 청구는 기각되어야 합니다.\n' + EVIDENCE)

    def test_backup_in_same_second_does_not_overwrite(self):
        fixed = types.SimpleNamespace(datetime=types.SimpleNamespace(now=lambda: datetime(2026, 9, 23, 0, 43, 5)))
        with mock.patch.object(docx_merge, 'datetime', fixed):
            self.assertEqual(self.merge(self.DRAFT)[0], 0)
            d = docx.Document(str(self.out))
            d.add_paragraph('HUMAN EDIT MARKER')
            d.save(str(self.out))
            self.assertEqual(self.merge(self.DRAFT)[0], 0)
            self.assertEqual(self.merge(self.DRAFT)[0], 0)
        backups = self.backups()
        self.assertEqual([p.name for p in backups],
                         ['(테스트) 준비서면_초안.bak_merge_20260923_004305.docx',
                          '(테스트) 준비서면_초안.bak_merge_20260923_004305_2.docx'])
        self.assertIn('HUMAN EDIT MARKER', [p.text for p in docx.Document(str(backups[0])).paragraphs])

    def test_draft_without_evidence_section_changes_nothing(self):
        self.assertEqual(self.merge(self.DRAFT)[0], 0)
        before = self.out.read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.merge(self.DRAFT.replace('입 증 방 법', ''))
        self.assertIn("'입 증 방 법' 줄이 없습니다", str(cm.exception.code))
        self.assertEqual(self.out.read_bytes(), before)
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.leftovers(), [])

    def test_frame_without_evidence_title_stops(self):
        make_frame(self.frame)
        d = docx.Document(str(self.frame))
        for p in d.paragraphs:
            if p.style.name == '별지제목':
                p.style = d.styles['Normal']
        d.save(str(self.frame))
        self.md.write_text(self.DRAFT, encoding='utf-8')
        with self.assertRaises(SystemExit) as cm:
            run(docx_merge.merge, str(self.frame), str(self.md), str(self.out))
        self.assertIn('별지제목', str(cm.exception.code))
        self.assertFalse(self.out.exists())

    def test_failure_after_merge_keeps_previous_output(self):
        self.assertEqual(self.merge(self.DRAFT)[0], 0)
        before = self.out.read_bytes()
        with mock.patch.object(docx_merge.docx_footnotes, 'convert', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.merge(self.DRAFT)
        self.assertEqual(self.out.read_bytes(), before)
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.leftovers(), [])

    def test_clean_merge_reports_three_checks(self):
        code, log = self.merge(self.DRAFT)
        self.assertEqual(code, 0, log)
        self.assertIn('계층 스타일 비정합 0건', log)
        self.assertIn('남은 [[각주:]] 표시 0건 / 현재 각주 1개', log)
        self.assertIn('원문자 글꼴 비정합 0건', log)

    def test_folder_form_still_writes_old_name(self):
        make_frame(self.frame)
        self.md.write_text(self.DRAFT, encoding='utf-8')
        # 한국어 Windows 의 파이프 출력(cp949)에서도 UTF-8 로 내보내는지 함께 본다
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'docx_merge.py'), str(self.outdir)],
                                capture_output=True, text=True, encoding='utf-8', env=CP949)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.outdir / '최종서면.docx').exists())
        self.assertIn('호환용', result.stdout)


class DraftBoundaryTests(CaseDir):
    """본문과 하단 목록의 경계('---' 대시 3개 이상)와 병합 전 점검."""

    BODY = '1. 이 사건의 경위\n\n피고는 원고를 징계하였습니다.\n\n2. 결론\n\n원고의 청구는 기각되어야 합니다.\n'
    BOTTOM = ('① [확인 필요 사항]\n- 없음\n② ⚠️ [취약 논리 및 보완 방향]\n- 징계양정 비교 사례 부족\n'
              '※ 본 서면 초안은 AI 보조 작성물로, 최종 검토 및 법적 판단은 담당 변호사·노무사의 확인이 필요합니다.\n')
    EV = '\n입 증 방 법\n\n    을나 제1호증  징계위원회 회의록\n'

    def texts(self):
        return [text for _, text, *_ in rows(self.out)]

    def test_long_rule_line_ends_body(self):
        code, log = self.merge(self.BODY + self.EV + '\n-----\n' + self.BOTTOM)
        self.assertEqual(code, 0, log)
        joined = '\n'.join(self.texts())
        self.assertNotIn('확인 필요 사항', joined)
        self.assertNotIn('AI 보조 작성물', joined)
        self.assertNotIn('-----', joined)

    def test_bottom_lists_without_rule_line_stop(self):
        with self.assertRaises(SystemExit) as cm:
            self.merge(self.BODY + self.EV + '\n' + self.BOTTOM)
        self.assertIn("'---' 한 줄", str(cm.exception.code))
        self.assertFalse(self.out.exists())

    def test_rule_line_matches_style_check(self):
        import style_check
        rule = getattr(style_check, 'RULE_LINE', None)
        if rule is None:
            self.skipTest('style_check.RULE_LINE 없음')
        for line in ('---', '-----', '  ---  ', '--', '- 목록', '|---|---|'):
            self.assertEqual(bool(docx_merge.RULE_LINE.match(line)), bool(rule.match(line)), line)

    def test_markdown_table_stops(self):
        table = '\n| 연도 | 처분 |\n|---|---|\n| 2021 | 정직 3월 |\n'
        with self.assertRaises(SystemExit) as cm:
            self.merge(self.BODY + table + self.EV)
        self.assertIn('md 표', str(cm.exception.code))
        self.assertFalse(self.out.exists())

    def test_unbalanced_footnote_marker_stops(self):
        body = self.BODY.replace('징계하였습니다.', '징계하였습니다[[각주: 근속기간은 갑 제1호증 참조).].')
        with self.assertRaises(SystemExit) as cm:
            self.merge(body + self.EV)
        self.assertIn("'[[각주:' 와 ']]' 짝", str(cm.exception.code))
        self.assertFalse(self.out.exists())


def visible(p):
    """문단 글자(탭 '\\t', 줄바꿈 '\\n' 포함). 스크립트의 함수를 쓰지 않고 따로 센다."""
    out = []
    for el in p._p.iter(qn('w:t'), qn('w:tab'), qn('w:br')):
        if el.getparent().tag != qn('w:r'):
            continue
        if el.tag == qn('w:t'):
            out.append(el.text or '')
        else:
            out.append('\t' if el.tag == qn('w:tab') else '\n')
    return ''.join(out)


class FootnoteTests(unittest.TestCase):
    """각주 변환은 표시 글자만 떼어 내고 탭·줄바꿈·변경 추적 문구를 제자리에 둔다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / '수정안.docx'

    def tearDown(self):
        self.tmp.cleanup()

    def notes(self):
        return run(docx_footnotes.convert, str(self.path), list_only=True)[1]

    def test_tab_break_and_tracked_insert_are_kept(self):
        d = docx.Document()
        p = d.add_paragraph()
        p.add_run('가. 원고는\t피고 회사의 근로자입니다')
        p.add_run('(갑 제1호증).')
        p.add_run().add_break()
        p.add_run('대법원 2019도10516 판결[[각주: 판결 원문 설시.]]은 이를 밝혔습니다.')
        q = d.add_paragraph()
        q._p.append(parse_xml('<w:r %s><w:tab/><w:t>들여쓴 문장[[각주: 각주 A.]]입니다.</w:t></w:r>' % nsdecls('w')))
        q._p.append(parse_xml('<w:ins %s w:id="1" w:author="변호사" w:date="2026-09-20T00:00:00Z">'
                              '<w:r><w:t>(변호사 추가 문장)</w:t></w:r></w:ins>' % nsdecls('w')))
        q._p.append(parse_xml('<w:r %s><w:t xml:space="preserve"> 끝.</w:t></w:r>' % nsdecls('w')))
        d.save(str(self.path))
        code, log = run(docx_footnotes.convert, str(self.path))
        self.assertEqual(code, 0, log)
        a, b = docx.Document(str(self.path)).paragraphs[:2]
        self.assertEqual(visible(a), '가. 원고는\t피고 회사의 근로자입니다(갑 제1호증).\n대법원 2019도10516 판결은 이를 밝혔습니다.')
        self.assertEqual(visible(b), '\t들여쓴 문장입니다.(변호사 추가 문장) 끝.')
        ins = b._p.find(qn('w:ins'))
        self.assertEqual(''.join(t.text for t in ins.iter(qn('w:t'))), '(변호사 추가 문장)')
        # 각주번호는 표시가 있던 자리(어구 바로 뒤)에 들어간다
        kids = [k for k in a._p if k.tag == qn('w:r')]
        ref = next(i for i, k in enumerate(kids) if k.find(qn('w:footnoteReference')) is not None)
        self.assertTrue(''.join(t.text for t in kids[ref - 1].iter(qn('w:t'))).endswith('판결'))
        self.assertIn('[1] 판결 원문 설시.', self.notes())
        self.assertIn('[2] 각주 A.', self.notes())

    def test_marker_split_across_runs(self):
        d = docx.Document()
        p = d.add_paragraph()
        p.add_run('판결[[각')
        p.add_run('주: 설시').bold = True
        p.add_run(' 내용.]]은 ')
        p.add_run('그러합니다.')
        d.save(str(self.path))
        self.assertEqual(run(docx_footnotes.convert, str(self.path))[0], 0)
        self.assertEqual(visible(docx.Document(str(self.path)).paragraphs[0]), '판결은 그러합니다.')
        self.assertIn('[1] 설시 내용.', self.notes())

    def test_broken_marker_is_counted_and_not_swallowed(self):
        d = docx.Document()
        d.add_paragraph('원고는 3년 이상 근무하였습니다[[각주: 근속기간은 갑 제1호증 참조).]. '
                        '또한 피고는[[각주: 정상 표시.]] 다투지 않았습니다.')
        d.save(str(self.path))
        code, log = run(docx_footnotes.convert, str(self.path), check_only=True)
        self.assertEqual(code, 1)
        self.assertIn('남은 [[각주:]] 표시 2건', log)
        self.assertIn("맞지 않는 표시 1건", log)
        code, log = run(docx_footnotes.convert, str(self.path))
        self.assertEqual(code, 1, log)          # 잘못 닫은 표시가 남았다고 알린다
        text = visible(docx.Document(str(self.path)).paragraphs[0])
        self.assertEqual(text, '원고는 3년 이상 근무하였습니다[[각주: 근속기간은 갑 제1호증 참조).]. 또한 피고는 다투지 않았습니다.')
        self.assertIn('[1] 정상 표시.', self.notes())
        code, log = run(docx_footnotes.convert, str(self.path), check_only=True)
        self.assertEqual(code, 1)
        self.assertIn('남은 [[각주:]] 표시 1건', log)


def rfonts(**attrs):
    """w:rFonts 요소. rfonts(hAnsi='바탕체', hint='eastAsia')"""
    return '<w:rFonts %s/>' % ' '.join('w:%s="%s"' % kv for kv in attrs.items())


def rstyle(style_id):
    return '<w:rStyle w:val="%s"/>' % style_id


def font_style(d, name, kind, fonts=None, based=None):
    """글꼴만 지정한 스타일을 만들고 스타일 ID 를 돌려준다. based 를 주지 않으면 기반 스타일이 없다."""
    el = d.styles.add_style(name, kind).element
    if based:
        el.find(qn('w:name')).addnext(parse_xml('<w:basedOn %s w:val="%s"/>' % (nsdecls('w'), based)))
    if fonts:
        el.append(parse_xml('<w:rPr %s>%s</w:rPr>' % (nsdecls('w'), fonts)))
    return el.get(qn('w:styleId'))


def circled(d, text='①', rpr=None, style=None, mark=None, cell=None):
    """원문자가 든 run 하나짜리 문단을 붙이고 (문단, run) 을 돌려준다. rpr·mark 는 run·문단표식의 w:rPr 안쪽 XML,
    style 은 문단 스타일 ID 이고, cell 을 주면 그 표 칸의 첫 문단에 넣는다."""
    p = cell.paragraphs[0] if cell is not None else d.add_paragraph()
    ppr = p._p.get_or_add_pPr()
    if style:
        ppr.insert(0, parse_xml('<w:pStyle %s w:val="%s"/>' % (nsdecls('w'), style)))
    if mark:
        ppr.append(parse_xml('<w:rPr %s>%s</w:rPr>' % (nsdecls('w'), mark)))
    r = p.add_run(text)
    if rpr:
        r._r.insert(0, parse_xml('<w:rPr %s>%s</w:rPr>' % (nsdecls('w'), rpr)))
    return p, r


XMLNS = (nsdecls('w') + ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
         ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
         ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
         ' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
         ' xmlns:v="urn:schemas-microsoft-com:vml"')
# Word 는 글상자를 새 형식(mc:Choice)으로 적고 옛 형식 사본(mc:Fallback)을 한 번 더 적는다
NEW_BOX = ('<w:drawing><wp:inline><wp:extent cx="3600000" cy="432000"/><wp:docPr id="1" name="TextBox 1"/><a:graphic>'
           '<a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><wps:wsp>'
           '<wps:cNvSpPr txBox="1"/><wps:spPr/><wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx><wps:bodyPr/>'
           '</wps:wsp></a:graphicData></a:graphic></wp:inline></w:drawing>')
OLD_BOX = ('<w:pict><v:rect style="width:283.5pt;height:34pt"><v:textbox><w:txbxContent>%s</w:txbxContent></v:textbox>'
           '</v:rect></w:pict>')


def wx(xml):
    """XML 조각 하나를 요소로 만든다(글상자에 쓰는 네임스페이스까지 선언한다)."""
    return parse_xml('<w:body %s>%s</w:body>' % (XMLNS, xml))[0]


def wr(text, rpr=''):
    """run 의 XML. rpr 은 w:rPr 안쪽 XML 이다."""
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % ('<w:rPr>%s</w:rPr>' % rpr if rpr else '', text)


def put(d, where, inner, style=None):
    """where 자리에 문단을 하나 만들어 inner(문단 안쪽 XML)를 넣는다. style 은 문단 스타일 ID 이다."""
    para = '<w:p>%s%s</w:p>' % ('<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % style if style else '', inner)
    if where in ('각주', '미주'):
        tag, reltype = ('footnote', RT.FOOTNOTES) if where == '각주' else ('endnote', RT.ENDNOTES)
        part = next(rel.target_part for rel in d.part.rels.values() if rel.reltype == reltype)
        root = etree.fromstring(part.blob)                 # docx_footnotes.py 처럼 blob 을 읽어 고치고 다시 쓴다
        number = max(int(note.get(qn('w:id'))) for note in root) + 1
        root.append(etree.fromstring('<w:%s %s w:id="%d">%s</w:%s>' % (tag, XMLNS, number, para, tag)))
        part._blob = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        d.add_paragraph()._p.append(wx('<w:r><w:%sReference w:id="%d"/></w:r>' % (tag, number)))
        return
    if where == '글상자':
        para = ('<w:p><w:r><mc:AlternateContent><mc:Choice Requires="wps">%s</mc:Choice><mc:Fallback>%s</mc:Fallback>'
                '</mc:AlternateContent></w:r></w:p>' % (NEW_BOX % para, OLD_BOX % para))
    elif where == '옛 글상자':
        para = '<w:p><w:r>%s</w:r></w:p>' % (OLD_BOX % para)
    elif where == '누름틀 문단':
        para = '<w:sdt><w:sdtPr/><w:sdtContent>%s</w:sdtContent></w:sdt>' % para
    new, section = wx(para), d.sections[0]
    if where == '머리글':
        section.header.is_linked_to_previous = False
        section.header._element.append(new)
    elif where == '바닥글':
        section.footer._element.append(new)
    elif where in ('표 칸', '표 안의 표', '병합한 칸'):
        table = d.add_table(2, 2)
        cell = (table.cell(0, 0).merge(table.cell(0, 1)) if where == '병합한 칸' else
                table.cell(0, 0).add_table(1, 1).cell(0, 0) if where == '표 안의 표' else table.cell(0, 0))
        cell.paragraphs[0]._p.addprevious(new)
    else:
        d.element.body.find(qn('w:sectPr')).addprevious(new)


def parts_xml(path):
    """[(파트 이름, 루트 요소)] — 본문·각주·미주·머리글·바닥글. 스크립트의 함수를 쓰지 않고 zip 에서 직접 읽는다."""
    with zipfile.ZipFile(str(path)) as archive:
        return [(name, etree.fromstring(archive.read(name))) for name in sorted(archive.namelist())
                if name.startswith('word/') and name.count('/') == 1
                and name[5:].startswith(('document', 'footnotes', 'endnotes', 'header', 'footer'))]


def all_text(path):
    """{파트 이름: 글자}. 지운 글(w:delText)도 넣는다."""
    return {name: ''.join(t.text or '' for t in root.iter(qn('w:t'), qn('w:delText'))) for name, root in parts_xml(path)}


def circled_runs(path):
    """원문자가 든 run 을 [(문단 글자, 감싼 요소 이름들, w:rFonts 속성)] 으로 읽는다."""
    found = []
    for _, root in parts_xml(path):
        for r in root.iter(qn('w:r')):
            text = ''.join(t.text or '' for t in r if t.tag in (qn('w:t'), qn('w:delText')))
            if not any('①' <= ch <= '⑳' for ch in text):
                continue
            p = next(r.iterancestors(qn('w:p')))
            fonts = r.find('%s/%s' % (qn('w:rPr'), qn('w:rFonts')))
            found.append((''.join(t.text or '' for t in p.iter(qn('w:t'), qn('w:delText'))),
                          [etree.QName(a).localname for a in r.iterancestors()],
                          {etree.QName(k).localname: v for k, v in fonts.attrib.items()} if fonts is not None else {}))
    return found


class NormalizeTests(unittest.TestCase):
    """원문자 글꼴은 run 에 적힌 속성이 아니라 Word 가 실제로 찍는 글꼴로 판정한다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / '수정안.docx'

    def tearDown(self):
        self.tmp.cleanup()

    def test_font_inherited_from_style_is_not_counted(self):
        # Word 는 저장할 때 스타일과 같은 값인 w:eastAsia 를 run 에서 지운다. 2026. 10. 7. 담당자가 그림 크기만 고쳐
        # 저장한 답변서에서 11건이 비정합으로 잡혔지만, Word 로 낸 PDF 에서는 모두 바탕체로 찍혀 있었다.
        B = '바탕체'
        d = docx.Document()
        normal = d.styles['Normal']                    # 프레임처럼 ascii·hAnsi=Times New Roman, eastAsia=바탕체
        normal.font.name = 'Times New Roman'
        normal.element.rPr.rFonts.set(qn('w:eastAsia'), B)
        outer = font_style(d, '1.번호매기기_내용', WD_STYLE_TYPE.PARAGRAPH, based=normal.style_id)
        inner = font_style(d, '(1)번호매기기_내용', WD_STYLE_TYPE.PARAGRAPH, based=outer)
        circled(d, '①', rfonts(ascii=B, hAnsi=B, eastAsia=B, cs=B, hint='eastAsia'))               # (a) run 에 직접 있다
        circled(d, '②', rfonts(ascii=B, hAnsi=B, cs=B, hint='eastAsia'), style=inner)              # (b) Word 가 지웠다
        d.save(str(self.path))
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), (B, 0))
        circled(d, '③', rfonts(ascii=B, hAnsi=B, eastAsia='맑은 고딕', cs=B, hint='eastAsia'))      # (c) 다른 글꼴
        d.save(str(self.path))
        before = self.path.read_bytes()
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'docx_normalize.py'), str(self.path), '--check'],
                                capture_output=True, text=True, encoding='utf-8', env=CP949)
        self.assertEqual(result.returncode, 1)
        self.assertIn('본문 한글 글꼴: 바탕체 / 원문자 run 비정합 1건', result.stdout)
        self.assertEqual(self.path.read_bytes(), before)
        # 정리 모드도 (c) 만 고친다. 상속으로 맞는 (b) 에 eastAsia 를 다시 써 넣지 않는다
        self.assertEqual(docx_normalize.normalize(str(self.path)), (B, 1))
        east = [p.runs[0]._r.find(qn('w:rPr')).find(qn('w:rFonts')).get(qn('w:eastAsia'))
                for p in docx.Document(str(self.path)).paragraphs]
        self.assertEqual(east, [B, None, B])
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), (B, 0))

    def test_judgment_follows_the_font_word_prints(self):
        """2026. 10. 8. 표준양식에 아래 변형을 넣어 Word 16 으로 PDF 를 내보내고 원문자가 찍힌 글꼴을 읽었다.
        정상으로 보는 run 은 Word 가 바탕체로 찍은 것뿐이어야 한다. ⑯~⑳ 은 바탕체에 글리프가 없어 쓰지 않았다."""
        B, M, D, CM = '바탕체', '맑은 고딕', '돋움체', 'Cambria Math'
        P, C = WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER
        d = docx.Document(str(TEMPLATE))      # Normal: ascii·hAnsi=Times New Roman, eastAsia=바탕체. docDefaults: 테마 글꼴
        ids = {name: d.styles[name].style_id for name in
               ('Normal', 'Heading 1', '1.번호매기기', '본문_중제목 Char', '1.번호매기기_내용 Char')}
        hint, all_b = rfonts(hint='eastAsia'), dict(ascii=B, hAnsi=B, eastAsia=B, cs=B)
        p_b = font_style(d, 'P_B', P, based=font_style(d, 'P_A', P, rfonts(eastAsia=D), based=ids['Normal']))
        p_bbb = font_style(d, 'P_BBB', P, rfonts(ascii=B, hAnsi=B, eastAsia=B))
        p_mmm = font_style(d, 'P_MMM', P, rfonts(ascii=M, hAnsi=M, eastAsia=M))
        p_empty = font_style(d, 'P_EMPTY', P)
        p_hint = font_style(d, 'P_HINT', P, hint, based=ids['Normal'])
        c_b = font_style(d, 'C_B', C, based=font_style(d, 'C_A', C, rfonts(eastAsia=D)))
        c_hint = font_style(d, 'C_HINT', C, hint)
        table = d.add_table(rows=1, cols=1)
        table._tbl.tblPr.insert(0, parse_xml('<w:tblStyle %s w:val="%s"/>' % (
            nsdecls('w'), font_style(d, 'T_D', WD_STYLE_TYPE.TABLE, rfonts(eastAsia=D)))))
        cases = [   # (Word 가 찍은 글꼴, 정상으로 보는가, circled() 인자)
            # run 에 hint 가 있다 → eastAsia 글꼴로 찍힌다
            ('BatangChe', True, dict(rpr=rfonts(hint='eastAsia', **all_b))),
            ('BatangChe', True, dict(rpr=rfonts(ascii=B, hAnsi=B, cs=B, hint='eastAsia'))),      # Word 가 eastAsia 를 지운 run
            ('BatangChe', True, dict(rpr=hint)),
            ('BatangChe', True, dict(rpr=hint, text='① 원고는 abc')),
            ('BatangChe', True, dict(rpr=rfonts(ascii=M, hAnsi=M, hint='eastAsia'))),
            ('BatangChe', True, dict(rpr=rfonts(ascii=CM, hAnsi=CM, cs=CM, hint='eastAsia'))),
            ('MalgunGothic', False, dict(rpr=rfonts(ascii=B, hAnsi=B, eastAsia=M, cs=B, hint='eastAsia'))),
            ('H2gtrE', False, dict(rpr=hint, style=ids['1.번호매기기'])),                        # 문단 스타일이 HY견고딕
            ('DotumChe', False, dict(rpr=hint, style=p_b)),                                      # basedOn 사슬 위의 돋움체
            ('DotumChe', False, dict(rpr=rstyle(ids['본문_중제목 Char']) + hint)),               # 문자 스타일이 돋움체
            ('DotumChe', False, dict(rpr=rstyle(c_b) + hint)),
            ('MalgunGothic', False, dict(rpr=rfonts(eastAsia=B, eastAsiaTheme='minorEastAsia', hint='eastAsia'))),
            ('MalgunGothic', False, dict(rpr=hint, style=ids['Heading 1'])),                     # 스타일의 테마 글꼴
            ('BatangChe', True, dict(rpr=rfonts(eastAsia=B, hint='eastAsia'), style=ids['Heading 1'])),
            ('BatangChe', True, dict(rpr=rstyle(ids['1.번호매기기_내용 Char']) + hint, style=ids['Heading 1'])),
            ('MalgunGothic', False, dict(rpr=hint, style=p_empty)),                              # docDefaults 의 테마 글꼴
            ('BatangChe', True, dict(rpr=hint, style='NoSuchStyle')),                            # 없는 스타일 → 기본 문단 스타일
            ('BatangChe', True, dict(rpr=hint, cell=table.cell(0, 0))),                          # 표 스타일(돋움체)은 Normal 을 못 덮는다
            # run 에 hint 가 없다 → hAnsi 글꼴로 찍힌다(Times New Roman 에는 원문자가 없어 Cambria Math 가 된다)
            ('CambriaMath', False, dict()),
            ('CambriaMath', False, dict(text='① 원고는 abc')),
            ('CambriaMath', False, dict(rpr=rfonts(ascii=CM, hAnsi=CM, cs=CM))),                 # Word 가 대신 쓴 글꼴을 적어 둔 run
            ('BatangChe', True, dict(rpr=rfonts(hAnsi=B))),
            ('CambriaMath', False, dict(rpr=rfonts(ascii=B))),
            ('BatangChe', True, dict(rpr=rfonts(ascii=M, hAnsi=B))),
            ('MalgunGothic', False, dict(rpr=rfonts(ascii=B, hAnsi=M))),
            ('MalgunGothic', False, dict(rpr=rfonts(ascii=B, hAnsi=B, hAnsiTheme='minorHAnsi'))),
            ('BatangChe', True, dict(rpr=rfonts(**all_b))),
            ('BatangChe', True, dict(style=p_bbb)),
            ('MalgunGothic', False, dict(style=p_mmm)),
            ('CambriaMath', False, dict(rpr=rfonts(hint='default'))),
            ('CambriaMath', False, dict(mark=rfonts(hint='eastAsia', **all_b))),                 # 문단표식의 글꼴은 run 에 미치지 않는다
            ('CambriaMath', False, dict(rpr=rstyle(c_hint))),                                    # 문자 스타일의 hint 는 통하지 않는다
            # Word 는 바탕체로 찍지만 비정합으로 본다(엄격한 쪽)
            ('BatangChe', False, dict(rpr=rfonts(ascii=B, hAnsi=B, eastAsia=M))),                # hint 가 붙으면 맑은 고딕이 된다
            ('BatangChe', False, dict(style=p_hint)),                                            # 문단 스타일에만 있는 hint
        ]
        font, index = docx_normalize.body_font(d), docx_normalize.style_index(d)
        for i, (printed, ok, how) in enumerate(cases, 1):
            p, r = circled(d, **how)
            with self.subTest(case=i, printed=printed, **how):
                self.assertEqual(docx_normalize.run_ok(r, p, font, index), ok)
                self.assertTrue(printed == 'BatangChe' or not ok)
        bad = sum(not ok for _, ok, _ in cases)
        d.save(str(self.path))
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), (B, bad))
        self.assertEqual(docx_normalize.normalize(str(self.path)), (B, bad))
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), (B, 0))

    def test_tabs_and_breaks_are_not_copied(self):
        d = docx.Document()
        d.add_paragraph().add_run('① 원고는\t피고의 근로자이고, ② 피고는\n원고를 해고하였습니다.')
        d.save(str(self.path))
        font, bad = docx_normalize.normalize(str(self.path))
        self.assertEqual(bad, 1)
        p = docx.Document(str(self.path)).paragraphs[0]
        self.assertEqual(visible(p), '① 원고는\t피고의 근로자이고, ② 피고는\n원고를 해고하였습니다.')
        self.assertEqual(len(p._p.findall('.//' + qn('w:tab'))), 1)
        self.assertEqual(len(p._p.findall('.//' + qn('w:br'))), 1)
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), (font, 0))

    def test_words_option_points_to_style_check(self):
        d = docx.Document()
        d.add_paragraph('① 원고는 한자(漢字)를 병기하였습니다.')
        d.save(str(self.path))
        before = self.path.read_bytes()
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'docx_normalize.py'), str(self.path), '--words'],
                                capture_output=True, text=True, encoding='utf-8', env=CP949)
        self.assertEqual(result.returncode, 2)
        self.assertIn('금지 낱말 검사는 style_check.py', result.stdout)
        self.assertEqual(self.path.read_bytes(), before)

    def test_every_place_is_judged_like_a_run_in_the_body(self):
        """2026. 10. 8. 표준양식에 아래 자리마다 다섯 변형을 넣어 Word 16 으로 PDF 를 내보내고 원문자가 찍힌 글꼴을 읽었다.
        목차 문단을 뺀 어느 자리에서나 본문 문단 바로 아래의 run 과 같은 글꼴로 찍혔고, 글상자의 옛 형식 사본(mc:Fallback)은
        찍히지 않았다. 정리한 뒤에는 모든 자리에서 바탕체로 찍혔다. 예전 점검은 본문 문단과 최상위 표 칸의 직계 run 만 보았고,
        병합한 칸은 여러 번 돌아 두 번씩 세었다(GGM 소장 청구원인의 표 안 목차 하이퍼링크 ①②③, 현수막 사건 서면의 각주 ①~④)."""
        B, CM = '바탕체', 'Cambria Math'
        SIGN = dict(ascii=B, hAnsi=B, eastAsia=B, cs=B, hint='eastAsia')
        plain = [   # (Word 가 찍은 글꼴, 정상으로 보는가, run 의 w:rFonts 속성)
            ('CambriaMath', False, {}),
            ('BatangChe', True, dict(hint='eastAsia')),
            ('CambriaMath', False, dict(ascii=CM, hAnsi=CM, cs=CM)),               # Word 가 대신 쓴 글꼴을 적어 둔 run
            ('BatangChe', True, SIGN),
            ('BatangChe', True, dict(hAnsi=B)),
        ]
        # 목차 문단('toc 1')은 스타일이 테마 글꼴(맑은 고딕)이다. 끝 변형은 바탕체로 찍히지만 엄격한 쪽으로 본다
        toc = [('MalgunGothic', False), ('MalgunGothic', False), ('CambriaMath', False), ('BatangChe', True),
               ('BatangChe', False)]
        for printed, ok, *_ in plain + toc:
            self.assertTrue(printed == 'BatangChe' or not ok)
        d = docx.Document(str(TEMPLATE))
        ids = {s.find(qn('w:name')).get(qn('w:val')): s.get(qn('w:styleId')) for s in d.styles.element.findall(qn('w:style'))}
        link = '<w:hyperlink w:anchor="_Toc1" w:history="1">%s</w:hyperlink>'
        wraps = {   # 문단 안에서 run 을 감싸는 요소: (틀, run 의 w:rPr 앞머리)
            '하이퍼링크': (link, ''),
            '하이퍼링크(문자 스타일)': (link, rstyle(ids['Hyperlink'])),
            '삽입 표시': ('<w:ins w:id="901" w:author="변호사" w:date="2026-10-08T00:00:00Z">%s</w:ins>', ''),
            '누름틀': ('<w:sdt><w:sdtPr/><w:sdtContent>%s</w:sdtContent></w:sdt>', ''),
            '스마트 태그': ('<w:smartTag w:uri="urn:schemas-microsoft-com:office:smarttags" w:element="place">%s</w:smartTag>', ''),
            '필드': ('<w:fldSimple w:instr=" QUOTE x ">%s</w:fldSimple>', ''),
        }
        homes = ('본문', '표 칸', '표 안의 표', '병합한 칸', '누름틀 문단', '글상자', '옛 글상자', '각주', '미주', '머리글', '바닥글')
        styles = {'각주': ids['footnote text'], '머리글': ids['header'], '바닥글': ids['footer']}
        cases = []      # (표지, 자리, 문단이 놓인 곳, 정상으로 보는가, w:rFonts 속성)

        def add(where, home, ok, fonts, frame='%s', head='', style=None):
            label = 'K%02d ' % len(cases)
            put(d, home, wr(label) + frame % wr('①', head + (rfonts(**fonts) if fonts else '')), style or styles.get(home))
            cases.append((label, where, home, ok, fonts))

        for home in homes:
            for _, ok, fonts in plain:
                add(home, home, ok, fonts)
        for where, (frame, head) in wraps.items():
            for _, ok, fonts in plain:
                add(where, '본문', ok, fonts, frame, head)
        for (_, ok), (_, _, fonts) in zip(toc, plain):
            add('목차 문단의 하이퍼링크', '본문', ok, fonts, link, style=ids['toc 1'])
        d.save(str(self.path))
        want = {}
        for _, _, home, ok, _ in cases:
            if not ok:
                story = home if home in ('각주', '미주', '머리글', '바닥글') else '본문'
                want[story] = want.get(story, 0) + 1
        bad, detail = sum(want.values()), {}
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True, detail=detail), (B, bad))
        self.assertEqual(detail, dict(places=want, wrong=bad, no_glyph=0))
        text = all_text(self.path)
        self.assertEqual(docx_normalize.normalize(str(self.path)), (B, bad))
        self.assertEqual(all_text(self.path), text)
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), (B, 0))
        after = circled_runs(self.path)
        for label, where, home, ok, fonts in cases:
            mine = [(inside, got) for para, inside, got in after if para.startswith(label)]
            with self.subTest(label=label, where=where):
                # 비정합이던 run 만 본문 글꼴로 고친다. 정상이던 run 과 찍히지 않는 사본은 그대로 둔다
                self.assertEqual([got for inside, got in mine if 'Fallback' not in inside], [fonts if ok else SIGN])
                self.assertEqual([got for inside, got in mine if 'Fallback' in inside], [fonts] if home == '글상자' else [])

    def test_inserted_text_is_fixed_and_deleted_text_is_left_alone(self):
        """변경 추적의 삽입 표시 안에 든 글은 수락하면 본문이 되므로 세고 고친다(2026. 10. 8. 담당자 결정). 삽입 표시와 작성자·
        일시는 그대로다. 삭제 표시와 옮기기 전 자리(w:moveFrom)의 글은 Word PDF 에 찍히지 않았으므로 세지도 고치지도 않는다.
        옮긴 자리(w:moveTo)의 글은 삽입한 글처럼 찍혔다."""
        who = 'w:author="변호사" w:date="2026-09-20T00:00:00Z"'
        d = docx.Document()
        p = d.add_paragraph()._p
        for child in wx('<w:p>%s<w:ins w:id="1" %s>%s</w:ins><w:del w:id="2" %s><w:r><w:delText>③ 지운 글</w:delText></w:r></w:del>'
                        '<w:moveFrom w:id="3" %s>%s</w:moveFrom><w:moveTo w:id="4" %s>%s</w:moveTo>%s</w:p>'
                        % (wr('원고는 '), who, wr('① 근로자이고 ② 조합원이며'), who, who, wr('④ 옮기기 전 글'),
                           who, wr('⑤ 옮긴 글'), wr(' 끝.'))):
            p.append(child)
        d.save(str(self.path))
        text = all_text(self.path)
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), ('바탕체', 2))
        self.assertEqual(docx_normalize.normalize(str(self.path)), ('바탕체', 2))
        self.assertEqual(all_text(self.path), text)
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), ('바탕체', 0))
        p = docx.Document(str(self.path)).paragraphs[0]._p
        ins = p.find(qn('w:ins'))
        self.assertEqual((ins.get(qn('w:author')), ins.get(qn('w:date'))), ('변호사', '2026-09-20T00:00:00Z'))
        self.assertEqual([''.join(t.text for t in r.iter(qn('w:t'))) for r in ins],          # 조각이 삽입 표시 밖으로 나가지 않는다
                         ['①', ' 근로자이고 ', '②', ' 조합원이며'])
        self.assertEqual([k.tag for k in p if k.tag != qn('w:pPr')],
                         [qn('w:r'), qn('w:ins'), qn('w:del'), qn('w:moveFrom'), qn('w:moveTo'), qn('w:r')])
        self.assertEqual([(inside[0], fonts.get('hint')) for _, inside, fonts in circled_runs(self.path)],
                         [('ins', 'eastAsia'), ('ins', 'eastAsia'), ('del', None), ('moveFrom', None), ('moveTo', 'eastAsia')])

    def test_footnote_edited_in_word_is_fixed_in_its_own_part(self):
        """docx_footnotes.py 가 만든 각주는 글꼴을 맞춰 넣으므로 정상이다. 담당자가 Word 에서 고치거나 붙여 넣은 각주에는 글꼴
        지정이 없어 Cambria Math 로 찍힌다(2026. 10. 8. GGM 현수막 사건 서면의 각주 ①~④, 예전 점검은 0건). 각주 파트는
        docx_footnotes.py 처럼 blob 으로 읽어 고치고, 고치지 않은 파트는 다시 쓰지 않는다."""
        d = docx.Document(str(TEMPLATE))
        d.add_paragraph('대법원 판결[[각주: ① 사유, ② 절차를 본다.]]은 그러합니다.')
        d.save(str(self.path))
        self.assertEqual(run(docx_footnotes.convert, str(self.path))[0], 0)
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), ('바탕체', 0))
        d = docx.Document(str(self.path))                  # Word 에서 붙여 넣은 각주처럼 글꼴 지정을 지운다
        part = next(rel.target_part for rel in d.part.rels.values() if rel.reltype == RT.FOOTNOTES)
        root = etree.fromstring(part.blob)
        for fonts in list(root.iter(qn('w:rFonts'))):
            fonts.getparent().remove(fonts)
        part._blob = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        d.save(str(self.path))
        detail = {}
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True, detail=detail), ('바탕체', 2))
        self.assertEqual(detail['places'], {'각주': 2})
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'docx_normalize.py'), str(self.path), '--check'],
                                capture_output=True, text=True, encoding='utf-8', env=CP949)
        self.assertEqual(result.returncode, 1)
        self.assertIn('원문자 run 비정합 2건(각주 2건)', result.stdout)
        notes, text = run(docx_footnotes.convert, str(self.path), list_only=True)[1], all_text(self.path)
        with zipfile.ZipFile(str(self.path)) as archive:
            endnotes = archive.read('word/endnotes.xml')
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'docx_normalize.py'), str(self.path)],
                                capture_output=True, text=True, encoding='utf-8', env=CP949)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('원문자 run 비정합 2건(각주 2건) → 정리 완료', result.stdout)
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True), ('바탕체', 0))
        self.assertEqual(run(docx_footnotes.convert, str(self.path), list_only=True)[1], notes)
        self.assertEqual(all_text(self.path), text)
        with zipfile.ZipFile(str(self.path)) as archive:
            self.assertEqual(archive.read('word/endnotes.xml'), endnotes)

    def test_changed_text_is_not_saved_in_any_place(self):
        """정리하다 문단 글자가 달라지면 저장하지 않는 보호 장치는 각주와 하이퍼링크 안에도 걸린다."""
        for where, inner in (('각주', wr('① 각주에 붙여 넣은 글')),
                             ('본문', '<w:hyperlink w:anchor="_Toc1">%s</w:hyperlink>' % wr('① 휴게공간'))):
            d = docx.Document(str(TEMPLATE))
            put(d, where, inner)
            d.save(str(self.path))
            before = self.path.read_bytes()
            with self.subTest(where=where), mock.patch.object(docx_normalize, '_split_run',
                                                              side_effect=lambda r, font: r.getparent().remove(r)):
                with self.assertRaises(SystemExit) as cm:
                    docx_normalize.normalize(str(self.path))
                self.assertIn(where + ' 문단 글자가 달라져 저장하지 않았습니다', str(cm.exception.code))
                self.assertEqual(self.path.read_bytes(), before)

    def test_circled_numbers_above_fifteen_stay_counted(self):
        """⑯~⑳ 은 바탕체·맑은 고딕·굴림·HY견고딕에 글리프가 없다(2026. 10. 8. PyMuPDF Font.has_glyph). 넷 다 바탕체로 지정하고
        hint 를 붙여도 Word 16 은 ⑯·⑰·⑳ 을 Cambria Math 로 찍었고, 같은 지정의 ⑮ 는 바탕체로 찍었다. 글꼴 지정으로 고칠 수
        없으므로 건수에 넣고 따로 알린다(2026. 10. 8. 담당자 결정)."""
        B = '바탕체'
        cli = [sys.executable, '-B', str(SCRIPTS / 'docx_normalize.py'), str(self.path)]
        d = docx.Document()
        circled(d, '⑯', rfonts(ascii=B, hAnsi=B, eastAsia=B, cs=B, hint='eastAsia'))      # 글꼴 지정은 맞다
        d.save(str(self.path))
        before, detail = self.path.read_bytes(), {}
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True, detail=detail), (B, 1))
        self.assertEqual(detail, dict(places={'본문': 1}, wrong=0, no_glyph=1))
        for mode in (['--check'], []):                 # 정리로는 없어지지 않으므로 정리 모드도 종료 코드 1이다
            result = subprocess.run(cli + mode, capture_output=True, text=True, encoding='utf-8', env=CP949)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('원문자 run 비정합 1건', result.stdout)
            self.assertIn('⑯~⑳ 이 든 run 1건', result.stdout)
            self.assertNotIn('정리', result.stdout.splitlines()[0])
            self.assertEqual(self.path.read_bytes(), before)
        circled(d, '⑮ 가 ⑯ 나')                         # 글꼴 지정도 없다: ⑮ 는 고쳐지고 ⑯ 은 남는다
        d.save(str(self.path))
        result = subprocess.run(cli, capture_output=True, text=True, encoding='utf-8', env=CP949)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('원문자 run 비정합 2건 → 글꼴 지정 1건 정리', result.stdout)
        self.assertIn('⑯~⑳ 이 든 run 2건', result.stdout)
        self.assertEqual(docx_normalize.normalize(str(self.path), check_only=True, detail=detail), (B, 2))
        self.assertEqual(detail, dict(places={'본문': 2}, wrong=0, no_glyph=2))
        self.assertEqual(visible(docx.Document(str(self.path)).paragraphs[1]), '⑮ 가 ⑯ 나')

    def test_merge_reports_circled_number_above_fifteen(self):
        # 건수에 넣었으므로 ⑯ 이상이 든 초안을 병합하면 종료 코드 1이 된다. 파일은 저장되고 점검 줄에 사유가 나온다
        folder = Path(self.tmp.name) / '출력'
        folder.mkdir()
        frame, md, out = folder / '서면_프레임.docx', folder / '서면초안.md', folder / '(테스트) 준비서면_초안.docx'
        make_frame(frame)
        md.write_text('1. 이 사건의 경위\n\n피고는 ⑮ 원고를 징계하였고, ⑯ 해고하였습니다.\n\n'
                      '2. 결론\n\n원고의 청구는 기각되어야 합니다.\n' + EVIDENCE, encoding='utf-8')
        code, log = run(docx_merge.merge, str(frame), str(md), str(out))
        self.assertEqual(code, 1, log)
        self.assertIn('원문자 글꼴 비정합 1건', log)
        self.assertIn('⑯~⑳ 이 든 run 1건', log)
        self.assertTrue(out.exists())
        md.write_text(md.read_text(encoding='utf-8').replace('⑯', '⑭'), encoding='utf-8')
        code, log = run(docx_merge.merge, str(frame), str(md), str(out))
        self.assertEqual(code, 0, log)
        self.assertIn('원문자 글꼴 비정합 0건', log)


if __name__ == '__main__':
    unittest.main()
