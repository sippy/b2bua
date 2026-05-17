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
from sippy.Time.Timeout import TimeoutAbsMono

class UasStateTrying(UasStateProgressing):
    sname = 'Trying(UAS)'

    def _cancelNoProgressTimer(self):
        if self.ua.no_progress_timer is not None:
            self.ua.no_progress_timer.cancel()
            self.ua.no_progress_timer = None

    def _recvEventRing(self, event, eh):
        scode = event.getData()
        if scode is not None and scode[0] == 100:
            return None
        code = super()._recvEventRing(event, eh)
        if code is None:
            return None
        if self.ua.no_progress_timer is not None:
            self._cancelNoProgressTimer()
            if self.ua.expire_time is not None:
                self.ua.expire_timer = TimeoutAbsMono(self.ua.expires, self.ua.expire_mtime)
        if self.ua.p1xx_ts is None:
            self.ua.p1xx_ts = event.rtime
        return (self.ua.UasStateRinging, self.ua.ring_cbs, event.rtime, event.origin, code)

    def _recvEventConnect(self, event, eh):
        result = super()._recvEventConnect(event, eh)
        if result is not None:
            self._cancelNoProgressTimer()
        return result

    def _recvEventPreConnect(self, event, eh):
        result = super()._recvEventPreConnect(event, eh)
        if result is not None:
            self._cancelNoProgressTimer()
        return result

    def _recvEventRedirect(self, event, eh):
        result = super()._recvEventRedirect(event, eh)
        self._cancelNoProgressTimer()
        return result

    def _recvEventFail(self, event, eh):
        result = super()._recvEventFail(event, eh)
        self._cancelNoProgressTimer()
        return result

    def _recvEventDisconnect(self, event, eh):
        result = super()._recvEventDisconnect(event, eh)
        self._cancelNoProgressTimer()
        return result

    recv_event_handlers = {
      CCEventRing: _recvEventRing,
      CCEventConnect: _recvEventConnect,
      CCEventPreConnect: _recvEventPreConnect,
      CCEventRedirect: _recvEventRedirect,
      CCEventFail: _recvEventFail,
      CCEventDisconnect: _recvEventDisconnect,
    }
