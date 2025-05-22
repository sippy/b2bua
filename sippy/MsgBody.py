#
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

from sippy.SdpBody import SdpBody
from sippy.SipContentType import SipContentType

try:
    # Python < 3
    str_types = (str, unicode)
except NameError:
    str_types = (str,)

DEFAULT_CTYPE = SipContentType('application/sdp')
DEFAULT_CTYPE.parse()

class MsgBody(object):
    content = None
    mtype = None
    needs_update = True
    parsed = False

    def __init__(self, content = None, mtype = DEFAULT_CTYPE, cself = None):
        if content != None:
            self.mtype = mtype
            self.content = content
            self.parsed = type(content) not in str_types
            return
        if cself is not None:
            if type(cself.content) in str_types:
                self.content = cself.content
            else:
                self.content = cself.content.getCopy()
            self.mtype = cself.mtype.getCopy()
            self.parsed = True

    def parse(self):
        b_types = {'application/sdp':SdpBody,
                   'multipart/mixed':MultipartMixBody}
        if not self.parsed:
            mtype = self.getType()
            if mtype in b_types:
                self.content = b_types[mtype](self.content, ctype=self.mtype)
            self.parsed = True

    def __str__(self):
        return str(self.content)

    def localStr(self, local_addr = None):
        if type(self.content) in str_types:
            return self.content
        return self.content.localStr(local_addr)

    def getType(self):
        return self.mtype.name.lower()

    def getCopy(self):
        if not self.parsed:
            return MsgBody(self.content)
        return MsgBody(cself = self)

if 'MultipartMixBody' not in globals():
    from sippy.MultipartMixBody import MultipartMixBody
