# -*- coding: utf-8 -*-
"""서류를 담당자가 고른 프린터로 인쇄한다. 절차는 `공통/운영.md` '인쇄'.

    python -B 공통/scripts/print_docs.py printers
    python -B 공통/scripts/print_docs.py print --프린터 "{프린터 이름}" [--부수 N] "{파일}" ["{파일}" …]
    python -B 공통/scripts/print_docs.py print --프린터 "{프린터 이름}" --파일로 "{폴더}" "{파일}" …

형식마다 인쇄하는 길이 다르다.
- .hwp/.hwpx: 한글 자동화로 원본을 그대로 인쇄한다(한글에서 인쇄 단추를 누른 것과 같다). 메모·누름틀 안내문은 한글 기본값대로 인쇄하지 않는다.
- .docx/.doc: Word 자동화로 원본을 그대로 인쇄한다. Word 안의 프린터만 바꾸고 시스템 기본 프린터는 바꾸지 않는다
  (`WordBasic.FilePrintSetup` 에 DoNotSetAsSysDefault. 이 함수는 이름 붙은 인자를 받지 못해 순서대로 넘긴다).
- .pdf: 이 PC에는 PDF 를 명령으로 인쇄할 프로그램이 없어(PDF 기본 앱이 엣지) 면을 그림으로 그려 GDI 로 보낸다.
  글자가 있는 면은 프린터 해상도(최대 600dpi), 글자가 없는 스캔 면은 300dpi 로 그리고, 실제 크기(100%)로 놓는다.
  면이 용지보다 크면 줄여 맞추고, 가로 면을 세로 용지에 낼 때에는 돌린다.
  LibreOffice(`sdraw.exe -pt`)도 PDF 를 인쇄하지만 PDF 를 다시 그려 글꼴·배치가 바뀔 수 있어 쓰지 않는다.

- 원본은 OneDrive 밖 임시 폴더에 복사해 연다(열린 파일·동기화와 부딪치지 않게).
- `--파일로` 는 종이 없이 그 프린터 드라이버의 출력 파일(.prn)을 만든다. 도구·문서를 시험할 때 쓴다.
- 인쇄 뒤 그 프린터의 대기열을 보고 남은 작업을 알린다. 종이로 나왔는지는 담당자가 본다.

2026. 10. 28. 이승민 질병판정위원회 출석 서류를 PDF 를 그려 인쇄한 뒤 담당자 지시("인쇄 방식은 개선 필요가 있군", "지침에 넣지 모")로 만들었다.
"""
import argparse
import os
import shutil
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")

VIRTUAL_PORTS = ("nul:", "PORTPROMPT:", "SHRFAX:", "PPP:", "Hancom PDF Port", "PG108G:", "FILE:", "XPSPort:")
VIRTUAL_WORDS = ("PDF", "XPS", "OneNote", "Fax")
WORK_OFFLINE = 0x400


class PrintError(Exception):
    pass


def printer_rows():
    import win32print
    try:
        default = win32print.GetDefaultPrinter()
    except Exception:
        default = ""
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    rows = []
    for p in win32print.EnumPrinters(flags, None, 2):
        name, port, driver = p["pPrinterName"], p["pPortName"] or "", p["pDriverName"] or ""
        virtual = port.startswith(VIRTUAL_PORTS) or any(w.lower() in (name + driver).lower() for w in VIRTUAL_WORDS) \
            or port.startswith("Microsoft.Office.OneNote")
        rows.append({"name": name, "port": port, "driver": driver, "default": name == default,
                     "offline": bool(p["Attributes"] & WORK_OFFLINE), "virtual": virtual, "jobs": p["cJobs"]})
    rows.sort(key=lambda r: (r["virtual"], not r["default"], r["name"]))
    return rows


def cmd_printers(_a):
    for r in printer_rows():
        tags = [t for t, on in (("기본", r["default"]), ("가상", r["virtual"]), ("오프라인", r["offline"])) if on]
        print("%s%s · 포트 %s · 대기 %d건" % (r["name"], " [%s]" % ", ".join(tags) if tags else "", r["port"], r["jobs"]))


# ── 한글 ──────────────────────────────────────────────

