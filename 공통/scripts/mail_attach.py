"""메일 첨부를 사건 폴더로 받는다. 작업에 원본이 필요한 첨부만 그때그때 받는다.

Microsoft 365 연결(claude.ai 커넥터)은 첨부의 글자만 돌려주고 파일은 내려받지 못한다(한글 hwp·hwpx 는 글자도
돌려주지 않는다). 원본이 있어야 하는 첨부(한글 파일, 글자가 없는 스캔본, 변경 내용 추적으로 고칠 의뢰인 문서,
증거로 낼 파일)는 이 스크립트가 Microsoft Graph 에서 이 PC의 사건 폴더로 받는다. 메일은 연결로 찾고
(outlook_email_search·read_resource), 연결이 준 주소(mail:///…)를 그대로 넘긴다. 절차는 공통/운영.md '메일 첨부 받기'.

    python -B 공통/scripts/mail_attach.py get "mail:///messages/…/attachments/…" --to "1_검토의견/사건/{의뢰인}_{검토내용}"
    python -B 공통/scripts/mail_attach.py get "mail:///messages/…" --to "…" --name 참석자   # 이름에 '참석자'가 든 첨부만
    python -B 공통/scripts/mail_attach.py get "mail:///messages/…" --to "…" --eml          # 메일 원본(.eml)도
    python -B 공통/scripts/mail_attach.py login             # PC마다 처음 한 번. 브라우저 창에서 회사 계정을 고른다
    python -B 공통/scripts/mail_attach.py login --device    # 브라우저 창이 뜨지 않을 때. 코드를 받아 휴대폰에서 로그인
    python -B 공통/scripts/mail_attach.py status            # 로그인되어 있는지(네트워크를 쓰지 않는다)
    python -B 공통/scripts/mail_attach.py logout

- 권한은 메일 읽기(Mail.Read) 하나이다. 메일을 고치거나 보내거나 지우지 않는다.
- 로그인은 마이크로소프트가 스크립트용으로 둔 공용 앱(Microsoft Graph Command Line Tools)으로 한다. 법인 설정에
  따라 처음 로그인할 때 관리자 승인이 필요할 수 있다.
- 로그인 정보는 PC마다 %LOCALAPPDATA%\\노동사건자동화\\메일\\ 에 두고(Windows 는 사용자 계정으로 암호화한다)
  OneDrive·git 에 두지 않는다.
- 받는 자리는 저장소 밖이거나 사건 폴더(경로에 '사건' 폴더가 있는 곳)여야 한다. 저장소의 다른 자리에 받으면
  의뢰인 파일이 git 에 올라갈 수 있다.
- 같은 이름의 파일이 있으면 내용이 같을 때 건너뛰고, 다르면 '이름 (2).확장자'로 받는다. 덮어쓰지 않는다.

종료 코드: 0 받음, 1 오류·받은 것 없음, 3 로그인 필요(login 을 먼저 한다),
4 기기 코드 로그인을 기다리는 중(로그인을 마친 뒤 같은 명령을 다시 실행한다).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH = 'https://graph.microsoft.com/v1.0'
CLIENT_ID = '14d82eec-204b-4c2f-b7e8-296a70dab67e'      # Microsoft Graph Command Line Tools
AUTHORITY = 'https://login.microsoftonline.com/organizations'
SCOPES = ['Mail.Read']
OPENER = urllib.request.urlopen
KST = timezone(timedelta(hours=9))
NEED_LOGIN, PENDING = 3, 4
INSTALL = 'python -m pip install -r 공통/requirements.txt'
LOGIN = 'python -B 공통/scripts/mail_attach.py login'
SELECT = 'id,subject,from,receivedDateTime,internetMessageId,hasAttachments'
# 법인 관리자가 앱에 동의해 주어야 풀리는 로그인 거절
ADMIN_CODES = ('AADSTS65001', 'AADSTS90094', 'AADSTS90095', 'AADSTS900941', 'AADSTS50105')
INVALID = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}


class MailError(Exception):
    code = 1
    status = None                                       # Microsoft Graph 가 돌려준 HTTP 상태


class NeedLogin(MailError):
    code = NEED_LOGIN


def home() -> Path:
    base = os.environ.get('MAIL_ATTACH_HOME')
    if base:
        return Path(base)
    return Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / '노동사건자동화' / '메일'


# ── 로그인 ──

def cache():
    """로그인 정보 보관함. Windows 에서는 사용자 계정으로 암호화(DPAPI)해 둔다."""
    try:
        from msal_extensions import FilePersistence, FilePersistenceWithDataProtection, PersistedTokenCache
    except ImportError:
        raise MailError(f'로그인 도구(msal)가 없습니다. {INSTALL} 로 설치한 뒤 다시 실행하십시오.') from None
    home().mkdir(parents=True, exist_ok=True)
    where = str(home() / 'token.bin')
    persistence = FilePersistenceWithDataProtection(where) if sys.platform == 'win32' else FilePersistence(where)
    return PersistedTokenCache(persistence)


def app():
    token_cache = cache()
    import msal
    try:
        return msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=token_cache)
    except Exception as exc:                            # 로그인 서버에 닿지 않을 때 등
        raise MailError(f'Microsoft 로그인 서버에 연결하지 못했습니다({type(exc).__name__}: {exc}).') from None


def silent(a) -> str | None:
    for account in a.get_accounts():
        result = a.acquire_token_silent(SCOPES, account=account)
        if result and 'access_token' in result:
            return result['access_token']
    return None


def token() -> str:
    a = app()
    try:
        found = silent(a)
    except Exception as exc:
        raise MailError(f'로그인 정보를 새로 받지 못했습니다({type(exc).__name__}: {exc}).') from None
    if found:
        return found
    raise NeedLogin('이 PC에서 메일 로그인이 되어 있지 않거나 만료되었습니다. 사용자에게 곧 뜨는 브라우저 창에서 회사 계정을 '
                    f'고르라고 한 줄로 알리고 {LOGIN} 을 실행한 뒤(5분까지 기다린다) 같은 get 을 다시 실행하십시오.')


def explain(result: dict) -> str:
    code = result.get('error') or '알 수 없는 오류'
    lines = (result.get('error_description') or '').strip().splitlines()
    first = lines[0] if lines else ''
    if code == 'consent_required' or any(c in first for c in ADMIN_CODES):
        return ('법인 관리자의 승인이 필요합니다. 관리자가 Microsoft Entra 관리 센터에서 "Microsoft Graph Command Line Tools" '
                '앱의 메일 읽기(Mail.Read) 권한에 동의해 주면 됩니다. 그동안 첨부는 사용자에게 사건 폴더에 저장해 달라고 한다. '
                f'({first})')
    if 'AADSTS53003' in first:
        return f'법인의 접근 정책(조건부 액세스)이 이 로그인을 막았습니다. 관리자에게 확인이 필요합니다. ({first})'
    if code == 'access_denied' or 'AADSTS65004' in first:
        return f'로그인이 취소되었거나 권한 동의를 하지 않았습니다. ({first or code})'
    return f'로그인하지 못했습니다: {code} {first}'.strip()


def finish(result: dict) -> int:
    if result and 'access_token' in result:
        who = (result.get('id_token_claims') or {}).get('preferred_username')
        print(f'로그인했습니다{f"({who})" if who else ""}. 이 PC에서는 다시 로그인하지 않아도 됩니다'
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
        print('이미 로그인되어 있습니다.')
        return 0
    if device:
        return login_device(a)
    print('브라우저 창에서 회사 계정을 고르십시오. 처음이면 "메일 읽기" 권한 동의를 묻습니다. 5분 안에 마치지 않으면 끝납니다.',
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
    """기기 코드 로그인. 코드를 보여 주고 끝낸 뒤(4), 다시 부르면 로그인이 끝났는지 1분까지 확인한다."""
    path = home() / 'device_flow.json'
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
        minutes = max(1, int((flow.get('expires_at', time.time() + 900) - time.time()) // 60))
        print(f'휴대폰이나 다른 컴퓨터에서 {flow.get("verification_uri") or "https://microsoft.com/devicelogin"} 에 들어가 '
              f'코드 {flow["user_code"]} 를 넣고 회사 계정으로 로그인하십시오({minutes}분 안에). '
              '마친 뒤 같은 명령(login --device)을 한 번 더 실행하면 로그인이 끝납니다.')
        return PENDING
    deadline = time.time() + 60
    result = a.acquire_token_by_device_flow(flow, exit_condition=lambda f: time.time() > deadline)
    if result.get('error') in ('authorization_pending', 'slow_down'):
        print(f'아직 로그인이 끝나지 않았습니다. 코드 {flow.get("user_code")} 로 로그인을 마친 뒤 같은 명령을 다시 실행하십시오.')
        return PENDING
    path.unlink(missing_ok=True)
    return finish(result)


def status() -> int:
    saved = cache()
    accounts = list(saved.search('Account')) if hasattr(saved, 'search') else saved.find('Account')
    if not accounts:
        print('이 PC에서는 메일 로그인이 되어 있지 않습니다. 첫 get 이 로그인 필요(종료 코드 3)로 끝나면 login 을 한다.')
        return NEED_LOGIN
    print('로그인되어 있습니다: ' + ', '.join(a.get('username') or '(이름 없음)' for a in accounts))
    return 0


def logout() -> int:
    gone = [p for p in (home() / 'token.bin', home() / 'token.bin.lockfile', home() / 'device_flow.json') if p.exists()]
    for p in gone:
        p.unlink()
    print('이 PC의 메일 로그인 정보를 지웠습니다.' if gone else '지울 로그인 정보가 없습니다.')
    return 0


# ── Microsoft Graph ──

def q(value: str) -> str:
    return urllib.parse.quote(value, safe='')


def call(target: str, tok: str, *, raw: bool = False):
    url = target if target.startswith(GRAPH + '/') else GRAPH + target
    if not url.startswith(GRAPH + '/'):
        raise MailError(f'Microsoft Graph 가 아닌 주소에는 요청하지 않습니다: {url[:80]}')
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
    try:
        with OPENER(request, timeout=120) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        raise graph_error(exc) from None
    except urllib.error.URLError as exc:
        raise MailError(f'Microsoft Graph 에 연결하지 못했습니다({exc.reason}). 클라우드 세션이면 PC에서 받는다.') from None
    return data if raw else json.loads(data.decode('utf-8'))


def graph_error(exc: urllib.error.HTTPError) -> MailError:
    error = describe_error(exc)
    error.status = exc.code
    return error


def describe_error(exc: urllib.error.HTTPError) -> MailError:
    try:
        detail = json.loads(exc.read().decode('utf-8')).get('error', {}).get('message', '')
    except Exception:
        detail = ''
    if exc.code == 401:
        return NeedLogin(f'로그인이 만료되었습니다. {LOGIN} 을 다시 실행한 뒤 같은 get 을 다시 하십시오. ({detail})')
    if exc.code == 404:
        return MailError('메일이나 첨부를 찾지 못했습니다. 메일이 다른 폴더로 옮겨지면 주소가 바뀌므로 연결로 다시 찾아 새 주소를 '
                         f'넘기십시오(<internetMessageId> 로 넘기면 옮겨져도 찾는다). ({detail})')
    if exc.code == 403:
        return MailError(f'이 메일을 읽을 권한이 없습니다(공유 메일함이거나 법인 정책). ({detail})')
    return MailError(f'Microsoft Graph 오류 {exc.code}: {detail}')


def find_message(tok: str, message_id: str | None, internet_id: str | None) -> dict:
    if internet_id:
        flt = "internetMessageId eq '" + internet_id.replace("'", "''") + "'"
        found = call(f'/me/messages?$filter={q(flt)}&$select={SELECT}&$top=5', tok).get('value') or []
        if not found:
            raise MailError(f'그 internetMessageId 의 메일을 찾지 못했습니다: {internet_id}')
        return found[0]                                 # 보낸편지함과 받은편지함에 같은 메일이 있어도 첨부는 같다
    return call(f'/me/messages/{q(message_id)}?$select={SELECT}', tok)


def list_attachments(tok: str, message_id: str) -> list[dict]:
    """첨부 목록(내용 없이). 다음 쪽 주소가 있으면 따라간다."""
    base = f'/me/messages/{q(message_id)}/attachments'
    try:
        return pages(base + '?$select=id,name,contentType,size,isInline', tok)
    except MailError as exc:
        if exc.status != 400:
            raise
        return pages(base, tok)                         # 고른 칸만 달라는 요청을 거절하면 내용까지 받아 목록으로만 쓴다


def pages(target: str, tok: str) -> list[dict]:
    found = []
    while target:
        data = call(target, tok)
        found += data.get('value') or []
        target = data.get('@odata.nextLink')
    return found


def kind(att: dict) -> str:
    t = (att.get('@odata.type') or '').lower()
    if 'referenceattachment' in t:
        return 'link'
    if 'itemattachment' in t or (att.get('contentType') or '').lower() == 'message/rfc822':
        return 'item'
    return 'file'


def choose(atts: list[dict], attachment_id: str | None, names, inline: bool):
    """받을 첨부와 건너뛸 첨부(사유). 첨부를 하나 지목했으면 본문 그림이어도 받는다."""
    if attachment_id:
        picked = [a for a in atts if a.get('id') == attachment_id]
        if not picked:
            raise MailError('그 첨부를 이 메일에서 찾지 못했습니다. 메일 주소와 --name 으로 다시 하십시오. 첨부: '
                            + ', '.join(a.get('name') or '?' for a in atts))
        return picked, []
    wanted = [nfc(n).lower() for n in names]
    picked, skipped = [], []
    for a in atts:
        if wanted and not any(n in nfc(a.get('name') or '').lower() for n in wanted):
            continue
        if a.get('isInline') and not inline:
            skipped.append((a, '본문에 박힌 그림(서명 등)'))
        else:
            picked.append(a)
    if wanted and not picked and not skipped:
        raise MailError('이름에 ' + '·'.join(names) + ' 이(가) 든 첨부가 없습니다. 첨부: '
                        + (', '.join(a.get('name') or '?' for a in atts) or '없음'))
    return picked, skipped


# ── 저장 ──

def nfc(text: str) -> str:
    """맥에서 보낸 파일 이름은 한글 자모가 풀려(NFD) 온다. 맞대거나 저장하기 전에 붙인다."""
    return unicodedata.normalize('NFC', text)


def safe_name(name: str, limit: int = 120) -> str:
    """Windows 에서 쓸 수 없는 글자를 바꾸고 길이를 줄인다. OneDrive 사건 폴더 경로가 길어 이름은 120자로 둔다."""
    name = INVALID.sub('_', nfc(name or '')).strip().strip('.').strip()
    stem, ext = os.path.splitext(name or '첨부')
    if len(ext) > 10:
        stem, ext = stem + ext, ''
    if stem.split('.')[0].upper() in RESERVED:
        stem = '_' + stem
    stem = stem[:max(1, limit - len(ext))].rstrip(' .') or '첨부'
    return stem + ext


def place(folder: Path, name: str, data: bytes) -> tuple[Path, bool]:
    """같은 이름이 있으면 내용이 같을 때 그 파일을, 다르면 '이름 (2)' 로 새로 쓴다. (경로, 새로 썼는지)."""
    target = folder / name
    stem, suffix = os.path.splitext(name)
    n = 1
    while target.exists():
        if target.is_file() and target.read_bytes() == data:
            return target, False
        n += 1
        target = folder / f'{stem} ({n}){suffix}'
    part = target.with_name(target.name + '.part')
    part.write_bytes(data)
    part.replace(target)
    return target, True


def destination(value: str, root: Path) -> Path:
    p = Path(value)
    p = (p if p.is_absolute() else root / p).resolve()
    if p.is_relative_to(root) and '사건' not in p.relative_to(root).parts:
        raise MailError(f"받는 자리는 사건 폴더(경로에 '사건' 폴더가 있는 곳)여야 합니다: {p.relative_to(root).as_posix() or '.'} — "
                        '저장소의 다른 자리에 받으면 의뢰인 파일이 git 에 올라갈 수 있습니다.')
    p.mkdir(parents=True, exist_ok=True)
    return p


def shown(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix() if p.is_relative_to(root) else str(p)


def kst(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(KST)


def parse_ref(ref: str) -> tuple[str | None, str | None, str | None]:
    """연결이 준 주소(mail:///messages/{id}[/attachments/{id}]), 메일 id, <internetMessageId> 를 가른다.

    (메일 id, 첨부 id, internetMessageId) 를 돌려준다.
    """
    ref = (ref or '').strip()
    if ref.startswith('<') and ref.endswith('>') and '@' in ref:
        return None, None, ref
    m = re.fullmatch(r'mail:///messages/([^/?#]+)(?:/attachments/([^/?#]+))?(\?.*)?', ref)
    if m:
        if m[3] and 'owner=' in m[3]:
            raise MailError('공유 메일함의 메일은 받지 못합니다. 첨부는 사용자에게 사건 폴더에 저장해 달라고 하십시오.')
        return urllib.parse.unquote(m[1]), (urllib.parse.unquote(m[2]) if m[2] else None), None
    if re.fullmatch(r'[A-Za-z0-9+/=_%-]{20,}', ref):
        return urllib.parse.unquote(ref), None, None
    raise MailError(f'메일 주소를 알아보지 못했습니다: {ref[:80]} — 연결이 준 mail:/// 주소나 <internetMessageId> 를 넘기십시오.')


def get(ref: str, to: str, names=(), eml: bool = False, inline: bool = False, root: Path = ROOT) -> int:
    message_id, attachment_id, internet_id = parse_ref(ref)
    ref_message_id = message_id
    root = root.resolve()
    folder = destination(to, root)
    tok = token()
    msg = find_message(tok, message_id, internet_id)
    message_id = msg['id']
    sender = (msg.get('from') or {}).get('emailAddress') or {}
    when = kst(msg.get('receivedDateTime'))
    print(f"메일: {msg.get('subject') or '(제목 없음)'} | {sender.get('name', '')} <{sender.get('address', '')}> | "
          + (f'{when.year}. {when.month}. {when.day}. {when:%H:%M}' if when else '받은 일시 없음'))

    picked, skipped = [], []
    if attachment_id or names or msg.get('hasAttachments', True) or not eml:
        atts = list_attachments(tok, message_id)
        if attachment_id and not any(a.get('id') == attachment_id for a in atts):
            try:                                        # 목록의 첨부 id 가 연결이 준 것과 다른 꼴로 올 때
                one = call(f'/me/messages/{q(ref_message_id)}/attachments/{q(attachment_id)}'
                           '?$select=id,name,contentType,size,isInline', tok)
                atts.append({**one, 'id': attachment_id, '_message': ref_message_id})
            except MailError:
                pass                                    # choose() 가 첨부 목록과 함께 알린다
        picked, skipped = choose(atts, attachment_id, names, inline)
    new = same = 0
    for att, why in skipped:
        print(f"  건너뜀  {att.get('name')} — {why}")
    for att in picked:
        k = kind(att)
        if k == 'link':
            print(f"  건너뜀  {att.get('name')} — 링크 첨부(원드라이브·셰어포인트). 연결의 read_resource 로 읽는다")
            continue
        data = call(f"/me/messages/{q(att.get('_message') or message_id)}/attachments/{q(att['id'])}/$value", tok, raw=True)
        name = att.get('name') or '첨부'
        if k == 'item' and not name.lower().endswith('.eml'):
            name += '.eml'                              # 첨부된 메일은 원본(MIME)으로 온다
        path, fresh = place(folder, safe_name(name), data)
        print(f"  {'받음' if fresh else '이미 있음'}  {shown(path, root)}  ({len(data):,}바이트)")
        new, same = new + fresh, same + (not fresh)
    if eml:
        data = call(f'/me/messages/{q(message_id)}/$value', tok, raw=True)
        day = f'{when:%Y-%m-%d}_' if when else ''
        path, fresh = place(folder, safe_name(f"{day}{msg.get('subject') or '메일'}.eml"), data)
        print(f"  {'받음' if fresh else '이미 있음'}  {shown(path, root)}  (메일 원본, {len(data):,}바이트)")
        new, same = new + fresh, same + (not fresh)
    if not new and not same:
        print('받은 파일이 없습니다.')
        return 1
    print(f'받은 파일 {new}개' + (f', 이미 있던 파일 {same}개' if same else '') + '.')
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    subs = parser.add_subparsers(dest='command', required=True)
    s = subs.add_parser('get', help='메일의 첨부를 사건 폴더로 받는다')
    s.add_argument('ref', help='연결이 준 메일·첨부 주소(mail:///…), 메일 id, 또는 <internetMessageId>')
    s.add_argument('--to', required=True, help='받을 사건 폴더(저장소 루트 기준 상대경로)')
    s.add_argument('--name', action='append', default=[], help='이름에 이 글자가 든 첨부만 받는다(여러 번 줄 수 있다)')
    s.add_argument('--eml', action='store_true', help='메일 원본(.eml)도 받는다(증거로 낼 때)')
    s.add_argument('--inline', action='store_true', help='본문에 박힌 그림(서명 등)도 받는다')
    s = subs.add_parser('login', help='이 PC에서 처음 한 번 로그인한다')
    s.add_argument('--device', action='store_true', help='브라우저 창이 뜨지 않을 때: 코드를 받아 다른 기기에서 로그인한다')
    subs.add_parser('status', help='로그인되어 있는지 본다(네트워크를 쓰지 않는다)')
    subs.add_parser('logout', help='이 PC의 로그인 정보를 지운다')
    args = parser.parse_args(argv)
    try:
        if args.command == 'get':
            return get(args.ref, args.to, args.name, args.eml, args.inline, root=args.root)
        if args.command == 'login':
            return login(args.device)
        if args.command == 'status':
            return status()
        return logout()
    except MailError as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return exc.code


if __name__ == '__main__':
    raise SystemExit(main())
