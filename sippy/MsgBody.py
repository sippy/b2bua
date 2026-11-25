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

DEFAULT_CTYPE = SipContentType('application/sdp')
DEFAULT_CTYPE.parse()

OCTET_STREAM_CTYPE = SipContentType('application/octet-stream')
OCTET_STREAM_CTYPE.parse()


class RawBody:
    """Parsed representation of an opaque MIME body."""

    def __init__(self, content):
        self.content = content

    def __str__(self):
        return self.localStr()

    def localStr(self, local_addr = None, *, as_bytes = False):
        return self.content if as_bytes else self.content.decode('utf-8')

    def getCopy(self):
        return RawBody(self.content)


class MsgBody:
    """A MIME body: wire bytes until explicitly parsed."""

    content = None
    mtype = None
    parsed = False
    needs_update = True

    def __init__(self, content = None, mtype = DEFAULT_CTYPE, cself = None):
        if cself is not None:
            self.content = (cself.content if isinstance(cself.content, bytes)
                            else cself.content.getCopy())
            self.mtype = cself.mtype.getCopy()
            self.parsed = cself.parsed
        elif content is not None:
            self.content = content.encode('utf-8') if isinstance(content, str) else content
            self.mtype = DEFAULT_CTYPE if mtype is None else mtype
            self.parsed = not isinstance(self.content, bytes)
            if mtype is None and not self.parsed:
                # Keep the SDP default for undeclared UTF-8 bodies only.
                try:
                    self.content.decode('utf-8')
                except UnicodeDecodeError:
                    self.mtype = OCTET_STREAM_CTYPE

    def parse(self):
        if self.parsed or self.content is None:
            return
        parser = self.b_types.get(self.getType(), RawBody)
        if parser is RawBody:
            self.content = RawBody(self.content)
        else:
            self.content = parser(self.content.decode('utf-8'), ctype=self.mtype)
        self.parsed = True

    def __str__(self):
        return self.localStr() if isinstance(self.content, bytes) else str(self.content)

    def localStr(self, local_addr = None, *, as_bytes = False):
        """Render exact wire bytes or a strict UTF-8 text view."""
        if isinstance(self.content, bytes):
            return self.content if as_bytes else self.content.decode('utf-8')
        if isinstance(self.content, (RawBody, MultipartMixBody)):
            return self.content.localStr(local_addr, as_bytes=as_bytes)
        text = self.content.localStr(local_addr)
        return text.encode('utf-8') if as_bytes else text

    def getType(self):
        return self.mtype.name.lower()

    def getCopy(self):
        if self.content is None:
            return MsgBody()
        return MsgBody(cself = self)


from sippy.MultipartMixBody import MultipartMixBody

MsgBody.b_types = {'application/sdp': SdpBody,
                   'multipart/mixed': MultipartMixBody,
                   'application/octet-stream': RawBody}
