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
from sippy.Exceptions.SdpParseError import SdpParseError

DTLS_TRANSPORTS = ('UDP/TLS/RTP/SAVP', 'UDP/TLS/RTP/SAVPF')
DTLS_ATTRS = ('setup', 'fingerprint', 'rtcp', 'ssrc')
DTLS_ATTRS_RM = tuple([a for a in DTLS_ATTRS if a != 'ssrc'])

class subcommand():
    name = 'subcommand'
    mod_2_i_mod = {'dtls_gw':'M4:1', 'ice_lite':'M5:1'}
    commands: list
    def __init__(self, cmd):
        self.commands = [cmd,]

    def append(self, command):
        self.commands.append(command)

    def handle_results(self, results, ur):
        if len(results) != len(self.commands):
            return RtpProxyError(f'RTPProxy errored: {self.name}: {results=}')
        return None

    def _sdp_attrs_rm(self, sdp_bc, sect, attrs_rm):
        rmlist = []
        for obj in sect, sdp_bc:
            for a_header in [x for x in obj.a_headers if x.name in attrs_rm and x.name not in rmlist]:
                obj.a_headers.remove(a_header)
                rmlist.append(a_header.name)

    def fin_sdp_sect(self):
        pass

class subcommand_dtls(subcommand):
    name = 'DTLS'
    dtls_mode: str
    dtls_fingerprint: str
    i_mod = subcommand.mod_2_i_mod['dtls_gw']

    def __init__(self):
        super().__init__(f'{self.i_mod} S')

    def handle_results(self, results, ur):
        if ex:=super().handle_results(results, ur): return ex
        dtls_res = results[0].split(None, 1)
        if len(dtls_res) != 2:
            return RtpProxyError(f'RTPProxy errored: DTLS: {results=}')
        self.dtls_mode, self.dtls_fingerprint = dtls_res
        ur.sdp_sect_fins.append(self.sdp_sect_fin)
        return None

    def sdp_sect_fin(self, sdp_bc, sect):
        self._sdp_attrs_rm(sdp_bc, sect, DTLS_ATTRS_RM)
        sect.addHeader('a', F'setup:{self.dtls_mode}')
        sect.addHeader('a', F'fingerprint:{self.dtls_fingerprint}')

class subcommand_dedtls(subcommand):
    name = 'deDTLS'
    i_mod = subcommand.mod_2_i_mod['dtls_gw']

    def __init__(self, sdp_bc, sect):
        adict = {}
        for atr in (ah for ah in sect.a_headers + sdp_bc.a_headers \
                    if ah.name in DTLS_ATTRS and ah.name not in adict):
            adict[atr.name] = atr.value
        if 'setup' not in adict:
            raise SdpParseError('Missing DTLS connection mode parameter')
        if 'fingerprint' not in adict:
            raise SdpParseError('Missing DTLS fingerprint parameter')
        asetup = adict['setup']
        if asetup in ('active', 'actpass'):
            s_dtls = f'{self.i_mod} A'
        elif asetup in ('passive',):
            s_dtls = f'{self.i_mod} P'
        else:
            raise SdpParseError(F'Unknown connection mode: "{asetup}"')
        s_dtls += F' {adict["fingerprint"]}'
        if 'ssrc' in adict:
            ssrc = adict['ssrc'].split(None, 1)[0]
            s_dtls += F' {ssrc}'
        super().__init__(s_dtls)

    def handle_results(self, results, ur):
        if ex:=super().handle_results(results, ur): return ex
        if any(True for r in results if r != '0'):
            return RtpProxyError(f'RTPProxy errored: {self.name}: {results=}')
        ur.sdp_sect_fins.append(self.sdp_sect_fin)
        return None

    def sdp_sect_fin(self, sdp_bc, sect):
        self._sdp_attrs_rm(sdp_bc, sect, DTLS_ATTRS_RM)
        sect.m_header.transport = 'RTP/AVP'
