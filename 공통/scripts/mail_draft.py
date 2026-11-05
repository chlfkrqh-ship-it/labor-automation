"""메일 초안을 Microsoft Graph 로 메일함의 임시 보관함에 바로 만든다. 받는 사람·참조·제목·본문·서명·첨부까지 넣고, 보내지 않는다.

새 Outlook 화면을 조작해 초안을 만들면 대화마다 화면 제어 승인을 받아야 한다. 이 스크립트는 화면을 쓰지 않으므로 승인 창 없이
초안을 만든다. 메일은 연결(outlook_email_search·read_resource)로 찾고, 연결이 준 주소(mail:///…)를 그대로 넘긴다.

    python -B 공통/scripts/mail_draft.py reply "mail:///messages/…" --all --body 본문.txt --attach a.pdf b.docx --prefix "(수정 송부) "
    python -B 공통/scripts/mail_draft.py new --to a@example.com --cc b@example.com --subject "…" --body 본문.txt --attach a.pdf
    python -B 공통/scripts/mail_draft.py check "mail:///messages/…" --files a.pdf b.docx   # 받는 사람·첨부를 보고 SHA-256 을 맞댄다
    python -B 공통/scripts/mail_draft.py login             # PC마다 처음 한 번. 브라우저 창에서 회사 계정을 고르고 메일 쓰기에 동의한다
    python -B 공통/scripts/mail_draft.py login --device    # 브라우저 창이 뜨지 않을 때. 코드를 받아 휴대폰에서 로그인
    python -B 공통/scripts/mail_draft.py status            # 메일 쓰기 권한으로 로그인되어 있는지

- 권한은 메일 쓰기(Mail.ReadWrite) 하나이다. 초안을 만들고 고치고 첨부를 붙이기만 한다. 보내기(Mail.Send)는 받지 않았고
  보내기·옮기기·복사·지우기 요청은 이 스크립트가 막는다. 보내는 것은 담당자가 Outlook 에서 누르거나 담당자가 그 자리에서
  보내라고 한 때이고, 초안 만들기도 담당자가 시킨 때에만 한다(CLAUDE.md 'Microsoft 365 연결은 읽기만 한다').
- 로그인은 mail_attach.py 와 같은 공용 앱(Microsoft Graph Command Line Tools)·같은 보관함(%LOCALAPPDATA%\\노동사건자동화\\메일\\)을
  쓰되 권한은 따로 동의받는다. mail_attach.py 는 그대로 읽기 전용이다.
- 본문은 UTF-8 글 파일이고 줄마다 맑은 고딕 11pt 줄로 넣는다(빈 줄은 빈 줄로). 서명은 보낸 편지함의 최근 메일에서
  <div id="Signature"> 를 그대로 가져와 그 아래에 붙인다(새 Outlook 이 화면에서 넣는 서명과 같은 모양). --no-signature 로 뺀다.
- 회신은 원 메일에 createReply·createReplyAll 로 만들어 대화가 이어진다. 받는 사람은 새 Outlook 과 같게 정한다: 내가 보낸 메일에
  회신하면 그 메일의 받는 사람(전체 회신이면 참조도), 남의 메일이면 보낸 사람(전체 회신이면 받는 사람·참조도). 내 주소는 뺀다.
  제목은 --subject 가 없으면 '{--prefix}{원 제목}' 이고, 원 제목이 Re:·RE:·회신: 으로 시작하지 않으면 'Re: ' 를 붙인다.
- 첨부는 보통 첨부로 붙인다(OneDrive 링크가 아니다). 3MB 미만은 한 번에, 그 이상은 업로드 세션으로 나누어 올린다.
- 만든 뒤 서버에서 다시 읽어 제목·받는 사람·참조·첨부를 보여 주고, 첨부를 내려받아 올린 파일과 SHA-256 을 맞댄다.

종료 코드: 0 만듦·맞음, 1 오류·다름, 3 로그인 필요(login 을 먼저 한다), 4 기기 코드 로그인을 기다리는 중.
2026. 11. 4. 한전 태양광 준비서면(3) 수정 송부 초안을 새 Outlook 화면 제어로 만들자 담당 노무사 "아웃룩 관련해서 매번 이런 식으로
내 허용 구해야 함? 자동으로 싹 안되나 pc에 앱도 깔려있는 마당에", 이어서 "바꾸기".
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.util
import json
import mimetypes
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_spec = importlib.util.spec_from_file_location('mail_attach', Path(__file__).resolve().with_name('mail_attach.py'))
ma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ma)

GRAPH = ma.GRAPH
SCOPES = ['Mail.ReadWrite']
OPENER = urllib.request.urlopen
LOGIN = 'python -B 공통/scripts/mail_draft.py login'
SMALL = 3 * 1024 * 1024                                 # 이보다 작은 첨부는 한 번에 올린다
CHUNK = 10 * 320 * 1024                                 # 업로드 세션 조각(320KiB 의 배수여야 한다)
LIMIT = 150 * 1024 * 1024                               # Graph 가 받는 첨부 하나의 상한
UPLOAD_HOSTS = ('outlook.office.com', 'outlook.office365.com')
STYLE = 'font-family:&quot;Malgun Gothic&quot;,&quot;맑은 고딕&quot;,AppleGothic,sans-serif;font-size:11pt;color:rgb(0,0,0)'
REPLY = re.compile(r'^\s*(re|회신)\s*:', re.I)
SIGNATURE = re.compile(r'<div\b[^>]*\bid=["\']?Signature["\'\s>]', re.I)
DIV = re.compile(r'<(/?)div\b[^>]*>', re.I)
MailError, NeedLogin = ma.MailError, ma.NeedLogin


# ── 로그인(보관함은 mail_attach.py 와 같고 권한만 다르다) ──

def app():
    return ma.app()


def silent(a) -> tuple[str, str] | None:
    for account in a.get_accounts():
        result = a.acquire_token_silent(SCOPES, account=account)
        if result and 'access_token' in result:
            return result['access_token'], account.get('username') or ''
    return None


def session() -> tuple[str, str]:
    """(토큰, 내 주소)."""
    a = app()
    try:
        found = silent(a)
    except Exception as exc:
        raise MailError(f'로그인 정보를 새로 받지 못했습니다({type(exc).__name__}: {exc}).') from None
    if found:
        return found
    raise NeedLogin('이 PC에서 메일 쓰기 권한 로그인이 되어 있지 않거나 만료되었습니다. 사용자에게 곧 뜨는 브라우저 창에서 회사 계정을 '
                    f'고르고 권한에 동의해 달라고 한 줄로 알리고 {LOGIN} 을 실행한 뒤(5분까지 기다린다) 같은 명령을 다시 실행하십시오.')


def explain(result: dict) -> str:
    return (ma.explain(result).replace('메일 읽기(Mail.Read)', '메일 쓰기(Mail.ReadWrite)')
            .replace('그동안 첨부는 사용자에게 사건 폴더에 저장해 달라고 한다.', '그동안 초안은 새 Outlook 화면 제어로 만든다.'))


def finish(result: dict) -> int:
    if result and 'access_token' in result:
        who = (result.get('id_token_claims') or {}).get('preferred_username')
        print(f'메일 쓰기 권한으로 로그인했습니다{f"({who})" if who else ""}. 이 PC에서는 다시 동의하지 않아도 됩니다'
              '(오래 쓰지 않거나 법인 정책에 따라 다시 물을 수 있다).')
        return 0
    raise MailError(explain(result or {}))


def login(device: bool = False) -> int:
    a = app()
    try:
        already = silent(a)
    except Exception:                                   # 새로 받다 실패하면 다시 로그인한다
        already = None
    if already:
        print('이미 메일 쓰기 권한으로 로그인되어 있습니다.')
        return 0
    if device:
        return login_device(a)
    print('브라우저 창에서 회사 계정을 고르십시오. 처음이면 "메일 읽기 및 쓰기" 권한 동의를 묻습니다. 5분 안에 마치지 않으면 끝납니다.',
          flush=True)
    try:
        result = a.acquire_token_interactive(SCOPES, prompt='select_account', timeout=300)
    except Exception as exc:
        if type(exc).__name__ == 'BrowserInteractionTimeoutError':
            raise MailError('5분 안에 로그인을 마치지 않아 끝났습니다. login 을 다시 실행하십시오.') from None
        raise MailError(f'브라우저 로그인을 시작하지 못했습니다({type(exc).__name__}: {exc}). '
                        'login --device 로 다시 하십시오.') from None
    return finish(result)


def login_device(a) -> int:
    """기기 코드 로그인. mail_attach.py 와 같되 기다리는 코드를 따로 둔다."""
    path = ma.home() / 'device_flow_draft.json'
    flow = None
    if path.is_file():
        try:
            flow = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            flow = None
        if not isinstance(flow, dict) or flow.get('expires_at', 0) <= time.time() + 5:
            flow = None
    if flow is None:
        flow = a.initiate_device_flow(scopes=SCOPES)
        if 'user_code' not in flow:
            raise MailError(explain(flow))
        path.write_text(json.dumps(flow), encoding='utf-8')
        print(f'휴대폰이나 다른 컴퓨터에서 {flow.get("verification_uri") or "https://microsoft.com/devicelogin"} 에 들어가 '
              f'코드 {flow["user_code"]} 를 넣고 회사 계정으로 로그인한 뒤 권한에 동의하십시오. '
              '마친 뒤 같은 명령(login --device)을 한 번 더 실행하면 로그인이 끝납니다.')
        return ma.PENDING
    deadline = time.time() + 60
    result = a.acquire_token_by_device_flow(flow, exit_condition=lambda f: time.time() > deadline)
    if result.get('error') in ('authorization_pending', 'slow_down'):
        print(f'아직 로그인이 끝나지 않았습니다. 코드 {flow.get("user_code")} 로 로그인을 마친 뒤 같은 명령을 다시 실행하십시오.')
        return ma.PENDING
    path.unlink(missing_ok=True)
    return finish(result)


def status() -> int:
    try:
        found = silent(app())
    except Exception:
        found = None
    if not found:
        print(f'이 PC에서는 메일 쓰기 권한으로 로그인되어 있지 않습니다. {LOGIN} 을 한다.')
        return ma.NEED_LOGIN
    print(f'메일 쓰기 권한으로 로그인되어 있습니다: {found[1] or "(이름 없음)"}')
    return 0


# ── Microsoft Graph ──

q = ma.q


def request(method: str, target: str, tok: str | None, body=None, *, raw: bool = False, headers=None):
    """Microsoft Graph(또는 Graph 가 준 첨부 업로드 주소)에 요청한다. body 가 dict 면 JSON, bytes 면 그대로 보낸다."""
    url = target if target.startswith('https://') else GRAPH + target
    parts = urllib.parse.urlsplit(url)
    upload = parts.scheme == 'https' and parts.hostname in UPLOAD_HOSTS
    if not (url.startswith(GRAPH + '/') or upload):
        raise MailError(f'Microsoft Graph 가 아닌 주소에는 요청하지 않습니다: {url[:80]}')
    if method == 'DELETE' or re.search(r'/(send|move|copy|forward|reply|replyAll)$', parts.path, re.I):
        raise MailError(f'이 스크립트는 메일을 보내거나 옮기거나 지우지 않습니다: {method} {parts.path[:80]}')
    head = dict(headers or {})
    if not upload:
        head['Authorization'] = 'Bearer ' + tok         # 업로드 주소는 그 자체로 인증되어 있어 토큰을 붙이지 않는다
    data = body
    if isinstance(body, (dict, list)):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        head['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=head, method=method)
    try:
        with OPENER(req, timeout=300) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise http_error(exc) from None
    except urllib.error.URLError as exc:
        raise MailError(f'Microsoft Graph 에 연결하지 못했습니다({exc.reason}). 클라우드 세션이면 PC에서 만든다.') from None
    if raw:
        return payload
    return json.loads(payload.decode('utf-8')) if payload.strip() else {}


def http_error(exc: urllib.error.HTTPError) -> MailError:
    try:
        detail = json.loads(exc.read().decode('utf-8')).get('error', {}).get('message', '')
    except Exception:
        detail = ''
    if exc.code == 401:
        error = NeedLogin(f'로그인이 만료되었습니다. {LOGIN} 을 다시 실행한 뒤 같은 명령을 다시 하십시오. ({detail})')
    elif exc.code == 403:
        error = MailError(f'메일 쓰기 권한이 없습니다. {LOGIN} 으로 권한에 동의했는지 보고, 법인 정책이면 관리자 승인이 필요합니다. ({detail})')
    elif exc.code == 404:
        error = MailError('메일을 찾지 못했습니다. 메일이 다른 폴더로 옮겨지면 주소가 바뀌므로 연결로 다시 찾아 새 주소를 넘기십시오'
                          f'(<internetMessageId> 로 넘기면 옮겨져도 찾는다). ({detail})')
    else:
        error = MailError(f'Microsoft Graph 오류 {exc.code}: {detail}')
    error.status = exc.code
    return error


# ── 본문·서명·받는 사람·제목 ──

def body_html(text: str) -> str:
    """글 파일의 줄을 새 Outlook 이 쓰는 꼴(맑은 고딕 11pt 한 줄씩)로 바꾼다."""
    lines = text.replace('\r\n', '\n').strip('\n').split('\n')
    return ''.join(f'<div class="elementToProof" style="{STYLE}">{html.escape(line) if line.strip() else "<br />"}</div>'
                   for line in lines)


빈_서명_첫줄 = re.compile(r'\s*<(?:div|p)\b[^>]*>(?:\s|<br\s*/?>|&nbsp;|<o:p>\s*</o:p>)*</(?:div|p)>', re.I)


def sign_gap(text: str, sign: str | None) -> str:
    """본문과 서명 사이의 빈 줄 하나. 본문 끝이 빈 줄이거나 서명이 빈 줄로 시작하면 넣지 않는다.
    본문 글의 끝 빈 줄은 body_html 이 지운다. 2026. 11. 5. 보낸 편지함의 최근 서명이 '감사합니다.'로 바로 시작해
    삼양인터내셔날 내부 회신 초안의 본문 끝 줄에 붙어 나왔다(담당자가 Outlook 에서 쓴 서명은 빈 줄로 시작한다)."""
    if not sign:
        return ''
    lines = text.replace('\r\n', '\n').strip('\n').split('\n')
    if not lines[-1].strip():
        return ''
    안쪽 = re.sub(r'^\s*<div\b[^>]*>', '', sign, count=1)       # 서명 div 를 여는 태그 뒤
    return '' if 빈_서명_첫줄.match(안쪽) else f'<div class="elementToProof" style="{STYLE}"><br /></div>'


def signature_of(page: str) -> str | None:
    """HTML 에서 <div id="Signature">…</div> 를 짝 맞추어 꺼낸다."""
    m = SIGNATURE.search(page or '')
    if not m:
        return None
    depth = 0
    for tag in DIV.finditer(page, m.start()):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return page[m.start():tag.end()]
    return None


def my_signature(tok: str) -> str | None:
    """보낸 편지함의 최근 메일 열 통에서 처음 나오는 서명. 내가 쓴 글 아래의 것이 먼저 나온다."""
    data = request('GET', f"/me/mailFolders/sentitems/messages?$top=10&$orderby={q('sentDateTime desc')}&$select=body", tok)
    for message in data.get('value') or []:
        found = signature_of((message.get('body') or {}).get('content') or '')
        if found:
            return found
    return None


def put_on_top(page: str, block: str) -> str:
    """회신 초안 본문(원문 인용이 든 HTML)의 맨 위에 넣는다."""
    m = re.search(r'<body\b[^>]*>', page or '', re.I)
    return page[:m.end()] + block + page[m.end():] if m else block + (page or '')


def address(entry: dict) -> str:
    return ((entry or {}).get('emailAddress') or {}).get('address') or ''


def recipients(original: dict, me: str, everyone: bool) -> tuple[list[dict], list[dict]]:
    """새 Outlook 이 회신을 열 때와 같게 받는 사람·참조를 정한다. 내 주소와 겹친 주소는 뺀다."""
    me = (me or '').lower()
    sender = (original.get('from') or {})
    to, cc = list(original.get('toRecipients') or []), list(original.get('ccRecipients') or [])
    if address(sender).lower() == me:                   # 내가 보낸 메일에 회신하면 그 메일을 받은 사람에게 다시 간다
        to, cc = to, (cc if everyone else [])
    else:
        to, cc = [sender] + (to if everyone else []), (cc if everyone else [])
    seen, keep = {me, ''}, ([], [])
    for target, entries in zip(keep, (to, cc)):
        for entry in entries:
            key = address(entry).lower()
            if key not in seen:
                seen.add(key)
                target.append({'emailAddress': {k: v for k, v in (entry.get('emailAddress') or {}).items()
                                                if k in ('name', 'address')}})
    return keep


def reply_subject(original: str, prefix: str = '') -> str:
    subject = (original or '').strip()
    if not REPLY.match(subject):
        subject = 'Re: ' + subject
    return prefix + subject


def plain(addresses) -> list[dict]:
    return [{'emailAddress': {'address': a.strip()}} for a in addresses or [] if a.strip()]


# ── 첨부 ──

def files_of(paths) -> list[Path]:
    found = []
    for p in paths or []:
        path = Path(p)
        if not path.is_file():
            raise MailError(f'붙일 파일이 없습니다: {p}')
        if path.stat().st_size > LIMIT:
            raise MailError(f'첨부 하나는 150MB 를 넘을 수 없습니다: {path.name}')
        found.append(path)
    total = sum(p.stat().st_size for p in found)
    if total > 25 * 1024 * 1024:
        print(f'알림: 첨부 합계가 {total / 1024 / 1024:.1f}MB 입니다. 받는 쪽 메일 서버가 거절할 수 있습니다.', file=sys.stderr)
    return found


def attach_file(tok: str, draft_id: str, path: Path) -> None:
    data = path.read_bytes()
    kind = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    base = f'/me/messages/{q(draft_id)}/attachments'
    if len(data) < SMALL:
        request('POST', base, tok, {'@odata.type': '#microsoft.graph.fileAttachment', 'name': path.name,
                                    'contentType': kind, 'contentBytes': base64.b64encode(data).decode('ascii')})
        return
    upload = request('POST', base + '/createUploadSession', tok,
                     {'AttachmentItem': {'attachmentType': 'file', 'name': path.name, 'size': len(data), 'contentType': kind}})
    for start in range(0, len(data), CHUNK):
        part = data[start:start + CHUNK]
        request('PUT', upload['uploadUrl'], None, part,
                headers={'Content-Type': 'application/octet-stream',
                         'Content-Range': f'bytes {start}-{start + len(part) - 1}/{len(data)}'})


# ── 초안 만들기·확인 ──

def find(tok: str, ref: str) -> dict:
    message_id, attachment_id, internet_id = ma.parse_ref(ref)
    if attachment_id:
        raise MailError('첨부 주소가 아니라 메일 주소(mail:///messages/…)를 넘기십시오.')
    select = 'id,subject,from,toRecipients,ccRecipients'
    if internet_id:
        flt = "internetMessageId eq '" + internet_id.replace("'", "''") + "'"
        found = request('GET', f'/me/messages?$filter={q(flt)}&$select={select}&$top=5', tok).get('value') or []
        if not found:
            raise MailError(f'그 internetMessageId 의 메일을 찾지 못했습니다: {internet_id}')
        return found[0]
    return request('GET', f'/me/messages/{q(message_id)}?$select={select}', tok)


def read_body(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise MailError(f'본문 글 파일이 없습니다: {path}')
    return p.read_text(encoding='utf-8-sig')


def reply(ref: str, body: str, attach=(), everyone: bool = False, prefix: str = '', subject: str | None = None,
          to=None, cc=None, signature: bool = True) -> int:
    files, text = files_of(attach), read_body(body)
    tok, me = session()
    original = find(tok, ref)
    draft = request('POST', f"/me/messages/{q(original['id'])}/{'createReplyAll' if everyone else 'createReply'}", tok, {})
    to_list, cc_list = recipients(original, me, everyone)
    sign = my_signature(tok) if signature else None
    if signature and not sign:
        print('알림: 보낸 편지함에서 서명을 찾지 못해 서명 없이 만들었습니다.', file=sys.stderr)
    content = put_on_top((draft.get('body') or {}).get('content') or '',
                         body_html(text) + sign_gap(text, sign) + (sign or '') + '<div id="appendonsend"></div>')
    request('PATCH', f"/me/messages/{q(draft['id'])}", tok, {
        'subject': subject or reply_subject(original.get('subject'), prefix),
        'body': {'contentType': 'html', 'content': content},
        'toRecipients': plain(to) if to else to_list,
        'ccRecipients': plain(cc) if cc else cc_list})
    for path in files:
        attach_file(tok, draft['id'], path)
    return report(tok, draft['id'], files)


def new(to, cc, subject: str, body: str, attach=(), signature: bool = True) -> int:
    files, text = files_of(attach), read_body(body)
    if not to:
        raise MailError('받는 사람(--to)을 하나 이상 주십시오.')
    tok, _ = session()
    sign = my_signature(tok) if signature else None
    draft = request('POST', '/me/messages', tok, {
        'subject': subject, 'toRecipients': plain(to), 'ccRecipients': plain(cc),
        'body': {'contentType': 'html', 'content': '<html><body>' + body_html(text) + sign_gap(text, sign) + (sign or '') + '</body></html>'}})
    for path in files:
        attach_file(tok, draft['id'], path)
    return report(tok, draft['id'], files)


def report(tok: str, draft_id: str, files=()) -> int:
    """서버에서 초안을 다시 읽어 보여 주고, 첨부를 내려받아 올린 파일과 맞댄다."""
    d = request('GET', f"/me/messages/{q(draft_id)}?$select=id,subject,toRecipients,ccRecipients,isDraft,hasAttachments", tok)
    atts = request('GET', f'/me/messages/{q(draft_id)}/attachments?$select=id,name,size,isInline', tok).get('value') or []
    who = lambda xs: '; '.join(f"{(r.get('emailAddress') or {}).get('name') or ''} <{address(r)}>".strip() for r in xs or []) or '없음'
    print(f"제목: {d.get('subject')}")
    print(f"받는 사람: {who(d.get('toRecipients'))}")
    print(f"참조: {who(d.get('ccRecipients'))}")
    print(f"초안: {'예' if d.get('isDraft') else '아니오(이미 보낸 메일)'}")
    ok = True
    by_name = {a.get('name'): a for a in atts}
    for a in atts:
        print(f"  첨부  {a.get('name')}  ({a.get('size') or 0:,}바이트{', 본문 그림' if a.get('isInline') else ''})")
    for path in files:
        a = by_name.get(path.name)
        if not a:
            print(f'  없음  {path.name} — 초안에 붙지 않았습니다')
            ok = False
            continue
        got = request('GET', f"/me/messages/{q(draft_id)}/attachments/{q(a['id'])}/$value", tok, raw=True)
        same = hashlib.sha256(got).hexdigest() == hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"  {'같음' if same else '다름'}  {path.name}  (내려받은 첨부와 올린 파일의 SHA-256)")
        ok = ok and same
    print('주소: mail:///messages/' + q(d.get('id') or draft_id))
    return 0 if ok else 1


def check(ref: str, files=()) -> int:
    tok, _ = session()
    message_id, _, internet_id = ma.parse_ref(ref)
    draft_id = find(tok, ref)['id'] if internet_id else message_id
    return report(tok, draft_id, [Path(f) for f in files or []])


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest='command', required=True)
    s = subs.add_parser('reply', help='받은·보낸 메일에 회신 초안을 만든다')
    s.add_argument('ref', help='연결이 준 메일 주소(mail:///messages/…), 메일 id, 또는 <internetMessageId>')
    s.add_argument('--all', action='store_true', help='전체 회신(참조까지)')
    s.add_argument('--body', required=True, help='본문 글 파일(UTF-8, 서명 위에 들어간다)')
    s.add_argument('--attach', nargs='*', default=[], help='붙일 파일')
    s.add_argument('--prefix', default='', help="제목 맨 앞에 붙일 말(예: '(수정 송부) ')")
    s.add_argument('--subject', help='제목을 통째로 정한다')
    s.add_argument('--to', action='append', help='받는 사람을 정해 바꾼다(여러 번)')
    s.add_argument('--cc', action='append', help='참조를 정해 바꾼다(여러 번)')
    s.add_argument('--no-signature', action='store_true', help='서명을 붙이지 않는다')
    s = subs.add_parser('new', help='새 메일 초안을 만든다')
    s.add_argument('--to', action='append', required=True)
    s.add_argument('--cc', action='append', default=[])
    s.add_argument('--subject', required=True)
    s.add_argument('--body', required=True)
    s.add_argument('--attach', nargs='*', default=[])
    s.add_argument('--no-signature', action='store_true')
    s = subs.add_parser('check', help='초안의 받는 사람·첨부를 보고 파일과 맞댄다')
    s.add_argument('ref')
    s.add_argument('--files', nargs='*', default=[])
    s = subs.add_parser('login', help='이 PC에서 처음 한 번 메일 쓰기 권한으로 로그인한다')
    s.add_argument('--device', action='store_true', help='브라우저 창이 뜨지 않을 때: 코드를 받아 다른 기기에서 로그인한다')
    subs.add_parser('status', help='메일 쓰기 권한으로 로그인되어 있는지 본다')
    args = parser.parse_args(argv)
    try:
        if args.command == 'reply':
            return reply(args.ref, args.body, args.attach, args.all, args.prefix, args.subject, args.to, args.cc,
                         not args.no_signature)
        if args.command == 'new':
            return new(args.to, args.cc, args.subject, args.body, args.attach, not args.no_signature)
        if args.command == 'check':
            return check(args.ref, args.files)
        if args.command == 'login':
            return login(args.device)
        return status()
    except MailError as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return exc.code


if __name__ == '__main__':
    raise SystemExit(main())
