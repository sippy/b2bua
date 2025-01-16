# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2014 Sippy Software, Inc. All rights reserved.
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

from functools import partial

from sippy.Time.MonoTime import MonoTime
from sippy.SipAddress import SipAddress
from sippy.SipRoute import SipRoute
from sippy.UaStateGeneric import UaStateGeneric
from sippy.UacStateTrying import UacStateTrying
from sippy.CCEvents import CCEventRing, CCEventConnect, CCEventFail, CCEventRedirect, \
  CCEventDisconnect, CCEventPreConnect

class UacStateRinging(UacStateTrying):
    sname = 'Ringing(UAC)'
    triedauth = False

    def _recvResponse(self, resp, tr):
        body = resp.getBody()
        code, reason = resp.getSCode()
        scode = (code, reason, body)
        if code < 200:
            if self.ua.p1xx_ts == None:
                self.ua.p1xx_ts = resp.rtime
            self.ua.last_scode = code
            event = CCEventRing(scode, rtime = resp.rtime, origin = self.ua.origin)
            for ring_cb in self.ua.ring_cbs:
                ring_cb(self.ua, resp.rtime, self.ua.origin, code)
            if body is not None:
                if self.ua.on_remote_sdp_change != None:
                    body = self.ua.on_remote_sdp_change(body, partial(self.ua.delayed_remote_sdp_update, event))
                    if body is None:
                        return None
                self.ua.rSDP = body.getCopy()
            else:
                self.ua.rSDP = None
            self.ua.equeue.append(event)
            return None
        if self.ua.expire_timer != None:
            self.ua.expire_timer.cancel()
            self.ua.expire_timer = None
        if code >= 200 and code < 300:
            self.updateRoutes(resp)
            tag = resp.getHFBody('to').getTag()
            if tag == None:
                print('tag-less 200 OK, disconnecting')
                scode = (502, 'Bad Gateway')
                event = CCEventFail(scode, rtime = resp.rtime, origin = self.ua.origin)
                self.ua.equeue.append(event)
                self.genBYE()
                if self.ua.setup_ts is None or resp.rtime >= self.ua.setup_ts:
                    self.ua.disconnect_ts = resp.rtime
                else:
                    self.ua.disconnect_ts = MonoTime()
                return (self.ua.UaStateFailed, self.ua.fail_cbs, resp.rtime, self.ua.origin, scode[0])
            self.ua.rUri.setTag(tag)
            if not self.ua.late_media or body is None:
                self.ua.late_media = False
                event = CCEventConnect(scode, rtime = resp.rtime, origin = self.ua.origin)
                self.ua.startCreditTimer(resp.rtime)
                self.ua.connect_ts = resp.rtime
                rval = (self.ua.UaStateConnected, self.ua.conn_cbs, resp.rtime, self.ua.origin)
            else:
                event = CCEventPreConnect(scode, rtime = resp.rtime, origin = self.ua.origin)
                tr.uack = True
                self.ua.pending_tr = tr
                rval = (self.ua.UaStateConnected,)
            if body is not None:
                if self.ua.on_remote_sdp_change != None:
                    body = self.ua.on_remote_sdp_change(body, partial(self.ua.delayed_remote_sdp_update, event))
                    if body is None:
                        return rval
                self.ua.rSDP = body.getCopy()
            else:
                self.ua.rSDP = None
            self.ua.equeue.append(event)
            return rval
        if code in (301, 302) and resp.countHFs('contact') > 0:
            scode = (code, reason, body, (resp.getHFBody('contact').getUri().getCopy(),))
            event = CCEventRedirect(scode, rtime = resp.rtime, origin = self.ua.origin)
        elif code == 300 and resp.countHFs('contact') > 0:
            redirects = tuple(x.getUri().getCopy() for x in resp.getHFBodys('contact'))
            scode = (code, reason, body, redirects)
            event = CCEventRedirect(scode, rtime = resp.rtime, origin = self.ua.origin)
        else:
            event = CCEventFail(scode, rtime = resp.rtime, origin = self.ua.origin)
        try:
            event.reason_rfc3326 = resp.getHFBody('reason')
        except:
            pass
        self.ua.equeue.append(event)
        if self.ua.setup_ts is None or resp.rtime >= self.ua.setup_ts:
            self.ua.disconnect_ts = resp.rtime
        else:
            self.ua.disconnect_ts = MonoTime()
        return (self.ua.UaStateFailed, self.ua.fail_cbs, resp.rtime, self.ua.origin, code)

    def recvEvent(self, event):
        if isinstance(event, CCEventFail) or isinstance(event, CCEventRedirect) or isinstance(event, CCEventDisconnect):
            self.ua.global_config['_sip_tm'].cancelTransaction(self.ua.tr, extra_headers = event.getExtraHeaders())
            if self.ua.expire_timer != None:
                self.ua.expire_timer.cancel()
                self.ua.expire_timer = None
            if self.ua.setup_ts is None or event.rtime >= self.ua.setup_ts:
                self.ua.disconnect_ts = event.rtime
            else:
                self.ua.disconnect_ts = MonoTime()
            return (self.ua.UacStateCancelling, self.ua.disc_cbs, event.rtime, event.origin, self.ua.last_scode)
        #print('wrong event %s in the Ringing state' % event)
        return None
