"""teams_get.py — 가짜 Microsoft Graph 로 팀즈 글의 본문 그림 받기를 시험한다(네트워크를 쓰지 않는다).

대화·사람·글은 모두 지어낸 값이다. 실제 대화에서 본 이름·글·사건번호를 여기에 옮기지 않는다(git 에 올라간다).
"""
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location('teams_get', Path(__file__).parents[1] / 'scripts' / 'teams_get.py')
teams = importlib.util.module_from_spec(spec)
spec.loader.exec_module(teams)

GRAPH = teams.ma.GRAPH
CHAT = '19:abc-def_ghi@unq.gbl.spaces'
MSG = '1790000000001'
PLAIN = '1790000000002'
CASE = '4_서면작성/사건/가나상사_해고/라운드1/작업'
PNG = b'\x89PNG\r\n\x1a\n' + b'picture-one'
JPG = b'\xff\xd8\xff\xe0' + b'picture-two'
HOSTED = {'aWQ9eF8wLWE=': PNG, 'aWQ9eF8wLWI=': JPG}
BODY = ('<p><img src="https://graph.microsoft.com/v1.0/chats/' + CHAT + '/messages/' + MSG
        + '/hostedContents/aWQ9eF8wLWE%3D/$value" style="width:600px"></p>'
        '<p>접수 목록 &amp; 처리 상태 보내드립니다!</p>')


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeGraph:
    """팀즈 대화 글과 본문 그림(hostedContents) 몇 갈래만 흉내 낸다. 둘째 그림은 본문에 없고 목록에만 있다."""

    def __init__(self):
        self.seen = []

    def __call__(self, request, timeout=None):
        assert request.full_url.startswith(GRAPH + '/'), request.full_url
        assert request.get_header('Authorization') == 'Bearer T'
        split = urllib.parse.urlsplit(request.full_url[len(GRAPH):])
        path = [urllib.parse.unquote(s) for s in split.path.split('/')[1:]]
        self.seen.append(path)
        if path[:3] != ['chats', CHAT, 'messages'] or path[3] not in (MSG, PLAIN):
            raise self.error(404, 'NotFound')
        rest = path[4:]
        if not rest:
            body = BODY if path[3] == MSG else '<p>그림 없는 글</p>'
            return self.json({'id': path[3], 'createdDateTime': '2026-11-10T04:27:13.847Z',
                              'from': {'user': {'displayName': '홍길동 대리'}}, 'body': {'contentType': 'html', 'content': body}})
        if rest == ['hostedContents']:
            return self.json({'value': [{'id': k} for k in HOSTED] if path[3] == MSG else []})
        if len(rest) == 3 and rest[0] == 'hostedContents' and rest[2] == '$value' and rest[1] in HOSTED:
            return Response(HOSTED[rest[1]])
        raise self.error(404, 'NotFound')

    @staticmethod
    def json(data):
        return Response(json.dumps(data).encode('utf-8'))

    @staticmethod
    def error(code, message):
        return urllib.error.HTTPError(GRAPH, code, 'error', {}, io.BytesIO(json.dumps({'error': {'message': message}}).encode()))


class ParseTests(unittest.TestCase):
    def test_connector_uri_and_web_url(self):
        uri = 'teams:///chats/' + urllib.parse.quote(CHAT, safe='') + '/messages/' + MSG
        self.assertEqual(teams.parse_ref(uri), (CHAT, MSG))
        web = ('https://teams.microsoft.com/l/message/' + urllib.parse.quote(CHAT, safe='') + '/' + MSG
               + '?context=%7b%22contextType%22%3a%22chat%22%7d&tenantId=t')
        self.assertEqual(teams.parse_ref(web), (CHAT, MSG))

    def test_channel_messages_are_refused(self):
        for ref in ('teams:///teams/t1/channels/c1/messages/m1',
                    'https://teams.microsoft.com/l/message/19%3Axyz%40thread.tacv2/1790000000003?groupId=g&tenantId=t'):
            with self.assertRaises(teams.MailError) as caught:
                teams.parse_ref(ref)
            self.assertIn('채널', str(caught.exception))
        with self.assertRaises(teams.MailError):
            teams.parse_ref('mail:///messages/AAMk')


class GetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'root'
        self.root.mkdir()
        self.graph = FakeGraph()
        self.patches = [mock.patch.object(teams.ma, 'OPENER', self.graph), mock.patch.object(teams, 'token', lambda: 'T')]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_get(self, ref, name=None, to=CASE):
        out = io.StringIO()
        with redirect_stdout(out):
            code = teams.get(ref, to, name, root=self.root)
        return code, out.getvalue()

    def test_pictures_are_saved_in_body_order_with_their_type(self):
        uri = 'teams:///chats/' + urllib.parse.quote(CHAT, safe='') + '/messages/' + MSG
        code, out = self.run_get(uri, name='청구 목록 캡처')
        self.assertEqual(code, 0, out)
        folder = self.root / CASE
        self.assertEqual((folder / '청구 목록 캡처_1.png').read_bytes(), PNG)     # 본문에 나온 그림이 먼저
        self.assertEqual((folder / '청구 목록 캡처_2.jpg').read_bytes(), JPG)     # 목록에만 있는 그림이 뒤에
        self.assertIn('홍길동 대리 | 2026. 11. 10. 13:27', out)                     # 한국 시각
        self.assertIn('접수 목록 & 처리 상태', out)
        code, out = self.run_get(uri, name='청구 목록 캡처')
        self.assertEqual(code, 0)
        self.assertIn('이미 있던 그림 2개', out)
        self.assertEqual(len(list(folder.iterdir())), 2)                           # 덮어쓰거나 겹쳐 쓰지 않았다

    def test_default_name_has_time_and_sender(self):
        code, out = self.run_get('teams:///chats/' + CHAT + '/messages/' + MSG)
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / CASE / '팀즈 그림_2026-11-10_1327_홍길동 대리_1.png').is_file())

    def test_message_without_pictures_and_missing_message(self):
        code, out = self.run_get('teams:///chats/' + CHAT + '/messages/' + PLAIN)
        self.assertEqual(code, 1)
        self.assertIn('본문 그림이 없습니다', out)
        with self.assertRaises(teams.MailError) as caught:
            self.run_get('teams:///chats/' + CHAT + '/messages/1790000000009')
        self.assertIn('팀즈 글을 찾지 못했습니다', str(caught.exception))

    def test_only_case_folders_inside_the_repository(self):
        with self.assertRaises(teams.MailError) as caught:
            self.run_get('teams:///chats/' + CHAT + '/messages/' + MSG, to='공통/scripts')
        self.assertIn('사건 폴더', str(caught.exception))
        self.assertEqual(self.graph.seen, [])                                       # 막힌 자리면 요청도 보내지 않는다


class LoginTests(unittest.TestCase):
    def test_token_needs_chat_permission_login(self):
        class NoLogin:
            def get_accounts(self):
                return []

        with mock.patch.object(teams, 'app', lambda: NoLogin()):
            with self.assertRaises(teams.NeedLogin) as caught:
                teams.token()
        self.assertEqual(caught.exception.code, 3)
        self.assertIn('teams_get.py login', str(caught.exception))
        self.assertIn('Chat.Read', teams.ma.LOGIN_SCOPES)                         # 한 번의 로그인에 이 도구의 권한도 든다
        self.assertEqual(teams.SCOPES, ['Chat.Read'])


if __name__ == '__main__':
    unittest.main()
