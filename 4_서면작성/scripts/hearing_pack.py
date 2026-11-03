"""심문회의 자료를 아이패드에서 보기 좋게 한 PDF 로 묶는다(노동위원회 심문회의·재판 기일 현장용).

2026. 11. 3. OES 부당해고 담당 노무사 "심문회의에서 활용할 자료 현장에서 아이패드로 보기 좋게 정리좀 부탁",
"항상 위원이 무슨 증거 얘기할 때 찾아다니느게 너무 힘들엇어", "첫 페이지로 돌아가는것도 용이해야겟다",
"서면 목차도 앞에 배치해서 서면 내용도 바로갈 수 있게 정리하면 딱 좋것네". GGM 세션의 제안(회전된 면, 인쇄 쪽 번호,
면 이름, 여러 면 호증의 면 단추, 앞·다음 호증, 호증을 인용한 서면 쪽, 녹음·영상 호증)을 함께 넣었다.

모양
- 1면(처음): 문서 단추(갈래별 색: 내부·우리·상대·서류)와 호증 번호 단추판(우리·상대). 누르면 그 첫 면으로 간다.
- 서면 목차: 문서마다 제목 줄. 누르면 그 자리로 가고, 오른쪽은 그 문서의 인쇄 쪽 번호이다.
- 호증 면 목록: 호증마다 면 단추(2면 이상)와 그 호증을 인용한 서면 쪽 단추(우리 서면은 남색, 상대 서면은 회색).
- 나머지 면: 원본 면 위에 띠를 덧대어 '◀ 처음'·'목차'(또는 '호증 목록')·'◀ 앞 호증'·'다음 호증 ▶' 단추와
  '사 제17호증 … 2/4면'·'답변서(1) … 23쪽' 같은 위치를 적는다. 원본 면의 내용 위에는 그리지 않는다
  (회전 0·상자가 단순한 면은 면 상자를 위로 늘리고, 아니면 새 면에 원본 면을 그대로 놓는다). 끝에 면마다 원본과 그림을 맞댄다.
- 면 이름(page label): '처음', '목차-1', '호증목록-1', 문서마다 '답1-23'(인쇄 쪽)·'사17-2' 꼴. 책갈피도 단다.
- PDF 가 아닌 호증: 그림(jpg·png)은 면으로 넣고, 녹음·영상 등은 자리 면을 두고 파일을 출력 폴더의 '호증 파일/' 에 복사한다.

설정 json(경로는 사건 폴더 기준. 사건 폴더는 설정 파일 위로 올라가며 '사건' 폴더 바로 아래의 것):
{
  "제목": "OES 부당해고 구제신청 심문회의 자료",
  "부제": "전남2026부해891 · 심문회의 2026. 11. 5.(목) 15:00 · 전남지방노동위원회",
  "출력": "라운드2/출력/심문회의 자료(2026. 11. 5.)/(OES) 심문회의 자료.pdf",
  "그림": {"dpi": 150, "품질": 75},                       # 생략하면 그림을 다시 압축하지 않는다(무손실 압축만)
  "문서": [
    {"이름": "예상 질의 및 답변", "약칭": "질의", "갈래": "내부", "파일": "….pdf", "목차": {"질의답변": "….docx"}},
    {"이름": "답변 요지 PT", "약칭": "PT", "갈래": "우리", "파일": "….pdf", "목차": "책갈피"},
    {"이름": "답변서(1)", "약칭": "답1", "갈래": "우리", "파일": "….pdf", "쪽시작면": 2, "목차": "목차면"},
    {"이름": "답변서(2)", "약칭": "답2", "갈래": "우리", "파일": "….pdf", "쪽시작면": 2, "목차": {"찾기": [[1, "1. …"], [2, "가. …"]]}},
    {"이름": "이유서", "약칭": "이1", "갈래": "상대", "파일": "….pdf", "목차": {"면": [[1, "신청취지", 2], [2, "1. 당사자관계", 2]]}},
    {"이름": "심문회의 서류", "약칭": "서류", "갈래": "서류", "뒤": true, "파일들": [{"이름": "참석자 명단", "파일": "….pdf"}]}
  ],
  "증거": [
    {"이름": "우리 증거", "갈래": "우리", "파일들": ["라운드1/출력/제출/증거/*", "라운드2/출력/제출/증거/*"]},
    {"이름": "상대 증거", "갈래": "상대", "파일들": ["라운드1/상대증거/호증별/노제*"]}
  ]
}
- "쪽시작면": 인쇄 쪽 번호 1 이 찍힌 PDF 면(표지에 번호가 없는 우리 서면은 2). 없으면 1. 띠·목차·면 이름이 이 번호를 쓴다.
- "목차": "목차면"(서면 앞쪽 목차 면의 링크), "책갈피"(원본 PDF 의 책갈피), {"찾기": [[단계, 글]]}(글자층에서 차례로 찾음, 공백 무시),
  {"면": [[단계, 글, 면]]}(스캔본처럼 글자가 없을 때 직접), {"질의답변": docx}(예상 질의답변 docx 의 절과 질문). 단계를 0 으로 주면
  '1.'·'가.'·'(1)' 머리로 정한다.
- "뒤": true 인 문서는 증거 다음에 둔다. 호증 이름은 파일 이름에서 읽는다('사 제17호증_…', '노제1호증_…', '노위 제2호증의1_…').

    python -B 4_서면작성/scripts/hearing_pack.py "<설정.json>"
    python -B 4_서면작성/scripts/hearing_pack.py "<설정.json>" --확인      # 다시 만들지 않고 만든 PDF 만 맞댄다
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path

import fitz

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
글꼴 = {"R": "C:/Windows/Fonts/malgun.ttf", "B": "C:/Windows/Fonts/malgunbd.ttf"}
S = 24                                   # 덧대는 띠 높이(pt)
A4 = (595.0, 842.0)
M = 22                                   # 앞 면 여백
남색 = (32 / 255, 70 / 255, 100 / 255)   # 평안 색
색 = {
    "내부": ((0.62, 0.40, 0.05), (1.00, 0.95, 0.85)),
    "우리": (남색, (0.90, 0.94, 0.98)),
    "상대": ((0.42, 0.42, 0.45), (0.94, 0.94, 0.95)),
    "서류": ((0.30, 0.38, 0.44), (0.93, 0.95, 0.96)),
}
상대호증색 = ((0.55, 0.16, 0.16), (0.99, 0.93, 0.93))
글색 = (0.13, 0.13, 0.15)
흐린글 = (0.38, 0.38, 0.42)
그림확장 = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff"}
_font = {}


def F(kind: str) -> fitz.Font:
    if kind not in _font:
        _font[kind] = fitz.Font(fontfile=글꼴[kind])
    return _font[kind]


def 폭(글: str, 크기: float, kind: str = "R") -> float:
    return F(kind).text_length(글, fontsize=크기)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def 빈칸없이(s: str) -> str:
    return re.sub(r"\s+", "", nfc(s))


def 줄나누기(글: str, 너비: float, 크기: float, kind: str = "R", 최대: int = 0) -> list:
    """너비 안에 들게 낱말 단위로(안 되면 글자 단위로) 줄을 나눈다. 최대 줄 수를 넘으면 끝을 '…'로 줄인다."""
    줄, 지금 = [], ""
    for 낱말 in re.split(r"(\s+)", 글):
        if not 낱말:
            continue
        후보 = 지금 + 낱말
        if 폭(후보, 크기, kind) <= 너비:
            지금 = 후보
            continue
        if 지금.strip():
            줄.append(지금.rstrip())
            지금 = 낱말.lstrip()
        else:
            지금 = 낱말.lstrip()
        while 폭(지금, 크기, kind) > 너비:          # 한 낱말이 너비보다 길면 글자로 자른다
            i = len(지금)
            while i > 1 and 폭(지금[:i], 크기, kind) > 너비:
                i -= 1
            줄.append(지금[:i])
            지금 = 지금[i:]
    if 지금.strip():
        줄.append(지금.rstrip())
    if 최대 and len(줄) > 최대:
        줄 = 줄[:최대]
        while 줄[-1] and 폭(줄[-1] + "…", 크기, kind) > 너비:
            줄[-1] = 줄[-1][:-1]
        줄[-1] += "…"
    return 줄


# ── 자료 읽기 ──

def 사건_폴더(설정: Path) -> Path:
    for p in 설정.resolve().parents:
        if p.parent.name == "사건":
            return p
    raise SystemExit(f"설정 파일이 사건 폴더 안에 있지 않다: {설정}")


호증꼴 = re.compile(r"^(?P<p>노위|사|노|갑|을|병)\s*제?\s*(?P<n>\d+)\s*호증(?:\s*의\s*(?P<s>\d+))?\s*[_ ]?\s*(?P<t>.*)$")
참고꼴 = re.compile(r"^(?P<p>참고자료)\s*(?P<n>\d+)\s*[_ ]?\s*(?P<t>.*)$")


def 호증_이름(파일: Path):
    stem = nfc(파일.stem).strip()
    m = 호증꼴.match(stem) or 참고꼴.match(stem)
    if not m:
        return None
    p, n = m.group("p"), int(m.group("n"))
    s = int(m.group("s")) if m.groupdict().get("s") else None
    if p == "참고자료":
        이름 = f"참고자료 {n}"
        짧은 = f"참{n}"
    else:
        이름 = f"{p} 제{n}호증" + (f"의{s}" if s else "")
        짧은 = f"{p}{n}" + (f"의{s}" if s else "")
    return {"접두": p, "번호": n, "가지": s, "이름": 이름, "짧은": 짧은, "표제": m.group("t").strip(" _")}


def 질의답변_목차(docx: Path) -> list:
    """예상 질의답변 docx(`/예상질의` 양식)의 절(다음 문단이 '가.' 질문인 짧은 문단)과 질문('가.' 머리 문단)."""
    x = zipfile.ZipFile(docx).read("word/document.xml").decode("utf-8")
    문단 = []
    for p in re.findall(r"<w:p\b[^>]*?/>|<w:p\b[^>]*?(?<!/)>.*?</w:p>", x, flags=re.S):
        t = "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", p)).strip()
        if t:
            문단.append(t)
    목록 = []
    for i, t in enumerate(문단):
        if re.match(r"^[가-하]\.", t):
            목록.append([2, re.sub(r"^([가-하]\.)\s*", r"\1 ", t)])
        elif i + 1 < len(문단) and re.match(r"^[가-하]\.", 문단[i + 1]) and len(t) <= 40 and not t.startswith("["):
            목록.append([1, t])
    for i, t in enumerate(문단):                     # 맨 끝의 '최종 진술' 같은 절(질문 없이 답만 있는 절)
        if t in ("최종 진술", "최종진술") and [1, t] not in 목록:
            목록.append([1, t])
    return 목록


def 머리_단계(글: str) -> int:
    if re.match(r"^\d+\.", 글):
        return 1
    if re.match(r"^[가-하]\.", 글):
        return 2
    if re.match(r"^\(\d+\)", 글):
        return 3
    return 1


def 쪽제목(src: fitz.Document) -> list:
    """쪽마다 위쪽 20% 안에서 가장 큰 글자의 줄을 그 쪽의 제목으로 한다(없으면 쪽 전체에서, 아래 10% 바닥글과 번호만 있는 줄은 뺌).
    PT 처럼 쪽이 곧 단위인 문서에 쓴다. 쪽 가운데의 큰 숫자 강조(예: '162명 84명')를 제목으로 잡지 않기 위해 위쪽을 먼저 본다."""
    목록 = []
    for i, pg in enumerate(src):
        줄들 = []
        for b in pg.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                글_ = "".join(s["text"] for s in l["spans"]).strip()
                if 글_ and l["bbox"][1] < pg.rect.height * 0.9:
                    줄들.append((max(s["size"] for s in l["spans"]), l["bbox"][1], 글_))
        if not 줄들:
            목록.append((1, f"{i + 1}쪽", i))
            continue
        줄들 = [x for x in 줄들 if len(x[2]) >= 2 and not re.fullmatch(r"[\d\s.,·~\-]+", x[2])] or 줄들   # 번호만 있는 줄은 뺀다
        위쪽 = [x for x in 줄들 if x[1] < pg.rect.height * 0.2]
        줄들 = 위쪽 or 줄들
        큰 = max(c for c, _, _ in 줄들)
        제목 = " ".join(t for c, _, t in sorted(줄들, key=lambda x: x[1]) if c >= 큰 - 0.5)
        목록.append((1, re.sub(r"\s+", " ", 제목)[:70], i))
    return 목록


def 목차_만들기(문: dict, src: fitz.Document, 사건: Path, 경고: list) -> list:
    """[(단계, 글, 원본 면 0부터)]"""
    spec = 문.get("목차")
    if not spec:
        return []
    if spec == "쪽제목":
        return 쪽제목(src)
    if spec == "책갈피":
        책 = [(lv, t, max(0, p - 1)) for lv, t, p, *_ in src.get_toc(simple=True)]
        if not 책 or all(re.match(r"^(슬라이드|Slide|페이지|Page)\s*\d+$", t.strip(), re.I) for _, t, _ in 책):
            return 쪽제목(src)                    # 'PowerPoint 로 저장한 PDF 의 '슬라이드 n' 책갈피는 쪽 제목으로 바꾼다
        return 책
    if spec == "목차면":
        목록 = []
        for pno in range(min(4, src.page_count)):
            pg = src[pno]
            for l in pg.get_links():
                if l.get("kind") != fitz.LINK_GOTO or l.get("page", -1) < 0:
                    continue
                t = re.sub(r"\s+", " ", pg.get_textbox(l["from"])).strip()
                t = re.sub(r"\s*[.·…]{2,}.*$", "", t).strip()
                t = re.sub(r"\s+\d+\s*$", "", t).strip()
                if not t:
                    continue
                if 목록 and not re.match(r"^(\d+\.|[가-하]\.|\(\d+\))", t) and 목록[-1][2] == l["page"]:
                    목록[-1] = (목록[-1][0], 목록[-1][1] + t, 목록[-1][2])     # 두 줄로 나뉜 제목
                    continue
                t = re.sub(r"^(\d+\.|[가-하]\.|\(\d+\))\s*", r"\1 ", t)
                목록.append((머리_단계(t), t, l["page"]))
        if not 목록:
            경고.append(f"{문['이름']}: 목차 면에서 링크를 찾지 못함")
        return 목록
    if isinstance(spec, dict) and "면" in spec:
        return [(lv or 머리_단계(t), t, int(p) - 1) for lv, t, p in spec["면"]]
    찾을 = None
    if isinstance(spec, dict) and "찾기" in spec:
        찾을 = [(lv or 머리_단계(t), t) for lv, t in spec["찾기"]]
    if isinstance(spec, dict) and "질의답변" in spec:
        찾을 = [tuple(x) for x in 질의답변_목차(사건 / spec["질의답변"])]
    if 찾을 is None:
        경고.append(f"{문['이름']}: 목차 지정을 알 수 없음 {spec}")
        return []
    면글 = [빈칸없이(pg.get_text()) for pg in src]
    목록, 시작 = [], 0
    for lv, t in 찾을:
        바늘 = 빈칸없이(t)[:18]
        찾은 = next((i for i in range(시작, len(면글)) if 바늘 in 면글[i]), None)
        if 찾은 is None:
            찾은 = next((i for i in range(0, len(면글)) if 바늘 in 면글[i]), None)
        if 찾은 is None:
            경고.append(f"{문['이름']}: 목차 줄을 찾지 못함 — {t[:40]}")
            continue
        목록.append((lv, t, 찾은))
        시작 = 찾은
    return 목록


def 조각_읽기(설정: dict, 사건: Path, 경고: list) -> tuple:
    """문서 조각과 증거 무리를 읽는다. 조각: {이름, 약칭, 갈래, 파일, 쪽시작면, 목차[], 면수, 원본}."""
    문서들, 뒤문서들 = [], []
    for 문 in 설정.get("문서", []):
        항목 = 문.get("파일들") or [{"이름": 문["이름"], "파일": 문["파일"]}]
        무리 = []
        for k, h in enumerate(항목):
            f = 사건 / h["파일"]
            if not f.exists():
                raise SystemExit(f"없는 파일: {f}")
            src = fitz.open(f)
            조각 = {
                "이름": 문["이름"] if len(항목) == 1 else f"{문['이름']} · {h['이름']}",
                "단추": 문["이름"], "단추글": 문.get("단추"), "작은이름": h["이름"],
                "약칭": 문.get("약칭", 문["이름"][:2]) + (f"{k + 1}" if len(항목) > 1 else ""),
                "갈래": 문.get("갈래", "우리"), "파일": f, "원본": src, "면수": src.page_count,
                "쪽시작면": int(h.get("쪽시작면", 문.get("쪽시작면", 1))), "인용찾기": 문.get("인용찾기", 문.get("갈래", "우리") != "서류"),
            }
            조각["목차"] = 목차_만들기(문 if len(항목) == 1 else {**문, **h}, src, 사건, 경고) if (len(항목) == 1 or h.get("목차")) else []
            무리.append(조각)
        (뒤문서들 if 문.get("뒤") else 문서들).append(무리)
    증거무리 = []
    for g in 설정.get("증거", []):
        파일, 본 = [], set()
        for pat in g["파일들"]:
            for f in sorted(glob.glob(str(사건 / pat))):
                p = Path(f)
                if p.is_file() and not p.name.startswith("~$") and p.suffix.lower() not in (".md", ".json", ".txt", ".zip") and p.resolve() not in 본:
                    본.add(p.resolve())
                    파일.append(p)
        호증들 = []
        for p in 파일:
            h = 호증_이름(p)
            if not h:
                경고.append(f"{g['이름']}: 호증 이름을 읽지 못해 뺌 — {p.name}")
                continue
            h["파일"] = p
            호증들.append(h)
        빈도 = {}
        for h in 호증들:
            빈도[h["접두"]] = 빈도.get(h["접두"], 0) + 1
        순 = {p: i for i, (p, _) in enumerate(sorted(빈도.items(), key=lambda x: (x[0] == "참고자료", -x[1])))}
        호증들.sort(key=lambda h: (순[h["접두"]], h["번호"], h["가지"] or 0))
        이름들 = [h["이름"] for h in 호증들]
        for n in set(이름들):
            if 이름들.count(n) > 1:
                경고.append(f"{g['이름']}: 같은 호증 이름이 둘 이상 — {n}")
        조각들 = []
        for h in 호증들:
            p = h["파일"]
            확장 = p.suffix.lower()
            if 확장 == ".pdf":
                src = fitz.open(p)
                종류 = "pdf"
            elif 확장 in 그림확장:
                src = fitz.open()
                im = fitz.open(p)
                r = im[0].rect
                w, hh = (A4 if r.width <= r.height else (A4[1], A4[0]))
                pg = src.new_page(width=w, height=hh)
                pg.insert_image(pg.rect + (18, 18, -18, -18), filename=str(p))
                종류 = "그림"
            else:
                src = fitz.open()
                src.new_page(width=A4[0], height=A4[1])
                종류 = "파일"
            조각들.append({
                "이름": f"{h['이름']} {h['표제']}".strip(), "호증": h, "약칭": h["짧은"], "갈래": g.get("갈래", "우리"),
                "파일": p, "원본": src, "면수": src.page_count, "쪽시작면": 1, "목차": [], "종류": 종류, "인용찾기": False,
            })
        증거무리.append({"이름": g["이름"], "갈래": g.get("갈래", "우리"), "조각들": 조각들})
    return 문서들, 증거무리, 뒤문서들


# ── 인용 찾기 ──

_주인용 = re.compile(r"(노위|사|노|갑|을)\s*제\s*(\d+)\s*호증(?:\s*의\s*(\d+))?")
_이어 = re.compile(r"\s*(,|및|내지|~|～)\s*(?:(?:노위|사|노|갑|을)\s*)?(?:제\s*(\d+)\s*호증)?(?:\s*의\s*)?(\d+)?")


def 인용_목록(글: str) -> set:
    """'사 제6호증의1 내지 3', '사 제10호증 내지 제12호증', '사 제2호증의1, 2' 를 (접두, 번호, 가지|None) 묶음으로 푼다."""
    글 = re.sub(r"\s+", " ", 글)
    나옴 = set()
    for m in _주인용.finditer(글):
        p, n, s = m.group(1), int(m.group(2)), (int(m.group(3)) if m.group(3) else None)
        나옴.add((p, n, s))
        끝 = m.end()
        while True:
            c = _이어.match(글, 끝)
            if not c or (not c.group(2) and not c.group(3)):
                break
            잇, 주, 가 = c.group(1), c.group(2), c.group(3)
            if 주:
                n2 = int(주)
                if 잇 in ("내지", "~", "～") and n2 > n:
                    for k in range(n + 1, n2 + 1):
                        나옴.add((p, k, None))
                else:
                    나옴.add((p, n2, int(가) if 가 else None))
                n, s = n2, (int(가) if 가 else None)
            elif 가 and s is not None:
                k2 = int(가)
                if 잇 in ("내지", "~", "～") and k2 > s:
                    for k in range(s + 1, k2 + 1):
                        나옴.add((p, n, k))
                else:
                    나옴.add((p, n, k2))
                s = k2
            else:
                break
            끝 = c.end()
    return 나옴


# ── 그리기 ──

def 글(page, xy, 내용, 크기, kind="R", 색=글색):
    page.insert_text(xy, 내용, fontname="hpR" if kind == "R" else "hpB", fontsize=크기, color=색)


def 글꼴_넣기(page):
    page.insert_font(fontname="hpR", fontfile=글꼴["R"])
    page.insert_font(fontname="hpB", fontfile=글꼴["B"])


def 면이름_쓰기(doc, 이름들: list):
    """면 이름(/PageLabels)을 직접 쓴다. set_page_labels 는 한글 접두를 UTF-8 로 적어 보는 프로그램에서 깨진다(2026. 11. 3. 확인)."""
    def pdf글(s: str) -> str:
        return "<FEFF" + s.encode("utf-16-be").hex().upper() + ">"
    nums = []
    for e in sorted(이름들, key=lambda e: e["startpage"]):
        d = (f"/S/{e['style']}" if e.get("style") else "") + (f"/P{pdf글(e['prefix'])}" if e.get("prefix") else "")
        nums.append(f"{e['startpage']}<<{d}>>")
    doc.xref_set_key(doc.pdf_catalog(), "PageLabels", f"<</Nums[{' '.join(nums)}]>>")


def 링크(page, rect, 대상: int):
    page.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(rect), "page": 대상, "to": fitz.Point(0, 0), "zoom": 0})


def 단추(page, rect, 내용, 대상, 테, 바탕, 글자색=(1, 1, 1), 크기=8.5, kind="B"):
    rect = fitz.Rect(rect)
    page.draw_rect(rect, color=테, fill=바탕, width=0.6, radius=0.18)
    w = 폭(내용, 크기, kind)
    글(page, (rect.x0 + (rect.width - w) / 2, rect.y0 + rect.height / 2 + 크기 * 0.36), 내용, 크기, kind, 글자색)
    링크(page, rect, 대상)


def 그림_줄이기(doc, 목표dpi: int, 품질: int) -> tuple:
    """큰 스캔 그림을 목표 dpi 의 JPEG 로 다시 넣는다(아이패드에서 가볍게). 8비트 회색·RGB 그림만 다루고, 투명(SMask·Mask)·
    마스크·Decode 가 있는 그림, 흑백 팩스(CCITT)·JBIG2·JPX 는 그대로 둔다. 이미 JPEG 이고 해상도가 목표 이하인 그림도 그대로 둔다.
    PyMuPDF 의 rewrite_images 는 회색 ICC 스캔(FlateDecode)을 깨뜨려(2026. 11. 3. OES 사 제22호증 등에서 글자가 겹쳐 보임) 쓰지 않는다.
    끝난 뒤 `확인` 이 면마다 원본과 그림을 맞댄다."""
    import io
    from PIL import Image
    쓰임 = {}                                   # xref → (면, 그 그림이 가장 크게 그려진 곳의 dpi)
    for pno in range(doc.page_count):
        pg = doc[pno]
        for item in pg.get_images(full=True):
            x = item[0]
            if x in 쓰임 and 쓰임[x][1] <= 목표dpi:
                continue
            try:
                rects = pg.get_image_rects(x)
            except Exception:
                continue
            for r in rects:
                if r.is_empty or r.width < 1:
                    continue
                dpi = max(item[2] / (r.width / 72), item[3] / (r.height / 72))
                if x not in 쓰임 or dpi < 쓰임[x][1]:
                    쓰임[x] = (pno, dpi)
    바꾼, 전, 후 = 0, 0, 0
    for x, (pno, dpi) in 쓰임.items():
        def 값(k):
            return doc.xref_get_key(x, k)
        if 값("ImageMask")[1] == "true" or 값("SMask")[0] != "null" or 값("Mask")[0] != "null" or 값("Decode")[0] != "null":
            continue
        if 값("BitsPerComponent")[1] != "8":
            continue
        filt = 값("Filter")[1]
        if any(f in filt for f in ("CCITT", "JBIG2", "JPX")):
            continue
        if "DCT" in filt and dpi <= 목표dpi * 1.15:
            continue
        try:
            pix = fitz.Pixmap(doc, x)
        except Exception:
            continue
        if pix.alpha or pix.n not in (1, 3) or pix.width * pix.height < 250_000:
            continue
        원래 = len(doc.xref_stream_raw(x) or b"")
        배율 = min(1.0, 목표dpi / dpi)
        w, h = max(1, round(pix.width * 배율)), max(1, round(pix.height * 배율))
        im = Image.frombytes("L" if pix.n == 1 else "RGB", (pix.width, pix.height), pix.samples)
        if (w, h) != (pix.width, pix.height):
            im = im.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=품질, optimize=True)
        새 = buf.getvalue()
        if len(새) >= 원래 * 0.85:
            continue
        doc[pno].replace_image(x, stream=새)
        바꾼, 전, 후 = 바꾼 + 1, 전 + 원래, 후 + len(새)
    return 바꾼, 전, 후


# ── 묶기 ──

def 묶기(설정경로: Path):
    설정 = json.loads(설정경로.read_text(encoding="utf-8"))
    사건 = 사건_폴더(설정경로)
    출력 = 사건 / 설정["출력"]
    경고 = []
    문서들, 증거무리, 뒤문서들 = 조각_읽기(설정, 사건, 경고)
    순서 = [z for 무리 in 문서들 for z in 무리] + [z for g in 증거무리 for z in g["조각들"]] + [z for 무리 in 뒤문서들 for z in 무리]

    # 인용: 문서 조각의 글자층에서 호증 인용을 찾아 (조각, 원본 면) 을 모은다
    호증별 = {}
    for g in 증거무리:
        for z in g["조각들"]:
            h = z["호증"]
            호증별[(h["접두"], h["번호"], h["가지"])] = z
            z["인용"] = []
    for z in 순서:
        if not z.get("인용찾기"):
            continue
        멈춤 = False
        for i, pg in enumerate(z["원본"]):
            if 멈춤:
                break
            줄들 = pg.get_text().splitlines()
            for k, 줄 in enumerate(줄들):              # 입증방법·증명자료 목록부터는 인용으로 세지 않는다(모든 호증이 나열됨)
                if 빈칸없이(줄) in ("입증방법", "증명자료", "증거방법", "첨부서류"):
                    줄들, 멈춤 = 줄들[:k], True
                    break
            for (p, n, s) in 인용_목록("\n".join(줄들)):
                대상들 = [호증별[(p, n, s)]] if (p, n, s) in 호증별 else []
                if not 대상들 and s is None:
                    대상들 = [v for (pp, nn, ss), v in 호증별.items() if pp == p and nn == n]
                if not 대상들 and s is not None and (p, n, None) in 호증별:
                    대상들 = [호증별[(p, n, None)]]
                for v in 대상들:
                    if (id(z), i) not in {(id(a), b) for a, b in v["인용"]}:
                        v["인용"].append((z, i))

    # 앞 면 짜기: 1면(처음), 서면 목차 면들, 호증 면 목록 면들
    목차줄 = []                                   # (조각, 단계, 글, 원본면) — 문서 머리 줄은 단계 0
    for z in 순서:
        if z["목차"]:
            목차줄.append((z, 0, z["이름"], 0))
            for lv, t, p in z["목차"]:
                목차줄.append((z, lv, t, p))
    너비 = A4[0] - 2 * M
    목차면들, y, 지금 = [], M + 34, []
    for 줄 in 목차줄:
        z, lv, t, p = 줄
        if lv == 0:
            h = 21 + (8 if 지금 else 0)
        else:
            들여 = 14 * (lv - 1)
            줄들 = 줄나누기(t, 너비 - 들여 - 52, 9.2 if lv > 1 else 9.6, "R" if lv > 1 else "B")
            h = 13 * len(줄들) + 4
        if y + h > A4[1] - M and 지금:
            목차면들.append(지금)
            지금, y = [], M + 34
        지금.append((줄, y, h))
        y += h
    if 지금:
        목차면들.append(지금)

    호증줄 = [z for g in 증거무리 for z in g["조각들"]]
    목록면들, y, 지금 = [], M + 34, []
    for z in 호증줄:
        면단추 = z["면수"] if z["면수"] >= 2 else 0
        단추폭, 인용폭 = 21, 44
        오른 = 너비 - 168
        면줄 = -(-면단추 // max(1, int(오른 // (단추폭 + 3)))) if 면단추 else 0
        인용줄 = -(-len(z["인용"]) // max(1, int(오른 // (인용폭 + 3)))) if z["인용"] else 0
        h = max(30, 6 + 17 * (면줄 + 인용줄) + (4 if 면줄 and 인용줄 else 0))
        if y + h > A4[1] - M and 지금:
            목록면들.append(지금)
            지금, y = [], M + 34
        지금.append((z, y, h))
        y += h + 3
    if 지금:
        목록면들.append(지금)

    앞면수 = 1 + len(목차면들) + len(목록면들)
    out = fitz.open()
    for _ in range(앞면수):
        out.new_page(width=A4[0], height=A4[1])

    # 본 면 넣기(회전·상자가 단순하면 그대로 넣고 위 상자를 늘리고, 아니면 새 면에 놓는다)
    for z in 순서:
        z["시작"] = out.page_count
        src = z["원본"]
        단순 = all(pg.rotation == 0 and pg.mediabox == pg.cropbox and pg.mediabox.x0 == 0 and pg.mediabox.y0 == 0 for pg in src)
        if 단순:
            out.insert_pdf(src, links=True, annots=True)
            z["놓은방식"] = ["늘림"] * src.page_count
        else:
            z["놓은방식"] = []
            for i, pg in enumerate(src):
                if pg.rotation == 0 and pg.mediabox == pg.cropbox and pg.mediabox.x0 == 0 and pg.mediabox.y0 == 0:
                    out.insert_pdf(src, from_page=i, to_page=i, links=False, annots=True)
                    z["놓은방식"].append("늘림")
                else:
                    r = pg.rect
                    np_ = out.new_page(width=r.width, height=r.height + S)
                    np_.show_pdf_page(fitz.Rect(0, S, r.width, r.height + S), src, i)
                    z["놓은방식"].append("놓음")
    목차면_시작 = 1
    목록면_시작 = 1 + len(목차면들)
    목차면_자리 = {}
    for k, 면 in enumerate(목차면들):
        for (줄, y, h) in 면:
            if 줄[1] == 0:
                목차면_자리.setdefault(id(줄[0]), 목차면_시작 + k)
    목록면_자리 = {}
    for k, 면 in enumerate(목록면들):
        for (z, y, h) in 면:
            목록면_자리[id(z)] = 목록면_시작 + k

    def 쪽(z, i):                                  # 원본 면 i(0부터)의 인쇄 쪽 번호. 없으면 None
        n = i + 1 - (z["쪽시작면"] - 1)
        return n if n >= 1 else None

    def 위치글(z, i):
        if z.get("호증") is not None or z["갈래"] == "서류":
            return f"{i + 1}/{z['면수']}면"
        n = 쪽(z, i)
        return f"{n}쪽" if n else "표지"

    def 면이름(z, i):
        n = 쪽(z, i) if z.get("호증") is None else i + 1
        return f"{z['약칭']}-{n}" if n else f"{z['약칭']}-표지"

    # 띠 덧대기
    전체호증 = 호증줄
    for z in 순서:
        for i in range(z["면수"]):
            pg = out[z["시작"] + i]
            if z["놓은방식"][i] == "늘림":
                mb = pg.mediabox
                pg.set_mediabox(fitz.Rect(mb.x0, mb.y0, mb.x1, mb.y1 + S))
            W = pg.rect.width
            글꼴_넣기(pg)
            pg.draw_rect(fitz.Rect(0, 0, W, S), color=None, fill=(0.95, 0.96, 0.97))
            pg.draw_line((0, S - 0.4), (W, S - 0.4), color=남색, width=0.8)
            x = 5
            단추(pg, (x, 3.5, x + 50, S - 3.5), "◀ 처음", 0, 남색, 남색)
            x += 54
            if z.get("호증") is not None:
                단추(pg, (x, 3.5, x + 54, S - 3.5), "호증 목록", 목록면_자리.get(id(z), 0), 남색, (1, 1, 1), 남색)
                x += 58
                k = 전체호증.index(z)
                if k > 0:
                    단추(pg, (x, 3.5, x + 50, S - 3.5), "◀ 앞 호증", 전체호증[k - 1]["시작"], 남색, (1, 1, 1), 남색)
                x += 54
                if k + 1 < len(전체호증):
                    단추(pg, (x, 3.5, x + 54, S - 3.5), "다음 호증 ▶", 전체호증[k + 1]["시작"], 남색, (1, 1, 1), 남색)
                x += 58
            elif id(z) in 목차면_자리:
                단추(pg, (x, 3.5, x + 40, S - 3.5), "목차", 목차면_자리[id(z)], 남색, (1, 1, 1), 남색)
                x += 44
            위치 = 위치글(z, i)
            위치폭 = 폭(위치, 9, "B")
            글(pg, (W - 6 - 위치폭, S / 2 + 3.3), 위치, 9, "B", 남색)
            남은 = W - 6 - 위치폭 - 8 - (x + 4)
            이름 = z["이름"]
            if 폭(이름, 9, "B") > 남은:
                이름 = 줄나누기(이름, 남은, 9, "B", 최대=1)[0]
            글(pg, (x + 4, S / 2 + 3.3), 이름, 9, "B", 글색)

    # 1면(처음)
    pg = out[0]
    글꼴_넣기(pg)
    y = M + 16
    글(pg, (M, y), 설정.get("제목", "심문회의 자료"), 15.5, "B", 남색)
    y += 15
    글(pg, (M, y), 설정.get("부제", ""), 9, "R", 흐린글)
    y += 12
    글(pg, (M, y), "단추를 누르면 그 첫 면으로 갑니다. 어느 면에서든 위 띠의 '◀ 처음'을 누르면 이 면으로 돌아옵니다.", 8, "R", 흐린글)
    y += 12
    단추들 = []
    for 무리 in 문서들 + 뒤문서들:
        z = 무리[0]
        단추들.append((z.get("단추글") or z["단추"], z["시작"], z["갈래"]))
    단추들.append(("서면 목차", 목차면_시작, "목차"))
    if 목록면들:
        단추들.append(("호증 면 목록", 목록면_시작, "목차"))
    열 = 5
    bw, bh, gap = (너비 - (열 - 1) * 6) / 열, 32, 6
    for k, (이름, 대상, 갈래) in enumerate(단추들):
        r, c = divmod(k, 열)
        rect = fitz.Rect(M + c * (bw + gap), y + r * (bh + gap), M + c * (bw + gap) + bw, y + r * (bh + gap) + bh)
        테, 바탕 = (남색, (1, 1, 1)) if 갈래 == "목차" else (색[갈래][0], 색[갈래][0])
        글자색 = 남색 if 갈래 == "목차" else (1, 1, 1)
        pg.draw_rect(rect, color=테, fill=바탕, width=1.0, radius=0.15)
        줄들 = [t for 부분 in 이름.split("\n") for t in 줄나누기(부분, bw - 10, 9, "B")][:2]
        yy = rect.y0 + rect.height / 2 - (len(줄들) - 1) * 5.5 + 3.2
        for t in 줄들:
            글(pg, (rect.x0 + (bw - 폭(t, 9, "B")) / 2, yy), t, 9, "B", 글자색)
            yy += 11
        링크(pg, rect, 대상)
    y += (-(-len(단추들) // 열)) * (bh + gap) + 2
    갈래설명 = [("내부", "내부 자료"), ("우리", "우리 서면"), ("상대", "상대 서면"), ("서류", "심문회의 서류")]
    xx = M
    for g, t in 갈래설명:
        if any(d[2] == g for d in 단추들):
            pg.draw_rect(fitz.Rect(xx, y + 1, xx + 9, y + 8), color=None, fill=색[g][0], radius=0.2)
            글(pg, (xx + 12, y + 7.6), t, 7.5, "R", 흐린글)
            xx += 16 + 폭(t, 7.5) + 10
    y += 16
    열 = 5
    줄수 = sum(-(-len(g["조각들"]) // 열) for g in 증거무리)
    남은높이 = (A4[1] - M) - y - 24 * len(증거무리)
    th = max(30.0, min(54.0, 남은높이 / 줄수 - 5)) if 줄수 else 40.0      # 남는 높이만큼 호증 단추를 키운다(누르기 쉽게)
    for g in 증거무리:
        테, 바탕 = 상대호증색 if g["갈래"] == "상대" else 색["우리"]
        글(pg, (M, y + 10), f"{g['이름']}", 11, "B", 테)
        글(pg, (M + 폭(g["이름"], 11, "B") + 6, y + 10), f"{len(g['조각들'])}개 · 누르면 그 호증 첫 면", 7.5, "R", 흐린글)
        y += 16
        tw, gap = (너비 - (열 - 1) * 5) / 열, 5
        for k, z in enumerate(g["조각들"]):
            r, c = divmod(k, 열)
            rect = fitz.Rect(M + c * (tw + gap), y + r * (th + gap), M + c * (tw + gap) + tw, y + r * (th + gap) + th)
            pg.draw_rect(rect, color=테, fill=바탕, width=0.8, radius=0.12)
            h = z["호증"]
            위 = rect.y0 + max(0.0, (th - 40) / 2)                         # 단추가 커지면 글을 가운데로
            글(pg, (rect.x0 + 5, 위 + 12.5), h["이름"], 10 if th >= 44 else 9.5, "B", 테)
            면 = f"{z['면수']}면" if z["종류"] == "pdf" else ("그림" if z["종류"] == "그림" else z["파일"].suffix.lower().lstrip("."))
            글(pg, (rect.x1 - 4 - 폭(면, 6.5), rect.y0 + 11.5), 면, 6.5, "R", 흐린글)
            for j, t in enumerate(줄나누기(h["표제"] or "", tw - 10, 7.2, "R", 최대=2)):
                글(pg, (rect.x0 + 5, 위 + 24 + j * 9.2), t, 7.2, "R", 글색)
            링크(pg, rect, z["시작"])
        y += (-(-len(g["조각들"]) // 열)) * (th + gap) + 8
    if y > A4[1] - M + 4:
        경고.append(f"1면이 넘침(y={y:.0f}) — 호증이 많으면 단추 크기를 줄이도록 도구를 고친다")

    # 서면 목차 면
    for k, 면 in enumerate(목차면들):
        pg = out[목차면_시작 + k]
        글꼴_넣기(pg)
        글(pg, (M, M + 16), "서면 목차" + (f" ({k + 1}/{len(목차면들)})" if len(목차면들) > 1 else ""), 15, "B", 남색)
        단추(pg, (A4[0] - M - 62, M + 2, A4[0] - M, M + 22), "◀ 처음", 0, 남색, 남색)
        for (줄, y, h) in 면:
            z, lv, t, p = 줄
            if lv == 0:
                yy = y + (8 if h > 21 else 0)
                rect = fitz.Rect(M, yy, A4[0] - M, yy + 18)
                테 = 색[z["갈래"]][0]
                pg.draw_rect(rect, color=None, fill=테, radius=0.12)
                글(pg, (M + 6, yy + 12.6), z["이름"], 10, "B", (1, 1, 1))
                끝 = f"{z['면수']}면"
                글(pg, (A4[0] - M - 6 - 폭(끝, 8.5), yy + 12.4), 끝, 8.5, "R", (1, 1, 1))
                링크(pg, rect, z["시작"])
                continue
            들여 = 14 * (lv - 1)
            kind, 크기 = ("B", 9.6) if lv == 1 else ("R", 9.2)
            줄들 = 줄나누기(t, 너비 - 들여 - 52, 크기, kind)
            for j, s in enumerate(줄들):
                글(pg, (M + 6 + 들여, y + 11 + j * 13), s, 크기, kind, 글색)
            n = 쪽(z, p)
            끝 = f"{n}쪽" if n else "표지"
            글(pg, (A4[0] - M - 4 - 폭(끝, 8.5), y + 11), 끝, 8.5, "R", 흐린글)
            pg.draw_line((M + 6 + 들여, y + h - 1), (A4[0] - M, y + h - 1), color=(0.88, 0.89, 0.91), width=0.4)
            링크(pg, fitz.Rect(M, y, A4[0] - M, y + h), z["시작"] + p)

    # 호증 면 목록
    for k, 면 in enumerate(목록면들):
        pg = out[목록면_시작 + k]
        글꼴_넣기(pg)
        머리 = "호증 면 목록" + (f" ({k + 1}/{len(목록면들)})" if len(목록면들) > 1 else "")
        글(pg, (M, M + 16), 머리, 15, "B", 남색)
        글(pg, (M + 폭(머리, 15, "B") + 10, M + 15), "숫자: 그 호증의 면 · '답1-12' 같은 단추: 그 호증을 인용한 서면의 쪽", 7.5, "R", 흐린글)
        단추(pg, (A4[0] - M - 62, M + 2, A4[0] - M, M + 22), "◀ 처음", 0, 남색, 남색)
        for (z, y, h) in 면:
            h_ = z["호증"]
            테, 바탕 = 상대호증색 if z["갈래"] == "상대" else 색["우리"]
            rect = fitz.Rect(M, y, M + 160, y + h)
            pg.draw_rect(rect, color=테, fill=바탕, width=0.6, radius=0.08)
            글(pg, (M + 5, y + 12), h_["이름"], 9.2, "B", 테)
            for j, t in enumerate(줄나누기(h_["표제"] or "", 150, 7, "R", 최대=max(1, int((h - 16) // 9)))):
                글(pg, (M + 5, y + 22 + j * 9), t, 7, "R", 글색)
            링크(pg, rect, z["시작"])
            x0, x, yy = M + 168, M + 168, y + 3
            if z["면수"] >= 2:
                for i in range(z["면수"]):
                    if x + 21 > A4[0] - M:
                        x, yy = x0, yy + 17
                    단추(pg, (x, yy, x + 21, yy + 14), str(i + 1), z["시작"] + i, 테, (1, 1, 1), 테, 7.5, "B")
                    x += 24
                x, yy = x0, yy + 17 + 4
            for (dz, i) in z["인용"]:
                이름 = 면이름(dz, i)
                w = max(44, 폭(이름, 7.5, "B") + 8)
                if x + w > A4[0] - M:
                    x, yy = x0, yy + 17
                c = 색[dz["갈래"]][0]
                단추(pg, (x, yy, x + w, yy + 14), 이름, dz["시작"] + i, c, c, (1, 1, 1), 7.5, "B")
                x += w + 3

    # 파일 호증(녹음·영상 등)의 자리 면과 복사
    for z in 호증줄:
        if z.get("종류") == "파일":
            pg = out[z["시작"]]
            글꼴_넣기(pg)
            글(pg, (60, S + 120), z["이름"], 16, "B", 남색)
            글(pg, (60, S + 150), f"PDF 로 볼 수 없는 파일입니다({z['파일'].suffix.lower()}).", 11, "R", 글색)
            글(pg, (60, S + 170), f"같은 폴더의 '호증 파일/{z['파일'].name}' 을 여십시오.", 11, "R", 글색)
            대상 = 출력.parent / "호증 파일"
            대상.mkdir(parents=True, exist_ok=True)
            shutil.copy2(z["파일"], 대상 / z["파일"].name)

    # 면 이름과 책갈피
    이름들 = [{"startpage": 0, "prefix": "처음", "style": "", "firstpagenum": 1}]
    if 목차면들:
        이름들.append({"startpage": 목차면_시작, "prefix": "목차-", "style": "D", "firstpagenum": 1})
    if 목록면들:
        이름들.append({"startpage": 목록면_시작, "prefix": "호증목록-", "style": "D", "firstpagenum": 1})
    for z in 순서:
        if z.get("호증") is None and z["쪽시작면"] > 1:
            이름들.append({"startpage": z["시작"], "prefix": f"{z['약칭']}-표지", "style": "", "firstpagenum": 1})
            if z["면수"] >= z["쪽시작면"]:
                이름들.append({"startpage": z["시작"] + z["쪽시작면"] - 1, "prefix": f"{z['약칭']}-", "style": "D", "firstpagenum": 1})
        else:
            이름들.append({"startpage": z["시작"], "prefix": f"{z['약칭']}-", "style": "D", "firstpagenum": 1})
    면이름_쓰기(out, 이름들)

    toc = [[1, "처음(단추판)", 1]]
    if 목차면들:
        toc.append([1, "서면 목차", 목차면_시작 + 1])
    if 목록면들:
        toc.append([1, "호증 면 목록", 목록면_시작 + 1])

    def 문서_책갈피(무리):
        z0 = 무리[0]
        toc.append([1, z0["단추"], z0["시작"] + 1])
        for z in 무리:
            if len(무리) > 1:
                toc.append([2, z["작은이름"], z["시작"] + 1])
            앞 = 2 if len(무리) == 1 else 3
            for lv, t, p in z["목차"]:
                단계 = min(앞 + lv - 1, toc[-1][0] + 1)
                toc.append([단계, t, z["시작"] + p + 1])
    for 무리 in 문서들:
        문서_책갈피(무리)
    for g in 증거무리:
        if g["조각들"]:
            toc.append([1, g["이름"], g["조각들"][0]["시작"] + 1])
            for z in g["조각들"]:
                toc.append([2, z["이름"], z["시작"] + 1])
    for 무리 in 뒤문서들:
        문서_책갈피(무리)
    out.set_toc(toc)

    if 설정.get("그림"):
        g = 설정["그림"]
        바꾼, 전, 후 = 그림_줄이기(out, int(g.get("dpi", 200)), int(g.get("품질", 80)))
        print(f"그림 다시 압축: {바꾼}개, {전 / 1e6:.1f}MB → {후 / 1e6:.1f}MB")
    out.subset_fonts()
    출력.parent.mkdir(parents=True, exist_ok=True)
    out.save(출력, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True)
    기록 = {
        "앞면": 앞면수, "목차면": len(목차면들), "호증목록면": len(목록면들),
        "조각": [{"이름": z["이름"], "파일": str(z["파일"].relative_to(사건)), "시작": z["시작"] + 1, "면수": z["면수"],
                  "놓은방식": sorted(set(z["놓은방식"])), "인용": len(z.get("인용", []))} for z in 순서],
    }
    (출력.parent / (출력.stem + "_만든기록.json")).write_text(json.dumps(기록, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"만듦: {출력.relative_to(사건)} ({out.page_count}면, {출력.stat().st_size / 1e6:.1f}MB)")
    print(f"앞 면 {앞면수}(처음 1, 서면 목차 {len(목차면들)}, 호증 면 목록 {len(목록면들)}) · 문서 조각 {sum(len(m) for m in 문서들 + 뒤문서들)} · "
          f"호증 {len(호증줄)} · 목차 줄 {sum(len(z['목차']) for z in 순서)} · 책갈피 {len(toc)}")
    인용됨 = sum(1 for z in 호증줄 if z["인용"])
    print(f"인용 쪽을 찾은 호증 {인용됨}/{len(호증줄)}")
    for w in 경고:
        print("경고:", w)
    return 출력, 순서, 앞면수


def 확인(설정경로: Path) -> int:
    """만든 PDF 를 다시 열어 본 면마다 띠 아래가 원본과 같은지(그림), 링크가 면 안을 가리키는지, 책갈피·면 이름이 있는지 본다."""
    설정 = json.loads(설정경로.read_text(encoding="utf-8"))
    사건 = 사건_폴더(설정경로)
    출력 = 사건 / 설정["출력"]
    기록 = json.loads((출력.parent / (출력.stem + "_만든기록.json")).read_text(encoding="utf-8"))
    from PIL import ImageChops
    d = fitz.open(출력)
    문제 = 0
    다른면 = []
    손실 = bool(설정.get("그림"))
    최대평균 = 0.0
    for z in 기록["조각"]:
        src_p = 사건 / z["파일"]
        if src_p.suffix.lower() != ".pdf":
            continue
        src = fitz.open(src_p)
        for i in range(z["면수"]):
            # 면 전체를 72dpi(1pt=1화소)로 그린 뒤 위 띠(S 화소)를 잘라 원본과 맞댄다. 잘라 그리면 보간 차이가 생긴다.
            a = src[i].get_pixmap(dpi=72).pil_image().convert("L")
            b = d[z["시작"] - 1 + i].get_pixmap(dpi=72).pil_image().convert("L")
            b = b.crop((0, S, b.width, b.height))
            w, h = min(a.width, b.width), min(a.height, b.height)
            if abs(a.width - b.width) > 1 or abs(a.height - b.height) > 1:
                다른면.append((z["이름"], i + 1, "크기"))
                continue
            hist = ImageChops.difference(a.crop((0, 0, w, h)), b.crop((0, 0, w, h))).histogram()
            합 = sum(hist)
            평균 = sum(k * v for k, v in enumerate(hist)) / 합
            큰차 = sum(hist[80:] if 손실 else hist[41:]) / 합
            최대평균 = max(최대평균, 평균)
            if (손실 and (평균 > 6 or 큰차 > 0.01)) or (not 손실 and 큰차 > 0.001):
                다른면.append((z["이름"], i + 1, f"평균 {평균:.1f}, 큰 차이 {큰차:.2%}"))
    링크수, 바깥 = 0, 0
    for pg in d:
        for l in pg.get_links():
            if l.get("kind") == fitz.LINK_GOTO:
                링크수 += 1
                if not (0 <= l.get("page", -1) < d.page_count):
                    바깥 += 1
    toc = d.get_toc()
    이름 = [d[i].get_label() for i in (0, min(1, d.page_count - 1), d.page_count - 1)]
    print(f"확인: {출력.name} {d.page_count}면, {출력.stat().st_size / 1e6:.1f}MB")
    print(f"- 원본과 그림이 다른 본 면: {len(다른면)}" + ("" if not 다른면 else " → " + "; ".join(f"{a} {b}면({c})" for a, b, c in 다른면[:10]))
          + f" (그림 다시 압축 {'함' if 손실 else '안 함'}, 면별 평균 차이 최대 {최대평균:.2f}/255)")
    print(f"- 면 안으로 가는 링크 {링크수}, 면 밖을 가리키는 링크 {바깥}")
    print(f"- 책갈피 {len(toc)}, 면 이름 예: {이름}")
    문제 = len(다른면) + 바깥 + (0 if toc else 1)
    return 1 if 문제 else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="심문회의 자료를 아이패드용 한 PDF 로 묶는다")
    ap.add_argument("설정", type=Path)
    ap.add_argument("--확인", action="store_true", help="다시 만들지 않고 만든 PDF 만 맞댄다")
    a = ap.parse_args(argv)
    if not a.확인:
        묶기(a.설정)
    return 확인(a.설정)


if __name__ == "__main__":
    sys.exit(main())
