import unittest
from sippy.Udp_server import self_test

class TestUdp_server(unittest.TestCase):
    def test_run(self):
        # Create an instance of the self_test class
        test_instance = self_test()

        # Run the existing logic
        test_instance.run()

        # You can add assertions here if needed to check the final state or outcomes.
        # For example, you might want to check if npongs reached 0.
        self.assertEqual(test_instance.npongs, 0)

if __name__ == '__main__':
    unittest.main()
