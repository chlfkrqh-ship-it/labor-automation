"""팀즈 대화 글에 붙여 넣은 그림(첨부가 아닌 본문 그림)을 사건 폴더로 받는다. 화면 제어 없이 Microsoft Graph 로 받는다.

Microsoft 365 연결(read_resource)은 팀즈 글의 본문 그림을 떼고 글만 돌려준다. 그 그림(화면 캡처 등)에 사건의 숫자·문언이 있으면
이 스크립트로 받는다. 글은 연결로 찾고(chat_message_search·teams_list_chats·read_resource), 연결이 준 주소
(teams:///chats/…/messages/…)나 글의 webUrl 을 그대로 넘긴다. 팀즈로 보낸 파일(첨부)은 공통/운영.md '팀즈 파일 받기'대로 연결로 복사한다.

    python -B 공통/scripts/teams_get.py get "teams:///chats/19%3A…/messages/1794…" --to "4_서면작성/사건/{사건}/라운드1/작업"
    python -B 공통/scripts/teams_get.py get "…" --to "…" --name "청구 목록 캡처"   # 파일 이름(없으면 '팀즈 그림_{날짜}_{시각}_{보낸 사람}')
    python -B 공통/scripts/teams_get.py status            # 팀즈 대화 읽기 권한으로 로그인되어 있는지
    python -B 공통/scripts/teams_get.py login             # mail_attach.py login 과 같다(공통 도구의 권한을 한 번에 동의받는다)

- 로그인은 mail_attach.py 와 같은 공용 앱·같은 보관함을 쓰고, 로그인 한 번에 공통 도구의 권한을 함께 동의받는다(mail_attach.py 의
  LOGIN_SCOPES). 이 스크립트가 쓰는 권한은 팀즈 대화 읽기(Chat.Read)이다. 팀즈에 글을 올리거나 고치거나 지우지 않는다.
- 채널 글(teams:///teams/…/channels/…)은 법인 관리자 승인이 드는 권한(ChannelMessage.Read.All)이 있어야 하므로 받지 않는다.
  채널 글의 그림은 팀즈 앱에서 내려받는다.
- 받는 자리, 같은 이름 처리, 파일 이름 다듬기는 mail_attach.py 와 같다(사건 폴더나 저장소 밖에만 받고, 덮어쓰지 않는다).
- 글의 보낸 사람·시각·글(앞 200자)을 함께 보여 준다. 사건 기록에는 출처(보낸 사람·보낸 일시·대화)를 적는다.

종료 코드: 0 받음, 1 오류·받은 그림 없음, 3 로그인 필요(login 을 먼저 한다).
2026. 11. 10. 직원이 1:1 대화에 붙인 정보공개청구 접수 목록 캡처를 팀즈 앱 화면 제어로 받자 담당 노무사가 "예전에 는 이렇게 제어 직접
안해도 메시지 뽑아오지 않았나..", 이어서 "마이크로소프트 오피스 관련한 권한 자꾸 찔끔찔끔 하는 것 같은데 필요하다면 그냥 다 승인 받는게
낫지 않나?" 하여 만들었다.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import re
import sys
import urllib.parse
from pathlib import Path

_spec = importlib.util.spec_from_file_location('mail_attach', Path(__file__).resolve().with_name('mail_attach.py'))
ma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ma)

ROOT = ma.ROOT
SCOPES = ['Chat.Read']
LOGIN = 'python -B 공통/scripts/teams_get.py login'
MailError, NeedLogin = ma.MailError, ma.NeedLogin
IMG = re.compile(r'<img\b[^>]*?\bsrc\s*=\s*["\']([^"\']*/hostedContents/([^/"\']+)/\$value)["\']', re.I)
MAGIC = ((b'\x89PNG\r\n\x1a\n', '.png'), (b'\xff\xd8\xff', '.jpg'), (b'GIF87a', '.gif'), (b'GIF89a', '.gif'), (b'BM', '.bmp'))
CHANNEL = '채널 글은 받지 못합니다(법인 관리자 승인이 드는 ChannelMessage.Read.All 권한이 있어야 한다). 팀즈 앱에서 그림을 내려받으십시오.'


# ── 로그인(mail_attach.py 와 같은 보관함) ──

def app():
    return ma.app()


def token() -> str:
    a = app()
    try:
        for account in a.get_accounts():
            result = a.acquire_token_silent(SCOPES, account=account)
            if result and 'access_token' in result:
                return result['access_token']
    except Exception as exc:
        raise MailError(f'로그인 정보를 새로 받지 못했습니다({type(exc).__name__}: {exc}).') from None
    raise NeedLogin('이 PC에서 팀즈 대화 읽기(Chat.Read) 권한으로 로그인되어 있지 않습니다. 사용자에게 곧 뜨는 브라우저 창에서 회사 계정을 '
                    f'고르고 권한에 동의해 달라고 한 줄로 알리고 {LOGIN} 을 실행한 뒤(5분까지 기다린다) 같은 명령을 다시 실행하십시오.')


def status() -> int:
    try:
        token()
    except NeedLogin:
        print(f'이 PC에서는 팀즈 대화 읽기 권한으로 로그인되어 있지 않습니다. {LOGIN} 을 한다.')
        return ma.NEED_LOGIN
    print('팀즈 대화 읽기 권한으로 로그인되어 있습니다.')
    return 0


# ── 팀즈 글 ──

def parse_ref(ref: str) -> tuple[str, str]:
    """연결이 준 주소(teams:///chats/{대화}/messages/{글})나 글의 webUrl 에서 (대화 id, 글 id) 를 가른다."""
    ref = (ref or '').strip()
    if ref.startswith('teams:///teams/'):
        raise MailError(CHANNEL)
    m = re.fullmatch(r'teams:///chats/([^/?#]+)/messages/([^/?#]+)', ref)
    if m:
        return urllib.parse.unquote(m[1]), urllib.parse.unquote(m[2])
    m = re.search(r'teams\.microsoft\.com/l/message/([^/?#]+)/(\d+)', ref)
    if m:
        chat_id = urllib.parse.unquote(m[1])
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(ref).query)
        if (re.search(r'@thread\.(tacv2|skype)$', chat_id) or 'groupId' in query       # 채널 글의 주소 꼴
                or any('channel' in v.lower() for v in query.get('context', []))):
            raise MailError(CHANNEL)
        return chat_id, m[2]
    raise MailError(f'팀즈 글 주소를 알아보지 못했습니다: {ref[:80]} — 연결이 준 teams:///chats/…/messages/… 주소를 넘기십시오.')


