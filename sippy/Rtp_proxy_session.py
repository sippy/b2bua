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

class _rtpps_callback_params(object):
    proxy_address = None
    callback_parameters = None
    atype = None
    remote_ip = None

    def __init__(self, proxy_address, callback_parameters, atype):
        self.proxy_address = proxy_address
        self.callback_parameters = callback_parameters
        self.atype = atype

class _rtpps_side(object):
    session_exists = False
    codecs = None
    raddress = None
    laddress = None
    repacketize = None

    def update(self, rtpps, remote_ip, remote_port, result_callback, options = '', index = 0, \
      atype = 'IP4', *callback_parameters):
        command = 'U'
        rtpps.max_index = max(rtpps.max_index, index)
        rtpc = rtpps.rtp_proxy_client
        if rtpc.sbind_supported:
            if self.raddress != None:
                #if rtpc.is_local and atype == 'IP4':
                #    options += 'L%s' % rtpps.global_config['_sip_tm'].l4r.getServer( \
                #      self.raddress).uopts.laddress[0]
                #elif not rtpc.is_local:
                options += 'R%s' % self.raddress[0]
            elif self.laddress != None and rtpc.is_local:
                options += 'L%s' % self.laddress
        command += options
        from_tag, to_tag = self.gettags(rtpps)
        otherside = self.getother(rtpps)
        if otherside.session_exists:
            command += ' %s %s %d %s %s' % ('%s-%d' % (rtpps.call_id, index), remote_ip, remote_port, from_tag, to_tag)
        else:
            command += ' %s %s %d %s' % ('%s-%d' % (rtpps.call_id, index), remote_ip, remote_port, from_tag)
        if rtpps.notify_socket != None and index == 0 and \
          rtpc.tnot_supported:
            command += ' %s %s' % (rtpps.notify_socket, rtpps.notify_tag)
        cpo = _rtpps_callback_params(rtpc.proxy_address, callback_parameters, atype)
        cpo.remote_ip = remote_ip
        rtpc.send_command(command, self.update_result, (rtpps, result_callback, cpo))

    def gettags(self, rtpps):
        if self not in (rtpps.caller, rtpps.callee):
            raise Exception("Corrupt Rtp_proxy_session")
        if self == rtpps.caller:
            return (rtpps.from_tag, rtpps.to_tag)
        else:
            return (rtpps.to_tag, rtpps.from_tag)

    def getother(self, rtpps):
        if self not in (rtpps.caller, rtpps.callee):
            raise Exception("Corrupt Rtp_proxy_session")
        if self == rtpps.caller:
            return rtpps.callee
        else:
            return rtpps.caller

    def update_result(self, result, args):
        #print '%s.update_result(%s)' % (id(self), result)
        rtpps, result_callback, cpo = args
        self.session_exists = True
        if result == None:
            result_callback(None, rtpps, *cpo.callback_parameters)
            return
        t1 = result.split()
        if t1[0][0] == 'E':
            result_callback(None, rtpps, *cpo.callback_parameters)
            return
        rtpproxy_port = int(t1[0])
        if rtpproxy_port == 0:
            result_callback(None, rtpps, *cpo.callback_parameters)
            return
        family = 'IP4'
        if len(t1) > 1:
            rtpproxy_address = t1[1]
            if len(t1) > 2 and t1[2] == '6':
                family = 'IP6'
        else:
            rtpproxy_address = cpo.proxy_address
        # Old-style request to put session on hold, convert it into
        # a new-style request.
        if cpo.atype == 'IP4' and cpo.remote_ip == '0.0.0.0':
            sendonly = True
        elif cpo.atype == 'IP6' and cpo.remote_ip == '::':
            sendonly = True
        else:
            sendonly = False
        cb_args = (rtpproxy_address, rtpproxy_port, family, sendonly)
        result_callback(cb_args, rtpps, *cpo.callback_parameters)

    def __play(self, result, rtpps, prompt_name, times, result_callback, index):
        from_tag, to_tag = self.gettags(rtpps)
        command = 'P%d %s %s %s %s %s' % (times, '%s-%d' % (rtpps.call_id, index), prompt_name, self.codecs, from_tag, to_tag)
        rtpps.rtp_proxy_client.send_command(command, rtpps.command_result, result_callback)

    def _play(self, rtpps, prompt_name, times = 1, result_callback = None, index = 0):
        if not self.session_exists:
            ED2.callFromThread(rtpps.command_result, None, result_callback)
            return
        otherside = self.getother(rtpps)
        if not otherside.session_exists:
            otherside.update(rtpps, '0.0.0.0', 0, self.__play, '', index, 'IP4', prompt_name, times, result_callback, index)
            return
        self.__play(None, rtpps, prompt_name, times, result_callback, index)

    def _stop_play(self, rtpps, result_callback = None, index = 0):
        if not self.session_exists:
            ED2.callFromThread(rtpps.command_result, None, result_callback)
            return
        from_tag, to_tag = self.gettags(rtpps)
        command = 'S %s %s %s' % ('%s-%d' % (rtpps.call_id, index), from_tag, to_tag)
        rtpps.rtp_proxy_client.send_command(command, rtpps.command_result, result_callback)

    def _on_sdp_change(self, rtpps, sdp_body, result_callback, en_excpt):
        sects = []
        try:
            sdp_body.parse()
        except Exception as exception:
            dump_exception('can\'t parse SDP body', extra = sdp_body.content)
            if en_excpt:
                raise exception
            else:
                return
        for i in range(0, len(sdp_body.content.sections)):
            sect = sdp_body.content.sections[i]
            if sect.m_header.transport.lower() not in ('udp', 'udptl', 'rtp/avp', \
              'rtp/savp', 'udp/bfcp'):
                continue
            sects.append(sect)
        if len(sects) == 0:
            sdp_body.needs_update = False
            result_callback(sdp_body)
            return
        formats = sects[0].m_header.formats
        self.codecs = ','.join([ str(x) for x in formats ])
        if self.repacketize != None:
            options = 'z%d' % self.repacketize
        else:
            options = ''
        for sect in sects:
            if sect.c_header.atype == 'IP6':
                sect_options = '6' + options
            else:
                sect_options = options
            self.update(rtpps, sect.c_header.addr, sect.m_header.port, self._sdp_change_finish, sect_options, \
              sects.index(sect), sect.c_header.atype, sdp_body, sect, sects, result_callback)
        return

    def _sdp_change_finish(self, cb_args, rtpps, sdp_body, sect, sects, result_callback):
        sect.needs_update = False
        if cb_args != None:
            rtpproxy_address, rtpproxy_port, family, sendonly = cb_args
            sect.c_header.atype = family
            sect.c_header.addr = rtpproxy_address
            if sect.m_header.port != 0:
                sect.m_header.port = rtpproxy_port
            if sendonly:
                while 'sendrecv' in sect.a_headers:
                    sect.a_headers.remove('sendrecv')
                if 'sendonly' not in sect.a_headers:
                    sect.a_headers.append('sendonly')
            if self.repacketize != None:
                fidx = -1
                for a_header in sect.a_headers[:]:
                    if a_header.startswith('ptime:'):
                        fidx = sect.a_headers.index(a_header)
                        sect.a_headers.remove(a_header)
                    if fidx == -1 and a_header.startswith('fmtp:'):
                        fidx = sect.a_headers.index(a_header) + 1
                sect.a_headers.insert(fidx, 'ptime:%d' % self.repacketize)
        if len([x for x in sects if x.needs_update]) == 0:
            if rtpps.insert_nortpp:
                sdp_body.content += 'a=nortpproxy:yes\r\n'
                sdp_body.content += 'a=nortpproxy:yes\r\n'
            # RFC4566
            # *******
            # For privacy reasons, it is sometimes desirable to obfuscate the
            # username and IP address of the session originator.  If this is a
            # concern, an arbitrary <username> and private <unicast-address> MAY be
            # chosen to populate the "o=" field, provided that these are selected
            # in a manner that does not affect the global uniqueness of the field.
            # *******
            sdp_body.content.o_header.address = '192.0.2.1' # 192.0.2.0/24 (TEST-NET-1)
            sdp_body.content.o_header.network_type = 'IN'
            sdp_body.content.o_header.address_type = 'IP4'
            sdp_body.needs_update = False
            result_callback(sdp_body)

    def _copy(self, rtpps, remote_ip, remote_port, result_callback = None, index = 0):
        if not self.session_exists:
            self.update(self, '0.0.0.0', 0, self.__copy, '', index, 'IP4', remote_ip, remote_port, result_callback, index)
            return
        self.__copy(None, rtpps, remote_ip, remote_port, result_callback, index)

    def __copy(self, result, rtpps, remote_ip, remote_port, result_callback = None, index = 0):
        from_tag, to_tag = self.gettags(rtpps)
        command = 'C %s udp:%s:%d %s %s' % ('%s-%d' % (rtpps.call_id, index), remote_ip, remote_port, from_tag, to_tag)
        rtpps.rtp_proxy_client.send_command(command, rtpps.command_result, result_callback)

