# -*- coding: utf-8 -*-
"""화자 분리(speaker diarization) 모듈.

sherpa-onnx 의 오프라인 화자분리(세그멘테이션 + 화자임베딩 클러스터링)를 사용합니다.
HuggingFace 토큰이 필요 없고 전부 로컬에서 실행됩니다.
모델이 없으면 download_diarization_models.py 를 먼저 실행하세요.

화자 수를 지정한 경우에는 같은 두 모델을 쓰되 군집만 이 파일에서 따로 합니다
(cluster_known_count 참고). sherpa-onnx 의 군집은 화자 수를 주면 한두 마디 맞장구에서
나온 임베딩을 한 화자로 떼어 내고 실제 화자들을 한데 묶는 일이 있습니다.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")
SEG_MODEL = os.path.join(MODELS_DIR, "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")
EMB_MODEL = os.path.join(MODELS_DIR, "3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx")

SAMPLE_RATE = 16000
THREADS = max(1, min(4, os.cpu_count() or 1))

# sherpa-onnx 와 같은 값. 이보다 짧은 구간은 버리고, 이보다 짧은 끊김은 잇는다(초).
MIN_DURATION_ON = 0.3
MIN_DURATION_OFF = 0.5

# 화자 수를 아는 경우의 군집에서, 화자 중심을 잡는 데 쓰는 임베딩의 최소 음성 길이(초).
# 이보다 짧게 말한 구간(맞장구 등)의 임베딩은 중심을 잡는 데 쓰지 않고 가까운 중심에 붙인다.
CENTER_MIN_SECONDS = 2.0

# 단어를 화자에 붙인 뒤의 정리(settle_phrases)에 쓰는 값.
SENTENCE_END = ".?!"
MAX_STRAY_WORDS = 3      # 이 단어 수 이하로 튄 조각만 구의 주된 화자에게 돌린다
MAX_PHRASE_WORDS = 20    # 이보다 긴 것은 한 사람이 한 번에 한 말로 보지 않는다
# 한두 마디로 받는 말. 상대의 말 사이에 끼어 있어도 그 사람의 말로 남겨 둔다. 맞장구는
# 녹취서에서 동의·인지 여부를 다투는 근거가 되므로 상대의 말에 섞어 넣지 않는다.
RESPONSE_WORDS = frozenset((
    "네", "예", "응", "어", "음", "아", "오", "네네", "예예", "응응", "어어", "네네네",
    "그래", "그래요", "그럼", "그럼요", "그렇지", "그렇죠", "그치", "그쵸",
    "맞아", "맞아요", "맞습니다", "아니", "아니요", "아뇨", "아니에요",
))


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


def _import_sherpa():
    try:
        import sherpa_onnx
    except ImportError:
        # 녹취.ps1 은 %LOCALAPPDATA% 의 가상환경 파이썬으로 돈다. PATH 의 pip 로 깔면 그 환경에 들어가지 않는다.
        raise DiarizationUnavailable(
            "sherpa-onnx 가 설치되어 있지 않습니다. 5_녹취록 폴더의 '녹취록 환경설치.bat' 을 다시 "
            f"실행하거나 \"{sys.executable}\" -m pip install sherpa-onnx 를 실행하세요."
        )
    return sherpa_onnx


def _ensure_models():
    if not os.path.exists(SEG_MODEL) or not os.path.exists(EMB_MODEL):
        # 모델이 없으면 최초 1회 자동으로 내려받습니다(HuggingFace 토큰 불필요).
        try:
            import download_diarization_models as dl
            print("[화자분리] 모델이 없어 자동 다운로드합니다 (최초 1회)...", flush=True)
            dl.ensure_models()
        except Exception as exc:
            raise DiarizationUnavailable(
                "화자분리 모델 다운로드에 실패했습니다. 인터넷 연결을 확인한 뒤 "
                f"\"{sys.executable}\" \"{os.path.join(HERE, 'download_diarization_models.py')}\" "
                f"를 실행해 보세요. (원인: {exc})"
            )


def _build_diarizer(num_speakers, cluster_threshold):
    sherpa_onnx = _import_sherpa()
    _ensure_models()

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
        min_duration_on=MIN_DURATION_ON,
        min_duration_off=MIN_DURATION_OFF,
    )
    if not config.validate():
        raise DiarizationUnavailable("화자분리 설정이 유효하지 않습니다. 모델 경로를 확인하세요.")
    return sherpa_onnx.OfflineSpeakerDiarization(config)


class _Segmenter:
    """세그멘테이션 모델(pyannote segmentation-3.0)을 ONNX Runtime 으로 직접 돌립니다.

    10초 창을 1초씩 옮겨 가며, 창마다 '그 창 안의 화자'(최대 3명)가 프레임별로 말하는지를
    냅니다. 창 안의 화자 번호는 창마다 따로이므로 창끼리 같은 사람을 잇는 일은 임베딩
    군집이 합니다. 창 크기·이동·구간 환산은 sherpa-onnx 와 같게 맞췄습니다. 여기에
    sherpa-onnx 의 군집을 끼우면 sherpa-onnx 와 같은 화자 구간이 나옵니다(_speech_parts 의
    표본 자리 참고).
    """

    def __init__(self):
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = THREADS
        self.session = ort.InferenceSession(SEG_MODEL, sess_options=opts,
                                            providers=["CPUExecutionProvider"])
        meta = self.session.get_modelmeta().custom_metadata_map
        self.window = int(meta["window_size"])
        self.shift = int(0.1 * self.window)
        self.rf_size = int(meta["receptive_field_size"])
        self.rf_shift = int(meta["receptive_field_shift"])
        local = int(meta["num_speakers"])
        # 모델은 '아무도 안 함 / 한 명 / 두 명 동시'를 한 클래스로 낸다. 화자별 0·1 로 푼다.
        classes = [()] + [(a,) for a in range(local)]
        classes += [(a, b) for a in range(local) for b in range(a + 1, local)]
        if int(meta["num_classes"]) != len(classes):
            raise RuntimeError("세그멘테이션 모델의 클래스 구성이 예상과 다릅니다.")
        self.mapping = np.zeros((len(classes), local), dtype=np.int8)
        for index, speakers in enumerate(classes):
            self.mapping[index, list(speakers)] = 1

    def local_speakers(self, samples):
        """(창 수, 프레임 수, 창 안의 화자 수) 크기의 0·1 배열과, 마지막 창을 채웠는지를 냅니다."""
        n = len(samples)
        full = (n - self.window) // self.shift + 1 if n >= self.window else 0
        padded = n < self.window or (n - self.window) % self.shift > 0
        chunks = full + (1 if padded else 0)
        name = self.session.get_inputs()[0].name
        out = []
        for first in range(0, chunks, 16):
            batch = np.zeros((min(16, chunks - first), 1, self.window), dtype=np.float32)
            for row in range(len(batch)):
                start = (first + row) * self.shift
                piece = samples[start:start + self.window]
                batch[row, 0, :len(piece)] = piece
            scores = self.session.run(None, {name: batch})[0]
            out.append(self.mapping[np.argmax(scores, axis=-1)])
        return np.concatenate(out), padded

    def frame_start(self, chunk):
        """창 번호 → 그 창의 첫 프레임이 전체 프레임열에서 놓이는 자리."""
        return int(chunk * self.shift / self.rf_shift + 0.5)

    def total_frames(self, chunks):
        return int((self.window + (chunks - 1) * self.shift) / self.rf_shift) + 1


def _speech_parts(labels, seg):
    """창 안의 화자마다, 혼자 말한 부분의 표본 구간들을 모읍니다.

    반환: [(창 번호, 창 안의 화자 번호)], [[(시작 표본, 끝 표본), ...]], [음성 길이(초)]

    두 사람이 겹쳐 말한 프레임은 뺀다(임베딩에 두 목소리가 섞인다). 남은 것이 10프레임
    (약 0.17초)에 못 미치면 그 창에서는 그 화자의 임베딩을 뽑지 않는다.

    표본 자리는 sherpa-onnx 와 한 표본씩 어긋나는 곳이 있다. sherpa-onnx 는 창 시작 자리를
    더한 값을 float32 로 계산해 큰 수에서 반올림이 생긴다. 그 정도 차이로 화자 구간이 달라져서는
    안 되는데, sherpa-onnx 의 군집은 8분 통화에서 화자 구간의 6%가 달라졌다(cluster_known_count
    는 0.2%). float32 로 맞춰 계산하면 sherpa-onnx 군집을 끼운 결과가 sherpa-onnx 와 같다.
    """
    solo = labels * (labels.sum(axis=-1, keepdims=True) < 2)
    chunks, frames, local = solo.shape
    pairs, parts, seconds = [], [], []
    for chunk in range(chunks):
        offset = chunk * seg.shift
        for speaker in range(local):
            active = solo[chunk, :, speaker]
            count = int(active.sum())
            if count < 10:
                continue
            edge = np.diff(np.concatenate(([0], active, [0])))
            starts = np.flatnonzero(edge == 1)
            # 창 끝까지 이어지면 마지막 프레임에서 끊는다(sherpa-onnx 와 같게).
            ends = np.minimum(np.flatnonzero(edge == -1), frames - 1)
            parts.append([(int(s / frames * seg.window) + offset, int(e / frames * seg.window) + offset)
                          for s, e in zip(starts, ends)])
            pairs.append((chunk, speaker))
            seconds.append(count * seg.rf_shift / SAMPLE_RATE)
    return pairs, parts, seconds


def _embeddings(samples, parts, progress=None):
    """표본 구간 묶음마다 화자 임베딩을 하나씩 뽑습니다. 못 뽑은 자리는 None 입니다."""
    sherpa_onnx = _import_sherpa()
    extractor = sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=EMB_MODEL, num_threads=THREADS))
    out = []
    for done, spans in enumerate(parts, 1):
        stream = extractor.create_stream()
        stream.accept_waveform(sample_rate=SAMPLE_RATE,
                               waveform=np.concatenate([samples[s:e] for s, e in spans]))
        stream.input_finished()
        vector = None
        if extractor.is_ready(stream):
            vector = np.asarray(extractor.compute(stream), dtype=np.float64)
            if not np.all(np.isfinite(vector)) or not np.any(vector):
                vector = None
        out.append(vector)
        if progress is not None:
            try:
                progress(done, len(parts))
            except Exception:
                pass
    return out


def _spherical_kmeans(x, weight, k, seed):
    """단위 벡터 x 를 코사인 유사도로 k 묶음으로 나눕니다. (중심, 점수)를 돌려줍니다."""
    rng = np.random.default_rng(seed)
    # 이미 고른 중심과 덜 닮은 임베딩을 다음 중심으로 뽑는다(k-means++ 방식).
    centers = [x[rng.choice(len(x), p=weight / weight.sum())]]
    while len(centers) < k:
        far = np.clip(1.0 - np.max(x @ np.array(centers).T, axis=1), 0.0, None) ** 2 * weight
        if far.sum() <= 0:
            far = weight
        centers.append(x[rng.choice(len(x), p=far / far.sum())])
    centers = np.array(centers)
    labels = None
    for _ in range(100):
        similarity = x @ centers.T
        new = np.argmax(similarity, axis=1)
        if labels is not None and np.array_equal(new, labels):
            break
        labels = new
        for c in range(k):
            members = labels == c
            if members.any():
                total = (x[members] * weight[members, None]).sum(axis=0)
            else:
                # 빈 묶음은 제 중심과 가장 덜 닮은 임베딩에서 다시 시작한다.
                total = x[np.argmin(np.max(similarity, axis=1))]
            centers[c] = total / (np.linalg.norm(total) + 1e-12)
    score = float((weight * np.max(x @ centers.T, axis=1)).sum())
    return centers, score


def cluster_known_count(embeddings, seconds, num_speakers, tries=None):
    """임베딩을 화자 num_speakers 명으로 나눕니다(화자 수를 아는 경우).

    embeddings: (임베딩 수, 차원), seconds: 임베딩마다 그것을 뽑은 음성 길이(초)
    반환: 임베딩마다 화자 번호(0 … num_speakers-1)

    sherpa-onnx 의 군집(완전 연결 계층 군집)은 화자 수를 주면 덴드로그램을 맨 위에서
    그 수만큼 자른다. 그런데 한두 마디 맞장구에서 뽑힌 임베딩은 누구와도 닮지 않아 맨 위
    갈래를 먼저 차지한다. 한쪽이 "네", "네네"로 받는 7분짜리 2인 통화에서 임베딩 758개가
    '23개 대 735개'로 갈려, 화자 구간이 362초 대 19초로 나오고 실제 두 사람은 한 화자로
    묶였다(같은 임베딩을 4명으로 자르면 290초·67초로 두 사람이 갈린다). 임베딩 모델이
    두 사람을 못 가른 것이 아니라 자르는 자리가 틀린 것이다. 3분 56초·4분 20초 통화도
    같았고(208초 대 12초, 212초 대 4초), 3명으로 지정한 대화는 2명만 나왔다.

    그래서 화자 수를 아는 경우에는 덴드로그램을 자르지 않고 화자 중심을 직접 잡는다.
    ① 충분히 길게 말한 구간(CENTER_MIN_SECONDS 이상)의 임베딩만으로 중심 num_speakers
    개를 잡고(음성 길이로 가중한 구형 k-평균), ② 모든 임베딩을 가까운 중심에 붙인다.
    짧은 맞장구는 중심을 흔들지 못하고 가까운 화자에게 간다. 예전 군집으로 잘 나뉘던
    47초·41초 통화는 결과가 그대로다.

    k-평균은 시작 값에 따라 답이 갈린다(3명 대화에서 점수가 가장 높은 답이 나온 것은 시작
    100가지 중 40가지, 위 7분 통화는 72가지). 그래서 화자 수의 10배만큼 시작을 바꿔 돌려
    점수가 가장 높은 것을 쓴다. 시작 값은 정해져 있어 같은 녹음에는 늘 같은 답이 나온다.
    """
    x = np.asarray(embeddings, dtype=np.float64)
    x = x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)
    seconds = np.maximum(np.asarray(seconds, dtype=np.float64), 1e-6)
    k = max(1, min(int(num_speakers), len(x)))
    if k == 1:
        return np.zeros(len(x), dtype=int)

    # 길게 말한 구간이 모자라면 기준을 낮춘다(짧은 녹음, 한쪽이 맞장구만 한 녹음).
    chosen = np.ones(len(x), dtype=bool)
    for floor in (CENTER_MIN_SECONDS, CENTER_MIN_SECONDS / 2, CENTER_MIN_SECONDS / 4):
        long_enough = seconds >= floor
        if long_enough.sum() >= 4 * k:
            chosen = long_enough
            break

    best = None
    for seed in range(tries or 10 * k):
        centers, score = _spherical_kmeans(x[chosen], seconds[chosen], k, seed)
        if best is None or score > best[1]:
            best = (centers, score)
    return np.argmax(x @ best[0].T, axis=1)


def _frames_to_segments(labels, pairs, speakers, seg, n_samples, padded):
    """창 안의 화자에 붙인 화자 번호를 프레임별로 모아 [(start, end, speaker)] 로 만듭니다."""
    chunks, frames, _ = labels.shape
    total = seg.total_frames(chunks)
    num_speakers = int(max(speakers)) + 1

    # 프레임마다 동시에 말하는 사람 수(겹친 창들의 평균을 반올림).
    talking = np.zeros(total)
    covered = np.zeros(total)
    per_chunk = labels.sum(axis=-1)
    for chunk in range(chunks):
        start = seg.frame_start(chunk)
        talking[start:start + frames] += per_chunk[chunk]
        covered[start:start + frames] += 1
    talking = (talking / np.maximum(covered, 1e-12) + 0.5).astype(int)

    # 프레임마다 화자별 득표(그 프레임을 덮는 창들에서 그 화자로 잡힌 횟수).
    votes = np.zeros((total, num_speakers))
    for (chunk, local), speaker in zip(pairs, speakers):
        start = seg.frame_start(chunk)
        votes[start:start + frames, speaker] += labels[chunk, :, local]
    if padded:
        stop = int(n_samples / seg.rf_shift)
        votes, talking = votes[:stop], talking[:stop]

    # 득표가 많은 화자부터, 그 프레임에서 동시에 말하는 사람 수만큼 고른다.
    order = np.argsort(-votes, axis=1, kind="stable")
    active = np.zeros(votes.shape, dtype=bool)
    for rank in range(num_speakers):
        rows = np.flatnonzero(talking > rank)
        active[rows, order[rows, rank]] = True

    scale = seg.rf_shift / SAMPLE_RATE
    offset = seg.rf_size / SAMPLE_RATE * 0.5
    segments = []
    for speaker in range(num_speakers):
        edge = np.diff(np.concatenate(([0], active[:, speaker].astype(np.int8), [0])))
        starts = np.flatnonzero(edge == 1)
        ends = np.minimum(np.flatnonzero(edge == -1), len(active) - 1)
        merged = []
        for s, e in zip(starts * scale + offset, ends * scale + offset):
            if merged and s - merged[-1][1] <= MIN_DURATION_OFF:
                merged[-1][1] = e
            else:
                merged.append([s, e])
        segments += [(float(s), float(e), speaker) for s, e in merged if e - s >= MIN_DURATION_ON]
    segments.sort()
    return segments


def _run_pipeline(samples, cluster, progress=None):
    """세그멘테이션 → 임베딩 → cluster(임베딩, 음성 길이) → 화자 구간."""
    seg = _Segmenter()
    labels, padded = seg.local_speakers(samples)
    pairs, parts, seconds = _speech_parts(labels, seg)
    vectors = _embeddings(samples, parts, progress)
    keep = [i for i, v in enumerate(vectors) if v is not None]
    if not keep:
        return []
    speakers = cluster(np.array([vectors[i] for i in keep]), np.array([seconds[i] for i in keep]))
    segments = _frames_to_segments(labels, [pairs[i] for i in keep], speakers, seg, len(samples), padded)
    # 먼저 말을 시작한 사람이 화자 0 이 되도록 번호를 다시 매긴다.
    order = {}
    for _, _, speaker in segments:
        order.setdefault(speaker, len(order))
    return [(start, end, order[speaker]) for start, end, speaker in segments]


def diarize(audio_path, num_speakers=0, cluster_threshold=0.5, progress=None):
    """오디오의 화자 구간을 [(start, end, speaker_int), ...] 로 반환합니다.

    화자 수를 주면(num_speakers > 0) 군집을 이 파일에서 하고(cluster_known_count),
    주지 않으면 sherpa-onnx 가 임계값(cluster_threshold)으로 화자 수를 정합니다.
    화자 수를 주면 임계값은 쓰이지 않습니다(sherpa-onnx 군집도 그렇습니다).
    """
    if num_speakers and num_speakers > 0:
        _import_sherpa()
        _ensure_models()
    samples = load_samples_16k(audio_path)

    if num_speakers and num_speakers > 0:
        try:
            return _run_pipeline(
                samples, lambda vectors, seconds: cluster_known_count(vectors, seconds, num_speakers),
                progress)
        except DiarizationUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — 안 되면 예전 방식으로라도 나눈다
            print(f"[화자분리] 화자 수 지정 군집을 하지 못했습니다({type(exc).__name__}: {exc}). "
                  "sherpa-onnx 군집으로 나눕니다. 한 화자에 몰릴 수 있으니 결과를 확인하세요.",
                  flush=True)

    sd = _build_diarizer(num_speakers, cluster_threshold)

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


def _bare(text):
    """문장부호와 공백을 뺀 글자만."""
    return "".join(ch for ch in text if ch.isalnum())


def _overlap_with(diar_segments, w_start, w_end, speaker):
    """단어 구간이 그 화자의 구간과 겹친 시간. 길이 0 인 단어는 구간 안에 있으면 겹친 것으로 본다."""
    total = 0.0
    for start, end, spk in diar_segments:
        if spk != speaker:
            continue
        if w_end > w_start:
            total += max(0.0, min(w_end, end) - max(w_start, start))
        elif start <= w_start <= end:
            total += 1e-6
    return total


def settle_phrases(words, labels, diar_segments, segment_ids):
    """한 구(句) 안에서 짧게 튄 조각을 그 구의 주된 화자에게 돌립니다.

    segment_ids: 단어마다 그 단어가 나온 전사 구간(세그먼트)의 번호

    화자 구간은 서로 겹친다. 한 사람이 말하는 사이에 상대가 "네" 하고 받으면 그 자리에서
    두 구간이 겹치는데, 전사기는 대개 그 "네"를 적지 않고 말하던 사람의 단어를 그 자리에
    걸쳐 놓는다(쉼 뒤 첫 단어가 앞의 쉼까지 끌어안아 길어진다). 그러면 그 단어가 상대
    화자에게 넘어가 "사무실에 / 그냥 계속 있었지…"처럼 문장 첫 단어만 떨어져 나간다.
    두 사람이 실제로 겹쳐 말한 자리에서도 문장 끝 한두 단어가 상대에게 넘어간다.

    전사기가 한 구간으로 묶은 말, 문장부호로 끊은 한 문장은 대개 한 사람의 말이다.
    그래서 구 안에서 단어가 가장 많은 화자를 주된 화자로 보고, 아래를 모두 채우는 조각만
    그 화자에게 돌린다.
      - MAX_STRAY_WORDS 단어 이하이다
      - 단어마다 주된 화자의 구간과도 겹쳐 있다(주된 화자가 그 시각에 말하고 있었다)
      - 받는 말(RESPONSE_WORDS)이 아니다

    7분 통화를 사람이 맥락으로 화자를 붙인 녹취서와 견주면, 화자를 아는 단어 673개 중 틀린
    것이 33개에서 10개로 줄었고 새로 틀린 것은 없었다. 47초 통화의 맞장구("예.", "네, 예.",
    "예, 예.")는 그대로 남는다.

    smooth() 와 다르다. smooth() 는 앞뒤 화자만 보고 짧은 조각을 지워서 맞장구까지 지운다.
    여기서는 상대가 말하지 않는 틈에 한 말, 받는 말, 전사기가 따로 한 구간으로 낸 말은
    건드리지 않는다. 한 구로 보기에 너무 긴 것(MAX_PHRASE_WORDS 초과)도 건드리지 않는다.
    전사기가 30초를 통째로 한 구간으로 내면 그 안에 여러 사람의 말이 들어 있다.
    """
    out = list(labels)
    count = len(words)
    first = 0
    while first < count:
        # 구의 끝: 전사 구간이 바뀌거나, 문장부호로 끝난 단어 다음.
        last = first + 1
        while (last < count and segment_ids[last] == segment_ids[last - 1]
               and words[last - 1][2].rstrip()[-1:] not in SENTENCE_END):
            last += 1
        tally = {}
        for i in range(first, last):
            tally[labels[i]] = tally.get(labels[i], 0) + 1
        ranked = sorted(tally.values(), reverse=True)
        if len(ranked) > 1 and ranked[0] > ranked[1] and last - first <= MAX_PHRASE_WORDS:
            main = max(tally, key=tally.get)
            start = first
            while start < last:
                stop = start + 1
                while stop < last and labels[stop] == labels[start]:
                    stop += 1
                if labels[start] != main and stop - start <= MAX_STRAY_WORDS and all(
                        _bare(words[i][2]) not in RESPONSE_WORDS
                        and _overlap_with(diar_segments, words[i][0], words[i][1], main) > 0
                        for i in range(start, stop)):
                    for i in range(start, stop):
                        out[i] = main
                start = stop
        first = last
    return out


def assign_words_to_speakers(words, diar_segments, min_run=1, segment_ids=None):
    """단어 리스트[(start, end, text)]를 화자별 발화 턴으로 묶습니다.

    segment_ids 는 단어마다 그 단어가 나온 전사 구간(세그먼트)의 번호입니다. 주면 구 안에서
    짧게 튄 조각을 정리하고(settle_phrases), 주지 않으면 하지 않습니다.

    반환: [(turn_start, turn_end, speaker_int, text), ...]
    """
    if not words:
        return []

    # 1) 단어마다 겹침 총량으로 화자를 정하고
    labels = [speaker_for_interval(diar_segments, s, e) for s, e, _ in words]
    # 2) 한 구 안에서 짧게 튄 조각을 그 구의 주된 화자에게 돌린 뒤
    if segment_ids is not None:
        labels = settle_phrases(words, labels, diar_segments, segment_ids)
    #    (기본값은 아무것도 하지 않음. smooth() 주석 참고)
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
