# Copyright (c) 2023 Sippy Software, Inc. All rights reserved.
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

from sippy.SipHeader import SipHeader

class MultipartMixBody():
    parts = None
    boundary = None

    def __init__(self, body = None, ctype = None):
        if body is None:
            return
        sep = f'--{ctype.params["boundary"]}'
        bparts = body.split(sep)
        assert len(bparts) > 2
        assert len(bparts[0]) == 0
        assert bparts[-1].strip() == '--'
        parts = [p.lstrip() for p in bparts[1:-1]]
        self.parts = []
        for sect in parts:
            ct, sect = sect.split('\r\n', 1)
            ct = SipHeader(ct).getBody()
            sect = MsgBody(sect, ct)
            self.parts.append(sect)
        self.boundary = ctype.params["boundary"]

    def __str__(self):
        bnd = f'--{self.boundary}\r\n'
        parts = [f'{bnd}Content-Type: {p.mtype}\r\n{p}' for p in self.parts]
        s = ''.join(parts)
        s += f'{bnd[:-2]}--\r\n'
        return s

    def localStr(self, local_addr = None):
        bnd = f'--{self.boundary}\r\n'
        parts = [f'{bnd}Content-Type: {p.mtype}\r\n{p.localStr(local_addr)}'
                 for p in self.parts]
        s = ''.join(parts)
        s += f'{bnd[:-2]}--\r\n'
        return s

    def getCopy(self):
        cself = MultipartMixBody()
        cself.parts = [p.getCopy() for p in self.parts]
        cself.boundary = self.boundary
        return cself

if not 'MsgBody' in globals():
    from sippy.MsgBody import MsgBody
