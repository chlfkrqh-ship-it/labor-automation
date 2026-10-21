# -*- coding: utf-8 -*-
"""제출 묶음의 증거를 바로 보낼 수 있는 압축파일 하나로 묶는다(`4_서면작성/CLAUDE.md` 2-1절).

2026. 10. 21. 박준선 항소이유서 담당자 지시("앞으로는 제출 폴더에 증거 압축파일도 zip으로 하나 만들어주고, 이름은 가령
(박준선) 항소이유서라면 (박준선) 항소이유서_서증 이런식으로 … 내가 바로 그냥 보낼 수 있게 하자는 취지").

 - 이름: 제출 폴더의 서면 파일 이름 '({의뢰인명}) {서면명}_초안.docx' 에서 판 이름(_초안, _n차 수정안, _수정, _최종, _간이안)을
   떼고 '_서증.zip' 을 붙인다 → '(박준선) 항소이유서_서증.zip'. 이름이 다른 서면이 둘 이상이면 --이름 으로 준다.
 - 담는 것: 제출/증거/ 의 파일 전부를 하위 폴더 없이 파일 이름 그대로, 호증 번호 순(숫자는 수로 견줌)으로 담는다.
   참고자료/ 와 서면은 넣지 않는다. 파일 이름은 UTF-8 표시를 붙여 넣는다(Windows 탐색기·반디집에서 한글이 그대로 보인다).
 - 다시 만들면 덮어쓴다. 증거를 고치면 압축파일도 다시 만든다(낡은 압축파일이 제출 묶음에 남지 않게).
 - 끝에 스스로 확인한다: 압축파일을 다시 열어 파일 목록·크기·SHA-256 이 증거/ 와 같은지, 손상 검사(testzip)를 통과하는지.
 - --확인 을 주면 만들지 않고, 지금 압축파일이 증거/ 와 같은지만 본다(`/서면` 9-2단계). 다르면 종료 코드 1 이다.

쓰는 법:
    python 4_서면작성/scripts/evidence_zip.py "<라운드N/출력/제출>" [--이름 "(의뢰인명) 서면명"] [--확인]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path

VERSION = re.compile(r'_(?:초안|\d+차\s*수정안|수정안?|최종|간이안)$')


def 자연순(path: Path):
    """'을나 제3호증' 이 '을나 제25호증' 보다 앞서도록 숫자는 수로 견준다."""
    return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', path.name)]


def 서면이름(제출: Path, 이름: str | None = None) -> str:
    if 이름:
        return 이름
    후보 = sorted({VERSION.sub('', p.stem) for p in 제출.glob('*.docx') if not p.name.startswith('~$')})
    if len(후보) != 1:
        raise SystemExit('서면 이름을 정하지 못했습니다(%s). --이름 "(의뢰인명) 서면명" 으로 주십시오.'
                         % (', '.join(후보) or '제출 폴더에 docx 없음'))
    return 후보[0]


def 증거목록(제출: Path) -> list[Path]:
    폴더 = 제출 / '증거'
    파일 = sorted((p for p in 폴더.glob('*') if p.is_file() and not p.name.startswith(('~$', '.'))), key=자연순) if 폴더.is_dir() else []
    if not 파일:
        raise SystemExit('증거 파일이 없습니다: %s' % 폴더)
    return 파일


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def 맞대기(zip경로: Path, 파일: list[Path]) -> list[str]:
    """압축파일이 증거/ 와 같은지 본다. 다른 점을 글로 돌려준다(같으면 빈 목록)."""
    다름 = []
    with zipfile.ZipFile(zip경로) as z:
        bad = z.testzip()
        if bad:
            다름.append('손상된 항목: %s' % bad)
        이름들 = z.namelist()
        if 이름들 != [p.name for p in 파일]:
            빠짐 = [p.name for p in 파일 if p.name not in 이름들]
            남음 = [n for n in 이름들 if n not in {p.name for p in 파일}]
            다름.append('파일 목록이 다름(빠짐 %s / 증거에 없음 %s / 순서 %s)'
                      % (빠짐 or '없음', 남음 or '없음', '다름' if not (빠짐 or 남음) else '-'))
        for p in 파일:
            if p.name in 이름들 and sha(z.read(p.name)) != sha(p.read_bytes()):
                다름.append('내용이 다름: %s' % p.name)
    return 다름


def 만들기(제출: Path, 이름: str | None = None) -> Path:
    파일 = 증거목록(제출)
    대상 = 제출 / ('%s_서증.zip' % 서면이름(제출, 이름))
    임시 = 대상.with_name(대상.name + '.tmp')
    with zipfile.ZipFile(임시, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in 파일:
            z.write(p, arcname=p.name)
    try:
        임시.replace(대상)
    except PermissionError:
        임시.unlink()
        raise SystemExit('중단: %s 가 열려 있어 쓸 수 없습니다. 닫은 뒤 다시 실행하십시오.' % 대상.name)
    다름 = 맞대기(대상, 파일)
    if 다름:
        raise SystemExit('만든 압축파일이 증거/ 와 다릅니다: ' + '; '.join(다름))
    return 대상


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('제출', help='라운드N/출력/제출 폴더')
    ap.add_argument('--이름', help='서면 이름("(의뢰인명) 서면명"). 주지 않으면 제출 폴더의 서면 docx 이름에서 정한다')
    ap.add_argument('--확인', action='store_true', help='만들지 않고 지금 압축파일이 증거/ 와 같은지만 본다')
    a = ap.parse_args(argv)
    제출 = Path(a.제출)
    파일 = 증거목록(제출)
    대상 = 제출 / ('%s_서증.zip' % 서면이름(제출, a.이름))
    if a.확인:
        if not 대상.exists():
            print('압축파일이 없습니다: %s' % 대상.name)
            return 1
        다름 = 맞대기(대상, 파일)
        print(('다름: ' + '; '.join(다름)) if 다름 else '같음: %s (파일 %d개)' % (대상.name, len(파일)))
        return 1 if 다름 else 0
    대상 = 만들기(제출, a.이름)
    원본 = sum(p.stat().st_size for p in 파일)
    print('만듦: %s — 파일 %d개, 증거 %.1fMB → 압축파일 %.1fMB, 다시 열어 목록·내용 같음'
          % (대상.name, len(파일), 원본 / 1048576, 대상.stat().st_size / 1048576))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
