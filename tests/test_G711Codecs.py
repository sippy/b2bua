"""Tests for G.711 codecs (PCMU and PCMA) using librtpsynth interfaces.

Tests encode/decode roundtrips, silence handling, resampling, and bulk comparisons
against native implementations.
"""

import unittest
import array
from array import array

from sippy.Rtp.Codecs.G711 import G711Codec, G711ALawCodec
from sippy.Rtp.Core.AudioChunk import AudioChunk, pcm16_from


class TestG711CodecPCMU(unittest.TestCase):
    """Tests for G.711 µ-law (PCMU) codec."""

    def setUp(self):
        self.codec = G711Codec()

    def test_ptype_zero(self):
        """Ensure PCMU has ptype 0."""
        self.assertEqual(self.codec.ptype, 0)

    def test_ename_pcmu(self):
        """Ensure PCMU has ename 'PCMU'."""
        self.assertEqual(self.codec.ename, 'PCMU')

    def test_srate_crate(self):
        """Ensure PCMU has correct sample and clock rates."""
        self.assertEqual(self.codec.srate, 8000)
        self.assertEqual(self.codec.crate, 8000)

    def test_rtpmap(self):
        """Test RTP map generation."""
        expected = 'rtpmap:0 PCMU/8000'
        self.assertEqual(self.codec.rtpmap(), expected)

    def test_silence_generation(self):
        """Test silence byte generation - should be 0xFF."""
        for nframes in [1, 5, 10, 20, 100]:
            with self.subTest(nframes=nframes):
                silence_bytes = self.codec.silence(nframes)
                self.assertEqual(len(silence_bytes), nframes)
                self.assertEqual(silence_bytes, bytes([0xFF] * nframes))

    def test_silence_decode(self):
        """Test silence decoding - should decode to 0."""
        nframes = 20
        silence_bytes = self.codec.silence(nframes)
        decoded = self.codec.decode(silence_bytes)
        self.assertEqual(decoded.samplerate, 8000)
        self.assertEqual(len(decoded.audio), nframes)
        # µ-law silence (0xFF) decodes to exactly 0
        for sample in decoded.audio:
            self.assertEqual(sample, 0)

    def test_encode_decode_roundtrip(self):
        """Test encode/decode roundtrip for various PCM values."""
        # Test canonical values (skip extreme values that have larger quantization)
        test_values = [0, 1, -1, 100, -100, 1000, -1000, 500, -500, 8192, -8192]

        for val in test_values:
            with self.subTest(value=val):
                pcm = array('h', [val])
                chunk = AudioChunk(pcm, 8000)

                # Encode
                encoded = self.codec.encode(chunk)
                self.assertEqual(len(encoded), 1)

                # Decode
                decoded = self.codec.decode(encoded)
                self.assertEqual(decoded.samplerate, 8000)
                self.assertEqual(len(decoded.audio), 1)

                # Check roundtrip (allowing for G.711 quantization)
                decoded_val = decoded.audio[0]
                # G.711 is lossy; check that decoded value is reasonably close
                error = abs(val - decoded_val)
                self.assertLessEqual(error, 500,
                    f"Quantization error too large for {val}: {error}")

    def test_bulk_encode_decode(self):
        """Test bulk encode/decode with multiple samples."""
        # Generate test data: 80 samples (10ms at 8kHz)
        n_samples = 80
        test_pcm = array('h', [i % 256 - 128 for i in range(n_samples)])
        chunk = AudioChunk(test_pcm, 8000)

        # Encode
        encoded = self.codec.encode(chunk)
        self.assertEqual(len(encoded), n_samples)

        # Decode
        decoded = self.codec.decode(encoded)
        self.assertEqual(decoded.samplerate, 8000)
        self.assertEqual(len(decoded.audio), n_samples)

        # Verify all samples decoded
        for i, (orig, dec) in enumerate(zip(test_pcm, decoded.audio)):
            with self.subTest(sample=i):
                # Allow for quantization error
                self.assertLessEqual(abs(orig - dec), 200)

    def test_resample_up(self):
        """Test resampling from 8kHz to 16kHz."""
        test_pcm = array('h', [i % 256 - 128 for i in range(80)])  # 10ms at 8kHz
        chunk = AudioChunk(test_pcm, 8000)

        encoded = self.codec.encode(chunk)
        decoded = self.codec.decode(encoded, resample=True, sample_rate=16000)

        self.assertEqual(decoded.samplerate, 16000)
        # 10ms at 8kHz = 80 samples, at 16kHz = 160 samples
        self.assertEqual(len(decoded.audio), 160)

    def test_resample_down(self):
        """Test resampling from 8kHz to 4kHz."""
        test_pcm = array('h', [i % 256 - 128 for i in range(80)])  # 10ms at 8kHz
        chunk = AudioChunk(test_pcm, 8000)

        encoded = self.codec.encode(chunk)
        decoded = self.codec.decode(encoded, resample=True, sample_rate=4000)

        self.assertEqual(decoded.samplerate, 4000)
        # 10ms at 8kHz = 80 samples, at 4kHz = 40 samples
        self.assertEqual(len(decoded.audio), 40)

    def test_e2d_frames(self):
        """Test encoded to decoded frames calculation."""
        enframes = 10
        decoded_frames = self.codec.e2d_frames(enframes)
        # 1 encoded frame = 1 sample at 8kHz
        self.assertEqual(decoded_frames, enframes)

        # Test with different output rate
        decoded_frames_16k = self.codec.e2d_frames(enframes, out_srate=16000)
        self.assertEqual(decoded_frames_16k, enframes * 2)

    def test_d2e_frames(self):
        """Test decoded to encoded frames calculation."""
        dnframes = 80
        encoded_frames = self.codec.d2e_frames(dnframes)
        self.assertEqual(encoded_frames, 80)

        encoded_frames_16k = self.codec.d2e_frames(dnframes, in_srate=16000)
        self.assertEqual(encoded_frames_16k, 40)

    def test_e2d_frames_d2e_frames_out_srate_default(self):
        """Regression: e2d_frames/d2e_frames must use out_srate default.

        Original GenCodec used self.out_srate as default, not self.crate.
        This ensures correct behavior when out_srate differs from srate.
        """
        self.codec.out_srate = 16000

        # e2d_frames: 160 encoded frames at out_srate=16000 -> 320 decoded samples
        self.assertEqual(self.codec.e2d_frames(160), 320)

        # d2e_frames: 320 decoded samples at out_srate=16000 -> 160 encoded frames
        self.assertEqual(self.codec.d2e_frames(320), 160)


