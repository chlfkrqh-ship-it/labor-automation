#!/usr/bin/env python3
"""노동사건 자동화 — 입력 폴더를 지켜보다가 계산표를 만든다.

    python watch.py                     한 번 훑고 끝 (기본)
    python watch.py --loop              10초마다 계속 지켜봄
    python watch.py --root D:\\다른폴더

폴더 구조 (없으면 만든다. 기본 위치는 6_손해배상계산 폴더 자신)

    6_손해배상계산/
      00_양식/     입력서.xlsx  <- 이걸 복사해서 채운다
      01_입력/     채운 입력서(.xlsx)나 사건 파일(.yaml)을 여기 넣는다
      02_결과/     계산표가 여기 나온다 ({사건번호}({성명})_계산표 또는 _노동금액계산표_{처리 시각}.xlsx)
      03_보관/     처리한 입력 파일이 여기로 옮겨진다 (이름 뒤에 처리 시각)
      99_오류/     처리 실패한 파일과 사유

처리하는 동안 입력 파일은 01_입력/처리중/ 에 옮겨 둔다. 엑셀에서 열려 있어 옮길 수 없으면
닫을 때까지 건너뛴다. 이 옮기기는 같은 PC 안에서만 잠금 역할을 하므로 감시는 한 PC에서만 켠다.
계산이 끝난 뒤 보관 이동이 실패하면 경고만 남기고 오류로 적지 않는다.

전부 로컬에서 돈다. 사건 자료가 밖으로 나가지 않는다.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path

from cli import is_labor_yaml, load_injury, run_injury, run_labor, utf8_console
from engine.inputform import make_template, read_form

SUB = ["00_양식", "01_입력", "02_결과", "03_보관", "99_오류"]
SUFFIXES = {".xlsx", ".xlsm", ".yaml", ".yml"}
CLAIM = "처리중"            # 01_입력 안. 처리하는 동안 입력 파일을 옮겨 두는 곳
_BUSY: set[str] = set()     # 열려 있어 옮기지 못한 파일. 같은 안내를 회차마다 되풀이하지 않는다


def ensure_root(root: Path) -> Path:
    for name in SUB:
        (root / name).mkdir(parents=True, exist_ok=True)
    form = root / "00_양식" / "입력서.xlsx"
    if not form.exists():
        make_template(form)
        print(f"  입력서 양식 생성: {form}")
    return root


def _unique(path: Path) -> Path:
    """같은 이름이 있으면 _2, _3 … 을 붙인다. 앞 사건의 파일을 덮어쓰지 않는다."""
    cand, n = path, 2
    while cand.exists():
        cand = path.with_name(f"{path.stem}_{n}{path.suffix}")
        n += 1
    return cand


def _move(src: Path, dst: Path) -> Path | None:
    """src 를 dst 로 옮긴다. 실패해도 감시를 멈추지 않고 경고만 남긴다."""
    try:
        return Path(shutil.move(str(src), str(_unique(dst))))
    except OSError as exc:
        print(f"  [경고] {src.name} 을(를) {dst.parent.name} 로 옮기지 못했습니다: {exc}")
        return None


def _claim(path: Path) -> Path | None:
    """처리 전에 입력 파일을 01_입력/처리중/ 으로 옮겨 가져온다. 가져오지 못하면 None.

    - 엑셀 등이 열고 있어 옮길 수 없으면(Windows) 이번 회차는 건너뛴다. 읽기만 하고 보관으로
      옮기지 못하면 다음 회차에 또 계산해 결과가 겹치기 때문이다.
    - 이미 없으면(다른 감시가 먼저 가져감) 조용히 넘어간다.
    """
    work = _unique(path.parent / CLAIM / path.name)
    try:
        work.parent.mkdir(exist_ok=True)
        os.rename(path, work)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if path.name not in _BUSY:
            _BUSY.add(path.name)
            print(f"  [대기] {path.name}: 옮길 수 없어 건너뜁니다({exc}). 엑셀에서 열려 있으면 닫아 주십시오.")
        return None
    _BUSY.discard(path.name)
    return work


def recover(root: Path) -> int:
    """지난번 감시가 처리 도중 멈춰 01_입력/처리중/ 에 남은 파일을 01_입력 으로 되돌린다."""
    claim = root / "01_입력" / CLAIM
    n = 0
    if claim.is_dir():
        for p in sorted(claim.iterdir()):
            if p.is_file() and _move(p, root / "01_입력" / p.name):
                print(f"  처리하다 멈춘 파일을 01_입력 으로 되돌렸습니다: {p.name}")
                n += 1
    return n


def _label(case_no: str, name: str, stem: str) -> str:
    """결과 파일 이름 앞부분. {사건번호}({성명}), 없으면 입력 파일 이름.

    파일 이름에 쓸 수 없는 글자(Windows 기준)는 _ 로 바꾼다.
    """
    base = case_no or stem
    label = f"{base}({name})" if name else base
    return re.sub(r'[\\/:*?"<>|\r\n\t]', "_", label).strip()


def process(path: Path, root: Path, stamp: str | None = None) -> Path:
    """입력 파일 하나를 계산표로 바꾼다."""
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    if is_labor_yaml(path):
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        label = _label(str(raw.get("case_no") or ""), str(raw.get("name") or ""), path.stem)
        return run_labor(path, _unique(root / "02_결과" / f"{label}_노동금액계산표_{stamp}.xlsx"))
    # 생년월일·사고일자 검사: 사건 파일은 load_injury, 입력서는 read_form(strict=True) 가 한다.
    case = load_injury(path) if path.suffix.lower() in (".yaml", ".yml") else read_form(path, strict=True)
    label = _label(case.case_no, case.name, path.stem)
    return run_injury(case, _unique(root / "02_결과" / f"{label}_계산표_{stamp}.xlsx"))


def _record_error(root: Path, path: Path, exc: Exception, stamp: str) -> None:
    """99_오류 에 사유를 적는다. except 블록 안에서 부른다(traceback 을 함께 남긴다)."""
    print(f"  [오류] {path.name}: {exc}")
    err = _unique(root / "99_오류" / f"{path.stem}_{stamp}.txt")
    try:
        err.write_text(
            f"파일: {path.name}\n시각: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
            f"{exc}\n\n---\n{traceback.format_exc()}",
            encoding="utf-8",
        )
    except OSError as werr:
        print(f"  [경고] 오류 사유를 기록하지 못했습니다: {werr}")
        return
    print(f"    -> {err.name}")


def scan_once(root: Path) -> int:
    inbox = root / "01_입력"
    done = 0
    for path in sorted(inbox.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if path.name.startswith("~$"):        # 엑셀 임시파일
            continue
        work = _claim(path)
        if work is None:
            continue
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        kept = f"{path.stem}_{stamp}{path.suffix}"     # 같은 이름의 앞 사건 입력을 덮어쓰지 않는다
        try:
            process(work, root, stamp)
        except Exception as exc:
            _record_error(root, path, exc, stamp)
            _move(work, root / "99_오류" / kept)
            continue
        # 계산은 끝났다. 보관 이동이 실패해도 오류로 적지 않는다(결과는 02_결과 에 있다).
        _move(work, root / "03_보관" / kept)
        done += 1
    return done


def main() -> None:
    utf8_console()
    ap = argparse.ArgumentParser(description="노동사건 손해배상 계산 자동화")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent), help="작업 폴더 (기본: 6_손해배상계산 폴더 자신)")
    ap.add_argument("--loop", action="store_true", help="계속 지켜보기")
    ap.add_argument("--interval", type=int, default=10, help="확인 간격(초), 기본 10")
    args = ap.parse_args()

    root = ensure_root(Path(args.root).expanduser().resolve())
    print(f"작업 폴더: {root}")
    print(f"입력 폴더: {root / '01_입력'}\n")
    recover(root)

    if not args.loop:
        n = scan_once(root)
        print(f"\n{n}건 처리했습니다." if n else "\n처리할 파일이 없습니다.")
        return

    print("지켜보는 중입니다. Ctrl+C 로 종료합니다.\n")
    try:
        while True:
            try:
                scan_once(root)
            except Exception:
                # 예상하지 못한 오류로 감시 창이 닫히지 않게 한다. 다음 회차에 다시 훑는다.
                traceback.print_exc()
                print("  [경고] 이번 회차를 끝내지 못했습니다. 다음 회차에 다시 확인합니다.")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
