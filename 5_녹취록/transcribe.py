# -*- coding: utf-8 -*-
"""
transcribe.py — 사건 녹음 파일을 로컬에서 텍스트로 변환하는 스크립트

특징
- faster-whisper 를 PC 안에서 실행합니다. 오디오가 외부로 나가지 않아 비밀유지에 안전합니다.
- 인터넷/API 키가 필요 없습니다. (단, 모델을 처음 받을 때 1회 다운로드가 필요합니다)
- ffmpeg 를 따로 설치하지 않아도 됩니다. (faster-whisper 내부의 PyAV 가 오디오를 디코딩합니다)
- 화자 분리는 sherpa-onnx(ONNX Runtime)로 CPU에서 수행합니다. GPU도 HuggingFace 토큰도
  필요 없습니다. 목소리 기준으로 구간을 나누어 '화자1·화자2'로 표기하며,
  그 구간이 누구인지 이름을 붙이는 일은 /녹취 단계에서 대화 맥락으로 합니다.
- 이 스크립트는 전사와 화자 '구간 분리'까지만 합니다. 화자 '이름 배정'은 하지 않습니다.

사용법
    python transcribe.py <오디오파일_또는_폴더> [옵션]

옵션
    --output-dir DIR    결과(.녹취.txt / .녹취.json) 저장 폴더 (기본: 원본과 같은 폴더)
    --model NAME        모델 크기 (기본: large-v3-turbo)
                        large-v3-turbo = large-v3보다 빠르고 반복 환각이 적음(실측)
    --language CODE     언어 코드 (기본: ko). 자동감지는 auto
    --compute-type T    int8 / int8_float16 / float16 / float32 (기본: int8, CPU에 적합)
    --device D          cpu / cuda / auto (기본: cpu)
    --no-vad            무음 구간 제거(VAD)를 끕니다
    --diarize           화자 분리(구간만). 미설치·모델없음이면 조용히 건너뜁니다
    --num-speakers N    화자 수를 알면 지정. 통화는 2. 지정하면 정확도가 크게 오릅니다
    --initial-prompt S  인식 힌트 문장 교체 (기본: 노동사건 어휘)
    --no-initial-prompt 인식 힌트를 쓰지 않습니다
    --force             이미 전사한 원본도 다시 전사합니다

출력
    <원본이름>.녹취.txt   사람이 읽는 타임스탬프 전사본
    <원본이름>.녹취.json  후처리용 구간 데이터
                          [{start, end, text, avg_logprob, no_speech_prob, speaker}, ...]
                          + review_needed(확인 필요 구간) + speaker_count
    확장자만 다른 원본(통화.m4a·통화.mp4)이 함께 있거나 그 이름의 결과가 이미 다른 원본의
    것이면, 서로 덮어쓰지 않도록 확장자까지 넣는다(<원본이름>.<확장자>.녹취.txt).

다시 돌릴 때
    같은 원본(이름·크기·수정시각)을 같은 조건(모델·언어·화자 수 등)으로 끝까지 전사한
    결과가 있으면 건너뜁니다. 조건을 바꾸면 다시 전사하고, --force 는 조건과 상관없이
    다시 전사합니다. 중간에 끊긴 결과(.부분.jsonl 이 남은 것)는 처음부터 다시 합니다.

저장 위치 제한
    전사본에는 대화 전문이 들어갑니다. 이 폴더가 git 작업본 안에 있으면, 저장소 안이면서
    사건/ 밖인 곳에는 결과를 쓰지 않고 멈춥니다(.gitignore 는 사건/ 아래만 막습니다).

중단 대비
    세그먼트가 나올 때마다 .녹취.txt 에 즉시 기록하고 .부분.jsonl 에도 한 줄씩 남깁니다.
    긴 녹음이 중간에 끊겨도 그때까지의 결과는 파일에 남습니다.
"""

import argparse
import datetime as _dt
import json
import os
import sys

# Windows 콘솔에서 한글 출력이 깨지지 않도록 UTF-8 로 맞춥니다.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 오디오·영상 확장자 (영상은 소리 트랙만 사용됩니다)
AUDIO_EXTS = {
    ".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus",
    ".wma", ".amr", ".mp4", ".mov", ".avi", ".mkv", ".webm",
}

