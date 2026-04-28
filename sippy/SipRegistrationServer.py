# Copyright (c) 2026 Sippy Software, Inc. All rights reserved.
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
from sippy.Time.Timeout import Timeout
from math import ceil

class SipRegistrationBinding(object):
    aor = None
    contact = None
    source = None
    paths = None
    call_id = None
    user_agent = None
    timer = None

    def __init__(self, aor, contact, expires, source = None, paths = (),
      call_id = None, user_agent = None):
        self.aor = aor
        self.contact = contact.getCopy()
        self.source = source
        self.paths = tuple(x.getCopy() for x in paths)
        self.call_id = call_id
        self.user_agent = user_agent.getCopy() if user_agent is not None else None
        self.setExpires(expires)

    def setExpires(self, expires):
        self.contact.address.setParam('expires', str(int(expires)))

    def getExpires(self):
        if self.timer is None or self.timer.etime is None:
            return 0
        expires = -self.timer.etime.offsetFromNow()
        return int(ceil(expires)) if expires > 0 else 0

    def getContact(self):
        contact = self.contact.getCopy()
        contact.address.setParam('expires', str(self.getExpires()))
        return contact

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

class SipRegistrationAuthContext(object):
    extra_attributes = None
    acctA = None
    acctO = None

class SipRegistrationAuthState(object):
    server = None
    req = None
    sip_t = None
    auth_context = None
    pre_auth_context = None

    def __init__(self, server, req, sip_t, auth_context, pre_auth_context):
        self.server = server
        self.req = req
        self.sip_t = sip_t
        self.auth_context = auth_context
        self.pre_auth_context = pre_auth_context

    def _getRemoteIP(self):
        if self.auth_context is not None and self.auth_context.remote_ip is not None:
            return self.auth_context.remote_ip
        try:
            return self.req.getSource()[0]
        except Exception:
            return ''

    def start(self):
        remote_ip = self._getRemoteIP()
        try:
            auth = self.req.getHFBody('authorization').getCopy()
        except IndexError:
            auth = None
        caller = self.req.getHFBody('from').getUrl().username or ''
        callee = self.req.getHFBody('to').getUrl().username or ''
        call_id = self.req.getHFBody('call-id')
        extra_attributes = self.pre_auth_context.extra_attributes
        if auth is None or auth.username is None or len(auth.username) == 0:
            username = remote_ip
            self.server.global_config['_radius_client'].do_auth(username, caller, callee, \
              call_id, remote_ip, self.rDone, extra_attributes = extra_attributes, \
              method = 'REGISTER')
            return
        self.server.global_config['_radius_client'].do_auth(auth.username, caller, \
          callee, call_id, remote_ip, self.rDone, auth.realm, auth.nonce, auth.uri, \
          auth.response, extra_attributes = extra_attributes, method = 'REGISTER', \
          algorithm = auth.algorithm or 'MD5')

    def rDone(self, results):
        if len(results) != 2 or results[1] != 0:
            challenge = None
            if self.auth_context is not None:
                challenge = self.auth_context.challenge
            if challenge is not None:
                resp = self.req.genResponse(401, 'Unauthorized')
                resp.appendHeader(challenge)
            else:
                resp = self.req.genResponse(403, 'Auth Failed')
        else:
            resp = self.server.processRequest(self.req)
        self.server.global_config['_sip_tm'].sendResponse(resp, self.sip_t)

