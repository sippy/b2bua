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

import socket

from .stream import Rtp_proxy_client_stream, test
from .Worker.internal import RTPPLWorker_internal as _RTPPLWorker

try: from rtp.io import rtpproxy
except ModuleNotFoundError as ex: rtpproxy = ex

class Rtp_proxy_client_internal(Rtp_proxy_client_stream):
    failed = None if not isinstance(rtpproxy, Exception) else rtpproxy
    def __init__(self, global_config, nworkers = 1, nsetup_f = None, **kwargs):
        if Rtp_proxy_client_internal.failed is not None:
            raise Rtp_proxy_client_internal.failed
        self.is_local = True
        self.worker_class = _RTPPLWorker
        if 'extra_args' in kwargs:
            extra_args = kwargs['extra_args']
            modules = [x.split('=', 1) for x in extra_args if x.startswith('modules=')]
            if len(modules) > 0:
                modules = tuple(modules[0][1].split('+'))
                kwargs['extra_args'] = [x for x in extra_args if not x.startswith('modules=')]
                kwargs['modules'] = modules
        self.rtpp = rtpproxy(**kwargs)
        if nsetup_f is not None:
            nsetup_f(self.rtpp.rtpp_nsock, self.rtpp.rtpp_nsock_spec)
            self.notify_socket = self.rtpp.rtpp_nsock_spec
        Rtp_proxy_client_stream.__init__(self, global_config = global_config, \
          address = self.rtpp.rtpp_sock, bind_address = None, nworkers = nworkers, \
          family = socket.AF_UNIX)

    def _reconnect(self, *args, **kwargs):
        raise RuntimeError('Rtp_proxy_client_internal does not support reconnecting')

    def shutdown(self):
        Rtp_proxy_client_stream.shutdown(self)
        if self.rtpp:
            del self.rtpp
            self.rtpp = None

if __name__ == '__main__':
    test(Rtp_proxy_client_internal)
