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

from hashlib import md5
from random import random
from time import time

from sippy.SipHeader import SipHeader
from sippy.UasStateIdle import UasStateIdle
from sippy.UacStateIdle import UacStateIdle
from sippy.SipRequest import SipRequest
from sippy.SipContentType import SipContentType
from sippy.SipMaxForwards import SipMaxForwards
from sippy.CCEvents import CCEventTry, CCEventFail, CCEventDisconnect, CCEventInfo
from sippy.MsgBody import MsgBody
from sippy.Time.MonoTime import MonoTime
from sippy.Time.Timeout import TimeoutAbsMono
from sippy.Exceptions.SdpParseError import SdpHandlingErrors
from sippy.SipConf import SipConf

class UA(object):
    global_config = None
    state = None
    event_cb = None
    uasReq = None
    uacResp = None
    username = None
    password = None
    auth_enalgs = None
    equeue = None
    dId = None
    credit_time = None
    credit_times = None
    credit_timer = None
    conn_cbs = None
    disc_cbs = None
    fail_cbs = None
    ring_cbs = None
    dead_cbs = None
    rCSeq = None
    lTag = None
    lUri = None
    rUri = None
    cId = None
    lCSeq = None
    lContact = None
    rAddr = None
    rAddr0 = None
    routes = None
    rTarget = None
    uasResp = None
    lSDP = None
    rSDP = None
    kaInterval = 0
    branch = None
    reqs = None
    extra_headers = None
    useRefer = True
    expire_time = None
    expire_timer = None
    no_progress_time = None
    no_progress_timer = None
    no_reply_time = None
    no_reply_timer = None
    on_local_sdp_change = None
    on_remote_sdp_change = None
    last_scode = 100
    setup_ts = None
    p100_ts = None
    p1xx_ts = None
    connect_ts = None
    disconnect_ts = None
    local_ua = None
    remote_ua = None
    elast_seq = None
    origin = None
    source_address = None
    outbound_proxy = None
    pass_auth = False
    pending_tr = None
    tr = None
    late_media = False
    godead_timeout = 32.0
    compact_sip = False
    uas_lossemul = 0

    if 'UasStateTrying' not in globals(): from sippy.UasStateTrying import UasStateTrying
    if 'UacStateTrying' not in globals(): from sippy.UacStateTrying import UacStateTrying
    if 'UacStateRinging' not in globals(): from sippy.UacStateRinging import UacStateRinging
    if 'UasStateRinging' not in globals(): from sippy.UasStateRinging import UasStateRinging
    if 'UaStateFailed' not in globals(): from sippy.UaStateFailed import UaStateFailed
    if 'UaStateConnected' not in globals(): from sippy.UaStateConnected import UaStateConnected
    if 'UacStateCancelling' not in globals(): from sippy.UacStateCancelling import UacStateCancelling
    if 'UasStateUpdating' not in globals(): from sippy.UasStateUpdating import UasStateUpdating
    if 'UacStateUpdating' not in globals(): from sippy.UacStateUpdating import UacStateUpdating
    if 'UaStateDisconnected' not in globals(): from sippy.UaStateDisconnected import UaStateDisconnected
    if 'UaStateDead' not in globals(): from sippy.UaStateDead import UaStateDead

    def __init__(self, global_config, event_cb = None, username = None, password = None, nh_address = None, credit_time = None, \
      conn_cbs = None, disc_cbs = None, fail_cbs = None, ring_cbs = None, dead_cbs = None, ltag = None, extra_headers = None, \
      expire_time = None, no_progress_time = None, nh_transport = SipConf.my_transport):
        self.global_config = global_config
        self.event_cb = event_cb
        self.equeue = []
        self.setAuth(username, password)
        self.setNextHop(nh_address, nh_transport)
        self.credit_time = credit_time
        self.credit_times = {}
        if conn_cbs != None:
            self.conn_cbs = conn_cbs
        else:
            self.conn_cbs = ()
        if disc_cbs != None:
            self.disc_cbs = disc_cbs
        else:
            self.disc_cbs = ()
        if fail_cbs != None:
            self.fail_cbs = fail_cbs
        else:
            self.fail_cbs = ()
        if ring_cbs != None:
            self.ring_cbs = ring_cbs
        else:
            self.ring_cbs = ()
        if dead_cbs != None:
            self.dead_cbs = dead_cbs
        else:
            self.dead_cbs = ()
        if ltag != None:
            self.lTag = ltag
        else:
            salt = str((random() * 1000000000) + time())
            self.lTag = md5(salt.encode()).hexdigest()
        self.reqs = {}
        self.extra_headers = extra_headers
        self.expire_time = expire_time
        self.no_progress_time = no_progress_time
        #print(self.username, self.password)

    def setNextHop(self, nh_address, nh_transport=SipConf.my_transport):
        assert self.state is None, "Cannot set next hop address after UA has been created"
        self.rAddr = (nh_address, nh_transport)
        self.rAddr0 = self.rAddr

    def setAuth(self, username, password):
        assert self.state is None, "Cannot set authentication after UA has been created"
        self.username = username
        self.password = password

    def recvRequest(self, req, sip_t):
        #print('Received request %s in state %s instance %s' % (req.getMethod(), self.state, self))
        #print(self.rCSeq, req.getHFBody('cseq').getCSeqNum())
        def sendResponse(*rcode):
            resp = req.genResponse(*rcode, server = self.local_ua)
            self.global_config['_sip_tm'].sendResponse(resp, lossemul = self.uas_lossemul)
        req.sendResponse = sendResponse
        sip_t.compact = self.compact_sip
        if self.remote_ua == None:
            self.update_ua(req)
        rmethod = req.getMethod()
        if self.rCSeq != None and self.rCSeq >= req.getHFBody('cseq').getCSeqNum():
            return (req.genResponse(500, 'Server Internal Error', server = self.local_ua), None, None)
        self.rCSeq = req.getHFBody('cseq').getCSeqNum()
        if self.state == None:
            if rmethod == 'INVITE':
                self.changeState((UasStateIdle,))
            else:
                return None
        newstate = self.state.recvRequest(req)
        if newstate != None:
            self.changeState(newstate)
        self.emitPendingEvents()
        if newstate != None and rmethod == 'INVITE':
            return (None, self.state.cancel, self.disconnect)
        else:
            return None

    def processChallenge(self, resp, cseq, ch_hfname, auth_hfname, extra_headers):
        if self.username == None or self.password == None or \
          self.reqs[cseq].countHFs(auth_hfname) != 0:
            return False
        for challenge in resp.getHFBodys(ch_hfname):
            #print(self.processChallenge, cseq, challenge, challenge.algorithm)
            if self.auth_enalgs is not None and challenge.algorithm not in self.auth_enalgs:
                continue
            supported, qop = challenge.supportedAlgorithm()
            if supported:
                break
        else:
            return False
        req = self.genRequest('INVITE', self.lSDP, (challenge, qop), extra_headers = extra_headers)
        self.newUacTransaction(req, req_extra_headers = extra_headers)
        del self.reqs[cseq]
        return True

    def recvResponse(self, resp, tr):
        if self.state is None or self.state.dead:
            return
        self.update_ua(resp)
        code, reason = resp.getSCode()
        cseq, method = resp.getHFBody('cseq').getCSeq()
        if method == 'INVITE' and not self.pass_auth and cseq in self.reqs:
            if code == 401 and self.processChallenge(resp, cseq, \
              'www-authenticate', 'authorization', tr.req_extra_headers):
                return None
            if code == 407 and self.processChallenge(resp, cseq, \
              'proxy-authenticate', 'proxy-authorization', tr.req_extra_headers):
                return None
        if code >= 200 and cseq in self.reqs:
            del self.reqs[cseq]
        newstate = self.state.recvResponse(resp, tr)
        if newstate != None:
            self.changeState(newstate)
        self.emitPendingEvents()

    def recvEvent(self, event):
        #print(self, event)
        if self.state == None:
            if isinstance(event, CCEventTry) or isinstance(event, CCEventFail) or isinstance(event, CCEventDisconnect):
                self.changeState((UacStateIdle,))
            else:
                return
        newstate = self.state.recvEvent(event)
        if newstate != None:
            self.changeState(newstate)
        self.emitPendingEvents()

    def disconnect(self, rtime = None, origin = None):
        if rtime == None:
            rtime = MonoTime()
        self.equeue.append(CCEventDisconnect(rtime = rtime, origin = origin))
        self.recvEvent(CCEventDisconnect(rtime = rtime, origin = origin))

    def expires(self):
        self.expire_timer = None
        self.disconnect()

    def no_progress_expires(self):
        self.no_progress_timer = None
        self.disconnect()

    def no_reply_expires(self):
        self.no_reply_timer = None
        self.disconnect()

    def credit_expires(self, rtime):
        self.credit_timer = None
        self.disconnect(rtime)

    def changeState(self, newstate):
        if self.state != None:
            self.state.onStateChange(newstate[0])
        self.state = newstate[0](self)
        if len(newstate) > 1:
            for callback in newstate[1]:
                callback(self, *newstate[2:])

    def emitEvent(self, event):
        if self.event_cb != None:
            if self.elast_seq != None and self.elast_seq >= event.seq:
                #print('ignoring out-of-order event', event, event.seq, self.elast_seq, self.cId)
                return
            self.elast_seq = event.seq
            self.event_cb(event, self)

    def emitPendingEvents(self):
        while len(self.equeue) != 0 and self.event_cb != None:
            event = self.equeue.pop(0)
            if self.elast_seq != None and self.elast_seq >= event.seq:
                #print('ignoring out-of-order event', event, event.seq, self.elast_seq, self.cId)
                continue
            self.elast_seq = event.seq
            self.event_cb(event, self)

    def genRequest(self, method, body = None, cqop = None, \
      extra_headers = None, max_forwards = None):
        if self.outbound_proxy != None:
            target = (self.outbound_proxy, SipConf.my_transport)
        else:
            target = self.rAddr
        if max_forwards != None:
            max_forwards_hf = SipMaxForwards(number = max_forwards)
        else:
            max_forwards_hf = None
        req = SipRequest(method = method, ruri = self.rTarget, to = self.rUri, fr0m = self.lUri,
                         cseq = self.lCSeq, callid = self.cId, contact = self.lContact,
                         routes = self.routes, target = target, user_agent = self.local_ua,
                         maxforwards = max_forwards_hf)
        if cqop != None:
            challenge, qop = cqop
            if body is not None and qop == 'auth-int':
                sbody = str(body)
                #print(len(sbody), sbody)
            else:
                sbody = None
            auth = challenge.genAuthHF(self.username, self.password, method, \
              str(self.rTarget), sbody, qop)
            req.appendHeader(SipHeader(body = auth))
        if body is not None:
            req.setBody(body)
        if self.extra_headers is not None:
            req.appendHeaders(self.extra_headers)
        if extra_headers is not None:
            req.appendHeaders(extra_headers)
        if method == 'INVITE':
            self.reqs[self.lCSeq] = req
        self.lCSeq += 1
        return req

    def sendUasResponse(self, scode, reason, body = None, contacts = None, \
      extra_headers = None, ack_wait = False):
        uasResp = self.uasResp.getCopy()
        uasResp.setSCode(scode, reason)
        uasResp.setBody(body)
        if contacts != None:
            for contact in contacts:
                uasResp.appendHeader(SipHeader(name = 'contact', body = contact))
        if extra_headers is not None:
            uasResp.appendHeaders(extra_headers)
        if ack_wait:
            ack_cb = self.recvACK
        else:
            ack_cb = None
        self.global_config['_sip_tm'].sendResponse(uasResp, ack_cb = ack_cb, \
          lossemul = self.uas_lossemul)

    def recvACK(self, req):
        if not self.isConnected():
            return
        #print('UA::recvACK', req)
        newstate = self.state.recvACK(req)
        if newstate != None:
            self.changeState(newstate)
        self.emitPendingEvents()

    def isYours(self, req = None, call_id = None, from_tag = None, to_tag = None):
        #print(self.branch, req.getHFBody('via').getBranch())
        if req != None:
            if req.getMethod() != 'BYE' and self.branch != None and \
              self.branch != req.getHFBody('via').getBranch():
                return None
            call_id = str(req.getHFBody('call-id'))
            from_tag = req.getHFBody('from').getTag()
            to_tag = req.getHFBody('to').getTag()
        #print(str(self.cId), call_id)
        if call_id != str(self.cId):
            return None
        #print(self.rUri.getTag(), from_tag)
        if self.rUri != None and self.rUri.getTag() != from_tag:
            return None
        #print(self.lUri.getTag(), to_tag)
        if self.lUri != None and self.lUri.getTag() != to_tag:
            return None
        return self

    def isDead(self):
        if self.state != None:
            return self.state.dead
        return False

    def isConnected(self):
        if self.state != None:
            return self.state.connected
        return False

    def getCLD(self):
        if self.rUri == None:
            return None
        return self.rUri.getUrl().username

    def getCLI(self):
        if self.lUri == None:
            return None
        return self.lUri.getUrl().username

    def getCallingName(self):
        if self.lUri == None:
            return None
        return self.lUri.getUri().name

    def getRAddr0(self):
        return self.rAddr0

    def getCID(self):
        # Return tuple containing call-id, local tag and remote tag
        rval = [str(self.cId), None, None]
        if self.lUri != None:
            rval[1] = self.lUri.getTag()
        if self.rUri != None:
            rval[2] = self.rUri.getTag()
        return tuple(rval)

    def delayed_remote_sdp_update(self, event, remote_sdp_body, ex=None):
        if ex is not None:
            if not isinstance(ex, SdpHandlingErrors): raise ex
            event = CCEventFail((ex.code, ex.msg))
            event.reason_rfc3326 = ex.getReason()
        else:
            self.rSDP = remote_sdp_body.getCopy()
        self.equeue.append(event)
        self.emitPendingEvents()
        if ex is not None:
            self.recvEvent(event)

    def delayed_local_sdp_update(self, event, local_sdp_body, ex=None):
        if ex is not None:
            if not isinstance(ex, SdpHandlingErrors): raise ex
            event = CCEventFail((ex.code, ex.msg))
            event.reason_rfc3326 = ex.getReason()
            self.equeue.append(event)
            self.emitPendingEvents()
        self.recvEvent(event)

    def getAcct(self):
        if self.disconnect_ts != None:
            disconnect_ts = self.disconnect_ts
            disconnected = True
        else:
            disconnect_ts = MonoTime()
            disconnected = False
        if self.connect_ts != None:
            return (disconnect_ts - self.connect_ts, self.connect_ts - self.setup_ts, True, disconnected)
        return (0, disconnect_ts - self.setup_ts, False, disconnected)

    def update_ua(self, msg):
        if msg.countHFs('user-agent') > 0:
            self.remote_ua = msg.getHFBody('user-agent').name
        elif msg.countHFs('server') > 0:
            self.remote_ua = msg.getHFBody('server').name
        return

    def cancelCreditTimer(self):
        if self.credit_timer != None:
            self.credit_timer.cancel()
            self.credit_timer = None

    def startCreditTimer(self, rtime):
        if self.credit_time != None:
            self.credit_times[0] = rtime.getOffsetCopy(self.credit_time)
            self.credit_time = None
        try:
            credit_time = min([x for x in self.credit_times.values() if x != None])
        except ValueError:
            return
        self.credit_timer = TimeoutAbsMono(self.credit_expires, credit_time, credit_time)

    def resetCreditTime(self, rtime, new_credit_times):
        self.credit_times.update(new_credit_times)
        if self.state.connected:
            self.cancelCreditTimer()
            self.startCreditTimer(rtime)

    def cleanup(self):
        pass

    def newTransaction(self, req, req_extra_headers = None, **kwa):
        tr = self.global_config['_sip_tm'].newTransaction(req, \
          laddress = self.source_address, compact = self.compact_sip, **kwa)
        tr.req_extra_headers = req_extra_headers
        return tr

    def newUacTransaction(self, req, **kwa):
        self.tr = self.newTransaction(req, resp_cb = self.recvResponse, \
          cb_ifver = 2, **kwa)
