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
from hashlib import md5
from random import random
from time import time
try:
    from _thread import get_ident
except ImportError:
    from thread import get_ident

from sippy.Core.EventDispatcher import ED2
from sippy.Exceptions.RtpProxyError import RtpProxyError
from sippy.Rtp_proxy.Cmd.sequencer import Rtp_proxy_cmd_sequencer
from sippy.Rtp_proxy.Session.side import _rtpps_side
from sippy.Rtp_proxy.Session.update import update_params

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
      notify_tag = None):
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
        self.notify_socket = self.rtp_proxy_client.notify_socket
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

    def start_recording(self, rname=None, result_callback=None, index=0, rflags=None, only_a=False):
        def make_command(side):
            t1 = self.from_tag if side == 'a' else self.to_tag
            t2 = self.to_tag if side == 'a' else self.from_tag
            if rname is None:
                assert side == 'a'
                return f'R{rflags} {self.call_id}-{index} {t1} {t2}'
            return f'C{rflags} {self.call_id}-{index} {rname}.{side} {t1} {t2}'
        next_stage = result_callback if (only_a or rname is None) \
          else partial(self._start_recording_o, make_command, result_callback)
        first_stage = partial(self._start_recording_a, make_command, next_stage)
        if not self.caller.session_exists:
            up = update_params()
            up.rtpps = self
            up.index = index
            up.result_callback = first_stage
            self.caller.update(up)
            return
        first_stage(result='dummy', rtpps=None)

    def _start_recording_a(self, make_command, next_stage, result, rtpps):
        if result is None:
            return next_stage(None)
        command = make_command('a')
        return self.rtpp_seq.send_command(command, next_stage)

    def _start_recording_o(self, make_command, result_callback, result):
        if result is None:
            return result_callback(None)
        command = make_command('o')
        return self.rtpp_seq.send_command(command, result_callback)

    def delete(self):
        if self.rtp_proxy_client == None:
            return
        while self.max_index >= 0:
            command = 'D %s %s %s' % ('%s-%d' % (self.call_id, self.max_index), self.from_tag, self.to_tag)
            self.rtpp_seq.send_command(command)
            self.max_index -= 1
        self.rtp_proxy_client = None
        self.rtpp_seq.delete()

    def on_caller_sdp_change(self, sdp_body, result_callback):
        self.caller._on_sdp_change(self, sdp_body, result_callback)

    def on_callee_sdp_change(self, sdp_body, result_callback):
        self.callee._on_sdp_change(self, sdp_body, result_callback)

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
    from sippy.Rtp_proxy.client import Rtp_proxy_client
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
