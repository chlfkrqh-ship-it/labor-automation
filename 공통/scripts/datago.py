"""공공데이터포털(data.go.kr) API 조회.

다섯을 다룬다. 법제처 API와는 다른 포털이므로 인증키가 따로 있고, **인증키는 계정에 하나지만
API마다 따로 활용신청해야 한다.** 신청하지 않은 API는 '등록되지 않은 서비스키'로 막힌다.

- 국세청 사업자등록 상태조회: 휴업·폐업 여부. 해고 뒤 위장폐업, 구제이익, 체당금, 상대방 실재 확인
- 국민연금 가입 사업장 내역: 사업장의 국민연금 가입자 수. 사업장 규모를 가늠할 때
  (**가입자 수는 근로기준법상 상시 근로자 수가 아니다.** 아래 '한계'를 읽는다)
- 한국산업안전보건공단 물질안전보건자료(MSDS): 화학물질의 유해성·노출기준·독성·법적 규제.
  산재에서 유해물질 노출이 쟁점일 때(.claude/skills/의학논문-검색/SKILL.md)
- 근로복지공단 산재보험 판례 판결문(34,912건, 2026. 11. 11.): API 에 검색어가 없어 처음 한 번 전체를 받아 이 PC 에
  색인을 두고(`산재판례 --새로` 로 다시 받는다) 판결 전문에서 낱말을 찾는다. 선고일·심급 칸이 없으므로 인용할 판결은
  `comwel.py 판례 {사건번호_법원} --심급` 으로 공단 누리집에서 연다
- 근로복지공단 심사결정서: 본문 검색어·사건명 검색어와 심사결과·청구유형·쟁점유형으로 공단이 거른다

산재판례·심사결정의 --out 은 폴더이다. {이름}_목록.json 과, --본문 N 이면 앞 N건의 전문 {이름}_본문.md 를 쓴다.

인증키와 받은 결과는 PC마다 %LOCALAPPDATA%\\노동사건자동화\\ 아래에 두고 OneDrive에 올리지 않는다.
인증키를 채팅에 받거나 대신 입력하지 않는다.

    python 공통/scripts/datago.py set-key 인증키
    python 공통/scripts/datago.py check
    python 공통/scripts/datago.py 사업자 1234567890 --out 결과.json
    python 공통/scripts/datago.py 사업장 --이름 "법무법인 평안" --상세
    python 공통/scripts/datago.py msds 벤젠
    python 공통/scripts/datago.py msds 71-43-2
    python 공통/scripts/datago.py msds-detail 001008 --절 2 8 11 15 --out 결과.json
    python 공통/scripts/datago.py 산재판례분류
    python 공통/scripts/datago.py 산재판례 --낱말 적응장애 "업무상 스트레스" --유형 요양 --본문 10 --out "{사건}/작업/공단산재판례"
    python 공통/scripts/datago.py 심사결정분류
    python 공통/scripts/datago.py 심사결정 --본문검색 근골격계 --결과 취소 --본문 10 --out "{사건}/작업/공단심사결정"
"""
import argparse
import html
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
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


NPS_SERVICE = '국민연금공단_국민연금 가입 사업장 내역'


