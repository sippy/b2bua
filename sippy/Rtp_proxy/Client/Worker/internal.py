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

from threading import Thread
from errno import EINTR
import socket

from sippy.Time.MonoTime import MonoTime
from sippy.Core.Exceptions import dump_exception
from sippy.Core.EventDispatcher import ED2

class RTPPLWorker_internal(Thread):
    daemon = True
    userv = None
    s = None

    def __init__(self, userv):
        Thread.__init__(self)
        self.userv = userv
        self.s = userv.address
        self.start()

    def send_raw(self, command, stime = None):
        #print('%s.send_raw(%s)' % (id(self), command))
        if stime == None:
            stime = MonoTime()
        while True:
            try:
                self.s.send(command.encode())
            except socket.error as why:
                if why.errno == EINTR:
                    continue
                raise why
            else: break
        while True:
            try:
                rval = self.s.recv(1024)
                if len(rval) == 0:
                    raise socket.error('Connection closed')
                rval = rval.decode('ascii').strip()
            except socket.error as why:
                if why.errno == EINTR:
                    continue
                raise why
            else: break
        rtpc_delay = stime.offsetFromNow()
        return (rval, rtpc_delay)

    def run(self):
        #print(self.run, 'enter')
        while True:
            #print(self.run, 'spin')
            wi = self.userv.wi.get()
            if wi == None:
                # Shutdown request, relay it further
                self.userv.wi.put(None)
            if wi == None:
                break
            command, result_callback, callback_parameters = wi
            try:
                data, rtpc_delay = self.send_raw(command)
                if len(data) == 0:
                    data, rtpc_delay = None, None
            except Exception as e:
                dump_exception('RTPPLWorker_internal: unhandled exception I/O RTPproxy')
                data, rtpc_delay = None, None
            if result_callback != None:
                ED2.callFromThread(result_callback, data, *callback_parameters)
            if rtpc_delay != None:
                ED2.callFromThread(self.userv.register_delay, rtpc_delay)
        self.userv = None
        self.s = None
