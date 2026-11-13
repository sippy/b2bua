import unittest
from sippy.SdpBody import SdpBody
from sippy.Rtp_proxy.Session.subcommand import subcommand
from sippy.Rtp_proxy.Session.subcommand_ice import subcommand_ice, subcommand_deice

BASE = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=-\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio 9000 RTP/AVP 0\r\n"

class TestIceSdpScope(unittest.TestCase):
    def test_lite_is_session_only_and_deduplicated(self):
        sdp = SdpBody(BASE)
        sect = sdp.sections[0]
        ice = subcommand_ice()
        ice.ice_lufrag, ice.ice_lpwd, ice.ice_candidates = "test", "password", []
        for _ in range(2):
            ice.sdp_sect_fin(sdp, sect)
        self.assertEqual([x.name for x in sdp.a_headers], ["ice-lite"])
        self.assertNotIn("ice-lite", [x.name for x in sect.a_headers])
        wire = str(sdp)
        self.assertLess(wire.index("a=ice-lite"), wire.index("m=audio"))
        # De-ICE removes inherited ICE-lite as well.
        subcommand_deice.sdp_sect_fin(ice, sdp, sect)
        self.assertNotIn("a=ice-lite", str(sdp))

    def test_remove_both_scopes_all_matches_exactly(self):
        sdp = SdpBody(BASE)
        sect = sdp.sections[0]
        for obj in (sdp, sect):
            for attr in ("candidate:one", "candidate:two", "rtcp:9", "rtcp-mux"):
                obj.addHeader("a", attr)
        subcommand("test")._sdp_attrs_rm(sdp, sect, ("candidate", "rtcp"))
        for obj in (sdp, sect):
            self.assertEqual([x.name for x in obj.a_headers], ["rtcp-mux"])
