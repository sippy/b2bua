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

from typing import Optional, Dict, Tuple
from threading import Thread
from asyncio import get_event_loop, all_tasks, new_event_loop, set_event_loop, CancelledError, \
  Queue as AsyncQueue, create_task
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from uuid import UUID
from websockets import WebSocketServerProtocol, ConnectionClosed, serve as ws_serve

from sippy.Core.EventDispatcher import ED2
from sippy.Network_server import Network_server, Network_server_opts, Remote_address
from sippy.Time.MonoTime import MonoTime

class Wss_server_opts(Network_server_opts):
    certfile: Optional[str] = None
    keyfile: Optional[str] = None

    def __init__(self, *args, certfile = None, keyfile = None, o = None):
        super().__init__(*args, o = o)
        if o != None:
            self.certfile, self.keyfile = o.certfile, o.keyfile
            return
        self.certfile = certfile
        self.keyfile = keyfile

class Wss_server(Thread, Network_server):
    transport = 'wss'
    daemon = True
    ssl_context: Optional[SSLContext] = None
    connections: Dict[UUID, Tuple[WebSocketServerProtocol, AsyncQueue]]

    def __init__(self, global_config, uopts:Wss_server_opts):
        Thread.__init__(self)
        Network_server.__init__(self, uopts)
        if self.uopts.certfile is not None:
            self.ssl_context = SSLContext(PROTOCOL_TLS_SERVER)
            self.ssl_context.load_cert_chain(self.uopts.certfile, self.uopts.keyfile)
        self.connections = {}
        self.start()

    async def monitor_queue(self):
        while True:
            item = await get_event_loop().run_in_executor(None, self.sendqueue.get)
            if item is None:
                for task in all_tasks():
                    task.cancel()
                break
            data, address = item
            uaddress = address[0]
            if uaddress not in self.connections:
                print(f'ERROR: Invalid address {uaddress=}')
                continue
            await self.connections[uaddress][1].put(data)

    async def sip_to_ws(self, queue:AsyncQueue, websocket:WebSocketServerProtocol):
        while True:
            item = await queue.get()
            await websocket.send(item)

    async def ws_to_sip(self, websocket):
        print(f'New connection {websocket.id=}')
        queue = AsyncQueue()
        sender = create_task(self.sip_to_ws(queue, websocket))
        conn_id = f'{websocket.id}.invalid'
        self.connections[conn_id] = (websocket, queue)
        if self.uopts.laddress[0] == '0.0.0.0':
            sock = websocket.transport.get_extra_info('socket')
            addr = sock.getsockname()
            ED2.callFromThread(self.set_laddress, addr)
        address = Remote_address(websocket.remote_address, self.transport)
        address.received = conn_id
        try:
            while True:
                data = await websocket.recv()
                rtime = MonoTime()
                ED2.callFromThread(self.handle_read, data, address, rtime)
        except ConnectionClosed:
            print(f'Connection {websocket.id} closed')
        finally:
            del self.connections[conn_id]
            sender.cancel()
            await sender

    async def async_run(self):
        start_server = ws_serve(
            self.ws_to_sip, self.uopts.laddress[0], self.uopts.laddress[1], ssl = self.ssl_context,
            subprotocols = ['sip']
        )
        server = await start_server
        await self.monitor_queue()
        server.close()
        await server.wait_closed()

    def addr2str(self, address):
        return f'{self.transport}:{address[0]}'

    def set_laddress(self, address):
        print(f'WSS server is listening on {address[0]}:{address[1]}')
        self.uopts.laddress = address

    def runFailed(self, exception):
        ED2.breakLoop(255)
        raise exception

    def run(self):
        loop = new_event_loop()
        set_event_loop(loop)
        try:
            loop.run_until_complete(self.async_run())
        except CancelledError:
            pass
        except OSError as ex:
            ED2.callFromThread(self.runFailed, ex)
        finally:
            loop.close()

if __name__ == '__main__':
    laddr = ('192.168.23.43', 9878)
    certfile = '/home/sobomax/server.crt'
    keyfile = '/home/sobomax/server.key'
    from sippy.SipRequest import SipRequest
    def data_callback(data, address, server, rtime):
        sr = SipRequest(data)
        print(f'Got {sr=} from {address=}')
        for rr in (100, 'Trying'), (666, 'Busy Here'):
            res = sr.genResponse(rr[0], rr[1])
            server.send_to(str(res), address)
        ED2.breakLoop()
    wopts = Wss_server_opts(laddr, data_callback, certfile = certfile, keyfile = keyfile)
    wserv = Wss_server(None, wopts)
    try:
        ED2.loop()
    finally:
        wserv.shutdown()