class TestG711ALawCodecPCMA(unittest.TestCase):
    """Tests for G.711 A-law (PCMA) codec."""

    def setUp(self):
        self.codec = G711ALawCodec()

    def test_ptype_eight(self):
        """Ensure PCMA has ptype 8."""
        self.assertEqual(self.codec.ptype, 8)

    def test_ename_pcma(self):
        """Ensure PCMA has ename 'PCMA'."""
        self.assertEqual(self.codec.ename, 'PCMA')

    def test_srate_crate(self):
        """Ensure PCMA has correct sample and clock rates."""
        self.assertEqual(self.codec.srate, 8000)
        self.assertEqual(self.codec.crate, 8000)

    def test_rtpmap(self):
        """Test RTP map generation."""
        expected = 'rtpmap:8 PCMA/8000'
        self.assertEqual(self.codec.rtpmap(), expected)

    def test_silence_contract(self):
        """Test that PCMA silence is exactly 0xD5 per sample.

        Per the spec: "PCMA encoded silence 0xD5 per native clock sample"
        """
        for nframes in [1, 5, 10, 20, 100]:
            with self.subTest(nframes=nframes):
                silence_bytes = self.codec.silence(nframes)
                self.assertEqual(len(silence_bytes), nframes)
                self.assertEqual(silence_bytes, bytes([0xD5] * nframes))

    def test_silence_decode_plus8(self):
        """Test that silence decodes to +8 (not exactly 0).

        G.711 A-law 0xD5 decodes to +8 due to quantization, which is correct.
        """
        silence_bytes = self.codec.silence(10)
        decoded = self.codec.decode(silence_bytes)

        # All samples should be +8 (the G.711 quantization of silence)
        for i, sample in enumerate(decoded.audio):
            with self.subTest(sample_index=i):
                self.assertEqual(sample, 8,
                    f"Silence sample {i} should be 8, got {sample}")

    def test_silence_decode(self):
        """Test silence decoding - should decode to small values near 0."""
        nframes = 20
        silence_bytes = self.codec.silence(nframes)
        decoded = self.codec.decode(silence_bytes)
        self.assertEqual(decoded.samplerate, 8000)
        self.assertEqual(len(decoded.audio), nframes)
        # Silence should decode to small values (8 for A-law)
        for sample in decoded.audio:
            self.assertEqual(sample, 8)

    def test_encode_decode_roundtrip(self):
        """Test encode/decode roundtrip for various PCM values."""
        # Test canonical values (skip extreme values that have larger quantization)
        test_values = [0, 1, -1, 100, -100, 1000, -1000, 500, -500, 8192, -8192]

        for val in test_values:
            with self.subTest(value=val):
                pcm = array('h', [val])
                chunk = AudioChunk(pcm, 8000)

                # Encode
                encoded = self.codec.encode(chunk)
                self.assertEqual(len(encoded), 1)

                # Decode
                decoded = self.codec.decode(encoded)
                self.assertEqual(decoded.samplerate, 8000)
                self.assertEqual(len(decoded.audio), 1)

                # Check roundtrip (allowing for G.711 quantization)
                decoded_val = decoded.audio[0]
                # G.711 is lossy; check that decoded value is reasonably close
                error = abs(val - decoded_val)
                self.assertLessEqual(error, 500,
                    f"Quantization error too large for {val}: {error}")

    def test_bulk_encode_decode(self):
        """Test bulk encode/decode with multiple samples."""
        # Generate test data: 80 samples (10ms at 8kHz)
        n_samples = 80
        test_pcm = array('h', [i % 256 - 128 for i in range(n_samples)])
        chunk = AudioChunk(test_pcm, 8000)

        # Encode
        encoded = self.codec.encode(chunk)
        self.assertEqual(len(encoded), n_samples)

        # Decode
        decoded = self.codec.decode(encoded)
        self.assertEqual(decoded.samplerate, 8000)
        self.assertEqual(len(decoded.audio), n_samples)

        # Verify all samples decoded
        for i, (orig, dec) in enumerate(zip(test_pcm, decoded.audio)):
            with self.subTest(sample=i):
                # Allow for quantization error
                self.assertLessEqual(abs(orig - dec), 200)

    def test_resample_up(self):
        """Test resampling from 8kHz to 16kHz."""
        test_pcm = array('h', [i % 256 - 128 for i in range(80)])  # 10ms at 8kHz
        chunk = AudioChunk(test_pcm, 8000)

        encoded = self.codec.encode(chunk)
        decoded = self.codec.decode(encoded, resample=True, sample_rate=16000)

        self.assertEqual(decoded.samplerate, 16000)
        # 10ms at 8kHz = 80 samples, at 16kHz = 160 samples
        self.assertEqual(len(decoded.audio), 160)

    def test_resample_down(self):
        """Test resampling from 8kHz to 4kHz."""
        test_pcm = array('h', [i % 256 - 128 for i in range(80)])  # 10ms at 8kHz
        chunk = AudioChunk(test_pcm, 8000)

        encoded = self.codec.encode(chunk)
        decoded = self.codec.decode(encoded, resample=True, sample_rate=4000)

        self.assertEqual(decoded.samplerate, 4000)
        # 10ms at 8kHz = 80 samples, at 4kHz = 40 samples
        self.assertEqual(len(decoded.audio), 40)

    def test_e2d_frames(self):
        """Test encoded to decoded frames calculation."""
        enframes = 10
        decoded_frames = self.codec.e2d_frames(enframes)
        # 1 encoded frame = 1 sample at 8kHz
        self.assertEqual(decoded_frames, enframes)

        # Test with different output rate
        decoded_frames_16k = self.codec.e2d_frames(enframes, out_srate=16000)
        self.assertEqual(decoded_frames_16k, enframes * 2)

    def test_d2e_frames(self):
        """Test decoded to encoded frames calculation."""
        dnframes = 80
        encoded_frames = self.codec.d2e_frames(dnframes)
        self.assertEqual(encoded_frames, 80)

        encoded_frames_16k = self.codec.d2e_frames(dnframes, in_srate=16000)
        self.assertEqual(encoded_frames_16k, 40)

    def test_e2d_frames_d2e_frames_out_srate_default(self):
        """Regression: e2d_frames/d2e_frames must use out_srate default."""
        self.codec.out_srate = 16000
        self.assertEqual(self.codec.e2d_frames(160), 320)
        self.assertEqual(self.codec.d2e_frames(320), 160)

    def test_native_vs_resample_comparison(self):
        """Test native 8kHz vs resampled 16kHz encoding/decoding.

        Compares bulk encoding/decoding at native rate vs resampled rate.
        """
        # Generate test data with moderate values to avoid extreme quantization
        n_samples_8k = 800  # 100ms at 8kHz
        test_pcm_8k = array('h', [(i * 50) % 16384 - 8192 for i in range(n_samples_8k)])

        # Encode at native 8kHz
        chunk_8k = AudioChunk(test_pcm_8k, 8000)
        encoded_8k = self.codec.encode(chunk_8k)

        # Decode at native rate
        decoded_8k = self.codec.decode(encoded_8k, resample=False)
        self.assertEqual(decoded_8k.samplerate, 8000)
        self.assertEqual(len(decoded_8k.audio), n_samples_8k)

        # Decode at resampled 16kHz
        decoded_16k = self.codec.decode(encoded_8k, resample=True, sample_rate=16000)
        self.assertEqual(decoded_16k.samplerate, 16000)
        self.assertEqual(len(decoded_16k.audio), n_samples_8k * 2)

        # Verify native decode quality
        mse_8k = sum((a - b) ** 2 for a, b in zip(test_pcm_8k, decoded_8k.audio)) / len(test_pcm_8k)
        self.assertLess(mse_8k, 20000, f"MSE at 8kHz too high: {mse_8k}")


