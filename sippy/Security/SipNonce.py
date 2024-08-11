# Copyright (c) 2020 Sippy Software, Inc. All rights reserved.
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

#import sys; sys.path.append('..')

from functools import partial
from base64 import b64encode, b64decode

from Crypto import Random
from Crypto.Cipher import AES

from sippy.Time.clock_dtime import clock_getntime, CLOCK_MONOTONIC

to_bytes_be = partial(int.to_bytes, byteorder='big')
from_bytes_be = partial(int.from_bytes, byteorder='big')

def bxor(ba1, ba2):
    olen = len(ba1)
    ba1 = from_bytes_be(ba1)
    ba2 = from_bytes_be(ba2)
    return to_bytes_be(ba1 ^ ba2, olen)

class AESCipher(object):
    bpad = '='.encode()
    cipher = None

    def __init__(self, key):
        self.cipher = AES.new(key, AES.MODE_ECB)

    def encrypt(self, raw):
        iv = Random.new().read(AES.block_size)
        raw = bxor(raw, iv)
        eraw = self.cipher.encrypt(iv + raw)
        return b64encode(eraw)[:-1]

    def decrypt(self, enc):
        enc = b64decode(enc + self.bpad)
        raw = self.cipher.decrypt(enc)
        iv = raw[:AES.block_size]
        return bxor(raw[AES.block_size:], iv)

DGST_MD5        = (1 << 0)
DGST_MD5SESS    = (1 << 1)
DGST_SHA256     = (1 << 2)
DGST_SHA256SESS = (1 << 3)
DGST_SHA512     = (1 << 4)
DGST_SHA512SESS = (1 << 5)

DGST_PRIOS = (DGST_SHA512, DGST_SHA512SESS, DGST_SHA256, DGST_SHA256SESS, DGST_MD5, DGST_MD5SESS)

class HashOracle(object):
    try: key # pylint: disable=used-before-assignment
    except: key = Random.new().read(AES.block_size * 2)
    ac = None
    vtime = 32 * 10**9

    def __init__(self):
        self.ac = AESCipher(self.key)

    def emit_challenge(self, cmask):
        ts128 = clock_getntime(CLOCK_MONOTONIC) << len(DGST_PRIOS)
        for ms in cmask:
            ts128 |= ms
        cryptic = self.ac.encrypt(to_bytes_be(ts128, AES.block_size))
        #return cryptic
        return cryptic.decode()

    def validate_challenge(self, cryptic, cmask):
        new_ts = clock_getntime(CLOCK_MONOTONIC)
        decryptic = from_bytes_be(self.ac.decrypt(cryptic.encode()))
        for ms in cmask:
            if (ms & decryptic) == 0:
                return False
        orig_ts = decryptic >> len(DGST_PRIOS)
        tsdiff = new_ts - orig_ts
        if tsdiff < 0 or tsdiff > self.vtime:
            return False
        return True

if __name__ == '__main__':
    from threading import Thread

    class TestExpiration(Thread):
        daemon = True
        nonce = None
        ho = HashOracle()
        excpt = None

        def __init__(self, nonce):
            Thread.__init__(self)
            self.nonce = nonce
            self.start()

        def run(self):
            from time import sleep
            if not self.ho.validate_challenge(self.nonce, DGST_PRIOS):
                self.excpt = Exception('Expiration Test Failed #1')
                return
            sleep(30)
            if not self.ho.validate_challenge(self.nonce, DGST_PRIOS):
                self.excpt = Exception('Expiration Test Failed #2')
                return
            sleep(2)
            if self.ho.validate_challenge(self.nonce, DGST_PRIOS):
                self.excpt = Exception('Expiration Test Failed #3')

    ho = HashOracle()

    expthr = TestExpiration(ho.emit_challenge(DGST_PRIOS))
    i = 0
    min_ts = None
    while i < 10000:
        cryptic = ho.emit_challenge(DGST_PRIOS)
        if not ho.validate_challenge(cryptic, DGST_PRIOS):
            raise Exception('Basic Test Failed')
        i += 1
    print(cryptic)
    expthr.join()
    if expthr.excpt != None:
        raise expthr.excpt
