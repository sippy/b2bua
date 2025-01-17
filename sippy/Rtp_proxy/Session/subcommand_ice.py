# Copyright (c) 2024 Sippy Software, Inc. All rights reserved.
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

from urllib.parse import unquote

from sippy.Exceptions.RtpProxyError import RtpProxyError
from sippy.Exceptions.SdpParseError import SdpParseError
from sippy.Rtp_proxy.Session.subcommand import subcommand

ICE_ATTRS = ('ice-ufrag', 'ice-pwd')
ICE_ATTRS_RM = ICE_ATTRS + ('candidate', 'ice-options', 'rtcp-mux',
  'end-of-candidates', 'ice-options')
ICE_ATTRS_RM += ('extmap', 'extmap-allow-mixed', 'msid',
  'msid-semantic', 'mid', 'group', 'rtcp-fb')

class subcommand_ice(subcommand):
    name = 'ICE'
    ice_lufrag: str
    ice_lpwd: str
    ice_candidates: list
    i_mod = subcommand.mod_2_i_mod['ice_lite']

    def __init__(self):
        super().__init__(f'{self.i_mod} S')

    def handle_results(self, results, ur):
        if ex:=super().handle_results(results, ur): return ex
        ice_res = results[0].split()
        if len(ice_res) < 3:
            return RtpProxyError(f'RTPProxy errored: {self.name}: {results=}')
        self.ice_lufrag, self.ice_lpwd = ice_res[:2]
        self.ice_candidates = [unquote(r[2:]) for r in ice_res[2:]]
        ur.sdp_sect_fins.append(self.sdp_sect_fin)
        return None

    def sdp_sect_fin(self, sdp_bc, sect):
        self._sdp_attrs_rm(sdp_bc, sect, ICE_ATTRS_RM)
        sect.addHeader('a', 'rtcp-mux')
        sect.addHeader('a', 'ice-lite')
        sect.addHeader('a', F'ice-ufrag:{self.ice_lufrag}')
        sect.addHeader('a', F'ice-pwd:{self.ice_lpwd}')
        for cand in self.ice_candidates:
            sect.addHeader('a', F'candidate:{cand}')
        sect.m_header.transport = 'UDP/TLS/RTP/SAVP'

class subcommand_deice(subcommand):
    name = 'deICE'
    i_mod = subcommand.mod_2_i_mod['ice_lite']

    def __init__(self, sdp_bc, sect):
        adict = dict([(x.name, x.value) for x in sect.a_headers
                        if x.name in ICE_ATTRS])
        for rattr in ('ice-ufrag', 'ice-pwd'):
            if rattr not in adict:
                raise SdpParseError(f'Missing ICE {rattr} parameter')
        super().__init__(f'{self.i_mod} A {adict["ice-ufrag"]} {adict["ice-pwd"]}')
        for cand in (x.value for x in sect.a_headers
                        if x.name == 'candidate'):
            pts = cand.split(None, 4)
            if pts[2].lower() != 'udp':
                continue
            if pts[4].startswith('192.') and not pts[4].startswith('192.168.'):
                # Carrier-grade NAT garbage
                continue
            self.append(f'{self.i_mod} C {cand}')

    def handle_results(self, results, ur):
        if ex:=super().handle_results(results, ur): return ex
        if any(True for r in results if r != '0'):
            return RtpProxyError(f'RTPProxy errored: {self.name}: {results=}')
        ur.sdp_sect_fins.append(self.sdp_sect_fin)
        return None

    def sdp_sect_fin(self, sdp_bc, sect):
        self._sdp_attrs_rm(sdp_bc, sect, ICE_ATTRS_RM)
        for a in [a for a in sect.a_headers if a.name == 'ssrc']:
            ssrc, attr = a.value.split(None, 1)
            if not attr.lower().startswith('msid:'): continue
            sect.a_headers.remove(a)
