"""memo_author.py — 검토본·서면의 새 메모·변경 작성자를 '법무법인 평안'으로 맞추는지 작은 docx·hwpx 로 시험한다.

사람 이름·메일은 지어낸 값이다(홍길동 = 의뢰인 쪽, 김담당 = 우리 쪽 개인). 원래 있던 메모·변경은 지난 일시(OLD),
이번에 새로 단 것은 지금 일시(NEW)로 둔다.
"""
import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location('memo_author', Path(__file__).parents[1] / 'scripts' / 'memo_author.py')
memo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memo)

HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
TYPES = HEAD + ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="xml" ContentType="application/xml"/></Types>')
OURS, THEIRS = '김담당 노무사', '홍길동'
OLD, NEW = '2026-10-10T09:00:00Z', '2026-10-16T05:30:00Z'


def ins(author, text, i, when=OLD):
    return f'<w:ins w:id="{i}" w:author="{author}" w:date="{when}"><w:r><w:t>{text}</w:t></w:r></w:ins>'


def dele(author, text, i, when=OLD):
    return f'<w:del w:id="{i}" w:author="{author}" w:date="{when}"><w:r><w:delText>{text}</w:delText></w:r></w:del>'


def bold(author, i, when=OLD):
    return (f'<w:r><w:rPr><w:b/><w:rPrChange w:id="{i}" w:author="{author}" w:date="{when}"><w:rPr/></w:rPrChange>'
            '</w:rPr><w:t>굵게</w:t></w:r>')


def document(*pieces):
    body = ''.join(f'<w:p>{p}</w:p>' for p in pieces)
    return HEAD + f'<w:document {W}><w:body>{body}</w:body></w:document>'


def comments(*items):
    """(id, 작성자, 머리글자, 글[, 일시])."""
    inner = ''.join(f'<w:comment w:id="{c[0]}" w:author="{c[1]}" w:initials="{c[2]}" w:date="{c[4] if len(c) > 4 else OLD}">'
                    f'<w:p><w:r><w:t>{c[3]}</w:t></w:r></w:p></w:comment>' for c in items)
    return HEAD + f'<w:comments {W}>{inner}</w:comments>'


def people(*who):
    inner = ''.join(f'<w15:person w15:author="{a}"><w15:presenceInfo w15:providerId="AD" w15:userId="S::{mail}::1"/>'
                    '</w15:person>' for a, mail in who)
    return HEAD + f'<w15:people xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml">{inner}</w15:people>'


def core(creator, last):
    return HEAD + ('<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                   f'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>{creator}</dc:creator>'
                   f'<cp:lastModifiedBy>{last}</cp:lastModifiedBy></cp:coreProperties>')


def write_docx(path, parts):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, text in parts.items():
            z.writestr(name, text)


def read(path, name):
    with zipfile.ZipFile(path) as z:
        return z.read(name).decode('utf-8')


ORIGINAL_DOCX = {
    '[Content_Types].xml': TYPES,
    'word/document.xml': document(ins(THEIRS, '의뢰인이 고친 곳', 1), '<w:r><w:t>본문</w:t></w:r>'),
    'word/comments.xml': comments((0, THEIRS, 'HG', '의뢰인 메모')),
    'word/people.xml': people((THEIRS, 'client@example.com')),
    'docProps/core.xml': core(THEIRS, THEIRS),
}
REVIEWED_DOCX = {
    '[Content_Types].xml': TYPES,
    'word/document.xml': document(ins(THEIRS, '의뢰인이 고친 곳', 1), '<w:r><w:t>김담당 노무사가 검토함</w:t></w:r>',
                                  ins(OURS, '우리가 넣은 글', 2, NEW), dele(OURS, '우리가 지운 글', 3, NEW)),
    'word/comments.xml': comments((0, THEIRS, 'HG', '의뢰인 메모'), (1, OURS, 'KD', '수정 이유 1', NEW),
                                  (2, OURS, 'KD', '수정 이유 2', NEW)),
    'word/people.xml': people((THEIRS, 'client@example.com'), (OURS, 'staff@example.com')),
    'docProps/core.xml': core(THEIRS, OURS),
}


class DocxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.original, self.review = t / '원본.docx', t / '(가나상사) 취업규칙_검토본.docx'
        write_docx(self.original, ORIGINAL_DOCX)
        write_docx(self.review, REVIEWED_DOCX)

    def tearDown(self):
        self.tmp.cleanup()

    def run_memo(self, *args, **kw):
        out = io.StringIO()
        with redirect_stdout(out):
            code = memo.run(self.review, self.original, *args, **kw)
        return code, out.getvalue()

    def test_new_memos_and_changes_become_the_firm_and_client_ones_stay(self):
        with zipfile.ZipFile(self.review) as z:
            order = [i.filename for i in z.infolist()]
        code, out = self.run_memo()
        self.assertEqual(code, 0, out)
        doc, com = read(self.review, 'word/document.xml'), read(self.review, 'word/comments.xml')
        self.assertNotIn(f'w:author="{OURS}"', doc + com)
        self.assertEqual(doc.count('w:author="법무법인 평안"'), 2)
        self.assertEqual(com.count('w:author="법무법인 평안" w:initials="평안"'), 2)
        self.assertIn(f'w:author="{THEIRS}" w:initials="HG"', com)                     # 의뢰인 메모는 그대로
        self.assertIn(f'w:author="{THEIRS}"', doc)
        self.assertIn('김담당 노무사가 검토함', doc)                                     # 본문 글자는 건드리지 않는다
        ppl = read(self.review, 'word/people.xml')
        self.assertNotIn('staff@example.com', ppl)
        self.assertNotIn(OURS, ppl)
        self.assertIn('client@example.com', ppl)
        props = read(self.review, 'docProps/core.xml')
        self.assertIn('<cp:lastModifiedBy>법무법인 평안</cp:lastModifiedBy>', props)
        self.assertIn(f'<dc:creator>{THEIRS}</dc:creator>', props)
        self.assertEqual(read(self.review, '[Content_Types].xml'), TYPES)              # 손대지 않은 부분은 그대로
        with zipfile.ZipFile(self.review) as z:
            self.assertEqual([i.filename for i in z.infolist()], order)
        self.assertIn(f'{OURS} → 법무법인 평안  (메모 2개, 변경 2개)', out)
        self.assertIn(f'그대로  {THEIRS}', out)
        self.assertFalse(list(Path(self.tmp.name).glob('*.part')))

    def test_check_mode_reports_without_changing(self):
        before = self.review.read_bytes()
        code, out = self.run_memo(check=True)
        self.assertEqual(code, 2)
        self.assertIn(f'바꿀 작성자  {OURS}', out)
        self.assertEqual(self.review.read_bytes(), before)
        self.run_memo()
        code, out = self.run_memo(check=True)
        self.assertEqual(code, 0, out)
        self.assertIn('바꿀 작성자가 없습니다', out)

    def test_names_already_in_the_original_change_only_when_named(self):
        earlier = dict(ORIGINAL_DOCX, **{'word/comments.xml': comments((0, THEIRS, 'HG', '의뢰인 메모'), (1, OURS, 'KD', '지난번 메모'))})
        write_docx(self.original, earlier)
        write_docx(self.review, dict(REVIEWED_DOCX, **{'word/comments.xml': earlier['word/comments.xml']}))
        self.run_memo()
        self.assertIn(f'w:author="{OURS}"', read(self.review, 'word/comments.xml'))   # 원본에 있던 메모라 그대로
        code, _ = self.run_memo(personal=[OURS])
        self.assertEqual(code, 0)
        self.assertNotIn(f'w:author="{OURS}"', read(self.review, 'word/comments.xml'))

    def test_staff_memo_in_the_base_stays_and_new_one_under_the_same_name_changes(self):
        # 서면: 담당자가 직접 메모·수정을 남긴 저장본 위에서 다시 고치면 Word 가 같은 사용자 이름으로 새 메모를 넣는다
        base = {'[Content_Types].xml': TYPES,
                'word/document.xml': document(ins(OURS, '담당자가 고친 곳', 1)),
                'word/comments.xml': comments((0, OURS, 'KD', '담당자가 직접 단 메모')),
                'word/people.xml': people((OURS, 'staff@example.com')),
                'docProps/core.xml': core(THEIRS, OURS)}
        write_docx(self.original, base)
        write_docx(self.review, dict(base, **{
            'word/document.xml': document(ins(OURS, '담당자가 고친 곳', 1), ins(OURS, '새로 넣은 글', 2, NEW)),
            'word/comments.xml': comments((0, OURS, 'KD', '담당자가 직접 단 메모'), (1, OURS, 'KD', '확인을 부탁드립니다', NEW))}))
        code, out = self.run_memo()
        self.assertEqual(code, 0, out)
        com, doc = read(self.review, 'word/comments.xml'), read(self.review, 'word/document.xml')
        self.assertIn(f'w:author="{OURS}" w:initials="KD"', com)                       # 담당자 메모는 그대로
        self.assertIn('w:author="법무법인 평안" w:initials="평안"', com)
        self.assertEqual((doc.count(f'w:author="{OURS}"'), doc.count('w:author="법무법인 평안"')), (1, 1))
        self.assertIn('staff@example.com', read(self.review, 'word/people.xml'))      # 남은 담당자 메모가 가리킨다
        self.assertIn(f'{OURS} → 법무법인 평안  (메모 1개, 변경 1개)', out)
        self.assertIn(f'그대로  {OURS}  (메모 1개', out)
        self.assertNotIn('본문 밖에 개인 이름', out)

    def test_pieces_of_an_original_change_stay_after_word_saves_again(self):
        # Word 가 다시 저장하며 원래 수정 하나를 여러 조각으로 나누어도(일시 표기가 조금 달라도) 원래 것으로 본다
        write_docx(self.original, dict(ORIGINAL_DOCX, **{'word/document.xml': document(
            ins(THEIRS, '의뢰인이 고친 곳', 1), bold(OURS, 5))}))
        write_docx(self.review, dict(ORIGINAL_DOCX, **{'word/document.xml': document(
            ins(THEIRS, '의뢰인이 ', 1), ins(THEIRS, '고친 곳', 4, '2026-10-10T09:00:00'),
            bold(OURS, 5), bold(OURS, 6, '2026-10-10T09:00:30Z'), bold(OURS, 7, NEW))}))
        self.run_memo()
        doc = read(self.review, 'word/document.xml')
        self.assertEqual((doc.count(f'w:author="{THEIRS}"'), doc.count(f'w:author="{OURS}"'),
                          doc.count('w:author="법무법인 평안"')), (2, 2, 1))

    def test_memo_already_by_the_firm_gets_the_firm_initials(self):
        write_docx(self.review, dict(ORIGINAL_DOCX, **{
            'word/comments.xml': comments((0, THEIRS, 'HG', '의뢰인 메모'), (1, '법무법인 평안', 'C', '수정 이유', NEW))}))
        code, out = self.run_memo()
        self.assertEqual(code, 0, out)
        self.assertIn('w:author="법무법인 평안" w:initials="평안"', read(self.review, 'word/comments.xml'))
        self.assertIn('메모 머리글자 1개 → 평안', out)

    def test_personal_name_left_elsewhere_is_reported(self):
        app = HEAD + f'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Manager>{OURS}</Manager></Properties>'
        write_docx(self.review, dict(REVIEWED_DOCX, **{'docProps/app.xml': app}))
        code, out = self.run_memo()
        self.assertEqual(code, 0, out)
        self.assertIn('본문 밖에 개인 이름이 남은 부분(눈으로 확인): docProps/app.xml', out)

    def test_open_file_is_reported_and_left_alone(self):
        before = self.review.read_bytes()
        with mock.patch.object(memo.os, 'replace', side_effect=PermissionError('locked')):
            with self.assertRaises(memo.MemoError) as caught:
                self.run_memo()
        self.assertIn('열려 있어', str(caught.exception))
        self.assertEqual(self.review.read_bytes(), before)
        self.assertFalse(list(Path(self.tmp.name).glob('*.part')))

    def test_unsupported_or_mismatched_files(self):
        pdf = Path(self.tmp.name) / '원본.pdf'
        pdf.write_bytes(b'%PDF')
        with self.assertRaises(memo.MemoError):
            memo.run(pdf, pdf)
        hwpx = Path(self.tmp.name) / '원본.hwpx'
        hwpx.write_bytes(b'x')
        with self.assertRaises(memo.MemoError):
            memo.run(self.review, hwpx)
        with self.assertRaises(memo.MemoError):
            memo.run(Path(self.tmp.name) / '없음.docx', self.original)


