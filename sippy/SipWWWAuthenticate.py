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
from sippy.SipConf import SipConf
from sippy.SipAuthorization import SipAuthorization, IsDigestAlgSupported, \
  NameList2AlgMask
from sippy.Security.SipNonce import HashOracle

from Crypto import Random

class SipWWWAuthenticate(SipGenericHF):
    hf_names = ('www-authenticate',)
    aclass = SipAuthorization
    realm = None
    nonce = None
    qop = None
    algorithm = None
    opaque = None
    otherparams = None
    ho = HashOracle()
    rng = Random.new()
    try:
        rng.read(1).hex()
        readhex = lambda self, x: self.rng.read(x).hex()
    except AttributeError:
        # Python 2.7 shim
        readhex = lambda self, x: self.rng.read(x).encode('hex')

    def __init__(self, body = None, realm = None, nonce = None, \
      algorithm = None):
        self.otherparams = []
        SipGenericHF.__init__(self, body)
        if body is not None:
            return
        self.parsed = True
        if algorithm != None:
            self.algorithm = algorithm
            self.qop = ('auth',)
        if nonce == None:
            nonce = self.ho.emit_challenge(NameList2AlgMask((self.algorithm,)))
        if realm == None:
            realm = SipConf.my_address
        self.realm = realm
        self.nonce = nonce

    def parse(self):
        parts = self.body.split(' ', 1)[1].strip().split('"')
        if len(parts) % 2 != 0 and len(parts[-1]) == 0:
            parts.pop()
        while len(parts) > 0:
            parts1 = [x.strip().split('=', 1) for x in parts.pop(0).strip(' ,=').split(',')]
            if len(parts) > 0:
                parts1[-1].append(parts.pop(0))
            for name, value in parts1:
                if name == 'realm':
                    self.realm = value
                elif name == 'nonce':
                    self.nonce = value
                elif name == 'algorithm':
                    if value == 'md5':
                        value = 'MD5'
                    self.algorithm = value
                elif name == 'qop':
                    self.qop = [x.strip() for x in value.split(',')]
                elif name == 'opaque':
                    self.opaque = value
                else:
                    self.otherparams.append((name, value))
        self.parsed = True

    def __str__(self):
        return self.localStr()

    def localStr(self, local_addr = None):
        if not self.parsed:
            return self.body
        if local_addr == None or 'my' not in dir(self.realm):
            local_addr = self.realm
        rval = 'Digest realm="%s",nonce="%s"' % (local_addr, self.nonce)
        if self.qop != None:
            sqop = self.qop[0]
            for qop in self.qop[1:]:
                sqop += ',%s' % qop
            if len(self.qop) > 1:
                rval += ',qop="%s"' % (sqop,)
            else:
                rval += ',qop=%s' % (sqop,)
        if self.algorithm != None:
            rval += ',algorithm=%s' % (self.algorithm,)
        if self.opaque != None:
            rval += ',opaque="%s"' % (self.opaque,)
        for param in self.otherparams:
            rval += ',%s="%s"' % param
        return rval

    def getCopy(self):
        if not self.parsed:
            return self.__class__(self.body)
        cself = self.__class__(realm = self.realm, nonce = self.nonce)
        cself.algorithm = self.algorithm
        cself.qop = self.qop
        cself.opaque = self.opaque
        if len(self.otherparams) > 0:
            cself.otherparams = self.otherparams[:]
        return cself

    def getCanName(self, name, compact = False):
        return 'WWW-Authenticate'

    def getRealm(self):
        return self.realm

    def getNonce(self):
        return self.nonce

    def genAuthHF(self, username, password, method, uri, body = None, qop = None):
        auth = self.aclass(realm = self.realm, nonce = self.nonce, uri = uri, username = username)
        auth.algorithm = self.algorithm
        if self.qop is not None and qop is not None:
            auth.qop = qop
            auth.nc = '00000001'
            auth.cnonce = self.readhex(4)
        if self.opaque != None:
            auth.otherparams.append(('opaque', f'"{self.opaque}"'))
        auth.genAuthResponse(password, method, body)
        return auth

    def supportedAlgorithm(self):
        if self.qop is not None:
            qops = [x for x in self.qop if x in ('auth', 'auth-int')]
            if len(qops) == 0:
                return False, None
            qop = qops[0]
        elif self.algorithm is not None and (self.algorithm.endswith('-sess') or self.algorithm != 'MD5'):
            # -sess variants and RFC8760 algorithms mandate qop
            return False, None
        else:
            qop = None
        return (IsDigestAlgSupported(self.algorithm), qop)
