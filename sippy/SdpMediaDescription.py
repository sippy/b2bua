# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2022 Sippy Software, Inc. All rights reserved.
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

from sippy.SdpConnecton import SdpConnecton
from sippy.SdpMedia import SdpMedia
from sippy.SdpGeneric import SdpGeneric

f_types = {'m':SdpMedia, 'i':SdpGeneric, 'c':SdpConnecton, 'b':SdpGeneric, \
  'k':SdpGeneric}

class a_header(object):
    name = None
    value = None

    def __init__(self, s):
        if isinstance(s, a_header):
            self.name = s.name
            self.value = s.value
            return
        parts = s.split(':', 1)
        self.name = parts[0]
        if len(parts) > 1:
            self.value = parts[1]

    def __str__(self):
        if self.value is None:
            return self.name
        return '%s:%s' % (self.name, self.value)

    def getCopy(self):
        return a_header(self)

class SdpMediaDescription(object):
    m_header = None
    i_header = None
    c_header = None
    b_header = None
    k_header = None
    a_headers = None
    all_headers = ('m', 'i', 'c', 'b', 'k')
    needs_update = True

    def __init__(self, cself = None):
        if cself != None:
            for header_name in [x + '_header' for x in self.all_headers]:
                try:
                    setattr(self, header_name, getattr(cself, header_name).getCopy())
                except AttributeError:
                    pass
            self.a_headers = [x.getCopy() for x in cself.a_headers]
            return
        self.a_headers = []

    def __str__(self):
        s = ''
        for name in self.all_headers:
            header = getattr(self, name + '_header')
            if header != None:
                s += '%s=%s\r\n' % (name, str(header))
        for header in self.a_headers:
            s += 'a=%s\r\n' % str(header)
        return s

    def localStr(self, local_addr = None, noC = False):
        s = ''
        for name in self.all_headers:
            if noC and name == 'c':
                continue
            header = getattr(self, name + '_header')
            if header != None:
                s += '%s=%s\r\n' % (name, header.localStr(local_addr))
        for header in self.a_headers:
            s += 'a=%s\r\n' % str(header)
        return s

    def __iadd__(self, other):
        self.addHeader(*other.strip().split('=', 1))
        return self

    def getCopy(self):
        return SdpMediaDescription(cself = self)

    def addHeader(self, name, header):
        if name == 'a':
            self.a_headers.append(a_header(header))
        else:
            setattr(self, name + '_header', f_types[name](header))

    def insertHeader(self, indx, name, header):
        assert(name == 'a')
        self.a_headers.insert(indx, a_header(header))

    def getPTbyName(self, name):
        for ah in self.a_headers:
            if ah.name == 'rtpmap' and ah.value.split(' ', 1)[1] == name:
                return int(ah.value.split(' ', 1)[0])
        return None

    def optimize_a(self):
        for ah in [x for x in self.a_headers if x.name in ('rtpmap', 'fmtp') and \
          x.value is not None]:
            try:
                pt = int(ah.value.split(' ', 1)[0])
            except ValueError:
                continue
            if pt in self.m_header.formats:
                continue
            self.a_headers.remove(ah)

    def isOnHold(self):
        if self.c_header.atype == 'IP4' and self.c_header.addr == '0.0.0.0':
            return True
        if self.c_header.atype == 'IP6' and self.c_header.addr == '::':
            return True
        if len([1 for x in self.a_headers if x.value is None and \
          x.name in ('sendonly', 'inactive')]) > 0:
            return True
        return False
