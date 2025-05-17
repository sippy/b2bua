import unittest
from sippy.B2B.Transforms import getTransProc

class FakeRequest():
    test: unittest.TestCase
    def __init__(self, test): self.test = test
    def getHFs(self, name):
        got = name
        want = 'X-foo-hdr'
        self.test.assertEqual(want, got)
        return tuple()
class FakeEvent(): pass
class FakeAccounting():
    test: unittest.TestCase
    def __init__(self, test): self.test = test
    def addAttributes(self, attrs):
        got = len(attrs)
        want = 2
        self.test.assertEqual(want, got)
        for a in ('foo', 'bar'), ('baz', 'xxx'):
            with self.test.subTest(a=a):
                got = a in attrs
                want = True
                self.test.assertEqual(want, got)

class FakeCC():
    def __init__(self, acctA = None, acctO = None): self.acctA, self.acctO = acctA, acctO

class TestB2BTransforms(unittest.TestCase):

    def test_getTransProc(self):
        transformations = [
            ('HDR2Xattrs[X-foo-hdr]', (FakeCC(), FakeRequest(self))),
            ('VAL2Xattrs[foo=bar,baz=xxx]', (FakeCC(acctA = FakeAccounting(self),
                                                    acctO = FakeAccounting(self)), FakeEvent())),
            ('VAL2XattrsA[foo=bar,baz=xxx]', (FakeCC(acctA = FakeAccounting(self)), FakeEvent())),
            ('VAL2XattrsO[foo=bar,baz=xxx]', (FakeCC(acctO = FakeAccounting(self)), FakeEvent())),
            ('Nop[]', (None, None)),
        ]

        for t, args in transformations:
            with self.subTest(t=t, args=args):
                p = getTransProc(t)
                self.assertIsNotNone(p, f"getTransProc({t}) returned None")
                self.assertIsNone(p(*args), f"__call__({args}) returned not None")

if __name__ == '__main__':
    unittest.main()
