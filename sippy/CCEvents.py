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

class CCEventGeneric(object):
    data = None
    name = None
    rtime = None
    origin = None
    reason = None
    extra_headers = None
    seq = 1

    def __init__(self, data = None, rtime = None, origin = None):
        self.data = data
        if rtime == None:
            self.rtime = MonoTime()
        else:
            self.rtime = rtime
        self.seq = CCEventGeneric.seq
        CCEventGeneric.seq += 1
        self.origin = origin

    def getData(self):
        return self.data

    def getBody(self):
        return None

    def getCopy(self):
        cself = self.__class__(self.data, self.rtime, self.origin)
        if self.reason != None:
            cself.reason = self.reason.getCopy()
        if self.extra_headers != None:
            cself.extra_headers = tuple([x.getCopy() for x in self.extra_headers])
        return cself

    def __str__(self):
        return self.name

class CCEventTry(CCEventGeneric):
    name = 'CCEventTry'
    max_forwards = None

    def getCopy(self):
        cself = CCEventGeneric.getCopy(self)
        cself.max_forwards = self.max_forwards
        return cself

    # Speacial method allowing tweaking internal parameters of the UAC
    # after everything has been setup but before INVITE goes out.
    def onUacSetupComplete(self, uac):
        pass

    def getBody(self):
        if self.data != None:
            return self.data[4]
        return None

class CCEventRing(CCEventGeneric):
    name = 'CCEventRing'

    def getBody(self):
        if self.data != None:
            return self.data[2]
        return None

class CCEventPreConnect(CCEventGeneric):
    name = 'CCEventPreConnect'

    def getBody(self):
        if self.data != None:
            return self.data[2]
        return None

class CCEventConnect(CCEventGeneric):
    name = 'CCEventConnect'

    def getBody(self):
        if self.data != None:
            return self.data[2]
        return None

class CCEventUpdate(CCEventGeneric):
    name = 'CCEventUpdate'
    max_forwards = None

    def getCopy(self):
        cself = CCEventGeneric.getCopy(self)
        cself.max_forwards = self.max_forwards
        return cself

    def getBody(self):
        return self.data

class CCEventInfo(CCEventGeneric):
    name = 'CCEventInfo'

    def getBody(self):
        return self.data

class CCEventDisconnect(CCEventGeneric):
    name = 'CCEventDisconnect'

    def getBody(self):
        return None

from sippy.SipHeader import SipHeader
from sippy.SipWarning import SipWarning

class CCEventFail(CCEventGeneric):
    name = 'CCEventFail'
    challenges = None
    warning = None

    def getCopy(self):
        cself = CCEventGeneric.getCopy(self)
        if self.challenges != None:
            cself.challenges = [x.getCopy() for x in self.challenges]
        return cself

    def setWarning(self, eistr):
        self.warning = SipHeader(body = SipWarning(text = eistr))

    def getBody(self):
        return None

class CCEventRedirect(CCEventGeneric):
    name = 'CCEventRedirect'

    def getBody(self):
        return None
