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

from typing import Optional, Tuple, List, Union
from queue import Queue
from abc import ABC, abstractmethod
from random import random, randint

from sippy.Core.Exceptions import dump_exception
from sippy.Time.MonoTime import MonoTime
from sippy.Time.Timeout import Timeout
from sippy.SipConf import MyPort

class Remote_address():
    transport: str
    address: Tuple[str, int]
    received: str

    def __init__(self, address:Tuple[str, int], transport:str):
        self.transport = transport
        self.address = address
        self.received = address[0]

    def __str__(self):
        return f'{self.transport}:{self.address[0]}:{self.address[1]}'

class Network_server_opts():
    laddress: Optional[Tuple[str, Union[int, callable, MyPort]]] = None
    data_callback: Optional[callable] = None
    direct_dispatch: bool = False
    ploss_out_rate: float = 0.0
    pdelay_out_max: float = 0.0
    ploss_in_rate: float = 0.0
    pdelay_in_max: float = 0.0

    def __init__(self, *args:Optional[Tuple[str, int]], o:Optional['Network_server_opts'] = None):
        if o != None:
            self.laddress, self.data_callback, self.direct_dispatch, \
              self.ploss_out_rate, self.pdelay_out_max, self.ploss_in_rate, \
              self.pdelay_in_max = o.laddress, o.data_callback, o.direct_dispatch, \
              o.ploss_out_rate, o.pdelay_out_max, o.ploss_in_rate, o.pdelay_in_max
            return
        self.laddress, self.data_callback = args

    def getCopy(self) -> 'Network_server_opts':
        return self.__class__(o = self)

    def isWildCard(self) -> bool:
        return False

class Network_server(ABC):
    transport: str
    uopts: Network_server_opts
    sendqueue: Queue
    stats: List[int]

    def __init__(self, uopts:Network_server_opts):
        self.uopts = uopts.getCopy()
        self.sendqueue = Queue()
        self.stats = [0, 0, 0]

    def getSIPaddr(self) -> Tuple[Tuple[str, int], int]:
        return (self.uopts.laddress, self.transport)

    def addr2str(self, address):
        return f'{self.transport}:{address[0]}:{address[1]}'

    def send_to(self, data:Union[bytes, str], address:object, delayed:bool = False):
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        if self.uopts.ploss_out_rate > 0.0 and not delayed:
            if random() < self.uopts.ploss_out_rate:
                return
        if self.uopts.pdelay_out_max > 0.0 and not delayed:
            pdelay = self.uopts.pdelay_out_max * random()
            Timeout(self.send_to, pdelay, 1, data, address, True)
            return
        self.sendqueue.put((data, address))
 
    def handle_read(self, data:bytes, address:Remote_address, rtime:MonoTime, delayed:bool = False):
        if len(data) > 0 and self.uopts.data_callback != None:
            self.stats[2] += 1
            if self.uopts.ploss_in_rate > 0.0 and not delayed:
                if random() < self.uopts.ploss_in_rate:
                    return
            if self.uopts.pdelay_in_max > 0.0 and not delayed:
                pdelay = self.uopts.pdelay_in_max * random()
                Timeout(self.handle_read, pdelay, 1, data, address, rtime.getOffsetCopy(pdelay), True)
                return
            try:
                self.uopts.data_callback(data, address, self, rtime)
            except Exception as ex:
                if isinstance(ex, SystemExit):
                    raise 
                dump_exception(f'{self.__class__}: unhandled exception when processing incoming data')

    @abstractmethod
    def join(self):
        pass

    def shutdown(self):
        self.sendqueue.put(None)
        self.join()
        self.uopts.data_callback = None

class PortAllocationError(Exception): pass

class RTP_port_allocator():
    min_port: int
    max_port: int

    def __init__(self, min_port:Optional[int]=None, max_port:Optional[int]=None):
        if min_port is None: min_port = 1024
        if max_port is None: max_port = 65535
        if min_port % 2 != 0:
            min_port += 1
        assert min_port <= max_port, f'min_port={min_port} > max_port={max_port}'
        self.min_port = min_port
        self.max_port = max_port

    def __call__(self, ntry: int) -> int:
        rlen = self.max_port - self.min_port
        if ntry > (rlen // 2):
            raise PortAllocationError(f'No free ports available after {ntry} tries')
        port = self.min_port + (randint(0, rlen // 2) * 2)
        assert port <= self.max_port, f'port={port} > self.max_port={self.max_port}'
        return port
