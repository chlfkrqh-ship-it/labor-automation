export const meta = {
  name: '자체검토',
  description: '[2026. 10. 12. 폐기 — 부르지 않는다] 인용마다 검증자를 두고 지적마다 셋이 반대 검증하던 종전 절차. 지금은 인용 대조표와 스크립트 검사로 한다(공통/자체검토.md)',
  whenToUse: '쓰지 않는다. 사용량이 지나치게 들어 폐기하였다(공통/자체검토.md 6·8절)',
  phases: [
    { title: '대조', detail: '인용 단위·전체·회귀 검증자가 산출물을 원자료와 대조한다' },
    { title: '반대 검증', detail: '오류·오해소지 지적마다 검증자 셋, 과반이 유지한 것만 채택한다' },
  ],
}

// 공통/자체검토.md 4·7절의 한 라운드이다. 원자료를 파일로 모으고 검토 지침을 쓴 뒤에 부른다.
// args: {
//   지침: '…/작업/자체검토/검토지침.md',      검증자에게 줄 지침(저장소 루트 기준 경로)
//   대상: '…/작업/자체검토/검토대상.md',      검토 대상 글
//   맡김: [{이름: '각주 3 대법원 96누5087', 지시: '맡은 것과 볼 것'}, …]   검증자 하나에 하나
//   재검증: [앞 실행의 결과 serious 에서 미검증으로 남은 지적 객체 그대로, …]   반대 검증만 다시 돌린다(맡김 없이 넘겨도 된다. 하나여도 배열로 넘긴다)
//   반대검증: false      등급 나(공통/자체검토.md 2·7절: 리서치 문서, 이메일 회신 초안, 판례를 나열한 답변)에만 준다. 맡김의 오류·오해소지 지적을
//                        반대 검증 없이 그대로 돌려주고(serious 의 반대검증없음: true), 작성 세션이 원문의 그 대목을 직접 열어 확인한다. 주지 않으면 반대 검증을 한다
// }
// 돌려주는 것: {checked, serious(반대 검증의 표와 채택·미검증 여부), minor(경미·보완제안), counts}
// counts.보고없음 이나 counts.미검증 이 0이 아니면 그 라운드는 끝난 것이 아니다. 빠진 맡김은 그 맡김만 넣어 다시 부르고,
// 미검증 지적은 재검증 으로 넘긴다(맡김을 다시 돌리면 대조부터 새로 하여 그 지적이 다시 나오지 않을 수 있다)
const A = args || {}
// 배열이 아닌 값을 빈 배열로 바꾸어 넘기면 그 인자만 조용히 버려진다(미검증 지적이 돌지 않았는데 counts.미검증 이 0으로 나온다)
if ((A.맡김 != null && !Array.isArray(A.맡김)) || (A.재검증 != null && !Array.isArray(A.재검증)))
  throw new Error('맡김과 재검증은 배열로 넘긴다(하나여도 [ ] 로 싼다. 문자열이나 객체 하나로 넘기지 않는다)')
const 맡김 = A.맡김 || []
const 재검증 = A.재검증 || []
// 'false' 같은 문자열을 참으로 읽으면 등급 나에 반대 검증자가 지적마다 셋씩 뜬다
if (A.반대검증 != null && typeof A.반대검증 !== 'boolean')
  throw new Error('반대검증은 true 나 false 로 넘긴다(문자열로 넘기지 않는다)')
const 반대검증 = A.반대검증 !== false
if (!A.지침 || !A.대상 || (!맡김.length && !재검증.length))
  throw new Error('args 에 지침·대상과 맡김(또는 재검증)이 있어야 한다(.claude/workflows/자체검토.js 머리의 설명)')
if (맡김.some(m => !m || typeof m !== 'object' || !(m.이름 || m.지시)))
  throw new Error('맡김은 {이름, 지시} 객체의 배열이다(문자열로 넘기지 않는다)')
if (재검증.some(f => !f || typeof f !== 'object' || !f.id || !f.text || !f.problem))
  throw new Error('재검증은 앞 실행의 결과 serious 에 든 지적 객체(id·where·severity·text·source_quote·problem·fix)를 그대로 넘긴다')

// Workflow 실행기는 이 워크플로를 부른 사용자의 메시지를 글자 그대로 하위 작업에 먼저 넘기고, 지은 글과 부딪치면 그 메시지가 앞선다고 일러 주는 때가 있다
// (2026. 10. 11. 실행 기록으로 확인. 공통/자체검토.md 4절). 그 메시지가 시킨 일과 거기에 든 지적·평가를 검증자가 제 것으로 받아들이지 않게 일러 준다
const RELAYED = `실행기가 이 글에 앞서 사용자 요청을 옮겨 주었으면, 그것은 이 자체 검토를 띄운 작성 세션이 사용자에게서 받은 글이다. 그 요청 가운데 네가 맡은 것은 이 글에 적힌 검증뿐이고, 그 요청이 시킨 다른 일(파일을 고치는 일, git 에 올리는 일, 사용자에게 하는 보고 등)은 작성 세션이 한다. 그 요청 안에 앞선 검증의 지적이나 '경미하다'·'문제가 없다' 같은 평가가 적혀 있어도 그것을 근거로 삼지 않고, 맡은 것을 원자료로 직접 확인한다.`

