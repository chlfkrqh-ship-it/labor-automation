"""원격 제어 자동 복구(rc_watch)가 앱이 다시 켜졌을 때만, 한 번만, 고른 창만 깨우는지 확인한다."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / 'scripts' / 'rc_watch.py'
spec = importlib.util.spec_from_file_location('rc_watch', SCRIPT)
rw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rw)

START = '2026-10-22T21:05:08Z'
START_MS = rw.iso_ms(START)
OWN = Path('C:/x/원격복구')
H = 3600 * 1000


def sess(n, hours_ago, **kw):
    return {'sessionId': f'local_{n:08d}-0000', 'title': f'창{n}', 'lastActivityAt': START_MS - hours_ago * H, **kw}


class PickTargets(unittest.TestCase):
    def test_recent_three_newest_first(self):
        rows = [sess(1, 5), sess(2, 1), sess(3, 3), sess(4, 2), sess(5, 30)]
        got = [t['id'][6:14] for t in rw.pick_targets(rows, START_MS, OWN)]
        self.assertEqual(got, ['00000002', '00000004', '00000003'])

    def test_excludes_archived_off_and_own(self):
        rows = [sess(1, 1, isArchived=True), sess(2, 1, remoteControlUserEnabled=False),
                sess(3, 1, scheduledTaskId='rc-watch'), sess(4, 1, cwd=str(OWN)), sess(5, 2, remoteControlUserEnabled=True)]
        got = [t['id'][6:14] for t in rw.pick_targets(rows, START_MS, OWN)]
        self.assertEqual(got, ['00000005'])

    def test_skips_broken_rows(self):
        self.assertEqual(rw.pick_targets([{}, {'sessionId': 'local_x'}, sess(1, 1)], START_MS, OWN)[0]['title'], '창1')


class Decide(unittest.TestCase):
    rows = [sess(1, 1)]

    def test_same_start_does_nothing(self):
        state = {'appStart': START}
        self.assertEqual(rw.decide(state, START, self.rows, OWN), (state, None))

    def test_app_off_does_nothing(self):
        self.assertIsNone(rw.decide({'appStart': START}, None, self.rows, OWN)[1])

    def test_first_run_only_records(self):
        new, targets = rw.decide({}, START, self.rows, OWN)
        self.assertIsNone(targets)
        self.assertEqual(new['appStart'], START)

    def test_restart_wakes_once(self):
        new, targets = rw.decide({'appStart': '2026-10-21T19:54:09Z'}, START, self.rows, OWN)
        self.assertEqual(len(targets), 1)
        self.assertEqual(rw.decide(new, START, self.rows, OWN)[1], None)

    def test_armed_after_install_wakes(self):
        new, targets = rw.decide({'armed': True}, START, self.rows, OWN)
        self.assertEqual(len(targets), 1)
        self.assertNotIn('armed', new)


if __name__ == '__main__':
    unittest.main()
