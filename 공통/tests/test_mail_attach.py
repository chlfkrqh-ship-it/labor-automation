"""mail_attach.py — 가짜 Microsoft Graph 와 가짜 로그인 도구로 첨부 받기를 시험한다(네트워크를 쓰지 않는다).

메일·사람·사건은 모두 지어낸 값이다. 실제 메일함에서 본 이름·주소·사건번호를 여기에 옮기지 않는다(git 에 올라간다).
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unicodedata
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location('mail_attach', Path(__file__).parents[1] / 'scripts' / 'mail_attach.py')
mail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mail)

GRAPH = mail.GRAPH
HAS_MSAL = importlib.util.find_spec('msal_extensions') is not None
CASE = '1_검토의견/사건/가나상사_취업규칙'


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


M1 = {'id': 'AAMkADm1-x_y=', 'subject': '[서울2026부해1] 심문일정 통지',
      'from': {'emailAddress': {'name': '홍길동', 'address': 'sender@example.com'}},
      'receivedDateTime': '2026-10-14T00:38:00Z', 'internetMessageId': '<notice-1@example.com>', 'hasAttachments': True}
M2 = {'id': 'AAMkADm2-no-attachments', 'subject': '안부', 'from': {'emailAddress': {'name': '김철수', 'address': 'k@example.com'}},
      'receivedDateTime': '2026-10-15T05:00:00Z', 'internetMessageId': '<plain@example.com>', 'hasAttachments': False}
ATTACHMENTS = [
    {'@odata.type': '#microsoft.graph.fileAttachment', 'id': 'A1', 'name': '심문일정 통지.pdf', 'isInline': False},
    {'@odata.type': '#microsoft.graph.fileAttachment', 'id': 'A2=', 'name': unicodedata.normalize('NFD', '참석자 명단.hwpx'),
     'isInline': False},                                # 맥에서 보낸 이름처럼 자모가 풀려 있다
    {'@odata.type': '#microsoft.graph.fileAttachment', 'id': 'A3', 'name': 'image001.png', 'isInline': True},
    {'@odata.type': '#microsoft.graph.referenceAttachment', 'id': 'A4', 'name': '공유 문서.docx', 'isInline': False},
    {'@odata.type': '#microsoft.graph.itemAttachment', 'id': 'A5', 'name': 'RE: 위임장 회신', 'contentType': None,
     'isInline': False},
]
CONTENT = {'A1': b'%PDF-1.7 notice', 'A2=': b'PK\x03\x04hwpx', 'A3': b'\x89PNG', 'A5': b'MIME-Version: 1.0\r\n\r\nreply'}
MIME = b'MIME-Version: 1.0\r\nSubject: notice\r\n\r\nbody'


class FakeGraph:
    """Microsoft Graph 의 메일 몇 갈래만 흉내 낸다. 첨부 목록은 세 개씩 나누어 다음 쪽 주소를 붙인다."""

    def __init__(self):
        self.seen = []
        self.status = None                              # 정하면 모든 요청이 그 HTTP 오류로 끝난다
        self.no_select = False                          # 첨부 목록에서 $select 를 거절하는 서버

    def __call__(self, request, timeout=None):
        assert request.full_url.startswith(GRAPH + '/'), request.full_url
        assert request.get_header('Authorization') == 'Bearer T'
        split = urllib.parse.urlsplit(request.full_url[len(GRAPH):])
        path = [urllib.parse.unquote(s) for s in split.path.split('/')[1:]]
        query = dict(urllib.parse.parse_qsl(split.query))
        self.seen.append((path, query))
        if self.status:
            raise self.error(self.status, '거절')
        assert path[:2] == ['me', 'messages'], path
        if len(path) == 2:
            hits = [m for m in (M1, M2) if query.get('$filter') == f"internetMessageId eq '{m['internetMessageId']}'"]
            return self.json({'value': hits})
        message = {M1['id']: M1, M2['id']: M2}.get(path[2])
        if message is None:
            raise self.error(404, 'The specified object was not found in the store.')
        rest = path[3:]
        if not rest:
            return self.json(message)
        if rest == ['$value']:
            return Response(MIME)
        items = ATTACHMENTS if message is M1 else []
        if rest == ['attachments']:
            if self.no_select and '$select' in query:
                raise self.error(400, 'Invalid $select')
            start = int(query.get('$skiptoken', 0))
            page = {'value': [dict(a) for a in items[start:start + 3]]}
            if start + 3 < len(items):
                page['@odata.nextLink'] = f"{GRAPH}/me/messages/{urllib.parse.quote(message['id'], safe='')}/attachments?$skiptoken={start + 3}"
            return self.json(page)
        if rest[0] == 'attachments' and len(rest) == 3 and rest[2] == '$value' and rest[1] in CONTENT:
            return Response(CONTENT[rest[1]])
        raise self.error(404, 'not found')

    @staticmethod
    def json(data):
        return Response(json.dumps(data).encode('utf-8'))

    @staticmethod
    def error(code, message):
        return urllib.error.HTTPError(GRAPH, code, 'error', {}, io.BytesIO(json.dumps({'error': {'message': message}}).encode()))


class GetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'root'
        self.root.mkdir()
        self.graph = FakeGraph()
        self.patches = [mock.patch.object(mail, 'OPENER', self.graph), mock.patch.object(mail, 'token', lambda: 'T')]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_get(self, ref, to=CASE, **kw):
        out = io.StringIO()
        with redirect_stdout(out):
            code = mail.get(ref, to, root=self.root, **kw)
        return code, out.getvalue()

    def names(self, to=CASE):
        return sorted(p.name for p in (self.root / to).iterdir())

    def test_all_attachments_are_saved_and_inline_pictures_and_links_skipped(self):
        code, out = self.run_get(f"mail:///messages/{urllib.parse.quote(M1['id'], safe='')}")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.names(), sorted(['심문일정 통지.pdf', '참석자 명단.hwpx', 'RE_ 위임장 회신.eml']))
        folder = self.root / CASE
        self.assertEqual((folder / '심문일정 통지.pdf').read_bytes(), CONTENT['A1'])
        self.assertEqual((folder / '참석자 명단.hwpx').read_bytes(), CONTENT['A2='])      # 이름은 NFC 로 붙여 저장
        self.assertEqual((folder / 'RE_ 위임장 회신.eml').read_bytes(), CONTENT['A5'])
        self.assertIn('메일: [서울2026부해1] 심문일정 통지 | 홍길동 <sender@example.com> | 2026. 10. 14. 09:38', out)
        self.assertIn('건너뜀  image001.png — 본문에 박힌 그림', out)
        self.assertIn('건너뜀  공유 문서.docx — 링크 첨부', out)
        self.assertIn('받은 파일 3개.', out)
        self.assertTrue(any(q.get('$skiptoken') == '3' for _, q in self.graph.seen))    # 다음 쪽까지 읽었다

    def test_attachment_list_without_select_support(self):
        self.graph.no_select = True
        code, out = self.run_get(M1['internetMessageId'], names=['통지'])
        self.assertEqual((code, self.names()), (0, ['심문일정 통지.pdf']), out)

    def test_attachment_address_gets_only_that_one_even_if_inline(self):
        code, out = self.run_get(f"mail:///messages/{urllib.parse.quote(M1['id'], safe='')}/attachments/A3")
        self.assertEqual((code, self.names()), (0, ['image001.png']), out)

    def test_percent_encoded_attachment_address_from_connector(self):
        code, out = self.run_get(f"mail:///messages/{urllib.parse.quote(M1['id'], safe='')}/attachments/A2%3D")
        self.assertEqual((code, self.names()), (0, ['참석자 명단.hwpx']), out)

    def test_name_filter_matches_names_sent_from_a_mac(self):
        code, out = self.run_get(M1['internetMessageId'], names=['참석자'])
        self.assertEqual((code, self.names()), (0, ['참석자 명단.hwpx']), out)
        with self.assertRaises(mail.MailError) as caught:
            self.run_get(M1['internetMessageId'], names=['위임장 원본'])
        self.assertIn('심문일정 통지.pdf', str(caught.exception))                       # 있는 첨부를 알려 준다

    def test_same_file_is_not_duplicated_and_different_file_is_not_overwritten(self):
        folder = self.root / CASE
        folder.mkdir(parents=True)
        (folder / '심문일정 통지.pdf').write_bytes(CONTENT['A1'])
        (folder / '참석자 명단.hwpx').write_bytes(b'old')
        code, out = self.run_get(M1['internetMessageId'])
        self.assertEqual(code, 0, out)
        self.assertIn(f'이미 있음  {CASE}/심문일정 통지.pdf', out)
        self.assertIn(f'받음  {CASE}/참석자 명단 (2).hwpx', out)
        self.assertEqual((folder / '참석자 명단.hwpx').read_bytes(), b'old')
        self.assertIn('받은 파일 2개, 이미 있던 파일 1개.', out)
        self.assertFalse(list(folder.glob('*.part')))

    def test_eml_saves_the_mail_itself_for_evidence(self):
        code, out = self.run_get(M1['internetMessageId'], names=['통지'], eml=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.names(), sorted(['심문일정 통지.pdf', '2026-10-14_[서울2026부해1] 심문일정 통지.eml']))
        self.assertEqual((self.root / CASE / '2026-10-14_[서울2026부해1] 심문일정 통지.eml').read_bytes(), MIME)

    def test_internet_message_id_is_looked_up_by_filter(self):
        code, _ = self.run_get('<notice-1@example.com>', names=['통지'])
        self.assertEqual(code, 0)
        self.assertEqual(self.graph.seen[0][1]['$filter'], "internetMessageId eq '<notice-1@example.com>'")

    def test_mail_without_attachments_reports_nothing_received(self):
        code, out = self.run_get(M2['internetMessageId'])
        self.assertEqual(code, 1)
        self.assertIn('받은 파일이 없습니다', out)
        code, out = self.run_get(M2['internetMessageId'], eml=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.names(), ['2026-10-15_안부.eml'])

    def test_destination_inside_repository_must_be_a_case_folder(self):
        for bad in ('공통', '.', '1_검토의견/templates'):
            with self.assertRaises(mail.MailError) as caught:
                self.run_get(M1['internetMessageId'], to=bad)
            self.assertIn('사건 폴더', str(caught.exception))
        self.assertEqual(self.graph.seen, [])                                           # 메일함에 묻기 전에 막는다
        outside = Path(self.tmp.name) / '다운로드'
        code, out = self.run_get(M1['internetMessageId'], to=str(outside), names=['통지'])
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ['심문일정 통지.pdf'])
        self.assertIn(str((outside / '심문일정 통지.pdf').resolve()), out)                # 스크립트는 경로를 풀어 적는다(8.3 짧은 이름 TEMP)

    def test_moved_or_missing_mail_and_expired_login(self):
        with self.assertRaises(mail.MailError) as caught:
            self.run_get('mail:///messages/AAMkADmoved-elsewhere')
        self.assertIn('찾지 못했습니다', str(caught.exception))
        self.graph.status = 401
        with self.assertRaises(mail.NeedLogin):
            self.run_get(M1['internetMessageId'])

    def test_main_exit_codes(self):
        err = io.StringIO()
        with mock.patch.object(mail, 'token', side_effect=mail.NeedLogin('로그인 필요')), redirect_stderr(err), \
                redirect_stdout(io.StringIO()):
            code = mail.main(['--root', str(self.root), 'get', M1['internetMessageId'], '--to', CASE])
        self.assertEqual((code, err.getvalue().strip()), (3, '오류: 로그인 필요'))
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            self.assertEqual(mail.main(['--root', str(self.root), 'get', 'hello', '--to', CASE]), 1)

    def test_requests_go_only_to_microsoft_graph(self):
        with self.assertRaises(mail.MailError):
            mail.call('https://example.com/v1.0/me/messages', 'T')
        self.assertEqual(self.graph.seen, [])


class NameAndAddressTests(unittest.TestCase):
    def test_parse_ref(self):
        self.assertEqual(mail.parse_ref('mail:///messages/AAMk-x_y%3D'), ('AAMk-x_y=', None, None))
        self.assertEqual(mail.parse_ref('mail:///messages/AAMk%3D/attachments/AAMkB%3D'), ('AAMk=', 'AAMkB=', None))
        self.assertEqual(mail.parse_ref(' <a.b@example.com> '), (None, None, '<a.b@example.com>'))
        self.assertEqual(mail.parse_ref('AAMkADlkNzUxM2QyLWM2ZTMtNDJlMi1hOTk2'), ('AAMkADlkNzUxM2QyLWM2ZTMtNDJlMi1hOTk2', None, None))
        for bad in ('mail:///messages/AAMk%3D?owner=shared@example.com', 'hello', ''):
            with self.assertRaises(mail.MailError):
                mail.parse_ref(bad)

    def test_safe_name(self):
        self.assertEqual(mail.safe_name('심문:일정/통지?.pdf'), '심문_일정_통지_.pdf')
        self.assertEqual(mail.safe_name('CON.txt'), '_CON.txt')
        self.assertEqual(mail.safe_name('aux.tar.gz'), '_aux.tar.gz')
        long = mail.safe_name('가' * 300 + '.hwpx')
        self.assertEqual((len(long), long[-5:]), (120, '.hwpx'))
        self.assertEqual(mail.safe_name(' . '), '첨부')
        self.assertEqual(mail.safe_name('끝에 점. '), '끝에 점')
        self.assertTrue(unicodedata.is_normalized('NFC', mail.safe_name(unicodedata.normalize('NFD', '한글.hwp'))))


class FakeApp:
    """msal.PublicClientApplication 대신. 정해 둔 응답을 차례로 돌려준다."""

    def __init__(self, accounts=(), silent=None, interactive=None, flows=(), polls=()):
        self.accounts, self.silent_result, self.interactive = list(accounts), silent, interactive
        self.flows, self.polls, self.calls = list(flows), list(polls), []

    def get_accounts(self):
        return self.accounts

    def acquire_token_silent(self, scopes, account):
        self.calls.append('silent')
        return self.silent_result

    def acquire_token_interactive(self, scopes, **kw):
        self.calls.append(('interactive', kw))
        if isinstance(self.interactive, Exception):
            raise self.interactive
        return self.interactive

    def initiate_device_flow(self, scopes):
        self.calls.append('initiate')
        return dict(self.flows.pop(0))

    def acquire_token_by_device_flow(self, flow, exit_condition=None):
        self.calls.append(('poll', flow['user_code'], exit_condition is not None))
        return self.polls.pop(0)


class BrowserInteractionTimeoutError(RuntimeError):
    """msal 이 브라우저 로그인 시간이 지나면 내는 예외와 이름이 같다."""


OK = {'access_token': 'T', 'id_token_claims': {'preferred_username': 'tester@example.com'}}


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {'MAIL_ATTACH_HOME': self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def login(self, fake, device=False):
        out = io.StringIO()
        with mock.patch.object(mail, 'app', lambda: fake), redirect_stdout(out):
            code = mail.login(device)
        return code, out.getvalue()

    def test_token_comes_from_saved_login_or_asks_for_login(self):
        with mock.patch.object(mail, 'app', lambda: FakeApp(accounts=[{'username': 'u'}], silent={'access_token': 'T1'})):
            self.assertEqual(mail.token(), 'T1')
        with mock.patch.object(mail, 'app', lambda: FakeApp()):
            with self.assertRaises(mail.NeedLogin) as caught:
                mail.token()
        self.assertEqual(caught.exception.code, 3)
        self.assertIn('login', str(caught.exception))

    def test_browser_login(self):
        fake = FakeApp(interactive=OK)
        code, out = self.login(fake)
        self.assertEqual(code, 0)
        self.assertIn('tester@example.com', out)
        self.assertEqual(fake.calls[-1], ('interactive', {'prompt': 'select_account', 'timeout': 300}))

    def test_already_logged_in_does_not_open_browser(self):
        fake = FakeApp(accounts=[{'username': 'u'}], silent={'access_token': 'T'})
        code, out = self.login(fake)
        self.assertEqual((code, fake.calls), (0, ['silent']))
        self.assertIn('이미 로그인', out)

    def test_browser_login_timeout_and_admin_approval(self):
        with self.assertRaises(mail.MailError) as caught:
            self.login(FakeApp(interactive=BrowserInteractionTimeoutError('late')))
        self.assertIn('5분', str(caught.exception))
        refused = {'error': 'invalid_grant', 'error_description': 'AADSTS90094: The grant requires admin permission.\r\nTrace ID: x'}
        with self.assertRaises(mail.MailError) as caught:
            self.login(FakeApp(interactive=refused))
        self.assertIn('관리자의 승인', str(caught.exception))
        self.assertIn('Microsoft Graph Command Line Tools', str(caught.exception))

    def test_device_code_login_in_two_steps(self):
        flow = {'user_code': 'ABCD-1234', 'device_code': 'dc', 'verification_uri': 'https://microsoft.com/devicelogin',
                'expires_at': time.time() + 900, 'interval': 5}
        fake = FakeApp(flows=[flow], polls=[{'error': 'authorization_pending'}, OK])
        saved = Path(self.tmp.name) / 'device_flow.json'
        code, out = self.login(fake, device=True)
        self.assertEqual(code, 4)
        self.assertIn('ABCD-1234', out)
        self.assertTrue(saved.is_file())
        code, out = self.login(fake, device=True)                                       # 아직 로그인하지 않았다
        self.assertEqual(code, 4)
        self.assertIn('아직', out)
        code, out = self.login(fake, device=True)
        self.assertEqual(code, 0, out)
        self.assertFalse(saved.exists())
        self.assertEqual([c for c in fake.calls if c == 'initiate'], ['initiate'])       # 코드는 한 번만 받았다
        self.assertTrue(all(c[2] for c in fake.calls if isinstance(c, tuple) and c[0] == 'poll'))

    def test_expired_device_code_is_renewed(self):
        (Path(self.tmp.name) / 'device_flow.json').write_text(json.dumps({'user_code': 'OLD', 'expires_at': time.time() - 1}))
        fresh = {'user_code': 'NEW-CODE', 'device_code': 'dc', 'expires_at': time.time() + 900}
        code, out = self.login(FakeApp(flows=[fresh]), device=True)
        self.assertEqual(code, 4)
        self.assertIn('NEW-CODE', out)

    def test_missing_login_library_is_reported_with_install_command(self):
        with mock.patch.dict(sys.modules, {'msal_extensions': None}):
            with self.assertRaises(mail.MailError) as caught:
                mail.cache()
        self.assertIn('공통/requirements.txt', str(caught.exception))

    @unittest.skipUnless(HAS_MSAL, 'msal-extensions 가 없다(공통/requirements.txt)')
    def test_status_and_logout_use_only_the_saved_file(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(mail.status(), 3)
        from msal_extensions import FilePersistence, FilePersistenceWithDataProtection
        persistence = FilePersistenceWithDataProtection if sys.platform == 'win32' else FilePersistence
        account = {'home_account_id': 'h', 'environment': 'login.microsoftonline.com', 'realm': 'r',
                   'local_account_id': 'l', 'username': 'tester@example.com', 'authority_type': 'MSSTS'}
        persistence(str(Path(self.tmp.name) / 'token.bin')).save(json.dumps({'Account': {'k': account}}))
        with redirect_stdout(out):
            self.assertEqual(mail.status(), 0)
            self.assertEqual(mail.logout(), 0)
            self.assertEqual(mail.status(), 3)
        self.assertIn('tester@example.com', out.getvalue())
        self.assertIn('지웠습니다', out.getvalue())
        self.assertFalse((Path(self.tmp.name) / 'token.bin').exists())


if __name__ == '__main__':
    unittest.main()
