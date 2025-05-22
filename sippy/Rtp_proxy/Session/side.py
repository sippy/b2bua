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

from functools import partial

from sippy.SdpOrigin import SdpOrigin
from sippy.Core.Exceptions import dump_exception
from sippy.Core.EventDispatcher import ED2
from sippy.Exceptions.SdpParseError import SdpParseError
from sippy.Exceptions.RtpProxyError import RtpProxyError
from sippy.Rtp_proxy.Session.update import update_params
from sippy.Rtp_proxy.Session.subcommand import subcommand_dtls, \
  subcommand_dedtls, DTLS_TRANSPORTS
from sippy.Rtp_proxy.Session.subcommand_ice import subcommand_ice, \
  subcommand_deice

try:
    strtypes = (str, unicode)
except NameError:
    strtypes = (str,)

class _rtpps_side(object):
    session_exists = False
    codecs = None
    raddress = None
    laddress = None
    origin = None
    oh_remote = None
    repacketize = None
    gateway_dtls = 'pass'
    deice = False
    soft_repacketize = False
    after_sdp_change = None
    needs_new_port = False
    rinfo_hst = None

    def __init__(self, name):
        self.origin = SdpOrigin()
        self.name = name
        self.rinfo_hst = []

    def __str__(self):
        return f'_rtpps_side("name={self.name}")'

    def update(self, up):
        command = 'U'
        up.rtpps.max_index = max(up.rtpps.max_index, up.index)
        rtpc = up.rtpps.rtp_proxy_client
        rtpq = up.rtpps.rtpp_seq
        options = up.options
        if rtpc.sbind_supported:
            if self.raddress != None:
                #if rtpc.is_local and up.atype == 'IP4':
                #    options += 'L%s' % up.rtpps.global_config['_sip_tm'].l4r.getServer( \
                #      self.raddress).uopts.laddress[0]
                #elif not rtpc.is_local:
                options += 'R%s' % self.raddress[0]
            elif self.laddress != None and rtpc.is_local:
                options += 'L%s' % self.laddress
        otherside = self.getother(up.rtpps)
        if otherside.needs_new_port:
            options += 'N'
            otherside.needs_new_port = False
        command += options
        from_tag, to_tag = self.gettags(up.rtpps)
        if otherside.session_exists:
            command += ' %s %s %d %s %s' % ('%s-%d' % (up.rtpps.call_id, up.index), up.remote_ip, up.remote_port, from_tag, to_tag)
        else:
            command += ' %s %s %d %s' % ('%s-%d' % (up.rtpps.call_id, up.index), up.remote_ip, up.remote_port, from_tag)
        if up.rtpps.notify_socket != None and up.index == 0 and \
          rtpc.tnot_supported:
            command += ' %s %s' % (up.rtpps.notify_socket, up.rtpps.notify_tag)
        if len(up.subcommands) > 0:
            command = ' && '.join([command,] + [sc for subc in up.subcommands for sc in subc.commands])
        rtpq.send_command(command, self.update_result, up)

    def gettags(self, rtpps):
        if self not in (rtpps.caller, rtpps.callee):
            raise AssertionError("Corrupt Rtp_proxy_session")
        if self == rtpps.caller:
            return (rtpps.from_tag, rtpps.to_tag)
        else:
            return (rtpps.to_tag, rtpps.from_tag)

    def getother(self, rtpps):
        if self not in (rtpps.caller, rtpps.callee):
            raise AssertionError("Corrupt Rtp_proxy_session")
        if self == rtpps.caller:
            return rtpps.callee
        else:
            return rtpps.caller

    def update_result(self, result, up):
        #print('%s.update_result(%s)' % (id(self), result))
        self.session_exists = True
        ur = up.process_rtpp_result(result)
        self.rinfo_hst.append(ur)

    def __play(self, prompt_name, times, result_callback, index, result, rtpps):
        from_tag, to_tag = self.gettags(rtpps)
        command = 'P%d %s %s %s %s %s' % (times, '%s-%d' % (rtpps.call_id, index), prompt_name, self.codecs, from_tag, to_tag)
        rtpps.rtpp_seq.send_command(command, result_callback)

    def _play(self, rtpps, prompt_name, times = 1, result_callback = None, index = 0):
        if not self.session_exists:
            ED2.callFromThread(result_callback, None)
            return
        otherside = self.getother(rtpps)
        if not otherside.session_exists:
            up = update_params()
            up.rtpps = rtpps
            up.index = index
            up.result_callback = partial(self.__play, prompt_name, times, result_callback, index)
            otherside.update(up)
            return
        self.__play(prompt_name, times, result_callback, index, None, rtpps)

    def _stop_play(self, rtpps, result_callback = None, index = 0):
        if not self.session_exists:
            ED2.callFromThread(result_callback, None)
            return
        from_tag, to_tag = self.gettags(rtpps)
        command = 'S %s %s %s' % ('%s-%d' % (rtpps.call_id, index), from_tag, to_tag)
        rtpps.rtpp_seq.send_command(command, result_callback)

    def _on_sdp_change(self, rtpps, sdp_body, result_callback):
        sects = []
        try:
            sdp_body.parse()
        except Exception as exception:
            is_spe = isinstance(exception, SdpParseError)
            if not is_spe:
                dump_exception('can\'t parse SDP body', extra = sdp_body.content)
            raise SdpParseError(f'{exception}') from exception if not is_spe else exception
        sdp_bc = sdp_body.content
        if isinstance(sdp_bc, strtypes):
            sdp_body.needs_update = False
            return sdp_body
        for i, sect in enumerate(sdp_bc.sections):
            if sect.m_header.transport.lower() not in rtpps.SUPPORTED_TRTYPES:
                continue
            sects.append(sect)
        if len(sects) == 0:
            sdp_body.needs_update = False
            return sdp_body
        formats = sects[0].m_header.formats
        self.codecs = ','.join([ str(x) for x in formats ])
        if self.repacketize is not None and not self.soft_repacketize:
            options = 'z%d' % self.repacketize
        else:
            options = ''
        otherside = self.getother(rtpps)
        for si, sect in enumerate(sects):
            if sect.c_header.atype == 'IP6':
                sect_options = '6' + options
            else:
                sect_options = options
            up = update_params()
            up.rtpps = rtpps
            up.remote_ip = sect.c_header.addr
            up.remote_port = sect.m_header.port
            up.atype = sect.c_header.atype
            up.options = sect_options
            up.index = si
            if otherside.gateway_dtls == 'dtls':
                up.subcommands.append(subcommand_dtls())
            if otherside.deice:
                up.subcommands.append(subcommand_ice())
            if self.gateway_dtls == 'dtls' and sect.m_header.transport in DTLS_TRANSPORTS:
                up.subcommands.append(subcommand_dedtls(sdp_bc, sect))
            if self.deice:
                up.subcommands.append(subcommand_deice(sdp_bc, sect))
            up.result_callback = partial(self._sdp_change_finish, sdp_body, sect, sects, result_callback)
            self.update(up)
        return

    def _sdp_change_finish(self, sdp_body, sect, sects, result_callback, ur, rtpps, ex:Exception = None):
        if not sdp_body.needs_update:
            return
        sect.needs_update = False
        sdp_bc = sdp_body.content

        if ur == None:
            sdp_body.needs_update = False
            if ex is None: ex = RtpProxyError("RTPProxy errored")
            result_callback(None, ex=ex)
            return

        otherside = self.getother(rtpps)
        if self.after_sdp_change != None:
            self.after_sdp_change(ur.rtpproxy_address) # pylint: disable=not-callable
        ur.sdp_sect_fin(sdp_bc, sect)
        sect.c_header.atype = ur.family
        sect.c_header.addr = ur.rtpproxy_address
        if sect.m_header.port != 0:
            sect.m_header.port = ur.rtpproxy_port
        if ur.sendonly:
            for sendrecv in [x for x in sect.a_headers if x.name == 'sendrecv']:
                sect.a_headers.remove(sendrecv)
            if len([x for x in sect.a_headers if x.name == 'sendonly']) == 0:
                sect.addHeader('a', 'sendonly')
        if self.soft_repacketize or self.repacketize is not None:
            fidx = -1
            for a_header in sect.a_headers[:]:
                if a_header.name == 'ptime':
                    fidx = sect.a_headers.index(a_header)
                    sect.a_headers.remove(a_header)
                elif fidx == -1 and a_header.name == 'fmtp':
                    fidx = sect.a_headers.index(a_header) + 1
            sect.insertHeader(fidx, 'a', 'ptime:%d' % self.repacketize)
        for rtcp_header in [x for x in sect.a_headers if x.name == 'rtcp']:
            rtcp_header.value = '%d IN %s %s' % (ur.rtpproxy_port + 1, ur.family, ur.rtpproxy_address)

        if len([x for x in sects if x.needs_update]) == 0:
            if self.oh_remote != None:
                if self.oh_remote.session_id != sdp_bc.o_header.session_id:
                    self.origin = SdpOrigin()
                elif self.oh_remote.version != sdp_bc.o_header.version:
                    self.origin.version += 1
            self.oh_remote = sdp_bc.o_header.getCopy()
            sdp_bc.o_header = self.origin.getCopy()
            if rtpps.insert_nortpp:
                sdp_bc += 'a=nortpproxy:yes\r\n'
            sdp_body.needs_update = False
            result_callback(sdp_body)

    def _copy(self, rtpps, remote_ip, remote_port, result_callback = None, index = 0):
        if not self.session_exists:
            up = update_params()
            up.rtpps = self
            up.index = index
            up.result_callback = partial(self.__copy, remote_ip, remote_port, result_callback, index)
            self.update(up)
            return
        self.__copy(remote_ip, remote_port, result_callback, index, None, rtpps)

    def __copy(self, remote_ip, remote_port, result_callback, index, result, rtpps):
        from_tag, to_tag = self.gettags(rtpps)
        command = 'C %s udp:%s:%d %s %s' % ('%s-%d' % (rtpps.call_id, index), remote_ip, remote_port, from_tag, to_tag)
        rtpps.rtpp_seq.send_command(command, result_callback)
