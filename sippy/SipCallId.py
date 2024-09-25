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

from random import random
from hashlib import md5
from time import time
from math import floor
from sippy.SipConf import SipConf
from sippy.SipGenericHF import SipGenericHF

CALL_ID_CHARSET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-.!%*_+`\'~()<>:\\"/[]?{}'
_clen = len(CALL_ID_CHARSET)
DEFAULT_TEST_LEN = (32, 16)

def gen_test_cid(lens = DEFAULT_TEST_LEN):
    r = ''
    for j in (0, 1):
        for i in range(0, lens[j]):
            r += CALL_ID_CHARSET[int(floor(random() * _clen))]
        if j == 0:
            r += '@'
    return r

class SipCallId(SipGenericHF):
    hf_names = ('call-id', 'i')
    body = None

    def __init__(self, body = None):
        SipGenericHF.__init__(self, body)
        self.parsed = True
        if body is None:
            self.genCallId()

    def __add__(self, other):
        return SipCallId(self.body + str(other))

    def genCallId(self):
        salt = str((random() * 1000000000) + time())
        self.body = md5(salt.encode()).hexdigest()

    def getCanName(self, name, compact = False):
        if compact:
            return 'i'
        return 'Call-ID'
