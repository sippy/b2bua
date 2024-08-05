import unittest
from sippy.B2BTransforms import getTransProc

class FakeCC():
    acctA = None
    acctO = None
class FakeRequest():
    test: unittest.TestCase
    def __init__(self, test): self.test = test
    def getHFs(self, name):
        got = name
        want = 'X-foo-hdr'
        self.test.assertEqual(want, got)
        return tuple()
class FakeEvent(): pass

class TestB2BTransforms(unittest.TestCase):

    def test_getTransProc(self):
        transformations = [
            ('HDR2Xattrs[X-foo-hdr]', (FakeCC(), FakeRequest(self))),
            ('Nop[]', (None, None)),
        ]

        for t, args in transformations:
            with self.subTest(t=t, args=args):
                p = getTransProc(t)
                self.assertIsNotNone(p, f"getTransProc({t}) returned None")
                self.assertIsNone(p(*args), f"__call__({args}) returned not None")

if __name__ == '__main__':
    unittest.main()