class SipRegistrationServer(object):
    global_config = None
    locations = None
    default_expires = 300
    auth_cb = None

    def __init__(self, global_config, auth_cb = None, default_expires = 300):
        self.global_config = global_config
        self.auth_cb = auth_cb
        self.default_expires = default_expires
        self.locations = {}

    def recvRequest(self, req, sip_t = None):
        if req.getMethod() != 'REGISTER':
            return (req.genResponse(501, 'Not Implemented'), None, None)
        try:
            if req.getHFBody('cseq').getCSeqMethod() != 'REGISTER':
                return (req.genResponse(400, 'Bad Request'), None, None)
        except Exception:
            return (req.genResponse(400, 'Bad Request'), None, None)
        auth_context = self.auth_cb(req) if self.auth_cb is not None else None
        if auth_context is not None and auth_context.response is not None:
            return (auth_context.response, None, None)
        if not self.global_config['auth_enable']:
            return (self.processRequest(req), None, None)
        if '_radius_client' not in self.global_config:
            return (req.genResponse(500, 'Internal Server Error'), None, None)
        pre_auth_context = SipRegistrationAuthContext()
        if '_pre_auth_proc' in self.global_config:
            self.global_config['_pre_auth_proc'](pre_auth_context, req)
        auth_state = SipRegistrationAuthState(self, req, sip_t, auth_context, \
          pre_auth_context)
        auth_state.start()
        return (None, None, None)

    def processRequest(self, req):
        try:
            aor = self.getAOR(req)
            contacts = req.getHFBodys('contact')
            default_expires = self.getDefaultExpires(req)
            for contact in contacts:
                if contact.asterisk:
                    continue
                self.getContactExpires(contact, default_expires)
        except Exception:
            return req.genResponse(400, 'Bad Request')

        if len(contacts) == 0:
            return self.genOK(req, aor)

        wildcards = [x for x in contacts if x.asterisk]
        if len(wildcards) > 0:
            if len(contacts) != 1 or default_expires != 0:
                return req.genResponse(400, 'Bad Request')
            self.clearAOR(aor)
            return self.genOK(req, aor)

        for contact in contacts:
            expires = self.getContactExpires(contact, default_expires)
            if expires == 0:
                self.removeContact(aor, contact)
            else:
                self.saveContact(aor, contact, expires, req)
        return self.genOK(req, aor)

    def getAOR(self, req):
        aor = req.getHFBody('to').getUrl().getCopy()
        aor.password = None
        aor.headers = None
        return str(aor)

    def getDefaultExpires(self, req):
        try:
            expires = req.getHFBody('expires').getNum()
        except IndexError:
            expires = self.default_expires
        if expires < 0:
            raise ValueError('negative expires')
        return expires

    def getContactExpires(self, contact, default_expires):
        expires = default_expires
        if 'expires' in contact.address.params:
            expires = int(contact.address.params['expires'])
        if expires < 0:
            raise ValueError('negative contact expires')
        return expires

    def getContactKey(self, contact):
        return str(contact.getUrl())

    def saveContact(self, aor, contact, expires, req):
        key = self.getContactKey(contact)
        bucket = self.locations.setdefault(aor, {})
        old_binding = bucket.get(key, None)
        if old_binding is not None:
            old_binding.cancel()
        try:
            source = req.getSource(ver = 2)
        except Exception:
            source = None
        paths = req.getHFBodys('path')
        try:
            user_agent = req.getHFBody('user-agent')
        except IndexError:
            user_agent = None
        binding = SipRegistrationBinding(aor, contact, expires, source, paths, \
          str(req.getHFBody('call-id')), user_agent)
        bucket[key] = binding
        binding.timer = Timeout(self.expireContact, expires, 1, aor, key)

    def removeContact(self, aor, contact):
        bucket = self.locations.get(aor, None)
        if bucket is None:
            return
        binding = bucket.pop(self.getContactKey(contact), None)
        if binding is not None:
            binding.cancel()
        if len(bucket) == 0:
            del self.locations[aor]

    def clearAOR(self, aor):
        bucket = self.locations.pop(aor, {})
        for binding in bucket.values():
            binding.cancel()

    def expireContact(self, aor, key):
        bucket = self.locations.get(aor, None)
        if bucket is None:
            return
        bucket.pop(key, None)
        if len(bucket) == 0:
            del self.locations[aor]

    def genOK(self, req, aor):
        resp = req.genResponse(200, 'OK')
        for contact in self.lookup(aor):
            resp.appendHeader(SipHeader(name = 'contact', body = contact))
        return resp

    def _getLiveBucket(self, aor):
        if not isinstance(aor, str):
            aor = str(aor)
        bucket = self.locations.get(aor, None)
        if bucket is None:
            return None
        expired = [key for key, binding in bucket.items() if binding.getExpires() == 0]
        for key in expired:
            bucket.pop(key, None)
        if len(bucket) == 0:
            del self.locations[aor]
            return None
        return bucket

    def lookupBindings(self, aor):
        bucket = self._getLiveBucket(aor)
        if bucket is None:
            return ()
        return tuple(bucket.values())

    def lookupBinding(self, aor):
        bindings = self.lookupBindings(aor)
        if len(bindings) == 0:
            return None
        return bindings[0]

    def lookup(self, aor):
        bucket = self._getLiveBucket(aor)
        if bucket is None:
            return ()
        return tuple(binding.getContact() for binding in bucket.values())
