import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

SKILL = Path(__file__).parents[1] / '스킬' / 'lbox-검색' / 'SKILL.md'
HARNESS = Path(__file__).with_name('lbox_code_harness.js')


def js_blocks(text):
    return re.findall(r'```js\r?\n(.*?)```', text, re.S)


def numbers(source, name):
    body = re.search(r'const ' + name + r' = \{(.*?)\}', source).group(1)
    return {k: int(v) for k, v in re.findall(r'(\w+): (\d+)', body)}


class LboxCodeTests(unittest.TestCase):
    """lbox-검색 스킬의 브라우저 코드 블록을 SKILL.md 에서 그대로 떼어 시험한다. LBOX에는 요청하지 않는다."""

    @classmethod
    def setUpClass(cls):
        cls.blocks = js_blocks(SKILL.read_text(encoding='utf-8'))

    def block(self, marker):
        found = [b for b in self.blocks if marker in b]
        self.assertEqual(len(found), 1, marker)
        return found[0]

    def test_open_block_uses_same_limits(self):
        main = numbers(self.block('const 본문한도'), '본문한도')
        opener = numbers(self.block('await (async url =>'), '한도')
        for key in ('간격', '시간당', '하루', '경고뒤'):
            self.assertEqual(main[key], opener[key], key)

    @unittest.skipUnless(shutil.which('node'), 'node 가 없어 브라우저 코드 시험을 건너뛴다')
    def test_browser_code(self):
        payload = {
            'main': self.block('const 본문한도'),
            'harvest': self.block('async function lboxHarvest'),
            'cites': self.block('function lboxCites'),
            'opener': self.block('await (async url =>'),
        }
        run = subprocess.run(['node', str(HARNESS)], input=json.dumps(payload, ensure_ascii=False),
                             capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr)
        results = json.loads(run.stdout)
        self.assertGreaterEqual(len(results), 15)
        failed = {r['name']: r['detail'] for r in results if not r['ok']}
        self.assertEqual(failed, {})


if __name__ == '__main__':
    unittest.main()
