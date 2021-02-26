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
from sippy.SipCSeq import SipCSeq
from sippy.SipCallId import SipCallId
from sippy.SipFrom import SipFrom
from sippy.SipTo import SipTo
from sippy.SipMaxForwards import SipMaxForwards
from sippy.SipVia import SipVia
from sippy.SipContentLength import SipContentLength
from sippy.SipContentType import SipContentType
from sippy.SipExpires import SipExpires
from sippy.SipRecordRoute import SipRecordRoute
from sippy.SipRoute import SipRoute
from sippy.SipContact import SipContact
from sippy.SipWWWAuthenticate import SipWWWAuthenticate
from sippy.SipAuthorization import SipAuthorization
from sippy.SipServer import SipServer
from sippy.SipUserAgent import SipUserAgent
from sippy.SipCiscoGUID import SipCiscoGUID
from sippy.SipAlso import SipAlso
from sippy.SipReferTo import SipReferTo
from sippy.SipCCDiversion import SipCCDiversion
from sippy.SipReferredBy import SipReferredBy
from sippy.SipProxyAuthenticate import SipProxyAuthenticate
from sippy.SipProxyAuthorization import SipProxyAuthorization
from sippy.SipReplaces import SipReplaces
from sippy.SipPAssertedIdentity import SipPAssertedIdentity
from sippy.SipReason import SipReason
from sippy.SipAllow import SipAllow
from sippy.SipSupported import SipSupported
from sippy.ESipHeaderCSV import ESipHeaderCSV
from sippy.SipRSeq import SipRSeq
from sippy.SipRAck import SipRAck
from sippy.SipWarning import SipWarning
from sippy.SipDiversion import SipDiversion
from sippy.SipPath import SipPath

_hf_types = (SipCSeq, SipCallId, SipFrom, SipTo, SipMaxForwards, SipVia, SipContentLength, \
             SipContentType, SipExpires, SipRecordRoute, SipRoute, SipContact, SipWWWAuthenticate, \
             SipAuthorization, SipServer, SipUserAgent, SipCiscoGUID, SipAlso, SipReferTo, \
             SipCCDiversion, SipReferredBy, SipProxyAuthenticate, SipProxyAuthorization, \
             SipReplaces, SipPAssertedIdentity, SipReason, SipAllow, SipSupported, SipRSeq, \
             SipRAck, SipWarning, SipDiversion, SipPath)

hf_types = {}
for hf_type in _hf_types:
    for hf_name in hf_type.hf_names:
        hf_types[hf_name] = hf_type

class SipHeader(object):
    name = None
    body = None

    def __init__(self, s = None, name = None, body = None, bodys = None, fixname = False):
        if s != None:
            name, bodys = [x.strip() for x in s.split(':', 1)]
        if name != None:
            self.name = name.lower()
        if body is None:
            try:
                try:
                    body = hf_types[self.name](bodys)
                except KeyError:
                    body = SipGenericHF(bodys, name)
            except ESipHeaderCSV as einst:
                einst.name = self.name
                raise einst
        self.body = body
        # If no name is provided use canonic name from the body-specific
        # class.
        if self.name == None or fixname:
            self.name = body.hf_names[0]

    def __str__(self):
        return str(self.body.getCanName(self.name)) + ': ' + str(self.body)

    def localStr(self, local_addr = None, compact = False):
        return str(self.body.getCanName(self.name, compact)) + ': ' + \
          self.body.localStr(local_addr)

    def getBody(self):
        if not self.body.parsed:
            self.body.parse()
        return self.body

    def getBCopy(self):
        return self.body.getCopy()

    def getCopy(self):
        cself = self.__class__(name = self.name, body = self.body.getCopy())
        return cself
