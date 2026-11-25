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

from sippy.SipHeader import SipHeader
from sippy.SipContentLength import SipContentLength
from sippy.SipContentType import SipContentType
from sippy.MsgBody import MsgBody
from sippy.ESipHeaderCSV import ESipHeaderCSV
from sippy.ESipHeaderIgnore import ESipHeaderIgnore
from sippy.Exceptions.SipParseError import SipParseError
from sippy.Network_server import Remote_address


class WireHeaderError(SipParseError):
    """The header text is not valid UTF-8."""


class SipMsg(object):
    headers = None
    body = None
    startline = None
    target = None
    source = None
    nated = False
    rtime = None

    @staticmethod
    def split_wire_datagram(data_in):
        """Return decoded headers and the exact body bytes from a UDP datagram.

        Search for CRLFCRLF first; only try the legacy CR/CR and LF/LF
        separators when it is absent. An empty body is b''; None means no
        separator was found and the entire datagram was decoded as text.
        Raise WireHeaderError if the header text is not valid UTF-8.
        """
        boff = data_in.find(b'\r\n\r\n')
        separator_len = 4
        if boff == -1:
            separator_len = 2
            boff = data_in.find(b'\r\r')
            if boff == -1:
                boff = data_in.find(b'\n\n')
        if boff == -1:
            # No header terminator at all: historical behavior -- whole datagram
            # strict decode (a datagram that does not decode is malformed).
            try:
                return (data_in.decode(), None)
            except UnicodeDecodeError:
                raise WireHeaderError(
                    'no header terminator and datagram is not strict UTF-8')
        try:
            headers = data_in[:boff].decode()
        except UnicodeDecodeError:
            raise WireHeaderError('header part is not strict UTF-8')
        return headers, data_in[boff + separator_len:]

    def __init__(self, buf = None):
        self.headers = []
        self.__body_wire_octets = None
        self.__mbody = None
        if buf is None:
            return
        if isinstance(buf, bytes):
            buf, self.__body_wire_octets = self.split_wire_datagram(buf)
        else:
            for bdel in ('\r\n\r\n', '\r\r', '\n\n'):
                boff = buf.find(bdel)
                if boff != -1:
                    self.__mbody = buf[boff + len(bdel):] or None
                    buf = buf[:boff]
                    break
        # Split message into lines and put aside start line
        lines = buf.splitlines()
        self.setSL(lines[0])
        i = 2
        while i < len(lines):
            if len(lines[i]) == 0 or lines[i][0] in (' ', '\t'):
                lines[i - 1] += ' ' + lines[i].strip()
                del lines[i]
            else:
                i += 1
        # Parse headers
        self.__content_type = None
        self.__content_length = None
        header_names = []
        for line in lines[1:]:
            try:
                header = SipHeader(line, fixname = True)
                if header.name == 'content-type':
                    self.__content_type = header
                elif header.name == 'content-length':
                    self.__content_length = header
                else:
                    self.headers.append(header)
                    header_names.append(header.name)
            except ESipHeaderCSV as einst:
                for body in einst.bodys:
                    header = SipHeader(name = einst.name, bodys = body, fixname = True)
                    if header.name == 'content-type':
                        self.__content_type = header
                    elif header.name == 'content-length':
                        self.__content_length = header
                    else:
                        self.headers.append(header)
                        header_names.append(header.name)
            except ESipHeaderIgnore:
                continue
        if 'via' not in header_names:
            raise Exception('Via HF is missed')
        if 'to' not in header_names:
            raise Exception('To HF is missed')
        if 'from' not in header_names:
            raise Exception('From HF is missed')
        if 'cseq' not in header_names:
            raise Exception('CSeq HF is missed')

    def init_body(self):
        # Byte-domain source for the Content-Length policy.
        # When the transport supplies the exact entity-body octets (UDP
        # byte path), the policy runs over those octets before body
        # classification. The string path is unchanged.
        raw = self.__body_wire_octets is not None
        if raw:
            mbytes = self.__body_wire_octets
        elif self.__mbody == None:
            mbytes = b''
        else:
            mbytes = self.__mbody.encode('utf-8')
        mblen = len(mbytes)
        if self.__content_length != None:
            blen = self.__content_length.getBody().number
            # Content-Length is a byte count (RFC 3261).
            if blen == 0:
                # CL: 0 -> NO body, whatever trailing octets arrived
                # (historical semantics, preserved consistently on the
                # byte path: the raw carrier and the final octets are
                # reset together).
                self.__mbody = None
                mbytes = b''
                mblen = 0
            elif mblen == 0:
                # XXX: Should generate 400 Bad Request if such condition
                # happens with request
                raise SipParseError('Missed SIP body, %d bytes expected' % blen)
            elif blen > mblen:
                if blen - mblen < 7 and mblen > 7 and mbytes[-4:] == b'\r\n\r\n':
                    # XXX: we should not really be doing this, but it appears to be
                    # a common off-by-one/two/.../six problem with SDPs generated by
                    # the consumer-grade devices.
                    print('Truncated SIP body, %d bytes expected, %d received, fixing...' % (blen, mblen))
                    blen = mblen
                elif blen - mblen == 2 and mbytes[-2:] == b'\r\n':
                    # Missed last 2 \r\n is another common problem.
                    print('Truncated SIP body, %d bytes expected, %d received, fixing...' % (blen, mblen))
                    mbytes += b'\r\n'
                elif blen - mblen == 1 and mbytes[-3:] == b'\r\n\n':
                    # Another possible mishap
                    print('Truncated SIP body, %d bytes expected, %d received, fixing...' % (blen, mblen))
                    mbytes = mbytes[:-3] + b'\r\n\r\n'
                elif blen - mblen == 1 and mbytes[-2:] == b'\r\n':
                    # One more
                    print('Truncated SIP body, %d bytes expected, %d received, fixing...' % (blen, mblen))
                    mbytes += b'\r\n'
                else:
                    # XXX: Should generate 400 Bad Request if such condition
                    # happens with request
                    raise SipParseError('Truncated SIP body, %d bytes expected, %d received' % (blen, mblen))
                # The repairs only touch the ASCII CRLF tail.
                # Byte path: the repaired octets are retained VERBATIM
                # (no decode, no text projection) so that what is
                # retained and what will be re-sent are the same octets.
                # Text path: re-derive the repaired text (classic
                # MsgBody semantics; the repair keeps the body valid
                # UTF-8, so the UTF-8 re-encoding is byte-identical).
                if raw:
                    self.__body_wire_octets = mbytes
                else:
                    self.__mbody = mbytes.decode('utf-8')
                mblen = len(mbytes)
            elif blen < mblen:
                # Truncate in the byte domain.
                mbytes = mbytes[:blen]
                if raw:
                    # Base truncation policy preserved: if the RECEIVED
                    # body was valid UTF-8 and the declared CL cut would
                    # split a character, the declared length is simply
                    # wrong -- reject (400), never a partial char.  An
                    # already-opaque (not valid UTF-8) body has no
                    # character boundary: the (fewer) final octets are
                    # kept losslessly.
                    try:
                        self.__body_wire_octets.decode('utf-8')
                        orig_utf8 = True
                    except UnicodeDecodeError:
                        orig_utf8 = False
                    if orig_utf8:
                        try:
                            mbytes.decode('utf-8')
                        except UnicodeDecodeError:
                            raise SipParseError('Truncated SIP body, %d bytes expected, %d received' % (blen, mblen))
                    # The (fewer) final octets are retained VERBATIM
                    # (no decode, no text projection).
                    self.__body_wire_octets = mbytes
                else:
                    # If the cut would split a UTF-8 character the
                    # declared length is simply wrong -- reject (400),
                    # never repair.
                    try:
                        self.__mbody = mbytes.decode('utf-8')
                    except UnicodeDecodeError:
                        raise SipParseError('Truncated SIP body, %d bytes expected, %d received' % (blen, mblen))
                mblen = len(mbytes)
        if mbytes:
            ctype = (self.__content_type.getBody()
                     if self.__content_type is not None else None)
            self.body = MsgBody(mbytes, ctype)

    def __str__(self):
        s = self.getSL() + '\r\n'
        for header in self.headers:
            s += str(header) + '\r\n'
        body = self.body
        if body is not None:
            mbody = str(body)
            s += 'Content-Type: %s\r\n' % body.mtype
            # Even the text view reports the byte count of the wire body.
            s += 'Content-Length: %d\r\n\r\n' % len(body.localStr(as_bytes = True))
            s += mbody
        else:
            s += 'Content-Length: 0\r\n\r\n'
        return s

    def localStr(self, local_addr = None, compact = False, *, as_bytes = False):
        """Render as text by default, or as exact transport bytes."""
        s = self.getSL(local_addr) + '\r\n'
        for header in self.headers:
            s += header.localStr(local_addr, compact) + '\r\n'
        body = self.body
        body_bytes = b''
        if body is not None:
            body_bytes = body.localStr(local_addr, as_bytes = True)
            ctype = 'c' if compact else 'Content-Type'
            s += '%s: %s\r\n' % (ctype, body.mtype)
        clen = 'l' if compact else 'Content-Length'
        s += '%s: %d\r\n\r\n' % (clen, len(body_bytes))
        if as_bytes:
            return s.encode('utf-8') + body_bytes
        if body is not None:
            s += body.localStr(local_addr)
        return s

    def setSL(self, startline):
        self.startline = startline

    def getSL(self, local_addr = None):
        return self.startline

    def getHFs(self, name):
        return [x for x in self.headers if x.name == name]

    def countHFs(self, name):
        return len([x for x in self.headers if x.name == name])

    def delHFs(self, name):
        self.headers = [x for x in self.headers if x.name != name]

    def getHF(self, name):
        return [x for x in self.headers if x.name == name][0]

    def getHFBodys(self, name):
        return [x.getBody() for x in self.headers if x.name == name]

    def getHFBody(self, name, idx = 0):
        return [x for x in self.headers if x.name == name][idx].getBody()

    def getHFBCopys(self, name):
        return [x.getBCopy() for x in self.headers if x.name == name]

    def getHFBCopy(self, name, idx = 0):
        return [x for x in self.headers if x.name == name][idx].getBCopy()

    def replaceHeader(self, oheader, nheader):
        self.headers[self.headers.index(oheader)] = nheader

    def removeHeader(self, header):
        self.headers.remove(header)

    def appendHeader(self, header):
        self.headers.append(header)

    def appendHeaders(self, headers):
        self.headers.extend(headers)

    def insertHeaderAfter(self, iheader, header):
        self.headers.insert(self.headers.index(iheader) + 1, header)

    def insertHeaderBefore(self, iheader, header):
        self.headers.insert(self.headers.index(iheader), header)

    def getBody(self):
        return self.body

    def setBody(self, body):
        self.body = body

    def getTarget(self):
        return self.target

    def setTarget(self, address):
        self.target = address

    def getSource(self, ver=1):
        if ver == 1:
            return self.source[0]
        return self.source

    def setSource(self, ra:Remote_address):
        self.source = (ra.address, ra.transport)

    def getTId(self, wCSM = False, wBRN = False, wTTG = False):
        headers_dict = dict([(x.name, x) for x in self.headers if x.name in ('cseq', 'call-id', 'from')])
        cseq, method = headers_dict['cseq'].getBody().getCSeq()
        rval = [str(headers_dict['call-id'].getBody()), headers_dict['from'].getBody().getTag(), cseq]
        if wCSM:
            rval.append(method)
        if wBRN:
            rval.append(self.getHFBody('via').getBranch())
        if wTTG:
            rval.append(self.getHFBody('to').getTag())
        return tuple(rval)

    def getTIds(self):
        headers_dict = dict([(x.name, x) for x in self.headers if x.name in ('cseq', 'call-id', 'from')])
        call_id = str(headers_dict['call-id'].getBody())
        ftag = headers_dict['from'].getBody().getTag()
        cseq, method = headers_dict['cseq'].getBody().getCSeq()
        return tuple([(call_id, ftag, cseq, method, via.getBranch()) for via in self.getHFBodys('via')])

    def getCopy(self):
        cself = self.__class__()
        for header in self.headers:
            cself.appendHeader(header.getCopy())
        if self.body is not None:
            cself.body = self.body.getCopy()
        cself.startline = self.startline
        cself.target = self.target
        cself.source = self.source
        cself.nated = self.nated
        cself.rtime = self.rtime
        return cself
