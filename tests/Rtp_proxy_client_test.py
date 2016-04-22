import unittest
from sippy.Rtp_proxy_client import Rtp_proxy_client

class Test_Rtp_proxy_client(unittest.TestCase):
    """ This test requires that a rtpproxy.sock socket is available
    at /var/run/rtpproxy.sock"""

    def test_hrtb_config_defaults(self):
        global_config = {}
        global_config['_sip_address'] = '127.0.0.1'
        c = Rtp_proxy_client(global_config)
        self.assertEquals(c.hrtb_ival, 1.0)


    def test_hrtb_config(self):
        global_config = {}
        global_config['_sip_address'] = '127.0.0.1'
        global_config['hrtb_ival'] = 200
        global_config['hrtb_retr_ival'] = 500
        c = Rtp_proxy_client(global_config)
        self.assertEquals(c.hrtb_ival, 200)
        self.assertEquals(c.hrtb_retr_ival, 500)
