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

from sippy.SdpOrigin import SdpOrigin

from hashlib import md5
from random import random
from time import time
try:
    from _thread import get_ident
except ImportError:
    from thread import get_ident
import sys

from sippy.Core.Exceptions import dump_exception
from sippy.Core.EventDispatcher import ED2
from sippy.Exceptions.RtpProxyError import RtpProxyError
from sippy.Exceptions.SipParseError import SdpParseError

try:
    strtypes = (str, unicode)
except NameError:
    strtypes = (str,)

class Rtp_proxy_cmd_sequencer(object):
    rtp_proxy_client = None
    comqueue = None
    inflight = None
    deleted = False

    def __init__(self, rtpp_client):
        self.rtp_proxy_client = rtpp_client
        self.comqueue = []

    def send_command(self, command, result_callback = None, *callback_parameters):
        if self.rtp_proxy_client == None:
            return
        if self.inflight != None:
            self.comqueue.append((command, result_callback, callback_parameters))
            return
        self.inflight = (command, result_callback, callback_parameters)
        self.rtp_proxy_client.send_command(command, self.result_callback)

    def result_callback(self, result):
        command, result_callback, callback_parameters = self.inflight
        self.inflight = None
        if self.rtp_proxy_client != None and len(self.comqueue) > 0:
            self.inflight = self.comqueue.pop(0)
            self.rtp_proxy_client.send_command(self.inflight[0], self.result_callback)
        if result_callback != None:
            result_callback(result, *callback_parameters)
        if self.deleted:
            self.delete()
            return

    def delete(self):
        if self.inflight is not None:
            self.deleted = True
            return
        # break the reference loop
        self.rtp_proxy_client = None

class update_params():
    rtpps = None
    remote_ip = '0.0.0.0'
    remote_port = 0
    result_callback = None
    options = ''
    index = 0
    atype = 'IP4'
    callback_parameters = ()
    subcommands = None

    def __init__(self):
        self.subcommands = []

class update_result():
    rtpproxy_address = None
    rtpproxy_port = None
    family = None
    sendonly = None
    dtls_mode = None
    dtls_fingerprint = None

DTLS_TRANSPORTS = ('UDP/TLS/RTP/SAVP', 'UDP/TLS/RTP/SAVPF')
DTLS_ATTRS = ('setup', 'fingerprint', 'rtcp', 'ssrc')
DTLS_ATTRS_RM = tuple([a for a in DTLS_ATTRS if a != 'ssrc'])

