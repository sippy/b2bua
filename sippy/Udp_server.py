# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2024 Sippy Software, Inc. All rights reserved.
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

from __future__ import print_function

try: BrokenPipeError()
except NameError:
    class BrokenPipeError(Exception):
        pass

from errno import ECONNRESET, ENOTCONN, ESHUTDOWN, EWOULDBLOCK, ENOBUFS, EAGAIN, \
  EINTR, EBADF, EADDRINUSE
from datetime import datetime
from time import sleep, time
from threading import Thread
from sysconfig import get_platform
import socket

from sippy.Core.EventDispatcher import ED2
from sippy.Core.Exceptions import dump_exception
from sippy.Network_server import Network_server_opts, Network_server, Remote_address, \
  RTP_port_allocator
from sippy.Time.Timeout import Timeout
from sippy.Time.MonoTime import MonoTime
from sippy.SipConf import MyPort

class AsyncSender(Thread):
    daemon = True
    userv = None

    def __init__(self, userv):
        Thread.__init__(self)
        self.userv = userv
        self.start()

    def run(self):
        while True:
            wi = self.userv.sendqueue.get()
            if wi == None:
                # Shutdown request, relay it further
                self.userv.sendqueue.put(None)
                break
            data, address = wi
            try:
                ai = socket.getaddrinfo(address[0], None, self.userv.uopts.family)
            except:
                continue
            if self.userv.uopts.family == socket.AF_INET:
                address = (ai[0][4][0], address[1])
            else:
                address = (ai[0][4][0], address[1], ai[0][4][2], ai[0][4][3])
            for i in range(0, 20):
                try:
                    if self.userv.skt.sendto(data, address) == len(data):
                        break
                except socket.error as why:
                    if isinstance(why, BrokenPipeError):
                        self.userv = None
                        return
                    if why.errno not in (EWOULDBLOCK, ENOBUFS, EAGAIN):
                        break
                sleep(0.01)
        self.userv = None

class AsyncReceiver(Thread):
    daemon = True
    userv = None

    def __init__(self, userv):
        Thread.__init__(self)
        self.userv = userv
        self.start()

    def run(self):
        maxemptydata = 100
        while True:
            try:
                data, address = self.userv.skt.recvfrom(8192)
                if not data and address == None:
                    # Ugly hack to detect socket being closed under us on Linux.
                    # The problem is that even call on non-closed socket can
                    # sometimes return empty data buffer, making AsyncReceiver
                    # to exit prematurely.
                    maxemptydata -= 1
                    if maxemptydata == 0:
                        break
                    continue
                else:
                    maxemptydata = 100
                rtime = MonoTime()
            except socket.error as why:
                if why.errno in (ECONNRESET, ENOTCONN, ESHUTDOWN, EBADF):
                    break
                if why.errno in (EINTR,):
                    continue
                dump_exception('Udp_server[%d]: unhandled exception when receiving incoming data' % self.my_pid)
                continue
            except Exception:
                dump_exception('Udp_server[%d]: unhandled exception when receiving incoming data' % self.my_pid)
                sleep(1)
                continue
            if self.userv.uopts.family == socket.AF_INET6:
                address = ('[%s]' % address[0], address[1])
            if not self.userv.uopts.direct_dispatch:
                address = Remote_address(address, self.userv.transport)
                ED2.callFromThread(self.userv.handle_read, data, address, rtime)
            else:
                self.userv.handle_read(data, address, rtime)
        self.userv = None

_DEFAULT_FLAGS = socket.SO_REUSEADDR
if hasattr(socket, 'SO_REUSEPORT'):
    _DEFAULT_FLAGS |= socket.SO_REUSEPORT
_DEFAULT_NWORKERS = 3

class Udp_server_opts(Network_server_opts):
    family = None
    flags = _DEFAULT_FLAGS
    nworkers = _DEFAULT_NWORKERS

    def __init__(self, *args, family = None, o = None):
        super().__init__(*args, o=o)
        if o != None:
            self.family = o.family
            return
        if family == None:
            if self.laddress != None and self.laddress[0].startswith('['):
                family = socket.AF_INET6
                self.laddress = (self.laddress[0][1:-1], self.laddress[1])
            else:
                family = socket.AF_INET
        self.family = family

    def getSockOpts(self):
        sockopts = []
        if self.family == socket.AF_INET6 and self.isWildCard():
            sockopts.append((socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1))
        if (self.flags & socket.SO_REUSEADDR) != 0:
            sockopts.append((socket.SOL_SOCKET, socket.SO_REUSEADDR, 1))
        if self.nworkers > 1 and hasattr(socket, 'SO_REUSEPORT') and \
          (self.flags & socket.SO_REUSEPORT) != 0:
            sockopts.append((socket.SOL_SOCKET, socket.SO_REUSEPORT, 1))
        return sockopts

    def isWildCard(self):
        if (self.family, self.laddress[0]) in ((socket.AF_INET, '0.0.0.0'), \
          (socket.AF_INET6, '::')):
            return True
        return False

