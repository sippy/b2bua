import os
import unittest
from time import perf_counter

from sippy.Security.SipNonce import DGST_PRIOS, HashOracle


class TestHashOracle(unittest.TestCase):
    def test_emit_validate_speed(self):
        iterations = int(os.environ.get('SIPPY_HASHORACLE_SPEED_ITERATIONS', '2000'))
        min_rate = float(os.environ.get('SIPPY_HASHORACLE_MIN_RATE', '1000'))
        ho = HashOracle()

        for _ in range(100):
            nonce = ho.emit_challenge(DGST_PRIOS)
            self.assertTrue(ho.validate_challenge(nonce, DGST_PRIOS))

        start = perf_counter()
        for _ in range(iterations):
            nonce = ho.emit_challenge(DGST_PRIOS)
            self.assertTrue(ho.validate_challenge(nonce, DGST_PRIOS))
        elapsed = perf_counter() - start

        rate = iterations / elapsed
        print('HashOracle: %.0f emit+validate cycles/sec' % rate)
        self.assertGreaterEqual(rate, min_rate)


if __name__ == '__main__':
    unittest.main()
