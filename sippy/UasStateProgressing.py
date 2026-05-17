# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2026 Sippy Software, Inc. All rights reserved.
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

from sippy.CCEvents import CCEventDisconnect
from sippy.UasStateGeneric import UasStateGeneric

class UasStateProgressing(UasStateGeneric):
    def _recvEventRing(self, event, eh):
        return super()._recvEventRing(event, eh, (self.ua.lContact,))

    def _recvEventConnect(self, event, eh):
        cdata = self._getConnectData(event)
        if cdata is None:
            return None
        code, reason, body = cdata
        self.ua.sendUasResponse(code, reason, body, (self.ua.lContact,), ack_wait = False, \
          extra_headers = eh)
        self._cancelExpireTimer()
        self.ua.startCreditTimer(event.rtime)
        self.ua.connect_ts = event.rtime
        return (self.ua.UaStateConnected, self.ua.conn_cbs, event.rtime, event.origin)

    def _recvEventPreConnect(self, event, eh):
        cdata = self._getConnectData(event)
        if cdata is None:
            return None
        code, reason, body = cdata
        self.ua.sendUasResponse(code, reason, body, (self.ua.lContact,), ack_wait = True, \
          extra_headers = eh)
        return (self.ua.UaStateConnected,)

    def _recvEventRedirect(self, event, eh):
        scode = super()._recvEventRedirect(event, eh)
        self._cancelExpireTimer()
        self.ua.disconnect_ts = event.rtime
        return (self.ua.UaStateFailed, self.ua.fail_cbs, event.rtime, event.origin, scode[0])

    def _recvEventFail(self, event, eh):
        scode = self._sendFailResponse(event, eh)
        self._cancelExpireTimer()
        self.ua.disconnect_ts = event.rtime
        return (self.ua.UaStateFailed, self.ua.fail_cbs, event.rtime, event.origin, scode[0])

    def _recvEventDisconnect(self, event, eh):
        #import sys, traceback
        #traceback.print_stack(file = sys.stdout)
        self.ua.sendUasResponse(500, 'Disconnected', extra_headers = eh)
        self._cancelExpireTimer()
        self.ua.disconnect_ts = event.rtime
        return (self.ua.UaStateDisconnected, self.ua.disc_cbs, event.rtime, event.origin, self.ua.last_scode)

    def cancel(self, rtime, req):
        event = CCEventDisconnect(rtime = rtime, origin = self.ua.origin)
        if req is not None:
            try:
                event.reason_rfc3326 = req.getHFBody('reason')
            except:
                pass
        self.ua.disconnect_ts = rtime
        self.ua.changeState((self.ua.UaStateDisconnected, self.ua.disc_cbs, rtime, self.ua.origin))
        self.ua.emitEvent(event)