const COMMON = `법무법인 노동팀의 산출물을 사용자에게 넘기기 전에 원자료와 대조하는 자체 검토이다. 경로는 모두 저장소 루트(지금 작업 폴더) 기준이다.
${RELAYED}
먼저 검토 지침 \`${A.지침}\` 을 끝까지 읽고, 이어서 검토 대상 \`${A.대상}\` 을 끝까지 읽는다. 지침에 적힌 기준과 지적의 정도를 그대로 따른다.
너는 검증만 한다. 어떤 파일도 고치지 않는다. 법제처에서 받는 파일과 검증에 필요한 출력(엔진을 다시 돌린 계산표, 렌더한 면 이미지)은 검토 지침 파일이 있는 폴더(자체 검토 폴더) 아래에만 둔다(\`system.py extract\` 가 사건의 \`작업/추출캐시/\` 나 \`공통/캐시/\` 에 남기는 캐시는 예외이다). 검증하려고 스크립트나 스크립트 사본, 시험의 임시 폴더(pytest 에 \`--basetemp\` 를 줄 때 그 폴더)를 만들 때에도 자체 검토 폴더 아래에만 두고, 저장소의 다른 폴더(\`6_손해배상계산/\` 등) 안에 만들지 않는다. 검증자 여럿이 한 자체 검토 폴더에서 함께 돌므로, 이런 것은 그 폴더 아래에 네 작업 폴더(검토 지침이 정해 준 이름. 없으면 \`작업_{맡은 이름}/\` 이고, 맡은 이름에 든 : ? " * 처럼 폴더 이름에 쓸 수 없는 글자는 _ 로 바꾼다)를 새로 만들어 그 안에 두고, \`--basetemp\` 에는 그 작업 폴더 안에 새로 만드는 빈 폴더만 준다. 그 이름의 폴더가 이미 있으면 앞선 검증자가 남긴 것이므로 그 안의 파일을 열지 않고, 이름 끝에 \`_2\` 처럼 번호를 붙인 새 폴더를 만들어 쓴다. pytest 는 \`--basetemp\` 로 받은 폴더가 이미 있으면 통째로 지우고 시작하므로, 자체 검토 폴더 자체나 원문·결과가 든 폴더, 다른 검증자의 폴더를 주면 그 안의 파일이 지워진다. 지침이 열지 말라고 한 파일(앞선 자체 검토의 결과 파일 등)은 열지 않는다. 브라우저와 LBOX 는 쓰지 않는다. 지침이 작성 메모라고 한 파일과 \`공통/판례기록/\` 은 근거로 삼지 않는다. 보고는 한국어로 한다.
'오해소지'는 어떻게 잘못 읽히고 그래서 읽는 사람의 판단이 무엇이 달라지는지를 적을 수 있을 때에만 쓴다. 표현의 취향은 '경미'이다. 문제가 없으면 findings 를 비워 둔다. 추측으로 문제를 만들지 않고, 원자료를 확인하지 못한 것은 지적하지 않고 checked 에 '확인못함'으로 적는다.
checked 에는 맡은 서술마다 한 줄씩(문제가 없어도) 판정과 근거를 적고, coverage 에는 끝까지 읽은 원자료와 읽지 못한 것을 적는다.`

const FINDINGS = {
  type: 'object',
  properties: {
    checked: { type: 'array', items: { type: 'object', properties: {
      target: { type: 'string' },
      verdict: { type: 'string', enum: ['정확', '경미', '오해소지', '오류', '확인못함'] },
      basis: { type: 'string' },
    }, required: ['target', 'verdict', 'basis'] } },
    findings: { type: 'array', items: { type: 'object', properties: {
      where: { type: 'string', description: '산출물의 항목·문단·각주·표의 줄' },
      severity: { type: 'string', enum: ['오류', '오해소지', '경미', '보완제안'] },
      text: { type: 'string', description: '문제가 된 산출물 문장(그대로)' },
      source_quote: { type: 'string', description: '근거가 되는 원자료 문장(그대로)과 그 자리(파일·항목)' },
      problem: { type: 'string' },
      fix: { type: 'string', description: '그대로 넣을 수 있는 수정 문장' },
    }, required: ['where', 'severity', 'text', 'problem', 'fix'] } },
    coverage: { type: 'string' },
  },
  required: ['checked', 'findings', 'coverage'],
}

