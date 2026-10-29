"""제출 묶음의 서증 압축파일(4_서면작성/scripts/evidence_zip.py)을 확인한다.

이름은 서면 파일 이름에서 판 이름을 떼고 '_서증.zip' 을 붙이고, 증거/ 의 파일만 호증 번호 순으로 담으며,
다시 열어 목록·내용이 같은지 보고, --확인 은 증거가 바뀐 압축파일을 잡아야 한다(2026. 10. 21. 담당자 지시).
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location(
    'evidence_zip', Path(__file__).parents[2] / '4_서면작성' / 'scripts' / 'evidence_zip.py')
evidence_zip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence_zip)


class EvidenceZipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / '제출'
        (self.root / '증거').mkdir(parents=True)
        (self.root / '참고자료').mkdir()
        (self.root / '(홍길동) 준비서면_초안.docx').write_bytes(b'docx')
        (self.root / '참고자료' / '참고자료 1_판결.pdf').write_bytes(b'ref')
        for name in ('을 제10호증_징계현황.pdf', '을 제2호증_근로계약서.pdf', '을 제3호증의1_회의록.pdf'):
            (self.root / '증거' / name).write_bytes(('내용 ' + name).encode('utf-8'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_name_order_and_contents(self):
        out = evidence_zip.만들기(self.root)
        self.assertEqual(out.name, '(홍길동) 준비서면_서증.zip')
        with zipfile.ZipFile(out) as z:
            self.assertEqual(z.namelist(), ['을 제2호증_근로계약서.pdf', '을 제3호증의1_회의록.pdf', '을 제10호증_징계현황.pdf'])
            self.assertEqual(z.read('을 제2호증_근로계약서.pdf'), '내용 을 제2호증_근로계약서.pdf'.encode('utf-8'))
            self.assertTrue(all(i.flag_bits & 0x800 for i in z.infolist()))   # 한글 이름은 UTF-8 표시
        self.assertEqual(evidence_zip.main([str(self.root), '--확인']), 0)

    def test_version_suffixes_are_removed(self):
        for stem, base in (('(홍길동) 준비서면_1차 수정안', '(홍길동) 준비서면'), ('(한전) 준비서면_Rev_1', '(한전) 준비서면'), ('(이케아) 검토의견서_최종', '(이케아) 검토의견서'),
                           ('(박준선) 항소이유서_초안', '(박준선) 항소이유서'), ('(김경민) 소장', '(김경민) 소장')):
            with self.subTest(stem=stem):
                self.assertEqual(evidence_zip.VERSION.sub('', stem), base)

    def test_check_catches_changed_evidence(self):
        evidence_zip.만들기(self.root)
        (self.root / '증거' / '을 제2호증_근로계약서.pdf').write_bytes(b'changed')
        self.assertEqual(evidence_zip.main([str(self.root), '--확인']), 1)
        (self.root / '증거' / '을 제11호증_새증거.pdf').write_bytes(b'new')
        self.assertTrue(evidence_zip.맞대기(self.root / '(홍길동) 준비서면_서증.zip', evidence_zip.증거목록(self.root)))

    def test_two_briefs_need_a_name(self):
        (self.root / '(홍길동) 참고서면_초안.docx').write_bytes(b'docx')
        with self.assertRaises(SystemExit):
            evidence_zip.만들기(self.root)
        out = evidence_zip.만들기(self.root, '(홍길동) 참고서면')
        self.assertEqual(out.name, '(홍길동) 참고서면_서증.zip')


if __name__ == '__main__':
    unittest.main()
