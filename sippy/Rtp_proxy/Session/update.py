# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2022 Sippy Software, Inc. All rights reserved.
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

from sippy.Exceptions.RtpProxyError import RtpProxyError

class update_params():
    rtpps = None
    remote_ip = '0.0.0.0'
    remote_port = 0
    result_callback:callable = None
    options = ''
    index = 0
    atype = 'IP4'
    subcommands = None

    def __init__(self):
        self.subcommands = []

    def process_rtpp_result(self, result):
        if result == None:
            ex = RtpProxyError(f'RTPProxy errored')
            self.result_callback(None, self.rtpps, ex=ex)
            return
        result = result.rstrip()
        t0 = result.split('&&', 1)
        t1 = t0[0].split()
        if t1[0][0] == 'E':
            ex = RtpProxyError(f'RTPProxy errored: {t1[0]}')
            self.result_callback(None, self.rtpps, ex=ex)
            return
        ur = update_result()
        if len(self.subcommands) > 0:
            if len(t0) > 1:
                subc_ress = [x.strip() for x in t0[1].split('&&')]
                actual = len(subc_ress)
            else:
                subc_ress = []
                actual = 0
            expected = sum(len(sc.commands) for sc in self.subcommands)
            if actual > expected:
                ex = RtpProxyError(f'RTPProxy errored: too many results, {actual=}, {expected=}')
                self.result_callback(None, self.rtpps, ex=ex)
                return None
            if actual > 0 and subc_ress[-1] == '-1':
                foff = len(subc_ress)
                for subc in self.subcommands:
                    if foff > len(subc.commands):
                        foff -= len(subc.commands)
                        continue
                    ex = RtpProxyError(f'RTPProxy errored: {subc.commands[foff - 1]}: {subc_ress[-1]}')
                    self.result_callback(None, self.rtpps, ex=ex)
                    return None
            if actual < expected:
                subc_ress.extend(['0',] * (expected - actual))
            for subc in self.subcommands:
                results = subc_ress[:len(subc.commands)]
                ex = subc.handle_results(results, ur)
                if ex is not None:
                    self.result_callback(None, self.rtpps, ex=ex)
                    return None
                subc_ress = subc_ress[len(subc.commands):]
                if len(subc_ress) == 0:
                    break
        ur.rtpproxy_port = int(t1[0])
        if ur.rtpproxy_port == 0:
            ex = RtpProxyError(f'RTPProxy errored: bad port: {t1[0]}')
            self.result_callback(None, self.rtpps, ex=ex)
            return None
        ur.family = 'IP4'
        if len(t1) > 1:
            ur.rtpproxy_address = t1[1]
            if len(t1) > 2 and t1[2] == '6':
                ur.family = 'IP6'
        else:
            ur.rtpproxy_address = self.rtpps.rtp_proxy_client.proxy_address
        # Old-style request to put session on hold, convert it into
        # a new-style request.
        if self.atype == 'IP4' and self.remote_ip == '0.0.0.0':
            ur.sendonly = True
        elif self.atype == 'IP6' and self.remote_ip == '::':
            ur.sendonly = True
        else:
            ur.sendonly = False
        self.result_callback(ur, self.rtpps)
        self.result_callback = None
        return ur

class update_result():
    rtpproxy_address = None
    rtpproxy_port = None
    family = None
    sendonly = None
    sdp_sect_fins = None

    def __init__(self):
        self.sdp_sect_fins = []

    def sdp_sect_fin(self, sdp_bc, sect):
        for f in self.sdp_sect_fins: f(sdp_bc, sect)
