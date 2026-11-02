"""전 면 읽기 기록(4_서면작성/scripts/evidence_read.py)을 확인한다.

호증마다 단위(PDF 면, 그림, 압축파일 안 파일, 엑셀 시트)별 빈 줄이 있는 틀을 만드는지, 모든 단위를 채우지 않으면 check 가
막는지, '같음'·'반복'만 적은 줄을 빈 줄로 세는지, 기록한 뒤 파일이 바뀌면 막는지, 번호를 다시 매기면 기록을 옮기는지 본다.
문자인식(Windows)은 돌리지 않는다(--no-ocr).
"""
import importlib.util
import io
import os
from pathlib import Path
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
        self.fill('사6', '- 1면: 안전 안내 문자(10. 1.)\n- 2면: 안전 안내 문자(10. 2.)\n- 3면: 실천사항 "작업 중 시험 기기 사용 금지"')
        code, out = run('check', self.case, '--호증', '사6')
        self.assertEqual(code, 0, out)

    def test_ranges_and_other_units_count(self):
        run('make', self.case, '--no-ocr')
        self.fill('사6', '- 1~3면: 일자별 안전 문자(10. 1.~10. 3.), 3면에 시험 기기 사용 금지')
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
        self.fill('사6', '- 1면: 가\n- 2면: 나\n- 3면: 다')
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
        self.assertIn('- 3면: 다', t.split('## 앞선 기록')[1])
        code, out = run('check', self.case, '--호증', '사6')
        self.assertEqual(code, 1)                           # 앞선 기록은 세지 않는다. 다시 읽어 채워야 한다
        self.assertIn('1~4면', out)

    def test_renumbered_exhibit_carries_its_record(self):
        run('make', self.case, '--no-ocr', '--호증', '사6')
        self.fill('사6', '- 1면: 가\n- 2면: 나\n- 3면: 다')
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
        body = '- 1면: 급여 지급 안내와 2명의 1·2월 지급액 표\n- 2면: 담당자 서명'
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

    def test_same_file_read_in_another_case_is_offered_but_must_be_read_again(self):
        쪽 = [글 + f'{n}면 안내' for n in range(1, 4)]
        make_pdf(self.ours / '사 제6호증 문자.pdf', 쪽)
        run('make', self.case, '--no-ocr')
        rec = self.rec(self.case, '사6')
        t = rec.read_text(encoding='utf-8')
        t = t.replace('읽은 방식: \n', '읽은 방식: 글자층 전 면\n').replace('- 1면: ', '- 1면: 안전 안내(1)').replace('- 2면: ', '- 2면: 안전 안내(2)')
        t = t.replace('- 3면: ', '- 3면: 안전 안내(3)').replace('면)\n\n- \n', '면)\n\n- 3면 "안내"\n')
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
        self.assertIn('## 옮겨 온 기록의 쟁점 문구', t)
        code, out = run('check', other)
        self.assertEqual(code, 1)                                   # 다른 사건의 기록으로 갈음하지 않는다
        self.assertIn('다른 사건 기록에서 옮긴 줄 3개', out)
        t = t.replace('(옮김) ', '').replace('읽은 방식: \n', '읽은 방식: 글자층 전 면\n').replace('면)\n\n- \n', '면)\n\n- 없음\n', 1)
        self.rec(other, '갑2').write_text(t, encoding='utf-8')
        self.assertEqual(run('check', other)[0], 0)


if __name__ == '__main__':
    unittest.main()
