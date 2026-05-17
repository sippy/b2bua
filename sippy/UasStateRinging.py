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

from sippy.UasStateProgressing import UasStateProgressing
from sippy.CCEvents import CCEventRing, CCEventConnect, CCEventFail, CCEventRedirect, \
  CCEventDisconnect, CCEventPreConnect

class UasStateRinging(UasStateProgressing):
    sname = 'Ringing(UAS)'
    rseq = None

    def _recvEventRing(self, event, eh):
        code = super()._recvEventRing(event, eh)
        if code is None:
            return None
        if self.ua.p1xx_ts is None:
            self.ua.p1xx_ts = event.rtime
        for ring_cb in self.ua.ring_cbs:
            ring_cb(self.ua, event.rtime, event.origin, code)
        return None

    recv_event_handlers = {
      CCEventRing: _recvEventRing,
      CCEventConnect: UasStateProgressing._recvEventConnect,
      CCEventPreConnect: UasStateProgressing._recvEventPreConnect,
      CCEventRedirect: UasStateProgressing._recvEventRedirect,
      CCEventFail: UasStateProgressing._recvEventFail,
      CCEventDisconnect: UasStateProgressing._recvEventDisconnect,
    }

    def recvRequest(self, req):
        if req.getMethod() == 'BYE':
            self.ua.sendUasResponse(487, 'Request Terminated')
            req.sendResponse(200, 'OK')
            #print('BYE received in the Ringing state, going to the Disconnected state')
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
            if self.ua.expire_timer != None:
                self.ua.expire_timer.cancel()
                self.ua.expire_timer = None
            self.ua.disconnect_ts = req.rtime
            return (self.ua.UaStateDisconnected, self.ua.disc_cbs, req.rtime, self.ua.origin)
        return None
