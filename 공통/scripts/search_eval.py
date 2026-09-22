"""판례 검색 재현율 검증. 검색 방법을 바꾼 뒤 전보다 판례를 덜 찾게 되지 않았는지 잰다.

대법원 판결이 스스로 적은 참조판례를 정답으로 삼는다. 판시사항만 보고 만든 검색어로 법제처 판례를 수확하고
(`lawgo.harvest` — 검색 스킬이 쓰는 것과 같은 목록 정렬·인용 순위), 목록과 인용 순위에서 정답을 몇 건 찾는지 센다.
법제처 OPEN API만 쓰고 LBOX에는 요청을 보내지 않는다. LBOX 하급심 시험은 스크립트를 브라우저에 붙여 넣어 돌린다.

  run          재현율을 잰다. 결과를 공통/검증/판례검색/결과_{날짜}_본문{N}.json 에 남기고 같은 설정의 가장 이른 결과(기준)와 함께 보인다
  issues       검색어를 새로 만들 때 볼 판시사항만 낸다. 정답과 사건번호는 내지 않는다
  build        정답 목록을 새로 뽑는다. 이미 있으면 --force 없이는 덮어쓰지 않는다(기준선이 바뀌면 이전 결과와 비교할 수 없다)
  records      지난 사건에서 쓴 판례(공통/판례기록)가 법제처에 있는지 센다
  lbox-script  LBOX 하급심 시험 스크립트를 낸다. 목록 검색만 보내고 본문은 받지 않는다
  lbox-score   브라우저에서 저장한 하급심 시험 결과를 기준 결과와 함께 요약한다

절차와 기준 결과는 공통/검증/판례검색/README.md 에 있다.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '공통' / '검증' / '판례검색'
RECORDS = ROOT / '공통' / '판례기록'
ANSWERS, QUERIES, LOWER = '대법원_정답.json', '대법원_검색어.json', '하급심_시험.json'
_spec = importlib.util.spec_from_file_location('lawgo', Path(__file__).with_name('lawgo.py'))
lawgo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lawgo)

PLAN = [('근로기준법', 14), ('노동조합 및 노동관계조정법', 6), ('산업재해보상보험법', 4),
        ('근로자퇴직급여 보장법', 2), ('기간제 및 단시간근로자 보호 등에 관한 법률', 2), ('파견근로자 보호 등에 관한 법률', 2)]
KEYS = ('목록_전체', '목록_상위20', '목록_상위50', '인용_전체', '인용_상위10', '인용_상위20', '합계', '합친상위40')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, data):
    lawgo.write(Path(path), json.dumps(data, ensure_ascii=False, indent=1) + '\n')


def numbers(value):
    return [x.strip() for x in (value or '').split(',') if x.strip()]


def fatal(exc):
    """인증·연결 오류는 사건마다 되풀이되므로 거기서 멈춘다."""
    return any(s in str(exc) for s in ('사용자 정보', 'HTTP ', '연결 실패'))


def build(folder=DATA, plan=PLAN, seed=20260917, force=False, oc=None):
    folder = Path(folder)
    if (folder / ANSWERS).exists() and not force:
        raise lawgo.LawGoError(f'{ANSWERS} 가 이미 있습니다. 정답 목록을 새로 뽑으면 이전 결과와 비교할 수 없으므로 그때만 --force 를 붙입니다.')
    oc = lawgo.oc_value(oc)
    rng, cases, seen = random.Random(seed), [], set()
    for law, want in plan:
        rows = lawgo.search('판례', ref_law=law, court='대법원', limit=100, oc=oc)['rows']
        rng.shuffle(rows)
        got = 0
        for row in rows:
            if got >= want:
                break
            if row['사건번호'] in seen:
                continue
            try:
                doc = lawgo.show('판례', row['id'], oc=oc)
            except lawgo.LawGoError as exc:
                if fatal(exc):
                    raise
                continue
            issue = doc['본문'].get('판시사항', '')
            targets = {n for court, n in lawgo.cited_cases(doc['본문'].get('참조판례', '')) if court == '대법원'} - set(numbers(row['사건번호']))
            if len(targets) >= 2 and len(issue) >= 30:
                seen.add(row['사건번호'])
                cases.append({'번호': len(cases) + 1, '법': law, 'id': row['id'], '사건번호': row['사건번호'],
                              '선고': row['일자'], '판시사항': issue, '정답': sorted(targets)})
                got += 1
    save(folder / ANSWERS, cases)
    return {'사례': len(cases), '정답': sum(len(c['정답']) for c in cases),
            '다음': 'issues 로 판시사항만 보고 검색어 파일을 새로 만든다'}


def issues(folder=DATA):
    cases = load(Path(folder) / ANSWERS)
    return ('# 검색어를 만들 판시사항\n\n정답(참조판례)과 사건번호는 싣지 않는다. 사건마다 lbox-검색 스킬 1항대로 검색어를 만들어 '
            '{"번호": ["검색어", …]} 꼴의 JSON 파일로 이 폴더에 두고 `run --queries 파일이름`으로 잰다.\n\n'
            + '\n\n'.join(f"## {c['번호']} ({c['법']})\n\n{c['판시사항']}" for c in cases) + '\n')


def measure(targets, listed, ranking, top=20):
    targets = set(targets)
    found = lambda items: len(targets & set(items))
    combined = list(dict.fromkeys(list(ranking[:top]) + list(listed[:top])))
    return {'정답수': len(targets), '목록_전체': found(listed), '목록_상위20': found(listed[:20]), '목록_상위50': found(listed[:50]),
            '인용_전체': found(ranking), '인용_상위10': found(ranking[:10]), '인용_상위20': found(ranking[:20]),
            '합계': found(set(listed) | set(ranking)), '합친상위40': found(combined),
            '놓친정답': sorted(targets - set(listed) - set(ranking))}


def aggregate(per_case):
    total = sum(r['정답수'] for r in per_case)
    out = {'사례': len(per_case), '정답': total}
    for key in KEYS:
        value = sum(r[key] for r in per_case)
        out[key] = f'{value}/{total} ({value / total:.0%})' if total else '0/0'
    out['평균후보수'] = round(sum(r.get('후보수', 0) for r in per_case) / len(per_case)) if per_case else 0
    errors = [r['번호'] for r in per_case if r.get('오류')]
    if errors:
        out['오류사례'] = errors
    return out


def in_lawgo(court, number, oc):
    level = '대법원' if court == '대법원' else '하급심'
    rows = lawgo.search('판례', number=number, court=level, limit=10, sort=None, oc=oc)['rows']
    return any(lawgo.squash(r['기관']) == lawgo.squash(court) and number in numbers(r['사건번호']) for r in rows)


def baseline(folder, name, settings):
    """같은 설정으로 잰 가장 이른 결과. 이번 파일은 뺀다."""
    for f in sorted(Path(folder).glob('결과_*.json')):
        if f.name != name:
            data = load(f)
            if all(data.get(k) == v for k, v in settings.items()):
                return {'파일': f.name, **data['요약']}
    return None


def run(folder=DATA, queries_file=QUERIES, texts=20, limit=300, presence=False, oc=None):
    folder = Path(folder)
    cases, queries = load(folder / ANSWERS), load(folder / queries_file)
    oc = lawgo.oc_value(oc)
    start, started, per_case = lawgo.CALLS['n'], time.time(), []
    for case in cases:
        own, asked = set(numbers(case['사건번호'])), queries.get(str(case['번호']), [])
        head = {'번호': case['번호'], '사건번호': case['사건번호'], '검색어수': len(asked)}
        try:
            # 시험 사건 자신은 실제 사건에서는 아직 없는 판결이고, 그 본문에는 정답인 참조판례가 적혀 있으므로 수확에서 뺀다
            got = lawgo.harvest(['판례'], asked, body=True, court='대법원', limit=limit, texts=texts, exclude=own, oc=oc)['목록']['판례']
        except lawgo.LawGoError as exc:
            if fatal(exc):
                raise
            per_case.append({**head, '오류': str(exc), **measure(case['정답'], [], [])})
            continue
        listed = list(dict.fromkeys(n for row in got['rows'] for n in numbers(row['사건번호']) if n not in own))
        ranking = [r['사건번호'] for r in got['인용순위'] if r['법원'] == '대법원' and r['사건번호'] not in own]
        per_case.append({**head, '후보수': len(listed), **measure(case['정답'], listed, ranking)})
    today = date.today().isoformat()
    settings = {'검색어파일': Path(queries_file).name, '본문수': texts, '검색건수': limit}
    name = f'결과_{today}_본문{texts}' + ('' if settings['검색어파일'] == QUERIES else '_' + Path(queries_file).stem) + '.json'
    result = {'날짜': today, **settings, '요약': aggregate(per_case)}
    if presence:        # 놓친 정답이 법제처에 아예 없으면 검색 문제가 아니라 수록 문제이다
        missed = sorted({n for r in per_case for n in r['놓친정답']})
        there = [n for n in missed if in_lawgo('대법원', n, oc)]
        result['요약'].update(놓친정답_법제처에있음=len(there), 놓친정답_법제처에없음=len(missed) - len(there))
    result.update(호출=lawgo.CALLS['n'] - start, 초=round(time.time() - started), 사례=per_case)
    base = baseline(folder, name, settings)
    save(folder / name, result)
    return {k: v for k, v in result.items() if k != '사례'} | ({'기준': base} if base else {}) | {'파일': name}


def records(folder=RECORDS, out=DATA, oc=None):
    oc = lawgo.oc_value(oc)
    rows = []
    for f in sorted(Path(folder).glob('*.md')):
        court, _, number = f.stem.partition('_')
        if not number or (court != '대법원' and not court.endswith(('법원', '지원', '재판부'))):
            continue                                    # 안내문·위원회 결정은 판례가 아니다
        row = {'법원': court, '사건번호': number, '구분': '대법원' if court == '대법원' else '하급심'}
        try:
            row['법제처'] = in_lawgo(court, number, oc)
        except lawgo.LawGoError as exc:
            if fatal(exc):
                raise
            row.update(법제처=None, 오류=str(exc))
        rows.append(row)
    today = date.today().isoformat()
    count = lambda level: f"{sum(1 for r in rows if r['구분'] == level and r['법제처'])}/{sum(1 for r in rows if r['구분'] == level)}"
    result = {'날짜': today, '법제처수록': {level: count(level) for level in ('대법원', '하급심')},
              '법제처에있는하급심': [f"{r['법원']} {r['사건번호']}" for r in rows if r['구분'] == '하급심' and r['법제처']],
              '법제처에없는대법원': [r['사건번호'] for r in rows if r['구분'] == '대법원' and r['법제처'] is False],
              '확인실패': [f"{r['법원']} {r['사건번호']}" for r in rows if r['법제처'] is None], '판례': rows}
    name = f'결과_{today}_판례기록.json'
    save(Path(out) / name, result)
    return {k: v for k, v in result.items() if k != '판례'} | {'파일': name}


LBOX_SCRIPT = r"""// 하급심 찾기 시험(공통/검증/판례검색/README.md). lbox-검색 스킬 3항의 코드 블록(lboxGuard·lboxLock·lboxCall)을 붙여 넣은 lbox.kr 탭에서 돌린다.
// 목록 검색(POST)만 보내고 본문(GET)은 받지 않는다. 검색어마다 차례(lboxLock)를 받아 다른 세션 요청과 겹치지 않게 하고, 요청 사이 1.2초를 둔다.
// 결과는 window.하급심시험 에 쌓인다. 끝: true 가 되면 JSON.stringify(window.하급심시험) 을 결과_{날짜}_하급심.json 으로 저장한다.
(() => {
  lboxGuard();
  if (Date.now() - (+localStorage.getItem('lbox경고') || 0) < 24 * 3600e3) throw new Error('이용 확인 화면 뒤 24시간 안에는 시험을 돌리지 않는다');
  const 대상 = __대상__;
  const 쉼 = ms => new Promise(z => setTimeout(z, ms));
  const 시험 = window.하급심시험 = {날짜: new Date().toLocaleDateString('sv-SE'), 끝: false, 요청: 0, 결과: []};
  (async () => {
    for (const [판결, 검색어들] of 대상) {
      const 행 = {판결, 검색: []};
      시험.결과.push(행);                       // 도중에 멈추어도 받은 데까지 남는다
      for (const 검색어 of 검색어들) {
        행.검색.push(await lboxLock(async () => {
          const 줄 = {검색어, 전체: 0, 관련도순위: null, 피인용순위: null};
          for (const [sort, 쪽수] of [['SCORE:DESC', 3], ['QUOTED_COUNT:DESC', 1]]) {
            for (let p = 1; p <= 쪽수; p++) {
              const j = await lboxCall({type: 'PRECEDENT', query: 검색어, options: {}, paging: {page: p, size: 30, sort}, requiresCorrection: false});
              시험.요청++;
              const k = (j.result || []).findIndex(it => (it.textSubInfo || {}).id === 판결);
              if (sort === 'SCORE:DESC') {
                if (p === 1) 줄.전체 = j.count || 0;
                if (k >= 0) 줄.관련도순위 = (p - 1) * 30 + k + 1;
              } else if (k >= 0) 줄.피인용순위 = k + 1;
              await 쉼(1200);
              if (sort === 'SCORE:DESC' && (줄.관련도순위 !== null || p * 30 >= 줄.전체)) break;
            }
          }
          return 줄;
        }));
      }
    }
  })().catch(e => { 시험.오류 = e.message; }).finally(() => { 시험.끝 = true; });
  return '시작: 판결 ' + 대상.length + '건';
})();
"""


def lbox_script(folder=DATA):
    targets = [[t['판결'], t['검색어']] for t in load(Path(folder) / LOWER)['대상']]
    return LBOX_SCRIPT.replace('__대상__', json.dumps(targets, ensure_ascii=False))


def best_rank(row):
    return min((s['관련도순위'] for s in row['검색'] if s.get('관련도순위')), default=None)


def lower_summary(results):
    best = [best_rank(r) for r in results]
    asked = [s for r in results for s in r['검색']]
    return {'판결': len(results), '관련도90위안': sum(b is not None for b in best), '최고순위5위안': sum(b is not None and b <= 5 for b in best),
            '검색어별놓침': f"{sum(not s.get('관련도순위') for s in asked)}/{len(asked)}"}


def lbox_score(path, folder=DATA):
    now, base = load(path), load(Path(folder) / LOWER)['기준']
    before = {r['판결']: best_rank(r) for r in base['결과']}
    out = {'이번': {'날짜': now.get('날짜'), '요청': now.get('요청'), **lower_summary(now.get('결과', []))},
           '기준': {'날짜': base['날짜'], **lower_summary(base['결과'])},
           '판결별_최고순위': [{'판결': r['판결'], '이번': best_rank(r), '기준': before.get(r['판결'])} for r in now.get('결과', [])]}
    if now.get('오류') or not now.get('끝'):
        out['중단'] = now.get('오류') or '끝나기 전에 저장한 결과'
    return out


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dir', default=str(DATA), help='시험 자료 폴더')
    parser.add_argument('--oc', help='법제처 인증값을 이번 실행에만 지정한다')
    subs = parser.add_subparsers(dest='command', required=True)
    s = subs.add_parser('run', help='재현율을 잰다')
    s.add_argument('--queries', default=QUERIES, help='검색어 파일 이름(시험 자료 폴더 안)')
    s.add_argument('--texts', type=int, default=20, help='인용 순위를 세울 때 읽는 목록 상위 본문 수')
    s.add_argument('--limit', type=int, default=300, help='검색어마다 받는 최대 건수')
    s.add_argument('--presence', action='store_true', help='놓친 정답이 법제처에 있는지도 확인한다')
    s = subs.add_parser('issues', help='판시사항만 낸다'); s.add_argument('--out')
    s = subs.add_parser('build', help='정답 목록을 새로 뽑는다')
    s.add_argument('--seed', type=int, default=20260917); s.add_argument('--force', action='store_true')
    subs.add_parser('records', help='판례기록의 법제처 수록 여부를 센다')
    s = subs.add_parser('lbox-script', help='LBOX 하급심 시험 스크립트를 낸다'); s.add_argument('--out')
    s = subs.add_parser('lbox-score', help='하급심 시험 결과를 요약한다'); s.add_argument('file')
    args = parser.parse_args()
    try:
        if args.command in ('issues', 'lbox-script'):
            text = issues(args.dir) if args.command == 'issues' else lbox_script(args.dir)
            if args.out:
                lawgo.write(Path(args.out), text)
                text = json.dumps({'파일': args.out, '글자수': len(text)}, ensure_ascii=False)
            print(text)
            return 0
        if args.command == 'run':
            result = run(args.dir, args.queries, texts=args.texts, limit=args.limit, presence=args.presence, oc=args.oc)
        elif args.command == 'build':
            result = build(args.dir, seed=args.seed, force=args.force, oc=args.oc)
        elif args.command == 'records':
            result = records(out=args.dir, oc=args.oc)
        else:
            result = lbox_score(args.file, args.dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (lawgo.LawGoError, OSError, ValueError, KeyError) as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
