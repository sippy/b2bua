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

from sippy.SipRequest import SipRequest

class HDR2Xattrs():
    # Source: https://github.com/sippy/b2bua/pull/38
    # Author: @twmobius
    hdr_name:str
    def __init__(self, hdr_name:str):
        self.hdr_name = hdr_name

    def __call__(req:SipRequest, cc:'CallController'):
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
