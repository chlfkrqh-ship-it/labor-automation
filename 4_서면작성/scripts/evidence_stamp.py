"""호증·별첨·참고자료 PDF 의 첫 면에 사무소 도장을 넣는다(법원 외에 내는 서면, `4_서면작성/CLAUDE.md` 2-1절).

법원에 전자소송으로 내는 서증에는 쓰지 않는다. 전자소송이 서증 첫 면 아래 가운데에 '갑 제3호증' 같은 표시를 자동으로 넣는다.

모양은 사무소가 ezPDF 로 찍어 온 호증 도장을 잰 것이다(표본: GGM_변호인의견서 사건 `우리증거/중앙2026부노6/` 의
'사 제01호증', '사 제20호증의 1' 첫 면). 세로 테두리 상자 안에 궁서 글자를 세로로 놓고 번호만 검은 바탕체 18pt 굵은 글자로 한다.

 - 글자는 파일 이름 앞머리에서 읽는다. '사 제3호증_…'·'갑제12호증의2_…'·'을가 제5호증_…' 은 머리 글자·'제'·[번호]·'호'·'증'
   (가지번호는 '의'·[가지번호]), '참고자료 2_…' 는 '참'·'고'·'자'·'료'·[2], '별첨 4_…' 는 '별'·'첨'·[4] 이다.
   본문이 인용하는 표기와 같은 이름으로 파일을 둔다.
 - 색은 그 절차에서 의뢰인이 신청하는 쪽(신청인·재심신청인·진정인·청구인 등)이면 빨강, 상대하는 쪽(피신청인·재심피신청인·
   피진정인 등)이면 파랑이다(2026. 10. 14. 담당자 지시).
 - 첫 면에만 넣는다. 자리는 오른쪽 여백의 가운데 높이(표본과 같이 면 가운데보다 조금 아래)이고, 그 자리에 글이나 그림이 있으면
   오른쪽으로 옮긴다. 그래도 겹치면 같은 높이에서 세로 줄(문서 테두리·표 선)만 지나가는 자리를 찾아 상자 안을 희게 채워 덮고,
   그것도 없으면 위아래로 옮겨 빈 자리를 찾는다. 빈 자리가 없으면 가장 덜 겹치는 자리에 넣고 '겹침'으로 알린다.
 - 글자는 글꼴을 심지 않고 그림으로 넣는다(글꼴 묶음이 통째로 들어가 파일이 커진다). 테두리는 선으로 그린다.
 - 원본 폴더의 파일은 고치지 않는다. 낼 폴더에 사본을 만들어 첫 면에만 덧그린 뒤 덧붙여 저장(incremental)한다.
   PDF 가 아닌 파일(녹음 등)은 그대로 복사하고, 표시를 읽을 수 없는 이름은 건너뛴다.
 - 끝에 스스로 확인한다: 면수가 같은지, 2면부터는 원본과 그림이 같은지, 첫 면은 도장 자리 밖이 원본과 같은지.
   `--확인그림` 을 주면 도장 부분을 모은 그림을 만든다. 그림은 사건 폴더 안, 제출 묶음 밖(`증거관리/도장확인.png`)에 둔다.

쓰는 법:
    python 4_서면작성/scripts/evidence_stamp.py <원본 폴더> <낼 폴더> --색 빨강|파랑 [--확인그림 <png 경로>]
낼 파일 이름은 원본 이름에서 호증 머리와 '제' 사이만 띄운다('사제3호증_…' → '사 제3호증_…').
다른 스크립트에서는 `표시읽기(파일 이름)` 와 `도장(page, 표시, 색)` 을 불러 쓴다.

처음 만든 곳은 한영대(2026. 10. 8.)·GGM 정직3월(10. 12.)·OES(10. 13.) 사건 빌드 폴더의 `호증도장.py` 와
하나기술(10. 14.) `증거_만들기.py` 이다. 이 파일이 그것들을 대신한다.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('workflow_system', ROOT / '공통/scripts/system.py')
_system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_system)

글꼴묶음, 바탕체, 궁서 = 'C:/Windows/Fonts/batang.ttc', 1, 2      # 묶음 안 차례: 바탕, 바탕체, 궁서, 궁서체
색표 = {'빨강': (255, 0, 0), '파랑': (0, 0, 255)}

# 표본에서 잰 값(pt). 테두리 폭·굵기, 첫 글자의 먹 높이(궁서 크기를 여기에 맞춘다), 번호 크기(바탕체, 0.75pt 획을 덧그려 굵게)
폭, 테두리, 글자먹높이, 번호크기 = 30.4, 1.7, 16.7, 18.0
# 세로 간격(pt). 테두리 바깥 위 끝 → 첫 글자 먹 위, 번호 앞 글자 사이, 글자 먹 위 → 번호 밑줄, 번호 밑줄 → 다음 글자 먹 위,
# 번호 뒤 글자 사이, 마지막 먹 아래 → 테두리 바깥 아래 끝. '사 제01호증' 표본(글자 28.0·51.5, 번호 99.7, 글자 122.5·145.3,
# 높이 189.4. 가지번호 없는 표본 32.3 × 201.2 를 같은 글자 크기가 되게 30.4/32.3 으로 줄인 값)에서 잰 것이다.
위여백, 앞간격, 번호앞, 번호뒤, 뒤간격, 아래여백 = 28.0, 23.5, 48.2, 22.8, 22.8, 27.4
# 머리가 한 글자이고 가지번호가 있는 호증은 '사 제20호증의 1' 표본(30.4 × 232.4)을 그대로 쓴다
가지틀 = {'높이': 232.4, '글자': [(None, 25.8), ('제', 49.4), ('호', 120.5), ('증', 143.5), ('의', 166.4)],
         '번호': 97.5, '가지': 211.7}
배율 = 10                  # 글자 그림의 해상도(px/pt)
기본왼쪽, 기본가운데 = 557.5, 455.0     # A4(595 × 842) 기준 테두리 왼쪽 바깥 끝과 도장의 가운데 높이(표본 557.5, 454.6~456.4)
빈자리기준 = 0.0005        # 도장 자리(둘레 1.5pt 포함)에서 먹인 점의 비율이 이 값 이하이면 빈 자리로 본다

_호증 = re.compile(r'^(' + _system.EVIDENCE_PREFIX + r')\s?제\s?(\d+)\s?호증(?:\s?의\s?(\d+))?')
_참고자료 = re.compile(r'^참고자료\s?(\d+)')
_별첨 = re.compile(r'^별첨\s?(\d+)')


def 표시읽기(이름):
    """파일 이름 앞머리에서 도장 표시를 읽는다. 못 읽으면 None."""
    n = unicodedata.normalize('NFC', 이름)
    m = _호증.match(n)
    if m:
        return {'종류': '호증', '머리': m.group(1), '번호': int(m.group(2)), '가지': int(m.group(3)) if m.group(3) else None}
    for 종류, 틀 in (('참고자료', _참고자료), ('별첨', _별첨)):
        m = 틀.match(n)
        if m:
            return {'종류': 종류, '머리': '', '번호': int(m.group(1)), '가지': None}
    return None


def 표시글(표시):
    if 표시['종류'] == '호증':
        return f"{표시['머리']} 제{표시['번호']}호증" + (f"의 {표시['가지']}" if 표시['가지'] else '')
    return f"{표시['종류']} {표시['번호']}"


def 배치(표시):
    """(높이, [(글자, 먹 위 높이)], [(숫자, 밑줄 높이)]). 높이는 모두 테두리 바깥 위 끝에서 잰다."""
    if 표시['종류'] == '호증' and 표시['가지'] and len(표시['머리']) == 1:
        t = 가지틀
        return (t['높이'], [(g or 표시['머리'], y) for g, y in t['글자']],
                [(str(표시['번호']), t['번호']), (str(표시['가지']), t['가지'])])
    if 표시['종류'] == '호증':
        차례 = list(표시['머리']) + ['제', 표시['번호'], '호', '증'] + (['의', 표시['가지']] if 표시['가지'] else [])
    elif 표시['종류'] == '참고자료':
        차례 = ['참', '고', '자', '료', 표시['번호']]
    else:
        차례 = ['별', '첨', 표시['번호']]
    글자, 숫자 = [], []
    y, 앞, 번호지남 = 위여백, None, False
    for k in 차례:
        if isinstance(k, int):
            y += 번호앞 if 앞 == '글' else 0
            숫자.append((str(k), y))
            앞, 번호지남 = '번호', True
        else:
            if 앞 == '글':
                y += 뒤간격 if 번호지남 else 앞간격
            elif 앞 == '번호':
                y += 번호뒤
            글자.append((k, y))
            앞 = '글'
    높이 = y + (글자먹높이 if 앞 == '글' else 0) + 아래여백
    return round(높이, 1), 글자, 숫자


def _궁서글꼴():
    f = ImageFont.truetype(글꼴묶음, 18.0 * 배율, index=궁서)
    b = f.getbbox('사')     # 표본의 첫 글자. 이 글자의 먹 높이가 글자먹높이가 되게 크기를 정한다
    return ImageFont.truetype(글꼴묶음, 18.0 * 배율 * (글자먹높이 * 배율) / (b[3] - b[1]), index=궁서)


def 도장글자(표시, 색):
    """테두리 안에 들어갈 글자를 투명 바탕 그림(PNG)으로 만든다. 궁서 글자는 도장 색, 번호는 검정."""
    높이, 글자, 숫자 = 배치(표시)
    크기 = (round(폭 * 배율), round(높이 * 배율))
    색판, 검은판 = Image.new('L', 크기, 0), Image.new('L', 크기, 0)
    가운데 = 폭 * 배율 / 2
    글꼴 = _궁서글꼴()
    그림 = ImageDraw.Draw(색판)
    for 글, 먹위 in 글자:
        b = 글꼴.getbbox(글)
        # 글자는 먹의 폭이 아니라 글자 칸(전각)을 테두리 가운데에 맞춘다(표본이 그렇다). 높이는 먹이 시작하는 자리를 맞춘다
        그림.text((가운데 - 글꼴.getlength(글) / 2, 먹위 * 배율 - b[1]), 글, font=글꼴, fill=255)
    숫자글꼴 = ImageFont.truetype(글꼴묶음, 번호크기 * 배율, index=바탕체)
    검 = ImageDraw.Draw(검은판)
    for 글, 밑줄 in 숫자:
        검.text((가운데 - 숫자글꼴.getlength(글) / 2, 밑줄 * 배율), 글, font=숫자글꼴, fill=255, anchor='ls',
               stroke_width=round(0.375 * 배율), stroke_fill=255)
    판 = Image.new('RGB', 크기, 색)
    판.paste((0, 0, 0), mask=검은판.point(lambda v: 255 if v else 0))
    판.putalpha(ImageChops.lighter(색판, 검은판))
    통 = io.BytesIO()
    판.save(통, 'PNG', optimize=True)
    return 통.getvalue()


def _먹판(page, dpi=288):
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    return a.min(axis=2) < 225, dpi / 72


def 자리찾기(page, 높이):
    """도장을 놓을 자리(테두리 왼쪽 위 바깥 끝)와 그 자리의 먹 비율, 어떻게 정했는지를 돌려준다."""
    먹, 배 = _먹판(page)
    PW, PH = page.rect.width, page.rect.height

    def 비율(x0, y0, 둘레=1.5, 왼쪽=None, 선무시=False):
        왼 = 둘레 if 왼쪽 is None else 왼쪽
        sub = 먹[max(0, int((y0 - 둘레) * 배)):int((y0 + 높이 + 둘레) * 배),
                max(0, int((x0 - 왼) * 배)):int((x0 + 폭 + 둘레) * 배)]
        if not sub.size:
            return 1.0
        if 선무시:
            # 도장 높이 내내 먹인 열은 세로 줄(문서 테두리·표 선)이다. 글이 아니므로 도장으로 덮어도 된다
            sub = sub[:, sub.mean(axis=0) < 0.9]
            if not sub.size:
                return 0.0
        return float(sub.mean())

    밀림 = PW - 595.0 if PW > 596 else 0.0
    xs = [x + 밀림 for x in (기본왼쪽, 559.0, 560.5, 562.0) if x + 밀림 + 폭 <= PW - 2.0]
    y기본 = round(기본가운데 * PH / 842.0 - 높이 / 2, 1)
    # 먼저 본문과 4pt 넘게 떨어지는 자리를 찾고, 없으면 1.5pt 만 떨어지면 되는 자리를 찾는다(글에 바짝 붙지 않게).
    # 그래도 없으면 세로 줄만 지나가는 자리를 같은 높이에서 찾는다(오른쪽 여백에 테두리가 있는 계약서 표지 등. 2026. 10. 14.)
    for 왼쪽여유, 선무시 in ((4.0, False), (1.5, False), (4.0, True), (1.5, True)):
        for x in xs:
            v = 비율(x, y기본, 왼쪽=왼쪽여유, 선무시=선무시)
            if v <= 빈자리기준:
                어디 = '기본 자리' if x == xs[0] else '오른쪽으로 %.1fpt' % (x - xs[0])
                return x, y기본, v, 어디 + (', 세로 줄 위' if 선무시 else '')
    가장 = None
    for 선무시 in (False, True):
        for dy in range(6, int(PH), 6):
            for 부호 in (1, -1):
                y = y기본 + 부호 * dy
                if y < 15 or y + 높이 > PH - 15:
                    continue
                for x in xs:
                    v = 비율(x, y, 선무시=선무시)
                    if v <= 빈자리기준:
                        return x, y, v, '%s로 %dpt%s%s' % ('아래' if 부호 > 0 else '위', dy,
                                                           '' if x == xs[0] else ', 오른쪽으로 %.1fpt' % (x - xs[0]),
                                                           ', 세로 줄 위' if 선무시 else '')
                    if not 선무시 and (가장 is None or v < 가장[2]):
                        가장 = (x, y, v)
    return 가장[0], 가장[1], 가장[2], '겹침(빈 자리 없음)'


def 도장(page, 표시, 색):
    """page 에 도장을 넣고 (자리, 그 자리의 먹 비율, 어떻게 정했는지) 를 돌려준다. 색은 (R, G, B) 또는 '빨강'·'파랑'."""
    if isinstance(색, str):
        색 = 색표[색]
    높이 = 배치(표시)[0]
    x0, y0, 먹비율, 정한법 = 자리찾기(page, 높이)
    r = pymupdf.Rect(x0, y0, x0 + 폭, y0 + 높이)
    안 = 테두리 / 2
    if '세로 줄 위' in 정한법:
        page.draw_rect(r, color=None, fill=(1, 1, 1), width=0)     # 줄이 도장 글자를 지나가지 않게 상자 안을 희게 채운다
    page.draw_rect(pymupdf.Rect(r.x0 + 안, r.y0 + 안, r.x1 - 안, r.y1 - 안), color=tuple(c / 255 for c in 색), width=테두리)
    page.insert_image(r, stream=도장글자(표시, 색), overlay=True)
    return r, 먹비율, 정한법


def _면그림(page, dpi=60):
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(np.int16)


def 확인(원본, 사본, r):
    """면수, 2면 이후의 그림, 첫 면의 도장 자리 밖이 원본과 같은지 본다. 어긋난 것을 글로 돌려준다."""
    a, b = pymupdf.open(str(원본)), pymupdf.open(str(사본))
    흠 = []
    if len(a) != len(b):
        흠.append('면수 %d → %d' % (len(a), len(b)))
    for i in range(min(len(a), len(b))):
        x, y = _면그림(a[i]), _면그림(b[i])
        if x.shape != y.shape:
            흠.append('%d면 크기 다름' % (i + 1))
            continue
        d = np.abs(x - y).max(axis=2) > 24
        if i == 0:
            k = 60 / 72
            d[max(0, int((r.y0 - 3) * k)):int((r.y1 + 3) * k) + 1, max(0, int((r.x0 - 3) * k)):int((r.x1 + 3) * k) + 1] = False
        if d.any():
            흠.append('%d면에서 원본과 다른 점 %d개' % (i + 1, int(d.sum())))
    a.close()
    b.close()
    return 흠


def 확인그림(줄들, 경로):
    """도장 부분(오른쪽 여백과 그 옆 내용 조금)을 잘라 한 장에 모은다. 칸 위에 도장 표시를 적는다."""
    칸들 = []
    글꼴 = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)
    칸높이 = 470
    for 글, 사본, r in 줄들:
        d = pymupdf.open(str(사본))
        p = d[0]
        clip = pymupdf.Rect(max(0, r.x0 - 95), max(0, r.y0 - 22), p.rect.x1, min(p.rect.y1, r.y1 + 22))
        pix = p.get_pixmap(dpi=110, clip=clip, alpha=False)
        im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        칸 = Image.new('RGB', (im.width + 8, 칸높이), 'white')
        칸.paste(im, (4, 26))
        ImageDraw.Draw(칸).text((4, 3), 글, font=글꼴, fill=(200, 0, 0))
        칸들.append(칸)
        d.close()
    열 = 11
    w = max(c.width for c in 칸들)
    행 = (len(칸들) + 열 - 1) // 열
    판 = Image.new('RGB', (w * 열, 칸높이 * 행), 'white')
    for i, c in enumerate(칸들):
        판.paste(c, ((i % 열) * w, (i // 열) * 칸높이))
    Path(경로).parent.mkdir(parents=True, exist_ok=True)
    판.save(str(경로))
    print('확인 그림:', 경로)


def _차례(표시):
    return ({'호증': 0, '별첨': 1, '참고자료': 2}[표시['종류']], 표시['머리'], 표시['번호'], 표시['가지'] or 0)


def _낼이름(이름, 표시):
    if 표시['종류'] == '호증':
        return re.sub(r'^(' + _system.EVIDENCE_PREFIX + r')\s?제', r'\1 제', 이름)
    return 이름


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('원본')
    ap.add_argument('낼곳')
    ap.add_argument('--색', required=True, choices=sorted(색표), help='의뢰인이 신청하는 쪽이면 빨강, 상대하는 쪽이면 파랑')
    ap.add_argument('--확인그림', help='도장 부분을 모은 그림(png) 경로. 사건 폴더 안, 제출 묶음 밖')
    a = ap.parse_args(argv)
    원본폴더, 낼폴더 = Path(a.원본), Path(a.낼곳)
    if 원본폴더.resolve() == 낼폴더.resolve():
        raise SystemExit('원본 폴더와 낼 폴더가 같다. 원본은 고치지 않으므로 다른 폴더를 준다')
    낼폴더.mkdir(parents=True, exist_ok=True)
    파일들 = []
    for f in 원본폴더.iterdir():
        이름 = unicodedata.normalize('NFC', f.name)
        표시 = 표시읽기(이름) if f.is_file() else None
        if 표시 is None:
            print('건너뜀(도장 표시를 읽을 수 없는 이름):', 이름)
            continue
        파일들.append((_차례(표시), f, 이름, 표시))
    줄들, 문제 = [], []
    for _, f, 이름, 표시 in sorted(파일들, key=lambda x: x[0]):
        낼이름 = _낼이름(이름, 표시)
        낼 = 낼폴더 / 낼이름
        shutil.copyfile(f, 낼)
        if f.suffix.lower() != '.pdf':
            print('그대로 복사(도장 없음): %s' % 낼이름)
            continue
        d = pymupdf.open(str(낼))
        if d.is_encrypted or not d.can_save_incrementally():
            d.close()
            문제.append('%s: 덧붙여 저장할 수 없는 파일(암호 또는 손상). 도장을 넣지 않았다' % 낼이름)
            continue
        r, 먹비율, 정한법 = 도장(d[0], 표시, 색표[a.색])
        d.saveIncr()
        면수 = d.page_count
        d.close()
        흠 = 확인(f, 낼, r)
        print('%-16s %3d면 | 도장 [%.1f, %.1f] ~ [%.1f, %.1f] | %s%s%s' % (
            표시글(표시), 면수, r.x0, r.y0, r.x1, r.y1, 정한법,
            '' if 먹비율 <= 빈자리기준 else ' | 겹친 먹 비율 %.4f' % 먹비율, ' | 확인: ' + '; '.join(흠) if 흠 else ''))
        if 흠 or 먹비율 > 빈자리기준:
            문제.append('%s: %s' % (낼이름, '; '.join(흠) or '도장 자리에 내용이 있음(%s, 먹 비율 %.4f)' % (정한법, 먹비율)))
        줄들.append((표시글(표시), 낼, r))
    print('도장 넣은 파일 %d개 · 색 %s' % (len(줄들), a.색))
    if a.확인그림 and 줄들:
        확인그림(줄들, a.확인그림)
    if 문제:
        print('== 사람이 볼 것 %d건' % len(문제))
        for m in 문제:
            print('  ', m)
        return 1
    print('확인: 모든 파일의 면수가 같고, 2면부터는 원본과 같으며, 첫 면은 도장 자리 밖이 원본과 같다')
    return 0


if __name__ == '__main__':
    sys.exit(main())
