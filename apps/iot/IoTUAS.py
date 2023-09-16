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
from sippy.CCEvents import CCEventRing, CCEventConnect, CCEventPreConnect
from sippy.SipTransactionManager import SipTransactionManager
from sippy.SipCiscoGUID import SipCiscoGUID
from sippy.SipCallId import SipCallId
from sippy.MsgBody import MsgBody
from sippy.SdpOrigin import SdpOrigin
from sippy.Udp_server import Udp_server, Udp_server_opts
from sippy.SipURL import SipURL
from sippy.SipRegistrationAgent import SipRegistrationAgent

from sippy.misc import local4remote

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

class IoTUAS(object):
    global_config = None
    ua = None
    cli = 'pel150_uas'
    cld = 'pel150_uac'
    authname = None
    authpass = None
    body = None
    rgen = None
    rserv = None
    ragent = None

    def __init__(self, global_config, authname = None, authpass = None):
        self.global_config = global_config
        self.authname = authname
        self.authpass = authpass
        udsc, udsoc = SipTransactionManager.model_udp_server
        udsoc.nworkers = 1
        udsoc.flags = 0
        global_config['_sip_tm'] = SipTransactionManager(global_config, self.recvRequest)
        self.body = MsgBody(body_txt)
        self.body.parse()
        proxy, port = global_config['nh_addr']
        aor = SipURL(username = self.cli, host = proxy, port = port)
        caddr = local4remote(proxy)
        cport = global_config['_sip_port']
        contact = SipURL(username = self.cli, host = caddr, port = cport)
        ragent = SipRegistrationAgent(global_config, aor, contact, user = self.authname, passw = self.authpass)
        ragent.doregister()

    def sess_term(self, ua, rtime, origin, result = 0):
        print('disconnected')
        self.rgen.stop()
        self.rserv.shutdown()
        self.rserv = None
        self.rgen = None

    def rtp_received(self, data, address, udp_server, rtime):
        pass

    def recvRequest(self, req, sip_t):
        if req.getMethod() in ('NOTIFY', 'PING'):
            # Whynot?
            return (req.genResponse(200, 'OK'), None, None)
        if req.getMethod() == 'INVITE':
            if self.rserv != None:
                return (req.genResponse(486, 'Busy Here'), None, None)
            # New dialog
            uaA = UA(self.global_config, self.recvEvent, disc_cbs = (self.sess_term,))
            uaA.recvRequest(req, sip_t)
            return
        return (req.genResponse(501, 'Not Implemented'), None, None)

    def recvEvent(self, event, ua):
        if isinstance(event, CCEventTry):
            cId, cli, cld, sdp_body, auth, caller_name = event.getData()
            if sdp_body == None:
                return
            sdp_body.parse()
            sect = sdp_body.content.sections[0]
            rtp_target = (sect.c_header.addr, sect.m_header.port)
            rtp_laddr = local4remote(rtp_target[0])
            rserv_opts = Udp_server_opts((rtp_laddr, 0), self.rtp_received)
            rserv_opts.nworkers = 1
            self.rserv = Udp_server({}, rserv_opts)
            self.rgen = RTPGen()
            self.rgen.start(self.rserv, rtp_target)
            sect = self.body.content.sections[0]
            sect.c_header.addr = self.rserv.uopts.laddress[0]
            sect.m_header.port = self.rserv.uopts.laddress[1]
            self.body.content.o_header = SdpOrigin()
            oevent = CCEventConnect((200, 'OK', self.body))
            ua.recvEvent(oevent)
            return
