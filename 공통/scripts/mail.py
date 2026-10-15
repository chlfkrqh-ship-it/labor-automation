"""원드라이브 과거메일함의 메일(.eml)을 찾고, 본문과 첨부를 사건 폴더에 풀어 둔다.

Power Automate 가 받은 메일을 원드라이브 `과거메일함/자동저장/` 에 .eml 로 저장한다(`공통/메일저장.md`).
검토의견 등에서 의뢰인 메일을 지목하면 이 스크립트로 찾아 읽는다.

    python -B 공통/scripts/mail.py find --from 김철수 --since 2026-10-01
    python -B 공통/scripts/mail.py find --subject 근로시간 --text 연장근로
    python -B 공통/scripts/mail.py open "<eml 경로>" --to "1_검토의견/사건/HPS_근로시간면제 부여"

메일함은 %OneDriveCommercial%·%OneDrive% 아래(없으면 이 저장소의 위 폴더) `과거메일함` 을 하위 폴더까지 본다.
--dir 로 바꿀 수 있다. open 은 사건 폴더에 `메일/{받은 일시}_{제목}/` 을 만들어 본문(본문.txt)과 첨부를 둔다.
사건 자료가 git 에 실리지 않게 경로에 `사건` 폴더가 없는 곳에는 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import codecs
import email
import html
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAILBOX = '과거메일함'
KST = timezone(timedelta(hours=9))
UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def _korean_codecs(name):
    """국내 메일이 흔히 쓰는 ks_c_5601-1987 등을 cp949 로 읽는다(파이썬 기본 목록에 없다)."""
    if name.lower().replace('_', '-') in ('ks-c-5601-1987', 'ks-c-5601', 'ksc5601', 'ksc-5601', 'x-windows-949'):
        return codecs.lookup('cp949')
    return None


codecs.register(_korean_codecs)


def mailbox_dirs(given: str | None = None) -> list[Path]:
    if given:
        return [Path(given)]
    bases = [os.environ.get('OneDriveCommercial'), os.environ.get('OneDrive'), str(ROOT.parent), str(ROOT.parent.parent)]
    found = []
    for b in filter(None, bases):
        d = Path(b) / MAILBOX
        if d.is_dir() and d.resolve() not in [f.resolve() for f in found]:
            found.append(d)
    return found


def safe(text: str, limit: int = 60) -> str:
    text = UNSAFE.sub('_', text or '').strip(' .')
    return (text[:limit].rstrip(' .') or '제목없음')


class Mail:
    def __init__(self, path: Path):
        self.path = path
        self.msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        self.subject = str(self.msg['subject'] or '').strip()
        self.sender = str(self.msg['from'] or '').strip()
        self.to = str(self.msg['to'] or '').strip()
        self.cc = str(self.msg['cc'] or '').strip()
        try:
            d = parsedate_to_datetime(str(self.msg['date']))
            self.when = (d if d.tzinfo else d.replace(tzinfo=KST)).astimezone(KST)
        except (TypeError, ValueError):
            self.when = datetime.fromtimestamp(path.stat().st_mtime, KST)
        self._body = None

    @property
    def body(self) -> str:
        if self._body is None:
            part = self.msg.get_body(preferencelist=('plain', 'html'))
            text = _content(part) if part is not None else ''
            if part is not None and part.get_content_type() == 'text/html':
                text = html_to_text(text)
            self._body = text.strip()
        return self._body

    def attachments(self):
        """(파일 이름, 바이트). 서명 그림처럼 본문에 끼워 넣은 그림은 뺀다."""
        out = []
        for part in self.msg.iter_attachments():
            ctype = part.get_content_type()
            name = part.get_filename()
            if ctype.startswith('image/') and part['content-id'] and not name:
                continue
            if ctype == 'message/rfc822':
                inner = part.get_payload(0)
                data = inner.as_bytes()
                name = (name or str(inner['subject'] or '첨부메일')) + ('' if (name or '').lower().endswith('.eml') else '.eml')
            else:
                data = part.get_payload(decode=True) or b''
            out.append((name or '첨부', data))
        return out


def _content(part) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        data = part.get_payload(decode=True) or b''
        for enc in (part.get_content_charset() or 'utf-8', 'cp949', 'utf-8'):
            try:
                return data.decode(enc)
            except (LookupError, UnicodeDecodeError):
                continue
        return data.decode('utf-8', 'replace')


def html_to_text(text: str) -> str:
    text = re.sub(r'(?is)<(script|style|head)\b.*?</\1>', '', text)
    text = re.sub(r'(?i)<br\s*/?>|</(p|div|tr|li|h[1-6])>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text).replace('\xa0', ' ')
    return re.sub(r'\n[ \t]*\n[\s]*', '\n\n', text)


def _day(text: str) -> date:
    return datetime.strptime(text.replace('.', '-').strip('- '), '%Y-%m-%d').date()


def find(args) -> int:
    dirs = mailbox_dirs(args.dir)
    if not dirs:
        print(f'메일함({MAILBOX})을 찾지 못했습니다. 원드라이브에 {MAILBOX} 폴더가 있는지, Power Automate 저장이 켜져 있는지 '
              '확인하십시오(공통/메일저장.md).')
        return 1
    hits = []
    for d in dirs:
        for p in d.rglob('*.eml'):
            try:
                m = Mail(p)
            except Exception as exc:                    # 깨진 파일 하나 때문에 찾기를 멈추지 않는다
                print(f'  읽지 못함: {p} ({exc})', file=sys.stderr)
                continue
            if args.sender and args.sender.lower() not in m.sender.lower():
                continue
            if args.subject and args.subject.lower() not in m.subject.lower():
                continue
            if args.since and m.when.date() < _day(args.since):
                continue
            if args.until and m.when.date() > _day(args.until):
                continue
            if args.text and args.text.lower() not in (m.subject + '\n' + m.body).lower():
                continue
            hits.append(m)
    hits.sort(key=lambda m: m.when, reverse=True)
    for m in hits[:args.limit]:
        names = ', '.join(n for n, _ in m.attachments()) or '-'
        print(f'{m.when:%Y-%m-%d %H:%M} | {m.sender} | {m.subject} | 첨부: {names}\n    {m.path}')
    more = len(hits) - args.limit
    print(f'{len(hits)}건' + (f' (앞 {args.limit}건만 보임 — 조건을 더 주십시오)' if more > 0 else ''))
    return 0


def open_mail(args) -> int:
    m = Mail(Path(args.eml))
    to = Path(args.to)
    if not to.is_absolute():
        to = ROOT / to
    if '사건' not in to.resolve().parts:
        print(f'사건 폴더(경로에 `사건` 이 있는 곳)에만 풉니다 — 받은 경로: {args.to}')
        return 1
    out = to / '메일' / f'{m.when:%Y%m%d-%H%M}_{safe(m.subject)}'
    out.mkdir(parents=True, exist_ok=True)
    head = [f'보낸 사람: {m.sender}', f'받는 사람: {m.to}'] + ([f'참조: {m.cc}'] if m.cc else []) + [
        f'받은 일시: {m.when:%Y. %m. %d. %H:%M}', f'제목: {m.subject}', f'원본: {m.path}']
    written, used = [], set()
    for name, data in m.attachments():
        target = safe(name, 80)
        stem, ext = os.path.splitext(target)
        n = 2
        while target.lower() in used:                   # 같은 이름 첨부는 _2, _3 을 붙인다
            target = f'{stem}_{n}{ext}'
            n += 1
        used.add(target.lower())
        (out / target).write_bytes(data)
        written.append(target)
    head.append('첨부: ' + (', '.join(written) if written else '없음'))
    (out / '본문.txt').write_text('\n'.join(head) + '\n\n' + m.body + '\n', encoding='utf-8')
    print(f'풀어 둔 곳: {out}')
    print('  본문.txt' + ''.join(f'\n  {w}' for w in written))
    return 0


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('find', help='메일 찾기')
    f.add_argument('--from', dest='sender', help='보낸 사람 이름·주소 일부')
    f.add_argument('--subject', help='제목 일부')
    f.add_argument('--text', help='제목·본문에 든 낱말')
    f.add_argument('--since', help='이날부터(2026-10-01)')
    f.add_argument('--until', help='이날까지')
    f.add_argument('--limit', type=int, default=20)
    f.add_argument('--dir', help=f'메일함 폴더(기본: 원드라이브 {MAILBOX})')
    o = sub.add_parser('open', help='본문과 첨부를 사건 폴더에 풀기')
    o.add_argument('eml')
    o.add_argument('--to', required=True, help='사건 폴더(예: 1_검토의견/사건/{의뢰인}_{검토내용})')
    args = ap.parse_args()
    sys.exit(find(args) if args.cmd == 'find' else open_mail(args))


if __name__ == '__main__':
    main()