class TestPCMAEncodeDecodeVectors(unittest.TestCase):
    """Focused tests for PCMA encode/decode with known canonical vectors."""

    def setUp(self):
        self.codec = G711ALawCodec()

    def test_canonical_zero(self):
        """Test encoding/decoding of zero sample."""
        pcm = array('h', [0])
        chunk = AudioChunk(pcm, 8000)

        encoded = self.codec.encode(chunk)
        self.assertEqual(encoded, bytes([0xD5]))

        decoded = self.codec.decode(encoded)
        self.assertEqual(decoded.audio[0], 8)  # 0xD5 decodes to 8

    def test_canonical_positive(self):
        """Test encoding/decoding of positive samples."""
        test_cases = [
            (100, 0xD3),
            (500, 0xCA),
            (1000, 0xFA),
        ]

        for pcm_val, expected_enc in test_cases:
            with self.subTest(pcm_val=pcm_val):
                pcm = array('h', [pcm_val])
                chunk = AudioChunk(pcm, 8000)

                encoded = self.codec.encode(chunk)
                self.assertEqual(encoded, bytes([expected_enc]))

                decoded = self.codec.decode(encoded)
                # Check decoded value is close to original
                self.assertLessEqual(abs(pcm_val - decoded.audio[0]), 200)

    def test_canonical_negative(self):
        """Test encoding/decoding of negative samples."""
        test_cases = [
            (-100, 0x53),
            (-500, 0x4A),
            (-1000, 0x7A),
        ]

        for pcm_val, expected_enc in test_cases:
            with self.subTest(pcm_val=pcm_val):
                pcm = array('h', [pcm_val])
                chunk = AudioChunk(pcm, 8000)

                encoded = self.codec.encode(chunk)
                self.assertEqual(encoded, bytes([expected_enc]))

                decoded = self.codec.decode(encoded)
                # Check decoded value is close to original
                self.assertLessEqual(abs(pcm_val - decoded.audio[0]), 200)

    def test_full_scale_range(self):
        """Test encoding/decoding across full PCM range."""
        # Test at various points in the range (skip extreme values)
        test_points = [-8192, -4096, -2048, -1024, -512,
                       -256, -128, -64, -32, -16, -8, -4, -2, -1, 0,
                       1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048,
                       4096, 8192, 12288]

        for pcm_val in test_points:
            with self.subTest(pcm_val=pcm_val):
                pcm = array('h', [pcm_val])
                chunk = AudioChunk(pcm, 8000)

                encoded = self.codec.encode(chunk)
                self.assertEqual(len(encoded), 1)

                decoded = self.codec.decode(encoded)
                decoded_val = decoded.audio[0]

                # G.711 quantization error should be reasonable
                error = abs(pcm_val - decoded_val)
                self.assertLessEqual(error, 1000,
                    f"Quantization error too large for {pcm_val}: {error}")


