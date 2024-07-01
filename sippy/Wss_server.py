from typing import Optional, Dict, Tuple
from threading import Thread
from asyncio import get_event_loop, all_tasks, new_event_loop, set_event_loop, CancelledError, \
  Queue as AsyncQueue, create_task
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from uuid import UUID
from websockets import WebSocketServerProtocol, ConnectionClosed, serve as ws_serve

from sippy.Core.EventDispatcher import ED2
from sippy.Network_server import Network_server, Network_server_opts
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
            print(f'Got {item=}')
            if item is None:
                for task in all_tasks():
                    task.cancel()
                break
            data, address = item
            if not isinstance(address, UUID):
                print(Exception(f'Invalid address, not a UUID: {address=}'))
                continue
            await self.connections[address][1].put(data)

    async def sip_to_ws(self, queue:AsyncQueue, websocket:WebSocketServerProtocol):
        while True:
            item = await queue.get()
            await websocket.send(item)

    async def ws_to_sip(self, websocket, path):
        print(f'New connection {websocket.id=}')
        queue = AsyncQueue()
        sender = create_task(self.sip_to_ws(queue, websocket))
        self.connections[websocket.id] = (websocket, queue)
        try:
            while True:
                data = await websocket.recv()
                rtime = MonoTime()
                print(f'Got {data=} from {websocket.id=}')
                ED2.callFromThread(self.handle_read, data, websocket.id, rtime)
        except ConnectionClosed:
            print(f'Connection {websocket.id} closed')
        finally:
            del self.connections[websocket.id]
            sender.cancel()

    async def async_run(self):
        start_server = ws_serve(
            self.ws_to_sip, self.uopts.laddress[0], self.uopts.laddress[1], ssl = self.ssl_context,
            subprotocols = ['sip']
        )
        await start_server
        await self.monitor_queue()

    def run(self):
        loop = new_event_loop()
        set_event_loop(loop)
        try:
            loop.run_until_complete(self.async_run())
        except CancelledError:
            pass
        finally:
            loop.close()

if __name__ == '__main__':
    laddr = ('192.168.23.43', 9876)
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
    ED2.loop()
#    from time import sleep
#    sleep(120)
    wserv.shutdown()
