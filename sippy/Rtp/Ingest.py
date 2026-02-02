from typing import Optional, Union
from threading import Lock

from rtpsynth.RtpJBuf import RtpJBuf, RTPFrameType, RTPParseError

from .Codecs.GenCodec import GenCodec
from .Params import RTPParams


class RTPInStream():
    debug = False
    out_buffer: bytes = b''
    ob_rtime: float = 0.0
    out_chunk_sz_samples: int
    jb_size: int = 8
    last_output_lseq: Optional[int] = None
    codec: GenCodec
    npkts: int = 0
    def __init__(self, rtp_params:RTPParams, audio_in:callable):
        self.jbuf = RtpJBuf(self.jb_size)
        self.codec = rtp_params.codec()
        self.codec.out_srate = rtp_params.out_sr
        self.out_chunk_sz_samples = int(rtp_params.out_sr / 10) # 0.1s
        self.ring_lock = Lock()
        self.audio_in = audio_in

    def rtp_received(self, data, address, rtime):
        #self.dprint(f"RTP.Ingest.rtp_received: len(data) = {len(data)}")
        with self.ring_lock:
            self.pkt_proc(data, address, rtime)

    def stream_update(self):
        with self.ring_lock:
            self.jbuf = RtpJBuf(self.jb_size)
            self.last_output_lseq = None
            return

    def stream_connect(self, audio_in:callable):
        with self.ring_lock:
            self.audio_in = audio_in

    def pkt_proc(self, data, address, rtime):
        try:
            res = self.jbuf.udp_in(data, rtime)
        except RTPParseError as e:
            self.dprint(f"RTPParseError: {e}")
            return
        self.npkts += 1
        if self.npkts == 1:
            self.dprint(f"address={address}, rtime={rtime}, len(data) = {len(data)} data={data[:40]}")
        for pkt in res:
            if pkt.content.type == RTPFrameType.ERS:
                self.dprint(f"ERS packet received {pkt.content.lseq_start=}, {pkt.content.lseq_end=} {pkt.content.ts_diff=}")
                self.last_output_lseq = pkt.content.lseq_end
                rtp_data = self.codec.silence(pkt.content.ts_diff)
            else:
                if self.npkts < 10:
                    self.dprint(f"{pkt.content.frame.rtp.lseq=}")
                assert self.last_output_lseq is None or pkt.content.frame.rtp.lseq == self.last_output_lseq + 1
                self.last_output_lseq = pkt.content.frame.rtp.lseq
                if self.npkts < 10:
                    self.dprint(f"{len(pkt.rtp_data)=}, {type(pkt.rtp_data)=}")
                rtp_data = pkt.rtp_data
                new_rtime = pkt.opaque - self.codec.e2t(len(self.out_buffer))
                self.ob_rtime = new_rtime
            self.out_buffer += rtp_data
        while self.codec.e2d_frames(len(self.out_buffer)) >= self.out_chunk_sz_samples:
            decode_samples = self.codec.d2e_frames(self.out_chunk_sz_samples)
            chunk = self.codec.decode(self.out_buffer[:decode_samples])
            chunk.rtime = self.ob_rtime
            self.ob_rtime += self.codec.e2t(decode_samples)
            self.out_buffer = self.out_buffer[decode_samples:]
            self.audio_in(chunk)
        if self.npkts < 10 and len(res) > 0:
            self.dprint(f"{res=}")

    def dprint(self, *args):
        if self.debug:
            print(*args)
