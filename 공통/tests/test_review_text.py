import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / 'scripts' / 'review_text.py'
spec = importlib.util.spec_from_file_location('review_text', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'


def run(text):
    return '<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % text


def ref(i):
    return '<w:r><w:footnoteReference w:id="%d"/></w:r>' % i


def note(i, text, kind=''):
    return '<w:footnote w:id="%d"%s><w:p><w:r><w:footnoteRef/></w:r>%s</w:p></w:footnote>' % (i, kind, run(text))


class ReviewTextTests(unittest.TestCase):
    def make(self, body, footnotes, extra=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / '검토.docx'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', f'<w:document {NS}><w:body>{body}</w:body></w:document>')
            z.writestr('word/footnotes.xml', f'<w:footnotes {NS}>{footnotes}</w:footnotes>')
            for name, xml in (extra or {}).items():
                z.writestr(name, xml)
        return path

    def test_marks_follow_reference_order_not_ids(self):
        """각주 번호는 id 가 아니라 본문에 나오는 순서이다(새 각주를 끝에 붙이면 id 와 번호가 어긋난다)."""
        path = self.make(
            '<w:p>' + run('첫 문장.') + ref(7) + run(' 둘째 문장.') + ref(2) + '</w:p>'
            '<w:tbl><w:tr><w:tc><w:p>' + run('표 안') + ref(7) + '</w:p></w:tc></w:tr></w:tbl>'
            '<w:p></w:p>',
            note(-1, '', ' w:type="separator"') + note(2, '둘째 각주.') + note(7, '첫째 각주.') + note(9, '남은 각주.'))
        text, summary = module.review_text(path)
        self.assertIn('첫 문장.{{1}} 둘째 문장.{{2}}', text)
        self.assertIn('표 안{{1}}', text)
        self.assertIn('{{1}} 첫째 각주.\n{{2}} 둘째 각주.', text)
        self.assertIn('- 남은 각주.', text)
        self.assertEqual((summary['문단'], summary['각주']), (2, 2))
        self.assertEqual(summary['경고'], ['본문의 두 자리에서 참조한 각주: 1', '본문에서 참조하지 않는 각주 1개'])

    def test_tracked_changes_and_fallback(self):
        path = self.make(
            '<w:p><w:ins><w:r><w:t>넣은 글</w:t></w:r></w:ins><w:del><w:r><w:delText>지운 글</w:delText></w:r></w:del>'
            '<mc:AlternateContent><mc:Choice><w:r><w:t> 새 형식</w:t></w:r></mc:Choice>'
            '<mc:Fallback><w:r><w:t> 옛 사본</w:t></w:r></mc:Fallback></mc:AlternateContent></w:p>', '')
        text, summary = module.review_text(path)
        self.assertIn('넣은 글 새 형식', text)
        self.assertNotIn('지운 글', text)
        self.assertNotIn('옛 사본', text)
        self.assertTrue(any('변경 추적' in w for w in summary['경고']))

    def test_tab_stops_moves_and_empty_body(self):
        """문단 속성의 탭 자리 정의는 글자가 아니다. 옮기기 전 자리의 글은 빼고, 글자가 없는 문서는 경고한다."""
        path = self.make(
            '<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs></w:pPr>' + run('탭 자리만 있는 문단')
            + '<w:moveFrom><w:r><w:t>옮기기 전</w:t></w:r></w:moveFrom><w:moveTo><w:r><w:t> 옮긴 뒤</w:t></w:r></w:moveTo>' + ref(3) + '</w:p>',
            '<w:footnote w:id="3"><w:p><w:ins><w:r><w:t>각주에 넣은 글</w:t></w:r></w:ins></w:p></w:footnote>')
        text, summary = module.review_text(path)
        self.assertIn('탭 자리만 있는 문단 옮긴 뒤{{1}}', text.splitlines())      # 줄 앞에 탭 글자가 붙지 않는다
        self.assertNotIn('옮기기 전', text)
        self.assertEqual(len([w for w in summary['경고'] if '변경 추적' in w]), 2)      # 본문과 각주
        empty = self.make('<w:p></w:p>', '')
        self.assertTrue(any('글자가 없다' in w for w in module.review_text(empty)[1]['경고']))

    def test_deleted_reference_is_read_as_accepted(self):
        """변경 추적으로 지운 각주 참조는 자리 표시를 남기지 않는다. 번호는 모두 수락한 문서와 같아진다."""
        path = self.make(
            '<w:p>' + run('첫 문장.') + ref(1) + run(' 둘째 문장.') + '<w:del><w:r><w:footnoteReference w:id="2"/></w:r></w:del>'
            + '<w:del><w:r><w:tab/><w:delText>지운 글</w:delText></w:r></w:del>' + run(' 셋째 문장.') + ref(3) + ref(4) + '</w:p>',
            note(1, '첫째 각주.') + '<w:footnote w:id="2"><w:p><w:del><w:r><w:delText>지운 각주.</w:delText></w:r></w:del></w:p></w:footnote>'
            + note(3, '셋째 각주.') + '<w:footnote w:id="4"><w:p></w:p></w:footnote>')
        text, summary = module.review_text(path)
        self.assertIn('첫 문장.{{1}} 둘째 문장. 셋째 문장.{{2}}{{3}}', text.splitlines())
        self.assertIn('{{2}} 셋째 각주.', text)
        self.assertIn('{{3}} (글 없음)', text)                      # 참조는 살아 있는데 글이 빈 각주는 알린다
        self.assertNotIn('지운', text)
        self.assertEqual(summary['각주'], 3)
        self.assertTrue(any('각주 3 의 글을 찾지 못하였다' in w for w in summary['경고']))
        self.assertFalse(any('참조하지 않는' in w for w in summary['경고']))      # 지운 각주는 남은 각주로 세지 않는다
        self.assertEqual(len([w for w in summary['경고'] if '변경 추적' in w]), 2)      # 삭제만 있는 문서도 변경 추적을 알린다(본문과 각주)

    def test_word_comments_are_warned_not_extracted(self):
        """Word 메모의 글은 뽑지 않는다. 메모가 있으면 건수를 경고하여 따로 읽게 한다."""
        def memo(i, text):
            return '<w:comment w:id="%d" w:author="담당자"><w:p>%s</w:p></w:comment>' % (i, run(text))

        body = ('<w:p><w:commentRangeStart w:id="0"/>' + run('메모가 달린 문장.') + '<w:commentRangeEnd w:id="0"/>'
                '<w:r><w:commentReference w:id="0"/></w:r></w:p>')
        path = self.make(body, '', {'word/comments.xml': f'<w:comments {NS}>' + memo(0, '이 문장은 빼 주세요.') + memo(1, '답글.') + '</w:comments>'})
        text, summary = module.review_text(path)
        self.assertIn('메모가 달린 문장.', text.splitlines())
        self.assertNotIn('빼 주세요', text)
        self.assertEqual([w for w in summary['경고'] if '메모' in w], ['Word 메모 2건이 있다(word/comments.xml). 메모의 글은 이 글에 들어 있지 않다'])
        emptied = self.make(body, '', {'word/comments.xml': f'<w:comments {NS}></w:comments>'})      # 메모를 모두 지운 문서에 빈 파일만 남은 경우
        self.assertFalse(any('메모' in w for w in module.review_text(emptied)[1]['경고']))
        self.assertFalse(any('메모' in w for w in module.review_text(self.make(body, ''))[1]['경고']))
        # 비었거나 깨진 메모 파일이 있어도 본문은 뽑고, 읽지 못하였다고 알린다. 뒤의 둘은 XML 선언의 인코딩을 파이썬이 읽지 못하는
        # 경우로 ParseError 가 아니다(모르는 이름은 LookupError, euc-kr 같은 다바이트 인코딩은 ValueError)
        declared = '<?xml version="1.0" encoding="%s"?>' + f'<w:comments {NS}></w:comments>'
        for broken in ('', '<w:comments', declared % 'x-none-such', declared % 'euc-kr'):
            path = self.make(body, '', {'word/comments.xml': broken})
            text, summary = module.review_text(path)
            self.assertIn('메모가 달린 문장.', text.splitlines())
            self.assertEqual([w for w in summary['경고'] if '메모' in w], ['word/comments.xml 을 읽지 못하였다. Word 메모가 있는지 Word 에서 따로 확인한다'])
            self.assertIsNone(module.memo_notes(path))

    def test_memos_come_with_the_passage_they_are_attached_to(self):
        """--memos: 메모의 글만으로는 어느 문장에 단 메모인지 알 수 없다. 붙은 구절과 달린 문단을 함께 뽑는다."""
        import contextlib, io, sys
        from unittest import mock

        def memo(i, *texts):
            return '<w:comment w:id="%d" w:author="담당자" w:date="2026-10-09T10:00:00Z">%s</w:comment>' % (i, ''.join('<w:p>%s</w:p>' % run(t) for t in texts))

        def start(i):
            return '<w:commentRangeStart w:id="%d"/>' % i

        def end(i):
            return '<w:commentRangeEnd w:id="%d"/><w:r><w:commentReference w:id="%d"/></w:r>' % (i, i)

        body = (
            # 메모 0 과 그 답글 1: 한 문단 안의 두 런에 걸친 범위. 범위 안의 지운 글은 본문과 같이 뺀다
            '<w:p>' + run('앞 문장. ') + start(0) + start(1) + run('빼 달라는 ') + '<w:del><w:r><w:delText>삭제된낱말 </w:delText></w:r></w:del>'
            + run('문장.') + end(0) + end(1) + run(' 뒤 문장.') + ref(5) + '</w:p>'
            # 메모 2: 문단 사이에서 시작하여 두 문단에 걸친 범위
            + start(2) + '<w:p>' + run('둘째 문단 전체.') + '</w:p><w:p>' + run('셋째 문단 앞') + end(2) + run(' 셋째 문단 뒤.') + '</w:p>'
            # 메모 3: 범위 없이 메모 표시만 있다
            + '<w:p>' + run('표시만 달린 문단.') + '<w:r><w:commentReference w:id="3"/></w:r></w:p>'
            # 메모 5: 범위는 있으나 그 안의 글이 모두 변경 추적으로 지운 글이다
            + '<w:p>' + run('지운 자리 앞.') + start(5) + '<w:del><w:r><w:delText>삭제된낱말</w:delText></w:r></w:del>' + end(5) + run(' 지운 자리 뒤.')
            + '<w:r><w:endnoteReference w:id="1"/></w:r></w:p>')
        foot = '<w:footnote w:id="5"><w:p><w:r><w:footnoteRef/></w:r>' + run('각주 앞 ') + start(4) + run('각주에 단 구절') + end(4) + '</w:p></w:footnote>'
        # 메모 6: 미주 안의 메모. 범위에 탭과 줄바꿈이 들어 있다
        endnotes = f'<w:endnotes {NS}><w:endnote w:id="1"><w:p>' + start(6) + run('미주 구절') + '<w:r><w:tab/><w:t>탭 뒤</w:t><w:br/><w:t>줄 뒤</w:t></w:r>' \
            + end(6) + '</w:p></w:endnote></w:endnotes>'
        cx = f'<w:comments {NS}>' + memo(0, '이 문장은 빼 주세요.', '근거가 없습니다.') + memo(1, '답글.') + memo(2, '두 문단을 합쳐 주세요.') \
            + memo(3, '표시만.') + memo(4, '각주 메모.') + memo(5, '이 문장은 뺐습니다.') + memo(6, '미주 메모.') + memo(9, '자리가 없는 메모.') + '</w:comments>'
        path = self.make(body, foot, {'word/comments.xml': cx, 'word/endnotes.xml': endnotes})

        found = module.memo_notes(path)
        self.assertEqual([m['글'] for m in found], ['이 문장은 빼 주세요.\n근거가 없습니다.', '답글.', '두 문단을 합쳐 주세요.', '표시만.', '각주 메모.',
                                                   '이 문장은 뺐습니다.', '미주 메모.', '자리가 없는 메모.'])
        self.assertEqual([m['붙은 구절'] for m in found], ['빼 달라는 문장.', '빼 달라는 문장.', '둘째 문단 전체.\n셋째 문단 앞', '', '각주에 단 구절',
                                                        '', '미주 구절\t탭 뒤\n줄 뒤', ''])
        self.assertEqual([m['범위'] for m in found], [True, True, True, False, True, True, True, False])
        self.assertEqual([m['문단'] for m in found], ['앞 문장. 빼 달라는 문장. 뒤 문장.', '앞 문장. 빼 달라는 문장. 뒤 문장.', '둘째 문단 전체.',
                                                    '표시만 달린 문단.', '각주 앞 각주에 단 구절', '지운 자리 앞. 지운 자리 뒤.', '미주 구절\t탭 뒤\n줄 뒤', ''])
        self.assertEqual([m['자리'] for m in found], ['본문', '본문', '본문', '본문', '각주', '본문', '미주', ''])
        self.assertEqual((found[0]['작성자'], found[0]['날짜']), ('담당자', '2026-10-09T10:00:00Z'))

        def call(*argv):
            screen = io.StringIO()
            with mock.patch.object(sys, 'argv', ['review_text.py', *map(str, argv)]), contextlib.redirect_stdout(screen), contextlib.redirect_stderr(screen):
                module.main()
            return screen.getvalue()

        out, memos = Path(self.tmp.name) / '자체검토' / '검토대상.md', Path(self.tmp.name) / '자체검토' / 'Word메모.md'
        self.assertIn('--memos', call(path, '--out', out))      # 메모가 있는데 --memos 를 주지 않으면 따로 뽑으라고 알린다
        self.assertFalse(memos.exists())
        self.assertIn('Word 메모 8건 ->', call(path, '--out', out, '--memos', memos))
        self.assertNotIn('빼 주세요', out.read_text(encoding='utf-8'))      # 메모의 글은 검토 대상 글에 넣지 않는다
        shown, said = io.StringIO(), io.StringIO()      # 글을 화면에 낼 때에는 알림이 글에 섞이지 않는다
        with mock.patch.object(sys, 'argv', ['review_text.py', str(path)]), contextlib.redirect_stdout(shown), contextlib.redirect_stderr(said):
            module.main()
        self.assertEqual(shown.getvalue(), out.read_text(encoding='utf-8'))
        self.assertIn('--memos', said.getvalue())
        shown, said = io.StringIO(), io.StringIO()      # --out 없이 --memos 만 준 때의 알림도 글에 섞이지 않는다
        with mock.patch.object(sys, 'argv', ['review_text.py', str(path), '--memos', str(memos)]), contextlib.redirect_stdout(shown), contextlib.redirect_stderr(said):
            module.main()
        self.assertEqual(shown.getvalue(), out.read_text(encoding='utf-8'))
        self.assertIn('Word 메모 8건 ->', said.getvalue())
        written = memos.read_text(encoding='utf-8')
        self.assertIn('## 메모 1 — 담당자, 2026-10-09T10:00:00Z\n\n붙은 구절(본문):\n> 빼 달라는 문장.\n\n메모가 달린 문단:\n> 앞 문장. 빼 달라는 문장. 뒤 문장.\n\n'
                      '메모의 글:\n> 이 문장은 빼 주세요.\n> 근거가 없습니다.\n', written)
        self.assertIn('붙은 구절(본문):\n> 둘째 문단 전체.\n> 셋째 문단 앞\n', written)
        self.assertIn('붙은 구절(본문):\n> (범위 없이 메모 표시만 있다)\n\n메모가 달린 문단:\n> 표시만 달린 문단.\n', written)
        self.assertIn('붙은 구절(각주):\n> 각주에 단 구절\n', written)
        self.assertIn('붙은 구절(본문):\n> (범위는 있으나 그 안에 글로 뽑힌 것이 없다. 변경 추적으로 지운 글, 그림·공백, 각주·미주 번호만 든 범위이거나 빈 범위일 수 있다. '
                      '무엇에 단 메모인지는 Word 에서 따로 확인한다)\n\n메모가 달린 문단:\n> 지운 자리 앞. 지운 자리 뒤.\n', written)
        self.assertIn('붙은 구절(미주):\n> 미주 구절\t탭 뒤\n> 줄 뒤\n', written)
        self.assertIn('## 메모 8 — 담당자, 2026-10-09T10:00:00Z\n\n붙은 구절:\n> (본문·각주·미주에서 이 메모의 자리를 찾지 못하였다. Word 에서 따로 확인한다)\n\n메모의 글:\n> 자리가 없는 메모.\n', written)
        self.assertNotIn('삭제된낱말', written)
        with self.assertRaises(SystemExit):      # 검토 대상 글과 같은 파일에 쓰지 않는다
            call(path, '--out', out, '--memos', out)

        plain = self.make('<w:p>' + run('메모 없는 문서.') + '</w:p>', '')      # 메모가 없으면 파일을 만들지 않는다
        self.assertEqual(module.memo_notes(plain), [])
        none = Path(self.tmp.name) / '자체검토' / '없음.md'
        self.assertIn('메모가 없다', call(plain, '--out', Path(self.tmp.name) / '자체검토' / '검토대상2.md', '--memos', none))
        self.assertFalse(none.exists())

    def test_memo_marks_inside_deleted_text_and_unclosed_ranges(self):
        """Word 는 메모가 붙은 글을 변경 추적으로 지우면 범위 표시와 메모 표시를 지운 글(w:del) 안에 쓴다(2026. 10. 10. Word 16 저장본의 꼴).
        지운 글은 빼되 그 안의 표시는 읽는다. 끝 표시를 만나지 못한 범위는 그 뒤의 글을 구절로 적지 않는다."""
        def memo(i):
            return '<w:comment w:id="%d" w:author="담당자"><w:p>%s</w:p></w:comment>' % (i, run('메모 %d' % i))

        def start(i):
            return '<w:commentRangeStart w:id="%d"/>' % i

        def end(i):
            return '<w:commentRangeEnd w:id="%d"/><w:r><w:commentReference w:id="%d"/></w:r>' % (i, i)

        def gone(text, before=''):
            return '<w:r>%s<w:delText xml:space="preserve">%s</w:delText></w:r>' % (before, text)

        body = (
            # 메모 0: 범위의 끝을 걸쳐 지웠다. 끝 표시와 메모 표시가 지운 글 안에 있다. 범위 가운데의 지운 글에 든 탭·줄바꿈도 뺀다
            '<w:p>' + run('첫 문장. ') + start(0) + run('둘째 ') + '<w:del>' + gone('지운낱말', '<w:tab/><w:br/>') + '</w:del>' + run('문장')
            + '<w:del>' + gone('입니다.') + end(0) + gone(' 셋째') + '</w:del>' + run(' 문장.') + '</w:p>'
            # 메모 1: 범위 전체와 그 앞뒤를 지웠다. 시작·끝 표시와 메모 표시가 모두 지운 글 안에 있다
            + '<w:p>' + run('넷째 문단 ') + '<w:del>' + gone('머리. ') + start(1) + gone('다섯째.') + end(1) + gone(' 여섯째 ') + '</w:del>' + run('문장.') + '</w:p>'
            # 메모 2: 범위의 시작을 걸쳐 지웠다. 시작 표시만 지운 글 안에 있다
            + '<w:p>' + run('여덟째 ') + '<w:del>' + gone('하나. ') + start(2) + gone('여덟째 ') + '</w:del>' + run('둘.') + end(2) + run(' 셋.') + '</w:p>'
            # 메모 3: 범위와 같은 글을 지웠다. 문단에 남은 글이 없다
            + '<w:p>' + start(3) + '<w:del>' + gone('통째로 지운 문장.') + end(3) + '</w:del></w:p>'
            # 메모 4: 끝 표시가 없다(깨진 문서). 메모 5: 그 뒤의 메모
            + '<w:p>' + run('끝 표시가 없는 문단 앞. ') + start(4) + run('시작 표시 뒤의 글.') + '<w:r><w:commentReference w:id="4"/></w:r></w:p>'
            + '<w:p>' + start(5) + run('뒤 메모의 구절') + end(5) + run(' 그 뒤.') + '</w:p>'
            # 메모 6: 문단 밖에 범위만 있고 뒤따르는 문단이 없다
            + start(6) + '<w:commentRangeEnd w:id="6"/>')
        path = self.make(body, '', {'word/comments.xml': f'<w:comments {NS}>' + ''.join(memo(i) for i in range(7)) + '</w:comments>'})

        found = module.memo_notes(path)
        self.assertEqual([m['붙은 구절'] for m in found], ['둘째 문장', '', '둘.', '', '', '뒤 메모의 구절', ''])
        self.assertEqual([m['범위'] for m in found], [True] * 7)
        self.assertEqual([m['끝 표시 없음'] for m in found], [False, False, False, False, True, False, False])
        self.assertEqual([m['문단'] for m in found], ['첫 문장. 둘째 문장 문장.', '넷째 문단 문장.', '여덟째 둘. 셋.', '',
                                                    '끝 표시가 없는 문단 앞. 시작 표시 뒤의 글.', '뒤 메모의 구절 그 뒤.', ''])
        self.assertEqual([m['문단 없음'] for m in found], [False, False, False, False, False, False, True])
        self.assertEqual([m['자리'] for m in found], ['본문'] * 7)
        self.assertNotIn('지운', module.review_text(path)[0])      # 검토 대상 글은 종전대로 지운 글을 뺀다

        written = module.memo_text(path.name, found)
        self.assertIn('## 메모 1 — 담당자\n\n붙은 구절(본문):\n> 둘째 문장\n\n메모가 달린 문단:\n> 첫 문장. 둘째 문장 문장.\n', written)
        self.assertIn('## 메모 4 — 담당자\n\n붙은 구절(본문):\n> (범위는 있으나 그 안에 글로 뽑힌 것이 없다. 변경 추적으로 지운 글, 그림·공백, 각주·미주 번호만 든 범위이거나 '
                      '빈 범위일 수 있다. 무엇에 단 메모인지는 Word 에서 따로 확인한다)\n\n메모가 달린 문단:\n'
                      '> (달린 문단에 글로 뽑힌 것이 없다. 지운 글이나 그림만 든 문단일 수 있다)\n', written)
        self.assertIn('## 메모 5 — 담당자\n\n붙은 구절(본문):\n> (범위의 끝 표시(w:commentRangeEnd)를 찾지 못하여 구절을 적지 않았다. 무엇에 단 메모인지는 Word 에서 따로 확인한다)\n\n'
                      '메모가 달린 문단:\n> 끝 표시가 없는 문단 앞. 시작 표시 뒤의 글.\n', written)
        self.assertIn('## 메모 7 — 담당자\n\n붙은 구절(본문):\n> (범위는 있으나', written)
        self.assertIn('메모가 달린 문단:\n> (문단을 찾지 못하였다)\n\n메모의 글:\n> 메모 6\n', written)
        self.assertNotIn('지운', written.replace('지운 글', ''))      # 지운 글의 글자는 메모 파일에도 나오지 않는다


class ReviewResultTests(unittest.TestCase):
    """워크플로 결과를 라운드 기록으로 옮기는 스크립트. 결과가 래퍼({result: …})에 싸여 와도 읽는다."""

    def test_render_keeps_votes_and_empty_reports(self):
        path = Path(__file__).parents[1] / 'scripts' / 'review_result.py'
        spec2 = importlib.util.spec_from_file_location('review_result', path)
        result = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(result)
        data = {'checked': [{'이름': '각주 1', 'checked': [{'target': '사건 표시', 'verdict': '정확', 'basis': '머리와 같다'}], 'coverage': '끝까지'},
                            {'이름': '각주 2', 'checked': None, 'coverage': '보고 없음'}],
                'serious': [{'id': 'v1-1', 'severity': '오해소지', 'where': '2항', 'text': '문장', 'problem': '문제', 'fix': '수정', 'upheld': True,
                             'upheldVotes': 2, 'voters': 3, 'votes': [{'upheld': True, 'severity': '오해소지', 'reason': '맞다'}]}],
                'minor': [{'id': 'v1-2', 'severity': '경미', 'where': '3항', 'text': '문장', 'problem': '표현', 'fix': '다듬기'}],
                'counts': {'검증자': 2, '채택': 1}}
        with tempfile.TemporaryDirectory() as tmp:
            wrapped = Path(tmp) / '결과.json'
            wrapped.write_text(__import__('json').dumps({'summary': '…', 'result': data}, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(result.load(wrapped), data)
        text = result.render(data, '제목')
        self.assertIn('### v1-1 [오해소지 → 채택 2/3] 2항', text)
        self.assertIn('- 반대 검증 1: 유지 / 오해소지 — 맞다', text)
        self.assertIn('### v1-2 [경미] 3항', text)
        self.assertIn('- [정확] 사건 표시 — 머리와 같다', text)
        self.assertIn('- 읽은 범위: 보고 없음', text)
        pending = dict(data, serious=[dict(data['serious'][0], upheld=False, 미검증=True, upheldVotes=1, voters=1)])
        self.assertIn('### v1-1 [오해소지 → 미검증 1/1] 2항', result.render(pending, '제목'))
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / '결과.json'
            bad.write_text('{"result": null}', encoding='utf-8-sig')      # BOM 이 붙은 파일, 결과가 객체가 아닌 경우
            with self.assertRaises(SystemExit):
                result.load(bad)
            for other in ('{}', '{"result": {}}', '{"status": "completed", "output": {"checked": []}}'):      # 워크플로 결과가 아닌 객체
                bad.write_text(other, encoding='utf-8')
                with self.assertRaises(SystemExit):
                    result.load(bad)
            for key in ('checked', 'serious', 'minor', 'counts'):      # 네 키 가운데 하나만 빠져도 받지 않는다
                bad.write_text(__import__('json').dumps({k: v for k, v in data.items() if k != key}, ensure_ascii=False), encoding='utf-8')
                with self.assertRaises(SystemExit):
                    result.load(bad)
        # 지적은 맞다고 보았으나 정도를 낮게 본 표는 워크플로가 기각표로 센다. 기록도 그렇게 적는다
        low = dict(data, serious=[dict(data['serious'][0], upheld=False, upheldVotes=1, votes=[
            {'upheld': True, 'severity': '오해소지', 'reason': '맞다'}, {'upheld': True, 'severity': '경미', 'reason': '가볍다'},
            {'upheld': False, 'severity': '문제없음', 'reason': '틀렸다'}])])
        text = result.render(low, '제목')
        self.assertIn('- 반대 검증 2: 기각(지적은 맞다고 보았으나 정도가 낮아 기각표로 셈) / 경미 — 가볍다', text)
        self.assertIn('- 반대 검증 3: 기각 / 문제없음 — 틀렸다', text)

    def test_main_does_not_overwrite_a_record(self):
        """이미 있는 라운드 기록은 덮어쓰지 않는다(끝에 적은 처리 기록이 사라진다). --force 를 붙여야 덮어쓴다."""
        import contextlib, io, json, sys
        from unittest import mock
        path = Path(__file__).parents[1] / 'scripts' / 'review_result.py'
        spec2 = importlib.util.spec_from_file_location('review_result', path)
        result = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(result)
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / '결과.json', Path(tmp) / '결과_1차.md'
            pending = {'id': 'v2-1', 'severity': '오류', 'where': '3항', 'upheld': False, '미검증': True, 'upheldVotes': 1, 'voters': 1}
            src.write_text(json.dumps({'checked': [{'이름': '각주 2', 'checked': None, 'coverage': '보고 없음'}], 'serious': [pending],
                                       'minor': [], 'counts': {'채택': 0, '미검증': 1}}, ensure_ascii=False), encoding='utf-8')

            def call(*extra):
                argv = ['review_result.py', str(src), '--out', str(out), *extra]
                screen = io.StringIO()
                with mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(screen), contextlib.redirect_stderr(io.StringIO()):
                    result.main()
                return screen.getvalue()

            shown = call()      # 라운드가 끝나지 않았다는 두 줄을 화면에 알린다
            self.assertIn('보고가 비어 있는 검증자(다시 맡긴다): 각주 2', shown)
            self.assertIn('미검증(반대 검증을 다시 돌린다) v2-1', shown)
            out.write_text(out.read_text(encoding='utf-8') + '처리: 반영함', encoding='utf-8')
            with self.assertRaises(SystemExit):
                call()
            self.assertIn('처리: 반영함', out.read_text(encoding='utf-8'))
            call('--force')
            self.assertNotIn('처리: 반영함', out.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
