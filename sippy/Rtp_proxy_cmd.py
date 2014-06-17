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

def extract_to_next_token(s, match, invert = False):
    i = 0
    while i < len(s):
        if (not invert and s[i] not in match) or \
          (invert and s[i] in match):
            break
        i += 1
    if i == 0:
        return ('', s)
    if i == len(s):
        return (s, '')
    return (s[:i], s[i:])

class UpdateLookupOpts(object):
    destination_ip = None
    local_ip = None
    codecs = None
    otherparams = None

    def __init__(self, s = None, *params):
        if s == None:
            self.destination_ip, self.local_ip, self.codecs, self.otherparams = params
            return
        self.otherparams = ''
        while len(s) > 0:
            if s[0] == 'R':
                val, s = extract_to_next_token(s[1:], ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '.'))
                val = val.strip()
                if len(val) > 0:
                    self.destination_ip = val
            if s[0] == 'L':
                val, s = extract_to_next_token(s[1:], ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '.'))
                val = val.strip()
                if len(val) > 0:
                    self.local_ip = val
            elif s[0] == 'c':
                val, s = extract_to_next_token(s[1:], ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0', ','))
                val = val.strip()
                if len(val) > 0:
                    self.codecs = [int(x) for x in val.split(',')]
            else:
                val, s = extract_to_next_token(s, ('c', 'R'), True)
                if len(val) > 0:
                    self.otherparams += val

    def __str__(self):
        s = ''
        if self.destination_ip != None:
            s += 'R%s' % (self.destination_ip,)
        if self.local_ip != None:
            s += 'L%s' % (self.local_ip,)
        if self.codecs != None:
            s += 'c'
            for codec in self.codecs:
                s += '%s,' % (codec,)
            s = s[:-1]
        if self.otherparams != None and len(self.otherparams) > 0:
            s += + self.otherparams
        return s

class Rtp_proxy_cmd(object):
    type = None
    ul_opts = None
    command_opts = None
    call_id = None
    args = None

    def __init__(self, cmd):
        self.type = cmd[0].upper()
        if self.type in ('U', 'L', 'D', 'P', 'S', 'R', 'C', 'Q'):
            command_opts, self.call_id, self.args = cmd.split(None, 2)
            if self.type in ('U', 'L'):
                self.ul_opts = UpdateLookupOpts(command_opts[1:])
            else:
                self.command_opts = command_opts[1:]
        else:
            self.command_opts = cmd[1:]

    def __str__(self):
        s = self.type
        if self.ul_opts != None:
            s += str(self.ul_opts)
        elif self.command_opts != None:
            s += self.command_opts
        if self.call_id != None:
            s = '%s %s' % (s, self.call_id)
        if self.args != None:
            s = '%s %s' % (s, self.args)
        return s
