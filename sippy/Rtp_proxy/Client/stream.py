# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2025 Sippy Software, Inc. All rights reserved.
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

from queue import Queue
import socket

from sippy.Math.recfilter import recfilter
from sippy.Core.EventDispatcher import ED2

from ...Rtp_proxy.cmd import Rtp_proxy_cmd
from .net import Rtp_proxy_client_net
from .Worker.external import RTPPLWorker_external as _RTPPLWorker

class Rtp_proxy_client_stream(Rtp_proxy_client_net):
    is_local = None
    wi = None
    nworkers = None
    nworkers_act = None
    workers = None
    delay_flt = None
    family = None
    sock_type = socket.SOCK_STREAM
    worker_class = _RTPPLWorker

    def __init__(self, global_config, address = '/var/run/rtpproxy.sock', \
      bind_address = None, nworkers = 1, family = socket.AF_UNIX):
        #print('Rtp_proxy_client_stream.__init__', address, bind_address, nworkers, family)
        if family == socket.AF_UNIX:
            self.is_local = True
            self.address = address
        else:
            self.is_local = False
            self.address = self.getdestbyaddr(address, family)
        self.family = family
        self.wi = Queue()
        self.nworkers = nworkers
        self.workers = []
        for i in range(0, self.nworkers):
            self.workers.append(self.worker_class(self))
        self.nworkers_act = i + 1
        self.delay_flt = recfilter(0.95, 0.25)

    def send_command(self, command, result_callback = None, *callback_parameters):
        if self.nworkers_act == 0:
            self.rtpp_class._reconnect(self, self.address)
        if isinstance(command, Rtp_proxy_cmd):
            command = str(command)
        elif not command.endswith('\n'):
            command += '\n'
        self.wi.put((command, result_callback, callback_parameters))

    def shutdown(self):
        self.wi.put(None)
        for rworker in self.workers:
            rworker.join()
        self.workers = None

    def register_delay(self, rtpc_delay):
        self.delay_flt.apply(rtpc_delay)

    def get_rtpc_delay(self):
        return self.delay_flt.lastval

def test(class_obj):
    class robj(object):
        rval = None
    r = robj()
    def display(res, ro, arg):
        print(res, arg)
        ro.rval = (res, arg)
        ED2.breakLoop()
    rc = class_obj({'_sip_address':'1.2.3.4'})
    rc.send_command('VF 123456', display, r, 'abcd')
    ED2.loop()
    rc.shutdown()
    assert(r.rval == (u'0', u'abcd'))
    print('passed')

if __name__ == '__main__':
    test(Rtp_proxy_client_stream)
