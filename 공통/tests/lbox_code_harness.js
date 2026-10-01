// lbox-검색 스킬의 브라우저 코드를 node 에서 가짜 LBOX 로 돌려 본다. test_lbox_code.py 가 부른다.
// 입력(stdin): {main, harvest, cites, opener} — SKILL.md 의 코드 블록 원문. 출력(stdout): [{name, ok, detail}]
const vm = require('vm');

function 새환경(blocks) {
  let 지금 = Date.UTC(2026, 8, 19, 0, 0, 0);
  const 저장 = {};
  const 요청 = [];
  class 가짜날짜 extends Date {
    constructor(...a) { if (a.length) super(...a); else super(지금); }
    static now() { return 지금; }
  }
  const ctx = {
    console, JSON, Math, Promise, Object, Array, Set, Map, Error, RegExp, String, Number,
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
        const text = html.replace(/<[^>]+>/g, '');
        return {querySelectorAll: sel => (sel.startsWith('script') ? [] : [{innerText: text, textContent: text}])};
      }
    },
    fetch: async (url, opt = {}) => {
      요청.push({url, method: opt.method || 'GET', body: opt.body ? JSON.parse(opt.body) : null, at: 지금});
      return ctx.응답(url, opt);
    },
    응답: async () => { throw new Error('응답이 정해지지 않았다'); },
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const code of [blocks.main, blocks.harvest, blocks.cites]) vm.runInContext(code, ctx);
  const m = blocks.opener.match(/await \((async url => \{[\s\S]*\})\)\('[^']*'\);?/);
  if (!m) throw new Error('원문 열기 블록 모양이 다르다');
  vm.runInContext('globalThis.원문열기 = (' + m[1] + ');', ctx);
  return {ctx, 저장, 요청, 시각: () => 지금, 시각바꾸기: t => { 지금 = t; }};
}

const 판결문 = '대법원 2010. 1. 14. 선고 2009다12345 판결 [임금] ' + '이유 가. 판단 '.repeat(40);
const 좋은본문 = url => ({url, ok: true, status: 200, text: async () => '<main>' + 판결문 + '</main>'});
const 기록 = 환경 => JSON.parse(환경.저장['lbox본문'] || '[]');
const 주소 = n => Array.from({length: n}, (_, i) => 'https://lbox.kr/case/대법원/2020다' + (1000 + i));

const 시험들 = {
  async 한도값() {
    const {ctx} = 새환경(입력);
    const 한 = ctx.본문한도;
    return 한.동시 === 1 && 한.간격 === 4000 && 한.시간당 === 450 && 한.하루 === 3000 && 한.경고뒤 === 5 || JSON.stringify(한);
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
    환경.저장['lbox본문'] = JSON.stringify(Array.from({length: 449}, (_, i) => 환경.시각() - 60e3 - i * 1000));
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
    return 쓰임.시간당 === 90 && 쓰임.하루 === 600 && 쓰임.동시 === 1 || JSON.stringify(쓰임);
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
    환경.저장['lbox본문'] = JSON.stringify(Array.from({length: 450}, (_, i) => 환경.시각() - 60e3 - i * 1000));
    try { await 환경.ctx.원문열기('https://lbox.kr/case/대법원/2017두57318'); return '오류가 나지 않았다'; }
    catch (e) { return /본문 한도 초과/.test(e.message) && 기록(환경).length === 450 || e.message; }
  },
  async 원문열기는경고뒤낮춘한도를쓴다() {
    const 환경 = 새환경(입력);
    환경.저장['lbox경고'] = String(환경.시각());
    환경.저장['lbox본문'] = JSON.stringify(Array.from({length: 90}, (_, i) => 환경.시각() - 60e3 - i * 1000));
    try { await 환경.ctx.원문열기('https://lbox.kr/case/대법원/2017두57318'); return '오류가 나지 않았다'; }
    catch (e) { return /1시간 90\/90/.test(e.message) || e.message; }
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
};

let 입력;
(async () => {
  입력 = JSON.parse(require('fs').readFileSync(0, 'utf8'));
  const 결과 = [];
  for (const [name, fn] of Object.entries(시험들)) {
    try { const r = await fn(); 결과.push({name, ok: r === true, detail: r === true ? '' : String(r)}); }
    catch (e) { 결과.push({name, ok: false, detail: 'throw ' + e.message}); }
  }
  process.stdout.write(JSON.stringify(결과));
})();
