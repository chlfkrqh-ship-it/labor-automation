"""의뢰인 문서에 남긴 메모·변경 내용 추적의 작성자를 '법무법인 평안'으로 맞춘다.

Word·한글로 메모를 달거나 고치면 프로그램이 그 PC의 사용자 이름(담당자 개인 이름)을 작성자로 넣는다. 검토본·서면에
다는 메모는 개인 이름이 아니라 법인 이름이 보여야 하므로(2026. 10. 16. 담당 노무사 지시), 넘기기 전에 이 스크립트로
이번에 새로 생긴 메모·변경의 작성자를 바꾼다. 원본(의뢰인이 보낸 문서, 서면은 그 판을 만들기 전의 담당자 저장본·직전 판)에
원래 있던 메모·변경은 이름이 같아도 하나하나 맞대어 가려내고 그대로 둔다. 절차는 루트 CLAUDE.md 와 1_검토의견/CLAUDE.md 3-5.

    python -B 공통/scripts/memo_author.py "{검토본}" --원본 "{의뢰인이 보낸 원본·바탕 문서}"
    python -B 공통/scripts/memo_author.py "{검토본}" --원본 "{원본}" --확인           # 바꾸지 않고 보기만
    python -B 공통/scripts/memo_author.py "{검토본}" --원본 "{원본}" --개인 "홍길동"   # 원본에 든 우리 쪽 이전 메모도

- Word(.docx): 메모·변경의 작성자(w:author)와 메모 머리글자(w:initials), 계정 정보(word/people.xml 의 개인 이름·메일),
  문서 속성의 '마지막으로 수정한 사람'(docProps/core.xml)을 고친다.
- 한글(.hwpx): 메모 작성자(메모 칸의 Author), 변경 추적 작성자 목록(Contents/header.xml 의 trackChangeAuthor),
  '마지막 저장한 사람'(Contents/content.hpf 의 lastsaveby)을 고친다.
- 한글(.hwp): Windows 에서 한글 자동화로 hwpx 로 저장해 고친 뒤 다시 hwp 로 저장한다. 한글이 다시 저장하면서
  '마지막 저장한 사람'에 이 PC의 사용자 이름을 넣을 수 있다.
- 파일은 제자리에서 고친다. Word·한글에서 열려 있으면 닫고 다시 실행한다. 본문 글자는 건드리지 않는다.

종료 코드: 0 문제 없음(고쳤거나 고칠 것이 없음), 1 오류, 2 --확인에서 바꿀 작성자가 남아 있음.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FIRM, INITIALS = '법무법인 평안', '평안'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
W15 = '{http://schemas.microsoft.com/office/word/2012/wordml}'
CP = '{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}'
INSTALL = 'python -m pip install -r 공통/requirements.txt'


class MemoError(Exception):
    pass


def etree():
    try:
        from lxml import etree as et
    except ImportError:
        raise MemoError(f'lxml 이 없습니다. {INSTALL} 로 설치한 뒤 다시 실행하십시오.') from None
    return et


def parse(data: bytes):
    et = etree()
    return et.fromstring(data, et.XMLParser(resolve_entities=False, huge_tree=True))


def dump(root, before: bytes) -> bytes:
    standalone = True if b'standalone="yes"' in before[:200] else None
    return etree().tostring(root, xml_declaration=True, encoding='UTF-8', standalone=standalone)


def local(tag) -> str:
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def read_zip(path: Path) -> tuple[list[zipfile.ZipInfo], dict[str, bytes]]:
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            return infos, {i.filename: z.read(i.filename) for i in infos}
    except zipfile.BadZipFile:
        raise MemoError(f'{path.name} 을(를) 문서로 읽지 못했습니다(압축 형식이 아님).') from None


def write_zip(path: Path, infos: list[zipfile.ZipInfo], parts: dict[str, bytes]) -> None:
    """항목 순서와 압축 방식을 그대로 두고 다시 쓴다(hwpx 는 첫 항목 mimetype 이 무압축이어야 한다)."""
    part = path.with_name(path.name + '.part')
    with zipfile.ZipFile(part, 'w') as z:
        for info in infos:
            z.writestr(info, parts[info.filename])
    try:
        os.replace(part, path)
    except PermissionError:
        part.unlink(missing_ok=True)
        raise MemoError(f'{path.name} 이(가) 열려 있어 바꾸지 못했습니다. Word·한글에서 닫고 다시 실행하십시오.') from None


class Plan:
    """무엇을 바꾸는지. 원본(바탕 문서)에 없던 메모·변경과 --개인 으로 지목한 작성자의 것을 법인 이름으로 바꾼다.

    이름이 아니라 메모·변경 하나하나를 원본과 맞댄다. 서면은 담당자가 직접 단 메모가 든 저장본 위에서 다시 고치는
    일이 많아, 담당자의 메모와 이번에 Word 가 같은 사용자 이름으로 넣은 메모가 섞이기 때문이다. 일시가 있으면
    '누가·언제'(분 단위)로 맞댄다. 새로 단 것은 언제나 지금 시각이고, Word 가 다시 저장하며 원래 수정 표시를 여러
    조각으로 나누거나 합쳐도 누가·언제는 그대로이기 때문이다. 일시가 없으면 종류·작성자·글이 같은 것을 하나씩 지워 가며 맞춘다.
    """

    def __init__(self, before: Counter, pairs: set, personal=(), name: str = FIRM):
        self.before, self.pairs, self.personal, self.name = Counter(before), set(pairs), set(personal), name
        self.renamed = Counter()                        # (옛 이름, 종류) → 개수
        self.kept = Counter()
        self.initials = 0                               # 작성자는 이미 법인 이름인데 머리글자만 고친 메모

    def decide(self, key, author: str, kind: str, when: str = '') -> str:
        """'rename'(바꾼다), 'keep'(원본에 있던 것), 'firm-new'·'firm-old'(이미 법인 이름)."""
        if when:
            matched = (author, minute(when)) in self.pairs
        else:
            matched = self.before[key] > 0
            if matched:
                self.before[key] -= 1
        if author == self.name:
            return 'firm-old' if matched else 'firm-new'
        if matched and author not in self.personal:
            self.kept[(author, kind)] += 1
            return 'keep'
        self.renamed[(author, kind)] += 1
        return 'rename'

    def decide_name(self, author: str, kind: str, theirs: set[str]) -> str:
        """하나하나 가를 수 없는 자리(한글 변경 추적 작성자 목록 등)는 이름으로 가른다."""
        if author == self.name:
            return 'firm-old'
        if author in theirs and author not in self.personal:
            self.kept[(author, kind)] += 1
            return 'keep'
        self.renamed[(author, kind)] += 1
        return 'rename'


def minute(value: str) -> str:
    """일시를 분 단위로(Word 는 초를 버리고, 프로그램마다 'Z'·소수 초 표기가 다르다)."""
    try:
        moment = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        return value.strip()
    if moment.tzinfo:
        moment = moment.astimezone(timezone.utc)
    return moment.strftime('%Y-%m-%dT%H:%M')


# ── Word ──

TEXT = (W + 't', W + 'delText', W + 'instrText', W + 'delInstrText')


def docx_xml_parts(parts: dict[str, bytes]) -> list[str]:
    return [n for n in parts if n.startswith('word/') and n.endswith('.xml') and n != 'word/people.xml']


def docx_key(el) -> tuple:
    """메모·변경을 원본과 맞댈 열쇠: 종류, 작성자, 일시, 안의 글."""
    return (local(el.tag), el.get(W + 'author') or '', el.get(W + 'date') or '', ''.join(t.text or '' for t in el.iter(*TEXT)))


def docx_index(parts: dict[str, bytes]) -> tuple[Counter, set]:
    keys, pairs = Counter(), set()
    for name in docx_xml_parts(parts):
        for el in parse(parts[name]).iter():
            author = el.get(W + 'author')
            if author:
                keys[docx_key(el)] += 1
                if el.get(W + 'date'):
                    pairs.add((author, minute(el.get(W + 'date'))))
    return keys, pairs


def last_modified_by(parts: dict[str, bytes]):
    if 'docProps/core.xml' not in parts:
        return None, None
    root = parse(parts['docProps/core.xml'])
    return root, root.find(CP + 'lastModifiedBy')


def fix_docx(parts: dict[str, bytes], original: dict[str, bytes], plan: Plan, apply: bool) -> tuple[list[str], dict]:
    changed, notes, gone, still = {}, [], set(), set()
    for name in docx_xml_parts(parts):
        root, touched = parse(parts[name]), False
        for el in root.iter():
            author = el.get(W + 'author')
            if not author:
                continue
            kind = '메모' if el.tag == W + 'comment' else '변경'
            state = plan.decide(docx_key(el), author, kind, el.get(W + 'date') or '')
            if state == 'rename':
                el.set(W + 'author', plan.name)
                gone.add(author)
                touched = True
            if kind == '메모' and state in ('rename', 'firm-new') and el.get(W + 'initials') != INITIALS:
                el.set(W + 'initials', INITIALS)
                plan.initials += state == 'firm-new'
                touched = True
            still.add(el.get(W + 'author'))
        if touched:
            changed[name] = dump(root, parts[name])
    if 'word/people.xml' in parts:
        root = parse(parts['word/people.xml'])
        drop = [p for p in root.iter(W15 + 'person') if p.get(W15 + 'author') in gone - still]
        for p in drop:
            p.getparent().remove(p)
        if drop:
            changed['word/people.xml'] = dump(root, parts['word/people.xml'])
            notes.append('Word 계정 정보(people.xml)에서 개인 이름·메일 ' + ', '.join(p.get(W15 + 'author') for p in drop) + ' 을(를) 지움')
    core, last = last_modified_by(parts)
    _, before = last_modified_by(original)
    if last is not None and last.text and last.text != plan.name \
            and (last.text != (before.text if before is not None else None) or last.text in plan.personal):
        notes.append(f"문서 속성의 '마지막으로 수정한 사람' {last.text} → {plan.name}")
        last.text = plan.name
        changed['docProps/core.xml'] = dump(core, parts['docProps/core.xml'])
    if plan.initials:
        notes.append(f'메모 머리글자 {plan.initials}개 → {INITIALS}')
    if apply:
        parts.update(changed)
    return notes, changed


# ── 한글(hwpx) ──

def hwpx_xml_parts(parts: dict[str, bytes]) -> list[str]:
    return [n for n in parts if n.startswith('Contents/') and n.endswith(('.xml', '.hpf'))]


def memo_box(el) -> bool:
    name = local(el.tag)
    return (name == 'fieldBegin' and (el.get('type') or '').upper() == 'MEMO') or name in ('memo', 'memogroup')


def hwpx_slots(root):
    """작성자가 든 자리: (요소, 속성 이름 또는 None=글자, 종류, 가르는 법 'one'=하나하나 원본과 맞댐·'name'=이름으로)."""
    for el in root.iter():
        name = local(el.tag)
        if name == 'trackChangeAuthor' and el.get('name') is not None:
            yield el, 'name', '변경', 'name'
        if el.get('name') == 'Author' and any(memo_box(a) for a in el.iterancestors()):
            yield el, None, '메모', 'one'              # 메모 칸의 <hp:stringParam name="Author">
        for key in el.attrib:
            if local(key).lower() == 'author':          # 모양을 모르는 다른 작성자 칸
                yield el, key, '메모', 'name'
        if name == 'meta' and el.get('name') == 'lastsaveby':
            yield el, None, '저장', 'name'


def slot_value(el, attr):
    return el.get(attr) if attr else (el.text or '')


def memo_key(author_el) -> tuple:
    """한글 메모를 원본과 맞댈 열쇠: 작성자, 만든 일시, 메모 글."""
    box = next((a for a in author_el.iterancestors() if memo_box(a)), None)
    created = text = ''
    if box is not None:
        created = next((p.text or '' for p in box.iter() if p.get('name') == 'CreateDateTime'), '')
        text = ''.join(t.text or '' for t in box.iter() if local(t.tag) == 't')
    return ('memo', author_el.text or '', created, text)


def hwpx_index(parts: dict[str, bytes]) -> tuple[Counter, set]:
    keys = Counter(memo_key(el) for n in hwpx_xml_parts(parts) for el, _, _, how in hwpx_slots(parse(parts[n])) if how == 'one')
    return keys, {(k[1], minute(k[2])) for k in keys if k[2]}


def fix_hwpx(parts: dict[str, bytes], original: dict[str, bytes], plan: Plan, apply: bool) -> tuple[list[str], dict]:
    changed, notes = {}, []
    by_name = [(slot_value(el, attr), kind) for n in hwpx_xml_parts(original)
               for el, attr, kind, how in hwpx_slots(parse(original[n])) if how == 'name']
    names = {v for v, kind in by_name if kind != '저장'}
    saved = {v for v, kind in by_name if kind == '저장'}
    for name in hwpx_xml_parts(parts):
        root, touched = parse(parts[name]), False
        for el, attr, kind, how in hwpx_slots(root):
            value = slot_value(el, attr)
            if not value:
                continue
            if kind == '저장':
                if value != plan.name and (value not in saved or value in plan.personal):
                    notes.append(f"'마지막 저장한 사람' {value} → {plan.name}")
                    el.text = plan.name
                    touched = True
                continue
            if how == 'one':
                key = memo_key(el)
                state = plan.decide(key, value, kind, key[2])
            else:
                state = plan.decide_name(value, kind, names)
            if state == 'rename':
                if attr:
                    el.set(attr, plan.name)
                else:
                    el.text = plan.name
                touched = True
        if touched:
            changed[name] = dump(root, parts[name])
    if apply:
        parts.update(changed)
    return notes, changed


# ── 한글(.hwp): 한글 자동화로 hwpx 를 거친다 ──

def hwp_app():
    try:
        import win32com.client as win32
    except ImportError:
        raise MemoError('한글(.hwp)은 Windows 의 한글 자동화로만 바꿉니다(pywin32). 한글에서 hwpx 로 저장해 넘기십시오.') from None
    hwp = win32.DispatchEx('HWPFrame.HwpObject')
    if not hwp.RegisterModule('FilePathCheckDLL', 'FilePathCheckerModuleExample'):
        print('[주의] 보안 모듈이 등록되지 않아 파일 접근 창이 뜰 수 있습니다(뜨면 모두 허용).')
    if hwp.XHwpDocuments.Count != 1:
        hwp.Quit()
        raise MemoError('새 한글 창이 아닙니다.')
    return hwp


def convert(src: Path, dst: Path) -> None:
    """한글로 열어 다른 형식으로 저장한다(hwp ↔ hwpx). 이미 떠 있는 한글 창은 쓰지 않는다."""
    fmt = {'.hwp': 'HWP', '.hwpx': 'HWPX'}
    hwp = hwp_app()
    try:
        if not hwp.Open(str(src), fmt[src.suffix.lower()], 'forceopen:true'):
            raise MemoError(f'한글이 {src.name} 을(를) 열지 못했습니다.')
        hwp.SaveAs(str(dst), fmt[dst.suffix.lower()], '')
    finally:
        hwp.Clear(1)
        hwp.Quit()
    if not dst.is_file():
        raise MemoError(f'한글이 {dst.suffix} 로 저장하지 못했습니다: {src.name}')


# ── 실행 ──

BODY = ('word/document.xml', 'word/footnotes.xml', 'word/endnotes.xml')


def leftovers(parts: dict[str, bytes], names) -> list[str]:
    """본문 밖(문서 속성·계정 정보·머리 정보 등)에 개인 이름이 글자 그대로 남은 부분. 본문은 이름이 내용일 수 있어 보지 않는다."""
    names = [n.encode('utf-8') for n in names if n]
    skip = lambda n: n in BODY or n.startswith(('word/header', 'word/footer', 'Contents/section', 'Preview/'))
    return sorted(n for n, data in parts.items() if not skip(n) and any(x in data for x in names))


def report(path: Path, plan: Plan, notes: list[str], apply: bool) -> int:
    print(f'{"작성자 정리" if apply else "작성자 확인"}: {path.name}')
    olds = sorted({old for old, _ in plan.renamed})
    for old in olds:
        parts = ', '.join(f'{kind} {n}개' for (o, kind), n in sorted(plan.renamed.items()) if o == old)
        print(f"  {old} → {plan.name}  ({parts})" if apply else f'  바꿀 작성자  {old}  ({parts})')
    for (who, kind), n in sorted(plan.kept.items()):
        print(f'  그대로  {who}  ({kind} {n}개, 원본에 원래 있던 것)')
    for note in notes:
        print(f'  {note}' if apply else f'  바꿀 것  {note}')
    if not plan.renamed and not notes:
        print(f'  바꿀 작성자가 없습니다(새 메모·변경의 작성자가 모두 {plan.name}).')
        return 0
    return 0 if apply else 2


def run(path: Path, original: Path, personal=(), check: bool = False, name: str = FIRM) -> int:
    return process(Path(path), Path(original), personal, check, name)[0]


def process(path: Path, original: Path, personal=(), check: bool = False, name: str = FIRM) -> tuple[int, bool]:
    """(종료 코드, 파일을 바꿨는지)."""
    for p in (path, original):
        if not p.is_file():
            raise MemoError(f'파일이 없습니다: {p}')
    kind = path.suffix.lower()
    if kind == '.hwp':
        with tempfile.TemporaryDirectory() as tmp:
            review_x, original_x = Path(tmp) / 'review.hwpx', Path(tmp) / 'original.hwpx'
            convert(path, review_x)
            if original.suffix.lower() == '.hwpx':
                shutil.copyfile(original, original_x)
            else:
                convert(original, original_x)
            code, changed = process(review_x, original_x, personal, check, name)
            if changed:
                back = Path(tmp) / 'back.hwp'
                convert(review_x, back)
                part = path.with_name(path.name + '.part')
                shutil.copyfile(back, part)
                try:
                    os.replace(part, path)
                except PermissionError:
                    part.unlink(missing_ok=True)
                    raise MemoError(f'{path.name} 이(가) 열려 있어 바꾸지 못했습니다. 한글에서 닫고 다시 실행하십시오.') from None
                print("  한글(.hwp)로 다시 저장했습니다. '마지막 저장한 사람'에는 이 PC의 사용자 이름이 들어갈 수 있습니다.")
            return code, changed
    if kind not in ('.docx', '.hwpx'):
        raise MemoError(f'Word(.docx)와 한글(.hwpx·.hwp)만 다룹니다: {path.name}')
    if original.suffix.lower() != kind:
        raise MemoError(f'검토본과 원본의 형식이 다릅니다({path.suffix}, {original.suffix}). 같은 형식의 원본을 넘기십시오.')
    infos, parts = read_zip(path)
    _, before = read_zip(original)
    index, fix = (docx_index, fix_docx) if kind == '.docx' else (hwpx_index, fix_hwpx)
    plan = Plan(*index(before), personal, name)
    notes, changed = fix(parts, before, plan, apply=not check)
    if not check and changed:
        write_zip(path, infos, parts)
    gone = {old for old, _ in plan.renamed} - {who for who, _ in plan.kept}      # 원래 메모로 남은 이름은 빼고 본다
    rest = leftovers(parts, gone | plan.personal) if not check else []
    if rest:
        notes = notes + ['본문 밖에 개인 이름이 남은 부분(눈으로 확인): ' + ', '.join(rest)]
    return report(path, plan, notes, apply=not check), bool(changed) and not check


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', type=Path, help='의뢰인에게 넘길 검토본(.docx·.hwpx·.hwp)')
    parser.add_argument('--원본', dest='original', type=Path, required=True, help='의뢰인이 보낸 원본(의뢰인이 남긴 메모·변경을 가려낸다)')
    parser.add_argument('--확인', dest='check', action='store_true', help='바꾸지 않고 바꿀 것이 남았는지만 본다')
    parser.add_argument('--개인', dest='personal', action='append', default=[],
                        help='원본에 있어도 바꿀 작성자(우리 쪽이 전에 개인 이름으로 남긴 메모·변경). 여러 번 줄 수 있다')
    args = parser.parse_args(argv)
    try:
        return run(args.path, args.original, args.personal, args.check)
    except MemoError as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
