import unittest
from sippy.MyConfigParser import MyConfigParser


class TestMyConfigParser(unittest.TestCase):
    def TestParamHandling(self):
        m = MyConfigParser()
        m['_foo'] = 'bar'
        m['b2bua_socket'] = 'bar1'
        m['acct_enable'] = True
        m['auth_enable'] = 'False'

        self.assertTrue(m.has_key('_foo'))
        self.assertEqual(m['_foo'], 'bar')
        self.assertEqual(m['b2bua_socket'], 'bar1')
        self.assertEqual(m.get('_foo'), 'bar')
        self.assertEqual(m.get('b2bua_socket'), 'bar1')
        self.assertEqual(m.get('general', 'b2bua_socket'), 'bar1')
        self.assertTrue(m.get('acct_enable'))
        self.assertFalse(m.get('auth_enable'))

        m.check_and_set('keepalive_ans', '15')
        self.assertEqual(m['keepalive_ans'], 15)
        self.assertIsInstance(m.get('keepalive_ans'), int)

        m.check_and_set('pass_header', 'a')
        m.check_and_set('pass_header', 'b')

        self.assertEqual(m['pass_headers'], 'a,b')
        self.assertEqual(m['_pass_headers'][0], 'a')
        self.assertEqual(m['_pass_headers'][1], 'b')

        m.check_and_set('accept_ips', '1.2.3.4, 5.6.7.8')
        self.assertEqual(m['_accept_ips'][0], '1.2.3.4')
        self.assertEqual(m['_accept_ips'][1], '5.6.7.8')

        self.assertEqual(m.check_and_set('hrtb_ival', "1"), None)
        self.assertEqual(m['hrtb_ival'], 1)
        self.assertEqual(m.get('hrtb_ival'), 1)
        # Test that get method returns correct type
        self.assertIsInstance(m.get('hrtb_ival'), float)
        # Test that access by index returns correct type
        self.assertIsInstance(m['hrtb_ival'], float)

        with self.assertRaises(KeyError):
            m.check_and_set('non_existant_key', "1")

    def TestSipPortValidation(self):
        m = MyConfigParser()
        with self.assertRaises(ValueError):
            m.check_and_set('sip_port', "-1")
        with self.assertRaises(ValueError):
            m.check_and_set('sip_port', "0")
        with self.assertRaises(ValueError):
            m.check_and_set('sip_port', "65536")
        self.assertEquals(m.check_and_set('sip_port', "1"), None)
        self.assertEquals(m.check_and_set('sip_port', "65535"), None)

    def TestMaxCreditTime(self):
        m = MyConfigParser()
        with self.assertRaises(ValueError):
            m.check_and_set('max_credit_time', "-1")

    def TestMaxKeepAlive(self):
        m = MyConfigParser()
        with self.assertRaises(ValueError):
            m.check_and_set('keepalive_ans', "-1")
