from collections import deque
from array import array
from typing import Deque, Optional
import queue
import threading
import wave

from rtpsynth.RtpSynth import RtpSynth

from .Codecs.GenCodec import GenCodec
from .Core.AudioChunk import AudioChunk
from .Params import RTPParams
from .Singletons import acquire_rtp_proc, release_rtp_proc


class RTPOutputWorker():
    data_queue: queue.Queue[AudioChunk]
    debug = False
    dl_ofname: str = None
    data_log: Optional[bytearray] = None
    pkg_send_f = None
    state_lock: threading.Lock = None
    frames_rcvd = 0
    frames_prcsd = 0
    has_ended = False
    has_started = False
    codec: GenCodec
    samplerate_out: int
    out_ft: int # in ms

    def __init__(self, rtp_params:RTPParams):
        self.data_queue = queue.Queue()
        self.codec = rtp_params.codec()
        self.samplerate_out = self.codec.srate
        self.state_lock = threading.Lock()
        self.out_ft = rtp_params.out_ptime
        self._period_ns = self.out_ft * 1_000_000
        self._out_pt = self.codec.ptype
        self._out_fsize = self.samplerate_out * self.out_ft // 1000
        self._out_psize = self.codec.d2e_frames(self._out_fsize)
        self._enc_buffer = b''
        self._pending_chunks: Deque[list[int]] = deque()
        self._stream_started = False
        self._rsynth = RtpSynth(self.codec.crate, self.out_ft)
        self._proc = acquire_rtp_proc()
        self._proc_channel = None

    def enable_datalog(self, dl_ofname):
        self.dl_ofname = dl_ofname
        self.data_log = bytearray()

    def set_pkt_send_f(self, pkt_send_f):
        self.pkt_send_f = pkt_send_f

    def start(self):
        self.state_lock.acquire()
        assert not self.has_started
        assert not self.has_ended
        self.has_started = True
        self.state_lock.release()
        self._ensure_proc_channel()

    def join(self, timeout=None):
        _ = timeout
        try:
            self._close_proc_channel()
        finally:
            if self._proc is not None:
                self._release_proc()

    def ended(self):
        self.state_lock.acquire()
        t = self.has_ended
        self.state_lock.release()
        return t

    def end(self):
        self.state_lock.acquire()
        self.has_ended = True
        self.state_lock.release()

    def update_frm_ctrs(self, rcvd_inc=0, prcsd_inc=0):
        self.state_lock.acquire()
        self.frames_rcvd += rcvd_inc
        self.frames_prcsd += prcsd_inc
        rval = (self.frames_rcvd, self.frames_prcsd)
        self.state_lock.release()
        return rval

    def get_frm_ctrs(self):
        self.state_lock.acquire()
        res = (self.frames_rcvd, self.frames_prcsd)
        self.state_lock.release()
        return res

    def soundout(self, chunk:AudioChunk):
        #print(f'soundout: {monotonic():4.3f}')
        #return (0, False)
        assert len(chunk.audio) > 0
        if self.debug or chunk.debug:
            print(f'len(chunk) = {len(chunk.audio)}')
        self.update_frm_ctrs(rcvd_inc=chunk.nframes)
        self.data_queue.put(chunk)
        return (self.data_queue.qsize(), False)

    def _ensure_proc_channel(self):
        assert not self.ended()
        assert self._proc is not None
        assert self._proc_channel is None or self._proc_channel.closed
        channel = self._proc.create_channel(proc_in=self._proc_in)
        self._proc_channel = channel

    def _close_proc_channel(self):
        channel = self._proc_channel
        assert channel is not None
        assert not channel.closed
        channel.close()
        assert channel.closed
        self._proc_channel = None

    def _release_proc(self):
        proc = self._proc
        self._proc = None
        assert proc is not None
        release_rtp_proc(proc)

    def _mark_processed_bytes(self, nbytes:int):
        while nbytes > 0 and len(self._pending_chunks) > 0:
            rem_bytes, chunk_nframes = self._pending_chunks[0]
            if rem_bytes > nbytes:
                self._pending_chunks[0][0] = rem_bytes - nbytes
                return
            nbytes -= rem_bytes
            self._pending_chunks.popleft()
            self.update_frm_ctrs(prcsd_inc=chunk_nframes)

    def _proc_in(self, now_ns:int, deadline_ns:int):
        if self.ended():
            return None

        if deadline_ns == 0:
            # initial call
            self.update_frm_ctrs()
            assert now_ns > 0
            deadline_ns = now_ns

        while len(self._enc_buffer) < self._out_psize:
            try:
                chunk = self.data_queue.get_nowait()
            except queue.Empty:
                break
            chunk_nframes = chunk.nframes
            if chunk.samplerate != self.samplerate_out:
                chunk.resample(self.samplerate_out)
            if self.data_log is not None:
                self.data_log.extend(chunk.to_bytes())
            chunk_ebytes = self.codec.d2e_frames(chunk_nframes)
            pad_nbytes = (-chunk_ebytes) % self._out_psize
            if pad_nbytes != 0:
                pad_nframes = self.codec.e2d_frames(pad_nbytes)
                assert pad_nframes > 0
                chunk.audio.extend(array('h', [0]) * pad_nframes)
            audio_enc = self.codec.encode(chunk)
            if len(audio_enc) > 0:
                self._enc_buffer += audio_enc
                self._pending_chunks.append([len(audio_enc), chunk_nframes])
            else:
                self.update_frm_ctrs(prcsd_inc=chunk_nframes)
            self._stream_started = True
            if self.debug or chunk.debug:
                print(f'{self}._proc_in: {len(self._enc_buffer)=}')

        if len(self._enc_buffer) >= self._out_psize:
            assert len(self._enc_buffer) % self._out_psize == 0
            packet = self._enc_buffer[:self._out_psize]
            self._enc_buffer = self._enc_buffer[self._out_psize:]
            pkt = self._rsynth.next_pkt(self._out_psize, self._out_pt, pload=packet)
            if self.pkt_send_f is not None:
                self.pkt_send_f(pkt)
            self._mark_processed_bytes(self._out_psize)
        elif self._stream_started:
            self._rsynth.skip(1)

        if self.ended():
            return None
        return deadline_ns + self._period_ns

    def __del__(self):
        if self.debug:
            print('RTPOutputWorker.__del__')
        if self._proc_channel is not None:
            if self._proc_channel.closed:
                self._proc_channel = None
            else:
                self._close_proc_channel()
        if self._proc is not None:
            self._release_proc()
        if self.data_log is None or self.dl_ofname is None:
            return
        with wave.open(self.dl_ofname, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.samplerate_out)
            wf.writeframes(self.data_log)
