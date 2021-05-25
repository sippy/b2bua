# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006 Sippy Software, Inc. All rights reserved.
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

from sippy.Time.Timeout import Timeout
from sippy.SipURL import SipURL
from sippy.SipTo import SipTo
from sippy.SipFrom import SipFrom
from sippy.SipAddress import SipAddress
from sippy.SipContact import SipContact
from sippy.SipRequest import SipRequest
from sippy.SipHeader import SipHeader

class SipRegistrationAgent(object):
    global_config = None
    user = None
    passw = None
    rmsg = None
    dead = False
    atries = 0
    source_address = None
    exp = None

    def __init__(self, global_config, aor, contact, user = None, passw = None, exp = 180, rok_cb = None, rfail_cb = None, cb_arg = None, target = None):
        self.global_config = global_config
        self.user = user
        self.passw = passw
        self.rok_cb = rok_cb
        self.rfail_cb = rfail_cb
        self.cb_arg = cb_arg
        ruri = aor.getCopy()
        ruri.username = None
        aor.port = None
        tfaddr = SipAddress(url = aor)
        fr0m = SipFrom(address = tfaddr.getCopy())
        fr0m.genTag()
        to = SipTo(address = tfaddr)
        contact = SipContact(address = SipAddress(url = contact))
        contact.address.params['expires'] = str(exp)
        self.exp = exp
        self.rmsg = SipRequest(method = 'REGISTER', ruri = ruri, fr0m = fr0m, contact = contact, to = to, target = target)

    def doregister(self):
        if self.dead:
            return
        self.global_config['_sip_tm'].newTransaction(self.rmsg, self.gotreply, \
          laddress = self.source_address)
        self.rmsg.getHFBody('via').genBranch()
        self.rmsg.getHFBody('cseq').incCSeqNum()

    def stopregister(self):
        self.dead = True
        self.rmsg = None

    def gotreply(self, resp):
        if self.dead:
            return
        if resp.scode < 200:
            return
        if resp.scode >= 200 and resp.scode < 300 and resp.reason != 'Auth Failed':
            contact = None
            if resp.countHFs('contact') > 0:
                contact = resp.getHFBody('contact')
            if contact != None and 'expires' in contact.address.params:
                tout = int(contact.address.params['expires'])
            elif resp.countHFs('expires') > 0:
                tout = resp.getHFBody('expires').getNum()
            else:
                tout = self.exp
            timer = Timeout(self.doregister, tout)
            if self.rok_cb != None:
                self.rok_cb(timer.etime.realt, contact, self.cb_arg)
            self.atries = 0
            return
        if self.user != None and self.passw != None and self.atries < 3:
            for sc, chn, rhn in ((401, 'www-authenticate', 'authorization'),
                                 (407, 'proxy-authenticate', 'authorization')):
                if resp.scode != sc:
                    continue
                if resp.countHFs(chn) == 0:
                    break
                challenge = resp.getHFBody(chn)
                supported, qop = challenge.supportedAlgorithm()
                if not supported:
                    break
                auth = challenge.genAuthHF(self.user, self.passw, 'REGISTER',
                                           str(self.rmsg.ruri), qop=qop)
                for authorization in self.rmsg.getHFs(rhn):
                    self.rmsg.removeHeader(authorization)
                self.rmsg.appendHeader(SipHeader(name = rhn, body = auth))
                self.atries += 1
                self.doregister()
                return
        if self.rfail_cb != None:
            self.rfail_cb(resp.getSL(), self.cb_arg)
        Timeout(self.doregister, 60)
        self.atries = 0