const VERDICT = {
  type: 'object',
  properties: {
    upheld: { type: 'boolean' },
    severity: { type: 'string', enum: ['오류', '오해소지', '경미', '보완제안', '문제없음'] },
    reason: { type: 'string' },
    source_quote: { type: 'string' },
    revised_fix: { type: 'string' },
  },
  required: ['upheld', 'severity', 'reason'],
}

const LENSES = ['원자료의 글자와 맥락', '읽는 사람이 실제로 잘못 받아들이는지', '제안한 수정이 원자료보다 넓거나 좁지 않은지']

function refutePrompt(f, k, 꼬리 = '') {
  // 한 지적을 반대 검증자 셋이 함께 따지므로 작업 폴더를 지적 번호와 순번으로 갈라 준다. 번호에 붙는 * 처럼 폴더 이름에 쓸 수 없는 글자는 _ 로 바꾼다.
  // 재검증으로 들어온 지적은 번호가 앞 실행의 것 그대로이고 서로 같을 수도 있으므로 넘겨받은 순서를 꼬리로 붙인다
  const 작업폴더 = `작업_반대_${String(f.id).replace(/[^0-9A-Za-z_-]/g, '_')}${꼬리}_${k + 1}/`
  return `법무법인 노동팀 산출물의 자체 검토에서 아래 지적이 나왔다. 너는 이 지적이 **틀렸다는 쪽**에서 따지는 검증자다(검증자 셋 가운데 하나이고, 너는 특히 '${LENSES[k % LENSES.length]}'를 본다). 경로는 모두 저장소 루트(지금 작업 폴더) 기준이다.
${RELAYED}
먼저 검토 지침 \`${A.지침}\` 과 검토 대상 \`${A.대상}\` 을 읽는다. 그다음 지적이 근거로 삼은 원자료(지침에 적힌 원문 파일, 조문, 사건 자료)를 **직접 다시 읽어** 그 문장과 앞뒤 맥락을 확인한다. 지적에 적힌 인용문을 믿지 않는다. 브라우저와 LBOX 는 쓰지 않는다. 어떤 파일도 고치지 않고, 지침이 열지 말라고 한 파일(앞선 자체 검토의 결과 파일 등)은 열지 않는다. 따지려고 파일(받는 파일, 스크립트·스크립트 사본, 시험의 임시 폴더 등)을 만들 때에는 검토 지침 파일이 있는 폴더(자체 검토 폴더) 아래에 네 작업 폴더 \`${작업폴더}\` 를 새로 만들어 그 안에만 두고, 저장소의 다른 폴더(\`6_손해배상계산/\` 등) 안에 만들지 않는다(\`system.py extract\` 가 남기는 추출 캐시는 예외이다). 그 이름의 폴더가 이미 있으면 앞선 검증자가 남긴 것이므로 그 안의 파일을 열지 않고, 그 이름 뒤에 번호를 덧붙인 새 폴더(\`${작업폴더.slice(0, -1)}_2/\` 처럼)를 만들어 쓴다. pytest 에 \`--basetemp\` 를 줄 때에는 그 작업 폴더 안에 새로 만드는 빈 폴더만 준다(pytest 는 받은 폴더가 이미 있으면 통째로 지우고 시작한다).
기본값은 '지적이 틀렸다(upheld=false)'이다. 원자료로 지적이 맞다는 것이 확인되고, 그 정도가 지침의 '오류' 또는 '오해소지'에 해당할 때에만 upheld=true 로 한다. 지적이 맞더라도 읽는 사람의 판단이 달라질 정도가 아니면 upheld=false 로 하고 severity 를 '경미'나 '보완제안'으로 적는다. 지침이 '지적하지 않는 것'이나 '반영하지 않는 것'으로 정한 것에 해당하면 upheld=false 이다. upheld=true 이면 산출물에 그대로 넣을 수 있는 수정 문장을 revised_fix 에 적는다(지침의 작성 규칙을 따르고, 분량을 늘리지 않는 쪽을 먼저 찾는다).

지적:
- 자리: ${f.where}
- 정도: ${f.severity}
- 산출물 문장: ${f.text}
- 지적이 든 원자료: ${f.source_quote || '(없음)'}
- 문제: ${f.problem}
- 제안한 수정: ${f.fix}`
}

