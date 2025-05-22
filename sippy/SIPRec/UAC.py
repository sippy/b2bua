# Copyright (c) 2025 Sippy Software, Inc. All rights reserved.
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

from functools import partial

from sippy.UA import UA
from sippy.MsgBody import MsgBody
from sippy.MultipartMixBody import MultipartMixBody
from sippy.SdpBody import SdpBody
from sippy.Rtp_proxy.session import Rtp_proxy_session
from sippy.SipConf import SipConf
from sippy.SipCallId import SipCallId
from sippy.SdpOrigin import SdpOrigin
from sippy.CCEvents import CCEventTry, CCEventConnect, CCEventDisconnect
from sippy.Exceptions.RtpProxyError import RtpProxyError

class SRSTarget():
    address = None
    transport = SipConf.my_transport
    cli = None
    cld = None
    username = None
    password = None
    def __init__(self, address, **kwa):
        self.address = address
        for k, v in kwa.items():
            if not hasattr(self, k):
                raise ValueError(f"Invalid keyword argument: {k}")
            setattr(self, k, v)

class SIPRecUAC(UA):
    debug = False
    body_tmpl = '\r\n'.join(('v=0', f'o={SdpOrigin()}',
                             's=Sippy_SRC', 't=0 0'))
    def __init__(self, global_config, ua1, ua2, rtps, cId=None):
        if not rtps.rtp_proxy_client.copy_p_supported:
            raise RtpProxyError('RTP proxy server is too old, version 3.2 or higher is required')
        self.global_config = global_config
        self.ua1 = ua1
        self.ua2 = ua2
        self.rtps = rtps
        self.sidx2copy = {}
        if cId is None:
            cId = SipCallId()
        self.cId = cId
        super().__init__(global_config, self.outEvent, fail_cbs = (self.sess_term,),
                         disc_cbs = (self.sess_term,))

    def record(self, srs_target:SRSTarget):
        def extract_media_sections(sdp, ioff, copy_cmd):
            sdp.parse()
            ah_pass = ('rtpmap', 'ptime', 'rtcp-mux', 'ssrc')
            rval = []
            for i, sect in enumerate (s for s in sdp.content.sections):
                if not sect.m_header.transport.lower() in Rtp_proxy_session.AV_TRTYPES:
                    continue
                sect.a_headers = [x for x in sect.a_headers if x.name in ah_pass]
                sect.addHeader('a', 'sendonly')
                ioff += 1
                sect.addHeader('a', f'label:{ioff}')
                copy_sect_cmd = partial(copy_cmd, index=i)
                self.sidx2copy[ioff - 1] = copy_sect_cmd
                rval.append(sect)
            return tuple(rval)
        mbody = MultipartMixBody()
        sdp = MsgBody(content=SdpBody(self.body_tmpl))
        sdp.content.o_header = SdpOrigin()
        sects = []
        for (ua, copy_cmd) in (x for x in ((self.ua1, self.rtps.copy_caller), (self.ua2, self.rtps.copy_callee))):
            sects += extract_media_sections(ua.lSDP, len(sects), copy_cmd)
        sdp.content.sections.extend(sects)
        mbody.parts.append(sdp)
        self.setNextHop(srs_target.address, srs_target.transport)
        self.setAuth(srs_target.username, srs_target.password)
        body = MsgBody(content = mbody, mtype = mbody.getContentType())
        event = CCEventTry((self.cId, srs_target.cli, srs_target.cld, body, None, None))
        self.ua1.fail_cbs += (self.sess_term,)
        self.ua1.disc_cbs += (self.sess_term,)
        self.ua2.fail_cbs += (self.sess_term,)
        self.ua2.disc_cbs += (self.sess_term,)
        if self.debug:
            print(f"SIPRecUAC: Recording SDP: {str(body)}")
        self.recvEvent(event)

    def outEvent(self, event, ua):
        if self.debug:
            print('SIPRecUAC: outEvent:', str(event))
        if not isinstance(event, CCEventConnect):
            return
        sidx2copy = self.sidx2copy
        self.sidx2copy = None
        code, reason, body = event.getData()
        if body is None:
            # body-less INVITE is not supported (yet), open a PR!
            self.recvEvent(CCEventDisconnect())
            return
        body.parse()
        if body.getType() != 'application/sdp':
            # application/sdp body is expected
            self.recvEvent(CCEventDisconnect())
            return
        for i, sect in enumerate(body.content.sections):
            sidx2copy[i](sect.c_header.addr, sect.m_header.port)

    def sess_term(self, ua, rtime, origin, result = 0):
        if self.ua1 is None or self.ua2 is None:
            return
        if self.debug:
            print('SIPRecUAC: disconnected', self)
        self.ua1 = None
        self.ua2 = None
        self.rtps = None
        self.sidx2copy = None
        self.disconnect(rtime, origin)
