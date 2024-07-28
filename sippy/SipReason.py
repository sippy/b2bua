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

class SipReason(SipGenericHF):
    '''
    Class that implements RFC 3326 Reason header field.
    '''
    hf_names = ('reason',)
    protocol = None
    cause = None
    reason = None

    def __init__(self, body = None, protocol = None, cause = None, reason = None):
        SipGenericHF.__init__(self, body)
        if body is None:
            self.parsed = True
            self.protocol = protocol
            self.cause = cause
            self.reason = reason

    def parse(self):
        protocol, reason_params = self.body.split(';', 1)
        self.protocol = protocol.strip()
        while len(reason_params:=reason_params.lstrip()) > 0:
            rp_name, reason_params = (p:=reason_params.split('=', 1))[0], p[1].lstrip() if len(p) > 1 else ''
            assert rp_name in ('cause', 'text')
            if rp_name == 'text' and reason_params.startswith('"'):
                rp_value, reason_params = (p:=reason_params[1:].split('"', 1))[0], p[1] if len(p) > 1 else ''
                reason_params = '' if len(p:=reason_params.split(';', 1)) == 1 else p[1]
            else:
                rp_value, reason_params = (p:=reason_params.split(';', 1))[0], p[1] if len(p) > 1 else ''
            if rp_name == 'cause':
                self.cause = int(rp_value)
            elif rp_name == 'text':
                self.reason = rp_value
        assert(self.cause is not None)
        self.parsed = True

    def __str__(self):
        if not self.parsed:
            return self.body
        if self.reason == None:
            return '%s; cause=%d' % (self.protocol, self.cause)
        return '%s; cause=%d; text="%s"' % (self.protocol, self.cause, self.reason)

    def getCopy(self):
        if not self.parsed:
            return SipReason(self.body)
        return SipReason(protocol = self.protocol, cause = self.cause, reason = self.reason)

if __name__ == '__main__':
    ours = 'Reason: Q.850; cause=31; text="db4e8de3-ef1e-4427-b6b8-afc339de9f0d;Callee only had Trouter endpoints registered and PNH got delivery errors from all of them."'
    tset = (ours, 'Reason: Q.850;cause=31;text="db4e8de3-ef1e-4427-b6b8-afc339de9f0d;Callee only had Trouter endpoints registered and PNH got delivery errors from all of them."',
      'Reason: Q.850 ; cause= 31;   text=  "db4e8de3-ef1e-4427-b6b8-afc339de9f0d;Callee only had Trouter endpoints registered and PNH got delivery errors from all of them."     ',
      'Reason: Q.850 ;    text=  "db4e8de3-ef1e-4427-b6b8-afc339de9f0d;Callee only had Trouter endpoints registered and PNH got delivery errors from all of them."   ; cause= 31  ')
    for r in tset:
        s = SipReason(r)
        s.parse()
        assert str(s) == ours
