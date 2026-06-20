import gc
import socket
import unittest
import warnings
import weakref

try:
    import rtpsynth.RtpServer  # noqa: F401
except ImportError:
    rtpsynth_available = False
else:
    rtpsynth_available = True

from sippy.Rtp.Codecs.G711 import G711Codec
from sippy.Rtp.Conf import RTPConf
from sippy.Rtp.EPoint import RTPEPoint
from sippy.Rtp.Params import RTPParams


class TestRtpEPoint(unittest.TestCase):
    def _make_endpoint(self, target):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', ResourceWarning)
            params = RTPParams(target, out_ptime=20, out_sr=8000)
            params.codec = G711Codec
            return RTPEPoint(RTPConf(), params, lambda chunk: None)

    def _udp_port_is_free(self, port):
        skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            skt.bind(('0.0.0.0', port))
        except OSError:
            return False
        finally:
            skt.close()
        return True

    @unittest.skipUnless(rtpsynth_available, 'rtpsynth is not available')
    def test_endpoint_gc_releases_rtp_channel(self):
        for target in (None, ('127.0.0.1', 9)):
            with self.subTest(target=target):
                ep = self._make_endpoint(target)
                ep_ref = weakref.ref(ep)
                port = ep.rtp_params.rtp_lport

                del ep
                for _ in range(5):
                    gc.collect()

                retained = ep_ref()
                endpoint_alive = retained is not None
                port_free = self._udp_port_is_free(port)
                if retained is not None:
                    retained.shutdown()

                self.assertFalse(endpoint_alive)
                self.assertTrue(port_free)


if __name__ == '__main__':
    unittest.main()
