"""mail_draft.py — 가짜 Microsoft Graph 와 가짜 로그인 도구로 초안 만들기를 시험한다(네트워크를 쓰지 않는다).

메일·사람·주소는 모두 지어낸 값이다. 실제 메일함에서 본 이름·주소·사건번호를 여기에 옮기지 않는다(git 에 올라간다).
"""
import base64
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location('mail_draft', Path(__file__).parents[1] / 'scripts' / 'mail_draft.py')
draft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(draft)

GRAPH = draft.GRAPH
ME = 'me@example.com'
UPLOAD = 'https://outlook.office.com/api/v2.0/Users(1)/Messages(D1)/AttachmentSessions(S1)?authtoken=xyz'


def person(name, addr):
    return {'emailAddress': {'name': name, 'address': addr}}


SENT = {'id': 'AAMkADsent=draft-test-0001', 'subject': 'Re: 준비서면 확인 요청', 'from': person('나', ME),
        'toRecipients': [person('갑 변호사', 'a@example.com')],
        'ccRecipients': [person('을 변호사', 'b@example.com'), person('병 변호사', 'c@example.com')]}
RECEIVED = {'id': 'AAMkADrecv-draft-test-0002', 'subject': '자료 송부', 'from': person('정 부장', 'boss@example.com'),
            'toRecipients': [person('나', ME), person('무 과장', 'x@example.com')],
            'ccRecipients': [person('나', ME), person('기 대리', 'y@example.com')], 'sentDateTime': '2026-11-05T23:55:20Z'}
SIG = ('<div id="Signature" class="elementToProof"><div style="font-size:11pt"><br /></div>'
       '<div style="font-size:11pt">감사합니다.</div><div><div>홍길동 올림</div></div></div>')
QUOTE = ('<html><head><meta charset="utf-8"></head><body><hr style="display:inline-block;width:98%" />'      # createReply 가 주는 꼴
         '<div id="divRplyFwdMsg"><b>From:</b> 정 부장 &lt;boss@example.com&gt;<br /><b>Sent:</b> Thursday, 05 November 2026 23:55:20<br />'
         '<b>To:</b> 나 &lt;me@example.com&gt;<br /><b>Subject:</b> 자료 송부 <div> </div></div>'
         '<div><div id="x_divRplyFwdMsg">앞선 인용</div>원문 인용</div></body></html>')
