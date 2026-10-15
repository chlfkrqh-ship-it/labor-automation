"""mail.py — 과거메일함의 .eml 찾기와 사건 폴더에 풀기."""
import subprocess
import sys
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'mail.py'


def run(*args):
    return subprocess.run([sys.executable, '-B', str(SCRIPT), *args], capture_output=True, text=True, encoding='utf-8')


class MailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.box = t / '과거메일함' / '자동저장'
        self.box.mkdir(parents=True)
        self.case = t / '1_검토의견' / '사건' / 'HPS_근로시간면제'
        # 1) 한글 제목·본문, 첨부 PDF 와 같은 이름 첨부 둘
        m = EmailMessage()
        m['From'] = '김철수 <kim@client.co.kr>'
        m['To'] = '노무사 <me@pyeongan.kr>'
        m['Subject'] = '근로시간면제 한도 질의'
        m['Date'] = 'Tue, 14 Oct 2026 09:12:00 +0900'
        m.set_content('안녕하세요.\n근로시간면제 한도를 문의드립니다.')
        m.add_attachment(b'%PDF-1.4 sample', maintype='application', subtype='pdf', filename='단체협약.pdf')
        m.add_attachment(b'second', maintype='application', subtype='pdf', filename='단체협약.pdf')
        (self.box / 'a.eml').write_bytes(bytes(m))
        # 2) ks_c_5601-1987(국내 메일 흔한 표기) 제목·본문, HTML 만 있는 메일
        subject = '=?ks_c_5601-1987?B?' + __import__('base64').b64encode('연차수당 문의'.encode('cp949')).decode() + '?='
        body = '<html><body><p>연차수당&nbsp;계산을</p><div>부탁드립니다.</div></body></html>'.encode('cp949')
        raw = (b'From: =?utf-8?B?' + __import__('base64').b64encode('이영희'.encode()) + b'?= <lee@other.com>\r\n'
               b'Subject: ' + subject.encode() + b'\r\n'
               b'Date: Wed, 01 Oct 2026 18:00:00 +0900\r\n'
               b'MIME-Version: 1.0\r\nContent-Type: text/html; charset="ks_c_5601-1987"\r\n'
               b'Content-Transfer-Encoding: 8bit\r\n\r\n' + body)
        (self.box / 'b.eml').write_bytes(raw)

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_by_sender_subject_date_and_text(self):
        r = run('find', '--dir', str(self.box.parent), '--from', '김철수')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('근로시간면제 한도 질의', r.stdout)
        self.assertIn('첨부: 단체협약.pdf, 단체협약.pdf', r.stdout)
        self.assertIn('1건', r.stdout)
        self.assertIn('연차수당 문의', run('find', '--dir', str(self.box.parent), '--subject', '연차').stdout)
        self.assertIn('0건', run('find', '--dir', str(self.box.parent), '--since', '2026-10-02', '--from', '이영희').stdout)
        self.assertIn('연차수당 문의', run('find', '--dir', str(self.box.parent), '--text', '부탁드립니다').stdout)

    def test_open_writes_body_and_attachments_into_case_folder(self):
        r = run('open', str(self.box / 'a.eml'), '--to', str(self.case))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = self.case / '메일' / '20261014-0912_근로시간면제 한도 질의'
        body = (out / '본문.txt').read_text(encoding='utf-8')
        self.assertIn('보낸 사람: 김철수 <kim@client.co.kr>', body)
        self.assertIn('근로시간면제 한도를 문의드립니다.', body)
        self.assertEqual((out / '단체협약.pdf').read_bytes(), b'%PDF-1.4 sample')
        self.assertEqual((out / '단체협약_2.pdf').read_bytes(), b'second')

    def test_korean_legacy_charset_and_html_only_mail_are_readable(self):
        r = run('open', str(self.box / 'b.eml'), '--to', str(self.case))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = (self.case / '메일' / '20261001-1800_연차수당 문의' / '본문.txt').read_text(encoding='utf-8')
        self.assertIn('보낸 사람: 이영희 <lee@other.com>', body)
        self.assertIn('연차수당 계산을\n부탁드립니다.', body)

    def test_open_refuses_folders_outside_a_case_folder(self):
        r = run('open', str(self.box / 'a.eml'), '--to', str(Path(self.tmp.name) / '공통'))
        self.assertEqual(r.returncode, 1)
        self.assertFalse((Path(self.tmp.name) / '공통').exists())


if __name__ == '__main__':
    unittest.main()
