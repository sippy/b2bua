import sys
import threading
import wave
from array import array

from sippy.Rtp.Core.AudioChunk import AudioChunk
from sippy.Rtp.OutputWorker import RTPOutputWorker
from sippy.Rtp.Params import RTPParams
from sippy.Rtp.Codecs.G711 import G711Codec
from sippy.Rtp.Codecs.G722 import G722Codec


def parse_target(value: str):
    host, port = value.rsplit(':', 1)
    return host, int(port)


def _clamp16(val: int) -> int:
    if val > 32767:
        return 32767
    if val < -32768:
        return -32768
    return val


def _bytes_to_pcm16(raw: bytes, sampwidth: int, channels: int) -> array:
    if channels not in (1, 2):
        raise ValueError(f'Unsupported channel count: {channels}')
    if sampwidth == 2:
        pcm = array('h')
        pcm.frombytes(raw)
        if sys.byteorder == 'big':
            pcm.byteswap()
        if channels == 1:
            return pcm
        out = array('h')
        for i in range(0, len(pcm) - 1, 2):
            out.append(_clamp16((pcm[i] + pcm[i + 1]) // 2))
        return out
    if sampwidth == 1:
        out = array('h')
        if channels == 1:
            for b in raw:
                out.append((b - 128) << 8)
        else:
            for i in range(0, len(raw) - 1, 2):
                s0 = (raw[i] - 128) << 8
                s1 = (raw[i + 1] - 128) << 8
                out.append((s0 + s1) // 2)
        return out
    if sampwidth in (3, 4):
        out = array('h')
        shift = (sampwidth - 2) * 8
        step = sampwidth * channels
        for off in range(0, len(raw) - (step - 1), step):
            s0 = int.from_bytes(raw[off:off + sampwidth], 'little', signed=True)
            if channels == 2:
                s1 = int.from_bytes(raw[off + sampwidth:off + 2 * sampwidth], 'little', signed=True)
                s0 = (s0 + s1) // 2
            if shift:
                s0 = s0 >> shift
            out.append(_clamp16(s0))
        return out
    raise ValueError(f'Unsupported sample width: {sampwidth}')


class WaveChunker:
    def __init__(self, wav_path: str, frames_per_chunk: int):
        self.wav_path = wav_path
        self.frames_per_chunk = frames_per_chunk
        self._wf = wave.open(wav_path, 'rb')
        self._lock = threading.Lock()
        self._eof = False
        self.channels = self._wf.getnchannels()
        self.sample_width = self._wf.getsampwidth()
        self.rate = self._wf.getframerate()

    def close(self):
        self._wf.close()

    def next_chunk(self):
        with self._lock:
            if self._eof:
                return None
            raw = self._wf.readframes(self.frames_per_chunk)
            if not raw:
                self._eof = True
                return None
            pcm16 = _bytes_to_pcm16(raw, self.sample_width, self.channels)
            return AudioChunk(pcm16, self.rate)


class FeedingRTPParams(RTPParams):
    def __init__(self, rtp_target, on_drain, out_ptime=RTPParams.default_ptime,
                 out_sr=RTPParams.default_sr):
        super().__init__(rtp_target, out_ptime=out_ptime, out_sr=out_sr)
        assert callable(on_drain)
        self.on_drain = on_drain


class FeedingOutputWorker(RTPOutputWorker):
    def __init__(self, rtp_params: RTPParams):
        super().__init__(rtp_params)
        assert callable(rtp_params.on_drain)
        self._on_drain = rtp_params.on_drain

    def update_frm_ctrs(self, rcvd_inc=0, prcsd_inc=0):
        res = super().update_frm_ctrs(rcvd_inc, prcsd_inc)
        if res[0] == res[1]:
            self._on_drain(self)
        return res


def codec_from_name(name: str):
    lname = name.lower()
    if lname == 'g711':
        return G711Codec
    if lname == 'g722':
        return G722Codec
    raise ValueError(f'Unsupported codec: {name}')
