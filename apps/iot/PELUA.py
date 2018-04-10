# Copyright (c) 2018 Sippy Software, Inc. All rights reserved.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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
