"""공공데이터포털(data.go.kr) API 조회.

둘을 다룬다. 법제처 API와는 다른 포털이므로 인증키가 따로 있고, **인증키는 계정에 하나지만
API마다 따로 활용신청해야 한다.** 신청하지 않은 API는 '등록되지 않은 서비스키'로 막힌다.

- 국세청 사업자등록 상태조회: 휴업·폐업 여부. 해고 뒤 위장폐업, 구제이익, 체당금, 상대방 실재 확인
- 국민연금 가입 사업장 내역: 사업장의 국민연금 가입자 수. 사업장 규모를 가늠할 때
  (**가입자 수는 근로기준법상 상시 근로자 수가 아니다.** 아래 '한계'를 읽는다)

인증키와 받은 결과는 PC마다 %LOCALAPPDATA%\\노동사건자동화\\ 아래에 두고 OneDrive에 올리지 않는다.
인증키를 채팅에 받거나 대신 입력하지 않는다.

    python 공통/scripts/datago.py set-key 인증키
    python 공통/scripts/datago.py check
    python 공통/scripts/datago.py 사업자 1234567890 --out 결과.json
    python 공통/scripts/datago.py 사업장 --이름 "법무법인 평안" --상세
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

STATUS_URL = 'https://api.odcloud.kr/api/nts-businessman/v1/status'
NPS_BASE = 'https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2'   # V1은 폐기되었다(2026. 9. 20. 실측)
MAX_PER_CALL = 100      # 국세청 제한: 1회 100건, 1일 100만 건
DELAY = 0.3             # 호출 사이 간격(초)
OPENER = urllib.request.urlopen
CALLS = {'n': 0}


class DataGoError(Exception):
    pass


def home():
    base = os.environ.get('DATAGO_HOME') or Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / '노동사건자동화'
    return Path(base)


def key_value(given=None):
    if given:
        return given
    if os.environ.get('DATAGO_KEY'):
        return os.environ['DATAGO_KEY']
    config = home() / 'datago.json'
    if config.is_file():
        value = json.loads(config.read_text(encoding='utf-8')).get('KEY')
        if value:
            return value
    raise DataGoError('인증키가 없습니다. data.go.kr 에서 활용신청한 뒤 '
                      'python 공통/scripts/datago.py set-key 인증키 로 저장하십시오.')


def set_key(value):
    path = home() / 'datago.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'KEY': value.strip()}, ensure_ascii=False), encoding='utf-8')
    return {'저장': str(path)}


def normalize_no(value):
    digits = re.sub(r'\D', '', str(value))
    if len(digits) != 10:
        raise DataGoError(f'사업자등록번호는 숫자 10자리입니다: {value}')
    return digits


def check_digit_ok(digits):
    """사업자등록번호 끝자리는 앞 아홉 자리로 정해지는 검증번호이다.

    가중치 1·3·7·1·3·7·1·3·5를 곱해 더하고, 아홉째 자리×5의 십의 자리를 더한 뒤
    10에서 끝자리를 뺀 값이 검증번호이다. 이 계산이 맞지 않으면 실재할 수 없는 번호이므로
    '국세청에 등록되지 않았다'가 아니라 '번호가 잘못되었다'로 읽어야 한다.
    """
    d = [int(c) for c in digits]
    weights = (1, 3, 7, 1, 3, 7, 1, 3, 5)
    total = sum(a * b for a, b in zip(d[:9], weights)) + (d[8] * 5) // 10
    return (10 - total % 10) % 10 == d[9]


def call(url, body, key):
    # 인증키는 발급 화면에서 Encoding 값으로 주는 경우가 많아 두 번 인코딩되지 않게 한 번 풀고 다시 넣는다
    query = urllib.parse.urlencode({'serviceKey': urllib.parse.unquote(key), 'returnType': 'JSON'})
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(url + '?' + query, data=data, method='POST',
                                     headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                                              'User-Agent': 'Mozilla/5.0 (labor-workflow)'})
    for attempt in range(3):
        try:
            with OPENER(request, timeout=30) as response:
                raw = response.read()
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', 'replace')[:200] if hasattr(exc, 'read') else ''
            if exc.code in (400, 401, 403):
                raise DataGoError(f'HTTP {exc.code}: 인증키나 신청 상태를 확인하십시오. {detail}') from exc
            if attempt == 2:
                raise DataGoError(f'HTTP {exc.code}: {detail}') from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise DataGoError(f'연결 실패: {exc}') from exc
        time.sleep(1.5 * (attempt + 1))
    CALLS['n'] += 1
    time.sleep(DELAY)
    text = raw.decode('utf-8', 'replace')
    try:
        return json.loads(text)
    except ValueError as exc:
        raise DataGoError('JSON이 아닌 응답: ' + re.sub(r'\s+', ' ', text)[:200]) from exc


def status(numbers, *, key=None):
    """사업자등록번호의 휴업·폐업 여부를 받는다. 번호는 하이픈이 있어도 된다."""
    key = key_value(key)
    numbers = [normalize_no(n) for n in numbers]
    # 검증번호가 틀린 번호는 국세청에 물어도 '등록되지 않은 번호'로 오므로, 먼저 갈라내어 사유를 달리 적는다
    형식오류 = [n for n in numbers if not check_digit_ok(n)]
    numbers = [n for n in numbers if check_digit_ok(n)]
    rows, 조회안됨 = [], []
    for n in 형식오류:
        rows.append({'사업자등록번호': n, '상태': '사업자등록번호 형식 오류(검증번호 불일치)', '상태코드': '',
                     '과세유형': '', '폐업일자': '', '비고': '실재할 수 없는 번호이다. 국세청에 없는 것이 아니라 번호가 잘못된 것이므로 다시 확인한다'})
    for i in range(0, len(numbers), MAX_PER_CALL):
        묶음 = numbers[i:i + MAX_PER_CALL]
        data = call(STATUS_URL, {'b_no': 묶음}, key)
        if str(data.get('status_code', '')).upper() not in ('OK', ''):
            raise DataGoError(f"국세청 응답 오류: {data.get('status_code')} {str(data)[:200]}")
        받은 = {item.get('b_no'): item for item in data.get('data', [])}
        for no in 묶음:
            item = 받은.get(no)
            if not item or not item.get('b_stt_cd'):
                조회안됨.append(no)
                rows.append({'사업자등록번호': no, '상태': '국세청에 등록되지 않은 번호', '상태코드': '',
                             '과세유형': (item or {}).get('tax_type', ''), '폐업일자': ''})
                continue
            rows.append({'사업자등록번호': no,
                         '상태': item.get('b_stt') or '',
                         '상태코드': item.get('b_stt_cd') or '',
                         '과세유형': item.get('tax_type') or '',
                         '폐업일자': ymd(item.get('end_dt')),
                         '과세유형전환일자': ymd(item.get('tax_type_change_dt')),
                         '세금계산서적용일자': ymd(item.get('invoice_apply_dt'))})
    return {'조회건수': len(numbers) + len(형식오류), '받은건수': len(rows) - len(조회안됨) - len(형식오류),
            '조회안됨': 조회안됨, '형식오류': 형식오류, '호출': CALLS['n'], 'rows': rows}


def ymd(value):
    digits = re.sub(r'\D', '', str(value or ''))
    return f'{digits[:4]}-{digits[4:6]}-{digits[6:8]}' if len(digits) == 8 else ''


NPS_FIELDS = {'seq': 'seq', 'wkplNm': '사업장명', 'bzowrRgstNo': '사업자번호앞6', 'wkplRoadNmDtlAddr': '주소',
              'jnngpCnt': '가입자수', 'crrmmNtcAmt': '당월고지금액', 'vldtVlKrnNm': '업종',
              'wkplIntpCd': '업종코드', 'adptDt': '등록일', 'scsnDt': '탈퇴일',
              'wkplJnngStcd': '가입상태코드', 'wkplStylDvcd': '사업장유형코드',
              'ldongAddrMgplDgCd': '시도코드', 'ldongAddrMgplSgguCd': '시군구코드',
              'ldongAddrMgplSgguEmdCd': '읍면동코드', 'dataCrtYm': '자료기준월'}


def call_get(url, params, key):
    """공공데이터포털의 GET 계열 API. JSON으로 달라 하고 XML이 오면 그것도 읽는다."""
    query = urllib.parse.urlencode({'serviceKey': urllib.parse.unquote(key), **params})
    request = urllib.request.Request(url + '?' + query,
                                     headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0 (labor-workflow)'})
    try:
        with OPENER(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace') if hasattr(exc, 'read') else ''
        raise DataGoError(nps_reason(detail) or f'HTTP {exc.code}: {detail[:200]}') from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DataGoError(f'연결 실패: {exc}') from exc
    CALLS['n'] += 1
    time.sleep(DELAY)
    text = raw.decode('utf-8', 'replace')
    reason = nps_reason(text)
    if reason:
        raise DataGoError(reason)
    try:
        return json.loads(text)
    except ValueError:
        return xml_to_dict(text)


def nps_reason(text):
    """포털 공통 오류 봉투를 사람이 읽을 말로 바꾼다."""
    if 'SERVICE_KEY_IS_NOT_REGISTERED' in text or '등록되지 않은 서비스키' in text:
        return ('이 API에 활용신청이 되어 있지 않습니다. data.go.kr 에서 '
                "'국민연금공단_국민연금 가입 사업장 내역'을 활용신청하십시오(인증키는 그대로 씁니다).")
    if 'NO_OPENAPI_SERVICE_ERROR' in text:
        return '해당 오픈API 서비스가 없거나 폐기되었습니다. 주소를 확인하십시오.'
    for code in ('LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS', 'SERVICE_ACCESS_DENIED'):
        if code in text:
            return f'포털이 요청을 막았습니다({code}).'
    return ''


def xml_to_dict(text):
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DataGoError('JSON도 XML도 아닌 응답: ' + re.sub(r'\s+', ' ', text)[:200]) from exc

    def walk(node):
        children = list(node)
        if not children:
            return (node.text or '').strip()
        if len({c.tag for c in children}) == 1 and len(children) > 1:
            return [walk(c) for c in children]
        return {c.tag: walk(c) for c in children}
    return {root.tag: walk(root)}


def nps_items(data):
    """{'response': {'body': {'items': {'item': [...]}, 'totalCount': n}}} 에서 목록과 전체 건수를 꺼낸다."""
    body = (data.get('response') or {}).get('body') or {}
    header = (data.get('response') or {}).get('header') or {}
    if str(header.get('resultCode', '00')).lstrip('0') not in ('', '0'):
        raise DataGoError(f"국민연금 응답 오류: {header.get('resultCode')} {header.get('resultMsg', '')}")
    items = body.get('items') or {}
    items = items.get('item') if isinstance(items, dict) else items
    if items is None or items == '':
        items = []
    if isinstance(items, dict):
        items = [items]
    total = re.sub(r'\D', '', str(body.get('totalCount', '')))
    return items, int(total or 0)


def nps_row(item):
    row = {NPS_FIELDS.get(k, k): v for k, v in item.items()}
    for 칸 in ('가입자수', '당월고지금액'):
        digits = re.sub(r'\D', '', str(row.get(칸, '')))
        row[칸] = int(digits) if digits else None
    row['사업장유형'] = {'1': '법인'}.get(str(row.get('사업장유형코드', '')), '개인')
    row['가입상태'] = {'1': '등록'}.get(str(row.get('가입상태코드', '')), '탈퇴')
    if '사업자번호앞6' in row:      # 응답은 '116810****' 꼴로 뒤를 가린다
        row['사업자번호앞6'] = re.sub(r'\D', '', str(row['사업자번호앞6']))[:6]
    for 칸 in ('등록일', '탈퇴일'):
        if 칸 in row:
            # 탈퇴하지 않은 사업장의 탈퇴일은 '00010101'로 온다(2026. 9. 20. 실측)
            row[칸] = '' if str(row[칸]).startswith('0001') else ymd(row[칸])
    return row


def workplaces(*, name=None, bno=None, detail=False, latest_only=False, limit=24, key=None):
    """국민연금 가입 사업장을 이름이나 사업자등록번호 앞 6자리로 찾는다.

    한 사업장이 자료기준월마다 한 줄씩 온다(2026. 9. 20. 실측: 최근 12개월).
    latest_only 를 켜면 사업장마다 가장 최근 달만 남긴다(--상세 호출 수도 그만큼 준다).
    """
    key = key_value(key)
    # V2는 요청 파라미터 이름이 camelCase 이다. snake_case(wkpl_nm)로 보내면 조건 없이 0건이 온다(2026. 9. 20. 실측)
    params = {'pageNo': 1, 'numOfRows': min(100, max(1, limit))}
    if name:
        params['wkplNm'] = name
    if bno:
        digits = re.sub(r'\D', '', str(bno))
        if len(digits) < 6:
            raise DataGoError('사업자등록번호는 앞 6자리 이상 넣으십시오(국민연금은 앞 6자리만 공개합니다).')
        params['bzowrRgstNo'] = digits[:6]
    if not name and not bno:
        raise DataGoError('--이름 이나 --사업자번호 가운데 하나는 넣어야 합니다.')
    items, total = nps_items(call_get(NPS_BASE + '/getBassInfoSearchV2', params, key))
    rows = [nps_row(x) for x in items][:limit]
    # 사업장끼리는 이름순, 한 사업장 안에서는 최신 달이 앞에 오게 둔다(파이썬 정렬은 안정적이라 두 번 나누어 건다)
    rows.sort(key=lambda r: str(r.get('자료기준월', '')), reverse=True)
    rows.sort(key=lambda r: (str(r.get('사업장명', '')), str(r.get('주소', ''))))
    if latest_only:
        본것 = set()
        rows = [r for r in rows
                if (열쇠 := (r.get('사업장명', ''), r.get('주소', ''), r.get('사업자번호앞6', ''))) not in 본것
                and not 본것.add(열쇠)]
    if detail:
        for row in rows:
            if not row.get('seq'):
                continue
            try:
                더, _ = nps_items(call_get(NPS_BASE + '/getDetailInfoSearchV2', {'seq': row['seq']}, key))
                if 더:
                    row.update({k: v for k, v in nps_row(더[0]).items() if v not in (None, '')})
            except DataGoError as exc:
                row['상세오류'] = str(exc)
    최근, 달수 = {}, {}
    for row in rows:
        열쇠 = (row.get('사업장명', ''), row.get('주소', ''), row.get('사업자번호앞6', ''))
        달수[열쇠] = 달수.get(열쇠, 0) + 1
        최근.setdefault(열쇠, row)
    요약 = [{'사업장명': k[0], '주소': k[1], '사업자번호앞6': k[2], '자료기준월': v.get('자료기준월', ''),
            '가입자수': v.get('가입자수'), '업종': v.get('업종', ''), '등록일': v.get('등록일', ''),
            '탈퇴일': v.get('탈퇴일', ''), '받은달수': 달수[k]} for k, v in 최근.items()]
    return {'검색': {'이름': name or '', '사업자번호앞6': (params.get('bzowrRgstNo') or '')},
            '전체': total, '받은건수': len(rows), '사업장수': len(요약), '호출': CALLS['n'],
            '안내': '전체·받은건수는 사업장 수가 아니라 자료기준월별 줄 수이다. 사업장은 사업장수·요약으로 본다.',
            '요약': 요약, 'rows': rows}


def check(key=None):
    """인증키가 살아 있는지 확인한다. 실제 사업자가 아닌 번호를 넣어 응답 형식만 본다."""
    try:
        data = status(['0000000000'], key=key)
    except DataGoError as exc:
        return {'ok': False, '사유': str(exc)}
    return {'ok': True, '응답': data['rows'][0]['상태'], '호출': CALLS['n'],
            '저장': str(home() / 'datago.json')}


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--key', help='인증키를 직접 넘긴다(저장하지 않는다)')
    subs = parser.add_subparsers(dest='command', required=True)
    s = subs.add_parser('set-key', help='이 PC에 인증키를 저장한다'); s.add_argument('value')
    subs.add_parser('check', help='인증키가 쓰이는지 확인한다(호출 1회)')
    s = subs.add_parser('사업자', help='사업자등록번호의 휴업·폐업 여부를 받는다(국세청)')
    s.add_argument('numbers', nargs='+', help='사업자등록번호(하이픈 있어도 된다). 한 번에 100개까지')
    s.add_argument('--out', help='결과를 JSON 파일로 쓴다')
    s = subs.add_parser('사업장', help='국민연금 가입 사업장의 가입자 수를 받는다(국민연금공단)')
    s.add_argument('--이름', dest='name', help='사업장명(상호). 일부만 넣어도 된다')
    s.add_argument('--사업자번호', dest='bno', help='사업자등록번호. 앞 6자리만 쓴다')
    s.add_argument('--상세', dest='detail', action='store_true', help='가입자수·당월고지금액·업종까지 받는다(줄마다 1회 더 호출)')
    s.add_argument('--최신만', dest='latest_only', action='store_true',
                   help='사업장마다 가장 최근 자료기준월 한 줄만 남긴다(월별 추이가 필요 없을 때)')
    s.add_argument('--limit', type=int, default=24, help='받을 최대 줄 수(기본 24). 한 사업장이 월마다 한 줄이라 24면 두 사업장의 1년치이다')
    s.add_argument('--out', help='결과를 JSON 파일로 쓴다')
    args = parser.parse_args()
    try:
        if args.command == 'set-key':
            result = set_key(args.value)
        elif args.command == 'check':
            result = check(args.key)
        else:
            if args.command == '사업자':
                result = status(args.numbers, key=args.key)
            else:
                result = workplaces(name=args.name, bno=args.bno, detail=args.detail,
                                    latest_only=args.latest_only, limit=args.limit, key=args.key)
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                result = {k: v for k, v in result.items() if k != 'rows'} | {'파일': args.out, '앞 10건': result['rows'][:10]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.command != 'check' or result['ok'] else 1
    except DataGoError as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
