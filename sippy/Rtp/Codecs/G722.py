from array import array

from G722 import G722

from ..Core.AudioChunk import AudioChunk, pcm16_from
from .GenCodec import GenCodec

class G722Codec(GenCodec):
    codec:G722
    srate:int = 8000
    default_br:int = 64000
    ptype:int = 9 # G.722
    ename:str = 'G722' # encoding name
    chunk_cls = AudioChunk

    def __init__(self):
        super().__init__()
        self.codec = G722(self.srate, self.default_br, use_numpy=False)

    def encode(self, chunk):
        pcm16 = pcm16_from(chunk.audio)
        return self.codec.encode(pcm16)

    def make_chunk(self, pcm16: array, srate: int):
        return self.chunk_cls(pcm16, srate)

    def decode(self, audio_enc:bytes, resample:bool=True, sample_rate:int=None):
        pcm16 = array('h', self.codec.decode(audio_enc))
        if sample_rate is None:
            sample_rate = self.out_srate
        chunk = self.make_chunk(pcm16, self.srate)
        if resample and sample_rate != self.srate:
            chunk.resample(sample_rate)
        return chunk

    def silence(self, nframes:int):
        pcm16 = array('h', [0]) * self.e2d_frames(nframes)
        return self.encode(pcm16)

    def e2d_frames(self, enframes:int, out_srate:int=None):
        #assert out_srate % self.srate == 0
        if out_srate is None:
            out_srate = self.out_srate
        return enframes * (1 if self.srate == 8000 else 2) * out_srate // self.srate

    def d2e_frames(self, dnframes:int, in_srate:int=None):
        #assert in_srate % self.srate == 0
        if in_srate is None:
            in_srate = self.out_srate
        return dnframes * self.srate // ((1 if self.srate == 8000 else 2) * in_srate)

    def e2t(self, frames:int) -> float:
        return (frames * 8) / self.default_br
