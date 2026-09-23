"""서면 초안의 문체를 실측한다.

`4_서면작성/skills/노동서면작성/SKILL.md` 의 '저장 전 자가 점검' 가운데 아직
스크립트가 없던 항목(금지 낱말, 접속부사 뒤 쉼표, 3문장 이상 문단, 대괄호 메모,
본문 해라체)과 `4_서면작성/CLAUDE.md` 2-2절의 제출처별 대리인 표기를 기계로 센다.
규칙을 새로 만들지 않고 그 문서들에 적힌 것만 검사한다.

    python 4_서면작성/scripts/style_check.py 출력/서면초안.md
    python 4_서면작성/scripts/style_check.py "출력/(의뢰인명) 서면명_초안.docx" --json

`위반` 이 하나라도 있으면 종료 코드 1을 낸다. `참고` 는 세어서 보여 줄 뿐이며
판단을 대신하지 않는다. 사람이 그 자리를 열어 보고 정한다.

md 초안의 `[[각주: …]]` 는 판결 원문을 옮기는 자리이므로(docx_footnotes.py) 금지 낱말·
대괄호 메모·문장 수·해라체 검사에서 뺀다.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('workflow_system', ROOT / '공통/scripts/system.py')
_system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_system)

# '첫째·둘째·셋째' 는 문단을 나누는 열거('둘째,' '둘째로')만 잡는다. '둘째 자녀', '매월 첫째 주'는 사실이다.
BANNED = re.compile(
    r'뒷받침|국가기관인|객관적으로 확인|우선,|먼저,|다음으로,|마지막으로,'
    r'|(?<![가-힣])(?:첫째|둘째|셋째)(?:\s*,|로(?![가-힣]))'
    r'|살피건대|생각건대|요컨대|할 것입니다|다름 아|알 수 있습니다|입증합니다'
    r'|증명합니다|방증|예상됩니다|본건|금번|재판장님|한자\(|（')
# '사료됩니다' 는 루트 CLAUDE.md 의 완충 종결 예시이면서 서면 스킬이 피하라고 한 표현이라
# 위반으로 막지 않고 참고로만 센다. 평가·전망을 맺는 자리인지 사람이 보고 정한다.
HEDGE = re.compile(r'사료')
# 접속부사 뒤 쉼표. 낱말이 이어지면('가사근로자', '한편으로') 접속부사가 아니다. '가사'(假使)는
# '-더라도·-ㄹ지라도' 같은 양보 어미와 함께 쓰일 때만 접속부사로 본다('가사 사용인'은 법령 용어다).
CONJUNCTION = re.compile(r'^(그러나|따라서|또한|다만|한편|그리고)(?![,가-힣])'
                         r'|^(가사)(?![,가-힣])(?=.*(?:라도|여도|해도))')
# 대괄호 메모. 증거 캡션·대괄호 인용의 자료명('사실확인서', '경력확인원')과 사건명('해고무효확인
# 판결')에 든 '확인'은 메모가 아니다. '[갑 제3호증 원본 확인 필요]'는 메모로 잡는다.
MEMO = re.compile(r'\[[^\]]*(?:확인(?!\s*(?:서|원|판결|결정|청구|소송|의\s*소))|보완|필요)[^\]]*\]|【[^】]*】')
FOOTNOTE = re.compile(r'\[\[각주:.*?\]\]', re.S)
# 문장 끝: '다.' 또는 증거·판례 인용 괄호를 마침표 앞에 둔 '다(…).' '다[…].'(references/증거-인용.md).
# 소괄호 안의 소괄호는 한 겹까지 받는다.
_END = r'다(?:\s*(?:\([^()]*(?:\([^()]*\)[^()]*)*\)|\[[^\[\]]*\]))?\.'
SENTENCE = re.compile(_END)
# 해라체: 하십시오체는 모두 '니다.' 또는 '니다(인용).'로 끝나므로 그 밖의 문장 끝을 잡는다.
PLAIN = re.compile(r'(?<!니)' + _END + r'(?:\s|$)')
# 개요 기호('가. ', '다. ')는 문장 끝이 아니다.
OUTLINE = re.compile(r'^[가-하]\.\s')
# 증거 인용으로 끝나는 사실 문단 뒤에는 지시 접속어로 시작하는 평가 문단이 온다.
# 호증 표기는 공통/scripts/system.py 의 정의를 쓴다('갑 제2, 3호증' 같은 병기 포함).
CITED = re.compile(r'(?:\([^()]*?(?:' + _system.EVIDENCE_NUMBER + r')[^()]*\)'
                   r'|\[[^\[\]]*?(?:' + _system.EVIDENCE_NUMBER + r')[^\[\]]*\])\s*\.?\s*$')
# 발췌 캡션 한 줄('[갑 제8호증 징계처분사유설명서]')은 사실 문단이 아니다.
CAPTION = re.compile(r'^\[[^\[\]]*\]$')
POINTER = ('이처럼', '이와 같이', '이에 따를 때', '이러한', '이는', '특히', '무엇보다',
           '오히려', '앞서', '상술한', '그럼에도', '따라서', '결국',
           '이상과 같이', '가사', '백번', '위와 같은', '구체적으로', '나아가', '즉',
           '더욱이', '그러나', '한편', '또한', '다만')
NESTED = re.compile(r'\([^()]*\([^()]*\)[^()]*\)')
# 제출처('… 귀중' 줄)로 절차를 가른다. 본문에서 노동위원회 판정을 인용하는 것과 다르다.
VENUE_LABOR = re.compile(r'노동위원회\s*귀중')
LITIGATION_AGENT = re.compile(r'소송대리인')
SKIP_LINE = re.compile(r'^\s*(#|\||```|>|\d+\.\s*$)')
RULE_LINE = re.compile(r'^\s*-{3,}\s*$')
# references/문체-용례.md '실측치' (변호사 최종본 111문단 150문장)
REFERENCE = {'sentence_chars_mean': 97, 'sentence_chars_median': 89,
             'one_sentence_ratio': 82}


def prose(text):
    """문장 검사에 쓰는 글. 각주 표시와 첫머리 개요 기호를 걷어 낸다."""
    return OUTLINE.sub('', FOOTNOTE.sub('', text).strip(), count=1)


def split_sentences(text):
    """문장 끝(SENTENCE)마다 자른다. 인용 괄호는 앞 문장에 붙는다."""
    parts, start = [], 0
    for m in SENTENCE.finditer(text):
        parts.append(text[start:m.end()].strip())
        start = m.end()
    return [p for p in parts if p]


def median(values):
    if not values:
        return 0
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (ordered[middle] if len(ordered) % 2
            else round((ordered[middle - 1] + ordered[middle]) / 2, 1))


def paragraphs(path: Path):
    """(시작 행번호, 본문, 본문여부) 목록. 제목·표·인용·코드는 제외한다.

    MD 하단의 보완 메모는 제출용 본문이 아니므로 부속으로 표시한다. 공통/운영.md 에
    따라 보완 메모는 MD 하단에만 두고 DOCX 본문에는 넣지 않기 때문이다.
    """
    if path.suffix.lower() == '.docx':
        import docx
        return [(i + 1, p.text.strip(), True)
                for i, p in enumerate(docx.Document(str(path)).paragraphs)
                if p.text.strip() and not p.style.name.startswith(('Heading', '제목'))]
    lines = path.read_text(encoding='utf-8-sig').split('\n')
    result, buffer, start, body = [], [], 0, True
    for number, line in enumerate(lines, 1):
        if RULE_LINE.match(line) and number > 1:
            if buffer:
                result.append((start, ' '.join(buffer), body))
                buffer = []
            body = False          # 이 아래는 보완 메모로 본다
            continue
        if not line.strip() or SKIP_LINE.match(line):
            if buffer:
                result.append((start, ' '.join(buffer), body))
                buffer = []
            continue
        if not buffer:
            start = number
        buffer.append(line.strip())
    if buffer:
        result.append((start, ' '.join(buffer), body))
    return result


def cover_texts(path: Path):
    """표지와 서명 블록까지 포함한 문단별 글자. 본문 실측에는 쓰지 않는다.

    python-docx 의 paragraph.text 는 표 칸과 누름틀(내용 컨트롤) 안을 지나치므로
    제출처·대리인 표기는 document.xml 을 직접 읽는다. md 초안에는 표지가 없다.
    """
    if path.suffix.lower() != '.docx':
        return []
    import xml.etree.ElementTree as ET
    import zipfile
    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
    found = []
    for number, para in enumerate(root.iter(w + 'p'), 1):
        text = ''.join(node.text or '' for node in para.iter(w + 't')).strip()
        if text:
            found.append((number, text))
    return found


def check(path: Path):
    blocks = paragraphs(path)
    violations, notes = [], []

    def add(target, rule, line, text, detail=''):
        target.append({'rule': rule, 'line': line,
                       'detail': detail, 'text': text[:70]})

    previous_cited = False
    for line, text, body in blocks:
        if not body:                      # 보완 메모는 제출용 본문이 아니다
            previous_cited = False
            continue
        own = FOOTNOTE.sub('', text)      # 각주에 옮긴 판결 원문은 문체 검사 대상이 아니다
        sentences = prose(text)
        for hit in set(BANNED.findall(own)):
            add(violations, '금지 낱말', line, text, hit)
        conjunction = CONJUNCTION.match(own)
        if conjunction:
            add(violations, '접속부사 뒤 쉼표 없음', line, text,
                conjunction[1] or conjunction[2])
        for hit in set(m[0] for m in MEMO.finditer(own)):
            add(violations, '대괄호 메모 잔존', line, text, hit[:30])
        if HEDGE.search(own):
            add(notes, '사료 종결', line, text, HEDGE.search(own)[0])

        count = len(SENTENCE.findall(sentences))
        if count >= 3:
            add(notes, '3문장 이상 문단', line, text, '%d문장' % count)
        plain = PLAIN.search(sentences)
        if plain:
            add(notes, '해라체 종결', line, text, plain[0].strip())
        if previous_cited and not text.startswith(POINTER):
            add(notes, '증거 인용 뒤 평가 문단에 지시 접속어 없음', line, text)
        if NESTED.search(own):
            add(notes, '괄호 안 내부 소괄호', line, text,
                NESTED.search(own)[0][:40])
        previous_cited = bool(CITED.search(own.strip())) and not CAPTION.match(own.strip())

    # 제출처가 노동위원회인 서면에는 '소송대리인'을 쓰지 않는다(4_서면작성/CLAUDE.md 2-2절).
    # 노동위원회에는 공인노무사도 대리인으로 선임되기 때문이다.
    cover = cover_texts(path)
    if any(VENUE_LABOR.search(text) for _, text in cover):
        seen = set()
        for number, text in cover:
            if LITIGATION_AGENT.search(text) and text not in seen:
                seen.add(text)
                add(violations, '노동위 서면에 소송대리인', number, text, "'대리인'으로 고친다")

    body_text = [prose(t) for _, t, body in blocks if body]
    lengths = [len(s) for t in body_text for s in split_sentences(t)]
    per_paragraph = [len(SENTENCE.findall(t)) for t in body_text if SENTENCE.search(t)]
    one = sum(1 for n in per_paragraph if n == 1)
    measured = {
        'sentence_chars_mean': round(sum(lengths) / len(lengths), 1) if lengths else 0,
        'sentence_chars_median': median(lengths),
        'one_sentence_ratio': round(one / len(per_paragraph) * 100, 1) if per_paragraph else 0,
        'reference': REFERENCE,
    }
    if lengths and measured['sentence_chars_mean'] > REFERENCE['sentence_chars_mean'] * 1.5:
        notes.append({'rule': '문장이 기준보다 김', 'line': '-',
                      'detail': '평균 %.0f자 (기준 %d자)' % (measured['sentence_chars_mean'],
                                                        REFERENCE['sentence_chars_mean']),
                      'text': '문장을 나누지 말고 한 문단에 논지가 몇 개 들어갔는지 본다'})

    return {
        'file': path.as_posix(),
        'paragraphs': len(body_text),
        'appendix_paragraphs': sum(1 for _, _, body in blocks if not body),
        'sentences': len(lengths),
        'measured': measured,
        'violation_count': len(violations),
        'note_count': len(notes),
        'violations': violations,
        'notes': notes,
        'ok': not violations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('file', help='서면 초안 .md 또는 .docx')
    parser.add_argument('--json', action='store_true', help='JSON 으로만 출력')
    parser.add_argument('--notes', action='store_true', help='참고 항목도 모두 나열')
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    result = check(Path(args.file))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['ok'] else 1

    m, ref = result['measured'], result['measured']['reference']
    print('%s' % result['file'])
    print('본문 %d문단 %d문장 (보완 메모 %d문단 제외)'
          % (result['paragraphs'], result['sentences'], result['appendix_paragraphs']))
    print('  문장 평균 %5.0f자 (기준 %d자)   중앙값 %5.0f자 (기준 %d자)   1문장 문단 %4.0f%% (기준 %d%%)'
          % (m['sentence_chars_mean'], ref['sentence_chars_mean'],
             m['sentence_chars_median'], ref['sentence_chars_median'],
             m['one_sentence_ratio'], ref['one_sentence_ratio']))
    print('위반 %d건 / 참고 %d건\n' % (result['violation_count'], result['note_count']))
    for row in result['violations']:
        print('  [위반] %-18s %5s행  %s' % (row['rule'], row['line'], row['detail']))
        print('         %s' % row['text'])
    counts = {}
    for row in result['notes']:
        counts[row['rule']] = counts.get(row['rule'], 0) + 1
    if counts:
        print('\n  참고 항목 (판단은 사람이 한다)')
        for rule, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print('    %-28s %3d건' % (rule, n))
    if args.notes:
        for row in result['notes']:
            print('  [참고] %-18s %5s행  %s' % (row['rule'], row['line'], row['detail']))
            print('         %s' % row['text'])
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
