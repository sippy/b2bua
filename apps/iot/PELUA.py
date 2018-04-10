from sippy.UA import UA
from sippy.CCEvents import CCEventDisconnect, CCEventTry
from sippy.SipTransactionManager import SipTransactionManager
from sippy.SipCiscoGUID import SipCiscoGUID
from sippy.SipCallId import SipCallId
from sippy.MsgBody import MsgBody

from RTPGen import RTPGen

body_txt = 'v=0\r\n' + \
  'o=- 380960 380960 IN IP4 192.168.22.95\r\n' + \
  's=-\r\n' + \
  'c=IN IP4 192.168.22.95\r\n' + \
  't=0 0\r\n' + \
  'm=audio 16474 RTP/AVP 0\r\n' + \
  'a=rtpmap:0 PCMU/8000\r\n' + \
  'a=ptime:30\r\n' + \
  'a=sendrecv\r\n' + \
  '\r\n'

class PELUA(object):
    global_config = None
    ua = None
    cli = 'pel150_uac'
    cld = 'pel150_uas'
    authname = None
    authpass = None
    body = None
    rgen = None

    def __init__(self, global_config):
        self.global_config = global_config
        global_config['_sip_tm'] = SipTransactionManager(global_config)
        self.body = MsgBody(body_txt)
        self.body.parse()

    def sess_started(self):
        print('started')
        self.ua = UA(self.global_config, event_cb = self.recvEvent, \
          nh_address = tuple(self.global_config['nh_addr']))
        self.ua.username = self.authname
        self.ua.password = self.authpass
        event = CCEventTry((SipCallId(), SipCiscoGUID(), self.cli, self.cld, self.body, \
          None, 'PEL 150-2'))
        self.rgen = RTPGen()
        self.rgen.start()
        self.ua.recvEvent(event)

    def sess_ended(self):
        print('ended')
        event = CCEventDisconnect()
        self.ua.recvEvent(event)
        self.rgen.stop()

    def recvEvent(self, event, ua):
        pass
