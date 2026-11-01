"""근로복지공단 산재판례·심사결정서와 산업재해보상보험재심사위원회 재결사례 조회 도구.

로그인이 없고 LBOX 본문 한도를 쓰지 않는다. 받은 글은 --out 폴더에 건마다 md 로 쓰고, 파일 머리에
cite_check.py 가 읽는 사건 표시와 선고일을 적는다. 공공 누리집이므로 건마다 간격을 두고 차례로 보낸다.

  산재판례  https://sanjaecase.comwel.or.kr     판결 원문, 심급별 판결(1심·2심·3심)
  심사결정  https://simsacase.comwel.or.kr      근로복지공단 심사결정 원문(2017~2021년)
  재결사례  https://www.iaciac.go.kr             재결일·심리결과·상병명·쟁점(이유 전문은 없다)
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36'
JUDGE = 'https://sanjaecase.comwel.or.kr'
SIMSA = 'https://simsacase.comwel.or.kr'
IACIAC = 'https://www.iaciac.go.kr'
DELAY = 0.5         # 호출 사이 간격(초)
PAGE = 200          # 산재판례 목록 한 쪽의 최대 건수
ID = re.compile(r"goView\('([^']+)'\)")


def fetch(url, data=None, referer=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={'User-Agent': UA, 'Referer': referer or url})
    with urllib.request.urlopen(req, timeout=60) as res:
        return res.read().decode('utf-8', 'replace')


def plain(x):
    """HTML 을 줄 단위 글자로 바꾼다. 주석·스크립트는 지운다."""
    x = re.sub(r'<!--.*?-->', '', x, flags=re.S)
    x = re.sub(r'<script.*?</script>|<style.*?</style>', '', x, flags=re.S)
    x = re.sub(r'<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>|</dd>|</dt>', '\n', x)
    x = html.unescape(re.sub(r'<[^>]+>', ' ', x))
    x = re.sub(r'[ \t\xa0]+', ' ', x)
    return re.sub(r'\n\s*\n+', '\n', x).strip()


def day(s):
    """'2019. 05. 23' → '2019. 5. 23.'"""
    m = re.search(r'(\d{4})\s*[.\-]\s*(\d{1,2})\s*[.\-]\s*(\d{1,2})', s or '')
    return '%s. %d. %d.' % (m.group(1), int(m.group(2)), int(m.group(3))) if m else ''


def save(out, name, text):
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return path


def judge_rows_search(query):
    """통합검색. 검색어 형식은 q=query†검색어이고, 띄어 쓴 낱말은 AND 로 걸리지 않아(적응장애 258건, 적응장애 요양기간 909건) 낱말 하나씩 받아 글에서 거른다."""
    rows, seen, total, p = [], set(), None, 1
    q = urllib.parse.quote('query†' + query)
    while True:
        t = fetch('%s/search/judgeList?q=%s&pageIndex=%d&pageUnit=%d' % (JUDGE, q, p, PAGE))
        if total is None:
            m = re.search(r'allNum">([\d,]+)<', t)
            total = int(m.group(1).replace(',', '')) if m else 0
        new = 0
        for m in re.finditer(r"""<a href="javascript:goView\('([^']+)'\)"[^>]*>'?(.*?)</a>\s*</p>\s*<p class="highlight-text">(.*?)</p>""", t, re.S):
            if m.group(1) in seen:
                continue
            seen.add(m.group(1)); new += 1
            rows.append({'id': m.group(1), '제목': html.unescape(m.group(2)).strip(), '스니펫': plain(m.group(3))})
        if not new or len(rows) >= total:
            return total, rows
        p += 1
        time.sleep(DELAY)


