#!/usr/bin/env python3
"""자체 검토 워크플로(.claude/workflows/자체검토.js)가 돌려준 결과를 라운드 기록으로 정리한다(공통/자체검토.md 10절).

    python -B 공통/scripts/review_result.py "<워크플로 결과 파일>" --out "<자체검토 폴더>/결과_1차.md"

결과 파일은 Workflow 도구가 알려 준 출력 파일(JSON)이다. 채택된 지적, 기각된 지적과 반대 검증의 판정 이유,
경미·보완제안, 검증자마다 읽은 범위를 그대로 옮긴다. 반영 여부는 이 파일 끝에 작성 세션이 따로 적는다.
화면에는 건수, 보고가 비어 있는 검증자, 채택된 지적과 미검증 지적을 찍는다. 이미 있는 기록은 덮어쓰지 않는다(빠진 맡김·반대 검증만 다시 돌린
결과는 결과_N차_보충.md 로 따로 옮긴다).
"""
import argparse
import json
import sys
from pathlib import Path


def load(path):
    raw = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    data = raw['result'] if isinstance(raw, dict) and 'result' in raw and 'serious' not in raw else raw
    if not isinstance(data, dict) or not {'checked', 'serious', 'minor', 'counts'} <= set(data):
        raise SystemExit('자체 검토 워크플로의 결과가 아니다(checked·serious·minor·counts 가 든 객체여야 한다): ' + str(path))
    return data


def render(d, title):
    lines = ['# ' + title, '', '워크플로가 돌려준 것을 그대로 정리한 것이다. 반영 여부와 이유는 맨 끝 `처리` 에 적는다.', '',
             '건수: ' + json.dumps(d.get('counts', {}), ensure_ascii=False), '', '## 1. 오류·오해소지 지적과 반대 검증']
    for f in d.get('serious', []):
        state = '채택' if f.get('upheld') else '미검증' if f.get('미검증') else '기각'
        lines += [f"### {f.get('id')} [{f.get('severity')} → {state} {f.get('upheldVotes')}/{f.get('voters')}] {f.get('where')}",
                  f"- 검증자: {f.get('검증자', '')}", f"- 산출물 문장: {f.get('text', '')}", f"- 지적이 든 원자료: {f.get('source_quote', '')}",
                  f"- 문제: {f.get('problem', '')}", f"- 제안한 수정: {f.get('fix', '')}"]
        for k, v in enumerate(f.get('votes') or [], 1):
            # 워크플로는 지적이 맞다고 보았어도 정도를 경미·보완제안으로 본 표를 기각표로 센다
            kept = v.get('upheld') and v.get('severity') in ('오류', '오해소지')
            low = '(지적은 맞다고 보았으나 정도가 낮아 기각표로 셈)' if v.get('upheld') and not kept else ''
            lines += [f"- 반대 검증 {k}: {'유지' if kept else '기각'}{low} / {v.get('severity')} — {v.get('reason', '')}",
                      f"  - 든 원자료: {v.get('source_quote', '')}", f"  - 수정안: {v.get('revised_fix', '')}"]
        lines.append('')
    lines.append('## 2. 경미·보완제안(반대 검증 없음)')
    for f in d.get('minor', []):
        lines += [f"### {f.get('id')} [{f.get('severity')}] {f.get('where')}", f"- 검증자: {f.get('검증자', '')}",
                  f"- 산출물 문장: {f.get('text', '')}", f"- 원자료: {f.get('source_quote', '')}",
                  f"- 문제: {f.get('problem', '')}", f"- 제안: {f.get('fix', '')}", '']
    lines.append('## 3. 검증자마다 본 것과 읽은 범위')
    for g in d.get('checked', []):
        lines.append('### ' + str(g.get('이름')))
        for c in g.get('checked') or []:
            lines.append(f"- [{c.get('verdict')}] {c.get('target')} — {c.get('basis')}")
        lines += ['- 읽은 범위: ' + str(g.get('coverage', '')), '']
    lines += ['## 처리', '', '(채택된 지적의 반영, 경미·보완제안의 반영 여부와 이유, 확인하지 못한 것을 여기에 적는다)', '']
    return '\n'.join(lines)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('result')
    parser.add_argument('--out', required=True)
    parser.add_argument('--title', default='')
    parser.add_argument('--force', action='store_true', help='이미 있는 기록을 덮어쓴다')
    a = parser.parse_args()
    d = load(a.result)
    out = Path(a.out)
    if out.exists() and not a.force:      # 앞 실행의 판정과 작성 세션이 끝에 적은 처리 기록이 사라진다
        parser.error('이미 있는 기록이다: ' + a.out + '. 같은 라운드에서 빠진 맡김·반대 검증만 다시 돌린 결과는 이름을 달리 준다(결과_N차_보충.md, 이미 있으면 결과_N차_보충2.md). 덮어쓰려면 --force 를 붙인다')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(d, a.title or '자체 검토 결과 — ' + out.stem), encoding='utf-8')
    print(json.dumps(d.get('counts', {}), ensure_ascii=False), '->', a.out)
    missing = [g.get('이름') for g in d.get('checked', []) if not g.get('checked')]
    if missing:
        print('보고가 비어 있는 검증자(다시 맡긴다):', ', '.join(map(str, missing)))
    for f in d.get('serious', []):
        if f.get('upheld'):
            print(f"채택 {f.get('id')} [{f.get('severity')} {f.get('upheldVotes')}/{f.get('voters')}] {f.get('where')}")
        elif f.get('미검증'):
            print(f"미검증(반대 검증을 다시 돌린다) {f.get('id')} [{f.get('severity')} 보고 {f.get('voters')}건] {f.get('where')}")


if __name__ == '__main__':
    main()
