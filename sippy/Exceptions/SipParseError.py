# Copyright (c) 20012-2023 Sippy Software, Inc. All rights reserved.
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

from sippy.SipReason import SipReason
from sippy.SipHeader import SipHeader

class SipParseError(Exception):
    sip_response = None
    arg = None

    def __init__(self, arg, sip_response = None):
        super().__init__()
        self.arg = arg
        self.sip_response = sip_response

    def __str__(self):
        return str(self.arg)

    def getResponse(self, req=None):
        return self.sip_response

class SdpParseError(SipParseError):
    code = 488
    msg = 'Not Acceptable Here'
    def getResponse(self, req):
        if self.sip_response is not None:
            return self.sip_response
        resp = req.genResponse(self.code, self.msg)
        if (reason:=self.getReason()) is not None:
            rsh = SipHeader(body = reason)
            resp.appendHeader(rsh)
        return resp

    def getReason(self):
        if self.arg is not None and len(self.arg) > 0:
            return SipReason(protocol='SIP', cause=self.code,
                             reason=self.arg)
        return None