def print_hwp(path, printer, copies, out):
    import win32com.client as win32
    hwp = win32.DispatchEx("HWPFrame.HwpObject")
    if not hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleExample"):
        print("[주의] 한글 보안 모듈이 등록되지 않아 파일 접근 창이 뜰 수 있습니다(뜨면 모두 허용).")
    if hwp.XHwpDocuments.Count != 1:
        hwp.Quit()
        raise PrintError("새 한글 창이 아닙니다. 열려 있는 한글을 닫고 다시 하십시오.")
    try:
        fmt = "HWPX" if path.lower().endswith(".hwpx") else "HWP"
        if not hwp.Open(path, fmt, "forceopen:true"):
            raise PrintError("한글이 파일을 열지 못했습니다: " + os.path.basename(path))
        pages = hwp.PageCount
        p = hwp.HParameterSet.HPrint
        hwp.HAction.GetDefault("Print", p.HSet)
        p.PrinterName = printer
        p.NumCopy = copies
        p.Collate = 1
        p.Range = 0                      # 문서 전체
        if out:
            p.PrintToFile = 1
            p.filename = out
        if not hwp.HAction.Execute("Print", p.HSet):
            raise PrintError("한글 인쇄가 실행되지 않았습니다: " + os.path.basename(path))
        return pages
    finally:
        hwp.Clear(1)
        hwp.Quit()


# ── Word ──────────────────────────────────────────────

def print_word(path, printer, copies, out):
    import pythoncom
    import win32com.client as win32
    from win32com.client import dynamic
    app = dynamic.Dispatch(pythoncom.CoCreateInstanceEx("Word.Application", None, pythoncom.CLSCTX_LOCAL_SERVER, None,
                                                         (pythoncom.IID_IDispatch,))[0])
    before = app.Documents.Count
    old_printer = app.ActivePrinter
    wb = dynamic.Dispatch(app._oleobj_.Invoke(app._oleobj_.GetIDsOfNames("WordBasic"), 0,
                                              pythoncom.DISPATCH_PROPERTYGET, True))
    wb._FlagAsMethod("FilePrintSetup")
    missing = win32.VARIANT(pythoncom.VT_ERROR, -2147352572)       # DISP_E_PARAMNOTFOUND: 넘기지 않은 인자

    def set_printer(name):
        # 순서: .Printer, .Options(단추), .Network(단추), .DoNotSetAsSysDefault — 단추 자리는 비워 둔다
        wb.FilePrintSetup(name, missing, missing, 1)

    doc = None
    try:
        app.DisplayAlerts = 0
        doc = app.Documents.Open(path, False, True)               # ConfirmConversions=False, ReadOnly=True
        pages = doc.ComputeStatistics(2)                          # wdStatisticPages
        set_printer(printer)
        # PrintOut 도 순서대로 넘긴다. 이름 붙은 인자로 넘기면 PrintToFile·OutputFileName 이 무시되어 파일 대신 종이로 나갔다(2026. 10. 28. 시험).
        # 순서: Background, Append, Range(0 전체), OutputFileName, From, To, Item(0 본문), Copies, Pages, PageType(0 모든 쪽), PrintToFile, Collate
        doc.PrintOut(False, False, 0, out if out else missing, missing, missing, 0, copies, missing, 0, bool(out), True)
        return pages
    finally:
        if doc is not None:
            doc.Close(0)
        try:
            set_printer(old_printer)
        finally:
            if before == 0 and app.Documents.Count == 0:
                app.Quit(0)


# ── PDF ───────────────────────────────────────────────

def print_pdf(path, printer, copies, out, name):
    import pymupdf
    import win32con
    import win32ui
    from PIL import Image, ImageWin
    doc = pymupdf.open(path)
    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(printer)
    try:
        g = dc.GetDeviceCaps
        dpi_x, dpi_y = g(win32con.LOGPIXELSX), g(win32con.LOGPIXELSY)
        paper_w, paper_h = g(win32con.PHYSICALWIDTH), g(win32con.PHYSICALHEIGHT)          # 장치 점
        off_x, off_y = g(win32con.PHYSICALOFFSETX), g(win32con.PHYSICALOFFSETY)
        area_w, area_h = g(win32con.HORZRES), g(win32con.VERTRES)
        if out:
            dc.StartDoc(name, out)
        else:
            dc.StartDoc(name)
        for _ in range(copies):
            for page in doc:
                dpi = min(max(dpi_x, dpi_y), 600) if page.get_text().strip() else 300
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                pw, ph = page.rect.width / 72, page.rect.height / 72                         # 인치
                if (pw > ph) != (paper_w > paper_h):
                    img = img.transpose(Image.Transpose.ROTATE_90)
                    pw, ph = ph, pw
                w, h = pw * dpi_x, ph * dpi_y
                if w > paper_w + dpi_x * 0.08 or h > paper_h + dpi_y * 0.08:                # 2mm 넘게 크면 인쇄 영역에 맞춰 줄임
                    k = min(area_w / w, area_h / h)
                    w, h = w * k, h * k
                    x, y = (area_w - w) / 2, (area_h - h) / 2
                else:                                                                        # 실제 크기, 용지 가운데
                    x, y = (paper_w - w) / 2 - off_x, (paper_h - h) / 2 - off_y
                dc.StartPage()
                ImageWin.Dib(img).draw(dc.GetHandleOutput(), (round(x), round(y), round(x + w), round(y + h)))
                dc.EndPage()
        dc.EndDoc()
        return doc.page_count
    finally:
        dc.DeleteDC()


