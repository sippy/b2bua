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

from sippy.SipGenericHF import SipGenericHF

class SipContentType(SipGenericHF):
    hf_names = ('content-type', 'c')
    name = None
    params = None

    def __init__(self, body):
        SipGenericHF.__init__(self, body)

    def parse(self):
        parts = self.body.split(';')
        self.name = parts.pop(0)
        params = []
        for part in parts:
            param = part.split('=', 1)
            params.append(param)
        self.params = dict(params)
        self.parsed = True

    def getCanName(self, name, compact = False):
        if compact:
            return 'c'
        return 'Content-Type'

    def getCopy(self):
        if not self.parsed:
            return SipContentType(self.body)
        copy = SipContentType(None)
        copy.name = self.name
        copy.params = self.params.copy()
        copy.parsed = True
        return copy

    def __str__(self):
        if not self.parsed:
            return super().__str__()
        s = [self.name,]
        s += [f'{k}={v}' for k, v in self.params.items()]
        return ';'.join(s)

if __name__ == '__main__':
    t = 'multipart/mixed;boundary=OSS-unique-boundary-42'
    ct1 = SipContentType(t)
    ct1.parse()
    assert f'{ct1}' == t
    assert ct1.name == 'multipart/mixed'
    assert ct1.params['boundary'] == 'OSS-unique-boundary-42'
    ct2 = ct1.getCopy()
    assert f'{ct2}' == t
    ct1.params['some'] = 'value'
    assert f'{ct1}' == t + ';some=value'
    assert f'{ct2}' == t