FWD = ('<html><head><meta charset="utf-8"></head><body><div><br></div><hr style="display:inline-block;width:98%" tabindex="-1">'
       '<div id="divRplyFwdMsg" dir="ltr"><font face="Calibri, sans-serif" color="#000000" style="font-size:11pt">'
       '<b>From:</b> 정 부장 &lt;boss@example.com&gt;<br><b>Sent:</b> Friday, November 6, 2026 8:55 AM<br>'
       '<b>To:</b> 나 &lt;me@example.com&gt;<br><b>Subject:</b> 자료 송부</font><div>&nbsp;</div></div>'
       '<div><div id="x_divRplyFwdMsg">앞선 인용</div>원문 본문</div></body></html>')


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeGraph:
    """초안 만들기에 쓰는 Microsoft Graph 몇 갈래만 흉내 낸다."""

    def __init__(self, signature=True):
        self.seen, self.patch, self.created = [], None, None
        self.attachments, self.uploads, self.ranges = {}, bytearray(), []
        self.signature = signature

    def ok(self, data, code=200):
        return Response(b'' if data is None else json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def __call__(self, request, timeout=None):
        method, url = request.get_method(), request.full_url
        self.seen.append((method, url))
        if url.startswith(UPLOAD.split('?')[0]):
            assert method == 'PUT' and request.get_header('Authorization') is None, '업로드 주소에는 토큰을 붙이지 않는다'
            m = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', request.get_header('Content-range'))
            start, end, total = map(int, m.groups())
            assert start == len(self.uploads), '조각은 이어서 올린다'
            self.uploads += request.data
            self.ranges.append((start, end, total))
            if len(self.uploads) == total:
                self.attachments['L1'] = {'id': 'L1', 'name': self.upload_name, 'data': bytes(self.uploads)}
                return self.ok(None, 201)
            return self.ok({'nextExpectedRanges': [f'{end + 1}-']})
        assert url.startswith(GRAPH + '/') and request.get_header('Authorization') == 'Bearer T', url
        split = urllib.parse.urlsplit(url[len(GRAPH):])
        path = [urllib.parse.unquote(s) for s in split.path.split('/')[1:]]
        body = json.loads(request.data.decode('utf-8')) if request.data else None
        if path[:3] == ['me', 'mailFolders', 'sentitems']:
            plain_mail = {'body': {'content': '<html><body>서명 없는 메일</body></html>'}}
            sig = self.signature if isinstance(self.signature, str) else SIG      # 문자열을 주면 그 서명을 쓴다
            signed = {'body': {'content': f'<html><body><div>본문</div>{sig}<hr><div id="x_Signature">옛 서명</div></body></html>'}}
            return self.ok({'value': [plain_mail] + ([signed] if self.signature else [])})
        if path == ['me', 'messages'] and method == 'POST':
            self.created = body
            return self.ok({'id': 'D1', **body}, 201)
        msg = {SENT['id']: SENT, RECEIVED['id']: RECEIVED}.get(path[2])
        if msg and method == 'GET':
            return self.ok(msg)
        if msg and path[3:] in (['createReplyAll'], ['createReply']) and method == 'POST':
            self.created = {'kind': path[3]}
            return self.ok({'id': 'D1', 'subject': 'RE: ' + msg['subject'], 'body': {'contentType': 'html', 'content': QUOTE}}, 201)
        if msg and path[3:] == ['createForward'] and method == 'POST':
            self.created = {'kind': path[3]}
            self.attachments['F1'] = {'id': 'F1', 'name': '원문 첨부.pdf', 'data': b'%PDF-1.7 original'}   # 원 메일의 첨부가 따라온다
            return self.ok({'id': 'D1', 'subject': 'FW: ' + msg['subject'], 'body': {'contentType': 'html', 'content': FWD}}, 201)
        assert path[2] == 'D1', path
        rest = path[3:]
        if not rest and method == 'PATCH':
            self.patch = body
            return self.ok({'id': 'D1'})
        if not rest and method == 'GET':
            fields = self.patch or self.created or {}
            return self.ok({'id': 'D1', 'subject': fields.get('subject'), 'isDraft': True, 'hasAttachments': bool(self.attachments),
                            'toRecipients': fields.get('toRecipients'), 'ccRecipients': fields.get('ccRecipients')})
        if rest == ['attachments'] and method == 'POST':
            n = f'S{len(self.attachments) + 1}'
            self.attachments[n] = {'id': n, 'name': body['name'], 'data': base64.b64decode(body['contentBytes'])}
            return self.ok({'id': n}, 201)
        if rest == ['attachments', 'createUploadSession'] and method == 'POST':
            self.upload_name = body['AttachmentItem']['name']
            assert body['AttachmentItem']['size'] > draft.SMALL
            return self.ok({'uploadUrl': UPLOAD})
        if rest == ['attachments'] and method == 'GET':
            return self.ok({'value': [{'id': a['id'], 'name': a['name'], 'size': len(a['data']), 'isInline': False}
                                      for a in self.attachments.values()]})
        if len(rest) == 3 and rest[0] == 'attachments' and rest[2] == '$value':
            return Response(self.attachments[rest[1]]['data'])
        raise AssertionError(f'예상하지 못한 요청: {method} {url}')


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.small = self.dir / '수정안.pdf'
        self.small.write_bytes(b'%PDF-1.7 small')
        self.large = self.dir / '준비서면(3)_Rev_2.docx'
        self.large.write_bytes(os.urandom(draft.SMALL + 700_000))
        self.body = self.dir / '본문.txt'
        self.body.write_text('변호사님,\n\n수정본을 <다시> 보냅니다.\n', encoding='utf-8')
        self.graph = FakeGraph()
        self.patches = [mock.patch.object(draft, 'OPENER', self.graph),
                        mock.patch.object(draft, 'session', lambda: ('T', ME))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_cmd(self, fn, *args, **kw):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = fn(*args, **kw)
        return code, out.getvalue(), err.getvalue()

    def emails(self, entries):
        return [e['emailAddress']['address'] for e in entries]

    def test_reply_all_to_my_sent_mail_goes_back_to_its_recipients_with_both_attachments(self):
        code, out, err = self.run_cmd(draft.reply, 'mail:///messages/AAMkADsent%3Ddraft-test-0001', str(self.body), [self.small, self.large],
                                      everyone=True, prefix='(수정 송부) ')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.graph.created, {'kind': 'createReplyAll'})
        p = self.graph.patch
        self.assertEqual(p['subject'], '(수정 송부) Re: 준비서면 확인 요청')      # 'Re:' 를 겹치지 않는다
        self.assertEqual(self.emails(p['toRecipients']), ['a@example.com'])
        self.assertEqual(self.emails(p['ccRecipients']), ['b@example.com', 'c@example.com'])
        self.assertEqual(p['toRecipients'][0]['emailAddress']['name'], '갑 변호사')
        content = p['body']['content']
        top = content.index('<body>') + len('<body>')
        self.assertTrue(content[top:].startswith('<div class="elementToProof"'), content[:200])
        self.assertLess(content.index('변호사님,'), content.index('감사합니다.'))
        self.assertLess(content.index('홍길동 올림'), content.index('원문 인용'))       # 서명은 인용 위에, 통째로
        self.assertIn('수정본을 &lt;다시&gt; 보냅니다.', content)
        self.assertNotIn('옛 서명', content)
        names = {a['name']: a['data'] for a in self.graph.attachments.values()}
        self.assertEqual(names['수정안.pdf'], self.small.read_bytes())
        self.assertEqual(names['준비서면(3)_Rev_2.docx'], self.large.read_bytes())
        self.assertEqual(len(self.graph.ranges), 2)                                 # 3MB 넘는 파일은 나누어 올렸다
        self.assertTrue(all((e - s + 1) % (320 * 1024) == 0 for s, e, t in self.graph.ranges[:-1]))
        self.assertEqual(out.count('같음'), 2)
        self.assertIn('받는 사람: 갑 변호사 <a@example.com>', out)
        self.assertIn('주소: mail:///messages/D1', out)

    def test_reply_to_someone_elses_mail_goes_to_sender_and_drops_my_address(self):
        to, cc = draft.recipients(RECEIVED, 'ME@example.com', everyone=True)
        self.assertEqual(self.emails(to), ['boss@example.com', 'x@example.com'])
        self.assertEqual(self.emails(cc), ['y@example.com'])
        to, cc = draft.recipients(RECEIVED, ME, everyone=False)
        self.assertEqual((self.emails(to), cc), (['boss@example.com'], []))
        to, cc = draft.recipients(SENT, ME, everyone=False)
        self.assertEqual((self.emails(to), cc), (['a@example.com'], []))
        code, out, err = self.run_cmd(draft.reply, 'AAMkADrecv-draft-test-0002', str(self.body), [], everyone=False)
        self.assertEqual((code, self.graph.created), (0, {'kind': 'createReply'}))
        self.assertEqual(self.graph.patch['subject'], 'Re: 자료 송부')

    def test_reply_header_is_put_in_korean_with_korean_time(self):
        """createReply 가 넣는 영어 머리(From:·Sent:, 보낸 시각은 세계 표준시)를 화면에서 회신할 때의 한글 머리로 바꾼다
        (2026. 11. 9. 의뢰인 회신 초안에 아홉 시간 이른 시각이 들어감)."""
        code, out, err = self.run_cmd(draft.reply, 'AAMkADrecv-draft-test-0002', str(self.body), [], everyone=False)
        self.assertEqual(code, 0, out + err)
        self.assertNotIn('원문 머리를 찾지 못해', err)
        content = self.graph.patch['body']['content']
        self.assertIn('<div id="divRplyFwdMsg"><b>보낸 사람:</b> 정 부장 &lt;boss@example.com&gt;<br />'
                      '<b>보낸 날짜:</b> 2026년 11월 6일 금요일 오전 8:55<br />'
                      '<b>받는 사람:</b> 나 &lt;me@example.com&gt;; 무 과장 &lt;x@example.com&gt;<br />'
                      '<b>참조:</b> 나 &lt;me@example.com&gt;; 기 대리 &lt;y@example.com&gt;<br /><b>제목:</b> 자료 송부', content)
        self.assertNotIn('From:', content)
        self.assertNotIn('Sent:', content)
        self.assertLess(content.index('홍길동 올림'), content.index('<b>보낸 사람:</b>'))
        self.assertLess(content.index('<b>보낸 사람:</b>'), content.index('원문 인용'))
        self.assertIn('<div><div id="x_divRplyFwdMsg">앞선 인용</div>원문 인용</div>', content)    # 원문 속 앞선 머리는 건드리지 않는다
        with mock.patch.dict(globals(), {'QUOTE': '<html><body><hr><div>머리 없는 인용</div></body></html>'}):
            code, out, err = self.run_cmd(draft.reply, 'AAMkADrecv-draft-test-0002', str(self.body), [])
        self.assertEqual(code, 0, err)
        self.assertIn('원문 머리를 찾지 못해', err)
        self.assertIn('머리 없는 인용', self.graph.patch['body']['content'])

    def test_recipients_and_subject_can_be_given(self):
        code, out, err = self.run_cmd(draft.reply, 'AAMkADsent=draft-test-0001', str(self.body), [], everyone=True, subject='제목 통째로',
                                      to=['z@example.com'], cc=['w@example.com'])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.graph.patch['subject'], '제목 통째로')
        self.assertEqual(self.emails(self.graph.patch['toRecipients']), ['z@example.com'])
        self.assertEqual(self.emails(self.graph.patch['ccRecipients']), ['w@example.com'])

    def test_reply_subject(self):
        self.assertEqual(draft.reply_subject('Re: 가', '(수정 송부) '), '(수정 송부) Re: 가')
        self.assertEqual(draft.reply_subject('RE: 가'), 'RE: 가')
        self.assertEqual(draft.reply_subject('회신: 가'), '회신: 가')
        self.assertEqual(draft.reply_subject('Fw: 가'), 'Re: Fw: 가')
        self.assertEqual(draft.reply_subject('가', '[긴급] '), '[긴급] Re: 가')

    def test_signature_is_taken_whole_and_missing_signature_is_reported(self):
        self.assertEqual(draft.signature_of(f'<p>앞</p>{SIG}<div>뒤</div>'), SIG)
        self.assertIsNone(draft.signature_of('<div id="x_Signature">인용 속 서명</div>'))
        self.graph.signature = False
        code, out, err = self.run_cmd(draft.reply, 'AAMkADsent=draft-test-0001', str(self.body), [], everyone=True)
        self.assertEqual(code, 0)
        self.assertIn('서명을 찾지 못해', err)
        self.assertNotIn('Signature', self.graph.patch['body']['content'])

    def test_no_signature_option_skips_the_sent_items_lookup(self):
        code, out, err = self.run_cmd(draft.reply, 'AAMkADsent=draft-test-0001', str(self.body), [], signature=False)
        self.assertEqual(code, 0)
        self.assertFalse(any('sentitems' in url for _, url in self.graph.seen))

    def test_body_lines_are_escaped_and_blank_lines_kept(self):
        page = draft.body_html('\n첫 줄 & <b>\n\n끝\n\n')
        self.assertEqual(page.count('<div class="elementToProof"'), 3)
        self.assertIn('첫 줄 &amp; &lt;b&gt;', page)
        self.assertIn('<br />', page)
        self.assertIn('Malgun Gothic', page)

    def test_double_star_marks_bold_and_the_rest_stays_escaped(self):
        """'**…**' 는 굵게 넣고 별표는 지운다. 굵게 안팎의 글은 이스케이프하고, 짝이 없는 '**' 는 글자로 남긴다
        (2026. 11. 9. 김천에너지서비스 배당 회신 — 담당자가 항목 제목을 Outlook 에서 굵게 고쳐 보냄)."""
        page = draft.body_html('**1. 검토 요지**\n\n앞 **가운데 & <글>** 뒤\n별표 ** 하나')
        self.assertIn('<b>1. 검토 요지</b>', page)
        self.assertIn('앞 <b>가운데 &amp; &lt;글&gt;</b> 뒤', page)
        self.assertIn('별표 ** 하나', page)
        self.assertNotIn('**1.', page)
        self.assertEqual(page.count('<div class="elementToProof"'), 4)

    def test_runs_of_spaces_survive_html(self):
        """HTML 은 이어진 빈칸을 하나로 줄이므로 '- 아  래 -' 의 두 칸이 그대로 보이게 &nbsp; 를 넣는다(2026. 11. 9.)."""
        self.assertIn('- 아&nbsp; 래 -', draft.body_html('- 아  래 -'))
        self.assertIn('한 칸 그대로', draft.body_html('한 칸 그대로'))

    def test_one_blank_line_between_body_and_signature(self):
        """서명이 빈 줄로 시작하지 않으면 본문 끝에 빈 줄 하나를 넣는다(2026. 11. 5. 삼양인터내셔날 내부 회신에서 '감사합니다.'가 본문에 붙었다)."""
        빈 = '<br /></div>'
        붙은 = '<div id="Signature" class="elementToProof"><div style="font-size:11pt">감사합니다.</div><div>홍길동 올림</div></div>'
        self.assertTrue(draft.sign_gap('변호사님,\n\n드립니다.\n', 붙은).endswith(빈))
        self.assertEqual(draft.sign_gap('변호사님,\n\n드립니다.\n', SIG), '')               # 서명이 빈 줄로 시작한다
        self.assertEqual(draft.sign_gap('변호사님,\n\n드립니다.\n \n', 붙은), '')            # 본문이 빈 줄로 끝난다
        self.assertEqual(draft.sign_gap('변호사님,', None), '')
        self.assertEqual(draft.sign_gap('변호사님,', '<div id="Signature"><p class="MsoNormal">&nbsp;</p><p>감사합니다.</p></div>'), '')
        self.graph.signature = 붙은
        code, out, err = self.run_cmd(draft.reply, 'AAMkADsent=draft-test-0001', str(self.body), [], everyone=True)
        content = self.graph.patch['body']['content']
        self.assertIn('보냅니다.</div><div class="elementToProof" style="' + draft.STYLE + '"><br /></div><div id="Signature"', content)

    def test_new_draft(self):
        code, out, err = self.run_cmd(draft.new, ['a@example.com'], ['b@example.com'], '새 제목', str(self.body), [self.small])
        self.assertEqual(code, 0, err)
        made = self.graph.created
        self.assertEqual(made['subject'], '새 제목')
        self.assertEqual(self.emails(made['toRecipients']), ['a@example.com'])
        self.assertEqual(self.emails(made['ccRecipients']), ['b@example.com'])
        self.assertIn('홍길동 올림', made['body']['content'])
        self.assertEqual(out.count('같음'), 1)

    def test_forward_goes_to_the_people_of_an_earlier_mail_with_the_header_in_korean(self):
        code, out, err = self.run_cmd(draft.forward, 'AAMkADrecv-draft-test-0002', str(self.body), [],
                                      same_as='mail:///messages/AAMkADsent%3Ddraft-test-0001')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.graph.created, {'kind': 'createForward'})
        p = self.graph.patch
        self.assertEqual(p['subject'], 'Fw: 자료 송부')
        self.assertEqual(self.emails(p['toRecipients']), ['a@example.com'])
        self.assertEqual(self.emails(p['ccRecipients']), ['b@example.com', 'c@example.com'])
        self.assertEqual(p['ccRecipients'][0]['emailAddress']['name'], '을 변호사')
        content = p['body']['content']
        top = content.index('<body>') + len('<body>')
        self.assertTrue(content[top:].startswith('<div class="elementToProof"'), content[:200])
        self.assertLess(content.index('변호사님,'), content.index('홍길동 올림'))
        self.assertLess(content.index('홍길동 올림'), content.index('<b>보낸 사람:</b>'))
        self.assertIn('<div id="divRplyFwdMsg"><b>보낸 사람:</b> 정 부장 &lt;boss@example.com&gt;<br />'
                      '<b>보낸 날짜:</b> 2026년 11월 6일 금요일 오전 8:55<br />'
                      '<b>받는 사람:</b> 나 &lt;me@example.com&gt;; 무 과장 &lt;x@example.com&gt;<br />'
                      '<b>참조:</b> 나 &lt;me@example.com&gt;; 기 대리 &lt;y@example.com&gt;<br /><b>제목:</b> 자료 송부', content)
        self.assertNotIn('From:', content)
        self.assertIn('<div><div id="x_divRplyFwdMsg">앞선 인용</div>원문 본문</div>', content)    # 원문 속 앞선 머리는 건드리지 않는다
        self.assertIn('첨부  원문 첨부.pdf', out)                                                # 원 메일의 첨부가 붙어 있다

    def test_forward_recipients_can_be_given_and_are_required(self):
        code, out, err = self.run_cmd(draft.forward, 'AAMkADrecv-draft-test-0002', str(self.body), [], to=['z@example.com'],
                                      same_as='AAMkADsent=draft-test-0001')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.emails(self.graph.patch['toRecipients']), ['z@example.com'])          # --to 가 앞선다
        self.assertEqual(self.emails(self.graph.patch['ccRecipients']), ['b@example.com', 'c@example.com'])
        self.graph.seen.clear()
        code, out, err = self.run_cmd(draft.main, ['forward', 'AAMkADrecv-draft-test-0002', '--body', str(self.body)])
        self.assertEqual(code, 1)
        self.assertIn('받는 사람', err)
        self.assertEqual(self.graph.seen, [])

    def test_forward_subject_and_korean_date(self):
        self.assertEqual(draft.forward_subject('가'), 'Fw: 가')
        self.assertEqual(draft.forward_subject('FW: 가'), 'FW: 가')
        self.assertEqual(draft.forward_subject('전달: 가'), '전달: 가')
        self.assertEqual(draft.forward_subject('Re: 가', '[참고] '), '[참고] Fw: Re: 가')
        self.assertEqual(draft.korean_date('2026-11-05T00:23:25Z'), '2026년 11월 5일 목요일 오전 9:23')
        self.assertEqual(draft.korean_date('2026-11-05T03:05:00Z'), '2026년 11월 5일 목요일 오후 12:05')
        self.assertEqual(draft.korean_date('2026-11-05T15:30:00Z'), '2026년 11월 6일 금요일 오전 12:30')
        page, swapped = draft.korean_head('<body><div>머리 없는 본문</div></body>', RECEIVED)
        self.assertEqual((page, swapped), ('<body><div>머리 없는 본문</div></body>', False))

    def test_check_reports_a_different_file(self):
        self.run_cmd(draft.reply, 'AAMkADsent=draft-test-0001', str(self.body), [self.small])
        self.small.write_bytes(b'%PDF-1.7 changed later')
        code, out, err = self.run_cmd(draft.check, 'mail:///messages/D1', [str(self.small)])
        self.assertEqual(code, 1)
        self.assertIn('다름  수정안.pdf', out)

    def test_requests_never_send_move_or_delete_and_stay_on_microsoft_hosts(self):
        for method, target in (('POST', '/me/messages/D1/send'), ('POST', '/me/messages/D1/move'), ('POST', '/me/messages/D1/reply'),
                               ('POST', '/me/messages/D1/replyAll'), ('POST', '/me/messages/D1/forward'),
                               ('DELETE', '/me/messages/D1'), ('PUT', 'https://outlook.office.com.example.com/upload'),
                               ('GET', 'https://example.com/me')):
            with self.assertRaises(draft.MailError, msg=f'{method} {target}'):
                draft.request(method, target, 'T', {})
        self.assertFalse(any(m in ('DELETE',) or re.search(r'/(send|move)$', u) for m, u in self.graph.seen))

    def test_missing_files_are_refused_before_anything_is_made(self):
        code, out, err = self.run_cmd(draft.main, ['reply', 'AAMkADsent=draft-test-0001', '--body', str(self.body), '--attach', str(self.dir / '없음.pdf')])
        self.assertEqual(code, 1)
        self.assertIn('붙일 파일이 없습니다', err)
        self.assertEqual(self.graph.seen, [])


