"""Exercise UTF-8 fixtures under a simulated Windows GBK text-file default."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_engine(folder):
    spec = importlib.util.spec_from_file_location('encoding_test_engine', ROOT / 'demos' / folder / 'engine.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EncodingTests(unittest.TestCase):
    def test_rag_loads_chinese_corpus_with_gbk_default(self):
        original_read = Path.read_text

        def windows_read(path, encoding=None, errors=None):
            return original_read(path, encoding=encoding or 'gbk', errors=errors)

        with patch.object(Path, 'read_text', windows_read):
            rag = load_engine('02-process-rag')
        result = rag.search('铝合金薄壁精加工', '铝合金')
        self.assertFalse(result['refused'])
        self.assertEqual(result['hits'][0]['id'], 'AL-02')
        self.assertIn('铝合金', result['hits'][0]['text'])

    def test_repair_executes_unicode_fixture_with_gbk_default(self):
        repair = load_engine('01-repair-agent')
        original_write = Path.write_text

        def windows_write(path, data, encoding=None, errors=None, newline=None):
            return original_write(path, data, encoding=encoding or 'gbk', errors=errors, newline=newline)

        case = {'fn': 'greet', 'tests': [('世界', '你好，世界')], 'holdout': []}
        with patch.object(Path, 'write_text', windows_write):
            result = repair.check('def greet(value):\n    return "你好，" + value\n', case)
        self.assertTrue(result[0]['pass'])
        self.assertEqual(result[0]['actual'], '你好，世界')


if __name__ == '__main__':
    unittest.main()
