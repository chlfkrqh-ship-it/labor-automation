// lbox-검색 스킬의 브라우저 코드를 node 에서 가짜 LBOX 로 돌려 본다. test_lbox_code.py 가 부른다.
// 입력(stdin): {main, harvest, cites, opener, pdf} — SKILL.md 의 코드 블록 원문. 출력(stdout): [{name, ok, detail}]
const vm = require('vm');

function 새환경(blocks) {
  let 지금 = Date.UTC(2026, 8, 19, 0, 0, 0);
  const 저장 = {};
  const 보관함 = new Map();                                                                  // 본문 보관함(IndexedDB) 흉내. lboxCache 가 쓰는 만큼만 있다
  const 요청 = [];
  const 내려받기 = [];                                                                      // a.click() 으로 내려받은 것(이름·주소)
  class 가짜날짜 extends Date {
    constructor(...a) { if (a.length) super(...a); else super(지금); }
    static now() { return 지금; }
  }
  const ctx = {
    console, JSON, Math, Promise, Object, Array, Set, Map, Error, RegExp, String, Number, TextEncoder, Blob,
    encodeURIComponent, decodeURIComponent,
    Date: 가짜날짜,
    setTimeout: (fn, ms = 0) => { 지금 += Math.max(0, ms); setImmediate(fn); return 0; },   // 기다린 만큼 시계를 앞으로 돌린다
    clearTimeout: () => {},
    navigator: {},                                                                        // Web Locks 없음 → lboxLock 이 바로 부른다
    localStorage: {
      getItem: k => (k in 저장 ? 저장[k] : null),
      setItem: (k, v) => { 저장[k] = String(v); },
      removeItem: k => { delete 저장[k]; },
    },
    DOMParser: class {
      parseFromString(html) {
        const text = html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/g, '').replace(/<[^>]+>/g, '');   // lboxText 가 지우는 script·style 속 글은 화면 글자가 아니다
        return {querySelectorAll: sel => (sel.startsWith('script') ? [] : [{innerText: text, textContent: text}])};
      }
    },
    fetch: async (url, opt = {}) => {
      요청.push({url, method: opt.method || 'GET', body: opt.body ? JSON.parse(opt.body) : null, at: 지금});
      return ctx.응답(url, opt);
    },
    응답: async () => { throw new Error('응답이 정해지지 않았다'); },
    indexedDB: {
      open() {
        const 창고 = {
          get(k) { const g = {}; setImmediate(() => { g.result = 보관함.get(k); if (g.onsuccess) g.onsuccess(); }); return g; },
          put(v, k) { 보관함.set(k, v); },
        };
        const req = {result: {
          createObjectStore() {}, close() {},
          transaction() {                                                                   // 걸어 둔 get 이 모두 끝난 뒤에 oncomplete 를 부른다
            const tx = {objectStore: () => 창고};
            setImmediate(() => setImmediate(() => { if (tx.oncomplete) tx.oncomplete(); }));
            return tx;
          },
        }};
        setImmediate(() => { if (req.onsuccess) req.onsuccess(); });
        return req;
      },
    },
    document: {
      createElement: () => { const a = {click() { 내려받기.push({download: a.download, href: a.href}); }, remove() {}}; return a; },
      body: {appendChild() {}},
    },
    URL: {createObjectURL: () => 'blob:가짜'},
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const code of [blocks.main, blocks.harvest, blocks.cites, blocks.pdf]) vm.runInContext(code, ctx);
  const m = blocks.opener.match(/await \((async url => \{[\s\S]*\})\)\('[^']*'\);?/);
  if (!m) throw new Error('원문 열기 블록 모양이 다르다');
  vm.runInContext('globalThis.원문열기 = (' + m[1] + ');', ctx);
  return {ctx, 저장, 보관함, 요청, 내려받기, 시각: () => 지금, 시각바꾸기: t => { 지금 = t; }};
}

const 판결문 = '대법원 2010. 1. 14. 선고 2009다12345 판결 [임금] ' + '이유 가. 판단 '.repeat(40);
const 좋은본문 = url => ({url, ok: true, status: 200, text: async () => '<main>' + 판결문 + '</main>'});
const 기록 = 환경 => JSON.parse(환경.저장['lbox본문'] || '[]');
const 주소 = n => Array.from({length: n}, (_, i) => 'https://lbox.kr/case/대법원/2020다' + (1000 + i));

