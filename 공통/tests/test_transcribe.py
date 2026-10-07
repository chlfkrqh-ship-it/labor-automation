"""transcribe.py 의 재실행·이름 겹침·저장 위치·확인 표시 시험과, diarize.py 의 화자 군집·단어 배정 시험.

faster-whisper 와 sherpa-onnx 없이 돈다. 모델과 화자 분리는 가짜로 바꿔 끼운다.

    python -B -m pytest 5_녹취록/test_transcribe.py -q -p no:cacheprovider
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

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

    def test_word_dragged_into_listener_overlap_stays_with_its_sentence(self):
        # 상대가 "네" 하고 받은 자리(2.2~2.8초)를 전사기는 적지 않고, 쉼 뒤 첫 단어 '사무실에'가
        # 그 자리까지 끌어안았다. 세그먼트 번호를 넘겨받아 문장째로 화자1 에 둔다.
        self.audio('통화.m4a')
        model = FakeModel([
            segment(0.0, 2.0, '어 사무실에 있어', words=[word(0.0, 0.6, '어'), word(0.6, 1.3, '사무실에'),
                                                  word(1.3, 2.0, '있어')]),
            segment(2.0, 4.6, '사무실에 그냥 있지', words=[word(2.0, 3.4, '사무실에'), word(3.4, 4.0, '그냥'),
                                                   word(4.0, 4.6, '있지')]),
            segment(5.0, 5.4, '네', words=[word(5.0, 5.4, '네')]),
        ])
        speakers = [(0.0, 2.0, 0), (2.2, 2.8, 1), (3.0, 4.6, 0), (5.0, 5.4, 1)]
        with mock.patch.object(diarize, 'diarize', lambda *a, **k: speakers):
            self.run_main(self.src, '--output-dir', self.out, '--diarize', '--num-speakers', '2', model=model)
        meta = json.loads((self.out / '통화.녹취.json').read_text(encoding='utf-8'))
        self.assertEqual([(t['label'], t['text']) for t in meta['turns']],
                         [('화자1', '어 사무실에 있어 사무실에 그냥 있지'), ('화자2', '네')])

    def test_segment_that_repeats_the_hint_sentence_is_flagged(self):
        self.audio('통화.m4a')
        hint = '김철수 과장과 이영희 대리의 통화입니다. 김철수, 영희 씨, 송년회, 물류센터, 인사팀 같은 말이 나옵니다.'
        model = FakeModel([
            segment(0.0, 30.0, '김철수, 영희 씨, 송년회, 물류센터, 인사팀 같은 말이 나옵니다.', avg_logprob=-0.14),
            segment(30.0, 33.0, '송년회 때 물류센터에서 봤잖아'),    # 힌트의 낱말이 실제 대화에 나온 것은 정상
        ])
        self.run_main(self.src, '--output-dir', self.out, '--initial-prompt', hint, model=model)
        meta = json.loads((self.out / '통화.녹취.json').read_text(encoding='utf-8'))
        self.assertEqual([s['start'] for s in meta['review_needed']], [0.0])
        self.assertIn('인식 힌트 문장이 그대로 나옴', meta['review_needed'][0]['review'][0])
        self.assertTrue(any('--no-initial-prompt' in line for line in self.log))
        text = (self.out / '통화.녹취.txt').read_text(encoding='utf-8')
        self.assertIn('같은 말이 나옵니다. ※확인', text)

    def test_log_tells_when_one_speaker_takes_nearly_everything(self):
        self.audio('통화.m4a')
        model = FakeModel([segment(0.0, 2.0, '안녕하세요', words=[word(0.0, 2.0, '안녕하세요')])])
        lopsided = [(0.0, 362.0, 0), (5.0, 6.0, 1), (10.0, 11.0, 1)]
        with mock.patch.object(diarize, 'diarize', lambda *a, **k: lopsided):
            self.run_main(self.src, '--output-dir', self.out, '--diarize', '--num-speakers', '2', model=model)
        self.assertTrue(any('화자1 362초, 화자2 2초' in line for line in self.log))
        self.assertTrue(any('[주의] 화자2 의 구간이 전체의 1%뿐' in line for line in self.log))
        self.log.clear()
        even = [(0.0, 290.0, 0), (290.0, 370.0, 1)]
        with mock.patch.object(diarize, 'diarize', lambda *a, **k: even):
            self.run_main(self.src, '--output-dir', self.out, '--diarize', '--num-speakers', '2', '--force',
                          model=model)
        self.assertFalse(any('[주의]' in line for line in self.log))


def fake_segmenter(frames=20, hop=10, frame_samples=1600):
    """모델을 열지 않은 세그멘테이션기. 창 하나가 frames 프레임, 프레임 하나가 0.1초."""
    seg = diarize._Segmenter.__new__(diarize._Segmenter)
    seg.window, seg.shift = frames * frame_samples, hop * frame_samples
    seg.rf_size, seg.rf_shift = frame_samples, frame_samples
    return seg


class SpeakerClusterTests(unittest.TestCase):
    """화자 수를 아는 경우의 군집과, 창 안의 화자를 화자 구간으로 모으는 일."""

    def test_stray_short_embeddings_do_not_take_a_speaker(self):
        # 한쪽이 한두 마디로만 받는 통화. 맞장구에서 나온 흐린 임베딩과 누구와도 닮지 않은
        # 임베딩이 섞여 있어도, 길게 말한 두 사람이 서로 다른 화자로 갈려야 한다.
        rng = np.random.default_rng(7)
        a, b = np.zeros(32), np.zeros(32)
        a[0], b[1] = 1.0, 1.0
        vectors, seconds, who = [], [], []
        for _ in range(40):
            vectors.append(a + rng.normal(0, 0.08, 32)); seconds.append(5.0); who.append('A')
        for _ in range(12):
            vectors.append(b + rng.normal(0, 0.08, 32)); seconds.append(3.0); who.append('B')
        for _ in range(10):
            vectors.append(b + rng.normal(0, 0.25, 32)); seconds.append(0.3); who.append('b')
        for _ in range(5):
            stray = rng.normal(0, 1.0, 32)
            stray[:2] = 0.0
            vectors.append(stray); seconds.append(0.2); who.append('x')
        labels = diarize.cluster_known_count(np.array(vectors), np.array(seconds), 2)
        of_a = {int(l) for l, w in zip(labels, who) if w == 'A'}
        of_b = {int(l) for l, w in zip(labels, who) if w == 'B'}
        self.assertEqual((len(of_a), len(of_b)), (1, 1))
        self.assertNotEqual(of_a, of_b)
        short_b = [int(l) for l, w in zip(labels, who) if w == 'b']
        self.assertGreaterEqual(short_b.count(of_b.pop()), 9)       # 짧은 말은 가까운 화자에게 붙는다

    def test_cluster_handles_fewer_embeddings_than_speakers(self):
        self.assertEqual(list(diarize.cluster_known_count(np.array([[1.0, 0.0]]), [1.0], 2)), [0])
        two = diarize.cluster_known_count(np.array([[1.0, 0.0], [0.0, 1.0]]), [0.2, 0.2], 3)
        self.assertEqual(sorted(int(l) for l in two), [0, 1])
        self.assertEqual(list(diarize.cluster_known_count(np.array([[1.0, 0.0], [0.0, 1.0]]), [1.0, 1.0], 1)),
                         [0, 0])

    def test_speech_parts_skip_overlap_and_too_short_speech(self):
        seg = fake_segmenter(frames=40)
        labels = np.zeros((1, 40, 3), dtype=np.int8)
        labels[0, 0:25, 0] = 1          # 0~24 프레임
        labels[0, 20:40, 1] = 1         # 20~39 프레임 — 20~24 는 둘이 겹친다
        labels[0, 30:33, 2] = 1         # 겹침을 빼면 남는 것이 없다
        pairs, parts, seconds = diarize._speech_parts(labels, seg)
        self.assertEqual(pairs, [(0, 0), (0, 1)])
        self.assertEqual(parts, [[(0, 32000)], [(40000, 48000), (52800, 62400)]])
        self.assertEqual([round(s, 1) for s in seconds], [2.0, 1.2])

    def test_local_speakers_are_joined_across_windows(self):
        # A 0~1.5초, B 1.5~2.5초, A 2.5~4초. 창마다 '창 안의 화자' 번호가 다르게 붙어 있어도
        # 군집이 붙인 화자 번호로 이어져야 한다.
        seg = fake_segmenter()
        labels = np.zeros((3, 20, 3), dtype=np.int8)
        labels[0, 0:15, 0] = 1          # 창0(0~2초): A
        labels[0, 15:20, 1] = 1         #            B
        labels[1, 5:15, 0] = 1          # 창1(1~3초): B
        labels[1, 0:5, 1] = 1           #            A
        labels[1, 15:20, 1] = 1
        labels[2, 0:5, 0] = 1           # 창2(2~4초): B
        labels[2, 5:20, 2] = 1          #            A
        pairs = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 2)]
        segments = diarize._frames_to_segments(labels, pairs, [0, 1, 1, 0, 1, 0], seg, 64000, False)
        self.assertEqual([(round(s, 2), round(e, 2), k) for s, e, k in segments],
                         [(0.05, 1.55, 0), (1.55, 2.55, 1), (2.55, 4.05, 0)])

    def test_known_speaker_count_uses_own_clustering_and_falls_back_to_sherpa(self):
        calls = []
        one = types.SimpleNamespace(start=0.0, end=1.0, speaker=0)
        sherpa = types.SimpleNamespace(
            process=lambda samples: types.SimpleNamespace(sort_by_start_time=lambda: [one]))

        def build(num_speakers, threshold):
            calls.append(('sherpa', num_speakers))
            return sherpa

        def own(samples, cluster, progress=None):
            calls.append('own')
            return [(0.0, 2.0, 0)]

        def broken(samples, cluster, progress=None):
            raise RuntimeError('세그멘테이션 실패')

        with mock.patch.object(diarize, '_import_sherpa'), mock.patch.object(diarize, '_ensure_models'), \
             mock.patch.object(diarize, 'load_samples_16k', lambda path: np.zeros(16000, dtype=np.float32)), \
             mock.patch.object(diarize, '_build_diarizer', build):
            with mock.patch.object(diarize, '_run_pipeline', own):
                self.assertEqual(diarize.diarize('통화.m4a', num_speakers=2), [(0.0, 2.0, 0)])
                self.assertEqual(calls, ['own'])
                self.assertEqual(diarize.diarize('통화.m4a'), [(0.0, 1.0, 0)])     # 화자 수를 모르면 sherpa-onnx
                self.assertEqual(calls, ['own', ('sherpa', 0)])
            said = io.StringIO()
            with mock.patch.object(diarize, '_run_pipeline', broken), contextlib.redirect_stdout(said):
                self.assertEqual(diarize.diarize('통화.m4a', num_speakers=2), [(0.0, 1.0, 0)])
            self.assertEqual(calls[-1], ('sherpa', 2))
            self.assertIn('한 화자에 몰릴 수 있으니', said.getvalue())


class WordAssignmentTests(unittest.TestCase):
    """단어를 화자에 붙인 뒤, 한 구 안에서 짧게 튄 조각을 정리하는 일."""

    def turns(self, words, speakers, segment_ids):
        return [(spk, text) for _, _, spk, text in
                diarize.assign_words_to_speakers(words, speakers, segment_ids=segment_ids)]

    def test_response_word_inside_the_other_speakers_sentence_is_kept(self):
        words = [(0.0, 1.0, '그래서'), (1.0, 1.4, '네'), (1.4, 2.4, '갔어요')]
        speakers = [(0.0, 2.4, 0), (1.0, 1.4, 1)]
        self.assertEqual(self.turns(words, speakers, [0, 0, 0]), [(0, '그래서'), (1, '네'), (0, '갔어요')])

    def test_words_said_while_the_other_speaker_is_silent_are_kept(self):
        words = [(0.0, 1.0, '좋습니다'), (1.2, 1.8, '언제요'), (2.0, 2.6, '내일'), (2.6, 3.2, '오전에'),
                 (3.2, 4.0, '갑니다')]
        speakers = [(0.0, 1.0, 0), (1.2, 1.8, 1), (2.0, 4.0, 0)]
        self.assertEqual(self.turns(words, speakers, [0] * 5),
                         [(0, '좋습니다'), (1, '언제요'), (0, '내일 오전에 갑니다')])

    def test_sentence_end_and_segment_boundary_start_a_new_phrase(self):
        # '네.' 는 마침표로 끊긴 구라서 그대로이고, 다음 문장 첫 단어 '저'만 문장의 화자에게 돌아간다.
        words = [(0.0, 0.4, '네.'), (0.4, 0.9, '저'), (0.9, 1.6, '갔는데'), (1.6, 2.4, '없었어요.')]
        speakers = [(0.0, 0.9, 1), (0.5, 2.4, 0)]
        self.assertEqual(self.turns(words, speakers, [0, 0, 0, 0]), [(1, '네.'), (0, '저 갔는데 없었어요.')])
        # 같은 단어들이 세그먼트 둘로 나뉘어 있고 문장부호가 없어도 같다.
        bare = [(s, e, t.rstrip('.')) for s, e, t in words]
        self.assertEqual(self.turns(bare, speakers, [0, 1, 1, 1]), [(1, '네'), (0, '저 갔는데 없었어요')])

    def test_overlapped_sentence_tail_goes_back_but_longer_pieces_do_not(self):
        # 3초부터 상대가 겹쳐 말했다. 겹친 자리의 문장 끝 세 단어는 문장의 화자에게 돌아간다.
        head = [(0.0, 0.6, '제가'), (0.6, 1.2, '그'), (1.2, 1.8, '서류는'), (1.8, 2.4, '오늘'), (2.4, 3.0, '챙겨서')]
        tail = [(3.0, 3.6, '내일'), (3.6, 4.2, '오전까지'), (4.2, 5.0, '보내드릴게요')]
        self.assertEqual(self.turns(head + tail, [(0.0, 6.0, 1), (3.0, 5.0, 0)], [0] * 8),
                         [(1, '제가 그 서류는 오늘 챙겨서 내일 오전까지 보내드릴게요')])
        # 네 단어가 넘어갔으면 실제로 말이 넘어간 것일 수 있으므로 그대로 둔다.
        four = self.turns(head + tail + [(5.0, 5.5, '꼭이요')], [(0.0, 6.0, 1), (3.0, 5.5, 0)], [0] * 9)
        self.assertEqual(four, [(1, '제가 그 서류는 오늘 챙겨서'), (0, '내일 오전까지 보내드릴게요 꼭이요')])

    def test_long_segment_and_missing_segment_ids_are_left_alone(self):
        speakers = [(0.0, 30.0, 0), (10.0, 10.5, 1)]
        words = [(float(i), float(i) + 0.5, f'말{i}') for i in range(21)]
        split = [(0, ' '.join(f'말{i}' for i in range(10))), (1, '말10'),
                 (0, ' '.join(f'말{i}' for i in range(11, 21)))]
        self.assertEqual(self.turns(words, speakers, [0] * 21), split)                 # 21단어짜리 구
        self.assertEqual(self.turns(words[:20], speakers, [0] * 20), [(0, ' '.join(f'말{i}' for i in range(20)))])
        legacy = [(spk, text) for _, _, spk, text in diarize.assign_words_to_speakers(words[:20], speakers)]
        self.assertEqual(legacy, [(0, ' '.join(f'말{i}' for i in range(10))), (1, '말10'),
                                  (0, ' '.join(f'말{i}' for i in range(11, 20)))])


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
