# Copyright (c) 2024 Sippy Software, Inc. All rights reserved.
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

import sys

from sippy.SipRequest import SipRequest
from sippy.CCEvents import CCEventTry

class HDR2Xattrs():
    # Source: https://github.com/sippy/b2bua/pull/38
    # Author: @twmobius
    hdr_name:str
    def __init__(self, hdr_name:str):
        self.hdr_name = hdr_name

    def __call__(self, cc:'CallController', req:SipRequest):
        hfs = req.getHFs(self.hdr_name)

        if len(hfs) == 0:
            return

        extra_attributes = []

        for header in hfs:
            kvPairs = header.body.body.split(';')
            for pair in kvPairs:
                [key, _, value] = pair.partition("=")
                if value != '':
                    extra_attributes.append((key, value))
        if len(extra_attributes) == 0:
            return
        if cc.extra_attributes is None:
            cc.extra_attributes = extra_attributes
        else:
            cc.extra_attributes.extend(extra_attributes)

class VAL2Xattrs():
    # Source: https://github.com/sippy/b2bua/pull/39
    # Author: @twmobius
    doO: bool = True
    doA: bool = True
    radius_parameters: list
    def __init__(self, v:str):
        radius_parameters = []
        pairs = v.split(',')
        for pair in pairs:
            [key, _, value] = pair.partition("=")
            if value == '': raise ValueError(f'{v}: comma-separated list of key=value pairs is expected')
            radius_parameters.append((key, value))
        self.radius_parameters = radius_parameters

    def __call__(self, cc:'CallController', _:CCEventTry):
        if self.doO and cc.acctO is not None:
            cc.acctO.addAttributes(self.radius_parameters)
        if self.doA and cc.acctA is not None:
            cc.acctA.addAttributes(self.radius_parameters)

class Nop():
    def __init__(self, v:str): pass
    def __call__(self, *a, **kwa): pass

class VAL2XattrsA(VAL2Xattrs): doO = False
class VAL2XattrsO(VAL2Xattrs): doA = False

def getTransProc(value:str):
    rparts = value.split('[', 1)
    if not len(rparts) == 2 or not value.endswith(']'):
        raise ValueError(f'getTransProc: `{value}` should be in the format `function[argument]`')
    fname = rparts[0]
    bts = sys.modules[__name__]
    fclass = getattr(bts, fname)
    farg = rparts[1][:-1]
    return fclass(farg)

if __name__ == '__main__':
    for t in ('HDR2Xattrs[X-foo-hdr]', 'VAL2Xattrs[foo=bar,baz=xxx]', 'VAL2XattrsA[foo=bar,baz=xxx]', 'VAL2XattrsO[foo=bar,baz=xxx]'):
        p = getTransProc(t)