def call_get(url, params, key, service=NPS_SERVICE):
    """공공데이터포털의 GET 계열 API. JSON으로 달라 하고 XML이 오면 그것도 읽는다."""
    query = urllib.parse.urlencode({'serviceKey': urllib.parse.unquote(key), **params})
    request = urllib.request.Request(url + '?' + query,
                                     headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0 (labor-workflow)'})
    try:
        with OPENER(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace') if hasattr(exc, 'read') else ''
        raise DataGoError(nps_reason(detail, service) or f'HTTP {exc.code}: {detail[:200]}') from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DataGoError(f'연결 실패: {exc}') from exc
    CALLS['n'] += 1
    time.sleep(DELAY)
    text = raw.decode('utf-8', 'replace')
    reason = nps_reason(text, service)
    if reason:
        raise DataGoError(reason)
    try:
        return json.loads(text)
    except ValueError:
        return xml_to_dict(text)


def nps_reason(text, service=NPS_SERVICE):
    """포털 공통 오류 봉투를 사람이 읽을 말로 바꾼다."""
    if re.search(r'SERVICE[_ ]KEY[_ ]IS[_ ]NOT[_ ]REGISTERED', text) or '등록되지 않은 서비스키' in text:
        return ('이 API에 활용신청이 되어 있지 않습니다. data.go.kr 에서 '
                f"'{service}' 에 활용신청하십시오(인증키는 그대로 씁니다).")
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


def nps_items(data, name='국민연금'):
    """{'response': {'body': {'items': {'item': [...]}, 'totalCount': n}}} 에서 목록과 전체 건수를 꺼낸다."""
    body = (data.get('response') or {}).get('body') or {}
    header = (data.get('response') or {}).get('header') or {}
    if str(header.get('resultCode', '00')).lstrip('0') not in ('', '0'):
        raise DataGoError(f"{name} 응답 오류: {header.get('resultCode')} {header.get('resultMsg', '')}")
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


# data.go.kr 15157612 명세의 주소. 옛 주소(msds.kosha.or.kr/openapi)는 Accept JSON 에 406, http 에 '등록되지 않은 키'를 낸다(2026. 11. 1. 실측)
MSDS_BASE = 'https://apis.data.go.kr/B552468/msdschem1'
MSDS_SERVICE = '한국산업안전보건공단_물질안전보건자료 조회 서비스'
MSDS_KINDS = {'국문명': '0', 'CAS': '1', 'UN': '2', 'KE': '3', 'EN': '4'}   # getChemList001 의 searchCnd
MSDS_SECTIONS = {1: '화학제품과 회사에 관한 정보', 2: '유해성·위험성', 3: '구성성분의 명칭 및 함유량', 4: '응급조치 요령',
                 5: '폭발·화재시 대처방법', 6: '누출 사고시 대처방법', 7: '취급 및 저장방법', 8: '노출방지 및 개인보호구',
                 9: '물리화학적 특성', 10: '안정성 및 반응성', 11: '독성에 관한 정보', 12: '환경에 미치는 영향',
                 13: '폐기시 주의사항', 14: '운송에 필요한 정보', 15: '법적 규제현황', 16: '그 밖의 참고사항'}
MSDS_DEFAULT = (2, 8, 11, 15)    # 산재에서 보는 절: 유해성, 노출기준, 독성(발암성·생식독성), 법적 규제(특수건강진단 대상 등)
MSDS_FIELDS = {'chemNameKor': '물질명', 'casNo': 'CAS', 'unNo': 'UN', 'keNo': 'KE', 'enNo': 'EN', 'lastDate': '갱신일',
               'lev': '단계', 'msdsItemCode': '항목코드', 'msdsItemNameKor': '항목', 'itemDetail': '내용'}


def msds_kind(term):
    """검색어 모양으로 검색 방식을 고른다. CAS 71-43-2, UN 1114, KE-02380, EN 200-753-7, 그 밖은 국문명(영문명도 이 방식으로 찾힌다)."""
    t = re.sub(r'\s+', '', term).upper()
    if re.fullmatch(r'\d{2,7}-\d{2}-\d', t):
        return 'CAS'
    if re.fullmatch(r'(UN)?\d{4}', t):
        return 'UN'
    if re.fullmatch(r'KE-?\d{4,6}', t):
        return 'KE'
    if re.fullmatch(r'\d{3}-\d{3}-\d', t):
        return 'EN'
    return '국문명'


def msds_row(item):
    """명세의 칸 이름을 우리말로 바꾸고 모르는 칸은 그대로 둔다(명세가 바뀌어도 내용을 잃지 않는다)."""
    if not isinstance(item, dict):
        return {'값': item}
    row = {MSDS_FIELDS.get(k, k): v for k, v in item.items()}
    if '갱신일' in row:
        row['갱신일'] = ymd(row['갱신일']) or row['갱신일']
    if isinstance(row.get('내용'), str):      # 부등호가 한 번 더 이스케이프되어 'LD50 &gt;2000' 으로 온다(2026. 11. 1. 실측)
        row['내용'] = html.unescape(row['내용'])
    return row


def msds_list(path, params, key, limit):
    """목록을 쪽마다 넘겨 limit 줄까지 모은다. 포털 API는 한 쪽에 10줄만 주는 것이 기본이다."""
    size, rows, page = max(1, min(limit, 100)), [], 1
    while True:
        data = call_get(f'{MSDS_BASE}/{path}', {**params, 'numOfRows': size, 'pageNo': page}, key,
                        service=MSDS_SERVICE)
        items, total = nps_items(data, 'MSDS')
        rows += items
        if not items or len(rows) >= min(limit, total or len(rows)) or page >= 50:
            return [msds_row(it) for it in rows[:limit]], total or len(rows)
        page += 1


def msds_search(term, *, kind=None, limit=20, key=None):
    """MSDS 목록에서 화학물질을 찾는다. 결과의 chemId 로 msds_detail 을 부른다."""
    if not term.strip():
        raise DataGoError('검색어가 비었습니다.')
    kind = kind or msds_kind(term)
    if kind not in MSDS_KINDS:
        raise DataGoError(f"검색 방식은 {', '.join(MSDS_KINDS)} 가운데 하나입니다.")
    key = key_value(key)
    word = term.strip() if kind == '국문명' else re.sub(r'\s+', '', term).upper()
    if kind == 'UN':
        word = re.sub(r'^UN', '', word)
    rows, total = msds_list('getChemList001', {'searchWrd': word, 'searchCnd': MSDS_KINDS[kind]}, key, limit)
    return {'검색어': term, '검색방식': kind, '전체': total, '받은건수': len(rows), '호출': CALLS['n'], 'rows': rows}


def msds_detail(chem_id, *, sections=MSDS_DEFAULT, key=None):
    """MSDS 의 절(1~16)별 내용을 받는다. 기본은 산재에서 보는 2·8·11·15절이다."""
    chem_id = str(chem_id).strip()
    if not chem_id:
        raise DataGoError('chemId 가 비었습니다. msds 검색 결과의 chemId 를 넣으십시오.')
    if isinstance(sections, (str, int)):
        sections = [sections]
    if [str(n).strip().lower() for n in sections] == ['all']:
        sections = list(MSDS_SECTIONS)
    try:
        sections = list(dict.fromkeys(int(n) for n in sections))      # 같은 절을 두 번 부르지 않는다
    except (TypeError, ValueError) as exc:
        raise DataGoError('MSDS 절은 1~16 의 숫자이거나 all 입니다.') from exc
    bad = [n for n in sections if n not in MSDS_SECTIONS]
    if bad:
        raise DataGoError(f'MSDS 절은 1~16 입니다: {bad}')
    key = key_value(key)
    content = {}
    for n in sections:
        # 상세는 쪽 나누기 없이 한 번에 온다. numOfRows·pageNo 를 무시하고 totalCount 도 없다(2026. 11. 1. 실측)
        data = call_get(f'{MSDS_BASE}/getChemDetail{n:02d}1', {'chemId': chem_id}, key, service=MSDS_SERVICE)
        content[f'{n}. {MSDS_SECTIONS[n]}'] = [msds_row(it) for it in nps_items(data, 'MSDS')[0]]
    # 없는 번호나 앞의 0을 뺀 번호(1008)도 정상 코드와 빈 목록으로 온다(2026. 11. 1. 실측)
    if not any(content.values()):
        raise DataGoError(f'chemId {chem_id} 로 받은 내용이 없습니다. msds 결과의 chemId 를 앞의 0까지 그대로 넣으십시오.')
    return {'chemId': chem_id, '절': sections, '호출': CALLS['n'], '내용': content,
            '안내': 'MSDS 는 물질의 유해성 참고자료이다. 실제 노출(농도·기간·작업)은 작업환경측정 결과와 역학조사로 따로 본다.'}


# ---------------------------------------------------------------- 근로복지공단 산재판례 판결문·심사결정서
# data.go.kr 15041878(판결문)·15110818(심사결정서). 2026. 11. 11. 담당자 키로 승인만 되어 있던 것을 붙였다(공통/판례출처.md).
# 공단 누리집 화면을 읽는 comwel.py 와 같은 자료의 공식 API 이다. 판결문은 선고일 칸이 없으므로 인용할 판결은 comwel.py 판례로 연다.
SJB_BASE = 'https://apis.data.go.kr/B490001/sjbPrecedentInfoService'
SJB_SERVICE = '근로복지공단_산재보험 판례 판결문 조회 서비스'
SIMSA_BASE = 'https://apis.data.go.kr/B490001/simsaPstateInfoService'
SIMSA_SERVICE = '근로복지공단_심사결정서 조회 서비스'
SJB_PAGE = 1000          # 한 쪽 1,000줄이 1.5초·3.2MB 로 온다(2026. 11. 11. 실측, 전체 34,912건)
SJB_CODES = {'결과': ('getSjbPrecedentResultYuhyeongPstate', 'kinda'), '유형': ('getSjbSageonYuhyeongPstate', 'kindb'),
             '구분': ('getSjbSagoJilbyeongGubunPstate', 'kindc')}
SIMSA_CODES = {'결과': ('getSimsaResultYuhyeongPstate', 'kinda'), '청구': ('getChungguYuhyeongPstate', 'kindb'),
               '쟁점': ('getJaengjeomGubunPstate', 'kindc')}
_spec = importlib.util.spec_from_file_location('workflow_system', Path(__file__).with_name('system.py'))
_system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_system)
CASE_NUMBER = re.compile(_system.CASE_NUMBER)


def _items(data, name):
    items, total = nps_items(data, name)
    return [x for x in items if isinstance(x, dict)], total     # 분류 목록 끝에 빈 <item/> 이 온다


def _text(value):
    return html.unescape(value if isinstance(value, str) else '').strip()


def squash(text):
    return re.sub(r'[\s·ㆍ]+', '', text or '')


def snippet(text, words, width=90):
    """첫 낱말이 처음 나온 자리 앞뒤 글. 띄어쓰기가 달라도 찾는다."""
    for w in words:
        w = squash(w)
        if not w:
            continue
        m = re.search(r'\s*'.join(map(re.escape, w)), text or '')
        if m:
            a = max(0, m.start() - width)
            return ('…' if a else '') + re.sub(r'\s+', ' ', text[a:m.end() + width]).strip() + '…'
    return re.sub(r'\s+', ' ', (text or '')[:width * 2]).strip()


def sjb_row(item):
    raw = _text(item.get('accnum'))
    m = CASE_NUMBER.search(raw)
    branch = re.match(r'\(([^)]+)\)', raw)
    return {'사건번호': re.sub(r'\s', '', m.group(0)) if m else raw, '표시번호': raw, '법원': _text(item.get('courtname')),
            '지원': branch.group(1) if branch else '', '결과': _text(item.get('kinda')), '유형': _text(item.get('kindb')),
            '구분': _text(item.get('kindc')), '사건명': _text(item.get('title')), '본문': _text(item.get('noncontent'))}


def codes(kind, key=None):
    """산재판례(결과·유형·구분) 또는 심사결정(결과·청구·쟁점)의 분류 값. 검색 조건에 이 값을 글자 그대로 넣는다."""
    base, table, service = (SJB_BASE, SJB_CODES, SJB_SERVICE) if kind == '산재판례' else (SIMSA_BASE, SIMSA_CODES, SIMSA_SERVICE)
    key = key_value(key)
    out = {}
    for name, (op, field) in table.items():
        items, _ = _items(call_get(f'{base}/{op}', {'pageNo': 1, 'numOfRows': 100}, key, service=service), kind)
        out[name] = [_text(x.get(field)) for x in items if _text(x.get(field))]
    return {'분류': out, '호출': CALLS['n'], '안내': f'{kind} 명령의 조건에 이 값을 글자 그대로 넣는다'}


def sjb_index_path():
    return home() / '캐시' / 'datago' / '산재판례.jsonl'


def sjb_index(key=None, refresh=False):
    """판결문을 모두 받아 이 PC 에 색인을 둔다. 판결문 API 에는 검색어가 없고 분류 코드로만 거르기 때문이다.
    2026. 11. 11. 34,912건을 1,000줄씩 35회에 받는다(약 110MB, %LOCALAPPDATA% 아래라 OneDrive 에 올라가지 않는다)."""
    path, meta = sjb_index_path(), sjb_index_path().with_suffix('.json')
    if path.is_file() and not refresh:
        try:
            return json.loads(meta.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {'건수': None}
    key = key_value(key)
    rows, page, total, start = [], 1, None, CALLS['n']
    while True:
        data = call_get(f'{SJB_BASE}/getSjbPrecedentNaeyongPstate', {'pageNo': page, 'numOfRows': SJB_PAGE}, key, service=SJB_SERVICE)
        items, n = _items(data, '산재판례')
        total = n if total is None else total
        rows += [sjb_row(x) for x in items]
        if not items or len(rows) >= total:
            break
        page += 1
    if total and len(rows) < total:
        raise DataGoError(f'산재판례 색인을 다 받지 못했습니다({len(rows)}/{total}). 잠시 뒤 --새로 로 다시 받으십시오.')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    tmp.replace(path)
    info = {'건수': len(rows), '받은날': datetime.now().strftime('%Y-%m-%d'), '호출': CALLS['n'] - start}
    meta.write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
    return info


def sjb_search(words=(), *, result=None, kind=None, gubun=None, court=None, limit=200, key=None, refresh=False):
    """색인에서 낱말(띄어쓰기 무시, 모두 든 것)과 분류로 판결문을 찾는다. 사건명에 낱말이 든 것 → 본문에 많이 나온 것 순이다."""
    ws = [w for w in words if squash(w)]
    if not ws and not any((result, kind, gubun, court)):
        raise DataGoError('--낱말 이나 분류(--결과·--유형·--구분·--법원) 가운데 하나는 넣어야 합니다.')
    info = sjb_index(key, refresh)
    sq = [squash(w) for w in ws]
    hits = []
    with open(sjb_index_path(), encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if (result and r['결과'] != result) or (kind and r['유형'] != kind) or (gubun and r['구분'] != gubun) \
                    or (court and squash(court) not in squash(r['법원'] + r['지원'])):
                continue
            hay = squash(r['사건명'] + r['본문'])
            if all(w in hay for w in sq):
                r['_점수'] = (-sum(w in squash(r['사건명']) for w in sq), -sum(hay.count(w) for w in sq))
                hits.append(r)
    hits.sort(key=lambda r: r.pop('_점수'))
    rows = [{k: v for k, v in r.items() if k != '본문'} | {'스니펫': snippet(r['본문'], ws), 'comwel': f"{r['사건번호']}_{r['법원']}"}
            for r in hits[:limit]]
    return {'낱말': ws, '조건': {k: v for k, v in (('결과', result), ('유형', kind), ('구분', gubun), ('법원', court)) if v},
            '색인': info, '전체': len(hits), '받은건수': len(rows), 'rows': rows, '_본문': hits[:limit],
            '안내': '판결문 API 에는 선고일·심급 칸이 없다. 인용할 판결은 comwel.py 판례 {comwel} --심급 으로 공단 누리집에서 열어 선고일을 본다'}


def simsa_row(item):
    return {'결정번호': _text(item.get('accnum')), '결과': _text(item.get('kinda')), '청구유형': _text(item.get('kindb')),
            '쟁점': _text(item.get('kindc')), '사건명': _text(item.get('title')), '본문': _text(item.get('noncontent'))}


def simsa_search(*, body=None, title=None, result=None, claim=None, issue=None, limit=200, key=None):
    """심사결정서를 찾는다. 본문 검색어(cq)·사건명 검색어(tq)와 분류로 공단이 거른다. 둘을 함께 주면 본문으로 찾고 사건명은 받은 줄에서 거른다."""
    if not any((body, title, result, claim, issue)):
        raise DataGoError('--본문검색·--사건명 이나 분류(--결과·--청구·--쟁점) 가운데 하나는 넣어야 합니다.')
    key = key_value(key)
    op = 'getSimsaResultSageonPstate' if title and not body else 'getSimsaResultNaeyongPstate'
    params = {k: v for k, v in (('kinda', result), ('kindb', claim), ('kindc', issue)) if v}
    params.update({'cq': body} if body else ({'tq': title} if title else {}))
    rows, page, total, size = [], 1, None, max(1, min(SJB_PAGE, limit))
    while len(rows) < limit:
        items, n = _items(call_get(f'{SIMSA_BASE}/{op}', {**params, 'pageNo': page, 'numOfRows': size}, key, service=SIMSA_SERVICE), '심사결정')
        total = n if total is None else total
        rows += [simsa_row(x) for x in items]
        if not items or len(rows) >= total:
            break
        page += 1
    if body and title:
        rows = [r for r in rows if squash(title) in squash(r['사건명'] + r['본문'][:300])]
    rows = rows[:limit]
    words = [w for w in (body, title) if w]
    return {'조건': {k: v for k, v in (('본문검색', body), ('사건명', title), ('결과', result), ('청구', claim), ('쟁점', issue)) if v},
            '전체': total or 0, '받은건수': len(rows), '호출': CALLS['n'],
            'rows': [{k: v for k, v in r.items() if k != '본문'} | {'스니펫': snippet(r['본문'], words)} for r in rows], '_본문': rows}


def write_found(out, name, result, texts, head):
    """--out 폴더에 {이름}_목록.json 과 앞의 texts 건 본문 {이름}_본문.md 를 쓴다."""
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    docs = result.pop('_본문', [])[:texts]
    (folder / f'{name}_목록.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    written = [str(folder / f'{name}_목록.json')]
    if docs:
        parts = [f'# 근로복지공단 {name} {len(docs)}건\n']
        for d in docs:
            parts.append(f"## [{name}] {head(d)}\n\n" + '\n'.join(f'- {k}: {v}' for k, v in d.items() if k != '본문' and v)
                         + '\n\n' + d['본문'] + '\n')
        (folder / f'{name}_본문.md').write_text('\n'.join(parts), encoding='utf-8')
        written.append(str(folder / f'{name}_본문.md'))
    return written


# ---------------------------------------------------------------- 그 밖에 승인된 포털 API(공통 호출)·안전보건공단 재해사례
# 2026. 11. 11. 담당자가 추가로 신청해 승인된 API 를 실측한 주소·고정 변수. 안전보건공단 게이트웨이(B552468)는 경로와 관계없이
# callApiId 로 자료를 고른다(1030 KOSHA 자료 목록 9,276건, 1040 중대재해 사고 속보 2,998건, 1050 KOSHA GUIDE 1,039건,
# 1060 국내재해사례 6,398건, 1070 재해사례 첨부, 1080 은 certNo 가 필요하다). 1040·1060 은 business·keyword 를 받아도 거르지 않는다.
PORTAL_ALIASES = {
    '헌재판례': ('9750000/PrecedentInfomationService/getKorPrcdntList', {'type': 'json'}),      # eventNm·eventNo·eventType·rstaResult
    '헌재공보': ('9750000/PrecedentInfomationService/getOcprPrcdntList', {'type': 'json'}),     # title(공보 호수)·adjudgeYm
    '헌재주요판례': ('9750000/PrecedentInfomationService/getRealmMainPrcdntList', {'type': 'json', 'code': '0'}),   # eventNm·decisionNm
    '안전보건법령': ('B552468/srch/smartSearch', {'category': '0'}),                              # searchValue(필수)·category
    '코샤가이드': ('B552468/disaster_api02/getdisaster_api02', {'callApiId': '1050'}),          # techGdlnNm(이름에서 찾는다)
    '재해사례첨부': ('B552468/disaster_attach_api02/Disaster_attach_api02', {'callApiId': '1070'}),   # boardno(필수)
    'KOSHA자료': ('B552468/disaster_api02/getdisaster_api02', {'callApiId': '1030'}),
}
KOSHA_PATH = 'B552468/disaster_api02/getdisaster_api02'
KOSHA_BOARDS = {'사례': '1060', '속보': '1040'}      # 국내재해사례 6,398건·중대재해 사고 속보 2,998건(2026. 11. 11.)


def portal_rows(data):
    """포털 응답에서 (줄 목록, 전체 건수, body). response 봉투가 있든 없든(안전보건공단·헌법재판소 JSON 은 없다) 읽는다."""
    root = data.get('response', data) if isinstance(data, dict) else {}
    header = root.get('header') or {}
    code = str(header.get('resultCode', '00'))
    if code.strip('0'):
        raise DataGoError(f"포털 응답 오류: {code} {header.get('resultMsg', '')}"
                          + (' — 필수 변수나 고정값(callApiId 등)을 확인하십시오' if code in ('80', '90', '99') else ''))
    body = root.get('body') if isinstance(root.get('body'), dict) else {}
    items = body.get('items')
    items = items.get('item') if isinstance(items, dict) else items
    items = [items] if isinstance(items, dict) else (items if isinstance(items, list) else [])
    total = re.sub(r'\D', '', str(body.get('totalCount', '')))
    return [x for x in items if isinstance(x, dict)], int(total or 0), body


def portal(target, params=None, *, limit=100, key=None):
    """승인된 포털 API 를 부른다. target 은 PORTAL_ALIASES 의 이름, 'B552468/srch/smartSearch' 같은 경로, 전체 주소 가운데 하나이다."""
    path, fixed = PORTAL_ALIASES.get(target, (target, {}))
    url = path if path.startswith('http') else 'https://apis.data.go.kr/' + path.lstrip('/')
    params = {**fixed, **{k: v for k, v in (params or {}).items() if v not in (None, '')}}
    key = key_value(key)
    page = int(params.pop('pageNo', 1))
    size = int(params.pop('numOfRows', max(1, min(limit, SJB_PAGE))))
    rows, total, body = [], None, {}
    while len(rows) < limit:
        items, n, body = portal_rows(call_get(url, {**params, 'pageNo': page, 'numOfRows': size}, key, service=target))
        total = n if total is None else total
        rows += items
        if not items or not n or len(rows) >= n:
            break
        page += 1
    out = {'주소': url, '변수': params, '전체': total or 0, '받은건수': len(rows[:limit]), '호출': CALLS['n'], 'rows': rows[:limit]}
    if not rows and body:
        out['body'] = body          # 안전보건법령 스마트검색처럼 items 가 아닌 꼴로 오는 응답
    return out


def plain_html(text):
    text = re.sub(r'<br\s*/?>|</p>|</div>', '\n', text or '')
    text = html.unescape(re.sub(r'<[^>]+>', ' ', text))
    return re.sub(r'\n\s*\n+', '\n', re.sub(r'[ \t\xa0]+', ' ', text)).strip()


def kosha_index_path():
    return home() / '캐시' / 'datago' / '재해사례.jsonl'


def kosha_index(key=None, refresh=False):
    """안전보건공단 국내재해사례(1060)와 중대재해 사고 속보(1040)를 모두 받아 이 PC 에 색인을 둔다. 두 게시판은 업종·검색어로 거르지 않는다."""
    path, meta = kosha_index_path(), kosha_index_path().with_suffix('.json')
    if path.is_file() and not refresh:
        try:
            return json.loads(meta.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {'건수': None}
    rows, start = [], CALLS['n']
    for board, cid in KOSHA_BOARDS.items():
        got = portal(KOSHA_PATH, {'callApiId': cid}, limit=10 ** 6, key=key)
        if got['전체'] and got['받은건수'] < got['전체']:
            raise DataGoError(f"재해사례 {board} 색인을 다 받지 못했습니다({got['받은건수']}/{got['전체']}). --새로 로 다시 받으십시오.")
        for it in got['rows']:
            rows.append({'게시판': board, '번호': _text(it.get('boardno') or it.get('arno')), '업종': _text(it.get('business')),
                         '제목': _text(it.get('keyword')), '첨부': int(re.sub(r'\D', '', str(it.get('atcflcnt') or '')) or 0),
                         '본문': plain_html(it.get('contents') if isinstance(it.get('contents'), str) else '')})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    tmp.replace(path)
    info = {'건수': len(rows), '게시판별': {b: sum(1 for r in rows if r['게시판'] == b) for b in KOSHA_BOARDS},
            '받은날': datetime.now().strftime('%Y-%m-%d'), '호출': CALLS['n'] - start}
    meta.write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
    return info


def kosha_search(words=(), *, board=None, business=None, limit=200, key=None, refresh=False):
    """색인에서 낱말(띄어쓰기 무시, 모두 든 것)·게시판·업종으로 재해사례를 찾는다. 제목에 낱말이 든 것 → 최신 순이다."""
    ws = [w for w in words if squash(w)]
    if not ws and not any((board, business)):
        raise DataGoError('--낱말 이나 --게시판·--업종 가운데 하나는 넣어야 합니다.')
    info = kosha_index(key, refresh)
    sq = [squash(w) for w in ws]
    hits = []
    with open(kosha_index_path(), encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if (board and r['게시판'] != board) or (business and squash(business) not in squash(r['업종'])):
                continue
            if all(w in squash(r['제목'] + r['본문'] + r['업종']) for w in sq):
                hits.append(r)
    hits.sort(key=lambda r: r['번호'], reverse=True)            # 번호가 등록 일시로 시작한다(20261105093815…)
    hits.sort(key=lambda r: -sum(w in squash(r['제목']) for w in sq))
    rows = [{k: v for k, v in r.items() if k != '본문'} | {'스니펫': snippet(r['본문'], ws)} for r in hits[:limit]]
    return {'낱말': ws, '조건': {k: v for k, v in (('게시판', board), ('업종', business)) if v}, '색인': info,
            '전체': len(hits), '받은건수': len(rows), 'rows': rows, '_본문': hits[:limit],
            '안내': '사례 게시판의 첨부(PDF)는 포털 재해사례첨부 --변수 boardno={번호} 로 주소를 받는다. 속보는 신고 직후 내용이라 조사 결과와 다를 수 있다'}


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
    s = subs.add_parser('msds', help='화학물질을 MSDS 목록에서 찾는다(한국산업안전보건공단). 결과의 chemId 를 msds-detail 에 넣는다')
    s.add_argument('term', help='물질명(국문·영문, 일부도 된다) 또는 CAS·UN·KE·EN 번호')
    s.add_argument('--방식', dest='kind', choices=list(MSDS_KINDS), help='검색 방식. 비우면 검색어 모양으로 고른다')
    s.add_argument('--limit', type=int, default=20, help='받을 최대 줄 수(기본 20)')
    s.add_argument('--out', help='결과를 JSON 파일로 쓴다')
    s = subs.add_parser('msds-detail', help='MSDS 의 절별 내용을 받는다(기본 2·8·11·15절, 절마다 1회 호출)')
    s.add_argument('chem_id', help='msds 결과의 chemId(앞의 0까지 그대로)')
    s.add_argument('--절', dest='sections', nargs='+', default=list(MSDS_DEFAULT),
                   help='받을 절 번호(1~16). all 이면 16절 모두')
    s.add_argument('--out', help='결과를 JSON 파일로 쓴다')
    subs.add_parser('산재판례분류', help='산재판례 판결문의 결과·유형·구분 값을 받는다(근로복지공단, 호출 3회)')
    s = subs.add_parser('산재판례', help='근로복지공단 산재판례 판결문을 이 PC 의 색인에서 찾는다(색인이 없으면 먼저 전체를 받는다)')
    s.add_argument('--낱말', dest='words', nargs='*', default=[], help='판결 전문에 모두 든 것을 찾는다(띄어쓰기 무시)')
    s.add_argument('--결과', dest='result', help='사건결과(기각·취소·일부취소·파기환송 등)')
    s.add_argument('--유형', dest='kind', help='사건유형(요양·유족·장해·평균임금 등)')
    s.add_argument('--구분', dest='gubun', help='사고·질병 구분(업무상질병·업무상사고·퇴직후진단 등)')
    s.add_argument('--법원', dest='court', help='법원 이름의 일부')
    s.add_argument('--limit', type=int, default=200, help='목록에 둘 최대 줄 수(기본 200)')
    s.add_argument('--본문', dest='texts', type=int, default=0, help='앞 N건의 판결 전문을 {out}/산재판례_본문.md 에 쓴다')
    s.add_argument('--새로', dest='refresh', action='store_true', help='색인을 다시 받는다(호출 35회 안팎)')
    s.add_argument('--out', help='결과를 쓸 폴더')
    subs.add_parser('심사결정분류', help='심사결정서의 결과·청구·쟁점 값을 받는다(근로복지공단, 호출 3회)')
    s = subs.add_parser('심사결정', help='근로복지공단 심사결정서를 찾는다')
    s.add_argument('--본문검색', dest='body', help='결정서 본문 검색어')
    s.add_argument('--사건명', dest='title', help='사건명 검색어')
    s.add_argument('--결과', dest='result', help='심사결과(기각·취소·일부취소·각하·취하)')
    s.add_argument('--청구', dest='claim', help='청구유형(최초요양·추가상병·유족급여 등)')
    s.add_argument('--쟁점', dest='issue', help='쟁점유형 구분 값(심사결정분류로 본다)')
    s.add_argument('--limit', type=int, default=200, help='받을 최대 줄 수(기본 200)')
    s.add_argument('--본문', dest='texts', type=int, default=0, help='앞 N건의 결정서 전문을 {out}/심사결정_본문.md 에 쓴다')
    s.add_argument('--out', help='결과를 쓸 폴더')
    s = subs.add_parser('재해사례', help='안전보건공단 국내재해사례·중대재해 사고 속보를 이 PC 의 색인에서 찾는다(색인이 없으면 먼저 받는다)')
    s.add_argument('--낱말', dest='words', nargs='*', default=[], help='제목·사고 경위에 모두 든 것을 찾는다(띄어쓰기 무시)')
    s.add_argument('--게시판', dest='board', choices=list(KOSHA_BOARDS), help='사례(국내재해사례) 또는 속보(중대재해 사고 속보)')
    s.add_argument('--업종', dest='business', help='업종(사례 게시판의 건설업·제조업·조선업 등)')
    s.add_argument('--limit', type=int, default=200, help='목록에 둘 최대 줄 수(기본 200)')
    s.add_argument('--본문', dest='texts', type=int, default=0, help='앞 N건의 사고 경위를 {out}/재해사례_본문.md 에 쓴다')
    s.add_argument('--새로', dest='refresh', action='store_true', help='색인을 다시 받는다(호출 10회 안팎)')
    s.add_argument('--out', help='결과를 쓸 폴더')
    s = subs.add_parser('코샤가이드', help='KOSHA GUIDE(안전보건공단 기술지원규정)를 이름으로 찾는다(파일 주소 포함)')
    s.add_argument('--이름', dest='name', required=True, help='지침 이름에서 찾을 말(예: 소음)')
    s.add_argument('--limit', type=int, default=50)
    s.add_argument('--out', help='결과를 JSON 파일로 쓴다')
    s = subs.add_parser('포털', help='승인된 포털 API 를 부른다. 별칭: ' + ', '.join(PORTAL_ALIASES))
    s.add_argument('target', help='별칭이나 apis.data.go.kr 뒤의 경로(예: B552468/srch/smartSearch)')
    s.add_argument('--변수', dest='params', nargs='*', default=[], help='요청 변수 이름=값(예: searchValue=사다리)')
    s.add_argument('--limit', type=int, default=100, help='받을 최대 줄 수(기본 100)')
    s.add_argument('--out', help='결과를 JSON 파일로 쓴다')
    args = parser.parse_args()
    if args.command in ('산재판례', '심사결정', '재해사례') and args.out and Path(args.out.rstrip('/\\')).suffix.lower() in ('.json', '.md', '.txt'):
        parser.error(f'{args.command} 의 --out 은 폴더 이름이다({args.out})')
    if args.command == '포털' and any('=' not in p for p in args.params):
        parser.error('--변수 는 이름=값 꼴로 준다')
    try:
        if args.command == 'set-key':
            result = set_key(args.value)
        elif args.command == 'check':
            result = check(args.key)
        elif args.command in ('산재판례분류', '심사결정분류'):
            result = codes(args.command[:-2], key=args.key)
        elif args.command in ('산재판례', '심사결정', '재해사례'):
            if args.command == '산재판례':
                result = sjb_search(args.words, result=args.result, kind=args.kind, gubun=args.gubun, court=args.court,
                                    limit=args.limit, key=args.key, refresh=args.refresh)
                head = lambda d: ' '.join(x for x in (d['법원'], d['표시번호'], d['사건명']) if x)
            elif args.command == '재해사례':
                result = kosha_search(args.words, board=args.board, business=args.business, limit=args.limit, key=args.key,
                                      refresh=args.refresh)
                head = lambda d: ' '.join(x for x in (d['게시판'], d['업종'], d['제목']) if x)
            else:
                result = simsa_search(body=args.body, title=args.title, result=args.result, claim=args.claim, issue=args.issue,
                                      limit=args.limit, key=args.key)
                head = lambda d: ' '.join(x for x in ('심사결정', d['결정번호'], d['사건명'] or d['청구유형']) if x)
            if args.out:
                files = write_found(args.out, args.command, result, args.texts, head)     # _본문을 꺼내 쓰고 목록 파일을 쓴다
                result = {k: v for k, v in result.items() if k not in ('rows', '_본문')} | {'파일': files, '앞 10건': result['rows'][:10]}
            else:
                result.pop('_본문', None)
                result['rows'] = result['rows'][:20]
        else:
            if args.command == '코샤가이드':
                result = portal('코샤가이드', {'techGdlnNm': args.name}, limit=args.limit, key=args.key)
            elif args.command == '포털':
                result = portal(args.target, dict(p.split('=', 1) for p in args.params), limit=args.limit, key=args.key)
            elif args.command == '사업자':
                result = status(args.numbers, key=args.key)
            elif args.command == '사업장':
                result = workplaces(name=args.name, bno=args.bno, detail=args.detail,
                                    latest_only=args.latest_only, limit=args.limit, key=args.key)
            elif args.command == 'msds':
                result = msds_search(args.term, kind=args.kind, limit=args.limit, key=args.key)
            else:
                result = msds_detail(args.chem_id, sections=args.sections, key=args.key)
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                brief = {k: v for k, v in result.items() if k not in ('rows', '내용')} | {'파일': args.out}
                if 'rows' in result:
                    brief['앞 10건'] = result['rows'][:10]
                if '내용' in result:
                    brief['항목 수'] = {절: len(줄) for 절, 줄 in result['내용'].items()}
                result = brief
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.command != 'check' or result['ok'] else 1
    except DataGoError as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