class Rtp_proxy_session(object):
    rtp_proxy_client = None
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
                raise Exception('No online RTP proxy client has been found')
            self.rtp_proxy_client = rtp_proxy_clients[int(random() * n)]
        else:
            self.rtp_proxy_client = global_config['rtp_proxy_client']
            if not self.rtp_proxy_client.online:
                raise Exception('No online RTP proxy client has been found')
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
        self.caller = _rtpps_side()
        self.callee = _rtpps_side()

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
            self.caller.update(self, '0.0.0.0', 0, self._start_recording, '', index, 'IP4', rname, result_callback, index)
            return
        self._start_recording(None, self, rname, result_callback, index)

    def _start_recording(self, result, rtpps, rname, result_callback, index):
        if rname == None:
            command = 'R %s %s %s' % ('%s-%d' % (self.call_id, index), self.from_tag, self.to_tag)
            return self.rtp_proxy_client.send_command(command, self.command_result, result_callback)
        command = 'C %s %s.a %s %s' % ('%s-%d' % (self.call_id, index), rname, self.from_tag, self.to_tag)
        return self.rtp_proxy_client.send_command(command, self._start_recording1, \
          (rname, result_callback, index))

    def _start_recording1(self, result, args):
        rname, result_callback, index = args
        command = 'C %s %s.o %s %s' % ('%s-%d' % (self.call_id, index), rname, self.to_tag, self.from_tag)
        return self.rtp_proxy_client.send_command(command, self.command_result, result_callback)

    def command_result(self, result, result_callback):
        #print '%s.command_result(%s)' % (id(self), result)
        if result_callback != None:
            result_callback(result)

    def delete(self):
        if self.rtp_proxy_client == None:
            return
        while self.max_index >= 0:
            command = 'D %s %s %s' % ('%s-%d' % (self.call_id, self.max_index), self.from_tag, self.to_tag)
            self.rtp_proxy_client.send_command(command)
            self.max_index -= 1
        self.rtp_proxy_client = None

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
            #print 'Rtp_proxy_session.__del__() from wrong thread, re-routing'
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
