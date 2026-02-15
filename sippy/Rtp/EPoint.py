from typing import Optional, Tuple
from uuid import uuid4, UUID
from threading import Lock
import errno

from rtpsynth.RtpServer import RtpQueueFullError, RtpServer
from sippy.Time.MonoTime import MonoTime

from .Core.AudioChunk import AudioChunk
from .Handlers import RTPHandlers
from .Params import RTPParams
from .Conf import RTPConf
from .Singletons import acquire_rtp_server, release_rtp_server

class RTPEPoint():
    debug: bool = False
    id: UUID
    dl_file = None
    firstframe = True
    rtp_params:RTPParams
    state_lock: Lock
    handlers: RTPHandlers
    _rtp_server: Optional[RtpServer]
    def __init__(self, rc:RTPConf, rtp_params:RTPParams, audio_in:callable,
                 handlers:RTPHandlers=None):
        self.id = uuid4()
        self.rtp_params = rtp_params
        self.handlers = handlers or RTPHandlers()
        self._palloc = rc.palloc
        self._rtp_server = None
        self.state_lock = Lock()
        self.writer = None
        self.rsess = self.make_rtp_instream(rtp_params, audio_in)
        rserv_opts = self.make_udp_server_opts(rtp_params)
        self.rserv = self.make_udp_server(rserv_opts)
        if self.rtp_params.rtp_target is not None:
            self.writer_setup()

    def make_writer(self, rtp_params:RTPParams):
        return self.handlers.writer_cls(rtp_params)

    def make_rtp_instream(self, rtp_params:RTPParams, audio_in:callable):
        return self.handlers.rtp_instream_cls(rtp_params, audio_in)

    def make_udp_server_opts(self, rtp_params:RTPParams):
        palloc = self._palloc if rtp_params.rtp_lport == 0 else rtp_params.rtp_lport
        return (rtp_params.rtp_laddr, palloc)

    def make_udp_server(self, rserv_opts):
        rtp_laddr, palloc = rserv_opts
        server_cls = self.handlers.rtp_server_cls
        rtp_server = acquire_rtp_server(server_cls)
        channel = None
        self._rtp_server = rtp_server
        try:
            channel = self._bind_channel(rtp_server, rtp_laddr, palloc)
            target = self.rtp_params.rtp_target
            if target is not None:
                channel.set_target(target[0], target[1])
            return channel
        except Exception:
            release_rtp_server(rtp_server)
            self._rtp_server = None
            if channel is not None:
                channel.close()
            raise

    def _create_channel(self, rtp_server:RtpServer, bind_host:str, bind_port:int):
        bind_family = self.rtp_params.rtp_family
        ch_kwargs = dict(pkt_in=self.rtp_received, bind_host=bind_host, bind_port=bind_port)
        ch = rtp_server.create_channel(bind_family=bind_family, **ch_kwargs)
        self.rtp_params.rtp_lport = bind_port
        return ch

    def _bind_channel(self, rtp_server:RtpServer, rtp_laddr:str, palloc, preferred_port:int=None):
        if preferred_port is not None:
            try:
                return self._create_channel(rtp_server, rtp_laddr, preferred_port)
            except OSError as ex:
                if ex.errno != errno.EADDRINUSE:
                    raise
        if callable(palloc):
            ntry = -1
            while True:
                ntry += 1
                bind_port = int(palloc(ntry))
                try:
                    return self._create_channel(rtp_server, rtp_laddr, bind_port)
                except OSError as ex:
                    if ex.errno == errno.EADDRINUSE:
                        continue
                    raise
        return self._create_channel(rtp_server, rtp_laddr, int(palloc))

    def _swap_channel(self, old_channel, rtp_params:RTPParams):
        with self.state_lock:
            rtp_server = self._rtp_server
            if rtp_server is None or self.rserv is not old_channel:
                return
        rtp_laddr, palloc = self.make_udp_server_opts(rtp_params)
        preferred_port = old_channel.local_addr[1]
        new_channel = self._bind_channel(rtp_server, rtp_laddr, palloc, preferred_port=preferred_port)
        target = rtp_params.rtp_target
        if target is not None:
            new_channel.set_target(target[0], target[1])
        with self.state_lock:
            if self._rtp_server is None or self.rserv is not old_channel:
                new_channel.close()
                return
            self.rserv = new_channel
        old_channel.close()

    def writer_setup(self):
        assert self.writer is None
        writer = self.make_writer(self.rtp_params)
        writer.set_pkt_send_f(self.send_pkt)
        if self.dl_file is not None:
            writer.enable_datalog(self.dl_file)
        writer.start()
        self.writer = writer

    def send_pkt(self, pkt):
        with self.state_lock:
            channel = self.rserv
        assert channel is not None
        try:
            channel.send_pkt(pkt)
        except RtpQueueFullError:
            return

    def rtp_received(self, data, address, rtime_ns=None):
        #self.dprint(f"RTP.Ingest.rtp_received: len(data) = {len(data)}")
        if rtime_ns is None:
            rtime = MonoTime().monot
        else:
            rtime = rtime_ns / 1_000_000_000.0
        with self.state_lock:
            target = self.rtp_params.rtp_target
            if target is not None and address != target:
                if self.debug:
                    print(f"InfernRTPIngest.rtp_received: address mismatch {address=} {self.rtp_params.rtp_target=}")
                return
        self.rsess.rtp_received(data, address, rtime)

    def update(self, rtp_params:RTPParams):
        old_writer = None
        need_new_writer = False
        target_changed = False
        proto_changed = False
        with self.state_lock:
            target_changed = self.rtp_params.rtp_target != rtp_params.rtp_target
            proto_changed = self.rtp_params.rtp_proto != rtp_params.rtp_proto
            self.rtp_params.rtp_proto = rtp_params.rtp_proto
            self.rtp_params.rtp_target = rtp_params.rtp_target
            ptime_changed = self.rtp_params.out_ptime != rtp_params.out_ptime
            self.rtp_params.out_ptime = rtp_params.out_ptime
            self.rtp_params.out_sr = rtp_params.out_sr
            self.rtp_params.codec = rtp_params.codec
            channel = self.rserv
            if self.rtp_params.rtp_target is None:
                old_writer = self.writer
                self.writer = None
            elif self.writer is None:
                need_new_writer = True
            elif ptime_changed or proto_changed:
                old_writer = self.writer
                self.writer = None
                need_new_writer = True
        if old_writer is not None:
            old_writer.end()
            old_writer.join()
        if proto_changed and channel is not None:
            self._swap_channel(channel, rtp_params)
        elif target_changed and channel is not None and self.rtp_params.rtp_target is not None:
            target = self.rtp_params.rtp_target
            channel.set_target(target[0], target[1])
        if need_new_writer:
            new_writer = self.make_writer(rtp_params)
            new_writer.set_pkt_send_f(self.send_pkt)
            if self.dl_file is not None:
                new_writer.enable_datalog(self.dl_file)
            new_writer.start()
            with self.state_lock:
                if self.rserv is None or self.rtp_params.rtp_target is None:
                    # RTP endpoint has been shut down while swapping writer.
                    new_writer.end()
                    new_writer.join()
                else:
                    self.writer = new_writer
        self.rsess.stream_update()

    def connect(self, ain:callable):
        self.rsess.stream_connect(ain)

    def shutdown(self):
        with self.state_lock:
            writer, channel, rtp_server = self.writer, self.rserv, self._rtp_server
            self.writer, self._rtp_server = (None, None)
        if writer is not None:
            writer.end()
            writer.join()
        with self.state_lock:
            self.rserv = None
        if channel is not None:
            channel.close()
        if rtp_server is not None:
            release_rtp_server(rtp_server)

    def __del__(self):
        if self.debug:
            print('RTP.EPoint.__del__')

    def soundout(self, chunk:AudioChunk):
        if self.firstframe:
            if self.debug:
                nframes = chunk.nframes if hasattr(chunk, 'nframes') else len(chunk.audio)
                print(f'RTP.EPoint.soundout[{str(self.id)[:6]}]: {nframes}')
            self.firstframe = False
        with self.state_lock:
            if self.writer is None: return
            return self.writer.soundout(chunk)
