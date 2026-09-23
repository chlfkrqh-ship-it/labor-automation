"""transcribe.py 의 재실행·이름 겹침·저장 위치·확인 표시 시험.

faster-whisper 와 sherpa-onnx 없이 돈다. 모델과 화자 분리는 가짜로 바꿔 끼운다.

    python -B -m pytest 5_녹취록/test_transcribe.py -q -p no:cacheprovider
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

# 스크립트 폴더. 이 파일을 공통/tests/ 로 옮겨도 그대로 돌도록 찾아 둔다.
HERE = Path(__file__).resolve().parent
if not (HERE / 'transcribe.py').is_file():
    HERE = Path(__file__).resolve().parents[2] / '5_녹취록'
sys.path.insert(0, str(HERE))                    # transcribe 가 diarize 를 이름으로 불러온다
spec = importlib.util.spec_from_file_location('transcribe', HERE / 'transcribe.py')
transcribe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transcribe)
import diarize  # noqa: E402


def word(start, end, text):
    return types.SimpleNamespace(start=start, end=end, word=text)


def segment(start, end, text, avg_logprob=-0.2, words=()):
    return types.SimpleNamespace(start=start, end=end, text=text, avg_logprob=avg_logprob,
                                 no_speech_prob=0.01, words=list(words))


class FakeModel:
    def __init__(self, segments=None):
        self.calls = []
        self.segments = segments or [segment(0.0, 2.0, '안녕하세요')]

    def transcribe(self, audio_path, **kwargs):
        self.calls.append(os.path.basename(audio_path))
        return iter(self.segments), types.SimpleNamespace(language='ko', duration=2.0)


class TranscribeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.src = self.dir / '원본'
        self.out = self.dir / '전사'
        self.src.mkdir()
        self.log = []

    def tearDown(self):
        self.tmp.cleanup()

    def audio(self, name, data=b'audio'):
        path = self.src / name
        path.write_bytes(data)
        return path

    def run_main(self, *args, model=None):
        model = model or FakeModel()
        with mock.patch.object(transcribe, '_load_model', lambda *a, **k: model), \
             mock.patch.object(transcribe, '_log', self.log.append), \
             mock.patch.object(sys, 'argv', ['transcribe.py', *map(str, args)]):
            try:
                transcribe.main()
                code = 0
            except SystemExit as exc:
                code = exc.code
        return model.calls, code

    def test_rerun_skips_files_already_transcribed(self):
        self.audio('1차면담.m4a')
        self.audio('2차면담.m4a')
        calls, _ = self.run_main(self.src, '--output-dir', self.out)
        self.assertEqual(calls, ['1차면담.m4a', '2차면담.m4a'])
        calls, code = self.run_main(self.src, '--output-dir', self.out)
        self.assertEqual((calls, code), ([], 0))
        self.assertTrue(any('건너뜀 2개' in line for line in self.log))

    def test_force_changed_options_and_changed_audio_transcribe_again(self):
        self.audio('1차면담.m4a')
        self.audio('2차면담.m4a')
        self.run_main(self.src, '--output-dir', self.out)
        calls, _ = self.run_main(self.src, '--output-dir', self.out, '--force')
        self.assertEqual(calls, ['1차면담.m4a', '2차면담.m4a'])
        calls, _ = self.run_main(self.src, '--output-dir', self.out, '--num-speakers', '2')
        self.assertEqual(calls, ['1차면담.m4a', '2차면담.m4a'])  # 화자 수를 바꿔 다시 돌린다
        self.audio('2차면담.m4a', b'audio, re-recorded')
        calls, _ = self.run_main(self.src, '--output-dir', self.out, '--num-speakers', '2')
        self.assertEqual(calls, ['2차면담.m4a'])

    def test_interrupted_result_is_not_skipped(self):
        self.audio('1차면담.m4a')
        self.run_main(self.src, '--output-dir', self.out)
        (self.out / '1차면담.부분.jsonl').write_text('{}\n', encoding='utf-8')
        calls, _ = self.run_main(self.src, '--output-dir', self.out)
        self.assertEqual(calls, ['1차면담.m4a'])
        self.assertFalse((self.out / '1차면담.부분.jsonl').exists())

    def test_same_stem_different_extension_do_not_overwrite_each_other(self):
        self.audio('통화.m4a')
        self.audio('통화.mp4')
        self.run_main(self.src, '--output-dir', self.out)
        self.assertFalse((self.out / '통화.녹취.txt').exists())
        for name in ('통화.m4a', '통화.mp4'):
            meta = json.loads((self.out / (name + '.녹취.json')).read_text(encoding='utf-8'))
            self.assertEqual(meta['source_file'], name)
        calls, _ = self.run_main(self.src, '--output-dir', self.out)
        self.assertEqual(calls, [])

    def test_added_sibling_does_not_take_over_existing_result(self):
        self.audio('통화.m4a')
        self.run_main(self.src, '--output-dir', self.out)
        self.audio('통화.mp4')
        calls, _ = self.run_main(self.src, '--output-dir', self.out)
        self.assertEqual(calls, ['통화.mp4'])
        old = json.loads((self.out / '통화.녹취.json').read_text(encoding='utf-8'))
        self.assertEqual(old['source_file'], '통화.m4a')
        self.assertTrue((self.out / '통화.mp4.녹취.txt').exists())

    def test_simple_mode_does_not_write_inside_repo_outside_case_folder(self):
        repo = self.dir / 'repo'
        (repo / '5_녹취록' / '사건' / '김OO' / '원본').mkdir(parents=True)
        (repo / '.gitignore').write_text('**/사건/\n', encoding='utf-8')
        loose = repo / '5_녹취록' / '통화.m4a'
        loose.write_bytes(b'audio')
        with mock.patch.object(transcribe, 'REPO_ROOT', str(repo)):
            calls, code = self.run_main(loose)
            self.assertEqual((calls, code), ([], 2))
            self.assertEqual(sorted(p.name for p in loose.parent.iterdir()), ['사건', '통화.m4a'])
            filed = repo / '5_녹취록' / '사건' / '김OO' / '원본' / '통화.m4a'
            filed.write_bytes(b'audio')
            calls, code = self.run_main(filed)
            self.assertEqual((calls, code), (['통화.m4a'], 0))
            outside = self.audio('다운로드.m4a')              # 저장소 밖은 간이 모드 그대로
            calls, code = self.run_main(outside)
            self.assertEqual((calls, code), (['다운로드.m4a'], 0))

    def test_diarized_transcript_keeps_review_mark_on_turn(self):
        self.audio('면담.m4a')
        model = FakeModel([
            segment(0.0, 2.0, '안녕하세요 반갑습니다', avg_logprob=-1.5,
                    words=[word(0.0, 1.0, '안녕하세요'), word(1.0, 2.0, '반갑습니다')]),
            segment(2.0, 4.0, '네', words=[word(2.0, 4.0, '네')]),
        ])
        speakers = [(0.0, 2.0, 0), (2.0, 4.0, 1)]
        with mock.patch.object(diarize, 'diarize', lambda *a, **k: speakers):
            self.run_main(self.src, '--output-dir', self.out, '--diarize', model=model)
        lines = (self.out / '면담.녹취.txt').read_text(encoding='utf-8').splitlines()
        self.assertIn('[00:00:00] 화자1: 안녕하세요 반갑습니다 ※확인', lines)
        self.assertIn('[00:00:02] 화자2: 네', lines)
        meta = json.loads((self.out / '면담.녹취.json').read_text(encoding='utf-8'))
        self.assertEqual([t.get('review', False) for t in meta['turns']], [True, False])


class RecoveryHintTests(unittest.TestCase):
    """화자 분리를 못 할 때 안내하는 복구 명령이 실제로 도는 명령인지 본다."""

    def test_missing_sherpa_points_to_this_python(self):
        with mock.patch.dict(sys.modules, {'sherpa_onnx': None}):
            with self.assertRaises(diarize.DiarizationUnavailable) as caught:
                diarize._build_diarizer(0, 0.8)
        self.assertIn(f'"{sys.executable}" -m pip install sherpa-onnx', str(caught.exception))
        self.assertIn('녹취록 환경설치.bat', str(caught.exception))

    def test_failed_model_download_names_existing_script(self):
        def fail():
            raise OSError('network down')
        fake_dl = types.SimpleNamespace(ensure_models=fail)
        with mock.patch.dict(sys.modules, {'sherpa_onnx': types.ModuleType('sherpa_onnx'),
                                           'download_diarization_models': fake_dl}), \
             mock.patch.object(diarize, 'SEG_MODEL', str(HERE / '없는_모델.onnx')):
            with self.assertRaises(diarize.DiarizationUnavailable) as caught:
                diarize._build_diarizer(0, 0.8)
        quoted = re.findall(r'"([^"]+)"', str(caught.exception))
        self.assertEqual(quoted[0], sys.executable)
        self.assertTrue(Path(quoted[1]).is_file())
        self.assertEqual(Path(quoted[1]).name, 'download_diarization_models.py')


if __name__ == '__main__':
    unittest.main()
