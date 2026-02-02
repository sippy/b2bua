from __future__ import annotations

from array import array
from typing import Union
import sys

from rtpsynth.RtpUtils import resample_linear

PCM16Like = Union[array, bytes, bytearray, memoryview]

def pcm16_from(data: PCM16Like) -> array:
    if isinstance(data, array):
        if data.typecode != 'h':
            raise TypeError("PCM16 array must have typecode 'h'")
        return data
    else:
        mv = memoryview(data)
        if mv.format != 'h':
            mv = mv.cast('h')
        pcm = array('h', mv)
        if sys.byteorder == 'big':
            pcm.byteswap()
        return pcm

def pcm16_to_bytes(pcm: array) -> bytes:
    if sys.byteorder == 'big':
        pcm = array('h', pcm)
        pcm.byteswap()
    return pcm.tobytes()

class AudioChunk():
    debug: bool = False
    samplerate: int
    audio: array
    rtime: float | None = None
    def __init__(self, audio: PCM16Like, samplerate:int):
        self.audio = pcm16_from(audio)
        self.samplerate = samplerate

    def resample(self, sample_rate:int):
        assert sample_rate != self.samplerate
        self.audio = resample_linear(self.audio, self.samplerate, sample_rate)
        self.samplerate = sample_rate
        return self

    def duration(self):
        return len(self.audio) / self.samplerate

    def to_bytes(self) -> bytes:
        return pcm16_to_bytes(self.audio)

    @property
    def nframes(self) -> int:
        return len(self.audio)