class FakeApp:
    def __init__(self, accounts=(), silent=None, interactive=None):
        self.accounts, self.silent_result, self.interactive, self.scopes = list(accounts), silent, interactive, []

    def get_accounts(self):
        return self.accounts

    def acquire_token_silent(self, scopes, account):
        self.scopes.append(('silent', scopes))
        return self.silent_result

    def acquire_token_interactive(self, scopes, **kw):
        self.scopes.append(('interactive', scopes))
        return self.interactive


class LoginTests(unittest.TestCase):
    def test_write_permission_is_asked_separately_from_mail_attach(self):
        self.assertEqual(draft.SCOPES, ['Mail.ReadWrite'])
        self.assertEqual(draft.ma.SCOPES, ['Mail.Read'])                            # 첨부 받기는 그대로 읽기 전용
        with mock.patch.object(draft, 'app', lambda: FakeApp(accounts=[{'username': ME}], silent={'access_token': 'T1'})):
            self.assertEqual(draft.session(), ('T1', ME))
        with mock.patch.object(draft, 'app', lambda: FakeApp()):
            with self.assertRaises(draft.NeedLogin) as caught:
                draft.session()
        self.assertEqual(caught.exception.code, 3)
        self.assertIn('mail_draft.py login', str(caught.exception))
        fake = FakeApp(interactive={'access_token': 'T', 'id_token_claims': {'preferred_username': ME}})
        out = io.StringIO()
        with mock.patch.object(draft, 'app', lambda: fake), redirect_stdout(out):
            self.assertEqual(draft.login(), 0)
        self.assertEqual(fake.scopes[-1], ('interactive', draft.ma.LOGIN_SCOPES))       # 공통 도구의 권한을 한 번에 묻는다
        self.assertIn('Mail.ReadWrite', draft.ma.LOGIN_SCOPES)
        self.assertIn(ME, out.getvalue())

    def test_admin_approval_message_names_the_write_permission(self):
        text = draft.explain({'error': 'consent_required', 'error_description': 'AADSTS65001: consent'})
        self.assertIn('메일 쓰기(Mail.ReadWrite)', text)
        self.assertIn('화면 제어', text)


if __name__ == '__main__':
    unittest.main()
