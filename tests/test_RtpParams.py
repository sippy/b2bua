import unittest
from socket import AF_INET, AF_INET6
from unittest.mock import patch

from sippy.Rtp.Params import RTPParams, canonicalize_rtp_address, canonicalize_rtp_target


class TestRtpParams(unittest.TestCase):
    def test_canonicalize_ipv6_expanded_target(self):
        target = canonicalize_rtp_target(('0:0:0:0:0:0:0:1', 14086))
        self.assertEqual(target, ('::1', 14086))

    def test_canonicalize_bracketed_ipv6_target(self):
        target = canonicalize_rtp_target(('[::1]', '13998'))
        self.assertEqual(target, ('::1', 13998))

    def test_canonicalize_incoming_ipv6_address_tuple(self):
        source = canonicalize_rtp_address(('0:0:0:0:0:0:0:1', 14086, 0, 0))
        self.assertEqual(source, ('::1', 14086))

    def test_params_store_canonical_target(self):
        a = RTPParams(('::1', 14086), rtp_proto='IP6')
        b = RTPParams(('0:0:0:0:0:0:0:1', 14086), rtp_proto='IP6')
        self.assertEqual(a.rtp_target, b.rtp_target)

    def test_rtp_proto_setter_normalizes_and_updates_laddr(self):
        params = RTPParams(None, rtp_proto='IP4')
        self.assertEqual(params.rtp_laddr, '0.0.0.0')
        params.rtp_proto = 'ip6'
        self.assertEqual(params.rtp_proto, 'IP6')
        self.assertEqual(params.rtp_laddr, '::')

    def test_rtp_target_setter_canonicalizes_and_updates_laddr(self):
        params = RTPParams(None, rtp_proto='IP6')
        with patch('sippy.Rtp.Params.local4remote', return_value='[2001:db8::1]') as mock_l4r:
            params.rtp_target = ('0:0:0:0:0:0:0:1', '14086')
            mock_l4r.assert_called_once_with('::1', family=AF_INET6)
        self.assertEqual(params.rtp_target, ('::1', 14086))
        self.assertEqual(params.rtp_laddr, '2001:db8::1')

    def test_rtp_target_setter_skips_canonicalize_and_laddr_on_unchanged_value(self):
        params = RTPParams(None, rtp_proto='IP6')
        with patch('sippy.Rtp.Params.canonicalize_rtp_target',
                   side_effect=AssertionError('canonicalize_rtp_target should not be called')):
            with patch.object(params, '_get_laddr', side_effect=AssertionError('_get_laddr should not be called')):
                params.rtp_target = None

    def test_rtp_proto_setter_skips_laddr_on_unchanged_value(self):
        params = RTPParams(None, rtp_proto='IP4')
        with patch.object(params, '_get_laddr', side_effect=AssertionError('_get_laddr should not be called')):
            params.rtp_proto = 'ip4'

    def test_rtp_family_property_maps_proto(self):
        params = RTPParams(None, rtp_proto='IP4')
        self.assertEqual(params.rtp_family, AF_INET)
        params.rtp_proto = 'IP6'
        self.assertEqual(params.rtp_family, AF_INET6)

    def test_rtp_family_property_is_read_only(self):
        params = RTPParams(None, rtp_proto='IP4')
        with self.assertRaises(AttributeError):
            params.rtp_family = AF_INET6


if __name__ == '__main__':
    unittest.main()