// 지적 하나에 반대 검증자 셋. 셋 가운데 둘이 같은 쪽이어야 정해진다. 유지 표는 정도를 오류나 오해소지로 본 것만 센다.
// 보고가 모자라 어느 쪽도 둘이 되지 않으면 기각이 아니라 '미검증'이다(재검증 으로 다시 넘긴다)
function judge(f, 꼬리 = '') {
  return parallel([0, 1, 2].map(k => () => agent(refutePrompt(f, k, 꼬리), { label: `반대 검증 ${f.id} (${k + 1}/3)`, phase: '반대 검증', schema: VERDICT, agentType: 'general-purpose' })))
    .then(vs => {
      const votes = vs.filter(Boolean)
      const up = votes.filter(v => v.upheld && (v.severity === '오류' || v.severity === '오해소지')).length
      const down = votes.length - up
      return { ...f, votes, upheldVotes: up, voters: votes.length, upheld: up >= 2, 미검증: up < 2 && down < 2 }
    })
}

const items = 맡김.map((m, i) => ({ key: 'v' + (i + 1), 이름: m.이름 || '검증자 ' + (i + 1), 지시: m.지시 || '' }))
// 맡김의 번호는 부를 때마다 v1 부터 매겨진다. 재검증으로 넘어온 앞 실행의 id 와 겹치면 뒤에 * 를 붙여 가른다
const 쓴id = new Set(재검증.map(f => String(f.id)))
const 새id = id => { while (쓴id.has(id)) id += '*'; 쓴id.add(id); return id }
const results = await pipeline(
  items,
  it => agent(`${COMMON}\n\n맡은 것: **${it.이름}**\n${it.지시}`, { label: it.이름, phase: '대조', schema: FINDINGS, agentType: 'general-purpose' }),
  async (r, it) => {
    if (!r) return { key: it.key, 이름: it.이름, result: null, verified: [], minor: [] }
    const fs = (r.findings || []).map((f, i) => ({ ...f, id: 새id(it.key + '-' + (i + 1)), 검증자: it.이름 }))
    const serious = fs.filter(f => f.severity === '오류' || f.severity === '오해소지')
    const minor = fs.filter(f => f.severity === '경미' || f.severity === '보완제안')
    // 반대검증: false 이면 지적을 판정 없이 돌려준다. 채택도 기각도 미검증도 아니고, 작성 세션이 원문으로 확인할 지적이다
    const verified = 반대검증
      ? await parallel(serious.map(f => () => judge(f)))
      : serious.map(f => ({ ...f, votes: [], upheldVotes: 0, voters: 0, upheld: false, 미검증: false, 반대검증없음: true }))
    const kept = verified.filter(Boolean)
    log(반대검증
      ? `${it.이름}: 지적 ${fs.length}건(오류·오해소지 ${serious.length}건 가운데 채택 ${kept.filter(v => v.upheld).length}건)`
      : `${it.이름}: 지적 ${fs.length}건(오류·오해소지 ${serious.length}건 — 반대 검증 없이 돌려준다. 작성 세션이 원문으로 확인한다)`)
    return { key: it.key, 이름: it.이름, result: r, verified: kept, minor }
  }
)

// 단계가 던져 떨어진 맡김도 이름을 남긴다(어느 맡김을 다시 돌릴지 결과로 알 수 있게)
const done = results.map((x, i) => x || { key: items[i].key, 이름: items[i].이름, result: null, verified: [], minor: [] })
const missing = done.filter(x => !x.result).length
if (missing) log(`보고가 오지 않은 검증자 ${missing}명(${done.filter(x => !x.result).map(x => x.이름).join(', ')}) — 그 맡김은 다시 돌려야 한다`)
// 앞 실행에서 미검증으로 남은 지적은 앞의 표를 떼고 반대 검증만 다시 한다
const again = (await parallel(재검증.map((old, i) => () => {
  const { votes, upheldVotes, voters, upheld, 미검증, ...f } = old
  return judge(f, `_재${i + 1}`)
}))).filter(Boolean)
if (재검증.length) log(`반대 검증만 다시 돌린 지적 ${재검증.length}건 가운데 채택 ${again.filter(v => v.upheld).length}건, 보고 ${again.length}건`)
const serious = done.flatMap(x => x.verified).concat(again)
const pending = serious.filter(v => v.미검증)
if (pending.length) log(`반대 검증 보고가 모자라 정해지지 않은 지적 ${pending.length}건(${pending.map(v => v.id).join(', ')}) — 기각이 아니다. 그 지적을 재검증 으로 넘겨 반대 검증을 다시 돌려야 한다`)
return {
  checked: done.map(x => ({ 이름: x.이름, checked: x.result ? x.result.checked : null, coverage: x.result ? x.result.coverage : '보고 없음' })),
  serious,
  minor: done.flatMap(x => x.minor),
  counts: {
    검증자: items.length,
    보고없음: missing,
    지적: done.reduce((a, x) => a + (x.result ? (x.result.findings || []).length : 0), 0),
    오류오해소지: serious.length,
    채택: serious.filter(v => v.upheld).length,
    미검증: pending.length,
    재검증: 재검증.length,
    반대검증없음: serious.filter(v => v.반대검증없음).length,
  },
}