def judge_rows_menu(gubun, gubun2):
    """분류 목록. 표에 없는 상병명이 주석으로 함께 온다."""
    rows, seen, total, p = [], set(), None, 1
    while True:
        t = fetch('%s/service/dataList?gubun=%s&gubun2=%s&pageIndex=%d&pageUnit=%d' % (JUDGE, urllib.parse.quote(gubun), urllib.parse.quote(gubun2), p, PAGE))
        if total is None:
            m = re.search(r'>\s*([\d,]+)\s*</[a-z]+>\s*건', re.sub(r'<!--.*?-->', '', t, flags=re.S))
            total = int(m.group(1).replace(',', '')) if m else 0
        new = 0
        for tr in re.findall(r'<tr>(.*?)</tr>', t, re.S):
            m = ID.search(tr)
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1)); new += 1
            sick = re.search(r'<!--\s*<td>(.*?)</td>\s*-->', tr, re.S)
            cells = [plain(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', re.sub(r'<!--.*?-->', '', tr, flags=re.S), re.S)]
            rows.append({'id': m.group(1), '상병': html.unescape(sick.group(1)).strip() if sick else '',
                         '사건명': cells[3] if len(cells) > 3 else '', '심급': re.sub(r'\s+', ' ', cells[4]) if len(cells) > 4 else ''})
        if not new:                    # 건수 표시가 빠질 때가 있어 새 항목이 없을 때까지 넘긴다
            return total or len(rows), rows
        p += 1
        time.sleep(DELAY)


def judge_show(i):
    """판결 하나를 받아 (머리·글, 심급 id 목록)을 돌려준다. 없는 사건은 500 이 온다. id 는 '사건번호_법원'이다."""
    v = fetch('%s/service/dataView?id=%s' % (JUDGE, urllib.parse.quote(i)), referer=JUDGE + '/')
    tiers = list(dict.fromkeys(ID.findall(v)))
    t = plain(v)
    end = t.find('맨 위로 이동')
    t = t[:end].strip() if end > 0 else t
    start = t.find('만족도 조사')
    t = t[start + len('만족도 조사'):].strip() if start >= 0 else t
    no, _, court = i.partition('_')
    m = re.search(r'판결선고\s*([\d. ]+)', t)
    when = day(m.group(1)) if m else (day(t[t.rfind('주문'):]) if '대법원' in court else '')
    mark = '%s %s 선고 %s 판결' % (court, when, no) if when else '%s %s 판결' % (court, no)
    head = '# %s\n\n표시: %s\n\n출처: %s/service/dataView?id=%s\n\n선고일: %s\n\n심급: %s\n\n' % (i, mark, JUDGE, i, when or '원문에 표시 없음', ', '.join(tiers) or '표시 없음')
    return head + t + '\n', tiers


def simsa_rows(query):
    """심사결정 검색. 검색어는 띄어쓰기까지 붙은 구절로 걸린다(적응장애 요양기간 0건, 요양기간 단축 120건). 항목에 검색어가 처음 나온 곳부터의 글이 함께 온다."""
    t = fetch('%s/service/searchList?q=%s&pageIndex=1&pageUnit=1000' % (SIMSA, urllib.parse.quote(query)))
    return list(dict.fromkeys(re.findall(r"goViewNew\('(\d+)'\)", t)))


def simsa_show(no):
    """심사결정 하나. 응답 끝에 화면에 나오지 않는 표본 글이 붙으므로 첫 '소송을 제기할 수 있습니다.'까지만 쓴다."""
    t = plain(fetch('%s/service/dataView?id=%s' % (SIMSA, no), referer=SIMSA + '/'))
    end = t.find('소송을 제기할 수 있습니다.')
    t = t[:end + len('소송을 제기할 수 있습니다.')] if end >= 0 else t
    m = re.search(r'결정일자\s*([\d.\- ]+)', t)
    when = day(m.group(1)) if m else ''
    mark = '근로복지공단 %s자 심사결정 %s' % (when, no)
    return '# 근로복지공단 심사결정 %s\n\n표시: %s\n\n출처: %s/service/dataView?id=%s\n\n%s\n' % (no, mark, SIMSA, no, t)


def jaegyeol_rows(keyword='', result=''):
    """재결사례 목록. 검색칸은 사건명·상병명에만 걸리고 쟁점에는 걸리지 않는다(적응장애 6건, 쟁점까지 보면 8건, 요양기간 0건). --상세로 모두 받아 거른다."""
    rows, total, p = [], None, 1
    while True:
        t = fetch(IACIAC + '/adjudication/main.do', {'pageUnit': 50, 'pageIndex': p, 'searchKeyword': keyword, 'searchProcess': result})
        if total is None:
            m = re.search(r'전체 <span class="txt-blue">([\d,]+)</span>', t)
            total = int(m.group(1).replace(',', '')) if m else 0
        items = re.findall(r'data-idx="(\d+)".*?<h4 class="board-list__tit">(.*?)</h4>(.*?)</a>', t, re.S)
        for idx, title, rest in items:
            dd = [re.sub(r'\s+', ' ', plain(x)) for x in re.findall(r'<dd class="board-list__dd">(.*?)</dd>', rest, re.S)]
            rows.append({'idx': int(idx), '사건명': html.unescape(title).strip(), '분류': dd[0] if dd else '',
                         '재결일': dd[1] if len(dd) > 1 else '', '심리결과': dd[2] if len(dd) > 2 else ''})
        if not items or len(rows) >= total:
            return total, rows
        p += 1
        time.sleep(DELAY)


def jaegyeol_show(idx):
    t = fetch('%s/adjudication/view.do?idx=%s' % (IACIAC, idx))
    out = {}
    for a, b in re.findall(r'<dt class="table__col__tit">(.*?)</dt>\s*<dd class="table__col__cont">(.*?)</dd>', t, re.S):
        b = re.sub(r'\s+', ' ', plain(html.unescape(b)))
        b = re.sub(r'&[a-z0-9]+', ' ', b)                       # 누리집 글에서 문장부호가 빠지고 'p…p', '&lsquo' 같은 찌꺼기가 남아 있다
        out[a.strip()] = '' if b.strip() == 'pnullp' else re.sub(r'^p\s*(?=[^a-z])|\s*p$', '', b.strip()).strip()
    return out


def cmd_judge_list(a):
    total, rows = judge_rows_menu(a.분류[0], a.분류[1] if len(a.분류) > 1 else '') if a.분류 else judge_rows_search(a.검색어)
    print('전체 %d, 받은 목록 %d' % (total, len(rows)))
    name = '목록_%s.json' % re.sub(r'[\\/:*?"<>| ]+', '_', a.검색어 or '_'.join(a.분류))
    print(save(a.out, name, json.dumps(rows, ensure_ascii=False, indent=1)))
    if a.본문:
        judge_many(a.out, [r['id'] for r in rows], a.심급)


def judge_many(out, ids, tiers=False):
    done, miss, queue, seen = 0, [], list(ids), set(ids)
    while queue:
        i = queue.pop(0)
        path = os.path.join(out, i + '.md')
        if os.path.exists(path):       # 이미 받은 것은 다시 보내지 않는다
            if tiers:
                with open(path, encoding='utf-8') as f:
                    m = re.search(r'^심급: (.*)$', f.read(2000), re.M)
                for t in (m.group(1).split(', ') if m else []):
                    if '_' in t and t not in seen:
                        seen.add(t); queue.append(t)
            continue
        try:
            text, found = judge_show(i)
            save(out, i + '.md', text)
            done += 1
            if tiers:
                for t in found:
                    if t not in seen:
                        seen.add(t); queue.append(t)
        except urllib.error.HTTPError as e:
            miss.append('%s(%s)' % (i, e.code))
        if done and done % 50 == 0:
            print('  받음 %d, 남음 %d' % (done, len(queue)), flush=True)
        time.sleep(DELAY)
    print('새로 받음 %d, 없음 %d %s' % (done, len(miss), ' '.join(miss)))


def cmd_judge(a):
    judge_many(a.out, a.id, a.심급)


def cmd_simsa(a):
    for no in a.번호:
        print(save(a.out, no + '.md', simsa_show(no)))
        time.sleep(DELAY)


def cmd_simsa_list(a):
    rows = simsa_rows(a.검색어)
    print('받은 목록 %d' % len(rows))
    print(save(a.out, '심사목록_%s.json' % re.sub(r'[\\/:*?"<>| ]+', '_', a.검색어), json.dumps(rows, ensure_ascii=False, indent=1)))
    if a.본문:
        for no in rows:
            if not os.path.exists(os.path.join(a.out, no + '.md')):
                save(a.out, no + '.md', simsa_show(no))
                time.sleep(DELAY)


def cmd_jaegyeol(a):
    total, rows = jaegyeol_rows(a.검색어 or '', a.심리결과 or '')
    print('전체 %d, 받은 목록 %d' % (total, len(rows)))
    if a.상세:
        for n, r in enumerate(rows, 1):
            r.update(jaegyeol_show(r['idx']))
            if n % 50 == 0:
                print('  상세 %d' % n, flush=True)
            time.sleep(DELAY)
    print(save(a.out, '재결사례_%s.json' % (a.검색어 or '전체'), json.dumps(rows, ensure_ascii=False, indent=1)))


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = p.add_subparsers(dest='cmd', required=True)
    s = subs.add_parser('판례찾기', help='산재판례 통합검색 또는 분류 목록을 받는다')
    s.add_argument('검색어', nargs='?', default='')
    s.add_argument('--분류', nargs='+', help='요양 정신질환 처럼 메뉴 이름을 준다')
    s.add_argument('--본문', action='store_true', help='목록의 판결 원문을 모두 받는다')
    s.add_argument('--심급', action='store_true', help='심급 표시에 나온 다른 심급 판결도 받는다')
    s.add_argument('--out', required=True); s.set_defaults(fn=cmd_judge_list)
    s = subs.add_parser('판례', help='판결 원문을 받는다. id 는 2018구단57530_서울행정법원 형식이다')
    s.add_argument('id', nargs='+'); s.add_argument('--심급', action='store_true', help='다른 심급 판결도 받는다')
    s.add_argument('--out', required=True); s.set_defaults(fn=cmd_judge)
    s = subs.add_parser('심사찾기', help='심사결정 번호 목록을 받는다')
    s.add_argument('검색어'); s.add_argument('--본문', action='store_true', help='목록의 원문을 모두 받는다')
    s.add_argument('--out', required=True); s.set_defaults(fn=cmd_simsa_list)
    s = subs.add_parser('심사', help='심사결정 원문을 받는다')
    s.add_argument('번호', nargs='+'); s.add_argument('--out', required=True); s.set_defaults(fn=cmd_simsa)
    s = subs.add_parser('재결', help='재심사위원회 재결사례 목록을 받는다')
    s.add_argument('--검색어'); s.add_argument('--심리결과', choices=['취소', '기각', '각하', '일부취소'])
    s.add_argument('--상세', action='store_true', help='건마다 상병명·쟁점까지 받는다')
    s.add_argument('--out', required=True); s.set_defaults(fn=cmd_jaegyeol)
    a = p.parse_args()
    if a.cmd == '판례찾기' and not a.검색어 and not a.분류:
        p.error('검색어나 --분류를 준다')
    a.fn(a)


if __name__ == '__main__':
    main()
