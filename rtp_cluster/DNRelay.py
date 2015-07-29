# Copyright (c) 2015 Sippy Software, Inc. All rights reserved.
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

from threading import Thread, Condition
from errno import EINTR, EPIPE, ENOTCONN, ECONNRESET
import socket, select

import sys
sys.path.append('..')

from sippy.Cli_server_tcp import Cli_server_tcp

_MAX_RECURSE = 10

class _DNRLWorker(Thread):
    spath = None
    s = None
    poller = None
    wi_available = None
    wi = None
    sip_logger = None

    def __init__(self, spath, sip_logger):
        if spath.startswith('unix:'):
            spath = spath[5:]
        self.spath = spath
        self.sip_logger = sip_logger
        self.wi_available = Condition()
        self.wi = []
        Thread.__init__(self)
        self.setDaemon(True)
        self.start()

    def connect(self):
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.connect(self.spath)
        self.poller = select.poll()
        self.poller.register(self.s, select.POLLIN)

    def deliver_dnotify(self, dnstring, _recurse = 0):
        if self.s == None:
            self.connect()
        if _recurse > _MAX_RECURSE:
            raise Exception('Cannot reconnect: %s', self.spath)
        if not dnstring.endswith('\n'):
            dnstring += '\n'
        while True:
            try:
                self.s.send(dnstring)
                break
            except socket.error, why:
                if why[0] == EINTR:
                    continue
                elif why[0] in (EPIPE, ENOTCONN, ECONNRESET):
                    self.s = None
                    return self.deliver_dnotify(dnstring, _recurse + 1)
                raise why
        # Clean any incoming data on the socket
        if len(self.poller.poll(0)) > 0:
            try:
                self.s.recv(1024)
            except:
                pass
        return

    def run(self):
        while True:
            self.wi_available.acquire()
            while len(self.wi) == 0:
                self.wi_available.wait()
            wi = self.wi.pop(0)
            self.wi_available.release()
            if wi == None:
                # Shutdown request
                break
            try:
                self.deliver_dnotify(wi)
            except Exception, e:
                self.sip_logger.write('Cannot deliver notification "%s" to the "%s": %s' % \
                  (wi, self.spath, str(e)))
            else:
                self.sip_logger.write('notification "%s" delivered to the "%s"' % \
                  (wi, self.spath))
        self.sip_logger = None

    def send_dnotify(self, dnstring):
        self.wi_available.acquire()
        self.wi.append(dnstring)
        self.wi_available.notify()
        self.wi_available.release()

class DNRelay(object):
    clim = None
    workers = None
    dest_sprefix = None
    in_address = None
    sip_logger = None

    def __init__(self, dnconfig, sip_logger):
        self.workers = {}
        self.clim = Cli_server_tcp(self.recv_dnotify, dnconfig.in_address)
        self.clim.accept_list = []
        self.dest_sprefix = dnconfig.dest_sprefix
        self.in_address = dnconfig.in_address
        self.sip_logger = sip_logger

    def recv_dnotify(self, clim, dnstring):
        #print 'DNRelay.recv_dnotify(%s)' % dnstring
        if clim.raddr != None:
            self.sip_logger.write('disconnect notification from %s received on %s: "%s"' \
              % (str(clim.raddr), str(self.in_address), dnstring))
        else:
            self.sip_logger.write('disconnect notification received on %s: "%s"' \
              % (str(self.in_address), dnstring))
        ssufx, dnstring = dnstring.split(None, 1)
        spath = self.dest_sprefix + ssufx
        dnw = self.workers.get(spath, None)
        if dnw == None:
            dnw = _DNRLWorker(spath, self.sip_logger)
            self.workers[spath] = dnw
        self.sip_logger.write('forwarding notification to %s: "%s"', (spath, dnstring))
        dnw.send_dnotify(dnstring)

    def shutdown(self):
        for dnw in self.workers.itervalues():
            dnw.send_dnotify(None)
            dnw.join()
        self.clim.shutdown()
        self.sip_logger = None

    def cmpconfig(self, dnconfig):
        if dnconfig.dest_sprefix != self.dest_sprefix:
            return False
        if dnconfig.in_address != self.in_address:
            return False
        return True

    def allow_from(self, address):
        self.clim.accept_list.append(address[0])

    def disallow_from(self, address):
        self.clim.accept_list.remove(address[0])

    def get_allow_list(self):
        return tuple(self.clim.accept_list)

    def set_allow_list(self, accept_list):
        self.clim.accept_list = list(accept_list)
