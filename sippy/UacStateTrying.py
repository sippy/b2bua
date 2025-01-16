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

from sippy.SipAddress import SipAddress
from sippy.SipRoute import SipRoute
from sippy.UaStateGeneric import UaStateGeneric
from sippy.Time.Timeout import TimeoutAbsMono
from sippy.Time.MonoTime import MonoTime
from sippy.CCEvents import CCEventRing, CCEventConnect, CCEventFail, CCEventRedirect, \
  CCEventDisconnect, CCEventPreConnect
from sippy.Exceptions.SdpParseError import SdpHandlingErrors

class UacStateTrying(UaStateGeneric):
    sname = 'Trying(UAC)'
    triedauth = False

    def _recvResponse(self, resp, tr):
        body = resp.getBody()
        code, reason = resp.getSCode()
        scode = (code, reason, body)
        self.ua.last_scode = code

        if self.ua.no_reply_timer != None:
            self.ua.no_reply_timer.cancel()
            self.ua.no_reply_timer = None
            if code == 100 and self.ua.no_progress_time != None:
                self.ua.no_progress_timer = TimeoutAbsMono(self.ua.no_progress_expires, self.ua.no_progress_mtime)
            elif code < 200 and self.ua.expire_time != None:
                self.ua.expire_timer = TimeoutAbsMono(self.ua.expires, self.ua.expire_mtime)
        if code == 100:
            if self.ua.p100_ts == None:
                self.ua.p100_ts = resp.rtime
            self.ua.equeue.append(CCEventRing(scode, rtime = resp.rtime, origin = self.ua.origin))
            return None
        if self.ua.no_progress_timer != None:
            self.ua.no_progress_timer.cancel()
            self.ua.no_progress_timer = None
            if code < 200 and self.ua.expire_time != None:
                self.ua.expire_timer = TimeoutAbsMono(self.ua.expires, self.ua.expire_mtime)
        if code < 200:
            event = CCEventRing(scode, rtime = resp.rtime, origin = self.ua.origin)
            if body is not None:
                if self.ua.on_remote_sdp_change != None:
                    body = self.ua.on_remote_sdp_change(body, partial(self.ua.delayed_remote_sdp_update, event))
                    if body is None:
                        self.ua.p1xx_ts = resp.rtime
                        return (self.ua.UacStateRinging, self.ua.ring_cbs, resp.rtime, self.ua.origin, code)
                self.ua.rSDP = body.getCopy()
            else:
                self.ua.rSDP = None
            self.ua.equeue.append(event)
            self.ua.p1xx_ts = resp.rtime
            return (self.ua.UacStateRinging, self.ua.ring_cbs, resp.rtime, self.ua.origin, code)
        if self.ua.expire_timer != None:
            self.ua.expire_timer.cancel()
            self.ua.expire_timer = None
        if code >= 200 and code < 300:
            self.updateRoutes(resp)
            tag = resp.getHFBody('to').getTag()
            if tag == None:
                print('tag-less 200 OK, disconnecting')
                scode = (502, 'Bad Gateway')
                self.ua.equeue.append(CCEventFail(scode, rtime = resp.rtime, origin = self.ua.origin))
                # Generate and send BYE
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
            if self.ua.pass_auth:
                if code == 401 and resp.countHFs('www-authenticate') != 0:
                    event.challenges = [x.getCopy() for x in resp.getHFs('www-authenticate')]
                elif code == 407 and resp.countHFs('proxy-authenticate') != 0:
                    event.challenges = [x.getCopy() for x in resp.getHF('proxy-authenticate')]
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
            if self.ua.no_progress_timer != None:
                self.ua.no_progress_timer.cancel()
                self.ua.no_progress_timer = None
            if self.ua.no_reply_timer != None:
                self.ua.no_reply_timer.cancel()
                self.ua.no_reply_timer = None
            if self.ua.setup_ts is None or event.rtime >= self.ua.setup_ts:
                self.ua.disconnect_ts = event.rtime
            else:
                self.ua.disconnect_ts = MonoTime()
            return (self.ua.UacStateCancelling, self.ua.disc_cbs, event.rtime, event.origin, self.ua.last_scode)
        #print('wrong event %s in the Trying state' % event)
        return None

    def updateRoutes(self, resp):
        if resp.countHFs('contact') > 0:
            self.ua.rTarget = resp.getHFBody('contact').getUrl().getCopy()
        self.ua.routes = [x.getCopy() for x in resp.getHFBodys('record-route')]
        self.ua.routes.reverse()
        if len(self.ua.routes) > 0:
            if not self.ua.routes[0].getUrl().lr:
                self.ua.routes.append(SipRoute(address = SipAddress(url = self.ua.rTarget)))
                self.ua.rTarget = self.ua.routes.pop(0).getUrl()
                self.ua.rAddr = self.ua.rTarget.getTAddr()
            elif self.ua.outbound_proxy != None:
                self.ua.routes.append(SipRoute(address = SipAddress(url = self.ua.rTarget)))
                self.ua.rTarget = self.ua.routes[0].getUrl().getCopy()
                self.ua.rTarget.lr = False
                self.ua.rTarget.other = tuple()
                self.ua.rTarget.headers = tuple()
            else:
                self.ua.rAddr = self.ua.routes[0].getTAddr()
        else:
            self.ua.rAddr = self.ua.rTarget.getTAddr()

    def genBYE(self):
        req = self.ua.genRequest('BYE')
        self.ua.newTransaction(req)

    def recvResponse(self, resp, tr):
        try:
            return self._recvResponse(resp, tr)
        except SdpHandlingErrors as ex:
            scode = (ex.code, ex.msg)
            event = CCEventFail(scode, rtime = resp.rtime, origin = self.ua.origin)
            event.reason_rfc3326 = ex.getReason()
            code = resp.getSCode()[0]
            if code < 200:
                self.ua.global_config['_sip_tm'].cancelTransaction(self.ua.tr,
                  extra_headers = event.getExtraHeaders())
            elif code >= 200 and code < 300:
                self.genBYE()
            self.ua.equeue.append(event)
            self.ua.disconnect_ts = resp.rtime
            return (self.ua.UaStateFailed, self.ua.fail_cbs, resp.rtime, self.ua.origin, ex.code)