class TestPCMAWithJitterBuffer(unittest.TestCase):
    """Tests for PCMA codec with jitter buffer simulation."""

    def setUp(self):
        self.codec = G711ALawCodec()

    def test_packet_loss_silence_insertion(self):
        """Test silence insertion for packet loss simulation.

        Simulates what happens in Ingest.pkt_proc when ERS packet is received.
        """
        # Simulate 50ms of packet loss (5 frames at 10ms each)
        ts_diff = 5  # 5 frames
        silence_bytes = self.codec.silence(ts_diff)

        self.assertEqual(len(silence_bytes), ts_diff)
        self.assertEqual(silence_bytes, bytes([0xD5] * ts_diff))

        # Decode and verify
        decoded = self.codec.decode(silence_bytes)
        self.assertEqual(decoded.samplerate, 8000)
        self.assertEqual(len(decoded.audio), ts_diff)

    def test_continuous_stream_with_losses(self):
        """Test continuous stream with simulated packet losses.

        Simulates a stream with occasional packet losses where silence
        is inserted.
        """
        # Simulate: 10ms packet, 10ms loss, 10ms packet, 20ms loss, 10ms packet
        # Each frame is 10ms = 80 samples at 8kHz, but silence() takes nframes in encoded bytes
        packets = [
            (array('h', list(range(80))), 1),   # 10ms data (80 samples)
            (None, 1),                           # 10ms silence (1 encoded byte)
            (array('h', list(range(80, 160))), 1),  # 10ms data
            (None, 2),                           # 20ms silence (2 encoded bytes)
            (array('h', list(range(160, 240))), 1),  # 10ms data
        ]

        result_chunks = []
        for pcm_data, n_frames in packets:
            if pcm_data is None:
                # Insert silence for packet loss
                silence_bytes = self.codec.silence(n_frames)
                chunk = self.codec.decode(silence_bytes)
            else:
                chunk = AudioChunk(pcm_data, 8000)
                encoded = self.codec.encode(chunk)
                chunk = self.codec.decode(encoded)
            result_chunks.append(chunk)

        # Verify we got all chunks
        self.assertEqual(len(result_chunks), 5)

        # Verify silence chunks have correct sample count (1 frame = 1 sample after decode)
        self.assertEqual(len(result_chunks[1].audio), 1)   # 10ms silence
        self.assertEqual(len(result_chunks[3].audio), 2)   # 20ms silence

        # Verify data chunks have correct sample count
        self.assertEqual(len(result_chunks[0].audio), 80)
        self.assertEqual(len(result_chunks[2].audio), 80)
        self.assertEqual(len(result_chunks[4].audio), 80)