class _rtpps_side(object):
    session_exists = False
    codecs = None
    raddress = None
    laddress = None
    origin = None
    oh_remote = None
    repacketize = None
    gateway_dtls = 'pass'
    soft_repacketize = False
    after_sdp_change = None
    needs_new_port = False
    transports = None
    rinfo_hst = None

    def __init__(self, name):
        self.origin = SdpOrigin()
        self.name = name
        self.transports = {}
        self.rinfo_hst = []

    def __str__(self):
        return f'_rtpps_side("name={self.name},transports={self.transports}")'

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
            command = ' && '.join([command,] + up.subcommands)
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
        if result == None:
            up.result_callback(None, up.rtpps, *up.callback_parameters)
            return
        t0 = result.split('&&', 1)
        t1 = t0[0].split()
        if t1[0][0] == 'E':
            up.result_callback(None, up.rtpps, *up.callback_parameters)
            return
        ur = update_result()
        if len(t0) > 1:
            subc_res = t0[1].lstrip()
            if subc_res == '-1':
                up.result_callback(None, up.rtpps, *up.callback_parameters)
                return
            ur.dtls_mode, ur.dtls_fingerprint = subc_res.split(' ', 1)
        ur.rtpproxy_port = int(t1[0])
        if ur.rtpproxy_port == 0:
            up.result_callback(None, up.rtpps, *up.callback_parameters)
            return
        ur.family = 'IP4'
        if len(t1) > 1:
            ur.rtpproxy_address = t1[1]
            if len(t1) > 2 and t1[2] == '6':
                ur.family = 'IP6'
        else:
            ur.rtpproxy_address = up.rtpps.rtp_proxy_client.proxy_address
        # Old-style request to put session on hold, convert it into
        # a new-style request.
        if up.atype == 'IP4' and up.remote_ip == '0.0.0.0':
            ur.sendonly = True
        elif up.atype == 'IP6' and up.remote_ip == '::':
            ur.sendonly = True
        else:
            ur.sendonly = False
        self.rinfo_hst.append(ur)
        up.result_callback(ur, up.rtpps, *up.callback_parameters)

    def __play(self, result, rtpps, prompt_name, times, result_callback, index):
        from_tag, to_tag = self.gettags(rtpps)
        command = 'P%d %s %s %s %s %s' % (times, '%s-%d' % (rtpps.call_id, index), prompt_name, self.codecs, from_tag, to_tag)
        rtpps.rtpp_seq.send_command(command, rtpps.command_result, result_callback)

    def _play(self, rtpps, prompt_name, times = 1, result_callback = None, index = 0):
        if not self.session_exists:
            ED2.callFromThread(rtpps.command_result, None, result_callback)
            return
        otherside = self.getother(rtpps)
        if not otherside.session_exists:
            up = update_params()
            up.rtpps = rtpps
            up.index = index
            up.result_callback = self.__play
            up.callback_parameters = (prompt_name, times, result_callback, index)
            otherside.update(up)
            return
        self.__play(None, rtpps, prompt_name, times, result_callback, index)

    def _stop_play(self, rtpps, result_callback = None, index = 0):
        if not self.session_exists:
            ED2.callFromThread(rtpps.command_result, None, result_callback)
            return
        from_tag, to_tag = self.gettags(rtpps)
        command = 'S %s %s %s' % ('%s-%d' % (rtpps.call_id, index), from_tag, to_tag)
        rtpps.rtpp_seq.send_command(command, rtpps.command_result, result_callback)

    def _on_sdp_change(self, rtpps, sdp_body, result_callback, en_excpt):
        sects = []
        try:
            sdp_body.parse()
        except Exception as exception:
            is_spe = isinstance(exception, SdpParseError)
            if not is_spe:
                dump_exception('can\'t parse SDP body', extra = sdp_body.content)
            if is_spe or en_excpt:
                raise exception
            else:
                return
        if isinstance(sdp_body.content, strtypes):
            sdp_body.needs_update = False
            result_callback(sdp_body)
            return
        for i, sect in enumerate(sdp_body.content.sections):
            if sect.m_header.transport.lower() not in rtpps.SUPPORTED_TRTYPES:
                continue
            sects.append(sect)
        if len(sects) == 0:
            sdp_body.needs_update = False
            result_callback(sdp_body)
            return
        formats = sects[0].m_header.formats
        self.codecs = ','.join([ str(x) for x in formats ])
        if self.repacketize is not None and not self.soft_repacketize:
            options = 'z%d' % self.repacketize
        else:
            options = ''
        otherside = self.getother(rtpps)
        for si, sect in enumerate(sects):
            self.transports[si] = sect.m_header.transport
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
            up.result_callback = self._sdp_change_finish
            if otherside.gateway_dtls == 'dtls':
                up.subcommands.append('M4:1 S')
                otherside.transports[si] = 'UDP/TLS/RTP/SAVP'
            if self.gateway_dtls == 'dtls' and sect.m_header.transport in DTLS_TRANSPORTS:
                adict = dict([(x.name, x.value) for x in sect.a_headers
                              if x.name in DTLS_ATTRS])
                if 'setup' not in adict:
                    raise SdpParseError('Missing DTLS connection mode parameter')
                if 'fingerprint' not in adict:
                    raise SdpParseError('Missing DTLS fingerprint parameter')
                asetup = adict['setup']
                if asetup in ('active', 'actpass'):
                    subcommand = 'M4:1 A'
                elif asetup in ('passive',):
                    subcommand = 'M4:1 P'
                else:
                    raise SdpParseError(F'Unknown connection mode: "{asetup}"')
                subcommand += F' {adict["fingerprint"]}'
                if 'ssrc' in adict:
                    ssrc = adict['ssrc'].split(None, 1)[0]
                    subcommand += F' {ssrc}'
                up.subcommands.append(subcommand)
                if otherside.gateway_dtls == 'rtp':
                    otherside.transports[si] = 'RTP/AVP'
            up.callback_parameters = (sdp_body, sect, sects, result_callback)
            self.update(up)
        return

    def _sdp_change_finish(self, ur, rtpps, sdp_body, sect, sects, result_callback):
        sect.needs_update = False
        if ur != None:
            otherside = self.getother(rtpps)
            if self.after_sdp_change != None:
                self.after_sdp_change(ur.rtpproxy_address) # pylint: disable=not-callable
            si = sects.index(sect)
            if si in otherside.transports and self.gateway_dtls != 'pass' \
              and otherside.transports[si] != sect.m_header.transport:
                sect.m_header.transport = otherside.transports[si]
                for dtls_hdr in [x for x in sect.a_headers
                                 if x.name in DTLS_ATTRS_RM]:
                    sect.a_headers.remove(dtls_hdr)
            if ur.dtls_fingerprint:
                for dtls_hdr in [x for x in sect.a_headers if x.name in DTLS_ATTRS_RM]:
                    sect.a_headers.remove(dtls_hdr)
                sect.addHeader('a', F'setup:{ur.dtls_mode}')
                sect.addHeader('a', F'fingerprint:{ur.dtls_fingerprint}')
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
                if self.oh_remote.session_id != sdp_body.content.o_header.session_id:
                    self.origin = SdpOrigin()
                elif self.oh_remote.version != sdp_body.content.o_header.version:
                    self.origin.version += 1
            self.oh_remote = sdp_body.content.o_header.getCopy()
            sdp_body.content.o_header = self.origin.getCopy()
            if rtpps.insert_nortpp:
                sdp_body.content += 'a=nortpproxy:yes\r\n'
            sdp_body.needs_update = False
            result_callback(sdp_body)

    def _copy(self, rtpps, remote_ip, remote_port, result_callback = None, index = 0):
        if not self.session_exists:
            up = update_params()
            up.rtpps = self
            up.index = index
            up.result_callback = self.__copy
            up.callback_parameters = (remote_ip, remote_port, result_callback, index)
            self.update(up)
            return
        self.__copy(None, rtpps, remote_ip, remote_port, result_callback, index)

    def __copy(self, result, rtpps, remote_ip, remote_port, result_callback = None, index = 0):
        from_tag, to_tag = self.gettags(rtpps)
        command = 'C %s udp:%s:%d %s %s' % ('%s-%d' % (rtpps.call_id, index), remote_ip, remote_port, from_tag, to_tag)
        rtpps.rtpp_seq.send_command(command, rtpps.command_result, result_callback)

