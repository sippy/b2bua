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

from sippy.CCEvents import CCEventDisconnect

class UaStateGeneric(object):
    sname = 'Generic'
    ua = None
    connected = False
    dead = False
    recv_event_handlers = {}
    recv_request_handlers = {}

    def __init__(self, ua):
        self.ua = ua

    def recvRequest(self, req):
        handler = self.recv_request_handlers.get(req.getMethod())
        if handler is not None:
            return handler(self, req)
        return None

    def recvResponse(self, resp, tr):
        return None

    def recvEvent(self, event):
        handler = self.recv_event_handlers.get(event.__class__)
        if handler is not None:
            return handler(self, event, event.getExtraHeaders())
        return None

    def _getRequestAlso(self, req):
        if req.countHFs('also') > 0:
            return req.getHFBody('also').getCopy()
        return None

    def _disconnectFromRequest(self, req, also = None, copy_reason = True):
        event = CCEventDisconnect(also, rtime = req.rtime, origin = self.ua.origin)
        if copy_reason:
            try:
                event.reason_rfc3326 = req.getHFBody('reason')
            except:
                pass
        self.ua.equeue.append(event)
        self.ua.disconnect_ts = req.rtime
        return (self.ua.UaStateDisconnected, self.ua.disc_cbs, req.rtime, self.ua.origin)

    def cancel(self, rtime, req):
        return None

    def onStateChange(self, newstate):
        pass

    def __str__(self):
        return self.sname