# ── 실행 ──────────────────────────────────────────────

def queue_jobs(printer):
    import win32print
    h = win32print.OpenPrinter(printer)
    try:
        return [j["pDocument"] for j in win32print.EnumJobs(h, 0, 999, 1)]
    finally:
        win32print.ClosePrinter(h)


def cmd_print(a):
    names = {r["name"]: r for r in printer_rows()}
    if a.프린터 not in names:
        raise PrintError("그 이름의 프린터가 없습니다: %s (목록은 printers)" % a.프린터)
    if names[a.프린터]["offline"]:
        print("[주의] 오프라인으로 표시된 프린터입니다:", a.프린터)
    files = [os.path.abspath(f) for f in a.파일]
    for f in files:
        if not os.path.isfile(f):
            raise PrintError("파일이 없습니다: " + f)
        if os.path.splitext(f)[1].lower() not in (".hwp", ".hwpx", ".docx", ".doc", ".pdf"):
            raise PrintError("인쇄하지 않는 형식입니다(hwp·hwpx·docx·doc·pdf): " + os.path.basename(f))
    if a.파일로:
        os.makedirs(a.파일로, exist_ok=True)
    work = tempfile.mkdtemp(prefix="print_docs_", dir=os.path.join(os.environ["LOCALAPPDATA"], "Temp"))
    try:
        for i, f in enumerate(files, 1):
            base = os.path.basename(f)
            stem, ext = os.path.splitext(base)
            ext = ext.lower()
            copy = os.path.join(work, "%02d%s" % (i, ext))            # 한글·Word 가 긴 한글 경로에서 막히지 않게 짧은 이름으로
            shutil.copyfile(f, copy)
            out = os.path.join(os.path.abspath(a.파일로), base + ".prn") if a.파일로 else None    # 같은 이름의 hwp·pdf 가 겹치지 않게 확장자까지
            if out and os.path.exists(out):
                os.remove(out)
            if ext in (".hwp", ".hwpx"):
                pages, how = print_hwp(copy, a.프린터, a.부수, out), "한글 원본"
            elif ext in (".docx", ".doc"):
                pages, how = print_word(copy, a.프린터, a.부수, out), "Word 원본"
            else:
                pages, how = print_pdf(copy, a.프린터, a.부수, out, base), "PDF 그림(글자 면 600dpi·스캔 면 300dpi)"
            print("보냄 %d. %s — %s, %d면 × %d부%s" % (i, base, how, pages, a.부수,
                                                    " → " + out if out else ""))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if a.파일로:
        time.sleep(2)
        for f in files:
            out = os.path.join(os.path.abspath(a.파일로), os.path.basename(f) + ".prn")
            size = os.path.getsize(out) if os.path.exists(out) else 0
            print("파일 %s %s바이트" % (os.path.basename(out), format(size, ",")))
        return
    left = []
    for _ in range(10):                      # 대기열이 빌 때까지 최대 20초
        time.sleep(2)
        left = queue_jobs(a.프린터)
        if not left:
            break
    if left:
        print("[주의] 대기열에 남은 작업 %d건: %s" % (len(left), ", ".join(left)))
    else:
        print("대기열이 비었습니다(프린터로 넘어감). 종이로 나왔는지는 프린터에서 확인하십시오.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("printers")
    s = sub.add_parser("print")
    s.add_argument("--프린터", required=True, help="printers 목록의 이름 그대로")
    s.add_argument("--부수", type=int, default=1)
    s.add_argument("--파일로", help="종이 대신 이 폴더에 드라이버 출력 파일(.prn)을 만든다")
    s.add_argument("파일", nargs="+")
    a = ap.parse_args()
    try:
        cmd_printers(a) if a.cmd == "printers" else cmd_print(a)
    except PrintError as e:
        print("[멈춤]", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
