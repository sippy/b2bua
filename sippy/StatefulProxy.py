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

from sippy.SipVia import SipVia
from sippy.SipHeader import SipHeader

class StatefulProxy:
    global_config = None
    destination = None

    def __init__(self, global_config, destination):
        print(destination)
        self.global_config = global_config
        self.destination = (destination, 'udp')

    def recvRequest(self, req):
        try:
            max_forwards = req.getHFBody('max-forwards')
            mfval = max_forwards.incNum(incr=-1)
            if mfval <= 0:
                return (req.genResponse(483, 'Too Many Hops'), None, None)
        except IndexError:
            req.appendHeader(SipHeader(name = 'max-forwards'))
        via0 = SipVia()
        via0.genBranch()
        via1 = req.getHF('via')
        if req.getMethod() == 'REGISTER':
            self.insertPath(req)
        req.insertHeaderBefore(via1, SipHeader(name = 'via', body = via0))
        req.setTarget(self.destination)
        print(req)
        self.global_config['_sip_tm'].newTransaction(req, self.recvResponse)
        return (None, None, None)

    def recvResponse(self, resp):
        resp.removeHeader(resp.getHF('via'))
        self.global_config['_sip_tm'].sendResponse(resp)

    def insertPath(self, req):
        try:
            supported = req.getHFBody('supported')
        except IndexError: pass
        else:
            if 'path' in supported.caps:
                mypath = SipHeader(name = 'path')
                if req.countHFs('path') == 0:
                    req.appendHeader(mypath)
                else:
                    path1 = req.getHF('path')
                    req.insertHeaderBefore(path1, mypath)
