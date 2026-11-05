"""4_서면작성/scripts/hearing_pack.py(심문회의 현장용 묶음)의 인용 찾기를 확인한다.

'참고자료 N' 인용(줄바꿈이 낀 '참 고자료 1', '【참고자료 1】', 뒤에 말이 붙은 '참고자료 1 판정서 65면')을 '참고자료 N' 조각에 잇는지,
우리·상대가 같은 번호의 참고자료를 내면 그 문서 쪽의 것에 잇는지 본다. 2026. 11. 4. GGM 묶음에서 답변서(2)·PT 가 든 참고자료 1·3 의
인용 단추와 띠의 돌아가기 단추가 하나도 생기지 않았다('인용 쪽을 찾은 호증 63/67').
작은 PDF 를 임시 폴더에 만들어 묶으므로 사건 자료에는 아무것도 쓰지 않는다. 맑은 고딕(malgun.ttf)이 있는 Windows 에서만 돈다.
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import pymupdf

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / '4_서면작성' / 'scripts'))
import hearing_pack as hp  # noqa: E402

글꼴 = Path('C:/Windows/Fonts/malgun.ttf')


def 참(*ns):
    return {('참고자료', n, None) for n in ns}


def pdf(경로, 면들):
    d = pymupdf.open()
    for 글 in 면들:
        pg = d.new_page(width=595, height=842)
        pg.insert_font(fontname='kr', fontfile=str(글꼴))
        pg.insert_text((72, 100), 글, fontname='kr', fontsize=11)
    경로.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(경로))
    d.close()


class 인용목록(unittest.TestCase):
    def test_참고자료_꼴(self):
        풀기 = hp.인용_목록
        self.assertEqual(풀기('정반대입니다(참\n고자료 1 판정서 65\n면). 서울행정법원도'), 참(1))
        self.assertEqual(풀기('(참고자료 1 52면)'), 참(1))
        self.assertEqual(풀기('참고자료 3 판결 13면 반면'), 참(3))
        self.assertEqual(풀기('【참고자료 1】 전남 【참고자료 2】 중앙'), 참(1, 2))
        self.assertEqual(풀기('참고자료 1, 2'), 참(1, 2))
        self.assertEqual(풀기('참고자료 1 내지 3'), 참(1, 2, 3))
        self.assertEqual(풀기('참고자료 1·3'), 참(1, 3))
        self.assertEqual(풀기('(참고자료 1, 3면)'), 참(1))          # 3 은 쪽이다
        self.assertEqual(풀기('참고자료에 판정서와 판결이 있으며'), set())
        self.assertEqual(풀기('사 제3호증, 참고자료 2'), {('사', 3, None)} | 참(2))

    def test_호증_꼴(self):
        풀기 = hp.인용_목록
        self.assertEqual(풀기('사 제6호증의1 내지 3'), {('사', 6, 1), ('사', 6, 2), ('사', 6, 3)})
        self.assertEqual(풀기('사 제10호증 내지 제12호증'), {('사', 10, None), ('사', 11, None), ('사', 12, None)})
        self.assertEqual(풀기('사 제2호증의1, 2'), {('사', 2, 1), ('사', 2, 2)})


@unittest.skipUnless(글꼴.exists(), '맑은 고딕이 없음')
class 묶기(unittest.TestCase):
    def test_참고자료_인용_단추(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            사건 = Path(tmp) / '사건' / '시험'
            pdf(사건 / '질의.pdf', ['판정서에 있고(참고자료 1 52면), 판결도 있다(참고자료 2 판결 13면).'])
            pdf(사건 / '답변서.pdf', ['답 변 서', '신청인이 낸 판정서와 다릅니다(참\n고자료 1 판정서 65면). 사 제1호증',
                                     '입 증 방 법\n1. 사 제1호증\n참고자료 2'])
            pdf(사건 / '이유서.pdf', ['【참고자료 1】 판정서'])
            pdf(사건 / '우리' / '사 제1호증_계약서.pdf', ['계약서'])
            pdf(사건 / '우리' / '참고자료1_우리 판결.pdf', ['우리 판결'])
            pdf(사건 / '상대' / '참고자료1_상대 판정서.pdf', ['상대 판정서'])
            pdf(사건 / '상대' / '참고자료2_상대 판결.pdf', ['상대 판결'])
            설정 = {
                '제목': '시험', '출력': '출력/묶음.pdf',
                '문서': [
                    {'이름': '예상 질의', '약칭': '질의', '갈래': '내부', '파일': '질의.pdf'},
                    {'이름': '답변서', '약칭': '답1', '갈래': '우리', '쪽시작면': 2, '파일': '답변서.pdf'},
                    {'이름': '이유서', '약칭': '이1', '갈래': '상대', '파일': '이유서.pdf'}],
                '증거': [
                    {'이름': '우리 증거', '갈래': '우리', '파일들': ['우리/*']},
                    {'이름': '상대 증거', '갈래': '상대', '파일들': ['상대/*']}]}
            경로 = 사건 / '설정.json'
            경로.write_text(json.dumps(설정, ensure_ascii=False), encoding='utf-8')
            글 = io.StringIO()
            with redirect_stdout(글):
                출력, 순서, 앞면수 = hp.묶기(경로)
                확인 = hp.확인(경로)
            try:
                인용 = {(z['갈래'], z['호증']['이름']): [(a['약칭'], i) for a, i in z['인용']] for z in 순서 if z.get('호증')}
                # 우리 서면은 우리 참고자료 1 에, 상대 서면은 상대 참고자료 1 에 잇는다. 상대에만 있는 참고자료 2 는 질의가 든 것을 잇고,
                # 답변서 입증방법 면의 '참고자료 2' 는 세지 않는다. 질의의 '참고자료 1' 은 어느 쪽인지 몰라 잇지 않는다.
                self.assertEqual(인용, {
                    ('우리', '사 제1호증'): [('답1', 1)],
                    ('우리', '참고자료 1'): [('답1', 1)],
                    ('상대', '참고자료 1'): [('이1', 0)],
                    ('상대', '참고자료 2'): [('질의', 0)],
                })
                self.assertIn('인용 쪽을 찾은 호증 4/4', 글.getvalue())
                self.assertIn('어느 쪽 것인지 정하지 못한 인용 1곳', 글.getvalue())
                self.assertEqual(확인, 0, 글.getvalue())

                d = pymupdf.open(출력)
                시작 = {z['약칭']: z['시작'] for z in 순서}

                def 띠단추(pno):
                    pg = d[pno]
                    return {pg.get_textbox(l['from']).strip(): l['page'] for l in pg.get_links() if l['from'].x1 <= hp.B + 2}

                답 = 띠단추(시작['답1'] + 1)
                self.assertIn('◀ 참고자료1', 답)
                self.assertIn('◀ 사1', 답)
                self.assertTrue(1 <= 답['◀ 참고자료1'] < 앞면수)          # 호증 면 목록으로 돌아간다
                질 = 띠단추(시작['질의'])
                self.assertIn('◀ 참고자료2', 질)
                self.assertNotIn('◀ 참고자료1', 질)
                목록 = [(d[k].get_textbox(l['from']).strip(), l['page']) for k in range(1, 앞면수) for l in d[k].get_links()]
                self.assertEqual(목록.count(('답1-1', 시작['답1'] + 1)), 2)   # 사 제1호증·우리 참고자료 1 줄
                self.assertIn(('이1-1', 시작['이1']), 목록)
                self.assertIn(('질의-1', 시작['질의']), 목록)
                d.close()
            finally:
                for z in 순서:
                    z['원본'].close()


def 누운_pdf(경로, 글):
    """가로 표를 눕혀 A4 세로에 넣은 면처럼, 글이 아래에서 위로 읽히는 면 하나."""
    d = pymupdf.open()
    pg = d.new_page(width=595, height=842)
    pg.insert_font(fontname='kr', fontfile=str(글꼴))
    for k in range(3):
        pg.insert_text((120 + 40 * k, 760), 글, fontname='kr', fontsize=11, rotate=90)
    경로.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(경로))
    d.close()


@unittest.skipUnless(글꼴.exists(), '맑은 고딕이 없음')
class 누운면(unittest.TestCase):
    """2026. 11. 5. OES 담당 노무사 "사 제14호증같이 돌려져서 제출한건 적어도 내가 심문회의에서 볼 땐 보기 좋게 돌려줘야지".
    글자층이 있는 누운 면은 글 방향으로 스스로 세우고, 스캔처럼 글이 없는 면은 설정의 "돌림" 에 적은 면만 돌리며, 0 이면 돌리지 않는다.
    맞대기(확인)는 원본 그림을 같은 각도로 돌려 견주므로 0 이어야 한다."""

    def test_누운_면_세우기(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            사건 = Path(tmp) / '사건' / '시험'
            pdf(사건 / '답변서.pdf', ['답 변 서 사 제1호증, 사 제2호증, 사 제3호증'])
            누운_pdf(사건 / '우리' / '사 제1호증_재계약 현황.pdf', '계약직 채용자의 재계약 현황 및 퇴사사유 표의 한 줄입니다')
            pdf(사건 / '우리' / '사 제2호증_회의록.pdf', ['회의록 첫 면', '붙임 표가 있는 둘째 면'])
            누운_pdf(사건 / '우리' / '사 제3호증_표.pdf', '돌리지 않기로 한 누운 표의 한 줄입니다 그대로 둡니다')
            설정 = {'제목': '시험', '출력': '출력/묶음.pdf',
                    '문서': [{'이름': '답변서', '약칭': '답1', '갈래': '우리', '파일': '답변서.pdf'}],
                    '증거': [{'이름': '우리 증거', '갈래': '우리', '파일들': ['우리/*']}],
                    '돌림': {'사 제2호증': {'2': 90}, '사제3호증': 0}}
            경로 = 사건 / '설정.json'
            경로.write_text(json.dumps(설정, ensure_ascii=False), encoding='utf-8')
            글 = io.StringIO()
            with redirect_stdout(글):
                출력, 순서, 앞면수 = hp.묶기(경로)
                확인 = hp.확인(경로)
            try:
                self.assertEqual(확인, 0, 글.getvalue())
                self.assertIn('바로 세운 면 2', 글.getvalue())
                d = pymupdf.open(출력)
                시작 = {z['약칭']: z['시작'] for z in 순서}

                def 크기(pno):
                    r = d[pno].rect
                    return round(r.width - hp.B), round(r.height)

                self.assertEqual(크기(시작['사1']), (842, 595))         # 글 방향으로 세워 가로가 된다
                self.assertEqual(크기(시작['사2']), (595, 842))         # 설정에 없는 면은 그대로
                self.assertEqual(크기(시작['사2'] + 1), (842, 595))     # 설정의 '2': 90
                self.assertEqual(크기(시작['사3']), (595, 842))         # 설정 0 은 돌리지 않는다
                방향 = {(round(l['dir'][0]), round(l['dir'][1])) for b in d[시작['사1']].get_text('dict')['blocks']
                        for l in b.get('lines', []) if ''.join(s['text'] for s in l['spans']).strip()}
                self.assertEqual(방향, {(1, 0)})                         # 세운 면의 글은 왼쪽에서 오른쪽으로 읽힌다
                d.close()
            finally:
                for z in 순서:
                    z['원본'].close()


if __name__ == '__main__':
    unittest.main()
