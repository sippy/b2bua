"""Real native jitter-buffer erasure handling for both G.711 laws."""
from array import array
import struct
import unittest

from sippy.Rtp.Codecs.G711 import G711Codec, G711ALawCodec
from sippy.Rtp.Core.AudioChunk import AudioChunk
from sippy.Rtp.Ingest import RTPInStream
from sippy.Rtp.Params import RTPParams


class TestG711Ingest(unittest.TestCase):
    def test_exhaustive_native_parity(self):
        from rtpsynth.RtpUtils import linear2alaw, alaw2linear, linear2ulaw, ulaw2linear
        pcm = array('h', range(-32768, 32768))
        encoded = bytes(range(256))
        for codec_class, encode, decode in ((G711Codec, linear2ulaw, ulaw2linear),
                                             (G711ALawCodec, linear2alaw, alaw2linear)):
            with self.subTest(codec=codec_class.__name__):
                codec = codec_class()
                self.assertEqual(codec.encode(AudioChunk(pcm, 8000)), encode(pcm))
                self.assertEqual(codec.decode(encoded, resample=False).audio, decode(encoded))
                codec.out_srate = 16000
                self.assertEqual(codec.e2d_frames(160), 320)
                self.assertEqual(codec.d2e_frames(320), 160)
                self.assertEqual(codec.decode(encoded).samplerate, 16000)
                self.assertEqual(len(codec.decode(encoded).audio), 512)

    def test_native_packet_loss_and_resampling(self):
        for codec_class, silence_value in ((G711Codec, 0), (G711ALawCodec, 8)):
            for sample_rate in (8000, 16000):
                with self.subTest(codec=codec_class.__name__, sample_rate=sample_rate):
                    params = RTPParams(None, out_sr=sample_rate)
                    params.codec = codec_class
                    received = []
                    stream = RTPInStream(params, received.append)
                    erased = []
                    original_silence = stream.codec.silence

                    def record_erasure(nframes):
                        erased.append(nframes)
                        return original_silence(nframes)

                    stream.codec.silence = record_erasure
                    encoder = codec_class()
                    payload = encoder.encode(AudioChunk(array('h', [1000]) * 160, 8000))
                    for sequence in range(40):
                        if sequence == 5:
                            continue
                        packet = struct.pack('!BBHII', 0x80, encoder.ptype,
                                             sequence, sequence * 160, 1234) + payload
                        stream.rtp_received(packet, ('127.0.0.1', 4000), 100.0 + sequence * 0.02)
                    self.assertEqual(erased, [160])
                    self.assertTrue(received)
                    self.assertTrue(all(chunk.samplerate == sample_rate for chunk in received))
                    self.assertTrue(all(len(chunk.audio) == sample_rate // 10 for chunk in received))
                    combined = [value for chunk in received for value in chunk.audio]
                    self.assertGreaterEqual(combined.count(silence_value), sample_rate // 50 - 1)
                    self.assertGreater(max(combined), 900)


if __name__ == '__main__':
    unittest.main()
