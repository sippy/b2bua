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

from sippy.SipContact import SipContact
from sippy.UaStateGeneric import UaStateGeneric
from sippy.CCEvents import CCEventDisconnect, CCEventRing, CCEventConnect, CCEventFail, CCEventRedirect

class UasStateUpdating(UaStateGeneric):
    sname = 'Updating(UAS)'
    connected = True

    def recvRequest(self, req):
        if req.getMethod() == 'INVITE':
            req.sendResponse(491, 'Request Pending')
            return None
        elif req.getMethod() == 'BYE':
            self.ua.sendUasResponse(487, 'Request Terminated')
            req.sendResponse(200, 'OK')
            #print('BYE received in the Updating state, going to the Disconnected state')
            event = CCEventDisconnect(rtime = req.rtime, origin = self.ua.origin)
            try:
                event.reason_rfc3326 = req.getHFBody('reason')
            except:
                pass
            self.ua.equeue.append(event)
            self.ua.cancelCreditTimer()
            self.ua.disconnect_ts = req.rtime
            return (self.ua.UaStateDisconnected, self.ua.disc_cbs, req.rtime, self.ua.origin)
        elif req.getMethod() == 'REFER':
            if req.countHFs('refer-to') == 0:
                req.sendResponse(400, 'Bad Request')
                return None
            self.ua.sendUasResponse(487, 'Request Terminated')
            req.sendResponse(202, 'Accepted')
            also = req.getHFBody('refer-to').getCopy()
            self.ua.equeue.append(CCEventDisconnect(also, rtime = req.rtime, origin = self.ua.origin))
            self.ua.cancelCreditTimer()
            self.ua.disconnect_ts = req.rtime
            return (self.ua.UaStateDisconnected, self.ua.disc_cbs, req.rtime, self.ua.origin)
        #print('wrong request %s in the state Updating' % req.getMethod())
        return None

    def recvEvent(self, event):
        eh = event.getExtraHeaders()
        if isinstance(event, CCEventRing):
            scode = event.getData()
            if scode == None:
                scode = (180, 'Ringing', None)
            body = scode[2]
            if body is not None and self.ua.on_local_sdp_change != None and body.needs_update:
                self.ua.on_local_sdp_change(body, partial(self.ua.delayed_local_sdp_update, event))
                return None
            self.ua.lSDP = body
            self.ua.sendUasResponse(scode[0], scode[1], body, extra_headers = eh)
            return None
        elif isinstance(event, CCEventConnect):
            code, reason, body = event.getData()
            if body is not None and self.ua.on_local_sdp_change != None and body.needs_update:
                self.ua.on_local_sdp_change(body, partial(self.ua.delayed_local_sdp_update, event))
                return None
            self.ua.lSDP = body
            self.ua.sendUasResponse(code, reason, body, (self.ua.lContact,), \
              extra_headers = eh)
            return (self.ua.UaStateConnected,)
        elif isinstance(event, CCEventRedirect):
            scode = event.getData()
            contacts = None
            if scode == None:
                scode = (500, 'Failed', None, None)
            elif scode[3] != None:
                contacts = tuple(SipContact(address = x) for x in scode[3])
            self.ua.sendUasResponse(scode[0], scode[1], scode[2], contacts, \
              extra_headers = eh)
        elif isinstance(event, CCEventFail):
            scode = event.getData()
            if scode == None:
                scode = (500, 'Failed')
            self.ua.rSDP = None
            self.ua.sendUasResponse(scode[0], scode[1], extra_headers = eh)
            return (self.ua.UaStateConnected,)
        elif isinstance(event, CCEventDisconnect):
            self.ua.sendUasResponse(487, 'Request Terminated', extra_headers = eh)
            req = self.ua.genRequest('BYE', extra_headers = eh)
            self.ua.newTransaction(req)
            self.ua.cancelCreditTimer()
            self.ua.disconnect_ts = event.rtime
            return (self.ua.UaStateDisconnected, self.ua.disc_cbs, event.rtime, event.origin)
        #print('wrong event %s in the Updating state' % event)
        return None

    def cancel(self, rtime, inreq):
        req = self.ua.genRequest('BYE')
        self.ua.newTransaction(req)
        self.ua.cancelCreditTimer()
        self.ua.disconnect_ts = rtime
        self.ua.changeState((self.ua.UaStateDisconnected, self.ua.disc_cbs, rtime, self.ua.origin))
        event = CCEventDisconnect(rtime = rtime, origin = self.ua.origin)
        if inreq is not None:
            try:
                event.reason_rfc3326 = inreq.getHFBody('reason')
            except:
                pass
        self.ua.emitEvent(event)
