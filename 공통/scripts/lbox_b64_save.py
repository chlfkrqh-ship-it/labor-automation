# -*- coding: utf-8 -*-
"""인앱 브라우저에서 받은 파일(판결문 PDF·글 묶음 zip)을 저장 창 없이 폴더에 되살린다(lbox-검색 9항 '인앱 브라우저에서 받기').

인앱 브라우저의 내려받기는 쓸 수 없다(2026. 10. 22. 저장 창도 파일도 없이 'blob:' 제목의 Claude 창만 떴다). 그래서 페이지에서
파일을 base64 글로 바꿔 스크립트 실행 결과로 돌려받는다. 결과가 길면 도구가 세션의 tool-results 폴더에 JSON 파일로 저장하고
경로를 알려 준다(대화에는 들어오지 않는다). 이 스크립트가 그 파일에서
'LBOXB64|{퍼센트 인코딩한 저장 이름}|{바이트 수}|{base64}|END' 조각을 찾아 파일로 쓰고 확인한다.

    python -B 공통/scripts/lbox_b64_save.py "{결과 파일}" ["{결과 파일}" …] --out "{사건 폴더}/작업/인용판결_PDF"
    python -B 공통/scripts/lbox_b64_save.py … --out … --remove     # 모두 확인되면 결과 파일을 지운다

보는 것: 조각에 적힌 바이트 수와 되살린 크기가 같은지, PDF 는 '%PDF-' 머리와 면수, 첫 두 면에 저장 이름의 사건번호가 있는지.
하나라도 어긋나면 종료 코드 1 이고 --remove 를 해도 결과 파일을 지우지 않는다. LBOX 에는 요청을 보내지 않는다.
"""
import argparse
import base64
import json
import os
import re
import sys
from urllib.parse import unquote

sys.stdout.reconfigure(encoding="utf-8")
PIECE = re.compile(r"LBOXB64\|([^|\s]+)\|(\d+)\|([A-Za-z0-9+/=]+)\|END")
CASE = re.compile(r"(?:19|20)?\d{2}[가-힣]{1,3}\d+")


def read_result(path):
    """도구 결과 파일의 글. JSON 배열([{type, text}, …])이면 text 를 잇고, 아니면 그대로 읽는다."""
    raw = open(path, encoding="utf-8").read()
    try:
        arr = json.loads(raw)
    except ValueError:
        return raw
    if isinstance(arr, list):
        return "".join(x.get("text", "") for x in arr if isinstance(x, dict))
    return raw


def check_pdf(path, name):
    import pymupdf
    with pymupdf.open(path) as d:
        first = "".join(d[k].get_text() for k in range(min(2, d.page_count)))
        pages = d.page_count
    m = CASE.search(name)
    if not m:
        return pages, "사건번호 없는 이름"
    return pages, "있음" if re.sub(r"\s", "", m.group(0)) in re.sub(r"\s", "", first) else "없음"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+", help="스크립트 실행 결과가 저장된 tool-results 파일")
    ap.add_argument("--out", required=True, help="저장할 폴더")
    ap.add_argument("--remove", action="store_true", help="모두 확인되면 결과 파일을 지운다")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ok, n = True, 0
    for res in a.results:
        for name_enc, size, b64 in PIECE.findall(read_result(res)):
            name = os.path.basename(unquote(name_enc))
            data = base64.b64decode(b64)
            p = os.path.join(a.out, name)
            open(p, "wb").write(data)
            n += 1
            line = f"{name} | {len(data):,}바이트"
            if len(data) != int(size):
                ok = False
                line += f" | 크기 어긋남(적힌 값 {int(size):,})"
            if name.lower().endswith(".pdf"):
                if data[:5] != b"%PDF-":
                    ok = False
                    line += " | PDF 아님"
                else:
                    pages, found = check_pdf(p, name)
                    line += f" | {pages}면 | 첫 두 면 사건번호 {found}"
                    if found == "없음":
                        ok = False
            print(line)
    if n == 0:
        print("LBOXB64 조각을 찾지 못하였다")
        ok = False
    print(f"되살린 파일 {n}개 · {'이상 없음' if ok else '어긋남 있음'}")
    if ok and a.remove:
        for res in a.results:
            os.remove(res)
        print("결과 파일을 지웠다:", len(a.results))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
