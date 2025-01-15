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
from sippy.Security.SipNonce import HashOracle, DGST_MD5, DGST_MD5SESS, \
  DGST_SHA256, DGST_SHA256SESS, DGST_SHA512, DGST_SHA512SESS

from hashlib import md5, sha256

from Crypto.Hash import SHA512

class sha512_256(object):
    d = None

    def __init__(self):
        self.d = SHA512.new(truncate = '256')

    def update(self, arg):
        self.d.update(arg)

    def digest(self):
        return self.d.digest()

    def hexdigest(self):
        return self.d.hexdigest()

_HASH_FUNC = {None:(md5, DGST_MD5), 'MD5':(md5, DGST_MD5), 'MD5-sess':(md5, DGST_MD5SESS), \
  'SHA-256':(sha256, DGST_SHA256), 'SHA-256-sess':(sha256, DGST_SHA256SESS), \
  'SHA-512-256':(sha512_256, DGST_SHA512), 'SHA-512-256-sess':(sha512_256, DGST_SHA512SESS)}

class SipAuthorization(SipGenericHF):
    hf_names = ('authorization',)
    username = None
    uri = None
    realm = None
    nonce = None
    response = None
    qop = None
    cnonce = None
    nc = None
    algorithm = None
    otherparams = None
    ho = HashOracle()

    def __init__(self, body = None, username = None, uri = None, realm = None, nonce = None, response = None, \
                 cself = None):
        SipGenericHF.__init__(self, body)
        if body is not None:
            return
        self.parsed = True
        if cself != None:
            self.username = cself.username
            self.uri = cself.uri
            self.realm = cself.realm
            self.nonce = cself.nonce
            self.response = cself.response
            self.qop = cself.qop
            self.cnonce = cself.cnonce
            self.nc = cself.nc
            self.algorithm = cself.algorithm
            self.otherparams = cself.otherparams[:]
            return
        self.username = username
        self.uri = uri
        self.realm = realm
        self.nonce = nonce
        self.response = response
        self.otherparams = []

    def parse(self):
        self.otherparams = []
        for name, value in [x.strip(', ').split('=', 1) for x in self.body.split(' ', 1)[1].split(',')]:
            ci_name = name.lower()
            if ci_name == 'username':
                self.username = value.strip('"')
            elif ci_name == 'uri':
                self.uri = value.strip('"')
            elif ci_name == 'realm':
                self.realm = value.strip('"')
            elif ci_name == 'nonce':
                self.nonce = value.strip('"')
            elif ci_name == 'response':
                self.response = value.strip('"')
            elif ci_name == 'qop':
                self.qop = value.strip('"')
            elif ci_name == 'cnonce':
                self.cnonce = value.strip('"')
            elif ci_name == 'nc':
                self.nc = value.strip('"')
            elif ci_name == 'algorithm':
                self.algorithm = value.strip('"')
            else:
                self.otherparams.append((name, value))
        self.parsed = True

    def genAuthResponse(self, password, method, body):
        HA1 = DigestCalcHA1(self.algorithm, self.username, self.realm, password, \
          self.nonce, self.cnonce)
        self.response = DigestCalcResponse(self.algorithm, HA1, self.nonce, \
          self.nc, self.cnonce, self.qop, method, self.uri, body)

    def __str__(self):
        if not self.parsed:
            return self.body
        rval = 'Digest username="%s",realm="%s",nonce="%s",uri="%s",response="%s"' % \
               (self.username, self.realm, self.nonce, self.uri, self.response)
        if self.algorithm != None:
            rval += ',algorithm=%s' % (self.algorithm,)
        if self.qop != None:
            rval += ',qop=%s,nc=%s,cnonce="%s"' % (self.qop, self.nc, self.cnonce)
        for param in self.otherparams:
            rval += ',%s=%s' % param
        return rval

    def getCopy(self):
        if not self.parsed:
            return self.__class__(self.body)
        return self.__class__(cself = self)

    def verify(self, password, method, body = None):
        if not self.parsed:
            self.parse()
        HA1 = DigestCalcHA1(self.algorithm, self.username, self.realm, password, self.nonce, self.cnonce)
        return self.verifyHA1(HA1, method, body)

    def verifyHA1(self, HA1, method, body):
        if not self.parsed:
            self.parse()
        if self.algorithm not in _HASH_FUNC:
            return False
        if self.qop != None and self.qop not in ('auth', 'auth-int'):
            return False
        algmask = _HASH_FUNC[self.algorithm][1]
        if not self.ho.validate_challenge(self.nonce, (algmask,)):
            return False
        response = DigestCalcResponse(self.algorithm, HA1, self.nonce, self.nc, \
          self.cnonce, self.qop, method, self.uri, body)
        return response == self.response

    def getCanName(self, name, compact = False):
        return 'Authorization'

def IsDigestAlgSupported(algorithm):
    return (algorithm in _HASH_FUNC)

def NameList2AlgMask(nlist):
    return tuple([_HASH_FUNC[x][1] for x in nlist])

def DigestCalcHA1(pszAlg, pszUserName, pszRealm, pszPassword, pszNonce, pszCNonce):
    delim = ':'.encode()
    hashfunc = _HASH_FUNC[pszAlg][0]
    m = hashfunc()
    m.update(pszUserName.encode())
    m.update(delim)
    m.update(pszRealm.encode())
    m.update(delim)
    m.update(pszPassword.encode())
    HA1 = m.hexdigest().encode()
    if pszAlg and pszAlg.endswith('-sess'):
        m = hashfunc()
        m.update(HA1)
        m.update(delim)
        m.update(pszNonce.encode())
        m.update(delim)
        m.update(pszCNonce.encode())
        HA1 = m.hexdigest().encode()
    return HA1

def DigestCalcResponse(pszAlg, HA1, pszNonce, pszNonceCount, pszCNonce, pszQop, pszMethod, pszDigestUri, pszHEntity):
    delim = ':'.encode()
    hashfunc = _HASH_FUNC[pszAlg][0]
    m = hashfunc()
    m.update(pszMethod.encode())
    m.update(delim)
    m.update(pszDigestUri.encode())
    if pszQop == "auth-int":
        m.update(delim)
        if pszHEntity is None:
            pszHEntity = ''
        m1 = hashfunc()
        m1.update(pszHEntity.encode())
        HA_pszHEntity = m1.hexdigest()
        m.update(HA_pszHEntity.encode())
    HA2 = m.hexdigest()
    m = hashfunc()
    m.update(HA1)
    m.update(delim)
    m.update(pszNonce.encode())
    m.update(delim)
    if pszNonceCount and pszCNonce and pszQop:
        m.update(pszNonceCount.encode())
        m.update(delim)
        m.update(pszCNonce.encode())
        m.update(delim)
        m.update(pszQop.encode())
        m.update(delim)
    m.update(HA2.encode())
    response = m.hexdigest()
    return response