class TestPCMURegression(unittest.TestCase):
    """Regression tests to ensure PCMU (G711Codec) still works correctly."""

    def setUp(self):
        self.codec = G711Codec()

    def test_ptype_zero(self):
        """Ensure PCMU still has ptype 0."""
        self.assertEqual(self.codec.ptype, 0)

    def test_ename_pcmu(self):
        """Ensure PCMU still has ename 'PCMU'."""
        self.assertEqual(self.codec.ename, 'PCMU')

    def test_silence_0xff(self):
        """Ensure PCMU silence is still 0xFF."""
        silence = self.codec.silence(10)
        self.assertEqual(silence, bytes([0xFF] * 10))

    def test_roundtrip(self):
        """Ensure PCMU encode/decode still works."""
        test_pcm = array('h', [0, 1000, -1000, 16384, -16384])
        chunk = AudioChunk(test_pcm, 8000)

        encoded = self.codec.encode(chunk)
        decoded = self.codec.decode(encoded)

        self.assertEqual(decoded.samplerate, 8000)
        self.assertEqual(len(decoded.audio), len(test_pcm))


class TestPCMAAndPCMUComparison(unittest.TestCase):
    """Compare PCMA and PCMU codecs."""

    def setUp(self):
        self.codec_pcma = G711ALawCodec()
        self.codec_pcmu = G711Codec()

    def test_different_ptypes(self):
        """Ensure PCMA and PCMU have different payload types."""
        self.assertNotEqual(self.codec_pcma.ptype, self.codec_pcmu.ptype)
        self.assertEqual(self.codec_pcma.ptype, 8)
        self.assertEqual(self.codec_pcmu.ptype, 0)

    def test_different_enames(self):
        """Ensure PCMA and PCMU have different encoding names."""
        self.assertNotEqual(self.codec_pcma.ename, self.codec_pcmu.ename)
        self.assertEqual(self.codec_pcma.ename, 'PCMA')
        self.assertEqual(self.codec_pcmu.ename, 'PCMU')

    def test_different_silence_bytes(self):
        """Ensure PCMA and PCMU have different silence bytes."""
        silence_pcma = self.codec_pcma.silence(1)
        silence_pcmu = self.codec_pcmu.silence(1)

        self.assertNotEqual(silence_pcma, silence_pcmu)
        self.assertEqual(silence_pcma, bytes([0xD5]))
        self.assertEqual(silence_pcmu, bytes([0xFF]))

    def test_same_sample_rate(self):
        """Ensure both codecs use the same sample rate."""
        self.assertEqual(self.codec_pcma.srate, self.codec_pcmu.srate)
        self.assertEqual(self.codec_pcma.srate, 8000)

    def test_same_clock_rate(self):
        """Ensure both codecs use the same clock rate."""
        self.assertEqual(self.codec_pcma.crate, self.codec_pcmu.crate)
        self.assertEqual(self.codec_pcma.crate, 8000)


if __name__ == '__main__':
    unittest.main()
