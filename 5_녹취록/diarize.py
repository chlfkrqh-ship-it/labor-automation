# -*- coding: utf-8 -*-
"""화자 분리(speaker diarization) 모듈.

sherpa-onnx 의 오프라인 화자분리(세그멘테이션 + 화자임베딩 클러스터링)를 사용합니다.
HuggingFace 토큰이 필요 없고 전부 로컬에서 실행됩니다.
모델이 없으면 download_diarization_models.py 를 먼저 실행하세요.
"""
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")
SEG_MODEL = os.path.join(MODELS_DIR, "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")
EMB_MODEL = os.path.join(MODELS_DIR, "3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx")

SAMPLE_RATE = 16000


class DiarizationUnavailable(Exception):
    pass


def load_samples_16k(audio_path):
    """오디오를 16kHz mono float32 numpy 배열로 디코딩합니다."""
    import av
    inp = av.open(audio_path)
    stream = [s for s in inp.streams if s.type == "audio"][0]
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks = []
    for frame in inp.decode(stream):
        for rf in resampler.resample(frame):
            arr = rf.to_ndarray().reshape(-1).astype(np.float32) / 32768.0
            chunks.append(arr)
    inp.close()
    if not chunks:
        return np.zeros(1, dtype=np.float32)
    return np.concatenate(chunks)


