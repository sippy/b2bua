import unittest
from sippy.B2B.Route import B2BRoute

class TestB2BRoute(unittest.TestCase):
    test_route = '200110508667@b2bua.org;cli=16046288900;rid=-1;expires=30;np_expires=5;ash=Name%3AValue'
    test_po = f'{test_route};po_proc=VAL2Xattrs[x-attr=val1,y-attr=val2]'

    def test_B2BRoute_basic(self):
        route = B2BRoute(self.test_route)
        self.assertIsInstance(route, B2BRoute)

    def test_B2BRoute_with_po_proc(self):
        route = B2BRoute(self.test_po)
        self.assertIsInstance(route, B2BRoute)

    def test_B2BRoute_parameters(self):
        route = B2BRoute(self.test_po)
        self.assertEqual(route.params['po_proc'].radius_parameters, [('x-attr', 'val1'), ('y-attr', 'val2')])
        self.assertEqual(route.cli, '16046288900')
        self.assertEqual(route.cld, '200110508667')
        self.assertEqual(route.params['rid'], '-1')
        self.assertEqual(route.expires, 30)
        self.assertEqual(route.no_progress_expires, 5)
        self.assertEqual(str(route.extra_headers[0]), 'Name: Value')

if __name__ == '__main__':
    unittest.main()
