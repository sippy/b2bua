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

from functools import partial

from sippy.SipContact import SipContact
from sippy.UaStateGeneric import UaStateGeneric

class UasStateGeneric(UaStateGeneric):
    def _delayLocalSdpUpdate(self, event, body):
        if body is not None and self.ua.on_local_sdp_change is not None and body.needs_update:
            self.ua.on_local_sdp_change(body, partial(self.ua.delayed_local_sdp_update, event))
            return True
        return False

    def _recvEventRing(self, event, eh, contacts = None):
        scode = event.getData()
        if scode is None:
            code, reason, body = (180, 'Ringing', None)
        else:
            code, reason, body = scode
            if self._delayLocalSdpUpdate(event, body):
                return None
        self.ua.lSDP = body
        self.ua.sendUasResponse(code, reason, body, contacts, extra_headers = eh)
        return code

    def _getConnectData(self, event):
        code, reason, body = event.getData()
        if self._delayLocalSdpUpdate(event, body):
            return None
        self.ua.lSDP = body
        return (code, reason, body)

    def _recvEventRedirect(self, event, eh):
        scode = event.getData()
        contacts = None
        if scode is None:
            scode = (500, 'Failed', None, None)
        elif scode[3] is not None:
            contacts = tuple(SipContact(address = x) for x in scode[3])
        self.ua.sendUasResponse(scode[0], scode[1], scode[2], contacts, \
          extra_headers = eh)
        return scode

    def _sendFailResponse(self, event, eh):
        scode = event.getData()
        if scode is None:
            scode = (500, 'Failed')
        self.ua.sendUasResponse(scode[0], scode[1], extra_headers = eh)
        return scode

    def _cancelExpireTimer(self):
        if self.ua.expire_timer is not None:
            self.ua.expire_timer.cancel()
        self.ua.expire_timer = None