# 인식 힌트. 노동사건에서 자주 나오는 어휘를 미리 물려 오인식을 줄입니다.
# Whisper 의 initial_prompt 는 '앞서 나온 말'처럼 취급되므로 문장 형태로 둡니다.
LABOR_INITIAL_PROMPT = (
    "노동사건 상담 녹음입니다. "
    "권고사직, 해고예고수당, 부당해고, 구제신청, 대기발령, 징계위원회, 시말서, "
    "취업규칙, 근로계약서, 연차수당, 퇴직금, 중간정산, 임금체불, 통상임금, "
    "직장 내 괴롭힘, 산업재해, 요양급여, 휴업급여, 노동위원회, 근로복지공단, "
    "고용노동부, 진정, 이행강제금, 원직복직 같은 말이 나옵니다."
)

# 확인 필요 구간 판정 기준. 설계안 수치를 그대로 씁니다.
REVIEW_AVG_LOGPROB = -1.0
REVIEW_NO_SPEECH = 0.5

HERE = os.path.dirname(os.path.abspath(__file__))
# 이 폴더(5_녹취록)의 상위가 저장소 작업본 루트입니다.
REPO_ROOT = os.path.dirname(HERE)


def _log(msg):
    print(msg, flush=True)


def _hhmmss(seconds):
    """초 단위 실수를 HH:MM:SS 문자열로 변환합니다."""
    if seconds is None or seconds < 0:
        seconds = 0
    td = _dt.timedelta(seconds=int(round(seconds)))
    total = int(td.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _collect_inputs(path):
    """파일이면 그 파일 하나, 폴더면 폴더 안의 오디오/영상 파일들을 반환합니다."""
    if os.path.isfile(path):
        return [path]
    if os.path.isdir(path):
        found = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(name)[1].lower()
            # 전사 결과 파일 자체는 입력이 아닙니다. 이미 전사한 원본을 건너뛸지는 main 이 정합니다.
            if (name.endswith(".녹취.txt") or name.endswith(".녹취.json")
                    or name.endswith(".부분.jsonl")):
                continue
            if ext in AUDIO_EXTS:
                found.append(full)
        return found
    return []


def _exposed_to_git(folder):
    """결과를 이 폴더에 쓰면 git 추적 대상이 되는지 봅니다.

    저장소 안이면서 경로 어디에도 '사건' 폴더가 없는 자리가 그렇습니다. 사건 자료는
    각 폴더의 사건/ 아래에만 두고(루트 CLAUDE.md '파일 배치 규약'), .gitignore 는
    **/사건/ 으로 그 아래만 막습니다. 저장소 밖(바탕화면·다운로드 등)은 상관없습니다.
    """
    if not os.path.isfile(os.path.join(REPO_ROOT, ".gitignore")):
        return False  # 이 폴더를 저장소 밖으로 떼어 옮겨 쓰는 경우
    root = os.path.normcase(os.path.realpath(REPO_ROOT))
    target = os.path.normcase(os.path.realpath(folder or os.curdir))
    try:
        rel = os.path.relpath(target, root)
    except ValueError:  # Windows 에서 드라이브가 다르다
        return False
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        return False
    return "사건" not in rel.split(os.sep)


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _same_name(a, b):
    """파일 이름이 같은지. Windows 는 대소문자를 가리지 않습니다."""
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def _finished(base, audio_path, options):
    """같은 원본을 같은 조건으로 끝까지 전사한 결과가 base 에 있는지 봅니다."""
    if os.path.exists(base + ".부분.jsonl") or not os.path.exists(base + ".녹취.txt"):
        return False  # 지난 실행이 중간에 끊겼거나 전사본이 없다
    prev = _read_json(base + ".녹취.json")
    if not isinstance(prev, dict):
        return False
    try:
        size = os.path.getsize(audio_path)
        mtime = os.path.getmtime(audio_path)
    except OSError:
        return False
    recorded = prev.get("source_mtime")
    return (_same_name(prev.get("source_file", ""), os.path.basename(audio_path))
            and prev.get("source_size") == size
            # OneDrive·FAT 은 수정시각을 초 단위 이하에서 다르게 둘 수 있다
            and isinstance(recorded, (int, float)) and abs(recorded - mtime) <= 2
            and prev.get("transcribe_options") == options
            # 화자 분리를 요청했는데 지난번에 실패했으면 다시 해 본다
            and bool(prev.get("diarized") or not options.get("diarize")))


def _plan(inputs, out_dir, options, force=False):
    """입력마다 결과 파일 이름(앞부분)과 건너뛸지를 정합니다.

    이름은 원본에서 확장자를 뺀 것이 기본입니다(통화.m4a → 통화.녹취.txt). 확장자만 다른
    원본(통화.m4a·통화.mp4)이 함께 있거나 그 이름의 결과가 이미 다른 원본의 것이면, 서로
    덮어쓰지 않도록 확장자까지 넣습니다(통화.mp4.녹취.txt). --force 여도 다른 원본의 결과는
    덮어쓰지 않습니다.
    """
    plain = {}
    for p in inputs:
        folder = out_dir if out_dir else os.path.dirname(p)
        plain[p] = os.path.join(folder, os.path.splitext(os.path.basename(p))[0])
    shared = {}
    for base in plain.values():
        key = os.path.normcase(os.path.abspath(base))
        shared[key] = shared.get(key, 0) + 1

    def owner(base):
        prev = _read_json(base + ".녹취.json")
        return prev.get("source_file") if isinstance(prev, dict) else None

    jobs = []
    for p in inputs:
        name = os.path.basename(p)
        base = plain[p]
        qualified = os.path.join(os.path.dirname(base), name)
        renamed = False
        plain_owner = owner(base)
        if _same_name(owner(qualified) or "", name):
            base, renamed = qualified, True      # 전에 확장자까지 넣어 저장한 원본
        elif plain_owner and _same_name(plain_owner, name):
            pass
        elif plain_owner or shared[os.path.normcase(os.path.abspath(base))] > 1:
            base, renamed = qualified, True
        jobs.append({"audio": p, "base": base, "renamed": renamed,
                     "skip": not force and _finished(base, p, options)})
    return jobs


def _overlaps(a_start, a_end, b_start, b_end):
    """두 구간이 겹치는지. 길이 0인 구간은 상대 구간 안에 있으면 겹친 것으로 봅니다."""
    if max(a_start, b_start) < min(a_end, b_end):
        return True
    return a_start == a_end and b_start <= a_start <= b_end


def _resolve_device(device):
    """device 가 auto 면 GPU 유무를 실제로 확인해 cuda/cpu 로 확정합니다."""
    if device != "auto":
        return device
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _compute_type_candidates(device, requested):
    """요청한 연산 정밀도부터 시도하고, 실패에 대비한 폴백 순서를 만듭니다."""
    if device == "cuda":
        chain = [requested, "float16", "float32"]
    else:
        # 일부 CPU/백엔드는 int8 을 지원하지 않으므로 float32 로 폴백합니다.
        chain = [requested, "int8", "float32"]
    seen, ordered = set(), []
    for ct in chain:
        if ct and ct not in seen:
            seen.add(ct)
            ordered.append(ct)
    return ordered


def _load_model(model_name, device, compute_type):
    """faster-whisper 모델을 불러옵니다. 미설치 시 안내 후 종료합니다.

    연산 정밀도(int8 등)를 이 장치가 지원하지 않으면 지원되는 정밀도로 자동 폴백합니다.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        _log("")
        _log("[오류] faster-whisper 가 설치되어 있지 않습니다.")
        _log("5_녹취록 폴더의 '녹취록 환경설치.bat' 을 다시 실행하거나,")
        _log("지금 이 파이썬(가상환경)에 직접 설치하세요 (인터넷 필요):")
        _log("")
        _log(f'    "{sys.executable}" -m pip install -r "{os.path.join(HERE, "requirements-cpu.txt")}"')
        _log("")
        _log("설치 후 다시 실행하면 됩니다. (모델은 최초 1회 자동 다운로드됩니다)")
        sys.exit(2)

    device = _resolve_device(device)
    candidates = _compute_type_candidates(device, compute_type)

    _log(f"[모델 로드] {model_name} (device={device})")
    _log("  최초 실행이면 모델을 다운로드하므로 시간이 걸릴 수 있습니다...")

    last_err = None
    for ct in candidates:
        try:
            model = WhisperModel(model_name, device=device, compute_type=ct)
            _log(f"  연산 정밀도: {ct}")
            return model
        except ValueError as exc:
            # 이 장치가 지원하지 않는 정밀도이면 다음 후보로 넘어갑니다.
            last_err = exc
            _log(f"  '{ct}' 정밀도 미지원 → 다른 정밀도로 재시도합니다.")
            continue
    raise RuntimeError(
        f"지원되는 연산 정밀도를 찾지 못했습니다 (시도: {', '.join(candidates)}). "
        f"마지막 오류: {last_err}"
    )


def _review_flag(avg_logprob, no_speech_prob):
    """설계안 기준으로 '확인 필요 구간'인지 판정합니다."""
    reasons = []
    if avg_logprob is not None and avg_logprob < REVIEW_AVG_LOGPROB:
        reasons.append(f"인식 신뢰도 낮음(avg_logprob {avg_logprob:.2f})")
    if no_speech_prob is not None and no_speech_prob > REVIEW_NO_SPEECH:
        reasons.append(f"말이 아닐 가능성(no_speech_prob {no_speech_prob:.2f})")
    return reasons


def transcribe_one(model, audio_path, out_dir, language, use_vad, condition,
                   diarize=False, num_speakers=0, cluster_threshold=0.8,
                   initial_prompt=None, base=None, options=None):
    """오디오 한 개를 변환하고 .녹취.txt / .녹취.json 을 저장합니다.

    세그먼트가 나올 때마다 즉시 파일에 기록하므로 긴 녹음이 중간에 끊겨도
    그때까지의 결과는 남습니다.

    base 를 주면 결과 파일 이름의 앞부분으로 씁니다(main 이 이름 겹침을 피해 정한 것).
    options 는 다시 돌릴 때 건너뛸지 판단하도록 .녹취.json 에 적어 두는 전사 조건입니다.
    """
    if base is None:
        stem = os.path.splitext(os.path.basename(audio_path))[0]
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            base = os.path.join(out_dir, stem)
        else:
            base = os.path.join(os.path.dirname(audio_path), stem)
    elif os.path.dirname(base):
        os.makedirs(os.path.dirname(base), exist_ok=True)

    txt_path = base + ".녹취.txt"
    json_path = base + ".녹취.json"
    part_path = base + ".부분.jsonl"

    # 읽기 시작하는 시점의 원본 크기·수정시각. 다음 실행이 같은 원본인지 이것으로 가린다.
    source_size = os.path.getsize(audio_path)
    source_mtime = int(os.path.getmtime(audio_path))

    _log(f"\n[변환 시작] {os.path.basename(audio_path)}")
    if os.path.exists(part_path):
        _log(f"  [지난 실행이 중간에 끊긴 기록] {part_path} — 처음부터 다시 전사합니다.")

    # 화자 분리를 먼저 수행합니다(오디오 목소리 기준으로 누가 언제 말했는지 산출).
    diar_segments = None
    if diarize:
        try:
            import diarize as diar_mod
            _log("  [화자 분리] 목소리 기준으로 화자를 나눕니다...")
            diar_segments = diar_mod.diarize(
                audio_path, num_speakers=num_speakers, cluster_threshold=cluster_threshold
            )
            n_spk = len({spk for _, _, spk in diar_segments})
            _log(f"  [화자 분리] 완료 — 화자 {n_spk}명, 구간 {len(diar_segments)}개")
        except Exception as exc:  # noqa: BLE001 — 화자분리 실패 시 일반 전사로 진행
            _log(f"  [화자 분리 실패] {exc}")
            _log("  → 화자 표시 없이 일반 전사로 진행합니다.")
            diar_segments = None

    transcribe_kwargs = dict(
        beam_size=5,
        vad_filter=use_vad,
        vad_parameters=dict(min_silence_duration_ms=500) if use_vad else None,
        # 환각·반복 루프 억제: 이전 문장을 조건으로 물리지 않으면 같은 문구 반복이 크게 줄어듭니다.
        condition_on_previous_text=condition,
        # 무음/잡음 구간이 억지로 문장으로 변환되는 것을 걸러냅니다.
        no_speech_threshold=0.6,
        compression_ratio_threshold=2.4,
        temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        # 화자 분리 시 단어 단위 타임스탬프로 화자를 배정합니다.
        word_timestamps=bool(diar_segments),
    )
    if language and language.lower() != "auto":
        transcribe_kwargs["language"] = language
    if initial_prompt:
        # 노동사건 어휘를 미리 물려 고유명사·전문용어 오인식을 줄입니다.
        transcribe_kwargs["initial_prompt"] = initial_prompt

    segments, info = model.transcribe(audio_path, **transcribe_kwargs)

    detected = getattr(info, "language", None) or (language or "?")
    duration = getattr(info, "duration", None)
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    if diar_segments:
        n_spk = len({spk for _, _, spk in diar_segments})
        speaker_note = (f"화자 표기 : '화자1·화자2…'는 목소리 기준 자동 분리 결과(추정 {n_spk}명)입니다. "
                        "누가 화자1인지는 아직 정해지지 않았습니다.")
    else:
        n_spk = 0
        speaker_note = "화자 표기 : 화자 분리를 하지 않았습니다. 구간만 나뉘어 있습니다."
    header = [
        "녹취 원본 (자동 변환 — 확인 전 초안)",
        f"원본 파일 : {os.path.basename(audio_path)}",
        f"감지 언어 : {detected}",
        f"녹음 길이 : {_hhmmss(duration) if duration else '알 수 없음'}",
        f"변환 일시 : {now}",
        speaker_note,
        "─" * 40,
        "",
    ]

    # ── 증분 기록 ────────────────────────────────────────────────
    # 세그먼트가 나올 때마다 바로 쓰고 flush 합니다. 중간에 끊겨도 남습니다.
    # 화자 분리를 하는 경우 이 단계에서는 화자 자리를 비워 두고,
    # 전사가 끝난 뒤 단어를 화자 구간에 배정해 이 파일을 다시 씁니다.
    seg_list = []
    words = []
    # 전사본을 새로 쓰기 시작하면 예전 .녹취.json 은 짝이 맞지 않는다. 이번 실행이 끊기면
    # 전사본과 .부분.jsonl 만 남아 '끝나지 않은 결과'로 보이도록 먼저 지운다.
    try:
        os.remove(json_path)
    except OSError:
        pass
    txt_f = open(txt_path, "w", encoding="utf-8")
    part_f = open(part_path, "w", encoding="utf-8")
    try:
        txt_f.write("\n".join(header) + "\n")
        txt_f.flush()

        for seg in segments:
            text = (seg.text or "").strip()
            if not text:
                continue
            start = float(seg.start) if seg.start is not None else 0.0
            end = float(seg.end) if seg.end is not None else start
            alp = getattr(seg, "avg_logprob", None)
            nsp = getattr(seg, "no_speech_prob", None)
            rec = {
                "start": round(start, 3),
                "end": round(end, 3),
                "text": text,
                "avg_logprob": round(alp, 4) if alp is not None else None,
                "no_speech_prob": round(nsp, 4) if nsp is not None else None,
            }
            reasons = _review_flag(alp, nsp)
            if reasons:
                rec["review"] = reasons
            seg_list.append(rec)

            if diar_segments:
                for w in (seg.words or []):
                    wt = (w.word or "").strip()
                    if wt:
                        words.append((float(w.start), float(w.end), wt))

            mark = " ※확인" if reasons else ""
            txt_f.write(f"[{_hhmmss(start)}] {text}{mark}\n")
            txt_f.flush()
            part_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            part_f.flush()
            _log(f"  [{_hhmmss(start)}] {text}{mark}")
    finally:
        txt_f.close()
        part_f.close()

    # ── 화자 구간 배정 ───────────────────────────────────────────
    turn_list = []
    if diar_segments and words:
        import diarize as diar_mod
        turns = diar_mod.assign_words_to_speakers(words, diar_segments)
        flagged_segs = [s for s in seg_list if s.get("review")]
        lines = []
        for start, end, spk, text in turns:
            text = text.strip()
            if not text:
                continue
            label = f"화자{spk + 1}" if spk is not None else "화자?"
            turn = {"start": round(start, 3), "end": round(end, 3),
                    "speaker": spk, "label": label, "text": text}
            # 화자 판으로 다시 써도 확인 필요 구간이 걸친 발화 줄에는 ※확인 을 남긴다.
            mark = ""
            if any(_overlaps(start, end, s["start"], s["end"]) for s in flagged_segs):
                turn["review"] = True
                mark = " ※확인"
            turn_list.append(turn)
            lines.append(f"[{_hhmmss(start)}] {label}: {text}{mark}")
        if lines:
            # 화자가 붙은 판으로 .녹취.txt 를 다시 씁니다.
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(header + lines) + "\n")
            _log(f"  [화자 배정] 발화 턴 {len(turn_list)}개")

    # ── 확인 필요 구간 ───────────────────────────────────────────
    review = [s for s in seg_list if s.get("review")]
    if review:
        with open(txt_path, "a", encoding="utf-8") as f:
            f.write("\n" + "─" * 40 + "\n")
            f.write(f"확인 필요 구간 {len(review)}곳 — 이 부분만 원본을 들어 확인하세요.\n\n")
            for s in review:
                f.write(f"[{_hhmmss(s['start'])}] {s['text']}\n")
                f.write(f"    사유: {'; '.join(s['review'])}\n")
    _log(f"  [확인 필요 구간] {len(review)}곳")

    meta = {
        "source_file": os.path.basename(audio_path),
        "source_path": os.path.abspath(audio_path),
        "source_size": source_size,
        "source_mtime": source_mtime,
        "transcribe_options": options,
        "language": detected,
        "duration_sec": round(duration, 3) if duration else None,
        "converted_at": now,
        "model_initial_prompt": initial_prompt or None,
        "diarized": bool(diar_segments),
        "speaker_count": n_spk,
        "segment_count": len(seg_list),
        "segments": seg_list,
        "turns": turn_list,
        "review_needed": review,
        "review_criteria": {
            "avg_logprob_below": REVIEW_AVG_LOGPROB,
            "no_speech_prob_above": REVIEW_NO_SPEECH,
        },
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 정상 종료했으므로 중간 기록 파일은 지웁니다.
    try:
        os.remove(part_path)
    except OSError:
        pass

    _log(f"[저장 완료] {txt_path}")
    _log(f"[저장 완료] {json_path}  (구간 {len(seg_list)}개)")
    return txt_path, json_path


def main():
    parser = argparse.ArgumentParser(
        description="사건 녹음을 로컬에서 텍스트로 변환합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="오디오/영상 파일 또는 그 파일들이 든 폴더")
    parser.add_argument("--output-dir", default=None, help="결과 저장 폴더")
    parser.add_argument("--model", default="large-v3-turbo",
                        help="모델 크기 (기본: large-v3-turbo — large-v3보다 빠르고 반복 환각이 적음)")
    parser.add_argument("--language", default="ko", help="언어 코드 (기본: ko, 자동감지: auto)")
    parser.add_argument("--compute-type", default="int8", help="연산 정밀도 (기본: int8)")
    parser.add_argument("--device", default="cpu", help="cpu / cuda / auto (기본: cpu)")
    parser.add_argument("--no-vad", action="store_true", help="무음 제거(VAD) 끄기")
    parser.add_argument("--condition", action="store_true",
                        help="이전 문장을 조건으로 사용(문맥 일관성↑, 단 반복 환각 위험↑). 기본은 꺼짐")
    parser.add_argument("--diarize", action="store_true",
                        help="화자 분리: 목소리 기준으로 구간을 나눠 화자1·화자2로 표기")
    parser.add_argument("--num-speakers", type=int, default=0,
                        help="화자 수를 알면 지정(통화는 2). 0이면 자동 판단하나 과분할하기 쉬움")
    parser.add_argument("--cluster-threshold", type=float, default=0.8,
                        help="화자 자동 판단 임계값(작을수록 더 잘게 나눔). 기본 0.8")
    parser.add_argument("--initial-prompt", default=None,
                        help="인식 힌트 문장 교체 (기본: 노동사건 어휘)")
    parser.add_argument("--no-initial-prompt", action="store_true",
                        help="인식 힌트를 쓰지 않습니다")
    parser.add_argument("--force", action="store_true",
                        help="같은 원본을 같은 조건으로 끝낸 결과가 있어도 다시 전사합니다")
    args = parser.parse_args()

    if args.no_initial_prompt:
        initial_prompt = None
    else:
        initial_prompt = args.initial_prompt or LABOR_INITIAL_PROMPT

    inputs = _collect_inputs(args.input)
    if not inputs:
        _log(f"[오류] 변환할 오디오/영상 파일을 찾지 못했습니다: {args.input}")
        _log(f"  지원 확장자: {', '.join(sorted(AUDIO_EXTS))}")
        sys.exit(1)

    exposed = sorted({os.path.abspath(args.output_dir or os.path.dirname(p) or os.curdir)
                      for p in inputs
                      if _exposed_to_git(args.output_dir or os.path.dirname(p))})
    if exposed:
        _log("[중단] 전사 결과가 저장소 안이면서 사건/ 밖인 곳에 생깁니다.")
        for folder in exposed:
            _log(f"  - {folder}")
        _log("  전사본에는 대화 전문이 들어가므로 git 에 올라가지 않는 사건/ 아래에만 둡니다.")
        _log("  녹음을 5_녹취록/사건/{사건폴더}/원본/ 으로 옮겨 사건 폴더명으로 실행하거나,")
        _log("  --output-dir 로 사건/ 아래 폴더를 지정하십시오.")
        sys.exit(2)

    # 결과에 영향을 주는 조건. 이것이 같고 원본도 같으면 다시 전사하지 않는다.
    options = {
        "model": args.model,
        "language": args.language,
        "vad": not args.no_vad,
        "condition": args.condition,
        "diarize": args.diarize,
        "num_speakers": args.num_speakers,
        "cluster_threshold": args.cluster_threshold,
        "initial_prompt": initial_prompt,
    }
    jobs = _plan(inputs, args.output_dir, options, force=args.force)

    _log(f"[대상] {len(inputs)}개 파일")
    for job in jobs:
        note = ""
        if job["skip"]:
            note = "  → 건너뜀(같은 조건으로 끝낸 결과가 있음)"
        elif job["renamed"]:
            note = f"  → 이름이 겹쳐 {os.path.basename(job['base'])}.녹취.txt 로 저장"
        _log(f"  - {os.path.basename(job['audio'])}{note}")

    todo = [job for job in jobs if not job["skip"]]
    skipped = [job for job in jobs if job["skip"]]
    model = _load_model(args.model, args.device, args.compute_type) if todo else None

    results, failures = [], []
    for job in todo:
        audio_path = job["audio"]
        try:
            txt_path, json_path = transcribe_one(
                model, audio_path, args.output_dir, args.language,
                not args.no_vad, args.condition,
                diarize=args.diarize, num_speakers=args.num_speakers,
                cluster_threshold=args.cluster_threshold,
                initial_prompt=initial_prompt,
                base=job["base"], options=options,
            )
            results.append((audio_path, txt_path, json_path))
        except Exception as exc:  # noqa: BLE001 — 한 파일 실패해도 나머지는 계속
            _log(f"[실패] {os.path.basename(audio_path)} — {exc}")
            failures.append((audio_path, str(exc)))

    _log("\n" + "=" * 40)
    _log(f"[전체 완료] 성공 {len(results)}개 / 건너뜀 {len(skipped)}개 / 실패 {len(failures)}개")
    for _, txt_path, _json in results:
        _log(f"  ✔ {txt_path}")
    for job in skipped:
        _log(f"  = {job['base']}.녹취.txt (이미 전사됨)")
    for audio_path, err in failures:
        _log(f"  ✗ {os.path.basename(audio_path)}: {err}")
    if skipped:
        _log("  건너뛴 파일을 다시 전사하려면 --force 를 붙입니다(녹취.ps1 은 -Force).")

    if failures and not (results or skipped):
        sys.exit(1)


if __name__ == "__main__":
    main()
