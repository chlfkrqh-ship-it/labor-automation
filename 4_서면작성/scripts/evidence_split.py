# -*- coding: utf-8 -*-
"""합본 PDF 를 호증별 파일로 나눈다(노동위원회 사건의 상대 증거: `.claude/commands/증거정리.md` 4-1단계).

계획 파일(JSON, 경로는 저장소 루트 기준 상대경로):
{
  "폴더": "4_서면작성/사건/{사건}/라운드N/상대증거/호증별",
  "items": [
    {"원본": "4_서면작성/사건/{사건}/라운드N/상대증거/합본.pdf", "면": "1-8", "이름": "0_이유서_본문.pdf"},
    {"원본": "4_서면작성/사건/{사건}/라운드N/상대증거/합본.pdf", "면": "9-10", "이름": "노제1호증_근로계약서.pdf"},
    {"원본": "4_서면작성/사건/{사건}/라운드N/상대증거/영상.mp4", "이름": "노제3호증_영상.mp4"}
  ]
}
 - '면'은 원본의 면 번호(1부터)이다. '1-8', '9', '3-4,7' 처럼 적는다. '면'이 없으면 파일을 그대로 복사한다(영상, 이미 나뉜 파일).
 - 원본 면을 그대로 옮긴다. 회전·크기 조정·도장 넣기는 하지 않는다. 원본 파일은 고치거나 옮기지 않는다.
 - --apply 없이 돌리면 만들 파일과 면수만 보여 준다. 같은 원본 면이 두 파일에 들어가거나 원본에 없는 면을 적으면 멈춘다.
 - 원본마다 어느 파일에도 쓰이지 않은 면을 알린다. 폴더에 계획에 없는 파일이 남아 있으면 알린다(지우지는 않는다).

쓰는 법(저장소 루트에서):
    python 4_서면작성/scripts/evidence_split.py <계획.json>            # 미리보기
    python 4_서면작성/scripts/evidence_split.py <계획.json> --apply    # 만들기
나눈 뒤에는 evidence_check.py trace 와 sheet 로 확인한다(증거정리 4-1단계).
"""
import io, json, os, shutil, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)


def 면목록(글, 전체):
    면 = []
    for 토막 in str(글).split(','):
        토막 = 토막.strip()
        if not 토막:
            continue
        if '-' in 토막:
            a, b = 토막.split('-')
            면 += list(range(int(a), int(b) + 1))
        else:
            면.append(int(토막))
    밖 = [p for p in 면 if p < 1 or p > 전체]
    if 밖:
        raise SystemExit('원본에 없는 면: %s (원본 %d면)' % (밖, 전체))
    return 면


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    계획 = json.load(io.open(sys.argv[1], encoding='utf-8-sig'))
    적용 = '--apply' in sys.argv[2:]
    폴더 = 계획['폴더']
    import pymupdf
    쓴면 = {}
    줄 = []
    for it in 계획['items']:
        원 = it['원본']
        if not os.path.isfile(원):
            raise SystemExit('원본이 없음: %s' % 원)
        if 'pdf' == 원.lower().rsplit('.', 1)[-1] and it.get('면'):
            with pymupdf.open(원) as d:
                면 = 면목록(it['면'], len(d))
            겹침 = sorted(set(면) & 쓴면.setdefault(원, set()))
            if 겹침:
                raise SystemExit('같은 면이 두 파일에 들어감: %s %s' % (os.path.basename(원), 겹침))
            쓴면[원] |= set(면)
            줄.append((it, 면))
        else:
            줄.append((it, None))
    for it, 면 in 줄:
        print('%-46s ← %s %s' % (it['이름'], os.path.basename(it['원본']),
                                 ('면 %s (%d면)' % (it['면'], len(면))) if 면 is not None else '(그대로 복사)'))
    for 원, s in 쓴면.items():
        with pymupdf.open(원) as d:
            전체 = len(d)
        남은 = [p for p in range(1, 전체 + 1) if p not in s]
        print('원본 %s: %d면 가운데 %d면 사용%s' % (os.path.basename(원), 전체, len(s), (', 쓰지 않은 면 %s' % 남은) if 남은 else ''))
    if not 적용:
        print('미리보기입니다. 확인한 뒤 --apply 로 만듭니다.')
        return
    os.makedirs(폴더, exist_ok=True)
    for it, 면 in 줄:
        대상 = os.path.join(폴더, it['이름'])
        if 면 is None:
            shutil.copy2(it['원본'], 대상)
            continue
        src = pymupdf.open(it['원본'])
        out = pymupdf.open()
        for p in 면:
            out.insert_pdf(src, from_page=p - 1, to_page=p - 1)
        out.set_metadata({})
        out.save(대상, garbage=3, deflate=True)
        out.close()
        src.close()
    이름들 = {it['이름'] for it, _ in 줄}
    남은파일 = sorted(f for f in os.listdir(폴더) if f not in 이름들)
    print('만듦: %d개 → %s' % (len(줄), 폴더))
    if 남은파일:
        print('계획에 없는 파일이 폴더에 있음(지우지 않음): %s' % 남은파일)


if __name__ == '__main__':
    main()
