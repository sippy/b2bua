import unittest

from sippy.SdpBody import SdpBody

# TODO Rename test names so each one represents clearly what it is
# testing for. 

# Test data...
sdp_multi_stream = """v=0
o=LifeSize 1366021474 2 IN IP4 192.168.190.101
s=LifeSize SIP Call
i=LifeSize Icon_600/LS_RM3_1.1.0 (16)
c=IN IP4 192.168.190.101
b=CT:2500
t=0 0
m=audio 60022 RTP/AVP 113 123 122 121 9 0 8 101
a=rtpmap:113 MP4A-LATM/32000
a=fmtp:113 profile-level-id=2;object=2;bitrate=96000
a=rtpmap:123 G7221/32000
a=fmtp:123 bitrate=48000
a=rtpmap:122 G7221/32000
a=fmtp:122 bitrate=32000
a=rtpmap:121 G7221/32000
a=fmtp:121 bitrate=24000
a=rtpmap:9 G722/8000
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:101 telephone-event/8000
m=video 60024 RTP/AVP 96 97
b=TIAS:2500000
a=rtpmap:96 H264/90000
a=fmtp:96 profile-level-id=42802a;max-mbps=490000;max-fs=8192;packetization-mode=1
a=rtpmap:97 H263-1998/90000
a=fmtp:97 CIF4=1;CIF=1;QCIF=1
a=content:main
a=rtcp-fb:* ccm fir
a=rtcp-fb:* nack pli
a=rtcp-fb:* ccm tmmbr
m=application 60026 RTP/AVP 100
a=rtpmap:100 H224/4800
m=control 60028 RTP/AVP 96
b=TIAS:2500000
a=rtpmap:96 H264/90000
a=fmtp:96 profile-level-id=428029;max-mbps=245000;max-fs=8192;packetization-mode=1
a=label:3
a=rtcp-fb:* ccm fir
a=rtcp-fb:* nack pli
a=rtcp-fb:* ccm tmmbr
a=inactive
m=application 60032 TCP/BFCP *
a=floorctrl:c-only
a=setup:active
a=connection:new
"""


sdp_h323 = """v=0
o=H.323 45678 901234 IN IP4 192.168.1.2
s=H.323 SIP Call
c=IN IP4 224.5.6.7
t=0 0
a=type:H332
m=audio 49230 RTP/AVP 0
m=video 49232 RTP/AVP 31
m=application 12349 udp wb
m=control 49234 H323 mc
c=IN IP4 134.134.157.81
"""


sdp_single_audio = """v=0
o=- 12333 12333 IN IP4 192.168.1.42
s=-
c=IN IP4 192.168.1.42
t=0 0
m=audio 16442 RTP/AVP 18 0 2 4 8 96 97 98 101
a=rtpmap:18 G729a/8000
a=rtpmap:0 PCMU/8000
a=rtpmap:2 G726-32/8000
a=rtpmap:4 G723/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:96 G726-40/8000
a=rtpmap:97 G726-24/8000
a=rtpmap:98 G726-16/8000
a=rtpmap:101 telephone-event/8000
a=fmtp:101 0-15
a=ptime:30
a=sendrecv
"""

class TestSdpBodyFunctions(unittest.TestCase):

    def test_localStr(self):
        laddr  = (('1.2.3.4', 12345), 'udp')
        got = SdpBody(sdp_multi_stream).localStr(laddr)
        want = sdp_multi_stream.replace('\n','\r\n')
        self.assertEqual(want, got)

    def test_str_override_multiple_stremas(self):
        got = SdpBody(sdp_multi_stream)
        want = sdp_multi_stream.replace('\n','\r\n')
        self.assertEqual(want, str(got))

    def test_str_override_h323_sdp(self):
        got = SdpBody(sdp_h323)
        want = sdp_h323.replace('\n','\r\n')
        self.assertEqual(want, str(got))

    def test_str_override_single_audio(self):
        got = SdpBody(sdp_single_audio)
        want = sdp_single_audio.replace('\n','\r\n')
        self.assertEqual(want, str(got))

    def test_getPTbyName(self):
        got = SdpBody(sdp_single_audio).sections[0].getPTbyName('G726-40/8000')
        want = 96
        self.assertEqual(want, got)

if __name__ == '__main__':
    unittest.main()
