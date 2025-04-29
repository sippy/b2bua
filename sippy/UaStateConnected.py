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

from sippy.Time.Timeout import Timeout
from sippy.UaStateGeneric import UaStateGeneric
from sippy.SipAlso import SipAlso
from sippy.SipAddress import SipAddress
from sippy.SipHeader import SipHeader
from sippy.SipReferTo import SipReferTo
from sippy.SipReferredBy import SipReferredBy
from sippy.SipMaxForwards import SipMaxForwards
from sippy.CCEvents import CCEventDisconnect, CCEventFail, CCEventRedirect, CCEventUpdate, CCEventInfo, CCEventConnect
from sippy.Exceptions.SdpParseError import SdpHandlingErrors

class UaStateConnected(UaStateGeneric):
    sname = 'Connected'
    triedauth = None
    keepalives = None
    ka_tr = None
    connected = True

    def __init__(self, ua):
        self.keepalives = 0
        self.ka_tr = None
        super().__init__(ua)
        self.ua.branch = None
        if self.ua.kaInterval > 0:
            Timeout(self.keepAlive, self.ua.kaInterval)

    def recvRequest(self, req):
        if req.getMethod() == 'REFER':
            if req.countHFs('refer-to') == 0:
                req.sendResponse(400, 'Bad Request')
                return None
            req.sendResponse(202, 'Accepted')
            also = req.getHFBody('refer-to').getCopy()
            self.ua.equeue.append(CCEventDisconnect(also, rtime = req.rtime, origin = self.ua.origin))
            self.ua.recvEvent(CCEventDisconnect(rtime = req.rtime, origin = self.ua.origin))
            return None
        if req.getMethod() == 'INVITE':
            self.ua.uasResp = req.genResponse(100, 'Trying', server = self.ua.local_ua)
            self.ua.global_config['_sip_tm'].sendResponse(self.ua.uasResp)
            body = req.getBody()
            if body is None:
                # Some brain-damaged stacks use body-less re-INVITE as a means
                # for putting session on hold. Quick and dirty hack to make this
                # scenario working.
                body = self.ua.rSDP.getCopy()
                body.parse()
                for sect in body.content.sections:
                    sect.c_header.addr = '0.0.0.0'
            elif str(self.ua.rSDP) == str(body):
                self.ua.sendUasResponse(200, 'OK', self.ua.lSDP, (self.ua.lContact,))
                return None
            event = CCEventUpdate(body, rtime = req.rtime, origin = self.ua.origin)
            try:
                event.reason_rfc3326 = req.getHFBody('reason')
            except:
                pass
            try:
                event.max_forwards = req.getHFBody('max-forwards').getNum()
            except:
                pass
            if body is not None:
                if self.ua.on_remote_sdp_change != None:
                    body = self.ua.on_remote_sdp_change(body, partial(self.ua.delayed_remote_sdp_update, event))
                    if body is None:
                        return (self.ua.UasStateUpdating,)
                self.ua.rSDP = body.getCopy()
            else:
                self.ua.rSDP = None
            self.ua.equeue.append(event)
            return (self.ua.UasStateUpdating,)
        if req.getMethod() == 'BYE':
            req.sendResponse(200, 'OK')
            #print('BYE received in the Connected state, going to the Disconnected state')
            if req.countHFs('also') > 0:
                also = req.getHFBody('also').getCopy()
            else:
                also = None
            event = CCEventDisconnect(also, rtime = req.rtime, origin = self.ua.origin)
            try:
                event.reason_rfc3326 = req.getHFBody('reason')
            except:
                pass
            self.ua.equeue.append(event)
            self.ua.cancelCreditTimer()
            self.ua.disconnect_ts = req.rtime
            return (self.ua.UaStateDisconnected, self.ua.disc_cbs, req.rtime, self.ua.origin)
        if req.getMethod() == 'INFO':
            req.sendResponse(200, 'OK')
            event = CCEventInfo(req.getBody(), rtime = req.rtime, origin = self.ua.origin)
            try:
                event.reason_rfc3326 = req.getHFBody('reason')
            except:
                pass
            self.ua.equeue.append(event)
            return None
        if req.getMethod() == 'OPTIONS':
            req.sendResponse(200, 'OK')
            return None
        #print('wrong request %s in the state Connected' % req.getMethod())
        return None

    def recvACK(self, req):
        body = req.getBody()
        scode = ('ACK', 'ACK', body)
        event = CCEventConnect(scode, rtime = req.rtime, origin = self.ua.origin)
        if self.ua.expire_timer != None:
            self.ua.expire_timer.cancel()
            self.ua.expire_timer = None
        self.ua.cancelCreditTimer() # prevent timer leak on body-less re-INVITE
        self.ua.startCreditTimer(req.rtime)
        self.ua.connect_ts = req.rtime
        for callback in self.ua.conn_cbs:
            callback(self.ua, req.rtime, self.ua.origin)
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

    def recvEvent(self, event):
        eh = event.getExtraHeaders()
        if isinstance(event, CCEventDisconnect) or isinstance(event, CCEventFail) or isinstance(event, CCEventRedirect):
            #print('event', event, 'received in the Connected state sending BYE')
            redirect = None
            if isinstance(event, CCEventDisconnect):
                redirect = event.getData()
            elif isinstance(event, CCEventRedirect):
                redirects = event.getData()
                if redirects != None:
                    redirect = redirects[0]
            if redirect != None and self.ua.useRefer:
                req = self.ua.genRequest('REFER', extra_headers = eh)
                also = SipReferTo(address = redirect)
                req.appendHeader(SipHeader(name = 'refer-to', body = also))
                rby = SipReferredBy(address = SipAddress(url = self.ua.lUri.getUrl()))
                req.appendHeader(SipHeader(name = 'referred-by', body = rby))
                self.ua.newTransaction(req, resp_cb = self.rComplete)
            else:
                req = self.ua.genRequest('BYE', extra_headers = eh)
                if redirect != None:
                    also = SipAlso(address = redirect)
                    req.appendHeader(SipHeader(name = 'also', body = also))
                self.ua.newTransaction(req)
            self.ua.cancelCreditTimer()
            self.ua.disconnect_ts = event.rtime
            return (self.ua.UaStateDisconnected, self.ua.disc_cbs, event.rtime, event.origin)
        if isinstance(event, CCEventUpdate):
            body = event.getData()
            fake_laddr = (('127.0.0.1', None), None)
            if self.ua.lSDP.localStr(fake_laddr) == body.localStr(fake_laddr):
                if self.ua.rSDP != None:
                    self.ua.equeue.append(CCEventConnect((200, 'OK', self.ua.rSDP.getCopy()), \
                        rtime = event.rtime, origin = event.origin))
                else:
                    self.ua.equeue.append(CCEventConnect((200, 'OK', None), rtime = event.rtime, \
                      origin = event.origin))
                return None
            if body is not None and self.ua.on_local_sdp_change != None and body.needs_update:
                try:
                    self.ua.on_local_sdp_change(body, partial(self.ua.delayed_local_sdp_update, event))
                except SdpHandlingErrors as e:
                    event = CCEventFail((e.code, e.msg), rtime = event.rtime)
                    event.reason_rfc3326 = e.getReason()
                    self.ua.equeue.append(event)
                except Exception as e:
                    event = CCEventFail((400, 'Malformed SDP Body'), rtime = event.rtime)
                    event.setWarning(str(e))
                    self.ua.equeue.append(event)
                return None
            if event.max_forwards != None:
                if event.max_forwards <= 0:
                    self.ua.equeue.append(CCEventFail((483, 'Too Many Hops'), rtime = event.rtime))
                    return None
                max_forwards_hf = SipMaxForwards(number = event.max_forwards - 1)
            else:
                max_forwards_hf = None
            req = self.ua.genRequest('INVITE', body, extra_headers = eh, \
              max_forwards = max_forwards_hf)
            self.ua.lSDP = body
            self.ua.newUacTransaction(req, req_extra_headers = eh)
            return (self.ua.UacStateUpdating,)
        if isinstance(event, CCEventInfo):
            body = event.getData()
            req = self.ua.genRequest('INFO', body, extra_headers = eh)
            self.ua.newTransaction(req)
            return None
        if self.ua.pending_tr != None and isinstance(event, CCEventConnect):
            if self.ua.expire_timer != None:
                self.ua.expire_timer.cancel()
                self.ua.expire_timer = None
            code, reason, body = event.getData()
            if body is not None and self.ua.on_local_sdp_change != None and body.needs_update:
                self.ua.on_local_sdp_change(body, partial(self.ua.delayed_local_sdp_update, event))
                return None
            self.ua.cancelCreditTimer() # prevent timer leak on body-less re-INVITE
            self.ua.startCreditTimer(event.rtime)
            self.ua.connect_ts = event.rtime
            self.ua.lSDP = body
            self.ua.pending_tr.ack.setBody(body)
            self.ua.global_config['_sip_tm'].sendACK(self.ua.pending_tr)
            self.ua.pending_tr = None
            for callback in self.ua.conn_cbs:
                callback(self.ua, event.rtime, self.ua.origin)
            return None
        #print('wrong event %s in the Connected state' % event)
        return None

    def keepAlive(self):
        if self.ua.state != self:
            return
        #self.ua.lSDP.parse()
        #self.ua.lSDP.content.m_header.port += 4
        req = self.ua.genRequest('INVITE', self.ua.lSDP)
        self.triedauth = False
        self.ka_tr = self.ua.newTransaction(req, resp_cb = self.keepAliveResp)

    def keepAliveResp(self, resp):
        if self.ua.state != self:
            return
        code, reason = resp.getSCode()
        if code == 401 and resp.countHFs('www-authenticate') != 0 and \
          self.ua.username != None and self.ua.password != None and not self.triedauth:
            challenge = resp.getHFBody('www-authenticate')
            req = self.ua.genRequest('INVITE', self.ua.lSDP, challenge)
            self.ka_tr = self.ua.newTransaction(req, resp_cb = self.keepAliveResp)
            self.triedauth = True
            return
        if code == 407 and resp.countHFs('proxy-authenticate') != 0 and \
          self.ua.username != None and self.ua.password != None and not self.triedauth:
            challenge = resp.getHFBody('proxy-authenticate')
            req = self.ua.genRequest('INVITE', self.ua.lSDP, challenge)
            self.ka_tr = self.ua.newTransaction(req, resp_cb = self.keepAliveResp)
            self.triedauth = True
            return
        if code < 200:
            return
        self.ka_tr = None
        self.keepalives += 1
        if code in (408, 481, 486):
            _h, _p = self.ua.rAddr[0]
            if self.keepalives == 1:
                print('%s: Remote UAS at %s:%d does not support re-INVITES, disabling keep alives' % (self.ua.cId, _h, _p))
                Timeout(self.ua.disconnect, 600)
                return
            print('%s: Received %d response to keep alive from %s:%d, disconnecting the call' % (self.ua.cId, code, _h, _p))
            self.ua.disconnect()
            return
        Timeout(self.keepAlive, self.ua.kaInterval)

    def onStateChange(self, newstate):
        if self.ka_tr != None:
            self.ua.global_config['_sip_tm'].cancelTransaction(self.ka_tr)
            self.ka_tr = None
        if self.ua.pending_tr != None:
            self.ua.global_config['_sip_tm'].sendACK(self.ua.pending_tr)
            self.ua.pending_tr = None
        if self.ua.expire_timer != None:
            self.ua.expire_timer.cancel()
            self.ua.expire_timer = None

    def rComplete(self, resp):
        req = self.ua.genRequest('BYE')
        self.ua.newTransaction(req)
