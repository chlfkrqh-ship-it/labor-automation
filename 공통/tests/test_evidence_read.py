"""전 면 읽기 기록(4_서면작성/scripts/evidence_read.py)을 확인한다.

호증마다 단위(PDF 면, 그림, 압축파일 안 파일, 엑셀 시트)별 빈 줄이 있는 틀을 만드는지, 모든 단위를 채우지 않으면 check 가
막는지, '같음'·'반복'만 적은 줄을 빈 줄로 세는지, 기록한 뒤 파일이 바뀌면 막는지, 번호를 다시 매기면 기록을 옮기는지 본다.
압축·엑셀·워드·한글(hwpx)·메일 호증도 단위마다 글 덩이·면·그림의 확인표가 있어야 지나가는지 본다(OtherFormatsTest).
문자인식(Windows)은 돌리지 않는다(--no-ocr).
"""
import importlib.util
import io
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

import pymupdf

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('evidence_read', ROOT / '4_서면작성/scripts/evidence_read.py')
er = importlib.util.module_from_spec(spec)
spec.loader.exec_module(er)

글 = ('공지 문자 안내입니다 오늘도 안전한 하루 되십시오\n'       # 글자층이 넉넉한 면(80자 넘게)
     '현장의 모든 구성원은 안전 수칙을 지켜 주시기 바랍니다\n'
     '작업 전후 점검표를 확인하고 이상이 있으면 즉시 보고합니다\n'
     '보호구를 갖추고 정해진 통로로만 다닙니다\n')


def make_pdf(path: Path, pages):
    d = pymupdf.open()
    for t in pages:
        d.new_page().insert_text((40, 72), t, fontsize=7, fontname='korea')
    d.save(path)


def tok(case: Path, key: str, no: int) -> str:
    """그 면의 확인표. 글 면은 면별 글의 면 끝에서 읽고, 그림으로 볼 면은 `그림` 이 그린 띠의 값(같은 셈)이다."""
    글자 = (case / '증거관리' / '호증글자' / f'{key}.txt').read_text(encoding='utf-8')
    m = re.search(r'\[%d면 끝 · 확인표 ([A-Z0-9]{4})\]' % no, 글자)
    if m:
        return m.group(1)
    rec = (case / '증거관리' / '호증읽기' / f'{key}.md').read_text(encoding='utf-8')
    return er.확인표(case, er.해시(case / re.search(r'^파일: (.+)$', rec, re.M).group(1)), no, '그림')


XL = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
XR = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'