// LBOX 판례 페이지 모양을 줄인 것이다(2026. 10. 7. 수원지방법원 안산지원 2025가합6356 응답에서 확인한 구조).
// 화면에는 머리(사건명·상하위 판결)만 그려지고, 판결 글은 self.__next_f.push 조각 속 쿼리 자료로 온다. 조각은 실제처럼 둘로 나뉘어 올 수 있다
const 화면머리 = '판례새 작업수원지방법원 안산지원 2026. 4. 23. 선고 2025가합6356 판결[해고무효확인청구의소]상•하위 판결1확정여부 미확인원고패인용된 판례8인용된 조문4AI 유사판례1관련 문서가 없습니다';
const 쿼리 = (이름, data) => ({dehydratedAt: 0, state: {data, status: 'success'}, queryKey: ['precedents', 이름, '수원지방법원안산지원-2025가합6356'], queryHash: ''});
const 문단들 = ['1. 기초사실', '가. 당사자들의 지위', '피고는 신용사업을 영업하는 법인이고, 원고는 피고 조합에 입사하여 총무팀 팀장으로 근무하였다.', '4. 결론', '따라서 원고의 이 사건 청구는 이유 없으므로 기각하기로 하여 주문과 같이 판결한다.'];
const 글줄 = text => ({type: 'PARAGRAPH', text, align: 'LEFT', references: []});
const 요소들 = [
  {type: 'HEADER', text: '수원지방법원 안산지원 2026. 4. 23. 선고 2025가합6356 판결', tocType: 'TOC_2'}, {type: 'LINE', style: {lineType: 'SOLID'}},
  {type: 'TABLE', colgroup: [1, 4], table: [{style: null, cols: [{contents: [글줄('원고')]}, {contents: [글줄('E'), 글줄('소송대리인 법무법인 홍재')]}]}, {style: null, cols: [{contents: [글줄('피고')]}, {contents: [글줄('F조합')]}]}]},
  {type: 'HEADER', text: '주문', displayType: 'PRECEDENT_SECTION_HEADER'}, 글줄('1. 원고의 청구를 기각한다.'), {type: 'IMAGE', url: 'https://image.lbox.kr/그림.png'},
  {type: 'HEADER', text: '이유', displayType: 'PRECEDENT_SECTION_HEADER'}, ...문단들.map(글줄), {type: 'FOOTNOTE', footnoteId: '1', text: '제14조(직장 내 성희롱 발생 시 조치)'},
];
const 판결문글 = ['수원지방법원 안산지원 2026. 4. 23. 선고 2025가합6356 판결', '원고 E 소송대리인 법무법인 홍재\n피고 F조합', '주문', '1. 원고의 청구를 기각한다.',
  '이유', ...문단들, '제14조(직장 내 성희롱 발생 시 조치)'].join('\n');   // 요소들을 글로 푼 것. 표는 칸을 띄우고 행을 줄로 나눈다. 그림·줄은 글자가 없다
const 이유쿼리 = (문단 = 문단들) => 쿼리('sidebar', {isImagePrecedent: false, relations: {lowerList: []}, reasonSentences: 문단});
const 본문쿼리 = (요소 = 요소들) => 쿼리('contents', {tocId: 1, elements: 요소, limitType: null, annex: []});
const 계정쿼리 = {dehydratedAt: 0, state: {data: {plans: [{이름: '스탠다드'}]}, status: 'success'}, queryKey: ['/catalog/subscription-status'], queryHash: ''};
const 자료화면 = (쿼리들, {머리 = 화면머리, 따로온글 = '', 조각 = 2} = {}) => {
  const 자료 = '1:"$Sreact.fragment"\n' + 따로온글 + '16:' + JSON.stringify(['$', '$L1e', null, {state: {mutations: [], queries: 쿼리들}, children: '$L2b'}]) + '\n2b:["$","main",null,{}]\n';
  const 토막 = Array.from({length: 조각}, (_, k) => 자료.slice(Math.floor(자료.length * k / 조각), Math.floor(자료.length * (k + 1) / 조각)));
  return '<html><body><main>' + 머리 + '</main><script>(self.__next_f=self.__next_f||[]).push([0])</script>'
    + 토막.map(s => '<script>self.__next_f.push([1,' + JSON.stringify(s) + '])</script>').join('') + '</body></html>';
};
const 자료응답 = (쿼리들, 옵션) => async u => ({url: u, ok: true, status: 200, text: async () => 자료화면(쿼리들, 옵션)});