class Rtp_proxy_session(object):
    AV_TRTYPES = ('rtp/avp', 'rtp/savp', 'rtp/savpf', 'udp/tls/rtp/savp', 'udp/tls/rtp/savpf')
    SUPPORTED_TRTYPES = AV_TRTYPES + ('udp', 'udptl', 'udp/bfcp')
    rtp_proxy_client = None
    rtpp_seq = None
    call_id = None
    from_tag = None
    to_tag = None
    caller = None
    callee = None
    max_index = -1
    notify_socket = None
    notify_tag = None
    global_config = None
    my_ident = None
    insert_nortpp = False

    def __init__(self, global_config, call_id = None, from_tag = None, to_tag = None,
      notify_socket = None, notify_tag = None):
        self.global_config = global_config
        self.my_ident = get_ident()
        if '_rtp_proxy_clients' in global_config:
            rtp_proxy_clients = [x for x in global_config['_rtp_proxy_clients'] if x.online]
            n = len(rtp_proxy_clients)
            if n == 0:
                raise RtpProxyError('No online RTP proxy client has been found')
            self.rtp_proxy_client = rtp_proxy_clients[int(random() * n)]
        else:
            self.rtp_proxy_client = global_config['rtp_proxy_client']
            if not self.rtp_proxy_client.online:
                raise RtpProxyError('No online RTP proxy client has been found')
        self.rtpp_seq = Rtp_proxy_cmd_sequencer(self.rtp_proxy_client)
        if call_id != None:
            self.call_id = call_id
        else:
            salt = str(random()) + str(time())
            self.call_id = md5(salt.encode()).hexdigest()
        if from_tag != None:
            self.from_tag = from_tag
        else:
            salt = str(random()) + str(time())
            self.from_tag = md5(salt.encode()).hexdigest()
        if to_tag != None:
            self.to_tag = to_tag
        else:
            salt = str(random()) + str(time())
            self.to_tag = md5(salt.encode()).hexdigest()
        self.notify_socket = notify_socket
        self.notify_tag = notify_tag
        self.caller = _rtpps_side('caller')
        self.callee = _rtpps_side('callee')

    def version(self, result_callback):
        self.rtp_proxy_client.send_command('V', self.version_result, result_callback)

    def version_result(self, result, result_callback):
        result_callback(result)

    def play_caller(self, prompt_name, times = 1, result_callback = None, index = 0):
        return self.caller._play(self, prompt_name, times, result_callback, index)

    def play_callee(self, prompt_name, times = 1, result_callback = None, index = 0):
        return self.callee._play(self, prompt_name, times, result_callback, index)

    def stop_play_caller(self, result_callback = None, index = 0):
        return self.caller._stop_play(self, result_callback, index)

    def stop_play_callee(self, result_callback = None, index = 0):
        return self.callee._stop_play(self, result_callback, index)

    def copy_caller(self, remote_ip, remote_port, result_callback = None, index = 0):
        return self.caller._copy(self, remote_ip, remote_port, result_callback, index)

    def copy_callee(self, remote_ip, remote_port, result_callback = None, index = 0):
        return self.callee._copy(self, remote_ip, remote_port, result_callback, index)

    def start_recording(self, rname = None, result_callback = None, index = 0):
        if not self.caller.session_exists:
            up = update_params()
            up.rtpps = self
            up.index = index
            up.result_callback = self._start_recording
            up.callback_parameters = (rname, result_callback, index)
            self.caller.update(up)
            return
        self._start_recording(None, self, rname, result_callback, index)

    def _start_recording(self, result, rtpps, rname, result_callback, index):
        if rname == None:
            command = 'R %s %s %s' % ('%s-%d' % (self.call_id, index), self.from_tag, self.to_tag)
            return self.rtpp_seq.send_command(command, self.command_result, result_callback)
        command = 'C %s %s.a %s %s' % ('%s-%d' % (self.call_id, index), rname, self.from_tag, self.to_tag)
        return self.rtpp_seq.send_command(command, self._start_recording1, \
          (rname, result_callback, index))

    def _start_recording1(self, result, args):
        rname, result_callback, index = args
        command = 'C %s %s.o %s %s' % ('%s-%d' % (self.call_id, index), rname, self.to_tag, self.from_tag)
        return self.rtpp_seq.send_command(command, self.command_result, result_callback)

    def command_result(self, result, result_callback):
        #print('%s.command_result(%s)' % (id(self), result))
        if result_callback != None:
            result_callback(result)

    def delete(self):
        if self.rtp_proxy_client == None:
            return
        while self.max_index >= 0:
            command = 'D %s %s %s' % ('%s-%d' % (self.call_id, self.max_index), self.from_tag, self.to_tag)
            self.rtpp_seq.send_command(command)
            self.max_index -= 1
        self.rtp_proxy_client = None
        self.rtpp_seq.delete()

    def on_caller_sdp_change(self, sdp_body, result_callback, en_excpt = False):
        self.caller._on_sdp_change(self, sdp_body, result_callback, en_excpt)

    def on_callee_sdp_change(self, sdp_body, result_callback, en_excpt = False):
        self.callee._on_sdp_change(self, sdp_body, result_callback, en_excpt)

    def stats(self, result_callback, index = 0, *callback_parameters):
        command = 'Q %s %s %s' % ('%s-%d' % (self.call_id, index), self.from_tag, self.to_tag)
        self.rtp_proxy_client.send_command(command, self.stats_result, (result_callback, callback_parameters))

    def stats_result(self, result, args):
        t1 = result.split()
        result_callback, callback_parameters = args
        if len(t1) == 1:
            result_callback(None, *callback_parameters)
            return
        ttl, caller_rcount, callee_rcount, fwd_rcount, drop_rcount = [int(x) for x in t1]
        result_callback((ttl, caller_rcount, callee_rcount, fwd_rcount, drop_rcount), *callback_parameters)

    def __del__(self):
        if self.my_ident != get_ident():
            #print('Rtp_proxy_session.__del__() from wrong thread, re-routing')
            ED2.callFromThread(self.delete)
        else:
            self.delete()

if __name__ == '__main__':
    from sippy.Time.Timeout import Timeout
    from sippy.Rtp_proxy_client import Rtp_proxy_client
    def display(*args):
        print('got:', args)
        ED2.breakLoop()
    def waitonline(rpc):
        if rpc.online:
            ED2.breakLoop()
    gc = {'_sip_address':'1.2.3.4'}
    r = Rtp_proxy_client(gc)
    t = Timeout(waitonline, 0.1, 10, r)
    ED2.loop(2.0)
    assert(r.online)
    t.cancel()

    gc['rtp_proxy_client'] = r
    rs = Rtp_proxy_session(gc, 'call_id1', 'from_tag1', 'to_tag1')
    rs.version(display)
    ED2.loop()

    rs.start_recording('bogus', result_callback = display)
    print(1)
    ED2.loop()
    print(2)
    rs.play_callee('bogus', result_callback = display)
    ED2.loop()
    print(3)
    rs.stop_play_callee(result_callback = display)
    ED2.loop()
    print(4)
    rs.play_caller('bogus', result_callback = display)
    ED2.loop()
    print(5)
    rs.stop_play_caller(result_callback = display)
    ED2.loop()
    print(6)
    del rs
    r.shutdown()
    print(7, 'passed')
