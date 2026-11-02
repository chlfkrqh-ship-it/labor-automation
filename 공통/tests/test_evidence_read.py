"""전 면 읽기 기록(4_서면작성/scripts/evidence_read.py)을 확인한다.

호증마다 단위(PDF 면, 그림, 압축파일 안 파일, 엑셀 시트)별 빈 줄이 있는 틀을 만드는지, 모든 단위를 채우지 않으면 check 가
막는지, '같음'·'반복'만 적은 줄을 빈 줄로 세는지, 기록한 뒤 파일이 바뀌면 막는지, 번호를 다시 매기면 기록을 옮기는지 본다.
세션 기록으로 읽은 줄을 재는 실측과 스캔 표의 줄 복원도 본다. 문자인식(Windows)은 돌리지 않는다(--no-ocr).
"""
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import zipfile
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


def run(*args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = er.main([str(a) for a in args])
    return code, out.getvalue()


class EvidenceReadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        실측 = mock.patch.object(er, '실측_문제', return_value=[])      # 실측은 MeasuredReadingTest 가 본다
        실측.start()
        self.addCleanup(실측.stop)
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
        with zipfile.ZipFile(self.ours / '사 제4호증 근무표.xlsx', 'w') as z:
            z.writestr('xl/workbook.xml', '<workbook><sheets><sheet name="1월" sheetId="1"/><sheet name="2월" sheetId="2"/></sheets></workbook>')
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
        self.fill('사3', '- [파일] a.jpg: 출입문 사진\n- [파일] b.jpg: 작업대 사진', 문구='없음')
        self.fill('사4', '- [시트] 1월: 1월 근무표\n- [시트] 2월: 2월 근무표', 문구='없음')
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
        실측 = mock.patch.object(er, '실측_문제', return_value=[])
        실측.start()
        self.addCleanup(실측.stop)
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
        실측 = mock.patch.object(er, '실측_문제', return_value=[])
        실측.start()
        self.addCleanup(실측.stop)
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


def 세션(폴더: Path, 이름: str, 호출들):
    """세션 기록 한 개를 쓴다. 호출들: (도구, 입력, 결과). 앱이 남기는 꼴과 같게 줄마다 메시지 하나이다."""
    폴더.mkdir(parents=True, exist_ok=True)
    줄 = []
    for i, (도구, 입력, 결과) in enumerate(호출들):
        k = f'toolu_{이름}_{i}'
        줄.append({'type': 'assistant', 'message': {'id': f'm{i}', 'content': [{'type': 'tool_use', 'id': k, 'name': 도구, 'input': 입력}]}})
        줄.append({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': k, 'content': 결과}]}})
    (폴더 / f'{이름}.jsonl').write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in 줄) + '\n', encoding='utf-8')


def 줄번호(글_):
    """읽기 도구의 결과 꼴."""
    return '\n'.join(f'{i}\t{l}' for i, l in enumerate(글_.splitlines(), 1))


그림결과 = [{'type': 'image', 'source': {'type': 'base64', 'data': 'AAAA'}}]


class MeasuredReadingTest(unittest.TestCase):
    """확인표는 거른 줄과 함께 찍으면 옮겨 적을 수 있으므로 세션 기록으로 잰다(2026. 11. 3. 담당 노무사 "뭔가 여전히 증거는 대충 읽는 느낌이 있네")."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.case = self.root / '4_서면작성' / '사건' / 'GGM_정직'
        self.ours = self.case / '라운드1' / '우리증거'
        self.ours.mkdir(parents=True)
        self.기록 = self.root / '세션기록'
        self.기록.mkdir()
        self.env = mock.patch.dict(os.environ, {'EVIDENCE_READ_ROOT': str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def 글파일(self, key):
        return self.case / '증거관리' / '호증글자' / f'{key}.txt'

    def rec(self, key):
        return self.case / '증거관리' / '호증읽기' / f'{key}.md'

    def 채움(self, key, 면수, 방식='글자층 전 면'):
        """칸과 확인표를 모두 채운다. check 가 실측만 남기게 한다."""
        t = self.rec(key).read_text(encoding='utf-8').replace('읽은 방식: \n', f'읽은 방식: {방식}\n')
        for n in range(1, 면수 + 1):
            t = t.replace(f'- {n}면: \n', f'- {n}면: {n}면 내용 확인표 {tok(self.case, key, n)}\n')
        self.rec(key).write_text(t.replace('면)\n\n- \n', '면)\n\n- 없음\n', 1), encoding='utf-8')

    def 실측(self, *더):
        return run('실측', self.case, '--기록폴더', self.기록, *더)

    def 읽음(self, key, 글_=None):
        return ('Read', {'file_path': str(self.글파일(key))}, 줄번호(글_ if 글_ is not None else self.글파일(key).read_text(encoding='utf-8')))

    def 문자(self, n=3):
        make_pdf(self.ours / '사 제6호증 문자.pdf', [글 + f'{i}면 고유 문구입니다' for i in range(1, n + 1)])
        run('make', self.case, '--no-ocr')
        self.채움('사6', n)

    def test_filled_record_with_codes_but_no_measurement_is_blocked(self):
        self.문자()
        code, out = run('check', self.case)
        self.assertEqual(code, 1)
        self.assertIn('실제로 읽은 기록(실측)이 없다', out)
        self.assertNotIn('확인표가 없거나', out)

    def test_reading_the_whole_text_passes_and_leaves_a_line(self):
        self.문자()
        세션(self.기록, '세션1', [self.읽음('사6')])
        code, out = self.실측()
        self.assertEqual(code, 0, out)
        t = self.rec('사6').read_text(encoding='utf-8')
        self.assertRegex(t, r'(?m)^실측: \d{4}-\d\d-\d\d · 줄 (\d+)/\1 · 그림 없음 · 글 [0-9a-f]{12} · 세션 세션1$')
        self.assertEqual(run('check', self.case)[0], 0)

    def test_view_only_writes_nothing(self):
        self.문자()
        세션(self.기록, '세션1', [self.읽음('사6')])
        code, out = self.실측('--보기')
        self.assertEqual(code, 0, out)
        self.assertIn('보기만', out)
        self.assertNotIn('실측:', self.rec('사6').read_text(encoding='utf-8'))

    def test_filtered_lines_with_codes_do_not_pass(self):
        """한전 을 제105호증의10 처럼 거른 줄만 찍되 확인표 줄을 함께 찍으면 확인표는 맞아도 실측이 막는다."""
        self.문자()
        전체 = self.글파일('사6').read_text(encoding='utf-8')
        고른 = '\n'.join(l for l in 전체.splitlines() if '고유 문구' in l or '확인표' in l)
        세션(self.기록, '세션1', [('Bash', {'command': f'python 거르기.py "{self.글파일("사6")}"'}, 고른)])
        code, out = self.실측()
        self.assertEqual(code, 1)
        self.assertIn('덜 읽은 면 1~3', out)
        self.assertNotIn('실측:', self.rec('사6').read_text(encoding='utf-8'))
        self.assertEqual(run('check', self.case)[0], 1)

    def test_first_page_only_does_not_pass(self):
        self.문자()
        첫면 = self.글파일('사6').read_text(encoding='utf-8').split('=== 2면')[0]   # 첫 면만 읽은 것(GGM 사 제6호증)
        세션(self.기록, '세션1', [self.읽음('사6', 첫면)])
        code, out = self.실측()
        self.assertEqual(code, 1)
        self.assertIn('덜 읽은 면 2~3', out)

    def test_lines_are_counted_across_sessions_but_not_from_subagents(self):
        self.문자()
        앞, 뒤 = self.글파일('사6').read_text(encoding='utf-8').split('=== 2면')
        세션(self.기록, '세션1', [self.읽음('사6', 앞)])
        세션(self.기록 / '세션1' / 'subagents', 'agent-1', [self.읽음('사6', '=== 2면' + 뒤)])
        self.assertEqual(self.실측()[0], 1)                                        # 하위 작업이 읽은 것은 세지 않는다
        세션(self.기록, '세션2', [self.읽음('사6', '=== 2면' + 뒤)])
        code, out = self.실측()
        self.assertEqual(code, 0, out)
        self.assertIn('세션 세션1·세션2', self.rec('사6').read_text(encoding='utf-8'))

    def test_repeated_lines_must_be_read_at_the_head_too(self):
        make_pdf(self.ours / '사 제7호증 문자.pdf', [글 + f'{n}일 실천사항 점검표를 확인하고 이상이 있으면 즉시 보고합니다' for n in range(1, 7)])
        run('make', self.case, '--no-ocr')
        전체 = self.글파일('사7').read_text(encoding='utf-8')
        self.assertIn('- R1: ', 전체)
        세션(self.기록, '세션1', [self.읽음('사7', '=== 1면' + 전체.split('=== 1면', 1)[1])])      # 면만 읽고 머리의 되풀이 줄은 안 읽음
        self.assertEqual(self.실측()[0], 1)
        세션(self.기록, '세션1', [self.읽음('사7')])
        self.assertEqual(self.실측()[0], 0)

    def test_changed_text_needs_another_measurement(self):
        self.문자()
        세션(self.기록, '세션1', [self.읽음('사6')])
        self.실측()
        self.assertEqual(run('check', self.case)[0], 0)
        f = self.글파일('사6')
        f.write_text(f.read_text(encoding='utf-8') + '\n=== 4면 (글자층) ===\n새로 들어온 줄입니다\n', encoding='utf-8')
        code, out = run('check', self.case)
        self.assertEqual(code, 1)
        self.assertIn('면별 글이 바뀌었다', out)
        self.assertEqual(self.실측()[0], 1)                                         # 새 줄을 읽기 전에는 통과하지 못한다
        세션(self.기록, '세션2', [self.읽음('사6')])
        self.assertEqual(self.실측()[0], 0)
        self.assertEqual(run('check', self.case)[0], 0)

    def test_flagged_page_needs_its_own_image_not_a_contact_sheet(self):
        make_pdf(self.ours / '사 제4호증 급여.pdf', [글 + '급여 안내', '서명'])
        run('make', self.case, '--no-ocr')
        self.assertIn('그림으로 볼 면: 2면(글자 거의 없음)', self.글파일('사4').read_text(encoding='utf-8'))
        self.채움('사4', 2, '글자층 1면, 그림 2면')
        세션(self.기록, '세션1', [self.읽음('사4'), ('Read', {'file_path': str(self.case / '증거관리' / '모음그림.png')}, 그림결과)])
        code, out = self.실측()
        self.assertEqual(code, 1)
        self.assertIn('한 장씩 열지 않은 그림 2면', out)
        폴더 = self.root / '그림'
        self.assertEqual(run('그림', self.case, '--호증', '사4', '--out', 폴더)[0], 0)
        낱장 = 폴더 / '사4' / '002면.png'
        self.assertTrue(낱장.is_file())
        세션(self.기록, '세션1', [self.읽음('사4'), ('Read', {'file_path': str(낱장)}, 그림결과)])
        code, out = self.실측()
        self.assertEqual(code, 0, out)
        self.assertIn('그림 2면', self.rec('사4').read_text(encoding='utf-8'))
        self.assertEqual(run('check', self.case)[0], 0)

    def test_pdf_pages_read_directly_count_as_images(self):
        make_pdf(self.ours / '사 제4호증 급여.pdf', [글 + '급여 안내', '서명', 글 + '끝'])
        run('make', self.case, '--no-ocr')
        세션(self.기록, '세션1', [self.읽음('사4'), ('Read', {'file_path': str(self.ours / '사 제4호증 급여.pdf'), 'pages': '2-2'}, 그림결과)])
        self.assertEqual(self.실측('--호증', '사4')[0], 0)

    def test_image_exhibit_all_pieces_and_files_that_cannot_be_measured(self):
        d = pymupdf.open()
        pg = d.new_page(width=300, height=900)
        pg.insert_text((20, 60), '대화 갈무리', fontsize=12, fontname='korea')
        pg.get_pixmap(dpi=72).save(str(self.ours / '사 제2호증 대화.png'))
        (self.ours / '사 제5호증 메모.docx').write_bytes(b'PK')
        (self.ours / '사 제8호증 깨진 사진.jpg').write_bytes(b'\xff\xd8\xff')
        run('make', self.case, '--no-ocr')
        self.assertNotIn('실측', run('check', self.case, '--호증', '사5')[1])       # 줄이 없는 종류는 재지 않는다
        self.assertNotIn('실측', run('check', self.case, '--호증', '사8')[1])       # 열리지 않는 그림도 재지 않는다
        self.assertIn('실측', run('check', self.case, '--호증', '사2')[1])
        폴더 = self.root / '그림'
        run('그림', self.case, '--호증', '사2', '--out', 폴더)
        조각들 = sorted((폴더 / '사2').glob('*조각.png'))
        self.assertEqual(len(조각들), 3)                                            # 900 높이는 폭의 1.4배로 세 조각이다
        세션(self.기록, '세션1', [('Read', {'file_path': str(조각들[0])}, 그림결과)])
        code, out = self.실측('--호증', '사2')
        self.assertEqual(code, 1)
        self.assertIn('한 장씩 열지 않은 그림 2조각', out)
        세션(self.기록, '세션1', [('Read', {'file_path': str(x)}, 그림결과) for x in 조각들])
        code, out = self.실측('--호증', '사2')
        self.assertEqual(code, 0, out)
        self.assertIn('그림 3조각', self.rec('사2').read_text(encoding='utf-8'))


class RowRestoreTest(unittest.TestCase):
    """스캔 표의 칸 조각을 줄로 되돌린다(2026. 11. 3. 한전 을 제105호증의10: 면마다 칸 조각 700여 개가 한 줄씩 나왔다)."""

    칸 = ['2020-07-16', '14:03:21', '30,000', '1,250,000', '입금', '홍길동', '타행이체', '농협']

    def 조각(self, 기울기=0.0, 줄수=12, 줄간=30):
        out = []
        for r in range(줄수):
            for c, t in enumerate(self.칸):
                x = 50 + c * 150
                y = 100 + r * 줄간 + 기울기 * x
                out.append((f'{t}{r}', (x, y, x + 60, y + 12)))
        return out

    def 줄(self, r):
        return '| ' + ' | '.join(f'{t}{r}' for t in self.칸) + ' |'

    def test_fragments_become_rows_without_losing_any(self):
        rows = er.줄_복원(self.조각())
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[3], self.줄(3))
        self.assertEqual(sorted(x for r in rows for x in re.split(r'\s*\|\s*', r) if x), sorted(t for t, _ in self.조각()))

    def test_tilted_scan(self):
        rows = er.줄_복원(self.조각(기울기=0.03, 줄간=20))                         # 끝에서 끝까지 한 줄 넘게 기운 스캔
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[5], self.줄(5))

    def test_plain_text_is_not_a_table(self):
        글줄 = [(f'{i}번째 문장은 한 줄로 온전히 읽혔습니다', (50, 100 + i * 30, 900, 112 + i * 30)) for i in range(30)]
        self.assertFalse(er.표_모양(er.줄_복원(글줄)))
        self.assertFalse(er.표_모양(er.줄_복원(self.조각(줄수=2))))                 # 조각이 적으면 표로 보지 않는다
        self.assertTrue(er.표_모양(er.줄_복원(self.조각())))

    def test_make_writes_rows_for_scanned_pages_and_keeps_rotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / 'GGM_정직'
            ours = case / '라운드1' / '우리증거'
            ours.mkdir(parents=True)
            d = pymupdf.open()
            d.new_page(width=400, height=800)
            d.save(ours / '사 제9호증 계좌내역.pdf')
            캐시 = case / '증거관리' / '호증글자' / 'ocr' / '사9'
            캐시.mkdir(parents=True)
            (캐시 / 'pages.json').write_text(json.dumps({'1': {'png': 'p001.png', 'src': '문자인식(270도 돌림)', 'units': self.조각(기울기=0.01)}},
                                                        ensure_ascii=False), encoding='utf-8')
            with mock.patch.dict(os.environ, {'EVIDENCE_READ_ROOT': tmp}):
                run('make', case, '--no-ocr')
                글파일 = case / '증거관리' / '호증글자' / '사9.txt'
                t = 글파일.read_text(encoding='utf-8')
                self.assertIn('문자인식(270도 돌림)', t)                            # 칸마다 따로 읽혀 숫자 표로 잡히지 않아도 줄로 돌린다
                self.assertIn(self.줄(3), t)
                self.assertEqual(er.글_읽기(t)[2], {1: 270})
                # 누운 스캔은 돌린 대로 세워 그린다
                run('그림', case, '--호증', '사9', '--면', 1, '--out', Path(tmp) / '그림')
                pix = pymupdf.Pixmap(str(Path(tmp) / '그림' / '사9' / '001면.png'))
                self.assertGreater(pix.width, pix.height)
                # 면별 글만 다시 낸다
                글파일.write_text('옛 글', encoding='utf-8')
                run('make', case, '--no-ocr', '--글다시', '사9')
                self.assertIn(self.줄(3), 글파일.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