def _build_diarizer(num_speakers, cluster_threshold):
    try:
        import sherpa_onnx
    except ImportError:
        raise DiarizationUnavailable(
            "sherpa-onnx 가 설치되어 있지 않습니다. 'pip install sherpa-onnx' 를 실행하세요."
        )
    if not os.path.exists(SEG_MODEL) or not os.path.exists(EMB_MODEL):
        # 모델이 없으면 최초 1회 자동으로 내려받습니다(HuggingFace 토큰 불필요).
        try:
            import download_diarization_models as dl
            print("[화자분리] 모델이 없어 자동 다운로드합니다 (최초 1회)...", flush=True)
            dl.ensure_models()
        except Exception as exc:
            raise DiarizationUnavailable(
                "화자분리 모델 다운로드에 실패했습니다. "
                "'python scripts/download_diarization_models.py' 를 수동 실행해 보세요. "
                f"(원인: {exc})"
            )

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=SEG_MODEL),
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=EMB_MODEL),
        clustering=sherpa_onnx.FastClusteringConfig(
            # num_clusters>0 이면 화자 수를 그 값으로 고정, 아니면 threshold 로 자동 판단
            num_clusters=int(num_speakers) if num_speakers and num_speakers > 0 else -1,
            threshold=float(cluster_threshold),
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not config.validate():
        raise DiarizationUnavailable("화자분리 설정이 유효하지 않습니다. 모델 경로를 확인하세요.")
    return sherpa_onnx.OfflineSpeakerDiarization(config)


def diarize(audio_path, num_speakers=0, cluster_threshold=0.5, progress=None):
    """오디오의 화자 구간을 [(start, end, speaker_int), ...] 로 반환합니다."""
    sd = _build_diarizer(num_speakers, cluster_threshold)
    samples = load_samples_16k(audio_path)

    if progress is not None:
        def _cb(processed_chunks, total_chunks, _arg=None):
            try:
                progress(processed_chunks, total_chunks)
            except Exception:
                pass
            return 0
        try:
            result = sd.process(samples, callback=_cb)
        except TypeError:
            result = sd.process(samples)
    else:
        result = sd.process(samples)

    segments = result.sort_by_start_time()
    return [(float(s.start), float(s.end), int(s.speaker)) for s in segments]


def speaker_for_interval(diar_segments, w_start, w_end):
    """단어 구간 [w_start, w_end] 의 화자를 정합니다.

    화자 구간은 서로 겹친다. 짧은 맞장구가 상대방의 긴 발화 구간 안에
    통째로 들어앉기도 한다. 그래서 한 시점을 찍어 보는 대신 **겹침 총량**
    으로 정한다. 시점으로 찍으면 겹친 구간 중 무엇을 고르든 한쪽으로
    치우친다. 먼저 걸린 것을 쓰면 긴 구간이 늘 이겨 짧은 발화가 삼켜지고,
    짧은 것을 쓰면 잡음 구간이 이겨 문장 중간에서 화자가 튄다.
    """
    if w_end < w_start:
        w_start, w_end = w_end, w_start
    span = max(w_end - w_start, 1e-6)

    # 화자마다 겹친 총량과, 겹친 구간 중 가장 짧은 것의 길이를 함께 모은다.
    overlap = {}
    shortest = {}
    for start, end, spk in diar_segments:
        ov = min(w_end, end) - max(w_start, start)
        if ov > 0:
            overlap[spk] = overlap.get(spk, 0.0) + ov
            seg_len = end - start
            if spk not in shortest or seg_len < shortest[spk]:
                shortest[spk] = seg_len

    if overlap:
        # 겹침이 많은 쪽. 겹침이 같으면 더 짧은 구간을 낸 쪽.
        #
        # 짧은 맞장구가 상대방의 긴 발화 구간 안에 통째로 들어앉으면 두 화자의
        # 겹침이 똑같아진다. 이때 먼저 걸린 쪽(늘 긴 구간)을 쓰면 맞장구가
        # 한 건도 살아남지 못한다. 4분짜리 통화에서 화자2의 13개 구간이
        # 전부 이렇게 삼켜져 녹취록이 한 덩어리로 나왔다.
        # 더 짧은 구간이 더 좁혀 말하는 근거이므로 그쪽을 택한다.
        best = min(overlap, key=lambda s: (-overlap[s], shortest[s]))
        # 겹침이 단어 길이의 10% 도 안 되면 근거가 약하다고 보고 근접 구간에 맡긴다.
        if overlap[best] >= span * 0.1:
            return best

    mid = (w_start + w_end) / 2.0
    nearest, nearest_dist = None, None
    for start, end, spk in diar_segments:
        dist = 0.0 if start <= mid <= end else min(abs(mid - start), abs(mid - end))
        if nearest_dist is None or dist < nearest_dist:
            nearest, nearest_dist = spk, dist
    return nearest


def speaker_at(diar_segments, t):
    """시각 t(초)의 화자 번호. 예전 호출부를 위해 남겨 둡니다."""
    return speaker_for_interval(diar_segments, t, t)


def smooth(labels, min_run=1):
    """짧게 튄 화자 라벨을 앞뒤와 같게 되돌립니다.

    **기본값은 되돌리지 않는 것(min_run=1)이다.** 47초 통화로 실측해 보니
    되돌리기를 켜면 "예.", "예, 예." 같은 한두 마디 맞장구가 상대방 발화에
    흡수되어 사라졌다(턴 12개 → min_run=2 에서 10개, 3 에서 6개). 맞장구는
    녹취서에서 동의·인지 여부를 다투는 근거가 되므로 지우면 안 된다.

    경계에서 한 단어가 튀는 것이 거슬리는 녹음에서만 2 이상을 준다.
    """
    if not labels or min_run <= 1:
        return list(labels)
    out = list(labels)
    i = 0
    while i < len(out):
        j = i
        while j < len(out) and out[j] == out[i]:
            j += 1
        run = j - i
        if 0 < i and j < len(out) and run < min_run and out[i - 1] == out[j]:
            for k in range(i, j):
                out[k] = out[i - 1]
        i = j
    return out


def assign_words_to_speakers(words, diar_segments, min_run=1):
    """단어 리스트[(start, end, text)]를 화자별 발화 턴으로 묶습니다.

    반환: [(turn_start, turn_end, speaker_int, text), ...]
    """
    if not words:
        return []

    # 1) 단어마다 겹침 총량으로 화자를 정하고
    labels = [speaker_for_interval(diar_segments, s, e) for s, e, _ in words]
    # 2) (기본값은 아무것도 하지 않음. smooth() 주석 참고)
    labels = smooth(labels, min_run)

    # 3) 같은 화자가 이어지는 만큼 하나의 발화 턴으로 묶는다.
    turns = []
    cur_spk, cur_start, cur_end, cur_words = labels[0], words[0][0], words[0][1], []
    for (start, end, text), spk in zip(words, labels):
        if spk != cur_spk:
            if cur_words:
                turns.append((cur_start, cur_end, cur_spk, " ".join(cur_words).strip()))
            cur_spk, cur_start, cur_words = spk, start, []
        cur_end = end
        cur_words.append(text.strip())
    if cur_words:
        turns.append((cur_start, cur_end, cur_spk, " ".join(cur_words).strip()))
    return turns