def make_xlsx(path: Path, 시트: dict, 더=None):
    """시트 이름 → [[칸 값]] 로 작은 통합 문서를 만든다(글은 공유 문자열). 더: 넣을 파일 {이름: 바이트}."""
    공유, files = [], {}
    sheets, rels = [], []
    for i, (이름, 행들) in enumerate(시트.items(), 1):
        sheets.append(f'<sheet name="{이름}" sheetId="{i}" r:id="rId{i}"/>')
        rels.append(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>')
        rows = []
        for r, 칸 in enumerate(행들, 1):
            cs = []
            for c, v in enumerate(칸):
                ref = f'{chr(65 + c)}{r}'
                if isinstance(v, str):
                    공유.append(v)
                    cs.append(f'<c r="{ref}" t="s"><v>{len(공유) - 1}</v></c>')
                else:
                    cs.append(f'<c r="{ref}"><v>{v}</v></c>')
            rows.append(f'<row r="{r}">{"".join(cs)}</row>')
        files[f'xl/worksheets/sheet{i}.xml'] = f'<worksheet xmlns="{XL}"><sheetData>{"".join(rows)}</sheetData></worksheet>'
    files['xl/workbook.xml'] = f'<workbook xmlns="{XL}" xmlns:r="{XR}"><sheets>{"".join(sheets)}</sheets></workbook>'
    files['xl/_rels/workbook.xml.rels'] = f'<Relationships xmlns="{PKG}">{"".join(rels)}</Relationships>'
    files['xl/sharedStrings.xml'] = f'<sst xmlns="{XL}">' + ''.join(f'<si><t>{s}</t></si>' for s in 공유) + '</sst>'
    files.update(더 or {})
    with zipfile.ZipFile(path, 'w') as z:
        for n, x in files.items():
            z.writestr(n, x)


def 기대표(case: Path, key: str, 자료: bool = False) -> dict:
    """그 호증 기록의 단위마다 있어야 할 확인표(글 덩이·면은 면별 글에, 그림은 `그림` 이 그린 띠에 있는 값)."""
    자 = er.자리(case, 자료)
    rec = 자.기록_파일(key).read_text(encoding='utf-8')
    return er.기대_확인표(자, key, case / re.search(r'^파일: (.+)$', rec, re.M).group(1)) or {}


def run(*args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = er.main([str(a) for a in args])
    return code, out.getvalue()


class EvidenceReadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / 'GGM_정직'
        self.ours = self.case / '라운드1' / '우리증거'
        self.ours.mkdir(parents=True)
        (self.case / '라운드1' / '상대증거').mkdir()
        make_pdf(self.ours / '사 제6호증 문자.pdf', [글 + '1면', 글 + '2면', 글 + '작업 중 시험 기기 사용 금지'])
        make_pdf(self.case / '라운드1' / '상대증거' / '노 제1호증 진술서.pdf', [글 + '진술'])
        (self.ours / '사 제2호증 현장 사진.jpg').write_bytes(b'\xff\xd8\xff')
        with zipfile.ZipFile(self.ours / '사 제3호증 사진 묶음.zip', 'w') as z:
            z.writestr('b.jpg', b'1')
            z.writestr('a.jpg', b'2')
        make_xlsx(self.ours / '사 제4호증 근무표.xlsx', {'1월': [['성명', '출근'], ['홍길동', 20]], '2월': [['성명', '출근'], ['홍길동', 18]]})
        (self.ours / '사 제5호증 메모.docx').write_bytes(b'PK')
        (self.case / '라운드1' / '상대증거' / '신청이유서(2).pdf').write_bytes(b'')     # 호증 번호가 없는 상대 서면은 보지 않는다

    def tearDown(self):
        self.tmp.cleanup()

    def rec(self, key):
        return self.case / '증거관리' / '호증읽기' / f'{key}.md'

    def fill(self, key, body, 방식='글자층 전 면, 그림 3면', 문구='3면 "작업 중 시험 기기 사용 금지"'):
        t = self.rec(key).read_text(encoding='utf-8')
        head, rest = t.split('## 면별 내용', 1)
        tail = rest.split('## 쟁점에 닿는 문구', 1)[1]
        head = head.replace('읽은 방식: \n', f'읽은 방식: {방식}\n')
        tail = tail.replace('\n- \n', f'\n- {문구}\n', 1)
        self.rec(key).write_text(head + '## 면별 내용\n\n' + body + '\n\n## 쟁점에 닿는 문구' + tail, encoding='utf-8')

    def test_make_writes_one_blank_line_per_unit_for_every_exhibit(self):
        code, out = run('make', self.case, '--no-ocr')
        self.assertEqual(code, 0)
        self.assertEqual(sorted(p.stem for p in (self.case / '증거관리' / '호증읽기').glob('*.md')),
                         ['노1', '사2', '사3', '사4', '사5', '사6'])
        사6 = self.rec('사6').read_text(encoding='utf-8')
        self.assertIn('파일: 라운드1/우리증거/사 제6호증 문자.pdf', 사6)
        self.assertRegex(사6, r'해시: [0-9a-f]{12} · 3면')
        for line in ('- 1면: ', '- 2면: ', '- 3면: '):
            self.assertIn(line + '\n', 사6)
        self.assertIn('- [파일] a.jpg: \n- [파일] b.jpg: ', self.rec('사3').read_text(encoding='utf-8'))
        self.assertIn('- [시트] 1월: \n- [시트] 2월: ', self.rec('사4').read_text(encoding='utf-8'))
        self.assertIn('- 1면: ', self.rec('사2').read_text(encoding='utf-8'))
        self.assertIn('- 전체: ', self.rec('사5').read_text(encoding='utf-8'))
        면별글 = (self.case / '증거관리' / '호증글자' / '사6.txt').read_text(encoding='utf-8')
        self.assertIn('=== 3면', 면별글)
        self.assertIn('작업 중 시험 기기 사용 금지', 면별글)

    def test_check_blocks_until_every_page_is_written(self):
        run('make', self.case, '--no-ocr', '--호증', '사6')
        code, out = run('check', self.case, '--호증', '사6')
        self.assertEqual(code, 1)
        self.assertIn('1~3면', out)
        self.assertIn("'읽은 방식'이 비었다", out)          # 빈 '읽은 방식:' 이 다음 줄을 값으로 읽지 않는다
        self.fill('사6', '- 1면: 안전 안내 문자(10. 1.)')     # 첫 면만 읽은 기록
        code, out = run('check', self.case, '--호증', '사6')
        self.assertEqual(code, 1)
        self.assertIn('읽지 않았거나 비운 단위 2/3: 2~3면', out)
        self.fill('사6', '- 1면: 안전 안내 문자(10. 1.)\n- 2~3면: 반복 기재')   # 묶어서 '반복'만 적은 기록
        self.assertEqual(run('check', self.case, '--호증', '사6')[0], 1)
        다 = '- 1면: 안전 안내 문자(10. 1.){}\n- 2면: 안전 안내 문자(10. 2.){}\n- 3면: 실천사항 "작업 중 시험 기기 사용 금지"{}'
        self.fill('사6', 다.format('', '', ''))                 # 칸은 찼지만 면을 끝까지 열어 본 증표(확인표)가 없다
        code, out = run('check', self.case, '--호증', '사6')
        self.assertEqual(code, 1)
        self.assertIn('확인표가 없거나 맞지 않는 면 3/3: 1~3면', out)
        self.fill('사6', 다.format(*(f' 확인표 {tok(self.case, "사6", n)}' for n in (1, 2, 3))))
        code, out = run('check', self.case, '--호증', '사6')
        self.assertEqual(code, 0, out)

    def test_ranges_and_other_units_count(self):
        run('make', self.case, '--no-ocr')
        확인 = ' '.join(tok(self.case, '사6', n) for n in (1, 2, 3))
        self.fill('사6', f'- 1~3면: 일자별 안전 문자(10. 1.~10. 3.), 3면에 시험 기기 사용 금지 (확인표 {확인})')
        self.fill('사3', '- [파일] a.jpg: 출입문 사진\n- [파일] b.jpg: 작업대 사진', 문구='없음')     # 열리지 않는 그림은 신고로 본다
        self.fill('사4', '- [시트] 1월: 1월 근무표\n- [시트] 2월: 2월 근무표', 문구='없음')
        code, out = run('check', self.case, '--호증', '사4')
        self.assertEqual(code, 1)                               # 엑셀도 시트마다 끝까지 읽은 확인표가 있어야 한다
        self.assertIn('확인표가 없거나 맞지 않는 단위 2/2: [시트] 1월, [시트] 2월', out)
        표 = 기대표(self.case, '사4')
        self.fill('사4', f"- [시트] 1월: 1월 근무표 확인표 {표['[시트] 1월'][0]}\n- [시트] 2월: 2월 근무표 확인표 {표['[시트] 2월'][0]}", 문구='없음')
        self.assertEqual(run('check', self.case, '--호증', '사6', '사3', '사4')[0], 0)
        self.fill('사3', '- [파일] a.jpg: 출입문 사진', 문구='없음')
        code, out = run('check', self.case, '--호증', '사3')
        self.assertEqual(code, 1)
        self.assertIn('[파일] b.jpg', out)
        code, out = run('check', self.case)
        self.assertEqual(code, 1)
        self.assertIn('노 제1호증', out)                     # 상대 호증도 읽는다
        self.assertNotIn('신청이유서', out)

    def test_changed_file_is_blocked_and_redo_keeps_old_notes(self):
        run('make', self.case, '--no-ocr', '--호증', '사6')
        self.fill('사6', '\n'.join(f'- {n}면: {x} 확인표 {tok(self.case, "사6", n)}' for n, x in ((1, '가'), (2, '나'), (3, '다'))))
        self.assertEqual(run('check', self.case, '--호증', '사6')[0], 0)
        make_pdf(self.ours / '사 제6호증 문자.pdf', [글 + '1면', 글 + '2면', 글 + '3면', 글 + '새로 붙은 4면'])
        code, out = run('check', self.case, '--호증', '사6')
        self.assertEqual(code, 1)
        self.assertIn('파일이 바뀜', out)
        self.assertIn('읽지 않았거나 비운 단위 1/4: 4면', out)
        run('make', self.case, '--no-ocr', '--다시', '사6')
        t = self.rec('사6').read_text(encoding='utf-8')
        self.assertIn('- 4면: \n', t)
        self.assertIn('## 앞선 기록', t)
        self.assertIn('- 3면: 다 확인표', t.split('## 앞선 기록')[1])
        code, out = run('check', self.case, '--호증', '사6')
        self.assertEqual(code, 1)                           # 앞선 기록은 세지 않는다. 다시 읽어 채워야 한다
        self.assertIn('1~4면', out)

    def test_renumbered_exhibit_carries_its_record(self):
        run('make', self.case, '--no-ocr', '--호증', '사6')
        self.fill('사6', '\n'.join(f'- {n}면: {x} 확인표 {tok(self.case, "사6", n)}' for n, x in ((1, '가'), (2, '나'), (3, '다'))))
        (self.ours / '사 제6호증 문자.pdf').rename(self.ours / '사 제9호증 문자.pdf')
        code, out = run('make', self.case, '--no-ocr', '--호증', '사9')
        self.assertIn('옮김: 사6 → 사9', out)
        self.assertFalse(self.rec('사6').exists())
        t = self.rec('사9').read_text(encoding='utf-8')
        self.assertTrue(t.startswith('# 사 제9호증 읽기 기록'))
        self.assertIn('파일: 라운드1/우리증거/사 제9호증 문자.pdf', t)
        self.assertEqual(run('check', self.case, '--호증', '사9')[0], 0)

    def test_material_mode_for_review_opinions(self):
        case = Path(self.tmp.name) / '1_검토의견' / 'HPS_근로시간면제'
        att = case / '첨부'
        att.mkdir(parents=True)
        make_pdf(att / '단체협약.pdf', [글 + '제1조', 글 + '제2조 근로시간면제'])
        (att / '~$잠금.docx').write_bytes(b'')
        run('make', case, '--자료', att, '--no-ocr')
        rec = case / '작업' / '자료읽기' / '단체협약.pdf.md'
        self.assertTrue(rec.is_file())
        self.assertTrue((case / '작업' / '자료글자' / '단체협약.pdf.txt').is_file())
        self.assertFalse((case / '작업' / '자료읽기' / '~$잠금.docx.md').exists())
        code, out = run('check', case, '--자료', att)
        self.assertEqual(code, 1)
        self.assertIn('단체협약.pdf', out)

    def test_our_own_files_are_not_client_material(self):
        """검토의견서 변환 부품·붙이려고 받은 판결·법제처 수확·PDF 로 낸 검토의견서·계산표는 의뢰인 자료가 아니다(2026. 11. 2. 첫 밤 점검)."""
        case = Path(self.tmp.name) / 'HPS_근로시간면제'
        for 폴더 in ('첨부', '전환작업/워드확인', '별첨_각주 자료', '법제처2', '계산'):
            (case / 폴더).mkdir(parents=True)
        make_pdf(case / '첨부' / '단체협약.pdf', [글])
        make_pdf(case / '전환작업' / '워드확인' / 'opinion.pdf', [글])
        (case / '전환작업' / '워드확인' / 'page9.png').write_bytes(b'x')
        make_pdf(case / '별첨_각주 자료' / '각주01_회시.pdf', [글])
        (case / '법제처2' / '목록.txt').write_text('x', encoding='utf-8')
        make_pdf(case / '계산' / '표.pdf', [글])
        make_pdf(case / '(HPS) 근로시간면제 관련 검토.pdf', [글])
        (case / '_추출.txt').write_text('x', encoding='utf-8')
        (case / 'HPS_근로시간면제_계산표.xlsx').write_bytes(b'x')
        (case / '홍길동_노동금액계산표.xlsx').write_bytes(b'x')
        (case / '상대방 별지 계산표.xlsx').write_bytes(b'x')
        self.assertEqual(sorted(er.자료_목록(case, [case])), ['단체협약.pdf', '상대방 별지 계산표.xlsx'])


class CheaperReadingTest(unittest.TestCase):
    """읽는 비용을 줄이되 글을 하나도 빼지 않는지 본다(2026. 11. 2. 담당 노무사 "많이 줄여지지 않아도 완결성이 더 중요")."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.case = self.root / '4_서면작성' / '사건' / 'GGM_정직'
        self.ours = self.case / '라운드1' / '우리증거'
        self.ours.mkdir(parents=True)
        self.env = mock.patch.dict(os.environ, {'EVIDENCE_READ_ROOT': str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def text(self, key):
        return (self.case / '증거관리' / '호증글자' / f'{key}.txt').read_text(encoding='utf-8')

    def rec(self, case, key):
        return case / '증거관리' / '호증읽기' / f'{key}.md'

    def test_repeated_lines_are_numbered_once_and_every_page_keeps_its_own_lines(self):
        머리 = '공지 문자\n현장의 모든 구성원은 안전 수칙을 지켜 주시기 바랍니다\n'
        쪽 = [머리 + f'{n}일 실천사항 점검표를 확인하고 이상이 있으면 즉시 보고합니다 보호구를 갖춥니다' for n in range(1, 7)]
        쪽[2] = 머리 + '작업 중 시험 기기 등 전자 장비 사용 금지 보호구를 갖추고 통로로만 다닙니다'
        make_pdf(self.ours / '사 제6호증 문자.pdf', 쪽)
        run('make', self.case, '--no-ocr')
        t = self.text('사6')
        self.assertIn('- R1: ', t)
        self.assertEqual(t.count('현장의 모든 구성원은 안전 수칙을 지켜 주시기 바랍니다'), 1)    # 되풀이 줄은 한 번만
        셋째 = t.split('=== 3면')[1].split('\n=== ')[0]
        self.assertIn('작업 중 시험 기기 등 전자 장비 사용 금지', 셋째)         # 그 면에만 있는 줄은 그대로
        self.assertIn('[되풀이 줄: R1, R2]', 셋째)                                      # 어느 면에 어느 줄이 있는지 남는다

    def test_table_cells_are_kept_and_hard_pages_must_be_seen_as_images(self):
        d = pymupdf.open()
        pg = d.new_page()
        pg.insert_text((50, 60), '급여 지급 내역 안내 문서입니다 아래 표와 같이 지급하였음을 알려 드립니다\n'
                                 '확인 바랍니다 담당 부서 인사팀 문의는 내선으로 부탁드립니다 지급일은 매월 25일입니다', fontsize=8, fontname='korea')
        x0, y0, cw, rh = 50, 100, 120, 20
        for r in range(4):
            pg.draw_line((x0, y0 + r * rh), (x0 + 3 * cw, y0 + r * rh))
        for c in range(4):
            pg.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + 3 * rh))
        for r, row in enumerate([['성명', '월', '지급액'], ['홍길동', '1월', '3,000,000'], ['김담당', '2월', '3,100,000']]):
            for c, cell in enumerate(row):
                pg.insert_text((x0 + c * cw + 5, y0 + r * rh + 14), cell, fontsize=9, fontname='korea')
        d.new_page().insert_text((50, 80), '서명', fontsize=9, fontname='korea')        # 글자가 거의 없는 면(서명·사진)
        d.save(self.ours / '사 제4호증 급여.pdf')
        run('make', self.case, '--no-ocr')
        t = self.text('사4')
        self.assertIn('[표 1]', t)
        self.assertIn('| 홍길동 | 1월 | 3,000,000 |', t)
        self.assertIn('그림으로 볼 면: 2면(글자 거의 없음)', t)
        rec = self.rec(self.case, '사4')
        self.assertIn('그림으로 볼 면: 2면(글자 거의 없음)', rec.read_text(encoding='utf-8'))
        body = (f'- 1면: 급여 지급 안내와 2명의 1·2월 지급액 표 확인표 {tok(self.case, "사4", 1)}\n'
                f'- 2면: 담당자 서명 확인표 {tok(self.case, "사4", 2)}')
        self.assertIn('[2면 끝 · 그림으로 볼 면', t)                 # 그림으로 볼 면의 확인표는 글에 없고 그림에만 있다
        self.assertNotIn(tok(self.case, '사4', 2), t)
        t = rec.read_text(encoding='utf-8')
        head, rest = t.split('## 면별 내용', 1)
        tail = rest.split('## 쟁점에 닿는 문구', 1)[1].replace('\n- \n', '\n- 없음\n', 1)
        rec.write_text(head.replace('읽은 방식: \n', '읽은 방식: 글자층 1면\n') + '## 면별 내용\n\n' + body + '\n\n## 쟁점에 닿는 문구' + tail,
                       encoding='utf-8')
        code, out = run('check', self.case)
        self.assertEqual(code, 1)
        self.assertIn('그림으로 볼 면 2면을 그림으로 본 기록이 없다', out)
        rec.write_text(rec.read_text(encoding='utf-8').replace('읽은 방식: 글자층 1면', '읽은 방식: 글자층 1면, 그림 2면'), encoding='utf-8')
        self.assertEqual(run('check', self.case)[0], 0)
        그림폴더 = self.root / '그림'
        code, out = run('그림', self.case, '--호증', '사4', '--out', 그림폴더)
        self.assertEqual(code, 0, out)
        png = 그림폴더 / '사4' / '002면.png'
        self.assertTrue(png.is_file(), out)                          # 그림으로 볼 면만 그린다
        self.assertFalse((그림폴더 / '사4' / '001면.png').exists())
        쪽 = pymupdf.open(self.ours / '사 제4호증 급여.pdf')[1].rect
        pix = pymupdf.Pixmap(str(png))
        self.assertGreater(pix.height, pix.width * 쪽.height / 쪽.width + 30)      # 그림 아래에 확인표 띠가 붙는다

    def test_same_file_read_in_another_case_is_offered_but_must_be_read_again(self):
        쪽 = [글 + f'{n}면 안내' for n in range(1, 4)]
        make_pdf(self.ours / '사 제6호증 문자.pdf', 쪽)
        run('make', self.case, '--no-ocr')
        rec = self.rec(self.case, '사6')
        t = rec.read_text(encoding='utf-8')
        t = t.replace('읽은 방식: \n', '읽은 방식: 글자층 전 면\n')
        for n in (1, 2, 3):
            t = t.replace(f'- {n}면: ', f'- {n}면: 안전 안내({n}) 확인표 {tok(self.case, "사6", n)}')
        t = t.replace('면)\n\n- \n', '면)\n\n- 3면 "안내"\n')
        rec.write_text(t, encoding='utf-8')
        self.assertEqual(run('check', self.case)[0], 0)
        other = self.root / '4_서면작성' / '사건' / 'GGM_경영설명회'
        (other / '라운드1' / '우리증거').mkdir(parents=True)
        (other / '라운드1' / '우리증거' / '갑 제2호증 같은 문자.pdf').write_bytes((self.ours / '사 제6호증 문자.pdf').read_bytes())
        code, out = run('make', other, '--no-ocr')
        self.assertIn('다른 사건 기록에서 옮겨 옴 1건', out)
        t = self.rec(other, '갑2').read_text(encoding='utf-8')
        self.assertIn('옮겨 온 기록: 4_서면작성/사건/GGM_정직/증거관리/호증읽기/사6.md', t)
        self.assertIn('- 1면: (옮김) 안전 안내(1)', t)
        self.assertNotIn('확인표', t.split('## 면별 내용')[1].split('## 쟁점')[0])     # 그 사건의 확인표는 옮기지 않는다
        self.assertIn('## 옮겨 온 기록의 쟁점 문구', t)
        code, out = run('check', other)
        self.assertEqual(code, 1)                                   # 다른 사건의 기록으로 갈음하지 않는다
        self.assertIn('다른 사건 기록에서 옮긴 줄 3개', out)
        t = t.replace('(옮김) ', '').replace('읽은 방식: \n', '읽은 방식: 글자층 전 면\n').replace('면)\n\n- \n', '면)\n\n- 없음\n', 1)
        self.rec(other, '갑2').write_text(t, encoding='utf-8')
        code, out = run('check', other)
        self.assertEqual(code, 1)                                   # 같은 파일이어도 이 사건에서 면마다 다시 열어 보아야 한다
        self.assertIn('확인표가 없거나 맞지 않는 면 3/3', out)
        self.assertNotEqual(tok(other, '갑2', 1), tok(self.case, '사6', 1))
        for n in (1, 2, 3):
            t = t.replace(f'- {n}면: 안전 안내({n})', f'- {n}면: 안전 안내({n}) 확인표 {tok(other, "갑2", n)}')
        self.rec(other, '갑2').write_text(t, encoding='utf-8')
        self.assertEqual(run('check', other)[0], 0)


class ProofOfReadingTest(unittest.TestCase):
    """면을 끝까지 열어 본 증표(확인표) 없이는 지나가지 못하는지 본다.
    2026. 11. 3. 한전 태양광 22명: 스캔 계좌내역 95면을 문자인식 줄을 걸러 금액이 큰 줄 중심으로 읽고 나머지를 모음 그림으로 보았는데
    '그림 전 면(모음 그림)'이라는 신고로 check 를 지났다. 담당 노무사 "법률자료작성이므로 완결성 100%에 수렴해야 한다고 대충 읽고 쓰면 그게 되겠니"."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / '한전_태양광'
        self.ours = self.case / '라운드1' / '우리증거'
        self.ours.mkdir(parents=True)
        make_pdf(self.ours / '을 제105호증의8 계좌내역.pdf', [글 + f'{n}면 거래' for n in range(1, 5)])
        run('make', self.case, '--no-ocr')
        self.rec = self.case / '증거관리' / '호증읽기' / '을105-8.md'

    def tearDown(self):
        self.tmp.cleanup()

    def fill(self, 줄들, 방식='글자층 전 면'):
        t = self.rec.read_text(encoding='utf-8')
        head, rest = t.split('## 면별 내용', 1)
        tail = rest.split('## 쟁점에 닿는 문구', 1)[1].replace('\n- \n', '\n- 없음\n', 1)
        head = re.sub(r'^읽은 방식:.*$', lambda _: f'읽은 방식: {방식}', head, count=1, flags=re.M)
        self.rec.write_text(head + '## 면별 내용\n\n' + 줄들 + '\n\n## 쟁점에 닿는 문구' + tail, encoding='utf-8')

    def check(self):
        return run('check', self.case)

    def test_self_declared_filtered_reading_is_blocked(self):
        모두 = '\n'.join(f'- {n}면: 거래 내역 확인표 {tok(self.case, "을105-8", n)}' for n in range(1, 5))
        self.fill(모두)
        self.assertEqual(self.check()[0], 0)
        for 방식 in ('문자인식 줄을 걸러 금액이 큰 줄 중심으로 읽음', '그림 전 면(모음 그림)', '1면만 읽고 나머지는 모음 그림으로 봄'):
            self.fill(모두, 방식)
            code, out = self.check()
            self.assertEqual(code, 1, 방식)
            self.assertIn('다 읽지 않았다는 표현이 있다', out)
        self.fill(모두.replace('- 2면: 거래 내역', '- 2면: 거래 내역(가족 이름 줄 위주로 봄)'))
        self.assertIn('위주로 봄', self.check()[1])
        self.fill(모두.replace('- 2면: 거래 내역', '- 2면: 안전 수칙을 중심으로 진행된 교육'))    # 내용 설명은 막지 않는다
        self.assertEqual(self.check()[0], 0)

    def test_each_page_needs_its_own_code(self):
        코드 = [tok(self.case, '을105-8', n) for n in range(1, 5)]
        self.fill('\n'.join(f'- {n}면: 거래 확인표 {코드[0]}' for n in range(1, 5)))      # 첫 면의 확인표를 되풀이
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn('확인표가 없거나 맞지 않는 면 3/4: 2~4면', out)
        self.fill(f'- 1~4면: 거래 확인표 {코드[0]} {코드[1]} {코드[3]}')                    # 묶은 줄에 한 면이 빠짐
        self.assertIn('확인표가 없거나 맞지 않는 면 1/4: 3면', self.check()[1])
        self.fill(f'- 1~4면: 거래 확인표 {" ".join(코드).lower()}')                         # 대소문자는 가리지 않는다
        self.assertEqual(self.check()[0], 0)

    def test_old_text_without_codes_is_rewritten_by_make(self):
        글파일 = self.case / '증거관리' / '호증글자' / '을105-8.txt'
        글파일.write_text(re.sub(r'\n\[\d+면 끝 · [^\n]*\]', '', 글파일.read_text(encoding='utf-8')), encoding='utf-8')
        self.fill('\n'.join(f'- {n}면: 거래' for n in range(1, 5)))
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn('확인표가 없는 옛 판', out)
        run('make', self.case, '--no-ocr')
        self.assertIn('[1면 끝 · 확인표', 글파일.read_text(encoding='utf-8'))
        self.assertIn('- 1면: 거래', self.rec.read_text(encoding='utf-8'))          # 기록은 그대로 두고 면별 글만 새로 쓴다

    def test_scanned_table_pieces_are_joined_into_rows(self):
        조각 = [('2023-01-05', (10, 100, 80, 112)), ('입금', (100, 101, 130, 113)), ('1,000,000', (150, 99, 220, 111)), ('홍길동', (240, 100, 280, 112)),
              ('2023-01-06', (10, 130, 80, 142)), ('1,200,000', (150, 131, 220, 143)), ('출금', (100, 129, 130, 141)), ('합계 없음', (10, 170, 200, 182))]
        self.assertEqual(er.줄_복원(조각), ['| 2023-01-05 | 입금 | 1,000,000 | 홍길동 |', '| 2023-01-06 | 출금 | 1,200,000 |', '합계 없음'])
        self.assertEqual(sorted(x for 줄 in er.줄_복원(조각) for x in re.split(r'\s*\|\s*', 줄) if x),
                         sorted(t for t, _ in 조각))                                   # 글자는 하나도 빠지지 않는다

    def test_tall_screenshot_is_read_in_pieces_each_with_its_code(self):
        d = pymupdf.open()
        pg = d.new_page(width=300, height=1300)
        for y in range(60, 1300, 120):
            pg.insert_text((20, y), f'{y} 대화', fontsize=12, fontname='korea')
        pg.get_pixmap(dpi=72).save(str(self.ours / '을 제106호증 대화 갈무리.png'))
        run('make', self.case, '--no-ocr')
        rec = self.case / '증거관리' / '호증읽기' / '을106.md'
        t = rec.read_text(encoding='utf-8')
        h = er.해시(self.ours / '을 제106호증 대화 갈무리.png')
        코드 = [er.확인표(self.case, h, 1, '그림' if i == 1 else f'그림{i}') for i in range(1, 5)]
        head, rest = t.split('## 면별 내용', 1)
        tail = rest.split('## 쟁점에 닿는 문구', 1)[1].replace('\n- \n', '\n- 없음\n', 1)
        head = head.replace('읽은 방식: \n', '읽은 방식: 그림 전 면\n')
        rec.write_text(head + f'## 면별 내용\n\n- 1면: 대화 확인표 {코드[0]}\n\n## 쟁점에 닿는 문구' + tail, encoding='utf-8')
        code, out = run('check', self.case, '--호증', '을106')
        self.assertEqual(code, 1)                                     # 1300 높이는 폭의 1.4배로 네 조각이다
        self.assertIn('확인표가 없거나 맞지 않는 면 1/1', out)
        rec.write_text(rec.read_text(encoding='utf-8').replace(f'확인표 {코드[0]}', '확인표 ' + ' '.join(코드)), encoding='utf-8')
        self.assertEqual(run('check', self.case, '--호증', '을106')[0], 0)
        code, out = run('그림', self.case, '--호증', '을106', '--out', Path(self.tmp.name) / '그림')
        self.assertEqual(sorted(p.name for p in (Path(self.tmp.name) / '그림' / '을106').glob('*.png')),
                         ['01조각.png', '02조각.png', '03조각.png', '04조각.png'])


W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MC_NS = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
OD = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml'


class 윈도_이름(zipfile.ZipInfo):
    """윈도 탐색기처럼 이름을 cp949 바이트로 적고 UTF-8 표시를 하지 않는 압축 항목. 이름은 cp949 바이트를 cp437 로 푼 글로 준다."""

    def _encodeFilenameFlags(self):
        return self.filename.encode('cp437'), self.flag_bits & ~0x800


def 윈도_압축_항목(이름: str) -> zipfile.ZipInfo:
    return 윈도_이름(이름.encode('cp949').decode('cp437'))


def png_bytes(w, h, text):
    d = pymupdf.open()
    pg = d.new_page(width=w, height=h)
    for y in range(40, int(h), 100):
        pg.insert_text((20, y), f'{text} {y}', fontsize=14, fontname='korea')
    return pg.get_pixmap(dpi=72).tobytes('png')


def pdf_bytes(pages):
    d = pymupdf.open()
    for x in pages:
        d.new_page().insert_text((40, 72), x, fontsize=7, fontname='korea')
    return d.tobytes()


def docx_bytes(그림=()):
    """본문·변경 내용 추적·표·글상자(대체본 포함)·각주·메모·머리글이 든 워드. 그림: [(이름, 바이트)] → word/media."""
    w = f'xmlns:w="{W_NS}" xmlns:mc="{MC_NS}"'
    body = ('<w:p><w:r><w:t>근로계약서 제1조 근로시간은 09:00부터 18:00까지로 한다.</w:t></w:r></w:p>'
            '<w:p><w:del w:author="인사팀"><w:r><w:delText>수습기간 6개월</w:delText></w:r></w:del>'
            '<w:ins w:author="인사팀"><w:r><w:t>수습기간 3개월</w:t></w:r></w:ins></w:p>'
            '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>성명</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>홍길동</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
            '<w:p><w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><w:txbxContent><w:p><w:r><w:t>글상자 안 문구</w:t></w:r></w:p>'
            '</w:txbxContent></w:drawing></mc:Choice><mc:Fallback><w:pict><w:txbxContent><w:p><w:r><w:t>글상자 안 문구</w:t></w:r></w:p>'
            '</w:txbxContent></w:pict></mc:Fallback></mc:AlternateContent></w:r></w:p>')
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                               '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
                               '<Default Extension="emf" ContentType="image/x-emf"/>'
                               f'<Override PartName="/word/document.xml" ContentType="{CT}.document.main+xml"/>'
                               f'<Override PartName="/word/footnotes.xml" ContentType="{CT}.footnotes+xml"/>'
                               f'<Override PartName="/word/comments.xml" ContentType="{CT}.comments+xml"/>'
                               f'<Override PartName="/word/header1.xml" ContentType="{CT}.header+xml"/></Types>',
        '_rels/.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{OD}/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/_rels/document.xml.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{OD}/footnotes" Target="footnotes.xml"/>'
                                        f'<Relationship Id="rId2" Type="{OD}/comments" Target="comments.xml"/>'
                                        f'<Relationship Id="rId3" Type="{OD}/header" Target="header1.xml"/></Relationships>',
        'word/document.xml': f'<w:document {w}><w:body>{body}</w:body></w:document>',
        'word/footnotes.xml': f'<w:footnotes {w}><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:t>-</w:t></w:r></w:p></w:footnote>'
                              '<w:footnote w:id="1"><w:p><w:r><w:t>대법원 2019. 1. 1. 선고 판결</w:t></w:r></w:p></w:footnote></w:footnotes>',
        'word/comments.xml': f'<w:comments {w}><w:comment w:id="0" w:author="인사팀" w:date="2026-10-01T09:00:00Z"><w:p><w:r><w:t>확인 바람</w:t></w:r></w:p>'
                             '</w:comment></w:comments>',
        'word/header1.xml': f'<w:hdr {w}><w:p><w:r><w:t>대외비</w:t></w:r></w:p></w:hdr>',
    }
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for n, x in files.items():
            z.writestr(n, x)
        for n, x in 그림:
            z.writestr(f'word/media/{n}', x)
    return b.getvalue()


def xlsx_bytes():
    """날짜 칸, 숨긴 행·시트, 식만 있는 칸, 메모, 시트 위 그림과 도형 글이 든 통합 문서."""
    files = {
        'xl/workbook.xml': f'<workbook xmlns="{XL}" xmlns:r="{XR}"><sheets><sheet name="1월" sheetId="1" r:id="rId1"/>'
                           '<sheet name="숨김" sheetId="2" r:id="rId2" state="hidden"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                                      '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>',
        'xl/sharedStrings.xml': f'<sst xmlns="{XL}"><si><t>성명</t></si><si><t>홍길동</t></si><si><t>출근일</t></si></sst>',
        'xl/styles.xml': f'<styleSheet xmlns="{XL}"><cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>',
        'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{XL}" xmlns:r="{XR}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>2</v></c></row>'
                                    '<row r="2" hidden="1"><c r="A2" t="s"><v>1</v></c><c r="B2" s="1"><v>45297</v></c><c r="C2"><f>SUM(A1:A2)</f></c></row>'
                                    '</sheetData><drawing r:id="rId1"/></worksheet>',
        'xl/worksheets/_rels/sheet1.xml.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Target="../drawings/drawing1.xml"/>'
                                               '<Relationship Id="rId2" Target="../comments1.xml"/></Relationships>',
        'xl/drawings/drawing1.xml': '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
                                    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><xdr:twoCellAnchor><xdr:sp><xdr:txBody>'
                                    '<a:p><a:r><a:t>도형 메모: 연장근로 승인</a:t></a:r></a:p></xdr:txBody></xdr:sp></xdr:twoCellAnchor></xdr:wsDr>',
        'xl/drawings/_rels/drawing1.xml.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Target="../media/image1.png"/></Relationships>',
        'xl/comments1.xml': f'<comments xmlns="{XL}"><authors><author>인사팀</author></authors><commentList><comment ref="B2" authorId="0">'
                            '<text><t>지각 처리</t></text></comment></commentList></comments>',
        'xl/worksheets/sheet2.xml': f'<worksheet xmlns="{XL}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>숨긴 시트의 값</t></is></c></row>'
                                    '</sheetData></worksheet>',
    }
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for n, x in files.items():
            z.writestr(n, x)
        z.writestr('xl/media/image1.png', png_bytes(500, 300, '시트 그림'))
    return b.getvalue()


def eml_bytes():
    """본문(글·HTML), 본문에 넣은 이름 없는 그림, 같은 이름의 첨부 둘, PDF 첨부가 든 메일."""
    from email.message import EmailMessage
    m = EmailMessage()
    m['From'], m['To'], m['Date'], m['Subject'] = 'a@x.kr', 'b@y.kr', 'Mon, 02 Nov 2026 10:00:00 +0900', '징계 통보'
    m.set_content('징계위원회 출석을 통보합니다.\n11월 5일 10시')
    m.add_alternative('<html><body><p>징계위원회 출석을 통보합니다.</p><img src="cid:img1"></body></html>', subtype='html')
    m.get_payload()[1].add_related(png_bytes(300, 200, '본문 그림'), 'image', 'png', cid='<img1>')
    m.add_attachment(png_bytes(300, 200, '첫 사진'), maintype='image', subtype='png', filename='사진.png')
    m.add_attachment(png_bytes(300, 200, '둘째 사진'), maintype='image', subtype='png', filename='사진.png')
    m.add_attachment(pdf_bytes([글 + '출석 통지']), maintype='application', subtype='pdf', filename='출석통지서.pdf')
    return m.as_bytes()


def 채우기(case: Path, key: str, 표: dict, 방식='글자층·그림 전부'):
    """기록의 단위 줄마다(단위는 호증 파일에서) 그 단위의 확인표를 모두 적고 '읽은 방식'과 쟁점 문구를 채운다."""
    rec = case / '증거관리' / '호증읽기' / f'{key}.md'
    t = rec.read_text(encoding='utf-8')
    units = er.단위들(case / re.search(r'^파일: (.+)$', t, re.M).group(1))
    head, rest = t.split('## 면별 내용', 1)
    tail = rest.split('## 쟁점에 닿는 문구', 1)[1].replace('\n- \n', '\n- 없음\n', 1)
    줄 = [f'- {u}{"면" if isinstance(u, int) else ""}: 읽음 확인표 {" ".join(표.get(u, []))}' for u in units]
    head = re.sub(r'^읽은 방식:.*$', lambda _: f'읽은 방식: {방식}', head, count=1, flags=re.M)
    rec.write_text(head + '## 면별 내용\n\n' + '\n'.join(줄) + '\n\n## 쟁점에 닿는 문구' + tail, encoding='utf-8')


class OtherFormatsTest(unittest.TestCase):
    """압축·엑셀·워드·한글(hwpx)·메일 호증도 단위마다 끝까지 읽은 확인표가 있어야 지나간다.
    2026. 11. 3. 담당 노무사 "압축·엑셀·문서 호증도 확인표 넣어줘"."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name) / 'GGM_정직'
        self.ours = self.case / '라운드1' / '우리증거'
        self.ours.mkdir(parents=True)
        with zipfile.ZipFile(self.ours / '사 제3호증 자료 묶음.zip', 'w') as z:
            z.writestr('a.png', png_bytes(300, 1100, '대화'))
            z.writestr('b.pdf', pdf_bytes([글 + '1면', 글 + '2면']))
            z.writestr('c.docx', docx_bytes([('image1.png', png_bytes(400, 300, '현장 사진'))]))
            z.writestr(윈도_압축_항목('한글이름.txt'), '메모 내용입니다'.encode('cp949'))   # 윈도에서 만든 압축
        (self.ours / '사 제4호증 근무표.xlsx').write_bytes(xlsx_bytes())
        (self.ours / '사 제5호증 계약서.docx').write_bytes(docx_bytes([('image1.png', png_bytes(400, 300, '직인')),
                                                                     ('image2.png', png_bytes(16, 16, '.'))]))
        with zipfile.ZipFile(self.ours / '사 제7호증 보고서.hwpx', 'w') as z:
            z.writestr('Contents/section0.xml', '<hs:sec xmlns:hs="h" xmlns:hp="p"><hp:p><hp:run><hp:t>보고서 첫 문단</hp:t></hp:run></hp:p>'
                                                '<hp:p><hp:run><hp:t>둘째 문단</hp:t></hp:run></hp:p></hs:sec>')
        (self.ours / '사 제8호증 통보 메일.eml').write_bytes(eml_bytes())
        self.keys = ['사3', '사4', '사5', '사7', '사8']

    def tearDown(self):
        self.tmp.cleanup()

    def text(self, key):
        return (self.case / '증거관리' / '호증글자' / f'{key}.txt').read_text(encoding='utf-8')

    def rec(self, key):
        return self.case / '증거관리' / '호증읽기' / f'{key}.md'

    def 그림표(self, key):
        """그 호증의 그림 확인표(면별 글에 없고 `그림` 이 그린 띠에만 있다)."""
        p = self.case / re.search(r'^파일: (.+)$', self.rec(key).read_text(encoding='utf-8'), re.M).group(1)
        h = er.해시(p)
        return {er.확인표(self.case, h, er.키(it['단위'], it['경로'], f'그림{i}'), '그림')
                for it in er.목록_읽기(self.text(key)) if it['갈래'] == '그림' for i in range(1, it['수'] + 1)}

    def test_text_of_each_format_is_written_with_codes(self):
        code, out = run('make', self.case, '--no-ocr')
        self.assertEqual(code, 0, out)
        사3 = self.text('사3')
        for x in ('[파일] a.png ⟶ 그림 3 ⟶ a.png', '[파일] b.pdf ⟶ 면 글,글 ⟶ b.pdf', '[파일] c.docx ⟶ 글 1 ⟶ c.docx',
                  '[파일] c.docx ⟶ 그림 1 ⟶ c.docx›word/media/image1.png', '[파일] 한글이름.txt ⟶ 글 1 ⟶ 한글이름.txt'):
            self.assertIn('확인표 단위: ' + x, 사3)
        self.assertIn('메모 내용입니다', 사3)                                   # cp949 글
        self.assertIn('- [파일] 한글이름.txt: ', self.rec('사3').read_text(encoding='utf-8'))
        self.assertRegex(사3, r'\[\[파일\] b\.pdf · 2면 끝 · 확인표 [A-Z0-9]{4}\]')
        사4 = self.text('사4')
        for x in ('2024-01-06', '(숨긴 행)', '(숨긴 시트)', '숨긴 시트의 값', '=SUM(A1:A2)', '[메모 B2 인사팀] 지각 처리',
                  '[도형 글] 도형 메모: 연장근로 승인', '확인표 단위: [시트] 1월 ⟶ 그림 1 ⟶ xl/media/image1.png'):
            self.assertIn(x, 사4)
        사5 = self.text('사5')
        for x in ('[지움: 수습기간 6개월]', '수습기간 3개월', '| 성명 | 홍길동 |', '[각주 1] 대법원 2019. 1. 1. 선고 판결',
                  '[메모 인사팀 2026-10-01] 확인 바람', '[머리글] 대외비', '[작은 그림 1개', '확인표 단위: 전체 ⟶ 그림 1 ⟶ word/media/image1.png'):
            self.assertIn(x, 사5)
        self.assertEqual(사5.count('글상자 안 문구'), 1)                         # 대체본(mc:Fallback)을 두 번 적지 않는다
        self.assertIn('둘째 문단', self.text('사7'))
        사8 = self.text('사8')
        for x in ('Subject: 징계 통보', '11월 5일 10시', '확인표 단위: 전체 ⟶ 면 글 ⟶ 출석통지서.pdf', '그림 1 ⟶ 사진.png',
                  '그림 1 ⟶ 사진 (2).png', '그림 1 ⟶ 이름 없는 첨부1.png'):
            self.assertIn(x, 사8)
        code, out = run('check', self.case)
        self.assertEqual(code, 1)
        self.assertEqual(out.count('확인표가 없거나 맞지 않는 단위'), 5)

    def test_codes_from_text_and_pictures_let_it_pass_and_a_missing_one_blocks(self):
        run('make', self.case, '--no-ocr')
        for k in self.keys:
            표 = 기대표(self.case, k)
            그림 = self.그림표(k)
            for u, toks in 표.items():
                for x in toks:                  # 글 덩이·면의 확인표는 면별 글에, 그림의 확인표는 그림에만 있다
                    (self.assertNotIn if x in 그림 else self.assertIn)(f'확인표 {x}]', self.text(k), (k, u))
            채우기(self.case, k, 표)
        code, out = run('check', self.case)
        self.assertEqual(code, 0, out)
        표 = 기대표(self.case, '사3')
        채우기(self.case, '사3', {**표, '[파일] a.png': 표['[파일] a.png'][:2]})       # 긴 갈무리의 마지막 조각을 안 봄
        code, out = run('check', self.case, '--호증', '사3')
        self.assertEqual(code, 1)
        self.assertIn('확인표가 없거나 맞지 않는 단위 1/4: [파일] a.png', out)
        그림폴더 = Path(self.tmp.name) / '그림'
        code, out = run('그림', self.case, '--호증', '사3', '사8', '--out', 그림폴더)
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(p.name for p in (그림폴더 / '사3').glob('*.png')),
                         ['001_01조각.png', '001_02조각.png', '001_03조각.png', '003_01조각.png'])     # b.pdf 는 그림으로 볼 면이 없다
        self.assertEqual(len(list((그림폴더 / '사8').glob('*.png'))), 3)
        pix = pymupdf.Pixmap(str(그림폴더 / '사3' / '003_01조각.png'))
        self.assertGreater(pix.height, 300 + 20)                                   # 그림 아래 확인표 띠

    def test_new_extraction_version_rewrites_text_and_old_codes_stop_matching(self):
        run('make', self.case, '--no-ocr', '--호증', '사7')
        채우기(self.case, '사7', 기대표(self.case, '사7'))
        self.assertEqual(run('check', self.case, '--호증', '사7')[0], 0)
        with mock.patch.object(er, '글판', er.글판 + 1):
            code, out = run('check', self.case, '--호증', '사7')
            self.assertEqual(code, 1)
            self.assertIn('옛 판', out)
            run('make', self.case, '--no-ocr', '--호증', '사7')
            self.assertIn(f'글판: {er.글판}', self.text('사7'))
            code, out = run('check', self.case, '--호증', '사7')
            self.assertEqual(code, 1)                                               # 새 판의 글을 다시 읽어야 한다
            self.assertIn('확인표가 없거나 맞지 않는 단위 1/1: 전체', out)

    def test_unreadable_documents_block_until_a_pdf_of_the_same_name_stands_in(self):
        case = Path(self.tmp.name) / 'HPS_자문'
        att = case / '첨부'
        att.mkdir(parents=True)
        (att / '취업규칙.hwp').write_bytes(b'not a real hwp file \x00\x01')
        (att / '계약서.docx').write_bytes(docx_bytes([('image1.emf', b'not an emf picture')]))
        run('make', case, '--자료', att, '--no-ocr')
        code, out = run('check', case, '--자료', att)
        self.assertEqual(code, 1)
        self.assertIn('글을 뽑지 못한 곳: 전체(', out)
        self.assertIn('word/media/image1.emf(문서 안의 .emf 그림을 그리지 못했다', out)
        make_pdf(att / '취업규칙.pdf', [글 + '제1조'])
        make_pdf(att / '계약서.pdf', [글 + '제1조'])
        run('make', case, '--자료', att, '--no-ocr')
        code, out = run('check', case, '--자료', att)
        self.assertNotIn('글을 뽑지 못한 곳', out)                                  # 같은 이름의 PDF 를 면마다 읽는다
        self.assertIn('취업규칙.pdf', out)

    def test_ocr_cache_of_a_replaced_file_is_not_reused(self):
        d = pymupdf.open()
        d.new_page()                                                               # 글자층이 없는 스캔 면
        d.save(self.ours / '사 제6호증 스캔.pdf')
        캐시 = self.case / '증거관리' / '호증글자' / 'ocr' / '사6'
        캐시.mkdir(parents=True)
        (캐시 / 'pages.json').write_text('{"1": {"units": [["앞 파일의 문자인식 글", [0, 0, 10, 10]]], "png": "p001.png"}}', encoding='utf-8')
        (캐시 / '파일해시.txt').write_text('deadbeef0000', encoding='utf-8')
        run('make', self.case, '--no-ocr', '--호증', '사6')
        self.assertNotIn('앞 파일의 문자인식 글', self.text('사6'))
        self.assertEqual((캐시 / '파일해시.txt').read_text(encoding='utf-8') if 캐시.is_dir() else '', er.해시(self.ours / '사 제6호증 스캔.pdf') if 캐시.is_dir() else '')

    @unittest.skipUnless(er._et.soffice(), 'LibreOffice 가 없다')
    def test_old_word_file_and_emf_picture_go_through_libreoffice(self):
        doc = er._et._libre(docx_bytes(), '.docx', 'doc')
        self.assertTrue(doc)
        (self.ours / '사 제9호증 옛 계약서.doc').write_bytes(doc)
        svg = (b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect x="10" y="10" width="380" height="180" fill="#def"/>'
               b'<text x="40" y="110" font-size="30">EMF 3,000,000</text></svg>')
        emf = er._et._libre(svg, '.svg', 'emf')
        self.assertEqual(emf[40:44], b' EMF')
        (self.ours / '사 제10호증 그림 든 문서.docx').write_bytes(docx_bytes([('image3.emf', emf)]))
        run('make', self.case, '--no-ocr', '--호증', '사9', '사10')
        self.assertIn('확인표 단위: 전체 ⟶ 면 ', self.text('사9'))                  # PDF 로 바꾸어 면마다
        self.assertIn('수습기간3개월', re.sub(r'\s', '', self.text('사9')))           # PDF 글자층은 숫자 뒤를 띄우기도 한다
        self.assertIn('확인표 단위: 전체 ⟶ 그림 1 ⟶ word/media/image3.emf', self.text('사10'))
        for k in ('사9', '사10'):
            채우기(self.case, k, 기대표(self.case, k), 방식='글자층 전 면, 그림 전 면')
        self.assertEqual(run('check', self.case, '--호증', '사9', '사10')[0], 0)
        code, out = run('그림', self.case, '--호증', '사10', '--out', Path(self.tmp.name) / '그림')
        self.assertEqual(code, 0, out)
        self.assertEqual([p.name for p in (Path(self.tmp.name) / '그림' / '사10').glob('*.png')], ['001_01조각.png'])


class TextPiecesTest(unittest.TestCase):
    def test_chunks_keep_every_line_and_stay_small(self):
        줄들 = [f'{i}번째 줄 ' + '가' * (i % 50) for i in range(2000)] + ['나' * 7000]
        덩이 = er._et.덩이로('\n'.join(줄들))
        self.assertEqual('\n'.join(덩이).replace('\n', ''), ''.join(줄들))     # 글자는 하나도 빠지지 않는다
        self.assertTrue(all(len(x) <= er._et.덩이_크기 for x in 덩이))
        self.assertEqual(er._et.덩이로('  \n '), [])

    def test_zip_names_made_on_windows_are_read_in_cp949(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            z.writestr(윈도_압축_항목('급여명세서.pdf'), b'x')
            z.writestr('utf8이름.txt', b'y')
        with zipfile.ZipFile(b) as z:
            self.assertEqual([n for n, _ in er._et.zip_목록(z)], ['utf8이름.txt', '급여명세서.pdf'])

    def test_excel_numbers_are_shown_as_excel_shows_them(self):
        """근태 자료의 출퇴근 시각, '[h]:mm' 합계 시간, 백분율을 숫자로 두면 잘못 읽는다."""
        값 = lambda fid, code, v: er._et._엑셀_값(v, er._et._서식_갈래(fid, code), False)
        self.assertEqual(값(14, '', '45297'), '2024-01-06')
        self.assertEqual(값(20, '', '0.3708333333'), '08:54')                     # 초 단위로 반올림(엑셀과 같다)
        self.assertEqual(값(164, 'hh:mm:ss', '0.5000115740740741'), '12:00:01')
        self.assertEqual(값(164, '[h]:mm', '1.5'), '36:00')                       # 하루를 넘는 합계 시간
        self.assertEqual(값(10, '', '0.155'), '15.5%')
        self.assertEqual(값(164, 'yyyy"년" m"월" d"일"', '45297.5'), '2024-01-06 12:00')
        self.assertEqual(값(0, '', '2999999.9999999995'), '3000000')               # 엑셀처럼 유효 숫자 15자리
        self.assertEqual(값(164, '#,##0', '3000000'), '3000000')

    def test_word_symbols_text_encodings_and_junk_in_zips(self):
        p = ET.fromstring(f'<w:p xmlns:w="{W_NS}"><w:r><w:sym w:font="Wingdings" w:char="F0FE"/><w:t>동의</w:t>'
                          '<w:sym w:font="Wingdings" w:char="F0A8"/><w:t>거부</w:t><w:sym w:char="F099"/></w:r></w:p>')
        self.assertEqual(er._et._w_글(p), '☑동의☐거부[기호]')
        self.assertEqual(er._et.텍스트_글('출근 기록'.encode('utf-16')), '출근 기록')
        self.assertEqual(er._et.텍스트_글('출근 기록'.encode('cp949')), '출근 기록')
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            for n in ('사진/.DS_Store', 'Thumbs.db', '__MACOSX/._a.png', '사진/a.png'):
                z.writestr(n, b'x')
        with zipfile.ZipFile(b) as z:
            self.assertEqual([n for n, _ in er._et.zip_목록(z)], ['사진/a.png'])

    def test_mail_with_only_a_notice_in_plain_text_also_gives_the_html_body(self):
        from email.message import EmailMessage
        m = EmailMessage()
        m.set_content('이 메일은 HTML 형식입니다.')
        m.add_alternative('<html><body><p>징계위원회는 11월 5일 10시에 열립니다.</p><p>출석하지 않으면 진술을 포기한 것으로 봅니다.</p>'
                          '</body></html>', subtype='html')
        글 = er._et.eml_글(m.as_bytes())['글']
        self.assertIn('출석하지 않으면 진술을 포기한 것으로 봅니다.', 글)
        self.assertNotIn('<p>', 글)

    def test_same_attachment_names_are_kept_apart(self):
        self.assertEqual(er._et.고유('사진.png', ['사진.png', '사진 (2).png']), '사진 (3).png')
        self.assertEqual(er._et.고유('a.pdf', []), 'a.pdf')


if __name__ == '__main__':
    unittest.main()