const 시험들 = {
  async 한도값() {
    const {ctx} = 새환경(입력);
    const 한 = ctx.본문한도;
    return 한.동시 === 1 && 한.간격 === 4000 && 한.시간당 === 250 && 한.하루 === 400 && 한.경고뒤 === 5 || JSON.stringify(한);
  },
  async 본문은간격을두고받는다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox본문'] = JSON.stringify([환경.시각() - 1000]);         // 1초 전에 다른 세션이 받은 기록
    환경.ctx.응답 = 좋은본문;
    const 시작 = 환경.시각();
    const 받은 = await 환경.ctx.lboxText(주소(3));
    const t = 기록(환경), 벌어짐 = t.slice(1).map((x, i) => x - t[i]);
    if (받은.length !== 3) return '받은 ' + 받은.length;
    if (t.length !== 4) return '기록 ' + t.length;
    if (벌어짐.some(x => x < 4000)) return '간격 ' + 벌어짐;
    return 환경.요청[0].at >= 시작 + 3000 || '첫 요청이 앞 기록에서 4초를 기다리지 않았다';
  },
  async 한도를넘기면받지않는다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox본문'] = JSON.stringify(Array.from({length: 249}, (_, i) => 환경.시각() - 60e3 - i * 1000));
    환경.ctx.응답 = 좋은본문;
    try { await 환경.ctx.lboxText(주소(2)); return '오류가 나지 않았다'; }
    catch (e) { return /본문 한도 초과/.test(e.message) && 환경.요청.length === 0 || e.message; }
  },
  async 이용확인화면이면멈추고경고를남긴다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => ({url: 'https://lbox.kr/recaptcha?from=' + u, ok: true, status: 200, text: async () => ''});
    try { await 환경.ctx.lboxText(주소(2)); return '오류가 나지 않았다'; }
    catch (e) {
      return /본문 수신 중단/.test(e.message) && !!환경.저장['lbox중단'] && !!환경.저장['lbox경고'] && 환경.요청.length === 1 || e.message;
    }
  },
  async 없는주소는멈춤표시를남기지않는다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => ({url: u, ok: false, status: 404, text: async () => '없음'});
    try { await 환경.ctx.lboxText(주소(1)); return '오류가 나지 않았다'; }
    catch (e) { return !환경.저장['lbox중단'] && !환경.저장['lbox경고'] || '표시가 남았다'; }
  },
  async 이미지판결문은멈추지않고건너뛴다() {   // 2026. 10. 1. 대구지방법원 2023나320025: '텍스트 변환 진행중' 189자 화면
    const 환경 = 새환경(입력);
    const 이미지화면 = '<main>대구지방법원 2026. 2. 5. 선고 2023나320025 판결 [임금] 텍스트 변환 진행중 본 판례는 텍스트 변환 작업 중입니다. 빠른 시일 내에 텍스트 형태로 제공될 수 있도록 최선을 다하겠습니다.</main>';
    환경.ctx.응답 = async u => (u.endsWith('1001') ? {url: u, ok: true, status: 200, text: async () => 이미지화면} : 좋은본문(u));
    const 받은 = await 환경.ctx.lboxText(주소(3));
    const 마지막 = 환경.ctx.lboxText.마지막;
    return 받은.length === 2 && 마지막.이미지.length === 1 && 마지막.이미지[0].endsWith('1001') && 마지막.못받은.length === 0
      && !환경.저장['lbox중단'] && !환경.저장['lbox경고'] && 환경.요청.length === 3 && 기록(환경).length === 3
      || JSON.stringify({받은: 받은.length, 이미지: 마지막.이미지, 못받은: 마지막.못받은, 중단: 환경.저장['lbox중단'], 요청: 환경.요청.length});
  },
  async 안내문구가없어도이미지표시가있는짧은화면은건너뛴다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => ({url: u, ok: true, status: 200, text: async () => '<main>짧은 화면</main><script>{\\"isImagePrecedent\\":true}</script>'});
    const 받은 = await 환경.ctx.lboxText(주소(1));
    return 받은.length === 0 && 환경.ctx.lboxText.마지막.이미지.length === 1 && !환경.저장['lbox중단'] || JSON.stringify(환경.ctx.lboxText.마지막);
  },
  async 글자가있는이미지판결문은본문으로받는다() {   // 글자 변환이 끝난 사건은 이미지 표시가 남아 있어도 본문이다
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => ({url: u, ok: true, status: 200, text: async () => '<main>' + 판결문 + '</main><script>{\\"isImagePrecedent\\":true}</script>'});
    const 받은 = await 환경.ctx.lboxText(주소(1));
    return 받은.length === 1 && 환경.ctx.lboxText.마지막.이미지.length === 0 || JSON.stringify(환경.ctx.lboxText.마지막);
  },
  async 그밖의짧은화면은멈추고화면글자를사유에남긴다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => ({url: u, ok: true, status: 200, text: async () => '<main>존재하지 않거나 삭제된 페이지입니다</main>'});
    try { await 환경.ctx.lboxText(주소(2)); return '오류가 나지 않았다'; }
    catch (e) {
      const 표시 = 환경.저장['lbox중단'] || '';
      return /판결문이 아닌 화면/.test(e.message) && 표시.includes('삭제된 페이지') && !환경.저장['lbox경고'] && 환경.요청.length === 1
        || JSON.stringify({오류: e.message, 표시});
    }
  },
  // 아래는 판결 글이 화면에 그려지지 않고 페이지 자료로만 온 응답이다(2026. 10. 2. 수원지방법원 안산지원 2025가합6356의 142자 화면)
  async 페이지자료에서판결문을꺼낸다() {
    const {ctx} = 새환경(입력);
    const 온 = ctx.lboxPageText(자료화면([계정쿼리, 이유쿼리(), 본문쿼리()]));
    return !!온 && 온.범위 === '판결문' && 온.글 === 판결문글 || JSON.stringify(온);
  },
  async 본문자료가빠졌으면이유문단을꺼낸다() {
    const {ctx} = 새환경(입력);
    const 온 = ctx.lboxPageText(자료화면([계정쿼리, 이유쿼리()], {조각: 3}));
    const 쿼리밖 = ctx.lboxPageText('<script>self.__next_f.push([1,' + JSON.stringify('16:{"data":{"reasonSentences":["가 [1] 나","다 \\"라\\" }"]}}\n') + '])</script>');
    return !!온 && 온.범위 === '이유' && 온.글 === 문단들.join('\n') && !JSON.stringify(온).includes('스탠다드')   // 계정 정보는 돌려주지 않는다
      && !!쿼리밖 && 쿼리밖.글 === '가 [1] 나\n다 "라" }' || JSON.stringify({온, 쿼리밖});
  },
  async 판결글이없는자료에서는아무것도꺼내지않는다() {
    const {ctx} = 새환경(입력);
    return ctx.lboxPageText(자료화면([계정쿼리, 이유쿼리([])])) === null && ctx.lboxPageText('<main>존재하지 않거나 삭제된 페이지입니다</main>') === null
      && ctx.lboxPageText('<script>self.__next_f.push([1,"16:[\\"$\\",{\\"queries\\":[{\\"queryKey\\""])</script>') === null || '무언가 꺼냈다';   // 잘린 자료
  },
  async 따로온긴문단을제자리에되돌린다() {   // 긴 글은 'id:T바이트수,글'로 따로 오고 제자리에는 "$id" 만 남는다
    const {ctx} = 새환경(입력);
    const 긴문단 = '원고는 2024. 10. 14. 해고되었다(갑 제1호증, 𠀀 표시). ' + '가나다 abc '.repeat(120);
    const 따로온글 = '25:T' + Buffer.byteLength(긴문단, 'utf8').toString(16) + ',' + 긴문단;
    const 온 = ctx.lboxPageText(자료화면([이유쿼리(['1. 기초사실', '$25', '$$100을 지급하였다', '$3f'])], {따로온글}));
    return !!온 && 온.글 === ['1. 기초사실', 긴문단, '$100을 지급하였다', '[긴 문단을 자료에서 찾지 못함]'].join('\n') || JSON.stringify(온 && 온.글.slice(0, 200));
  },
  async 화면에안그려진판결문은자료에서옮겨받고멈추지않는다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => (u.endsWith('1001') ? 자료응답([계정쿼리, 이유쿼리(), 본문쿼리()])(u) : 좋은본문(u));
    const 받은 = await 환경.ctx.lboxText(주소(3));
    const 마지막 = 환경.ctx.lboxText.마지막, 글 = (받은.find(x => x.url.endsWith('1001')) || {}).text || '';
    const 다시 = await 환경.ctx.lboxText(주소(3));                                        // 보관함에 들어갔으므로 다시 요청하지 않는다
    return 받은.length === 3 && 글 === 화면머리 + '\n[이 판결은 LBOX 화면 글이 아니라 페이지 자료의 판결문에서 옮긴 것이다]\n' + 판결문글
      && 마지막.자료본문.length === 1 && 마지막.자료본문[0].endsWith('1001') && 마지막.이유만.length === 0 && 마지막.못받은.length === 0
      && !환경.저장['lbox중단'] && !환경.저장['lbox경고'] && 환경.요청.length === 3 && 다시.length === 3 && 환경.ctx.lboxText.마지막.보관함에서 === 3
      || JSON.stringify({받은: 받은.length, 글: 글.slice(0, 200), 마지막: {...마지막, 받은: 0}, 중단: 환경.저장['lbox중단'], 요청: 환경.요청.length});
  },
  // 본문 자료가 빠지고 이유 문단만 온 응답은 2026. 10. 2. 17:54부터 받은 판례 293건 전부였고 다음 날 24시간 제한이 왔다. 받은 글은 돌려주되 첫 건에서 멈춘다(10. 7. 사용자 결정)
  async 이유문단만오면글은돌려주고첫건에서멈춘다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => (u.endsWith('1000') ? 좋은본문(u) : 자료응답([계정쿼리, 이유쿼리()])(u));
    try { await 환경.ctx.lboxText(주소(4)); return '오류가 나지 않았다'; }
    catch (e) {
      const 마지막 = 환경.ctx.lboxText.마지막, 표시 = 환경.저장['lbox중단'] || '', 글 = (마지막.받은[1] || {}).text || '';
      return /본문 수신 중단\(판결 본문이 오지 않음\(이유 문단만 옴\)/.test(e.message) && 표시.includes('판결 본문이 오지 않음') && 표시.includes('2020다1001') && !환경.저장['lbox경고']
        && 환경.요청.length === 2 && 마지막.받은.length === 2 && 마지막.못받은.length === 2 && 마지막.새로받음 === 1
        && 글 === 화면머리 + '\n[이 판결은 LBOX 화면 글이 아니라 페이지 자료의 이유 문단에서 옮긴 것이다. 주문·당사자 표시는 빠져 있다]\n' + 문단들.join('\n')
        && 마지막.이유만.length === 1 && 마지막.자료본문.length === 1 && 마지막.이유만[0].endsWith('1001')
        && 환경.보관함.size === 1 && ![...환경.보관함.keys()].some(k => k.endsWith('1001'))   // 주문이 없는 글은 보관함에 넣지 않는다. 다시 받을 때 온전한 본문을 받아야 한다
        || JSON.stringify({오류: e.message, 표시, 요청: 환경.요청.length, 마지막: {...마지막, 받은: 마지막.받은.map(x => x.text.slice(0, 160))}, 보관함: [...환경.보관함.keys()]});
    }
  },
  async 머리만온화면이200자를넘어도이유문단만온응답으로본다() {   // 2026. 10. 2. 상·하위 판결이 많아 머리가 205~225자였던 3건은 본문 없이 받은 것으로 보관되었다
    const 환경 = 새환경(입력);
    const 긴머리 = 화면머리 + '서울고등법원 2017누57976확정여부 미확인'.repeat(4);
    환경.ctx.응답 = 자료응답([이유쿼리()], {머리: 긴머리});
    try { await 환경.ctx.lboxText(주소(2)); return '오류가 나지 않았다(머리 ' + 긴머리.length + '자)'; }
    catch (e) {
      return 긴머리.length > 200 && /판결 본문이 오지 않음/.test(e.message) && 환경.요청.length === 1 && 환경.ctx.lboxText.마지막.이유만.length === 1 && 환경.보관함.size === 0
        || JSON.stringify({오류: e.message, 머리: 긴머리.length});
    }
  },
  async 자료에도판결글이없는짧은화면은종전대로멈춘다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = 자료응답([계정쿼리, 이유쿼리([])]);
    try { await 환경.ctx.lboxText(주소(2)); return '오류가 나지 않았다'; }
    catch (e) {
      const 마지막 = 환경.ctx.lboxText.마지막;
      return /판결문이 아닌 화면/.test(e.message) && (환경.저장['lbox중단'] || '').includes('관련 문서가 없습니다') && !환경.저장['lbox경고'] && 환경.요청.length === 1
        && 마지막.받은.length === 0 && 마지막.자료본문.length === 0 && 마지막.이유만.length === 0 || JSON.stringify({오류: e.message, 마지막});
    }
  },
  async 본문이화면에온판결과결정례는화면글자그대로받는다() {
    const 환경 = 새환경(입력);
    const 그려진화면 = 화면머리 + 판결문글.replace('\n제14조', '1제14조').replace(/\n/g, '');   // 짧은 판결이 화면에 그려져 온 것. 자료에도 같은 글이 있고, 화면에는 각주 번호가 더 있다
    const 결정례 = 'https://lbox.kr/decision/' + encodeURIComponent('중앙노동위원회-2020부해1'), 판정 = '중앙노동위원회 2020부해1 판정사항 판정요지 ' + '가. 판단 '.repeat(60);
    환경.ctx.응답 = async u => ({url: u, ok: true, status: 200, text: async () => (u === 결정례 ? 자료화면([이유쿼리()], {머리: 판정}) : 자료화면([이유쿼리(), 본문쿼리()], {머리: 그려진화면}))});
    const 받은 = await 환경.ctx.lboxText([주소(1)[0], 결정례]);
    const 마지막 = 환경.ctx.lboxText.마지막;
    return 그려진화면.length < 1000 && 받은.length === 2 && 받은[0].text === 그려진화면 && 받은[1].text === 판정.trim() && 마지막.자료본문.length === 0 && !환경.저장['lbox중단']
      || JSON.stringify({받은: 받은.map(x => x.text.slice(0, 80)), 마지막: {...마지막, 받은: 0}, 중단: 환경.저장['lbox중단']});
  },
  async 멈춤표시가있으면보내지않는다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox중단'] = '다른 세션';
    환경.ctx.응답 = 좋은본문;
    try { await 환경.ctx.lboxText(주소(1)); return '오류가 나지 않았다'; }
    catch (e) { return /LBOX 요청 멈춤/.test(e.message) && 환경.요청.length === 0 || e.message; }
  },
  async 받는사이다른세션이멈추면그사유를지킨다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => { 환경.저장['lbox중단'] = '다른 세션의 이용 확인 화면'; return 좋은본문(u); };
    try { await 환경.ctx.lboxText(주소(3)); return '오류가 나지 않았다'; }
    catch (e) {
      const 마지막 = 환경.ctx.lboxText.마지막;
      return 환경.저장['lbox중단'] === '다른 세션의 이용 확인 화면' && !환경.저장['lbox경고'] && 마지막.받은.length === 1 && 환경.요청.length === 1
        || JSON.stringify({중단: 환경.저장['lbox중단'], 경고: 환경.저장['lbox경고'], 받은: 마지막 && 마지막.받은.length, 요청: 환경.요청.length});
    }
  },
  async 경고뒤에는한도를낮춘다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox경고'] = String(환경.시각() - 3600e3);
    const 쓰임 = 환경.ctx.lboxUsage();
    return 쓰임.시간당 === 50 && 쓰임.하루 === 80 && 쓰임.동시 === 1 || JSON.stringify(쓰임);
  },
  async 원문열기는간격을두고기록한다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox본문'] = JSON.stringify([환경.시각() - 1000]);
    const 결과 = await 환경.ctx.원문열기('https://lbox.kr/case/대법원/2017두57318');
    const t = 기록(환경);
    return 결과.열기.endsWith('2017두57318') && t.length === 2 && t[1] - t[0] >= 4000 || JSON.stringify({결과, t});
  },
  async 원문열기도한도를지킨다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox본문'] = JSON.stringify(Array.from({length: 250}, (_, i) => 환경.시각() - 60e3 - i * 1000));
    try { await 환경.ctx.원문열기('https://lbox.kr/case/대법원/2017두57318'); return '오류가 나지 않았다'; }
    catch (e) { return /본문 한도 초과/.test(e.message) && 기록(환경).length === 250 || e.message; }
  },
  async 원문열기는경고뒤낮춘한도를쓴다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox경고'] = String(환경.시각());
    환경.저장['lbox본문'] = JSON.stringify(Array.from({length: 50}, (_, i) => 환경.시각() - 60e3 - i * 1000));
    try { await 환경.ctx.원문열기('https://lbox.kr/case/대법원/2017두57318'); return '오류가 나지 않았다'; }
    catch (e) { return /1시간 50\/50/.test(e.message) || e.message; }
  },
  async 원문열기는멈춤표시를지킨다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox중단'] = '이용 확인 화면';
    try { await 환경.ctx.원문열기('https://lbox.kr/case/대법원/2017두57318'); return '오류가 나지 않았다'; }
    catch (e) { return /LBOX 요청 멈춤/.test(e.message) && 기록(환경).length === 0 || e.message; }
  },
  async 원문열기와본문수신이같은간격을쓴다() {
    const 환경 = 새환경(입력);
    await 환경.ctx.원문열기('https://lbox.kr/case/대법원/2017두57318');
    환경.ctx.응답 = 좋은본문;
    await 환경.ctx.lboxText(주소(1));
    const t = 기록(환경);
    return t.length === 2 && t[1] - t[0] >= 4000 || JSON.stringify(t);
  },
  async 인용뽑기() {
    const {ctx} = 새환경(입력);
    const 본문 = '대법원 2010. 1. 14. 선고 2009다12345 판결 [임금]\n이유 … 대법원 2000. 11. 10. 선고 98다31493 판결, 대법원 2001. 12. 11. 선고 2001다83838, 2001다83845 판결 참조. '
      + '서울고법 2019. 5. 1. 선고 2018나2045678 판결도 같다. 원고는 2015다1234 사건을 들었다.';
    const 뽑음 = ctx.lboxCites(본문);   // 자기 사건번호와 '선고'가 붙지 않은 번호는 빼고, 쉼표로 이어진 번호는 넣는다
    const 기대 = ['대법원-98다31493', '대법원-2001다83838', '대법원-2001다83845', '서울고등법원-2018나2045678'];
    return JSON.stringify(뽑음) === JSON.stringify(기대) || JSON.stringify(뽑음);
  },
  async 인용순위() {
    const {ctx} = 새환경(입력);
    const 본문들 = [
      {url: 'https://lbox.kr/case/서울행정법원/2020구합1', text: '서울행정법원 2021. 1. 1. 선고 2020구합1 판결\n대법원 2000. 1. 1. 선고 99두1 판결, 대법원 2001. 1. 1. 선고 2000두2 판결 참조'},
      {url: 'https://lbox.kr/case/서울행정법원/2020구합2', text: '서울행정법원 2021. 2. 1. 선고 2020구합2 판결\n대법원 2001. 1. 1. 선고 2000두2 판결 참조'},
    ];
    const 순위 = ctx.lboxCiteRank(본문들, [{id: '대법원-99두1'}]);
    return 순위[0].id === '대법원-2000두2' && 순위[0].인용건수 === 2 && 순위[1].목록에있음 === true || JSON.stringify(순위);
  },
  async 수확기는결정례에피인용정렬을보내지않는다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async () => ({ok: true, status: 200, json: async () => ({count: 45, result: [{textSubInfo: {}, documentId: 'd1', documentPageType: 'DECISION', mainTitle: '가'}]})});
    const 결과 = await 환경.ctx.lboxHarvestRun(['"가"'], {type: 'DECISION', pages: 2});
    const 정렬 = 환경.요청.map(x => x.body.paging.sort);
    return 환경.요청.length === 2 && !정렬.includes('QUOTED_COUNT:DESC') && 결과.실패.length === 0 || JSON.stringify({정렬, 실패: 결과.실패});
  },
  async 수확기는여러검색어에걸린판결을앞에둔다() {
    const 환경 = 새환경(입력);
    const 줄 = (id, 피 = 0) => ({textSubInfo: {id, quoted_count: 피}, mainTitle: id});
    환경.ctx.응답 = async (url, opt) => {
      const b = JSON.parse(opt.body);
      if (b.paging.sort === 'QUOTED_COUNT:DESC') return {ok: true, status: 200, json: async () => ({count: 0, result: []})};
      const result = b.query === '"가"' ? [줄('대법원-1다1'), 줄('대법원-2다2')] : [줄('대법원-2다2'), 줄('대법원-3다3'), 줄('대법원-4다4', 900)];
      return {ok: true, status: 200, json: async () => ({count: result.length, result})};
    };
    const 결과 = await 환경.ctx.lboxHarvestRun(['"가"', '"나"'], {pages: 1, 인용망: 0});
    const 순서 = 결과.rows.map(r => r.id);
    // 두 검색어에 걸린 2다2 → 3위지만 피인용 900건인 4다4(피인용 1,000건이 1위 한 번과 비슷한 무게) → 한 검색어 1위인 1다1 → 3다3
    return JSON.stringify(순서) === JSON.stringify(['대법원-2다2', '대법원-4다4', '대법원-1다1', '대법원-3다3']) && 결과.rows.every(r => r.점수 > 0) || JSON.stringify(결과.rows.map(r => [r.id, r.점수]));
  },
  async 추가수확은피인용정렬과인용망을건너뛴다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async () => ({ok: true, status: 200, json: async () => ({count: 100, result: [{textSubInfo: {id: '대법원-2020다1', quoted_count: 50}, mainTitle: '가'}]})});
    await 환경.ctx.lboxHarvestRun(['"가"'], {pages: 3, 인용망: 0, 피인용: false});
    const 정렬 = 환경.요청.map(x => x.body.paging.sort + ' ' + x.body.paging.page + ' ' + x.body.query);
    return 환경.요청.length === 3 && 정렬.every(s => s.startsWith('SCORE:DESC') && s.endsWith('"가"')) || JSON.stringify(정렬);
  },
  // LBOX 목록의 판례 선고일은 한국 자정을 UTC 로 적은 값이라 앞 10자만 자르면 하루 이르다(2026. 10. 8. 본문 머리·법제처와 8건 대조)
  async 목록의선고일은한국날짜로옮긴다() {
    const {ctx} = 새환경(입력);
    const 판례 = d => ctx.lboxRow({mainTitle: '가', textSubInfo: {id: '대법원-2020다1', announce_date: d}}).선고일;
    const 결정 = sub => ctx.lboxRow({documentId: 'd1', documentPageType: 'LABOR_COMMISSION', mainTitle: '가', textSubInfo: sub}).선고일;
    const 온 = [
      판례('2016-12-08T15:00:00Z'), 판례('2025-12-10T15:00:00Z'),            // 서울행정법원 2015구합82051(본문 2016. 12. 9.), 대법원 2025도3844(법제처 2025. 12. 11.)
      판례('2017-12-31T15:00:00.000Z'), 판례('2016-12-09T00:00:00+09:00'),   // 해가 넘어가는 날, 한국 시각으로 적힌 값
      판례('1987-07-13T15:00:00Z'), 판례('1987-07-13T14:00:00Z'),            // 서머타임이 있던 해. 자정이 한 시간 이르게 적혀 있어도 같은 날이다
      판례('2016-12-09'), 판례(undefined), 판례(null),                        // 날짜만 온 값, 날짜가 없는 줄
      결정({decisionDate: '2023-08-10T00:00:00'}), 결정({responseDate: '2008-04-07T00:00:00'}), 결정({}),   // 결정례·유권해석은 시간대 표시 없이 온다. 옮기지 않는다
    ];
    const 기대 = ['2016-12-09', '2025-12-11', '2018-01-01', '2016-12-09', '1987-07-14', '1987-07-14', '2016-12-09', '', '', '2023-08-10', '2008-04-07', ''];
    const 줄 = ctx.lboxLines([ctx.lboxRow({mainTitle: '임금', textSubInfo: {id: '대법원-2020다1', courtType: '대법원', announce_date: '2021-03-03T15:00:00Z'}})]);
    return JSON.stringify(온) === JSON.stringify(기대) && 줄.startsWith('1 | 대법원 | 21-03-04 | 대법원-2020다1 | 임금') || JSON.stringify({온, 줄});
  },
  async 읽기줄은한줄로줄여준다() {
    const {ctx} = 새환경(입력);
    const rows = [
      {id: '대법원-2020다1', 법원: '대법원', 선고일: '2021-03-04', 사건: '임금', 피인용: 12, 확정: true, 스니펫: '가'.repeat(300)},
      {id: '서울고등법원-2019나2', 법원: '서울고등법원', 선고일: '2020-01-02', 사건: '해고무효확인', 피인용: 0, 확정: false, 스니펫: '나 다  라'},
    ];
    const 줄 = ctx.lboxLines(rows).split('\n');
    return 줄.length === 2 && 줄[0].startsWith('1 | 대법원 | 21-03-04 | 대법원-2020다1 | 임금 | 피인용 12 | 확정 | ') && 줄[0].length < 200
      && 줄[1].startsWith('2 | 서울고등법원 | 20-01-02 | 서울고등법원-2019나2 | 해고무효확인 | 나 다 라') && !줄[1].includes('확정')
      || JSON.stringify(줄);
  },
  async 수확기는실패를모아돌려준다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async (url, opt) => {
      const b = JSON.parse(opt.body);
      if (b.paging.page === 2) return {ok: false, status: 400, json: async () => ({})};
      return {ok: true, status: 200, json: async () => ({count: 45, result: [{textSubInfo: {id: '대법원-2020다1', quoted_count: 0}, mainTitle: '가'}]})};
    };
    const 결과 = await 환경.ctx.lboxHarvestRun(['"가"'], {pages: 2});
    return 결과.실패.length === 1 && /2쪽/.test(결과.실패[0]) && 결과.건수 === 1 || JSON.stringify(결과.실패);
  },
  // 아래 넷은 2026. 10. 1. 첫 검색 목록에 있던 유사 사례를 본문을 받지 않아 놓친 일을 막으려는 것이다
  async 수확기는좁은검색어의스니펫을남긴다() {
    const 환경 = 새환경(입력);
    const 줄 = (id, snippet) => ({textSubInfo: {id, quoted_count: 0}, mainTitle: '해고무효확인', snippet});
    환경.ctx.응답 = async (url, opt) => {
      const b = JSON.parse(opt.body), 넓은 = b.query === '"가"';
      return {ok: true, status: 200, json: async () => ({count: 넓은 ? 500 : 5, result: [줄('서울고등법원-2021나1', 넓은 ? '기본급 인상분 대목' : '명절상품권 대목')]})};
    };
    const 결과 = await 환경.ctx.lboxHarvestRun(['"가"', '"나"'], {pages: 1, 인용망: 0, 피인용: false});
    const r = 결과.rows[0];
    return 결과.rows.length === 1 && r.스니펫 === '명절상품권 대목' && r.스니펫건수 === 5 && r.출처 === '"가" / "나"' || JSON.stringify(r);
  },
  async 수확을모으면좁은스니펫과출처가남는다() {
    const {ctx} = 새환경(입력);
    const 기본 = {rows: [{id: 'x-1', 점수: 0.02, 출처: '"가"', 스니펫: '넓은 대목', 스니펫건수: 500}, {id: 'x-2', 점수: 0.01, 출처: '"가"', 스니펫: '넓은 대목', 스니펫건수: 500}]};
    const 추가 = {rows: [{id: 'x-2', 점수: 0.03, 출처: '"나"', 스니펫: '좁은 대목', 스니펫건수: 5}]};
    const 모은 = ctx.lboxMerge(기본, 추가);
    return 모은.length === 2 && 모은[0].id === 'x-2' && 모은[0].스니펫 === '좁은 대목' && 모은[0].출처 === '"가" / "나"' && 모은[0].점수 === 0.04
      && 기본.rows[1].스니펫 === '넓은 대목' || JSON.stringify(모은);
  },
  async 받지않은후보는사건명이아니라낱말과검색어로고른다() {
    const {ctx} = 새환경(입력);
    const rows = [
      {id: '서울고등법원-2021나1', 사건: '해고무효확인', 스니펫: '기본급 인상분', 출처: '"복지포인트" "통상임금" / "명절상품권"'},
      {id: '대법원-2010두2', 사건: '평균임금정정신청불승인취소', 스니펫: '명절 선물도 평균임금', 출처: '"복지포인트" "통상임금"'},
      {id: '대법원-2020다3', 사건: '임금', 스니펫: '정기상여금', 출처: '"복지포인트" "통상임금"'},
      {id: '대법원-2020다4', 사건: '임금', 스니펫: '선물비', 출처: '"선물비" "통상임금"'},
    ];
    const 남은 = ctx.lboxUnread(rows, {낱말: ['선물', '상품권'], 검색어: ['"명절상품권"'], 받은: ['https://lbox.kr/case/대법원/2020다4']});
    return JSON.stringify(남은.map(r => r.id)) === JSON.stringify(['서울고등법원-2021나1', '대법원-2010두2'])
      && 남은[0].걸린검색어.length === 1 && 남은[0].걸린낱말.length === 0 && 남은[1].걸린낱말[0] === '선물' || JSON.stringify(남은);
  },
  async 대목뽑기는겹치는곳을합친다() {
    const {ctx} = 새환경(입력);
    const text = '머리 '.repeat(100) + '가'.repeat(1000) + '명절상품권' + '나'.repeat(100) + '상품권' + '다'.repeat(2000) + '상품권' + '라'.repeat(500);
    const 뽑음 = ctx.lboxExcerpt(text, ['명절상품권', '상품권'], 200, 6);
    return 뽑음.대목.length === 2 && 뽑음.곳 === 4 && 뽑음.남은대목 === 0 && 뽑음.대목[0].includes('명절상품권') && 뽑음.머리.startsWith('머리')
      || JSON.stringify({곳: 뽑음.곳, 대목수: 뽑음.대목.length, 남은: 뽑음.남은대목});
  },
  // 아래 셋은 판결 전문 PDF 를 한꺼번에 받아 압축파일 하나로 내려받는 9항 코드이다(2026. 10. 2.)
  async 압축파일은표준형식이다() {
    const {ctx} = 새환경(입력);
    const 글 = s => new TextEncoder().encode(s);
    const z = ctx.lboxZip([{name: '각주01_대법원 2016다48785 판결.pdf', data: 글('hello')}, {name: 'b.pdf', data: 글('%PDF-1.7 x')}]);
    const u = new Uint8Array(await z.arrayBuffer()), v = new DataView(u.buffer), 끝 = u.length - 22;
    압축시험 = Buffer.from(u).toString('base64');                                         // test_lbox_code.py 가 zipfile 로 다시 연다
    return v.getUint32(0, true) === 0x04034b50 && v.getUint16(6, true) === 0x0800 && v.getUint32(14, true) === 0x3610a686   // crc32('hello')
      && v.getUint32(끝, true) === 0x06054b50 && v.getUint16(끝 + 10, true) === 2
      || JSON.stringify({머리: v.getUint32(0, true).toString(16), crc: v.getUint32(14, true).toString(16), 개수: v.getUint16(끝 + 10, true)});
  },
  async 판결PDF를받아압축파일하나로내려받는다() {
    const 환경 = 새환경(입력);
    const pdf = new TextEncoder().encode('%PDF-1.7 가짜 판결문 %%EOF');
    환경.ctx.응답 = async u => (u.includes(encodeURIComponent('대법원-2026다3'))
      ? {url: u, ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0)}
      : {url: u, ok: true, status: 200, arrayBuffer: async () => pdf.buffer.slice(0)});
    const 받음 = await 환경.ctx.lboxPdfZip([['대법원-2020다1', '각주01_가.pdf'], ['대법원-2026다3', '각주02_나.pdf'], ['서울고등법원-2021나2', '각주03_다.pdf']], '묶음.zip');
    const t = 기록(환경), 벌어짐 = t.slice(1).map((x, i) => x - t[i]);
    return 받음.끝 === true && 받음.받은 === 2 && 받음.결과[0][1] === 'ok' && 받음.결과[1][1] === 'status 404' && 받음.결과[2][1] === 'ok'
      && 환경.요청.length === 3 && 환경.요청.every(x => x.method === 'POST' && x.url.endsWith('/pdf'))
      && t.length === 3 && 벌어짐.every(x => x >= 4000) && 환경.내려받기.length === 1 && 환경.내려받기[0].download === '묶음.zip' && !환경.저장['lbox중단']
      || JSON.stringify({받음, 요청: 환경.요청.length, 기록: t.length, 벌어짐, 내려받기: 환경.내려받기});
  },
  async 이용확인화면이면PDF받기를멈춘다() {
    const 환경 = 새환경(입력);
    환경.ctx.응답 = async u => ({url: 'https://lbox.kr/recaptcha?from=' + u, ok: true, status: 200, arrayBuffer: async () => new ArrayBuffer(0)});
    const 받음 = await 환경.ctx.lboxPdfZip([['대법원-2020다1', '가.pdf'], ['대법원-2020다2', '나.pdf']]);
    return 받음.받은 === 0 && 받음.결과.length === 1 && 받음.결과[0][1] === '이용 확인 화면' && !!환경.저장['lbox중단'] && !!환경.저장['lbox경고']
      && 환경.요청.length === 1 && 환경.내려받기.length === 0
      || JSON.stringify({받음, 중단: 환경.저장['lbox중단'], 요청: 환경.요청.length});
  },
};

let 입력, 압축시험 = '';
(async () => {
  입력 = JSON.parse(require('fs').readFileSync(0, 'utf8'));
  const 결과 = [];
  for (const [name, fn] of Object.entries(시험들)) {
    try { const r = await fn(); 결과.push({name, ok: r === true, detail: r === true ? '' : String(r)}); }
    catch (e) { 결과.push({name, ok: false, detail: 'throw ' + e.message}); }
  }
  결과.push({name: '_압축파일', ok: true, detail: 압축시험});
  process.stdout.write(JSON.stringify(결과));
})();