# ── 한글(hwpx) ──

HH = 'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'
HP = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
H_OLD, H_NEW = '2026-10-10 09:00:00', '2026-10-16 14:30:00'


def header(*authors):
    inner = ''.join(f'<hh:trackChangeAuthor id="{i}" name="{a}" mark="1" color="#FF0000"/>' for i, a in enumerate(authors))
    return HEAD + f'<hh:head {HH}><hh:refList><hh:trackChangeAuthors itemCnt="{len(authors)}">{inner}</hh:trackChangeAuthors></hh:refList></hh:head>'


def memo_field(i, author, text, when=H_OLD):
    return (f'<hp:ctrl><hp:fieldBegin id="{i}" type="MEMO" name=""><hp:parameters cnt="5" name="">'
            f'<hp:stringParam name="ID">m{i}</hp:stringParam><hp:integerParam name="Number">{i}</hp:integerParam>'
            f'<hp:stringParam name="Author">{author}</hp:stringParam>'
            f'<hp:stringParam name="CreateDateTime">{when}</hp:stringParam>'
            f'<hp:stringParam name="MemoShapeIDRef">0</hp:stringParam></hp:parameters>'
            f'<hp:subList><hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:fieldBegin></hp:ctrl>')


def section(*memos):
    runs = ''.join(f'<hp:p><hp:run>{m}<hp:t>본문 김담당 언급</hp:t></hp:run></hp:p>' for m in memos)
    return HEAD + f'<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" {HP}>{runs}</hs:sec>'