class Udp_server(Network_server):
    transport = 'udp'
    skt = None
    close_on_shutdown = get_platform().startswith('macosx-')
    asenders = None
    areceivers = None

    def __init__(self, global_config, uopts):
        super().__init__(uopts)
        self.skt = socket.socket(self.uopts.family, socket.SOCK_DGRAM)
        if self.uopts.laddress != None:
            ai = socket.getaddrinfo(self.uopts.laddress[0], None, self.uopts.family)
            if self.uopts.family == socket.AF_INET:
                address = (ai[0][4][0], self.uopts.laddress[1])
            else:
                address = (ai[0][4][0], self.uopts.laddress[1], ai[0][4][2], ai[0][4][3])
            for so_val in self.uopts.getSockOpts():
                self.skt.setsockopt(*so_val)
            if isinstance(address[1], MyPort):
                # XXX with some python 3.10 version I am getting
                # TypeError: 'MyPort' object cannot be interpreted as an integer
                # might be something inside socket.bind?
                address = (address[0], int(address[1]))
            if not callable(address[1]):
                self.skt.bind(address)
            else:
                ntry = -1
                for ntry in iter(lambda: ntry + 1, -1):
                    try_address = (address[0], address[1](ntry))
                    try: self.skt.bind(try_address)
                    except OSError as ex:
                        if ex.errno != EADDRINUSE:
                            raise
                    else:
                        self.uopts.laddress = try_address
                        break
            if self.uopts.laddress[1] == 0:
                self.uopts.laddress = self.skt.getsockname()
        self.asenders = []
        self.areceivers = []
        for i in range(0, self.uopts.nworkers):
            self.asenders.append(AsyncSender(self))
            self.areceivers.append(AsyncReceiver(self))

    def getSIPaddr(self):
        if self.uopts.family == socket.AF_INET:
            return super().getSIPaddr()
        return (('[%s]' % self.uopts.laddress[0], self.uopts.laddress[1]), self.transport)

    def send_to(self, data, address, delayed = False):
        if not isinstance(address, tuple):
            raise Exception('Invalid address, not a tuple: %s' % str(address))
        addr, port = address
        if self.uopts.family == socket.AF_INET6:
            if not addr.startswith('['):
                raise Exception('Invalid IPv6 address: %s' % addr)
            address = (addr[1:-1], port)
        super().send_to(data, address, delayed)
 
    def shutdown(self):
        try:
            self.skt.shutdown(socket.SHUT_RDWR)
        except socket.error as e:
            if e.errno != ENOTCONN:
                dump_exception('exception in the self.skt.shutdown()')
        except Exception:
            dump_exception('exception in the self.skt.shutdown()')
            pass
        super().shutdown()

    def join(self):
        for worker in self.asenders: worker.join()
        if self.close_on_shutdown:
            self.skt.close()
        for worker in self.areceivers: worker.join()
        if not self.close_on_shutdown:
            self.skt.close()
        self.asenders = None
        self.areceivers = None

class self_test(object):
    from sys import exit
    npongs = 2
    ping_data = b'ping!'
    ping_data6 = b'ping6!'
    pong_laddr = None
    pong_laddr6 = None
    pong_data = b'pong!'
    pong_data6 = b'pong6!'
    ping_laddr = None
    ping_laddr6 = None
    ping_raddr = None
    ping_raddr6 = None
    pong_raddr = None
    pong_raddr6 = None

    def ping_received(self, data, ra, udp_server, rtime):
        if udp_server.uopts.family == socket.AF_INET:
            print('ping_received')
            if data != self.ping_data or ra.address != self.pong_raddr:
                print(data, ra.address, self.ping_data, self.pong_raddr)
                exit(1)
            udp_server.send_to(self.pong_data, ra.address)
        else:
            print('ping_received6')
            if data != self.ping_data6 or ra.address != self.pong_raddr6:
                print(data, ra.address, self.ping_data6, self.pong_raddr6)
                exit(1)
            udp_server.send_to(self.pong_data6, ra.address)

    def pong_received(self, data, ra, udp_server, rtime):
        if udp_server.uopts.family == socket.AF_INET:
            print('pong_received')
            if data != self.pong_data or ra.address != self.ping_raddr:
                print(data, ra.address, self.pong_data, self.ping_raddr)
                exit(1)
        else:
            print('pong_received6')
            if data != self.pong_data6 or ra.address != self.ping_raddr6:
                print(data, ra.address, self.pong_data6, self.ping_raddr6)
                exit(1)
        self.npongs -= 1
        if self.npongs == 0:
            ED2.breakLoop()

    def run(self):
        palloc = RTP_port_allocator()
        local_host = '127.0.0.1'
        local_host6 = '[::1]'
        self.ping_laddr = (local_host, 12345)
        self.pong_laddr = (local_host, palloc)
        self.ping_laddr6 = (local_host6, 0)
        self.pong_laddr6 = (local_host6, 54321)
        uopts_ping = Udp_server_opts(self.ping_laddr, self.ping_received)
        uopts_ping6 = Udp_server_opts(self.ping_laddr6, self.ping_received)
        uopts_pong = Udp_server_opts(self.pong_laddr, self.pong_received)
        uopts_pong6 = Udp_server_opts(self.pong_laddr6, self.pong_received)
        udp_server_ping = Udp_server({}, uopts_ping)
        udp_server_pong = Udp_server({}, uopts_pong)
        self.ping_raddr = udp_server_ping.getSIPaddr()[0]
        self.pong_raddr = udp_server_pong.getSIPaddr()[0]
        udp_server_pong.send_to(self.ping_data, self.ping_raddr)
        udp_server_ping6 = Udp_server({}, uopts_ping6)
        udp_server_pong6 = Udp_server({}, uopts_pong6)
        self.ping_raddr6 = udp_server_ping6.getSIPaddr()[0]
        self.pong_raddr6 = udp_server_pong6.getSIPaddr()[0]
        udp_server_pong6.send_to(self.ping_data6, self.ping_raddr6)
        ED2.loop()
        for us in (udp_server_ping, udp_server_pong, udp_server_ping6, udp_server_pong6):
            us.shutdown()

if __name__ == '__main__':
    self_test().run()
