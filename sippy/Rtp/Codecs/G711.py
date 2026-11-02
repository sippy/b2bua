from array import array

from rtpsynth.RtpUtils import linear2ulaw, ulaw2linear, linear2alaw, alaw2linear

from ..Core.AudioChunk import AudioChunk, pcm16_from
from .GenCodec import GenCodec


class G711Codec(GenCodec):
    ptype = 0 # G.711u
    ename = 'PCMU'
    chunk_cls = AudioChunk
    _linear_to_encoded = staticmethod(linear2ulaw)
    _encoded_to_linear = staticmethod(ulaw2linear)
    _silence_byte = b'\xff'

    def encode(self, chunk):
        pcm16 = pcm16_from(chunk.audio)
        return self._linear_to_encoded(pcm16)

    def make_chunk(self, pcm16: array, srate: int):
        return self.chunk_cls(pcm16, srate)

    def decode(self, ulaw_bytes:bytes, resample:bool=True, sample_rate:int=None):
        pcm16 = self._encoded_to_linear(ulaw_bytes)
        if sample_rate is None:
            sample_rate = self.out_srate
        chunk = self.make_chunk(pcm16, self.srate)
        if resample and sample_rate != self.srate:
            chunk.resample(sample_rate)
        return chunk

    def e2d_frames(self, enframes:int, out_srate:int=None):
        if out_srate is None:
            out_srate = self.out_srate
        assert out_srate % self.srate == 0
        return enframes * out_srate // self.srate

    def d2e_frames(self, dnframes:int, in_srate:int=None):
        if in_srate is None:
            in_srate = self.out_srate
        assert in_srate % self.srate == 0
        return dnframes * self.srate // in_srate

    def silence(self, nframes:int):
        return self._silence_byte * nframes


class G711ALawCodec(G711Codec):
    """G.711 A-law, sharing PCM conversion and frame accounting with PCMU."""
    ptype = 8
    ename = 'PCMA'
    _linear_to_encoded = staticmethod(linear2alaw)
    _encoded_to_linear = staticmethod(alaw2linear)
    _silence_byte = b'\xd5'