def content(creator, last):
    return HEAD + ('<opf:package xmlns:opf="http://www.idpf.org/2007/opf/"><opf:metadata>'
                   f'<opf:meta name="creator" content="text">{creator}</opf:meta>'
                   f'<opf:meta name="lastsaveby" content="text">{last}</opf:meta></opf:metadata></opf:package>')


def write_hwpx(path, header_xml, section_xml, content_xml):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/hwp+zip', compress_type=zipfile.ZIP_STORED)
        for name, text in (('Contents/header.xml', header_xml), ('Contents/section0.xml', section_xml),
                           ('Contents/content.hpf', content_xml)):
            z.writestr(name, text, compress_type=zipfile.ZIP_DEFLATED)


class HwpxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.original, self.review = t / 'original.hwpx', t / 'review.hwpx'
        write_hwpx(self.original, header(THEIRS), section(memo_field(1, THEIRS, '의뢰인 메모')), content(THEIRS, THEIRS))
        write_hwpx(self.review, header(THEIRS, '김담당'),
                   section(memo_field(1, THEIRS, '의뢰인 메모'), memo_field(2, '김담당', '수정 이유', H_NEW)),
                   content(THEIRS, '김담당'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_memo_and_track_change_authors_become_the_firm(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = memo.run(self.review, self.original)
        self.assertEqual(code, 0, out.getvalue())
        head, sec, meta = (read(self.review, n) for n in ('Contents/header.xml', 'Contents/section0.xml', 'Contents/content.hpf'))
        self.assertIn('id="1" name="법무법인 평안"', head)
        self.assertIn(f'id="0" name="{THEIRS}"', head)
        self.assertIn('<hp:stringParam name="Author">법무법인 평안</hp:stringParam>', sec)
        self.assertIn(f'<hp:stringParam name="Author">{THEIRS}</hp:stringParam>', sec)
        self.assertEqual(sec.count('본문 김담당 언급'), 2)                                # 본문은 그대로
        self.assertIn('name="lastsaveby" content="text">법무법인 평안<', meta)
        self.assertIn(f'name="creator" content="text">{THEIRS}<', meta)
        with zipfile.ZipFile(self.review) as z:
            first = z.infolist()[0]
        self.assertEqual((first.filename, first.compress_type), ('mimetype', zipfile.ZIP_STORED))
        self.assertIn('김담당 → 법무법인 평안  (메모 1개, 변경 1개)', out.getvalue())

    def test_hangul_staff_memo_in_the_base_stays(self):
        write_hwpx(self.original, header('김담당'), section(memo_field(1, '김담당', '담당자 메모')), content(THEIRS, '김담당'))
        write_hwpx(self.review, header('김담당'),
                   section(memo_field(1, '김담당', '담당자 메모'), memo_field(2, '김담당', '새 메모', H_NEW)),
                   content(THEIRS, '김담당'))
        with redirect_stdout(io.StringIO()):
            memo.run(self.review, self.original)
        sec = read(self.review, 'Contents/section0.xml')
        self.assertEqual((sec.count('name="Author">김담당<'), sec.count('name="Author">법무법인 평안<')), (1, 1))
        self.assertIn('name="김담당"', read(self.review, 'Contents/header.xml'))       # 목록의 이름은 원본에 있던 것

    def test_memo_author_inside_a_memo_group_is_found(self):
        grouped = section(memo_field(2, '김담당', '수정 이유', H_NEW)).replace(
            '</hs:sec>', '<hp:memogroup><hp:memo id="2"><hp:stringParam name="Author">김담당</hp:stringParam></hp:memo></hp:memogroup></hs:sec>')
        write_hwpx(self.review, header(THEIRS), grouped, content(THEIRS, THEIRS))
        with redirect_stdout(io.StringIO()):
            memo.run(self.review, self.original)
        sec = read(self.review, 'Contents/section0.xml')
        self.assertNotIn('>김담당<', sec)
        self.assertEqual(sec.count('name="Author">법무법인 평안<'), 2)

    def test_hwp_goes_through_hwpx_with_hangul_and_is_saved_back_only_when_changed(self):
        hwp, original_hwp = Path(self.tmp.name) / '검토본.hwp', Path(self.tmp.name) / '원본.hwp'
        shutil.copyfile(self.review, hwp)                                                # 가짜: hwp 안에 hwpx 를 담아 둔다
        shutil.copyfile(self.original, original_hwp)
        calls = []

        def fake_convert(src, dst):
            calls.append((src.suffix, dst.suffix))
            shutil.copyfile(src, dst)

        with mock.patch.object(memo, 'convert', fake_convert), redirect_stdout(io.StringIO()):
            self.assertEqual(memo.run(hwp, original_hwp), 0)
            self.assertEqual(calls, [('.hwp', '.hwpx'), ('.hwp', '.hwpx'), ('.hwpx', '.hwp')])
            self.assertIn('<hp:stringParam name="Author">법무법인 평안</hp:stringParam>', read(hwp, 'Contents/section0.xml'))
            calls.clear()
            self.assertEqual(memo.run(hwp, original_hwp), 0)                             # 바꿀 것이 없으면 다시 저장하지 않는다
            self.assertEqual(calls, [('.hwp', '.hwpx'), ('.hwp', '.hwpx')])

    def test_hwp_needs_hangul_automation(self):
        with mock.patch.dict(sys.modules, {'win32com': None, 'win32com.client': None}):
            with self.assertRaises(memo.MemoError) as caught:
                memo.hwp_app()
        self.assertIn('hwpx', str(caught.exception))


class MinuteTests(unittest.TestCase):
    def test_minute_ignores_seconds_and_marks(self):
        self.assertEqual({memo.minute(v) for v in ('2026-10-10T09:00:00Z', '2026-10-10T09:00:30Z', '2026-10-10T09:00:00',
                                                    '2026-10-10T09:00:00.000Z', '2026-10-10 09:00:59')}, {'2026-10-10T09:00'})
        self.assertEqual(memo.minute('어제'), '어제')


if __name__ == '__main__':
    unittest.main()
