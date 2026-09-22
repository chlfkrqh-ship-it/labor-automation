# -*- coding: utf-8 -*-
"""화자 분리(diarization)에 쓰는 ONNX 모델을 GitHub 릴리스에서 내려받습니다.
HuggingFace 토큰이 필요 없습니다. 최초 1회만 실행하면 됩니다.
"""
import os
import ssl
import sys
import tarfile
import urllib.request

# Windows Store Python 의 urllib 은 시스템 CA 를 못 찾는 경우가 있어 certifi 번들을 씁니다.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")

SEG_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
           "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2")
EMB_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
           "speaker-recongition-models/3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx")

SEG_MODEL = os.path.join(MODELS_DIR, "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")
EMB_MODEL = os.path.join(MODELS_DIR, "3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx")


def _download(url, dst):
    print(f"[다운로드] {os.path.basename(dst)}")
    tmp = dst + ".part"
    with urllib.request.urlopen(url, context=_SSL_CTX) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                print(f"\r  {done//1024} / {total//1024} KB ({pct}%)", end="", flush=True)
    print()
    os.replace(tmp, dst)


def ensure_models():
    os.makedirs(MODELS_DIR, exist_ok=True)

    if not os.path.exists(SEG_MODEL):
        tar_path = os.path.join(MODELS_DIR, "seg.tar.bz2")
        _download(SEG_URL, tar_path)
        print("[압축 해제] 세그멘테이션 모델")
        with tarfile.open(tar_path, "r:bz2") as tar:
            tar.extractall(MODELS_DIR)
        os.remove(tar_path)
    else:
        print("[확인] 세그멘테이션 모델 이미 있음")

    if not os.path.exists(EMB_MODEL):
        _download(EMB_URL, EMB_MODEL)
    else:
        print("[확인] 임베딩 모델 이미 있음")

    print("\n세그멘테이션 :", SEG_MODEL)
    print("임베딩       :", EMB_MODEL)
    return SEG_MODEL, EMB_MODEL


if __name__ == "__main__":
    try:
        ensure_models()
        print("\n[완료] 화자 분리 모델 준비됨")
    except Exception as exc:
        print(f"[오류] 모델 다운로드 실패: {exc}")
        sys.exit(1)