def fetch(target: str, tok: str, *, raw: bool = False):
    try:
        return ma.call(target, tok, raw=raw)
    except NeedLogin:
        raise
    except MailError as exc:
        if exc.status == 404:
            raise MailError('팀즈 글을 찾지 못했습니다. 연결로 그 글을 다시 찾아 새 주소를 넘기십시오(채널 글이면 받지 못한다).') from None
        if exc.status == 403:
            raise MailError(f'이 대화를 읽을 권한이 없습니다(내가 들어 있지 않은 대화이거나 법인 정책). ({exc})') from None
        raise


def plain(body: str) -> str:
    text = re.sub(r'<img\b[^>]*>', ' [그림] ', body or '', flags=re.I)
    text = re.sub(r'<br\s*/?>|</p>|</div>', '\n', text, flags=re.I)
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    return re.sub(r'[ \t ]+', ' ', re.sub(r'\s*\n\s*', ' / ', text)).strip(' /')


def stamp(when) -> str:
    return f'{when.year}. {when.month}. {when.day}. {when:%H:%M}' if when else '보낸 일시 없음'


def extension(data: bytes) -> str:
    return next((ext for magic, ext in MAGIC if data.startswith(magic)), '.bin')


def get(ref: str, to: str, name: str | None = None, root: Path = ROOT) -> int:
    chat_id, message_id = parse_ref(ref)
    root = root.resolve()
    folder = ma.destination(to, root)
    tok = token()
    base = f'/chats/{ma.q(chat_id)}/messages/{ma.q(message_id)}'
    msg = fetch(base, tok)
    sender = ((msg.get('from') or {}).get('user') or {}).get('displayName') or '보낸 사람 모름'
    when = ma.kst(msg.get('createdDateTime'))
    body = (msg.get('body') or {}).get('content') or ''
    text = plain(body)
    print(f"글: {sender} | {stamp(when)} | {text[:200] or '(글 없음)'}")

    ids = list(dict.fromkeys(urllib.parse.unquote(m[2]) for m in IMG.finditer(body)))   # 본문에 나온 차례
    try:
        listed = [h.get('id') for h in ma.pages(base + '/hostedContents', tok)]
    except MailError:
        listed = []                                     # 목록을 주지 않으면 본문의 그림 주소만 쓴다
    ids += [i for i in listed if i and i not in ids]
    if not ids:
        print('이 글에는 본문 그림이 없습니다. 첨부 파일이면 공통/운영.md \'팀즈 파일 받기\'대로 연결로 복사한다.')
        return 1
    if name:
        stem = name
    elif when:
        stem = f'팀즈 그림_{when:%Y-%m-%d_%H%M}_{sender}'
    else:
        stem = f'팀즈 그림_{sender}'
    new = same = 0
    for n, hosted in enumerate(ids, 1):
        data = fetch(f'{base}/hostedContents/{ma.q(hosted)}/$value', tok, raw=True)
        file_name = ma.safe_name(stem + (f'_{n}' if len(ids) > 1 else '') + extension(data))
        path, fresh = ma.place(folder, file_name, data)
        print(f"  {'받음' if fresh else '이미 있음'}  {ma.shown(path, root)}  ({len(data):,}바이트)")
        new, same = new + fresh, same + (not fresh)
    print(f'받은 그림 {new}개' + (f', 이미 있던 그림 {same}개' if same else '') + '.')
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    subs = parser.add_subparsers(dest='command', required=True)
    s = subs.add_parser('get', help='팀즈 글의 본문 그림을 사건 폴더로 받는다')
    s.add_argument('ref', help='연결이 준 글 주소(teams:///chats/…/messages/…) 또는 글의 webUrl')
    s.add_argument('--to', required=True, help='받을 사건 폴더(저장소 루트 기준 상대경로)')
    s.add_argument('--name', help='파일 이름(확장자 없이). 그림이 여럿이면 뒤에 _1, _2 를 붙인다')
    s = subs.add_parser('login', help='이 PC에서 처음 한 번 로그인한다(mail_attach.py login 과 같다)')
    s.add_argument('--device', action='store_true', help='브라우저 창이 뜨지 않을 때: 코드를 받아 다른 기기에서 로그인한다')
    subs.add_parser('status', help='팀즈 대화 읽기 권한으로 로그인되어 있는지 본다')
    args = parser.parse_args(argv)
    try:
        if args.command == 'get':
            return get(args.ref, args.to, args.name, root=args.root)
        if args.command == 'login':
            return ma.login(args.device)
        return status()
    except MailError as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return exc.code


if __name__ == '__main__':
    raise SystemExit(main())
