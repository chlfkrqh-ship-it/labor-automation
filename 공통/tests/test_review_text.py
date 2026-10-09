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
    def make(self, body, footnotes):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / '검토.docx'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', f'<w:document {NS}><w:body>{body}</w:body></w:document>')
            z.writestr('word/footnotes.xml', f'<w:footnotes {NS}>{footnotes}</w:footnotes>')
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
