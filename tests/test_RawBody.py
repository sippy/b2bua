import unittest

from sippy.MsgBody import MsgBody, RawBody
from sippy.SipContentType import SipContentType

SDP = ('v=0\r\n'
       'o=- 1 1 IN IP4 127.0.0.1\r\n'
       's=session \xe4\xb8\xad\r\n'
       't=0 0\r\n'
       'c=IN IP4 127.0.0.1\r\n'
       'm=audio 1 RTP/AVP 0\r\n')
SDP_B = SDP.encode('utf-8')          # valid UTF-8, contains non-ASCII
B3 = b'\x81\xff\x00'                # NOT valid UTF-8


def _ct(text):
    c = SipContentType(text)
    c.parse()
    return c


class TestRawBody(unittest.TestCase):

    def test_opaque_types_parse_to_raw_body(self):
        for raw, ctype in ((B3, 'application/octet-stream'),
                           (SDP_B, 'application/octet-stream'),
                           (SDP_B, 'application/x-private')):
            with self.subTest(ctype=ctype):
                body = MsgBody(raw, _ct(ctype))
                self.assertFalse(body.parsed)
                self.assertEqual(body.content, raw)
                body.parse()
                content = body.content
                self.assertIsInstance(content, RawBody)
                self.assertEqual(content.content, raw)
                self.assertEqual(body.localStr(as_bytes=True), raw)
                body.parse()
                self.assertIs(body.content, content)

    def test_non_utf8_requires_byte_mode_before_and_after_parsing(self):
        body = MsgBody(B3, _ct('application/octet-stream'))
        for parsed in (False, True):
            if parsed:
                body.parse()
            with self.assertRaises(UnicodeDecodeError):
                body.localStr()
            self.assertEqual(body.localStr(as_bytes=True), B3)

    def test_declared_structured_types_reject_invalid_utf8(self):
        for ctype in ('application/sdp', 'multipart/mixed;boundary=part'):
            with self.subTest(ctype=ctype):
                body = MsgBody(B3, _ct(ctype))
                with self.assertRaises(UnicodeDecodeError):
                    body.parse()
                self.assertFalse(body.parsed)
                self.assertEqual(body.content, B3)

    def test_content_type_parser_trims_media_type_before_parameters(self):
        ctype = _ct('Application/SDP \t;charset=utf-8')
        self.assertEqual(ctype.name, 'Application/SDP')
        body = MsgBody(SDP_B, ctype)
        self.assertEqual(body.getType(), 'application/sdp')
        body.parse()
        self.assertIsNotNone(body.content.s_header)

    def test_constructor_accepts_text_but_stores_bytes(self):
        body = MsgBody(SDP)
        self.assertEqual(body.content, SDP_B)
        self.assertEqual(body.localStr(), SDP)
        self.assertTrue(body.needs_update)
        body.parse()
        self.assertIsNotNone(body.content.s_header)

    def test_msg_getcopy_preserves_raw_body(self):
        # NOTE: SipRequest.getCopy() is broken on master (pre-existing:
        # SipMsg.getCopy does self.__class__() -> kwarg ctor with
        # ruri=None); out of scope here, so the message-level copy is
        # exercised on SipResponse.
        from sippy.SipResponse import SipResponse
        hdr = ('SIP/2.0 200 OK\r\n'
               'Via: SIP/2.0/UDP 1.1.1.1;branch=z9hG4bK-rb1\r\n'
               'From: <sip:b@x>\r\n'
               'To: <sip:a@x>;tag=t1\r\n'
               'Call-ID: rb1@x\r\n'
               'CSeq: 1 INVITE\r\n'
               'Content-Type: application/x-private; charset=binary\r\n'
               'Content-Length: %d\r\n\r\n') % len(B3)
        resp = SipResponse(hdr.encode('utf-8') + B3)
        self.assertEqual(resp.body.content, B3)
        resp.body.parse()
        cp = resp.getCopy()
        self.assertIsInstance(cp.body.content, RawBody)
        self.assertIsNot(cp.body.content, resp.body.content)
        self.assertEqual(cp.body.localStr(as_bytes=True), B3)
        self.assertEqual(str(cp.body.mtype), 'application/x-private; charset=binary')
        # The Content-Type header line is unchanged in the serialization.
        self.assertIn(b'Content-Type: application/x-private; charset=binary\r\n',
                      cp.localStr(as_bytes=True))
        self.assertNotIn(b'Content-Type: application/octet-stream',
                         cp.localStr(as_bytes=True))


if __name__ == '__main__':
    unittest.main()
