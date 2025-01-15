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

from sippy.Time.MonoTime import MonoTime
from sippy.SipHeader import SipHeader
from sippy.SipWarning import SipWarning

class CCEventGeneric(object):
    data = None
    name = None
    rtime = None
    origin = None
    reason_rfc3326 = None
    extra_headers = None
    seq = 1

    def __init__(self, data = None, rtime = None, origin = None):
        self.data = data
        if rtime is None:
            self.rtime = MonoTime()
        else:
            self.rtime = rtime
        self.seq = CCEventGeneric.seq
        CCEventGeneric.seq += 1
        self.origin = origin

    def getData(self):
        return self.data

    def getCopy(self):
        cself = self.__class__(self.data, self.rtime, self.origin)
        if self.extra_headers is not None:
            cself.extra_headers = tuple(x.getCopy() for x in self.extra_headers)
        if self.reason_rfc3326 is not None:
            cself.reason_rfc3326 = self.reason_rfc3326.getCopy()
        return cself

    def getExtraHeaders(self):
        extra_headers = []
        if self.extra_headers is not None:
            extra_headers.extend(self.extra_headers)
        if self.reason_rfc3326 is not None:
            extra_headers.append(SipHeader(body = self.reason_rfc3326))
        return tuple(extra_headers) if len(extra_headers) > 0 else None

    def __str__(self):
        return self.name

class CCEventTry(CCEventGeneric):
    name = 'CCEventTry'
    max_forwards = None

    def getCopy(self):
        cself = super().getCopy()
        cself.max_forwards = self.max_forwards
        return cself

    # Speacial method allowing tweaking internal parameters of the UAC
    # after everything has been setup but before INVITE goes out.
    def onUacSetupComplete(self, uac):
        pass

class CCEventRing(CCEventGeneric):
    name = 'CCEventRing'

class CCEventPreConnect(CCEventGeneric):
    name = 'CCEventPreConnect'

class CCEventConnect(CCEventGeneric):
    name = 'CCEventConnect'

class CCEventUpdate(CCEventGeneric):
    name = 'CCEventUpdate'
    max_forwards = None

    def getCopy(self):
        cself = super().getCopy()
        cself.max_forwards = self.max_forwards
        return cself

class CCEventInfo(CCEventGeneric):
    name = 'CCEventInfo'

class CCEventDisconnect(CCEventGeneric):
    name = 'CCEventDisconnect'

class CCEventFail(CCEventGeneric):
    name = 'CCEventFail'
    challenges = None
    warning = None

    def getCopy(self):
        cself = super().getCopy()
        if self.challenges is not None:
            cself.challenges = [x.getCopy() for x in self.challenges]
        if self.warning is not None:
            cself.warning = self.warning.getCopy()
        return cself

    def getExtraHeaders(self):
        extra_headers = []
        if (eh := super().getExtraHeaders()) is not None:
            extra_headers.extend(eh)
        if self.challenges is not None:
            extra_headers.extend(self.challenges)
        if self.warning is not None:
            extra_headers.append(self.warning)
        return tuple(extra_headers) if len(extra_headers) > 0 else None

    def setWarning(self, eistr):
        self.warning = SipHeader(body = SipWarning(text = eistr))

class CCEventRedirect(CCEventGeneric):
    name = 'CCEventRedirect'
