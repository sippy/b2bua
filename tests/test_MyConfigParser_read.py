#
# Regression tests for MyConfigParser.read() on Python 3.12 and later.
#
# RawConfigParser.readfp() was removed in Python 3.12; read() uses the
# file-based RawConfigParser.read() API, which preserves the historical
# contract this module must keep:
#   - a single path (str) is accepted,
#   - a LIST of paths is accepted (files merged, in order),
#   - a missing path in the list is skipped without raising.
#
# Base-only: stdlib + sippy.MyConfigParser, no sip25519 options.
#
import os
import shutil
import tempfile
import unittest

from sippy.MyConfigParser import MyConfigParser


class TestMyConfigParserRead(unittest.TestCase):

    def _ini(self, tmp, name, lines):
        p = os.path.join(tmp, name)
        with open(p, 'w') as f:
            f.write('[general]\n' + '\n'.join(lines) + '\n')
        return p

    def test_single_path(self):
        # A single path (str) loads and validates the default section.
        tmp = tempfile.mkdtemp(prefix='mcpread-single-')
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        p = self._ini(tmp, 'a.ini', ['b2bua_socket = udp:127.0.0.1:7060'])
        cfg = MyConfigParser()
        cfg.read(p)
        self.assertEqual(cfg['b2bua_socket'], 'udp:127.0.0.1:7060')

    def test_multiple_paths(self):
        # A list of paths: every file is read and merged, in order.
        tmp = tempfile.mkdtemp(prefix='mcpread-multi-')
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        p1 = self._ini(tmp, 'a.ini', ['b2bua_socket = udp:127.0.0.1:7060'])
        p2 = self._ini(tmp, 'b.ini', ['logfile = /tmp/b2bua-test.log'])
        cfg = MyConfigParser()
        cfg.read([p1, p2])
        self.assertEqual(cfg['b2bua_socket'], 'udp:127.0.0.1:7060')
        self.assertEqual(cfg['logfile'], '/tmp/b2bua-test.log')

    def test_missing_file_skipped(self):
        # A missing path in the list is silently skipped (historical
        # RawConfigParser.read contract): no exception; present files
        # still load. A list of ONLY missing files must not raise
        # either, and leaves the parser empty.
        tmp = tempfile.mkdtemp(prefix='mcpread-missing-')
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        p = self._ini(tmp, 'a.ini', ['b2bua_socket = udp:127.0.0.1:7060'])
        missing = os.path.join(tmp, 'absent.ini')
        cfg = MyConfigParser()
        cfg.read([missing, p])
        self.assertEqual(cfg['b2bua_socket'], 'udp:127.0.0.1:7060')
        cfg2 = MyConfigParser()
        cfg2.read([missing])
        self.assertEqual(cfg2.getdefault('b2bua_socket', ''), '')


if __name__ == '__main__':
    unittest.main()
