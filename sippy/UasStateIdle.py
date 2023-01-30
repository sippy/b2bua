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

from sippy.Time.Timeout import TimeoutAbsMono
from sippy.UaStateGeneric import UaStateGeneric
from sippy.CCEvents import CCEventTry
from sippy.SipContact import SipContact
from sippy.SipFrom import SipFrom
from sippy.SipTo import SipTo

class UasStateIdle(UaStateGeneric):
    sname = 'Idle(UAS)'

    def recvRequest(self, req):
        if req.getMethod() != 'INVITE':
            #print 'wrong request %s in the Trying state' % req.getMethod()
            return None
        self.ua.origin = 'caller'
        #print('INVITE received in the Idle state, going to the Trying state')
        self.ua.uasResp = req.genResponse(100, 'Trying', server = self.ua.local_ua)
        self.ua.lCSeq = 100 # XXX: 100 for debugging so that incorrect CSeq generation will be easily spotted
        if self.ua.lContact == None:
            self.ua.lContact = SipContact()
        self.ua.rTarget = req.getHFBody('contact').getUrl().getCopy()
        self.ua.updateRouting(self.ua.uasResp, update_rtarget = False)
        self.ua.rAddr0 = self.ua.rAddr
        self.ua.global_config['_sip_tm'].sendResponse(self.ua.uasResp, lossemul = self.ua.uas_lossemul)
        self.ua.uasResp.getHFBody('to').setTag(self.ua.lTag)
        self.ua.lUri = SipFrom(address = self.ua.uasResp.getHFBody('to').getUri())
        self.ua.rUri = SipTo(address = self.ua.uasResp.getHFBody('from').getUri())
        self.ua.cId = self.ua.uasResp.getHFBody('call-id')
        self.ua.global_config['_sip_tm'].regConsumer(self.ua, str(self.ua.cId), compact = self.ua.compact_sip)
        if req.countHFs('authorization') == 0:
            auth = None
        else:
            auth = req.getHFBody('authorization').getCopy()
        body = req.getBody()
        self.ua.branch = req.getHFBody('via').getBranch()
        event = CCEventTry((self.ua.cId, self.ua.rUri.getUrl().username, req.getRURI().username, body, auth, \
          self.ua.rUri.getUri().name), rtime = req.rtime, origin = self.ua.origin)
        try:
            event.reason = req.getHFBody('reason')
        except:
            pass
        try:
            event.max_forwards = req.getHFBody('max-forwards').getNum()
        except:
            pass
        if self.ua.expire_time != None:
            self.ua.expire_mtime = event.rtime.getOffsetCopy(self.ua.expire_time)
        if self.ua.no_progress_time != None:
            self.ua.no_progress_mtime = event.rtime.getOffsetCopy(self.ua.no_progress_time)
            if self.ua.expire_time != None and self.ua.no_progress_time >= self.ua.expire_time:
                self.ua.no_progress_time = None
        if self.ua.no_progress_time != None:
            self.ua.no_progress_timer = TimeoutAbsMono(self.ua.no_progress_expires, self.ua.no_progress_mtime)
        elif self.ua.expire_time != None:
            self.ua.expire_timer = TimeoutAbsMono(self.ua.expires, self.ua.expire_mtime)
        if body != None:
            if self.ua.on_remote_sdp_change != None:
                self.ua.on_remote_sdp_change(body, lambda x: self.ua.delayed_remote_sdp_update(event, x))
                self.ua.setup_ts = req.rtime
                return (UasStateTrying,)
            else:
                self.ua.rSDP = body.getCopy()
        else:
            self.ua.rSDP = None
        self.ua.equeue.append(event)
        self.ua.setup_ts = req.rtime
        return (UasStateTrying,)

if not 'UasStateTrying' in globals():
    from sippy.UasStateTrying import UasStateTrying
