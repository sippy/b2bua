#
# UDP bodies obey byte-counted Content-Length. All unparsed bodies
# retain their exact octets and use the same MsgBody API.
#
import unittest
from hashlib import md5
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sippy.SipRequest import SipRequest
from sippy.SipResponse import SipResponse
from sippy.SipMsg import SipMsg, WireHeaderError
from sippy.SipTransactionManager import SipTransactionManager, SipTMRetransmitO
from sippy.Exceptions.SipParseError import SipParseError
from sippy.MsgBody import MsgBody, RawBody

ZHONG = '中'                      # U+4E2D, UTF-8 b'\xe4\xb8\xad'
B3 = b'\x81\xff\x00'              # NOT valid UTF-8 (opaque)


def _inv(body_bytes, cl=None):
    hdr = ('INVITE sip:dst@127.0.0.1 SIP/2.0\r\n'
           'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKfix1-1\r\n'
           'From: <sip:a@127.0.0.1>;tag=t1\r\n'
           'To: <sip:dst@127.0.0.1>\r\n'
           'Call-ID: fix1-1@127.0.0.1\r\n'
           'CSeq: 1 INVITE\r\n'
           'Max-Forwards: 70\r\n')
    if cl is not None:
        hdr += 'Content-Length: %d\r\n' % cl
    hdr += 'Content-Type: application/sdp\r\n'
    return (hdr + '\r\n').encode('utf-8') + body_bytes


def _parse_req(datagram):
    return SipRequest(datagram)


def _wire_body(msg, local_addr=None):
    wb = msg.localStr(local_addr, as_bytes=True)
    return wb.split(b'\r\n\r\n', 1)[1] if b'\r\n\r\n' in wb else b''


class TestOutgoingLogging(unittest.TestCase):
    def test_logs_text_without_changing_wire_or_cached_bytes(self):
        tm = SipTransactionManager.__new__(SipTransactionManager)
        logger = Mock()
        tm.global_config = {'_sip_logger': logger}
        tm.l1rcache = {}
        address = ('127.0.0.1', 5060)
        server = Mock()
        server.addr2str.return_value = 'udp:127.0.0.1:5060'
        for body, logged_body in ((ZHONG.encode('utf-8'), ZHONG), (b'\xff', r'\xff')):
            with self.subTest(body=body):
                data = b'SIP/2.0 200 OK\r\n\r\n' + body
                checksum = md5(data).digest()
                tm.transmitData(server, data, address, checksum)
                logger.write.assert_called_with(
                    'SENDING message to udp:127.0.0.1:5060:\n',
                    'SIP/2.0 200 OK\r\n\r\n' + logged_body)
                server.send_to.assert_called_with(data, address)
                self.assertIs(tm.l1rcache[checksum].data, data)


class TestRetransmitCache(unittest.TestCase):

    def setUp(self):
        self.tm = SipTransactionManager.__new__(SipTransactionManager)
        self.tm.global_config = {'_sip_logger': Mock()}
        self.tm.l1rcache = {}
        self.tm.l2rcache = {}
        self.tm.l4r = Mock()
        self.tm.transmitData = Mock()
        self.tm.transmitMsg = Mock()
        self.peer = SimpleNamespace(address=('127.0.0.1', 5060))
        self.server = object()
        self.time = SimpleNamespace(realt=0)

    def receive(self, data):
        self.tm.handleIncoming(data, self.peer, self.server, self.time)

    @patch.object(SipMsg, 'split_wire_datagram')
    def test_cached_reply_skips_split_in_both_cache_levels(self, split):
        data = _inv(b'', cl=0)
        self.tm.l1rcache[md5(data).digest()] = SipTMRetransmitO(
            self.server, b'reply', self.peer.address)
        self.receive(data)
        self.tm.rCachePurge()
        self.receive(data)
        split.assert_not_called()
        self.assertEqual(self.tm.transmitData.call_count, 2)
        self.tm.transmitData.assert_called_with(
            self.server, b'reply', self.peer.address, lossemul=None)

    @patch('sippy.SipTransactionManager.dump_exception')
    @patch.object(SipMsg, 'split_wire_datagram', wraps=SipMsg.split_wire_datagram)
    def test_malformed_datagrams_are_split_only_on_first_receipt(self, split, log):
        request = _inv(b'', cl=0).replace(b'Max-Forwards:', b'\xffMax-Forwards:')
        response = request.replace(b'INVITE sip:dst@127.0.0.1 SIP/2.0',
                                   b'SIP/2.0 500 Server Error', 1)
        for data in (request, response):
            self.receive(data)
            self.receive(data)
        self.tm.rCachePurge()
        for data in (request, response):
            self.receive(data)
        self.assertEqual(split.call_count, 2)
        self.assertEqual(log.call_count, 2)
        self.tm.transmitMsg.assert_called_once()
        self.assertEqual(self.tm.transmitMsg.call_args.args[1].getSCode()[0], 400)
        self.tm.transmitData.assert_not_called()


    @patch('sippy.SipTransactionManager.dump_exception')
    def test_request_parse_failure_uses_get_response(self, log):
        request = _inv(b'', cl=0)
        error = SipParseError('cannot parse request')
        response = SipResponse(scode=400, reason='Bad Request')
        with patch.object(error, 'getResponse', side_effect=(response, None)) as get_response, \
             patch('sippy.SipTransactionManager.SipRequest', side_effect=error):
            self.receive(request)
            self.receive(request + b' ')
        self.assertEqual(get_response.call_count, 2)
        self.tm.transmitMsg.assert_called_once_with(
            self.server, response, self.peer.address, md5(request).digest())


class TestBodyOctets(unittest.TestCase):

    def test_constructors_accept_bytes_and_text(self):
        body = ZHONG.encode('utf-8')
        request = _inv(body, cl=len(body))
        response = request.replace(b'INVITE sip:dst@127.0.0.1 SIP/2.0',
                                   b'SIP/2.0 200 OK', 1)
        for data, expected in ((request, SipRequest), (response, SipResponse)):
            for payload in (data, data.decode('utf-8')):
                with self.subTest(expected=expected, input_type=type(payload)):
                    msg = expected(payload)
                    self.assertIsInstance(msg, expected)
                    self.assertEqual(_wire_body(msg), body)

    def test_parse_attaches_bad_request_only_for_invalid_request_headers(self):
        request = _inv(b'', cl=0).replace(b'Max-Forwards:', b'\xffMax-Forwards:')
        response = request.replace(b'INVITE sip:dst@127.0.0.1 SIP/2.0',
                                   b'SIP/2.0 200 OK', 1)
        with self.assertRaises(WireHeaderError) as ctx:
            SipRequest(request)
        self.assertEqual(ctx.exception.sip_response.getSCode(), (400, 'Bad Request'))
        with self.assertRaises(WireHeaderError) as ctx:
            SipResponse(response)
        self.assertIsNone(ctx.exception.sip_response)

    def test_canonical_udp_separator_is_found_once(self):
        searches = []

        class Datagram(bytes):
            def find(self, separator):
                searches.append(separator)
                return super().find(separator)

        class Headers(str):
            def find(self, *args):
                raise AssertionError('pre-split headers must not be rescanned')

        body = B3 + b'\r\n\r\n\r\r\n\n'
        datagram = Datagram(_inv(body, cl=len(body)))
        split = SipMsg.split_wire_datagram

        def track_headers(buf):
            headers, octets = split(buf)
            return Headers(headers), octets

        with patch.object(SipMsg, 'split_wire_datagram', side_effect=track_headers):
            req = SipRequest(datagram)
        self.assertEqual(searches, [b'\r\n\r\n'])
        self.assertEqual(_wire_body(req), body)

    def test_legacy_udp_separator_fallback(self):
        headers, _, body = _inv(B3, cl=len(B3)).partition(b'\r\n\r\n')
        for eol in (b'\r', b'\n'):
            with self.subTest(eol=eol):
                datagram = headers.replace(b'\r\n', eol) + eol * 2 + body
                self.assertEqual(_wire_body(_parse_req(datagram)), body)

    def test_empty_wire_body_with_positive_content_length(self):
        with self.assertRaisesRegex(SipParseError, 'Missed SIP body') as ctx:
            _parse_req(_inv(b'', cl=3))
        response = ctx.exception.sip_response
        self.assertEqual(response.getSCode(),
                         (400, 'Bad Request - Missed SIP body, 3 bytes expected'))
        self.assertEqual(str(response.getHFBody('call-id')), 'fix1-1@127.0.0.1')

    def test_request_header_parse_error_gets_correlated_fallback(self):
        error = SipParseError('invalid header')
        with patch.object(SipRequest, 'setSL', side_effect=error):
            with self.assertRaises(SipParseError) as ctx:
                _parse_req(_inv(b'', cl=0))
        self.assertIs(ctx.exception, error)
        response = error.sip_response
        self.assertEqual(response.getSCode(), (400, 'Bad Request'))
        self.assertEqual(str(response.getHFBody('call-id')), 'fix1-1@127.0.0.1')

    def test_request_parse_error_with_response_is_re_raised_unchanged(self):
        response = SipResponse(scode=400, reason='Already built')
        error = SipParseError('invalid body', sip_response=response)
        with patch.object(SipMsg, 'init_body', side_effect=error), \
             patch.object(SipRequest, 'genResponse') as gen_response, \
             patch.object(SipRequest, '_unparsed400') as fallback:
            with self.assertRaises(SipParseError) as ctx:
                _parse_req(_inv(b'', cl=0))
        self.assertIs(ctx.exception, error)
        self.assertIs(ctx.exception.sip_response, response)
        gen_response.assert_not_called()
        fallback.assert_not_called()

    def test_unparsed_error_without_correlation_headers_has_no_response(self):
        with self.assertRaises(WireHeaderError) as ctx:
            SipRequest(b'INVITE sip:dst@127.0.0.1 SIP/2.0\r\n\xff')
        self.assertIsNone(ctx.exception.getResponse())

    def test_compact_framing_in_both_output_modes(self):
        wire = ZHONG.encode('utf-8')
        req = _parse_req(_inv(wire, cl=len(wire)))
        head_text, body_text = req.localStr(compact=True).split('\r\n\r\n', 1)
        head_bytes, body_bytes = req.localStr(compact=True, as_bytes=True).split(
            b'\r\n\r\n', 1)
        self.assertEqual(head_bytes, head_text.encode('utf-8'))
        self.assertIn(b'\r\nc: ', head_bytes)
        self.assertTrue(head_bytes.endswith(b'\r\nl: 3'))
        self.assertEqual(body_text, ZHONG)
        self.assertEqual(body_bytes, wire)

        empty = _parse_req(_inv(b'', cl=0))
        self.assertTrue(empty.localStr(compact=True).endswith('\r\nl: 0\r\n\r\n'))
        self.assertEqual(empty.localStr(compact=True, as_bytes=True),
                         empty.localStr(compact=True).encode('utf-8'))

    def test_valid_utf8_body_uses_text_api_and_round_trips(self):
        req = _parse_req(_inv(b'\xe4\xb8\xad', cl=3))
        body = req.getBody()
        self.assertIsInstance(body, MsgBody)
        self.assertFalse(body.parsed)
        self.assertEqual(body.content, ZHONG.encode('utf-8'))
        self.assertEqual(body.localStr(), ZHONG)
        self.assertEqual(_wire_body(req), b'\xe4\xb8\xad')
        head = req.localStr(as_bytes=True).split(b'\r\n\r\n', 1)[0]
        self.assertTrue(head.endswith(b'Content-Length: 3'))

    def test_udp_ingress_and_wire_output_defer_text_conversion(self):
        wire = ZHONG.encode('utf-8')
        req = _parse_req(_inv(wire, cl=len(wire)))
        self.assertEqual(_wire_body(req), wire)
        self.assertEqual(req.getBody().content, wire)
        self.assertFalse(req.getBody().parsed)

    def test_received_sdp_can_be_parsed_and_edited_in_place(self):
        sdp = (f'v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns={ZHONG}\r\n'
               'c=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio 1234 RTP/AVP 0\r\n')
        wire = sdp.encode('utf-8')
        req = _parse_req(_inv(wire, cl=len(wire)))
        self.assertEqual(_wire_body(req), wire)
        body = req.getBody()
        self.assertTrue(body.needs_update)
        body.parse()
        self.assertEqual(len(body.content.sections), 1)
        body.content.sections[0].c_header.addr = '192.0.2.1'
        self.assertIn(b'c=IN IP4 192.0.2.1\r\n', _wire_body(req))
        self.assertIn(ZHONG.encode('utf-8'), _wire_body(req))

    def test_received_multipart_copy_can_be_parsed(self):
        wire = b'--part\r\nContent-Type: text/plain\r\n\r\nhello\r\n--part--\r\n'
        req = _parse_req(_inv(wire, cl=len(wire)).replace(
            b'application/sdp', b'multipart/mixed;boundary=part', 1))
        self.assertEqual(_wire_body(req), wire)
        body = req.getBody()
        copied = body.getCopy()
        self.assertFalse(copied.parsed)
        self.assertEqual(str(copied.mtype), 'multipart/mixed;boundary=part')
        copied.parse()
        self.assertEqual(copied.content.parts[0].content, b'hello\r\n')
        self.assertFalse(body.parsed)

    def test_explicit_octet_stream_stays_binary_even_if_utf8(self):
        wire = b'plain\x00text'
        req = _parse_req(_inv(wire, cl=len(wire)).replace(
            b'application/sdp', b'application/octet-stream', 1))
        body = req.getBody()
        self.assertEqual(body.content, wire)
        body.parse()
        self.assertIsInstance(body.content, RawBody)
        self.assertEqual(body.content.content, wire)
        self.assertEqual(_wire_body(req), wire)

    def test_opaque_body_exact_octets(self):
        req = _parse_req(_inv(B3, cl=3).replace(
            b'application/sdp', b'application/x-private', 1))
        self.assertEqual(req.body.content, B3)
        with self.assertRaises(UnicodeDecodeError):
            req.localStr()
        self.assertEqual(_wire_body(req), B3)
        req.body.parse()
        self.assertIsInstance(req.body.content, RawBody)
        self.assertEqual(_wire_body(req), B3)
        self.assertEqual(str(req.body.mtype), 'application/x-private')

    def test_undeclared_ctype_defaults_by_body_representation(self):
        hdr = ('INVITE sip:dst@127.0.0.1 SIP/2.0\r\n'
               'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKfix1-d\r\n'
               'From: <sip:a@127.0.0.1>;tag=t1\r\n'
               'To: <sip:dst@127.0.0.1>\r\n'
               'Call-ID: fix1-d@127.0.0.1\r\n'
               'CSeq: 1 INVITE\r\n'
               'Content-Length: %d\r\n\r\n')
        for wire, ctype in (
            (b'WXYZ', 'application/sdp'),
            (B3, 'application/octet-stream'),
        ):
            with self.subTest(ctype=ctype):
                req = _parse_req((hdr % len(wire)).encode('utf-8') + wire)
                self.assertEqual(req.getBody().content, wire)
                self.assertEqual(req.body.getType(), ctype)
                self.assertEqual(_wire_body(req), wire)

    # An EXPLICIT textual replacement of a RawBody: the new body's
    # content is authoritative (UTF-8 of the new content).  A RawBody is
    # never implicitly coerced to text on mutation -- the only way a
    # message sends different octets is an explicit new body.
    def test_explicit_replacement_of_raw_body(self):
        req = _parse_req(_inv(B3, cl=3))
        self.assertEqual(_wire_body(req), B3)  # unmodified: exact
        req.body = MsgBody('replacement', req.body.mtype)
        wb = _wire_body(req)
        self.assertEqual(wb, 'replacement'.encode('utf-8'),
                         'an explicit textual replacement must transmit '
                         'the new content (UTF-8); got %r' % wb)
        self.assertNotEqual(wb, B3)
        head = req.localStr(as_bytes=True).split(b'\r\n\r\n', 1)[0]
        self.assertTrue(head.endswith(b'Content-Length: 11'),
                        'CL must follow the new content; head=%r' % head)

    # Content-Length: 0 WITH a trailing body -> the body is
    # DISCARDED (historical semantics), no EXTRA octets, CL 0.
    def test_cl0_extra_discarded(self):
        req = _parse_req(_inv(b'EXTRA', cl=0))
        self.assertIsNone(req.body,
                          'CL 0 must discard the body (base '
                          'semantics); body=%r' % (req.body,))
        wb = req.localStr(as_bytes=True)
        self.assertTrue(wb.endswith(b'Content-Length: 0\r\n\r\n'),
                        'serialized form must end with CL 0 and no '
                        'body; tail=%r' % wb[-40:])
        self.assertNotIn(b'EXTRA', wb,
                         'the EXTRA octets must not be serialized')

    # A RESPONSE with an opaque binary body serializes to the EXACT
    # octets (byte-mode localStr; serializing via str would double-
    # encode via latin-1 -> UTF-8).
    def test_response_binary_exact_bytes(self):
        hdr = ('SIP/2.0 200 OK\r\n'
               'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKfix1-r\r\n'
               'From: <sip:dst@127.0.0.1>\r\n'
               'To: <sip:a@127.0.0.1>;tag=tr1\r\n'
               'Call-ID: fix1-r@127.0.0.1\r\n'
               'CSeq: 1 INVITE\r\n'
               'Content-Length: %d\r\n'
               'Content-Type: application/sdp\r\n'
               '\r\n') % len(B3)
        datagram = hdr.encode('utf-8') + B3
        resp = SipResponse(datagram)
        self.assertEqual(resp.body.content, B3)
        wb = _wire_body(resp)
        self.assertEqual(wb, B3,
                         'a binary response body must serialize to '
                         'the exact octets; got %r' % wb)
        double = B3.decode('latin-1').encode('utf-8')
        self.assertNotEqual(wb, double,
                            'the latin-1->UTF-8 double encoding '
                            'must not appear; got %r' % wb)

    # SDP rewrite + non-ASCII parsed body: the serializer and the body
    # byte-mode body rendering are the SAME authoritative function
    # of the CURRENT body; a parsed/modified body never bypasses the
    # rewrite.
    def test_sdp_rewrite_nonascii_current_body(self):
        sdp = ('v=0\r\n'
               'o=- 1 1 IN IP4 0.0.0.0\r\n'
               's=%s session\r\n'
               't=0 0\r\n'
               'c=IN IP4 0.0.0.0\r\n'
               'm=audio 1 RTP/AVP 0\r\n') % ZHONG
        body = MsgBody(sdp)
        body.parse()
        from sippy.SdpBody import SdpBody
        self.assertIsInstance(body.content, SdpBody)
        addr = (('192.0.2.1', 5060), 'udp')
        wire = body.localStr(addr, as_bytes=True)
        # The CURRENT (parsed, finalized) text is authoritative (the
        # localStr(local_addr) finalize call; this tree's c= header
        # localStr is a no-op, so the bytes are the UTF-8 of the
        # current text):
        self.assertEqual(wire, body.localStr(addr).encode('utf-8'),
                         'wire octets must be the UTF-8 of the finalized '
                         'current text; got %r' % wire)
        self.assertIn(b'\xe4\xb8\xad', wire,
                      'the non-ASCII parsed content must survive as '
                      'UTF-8 in the wire octets; got %r' % wire)
        # Message serialization uses the same rendering of the current
        # body:
        msg = _parse_req(_inv(b'placeholder', cl=11))
        msg.body = body
        self.assertEqual(_wire_body(msg, addr), wire,
                         'message and body byte rendering must agree for '
                         'the same current body + local_addr')
        # No raw sidecar exists in the lazy design:
        self.assertFalse(hasattr(body, 'raw_octets'))
        # Mutating the content: the CURRENT content is authoritative.
        body.content = b'changed-text'
        self.assertEqual(str(body), 'changed-text')
        self.assertEqual(body.getCopy().content, b'changed-text')
        self.assertEqual(_wire_body(msg, addr),
                         b'changed-text',
                         'a modified parsed-body content must serialize '
                         'itself (no bypass)')

    # Framing policy on the byte path:
    def test_cl_policy_byte_domain(self):
        # CL > actual by 2 with a missed CRLF tail -> repaired (the
        # repair touches only the ASCII CRLF tail).
        req = _parse_req(_inv(b'v=0\r\nm=audio 1 RTP/AVP 0\r\n', cl=28))
        self.assertIs(type(req.body), MsgBody)
        self.assertEqual(_wire_body(req),
                         b'v=0\r\nm=audio 1 RTP/AVP 0\r\n\r\n')
        # CL splits a UTF-8 character -> 400 (never a partial char).
        try:
            _parse_req(_inv(b'\xe4\xb8\xad', cl=2))
            self.fail('CL splitting a UTF-8 char must be rejected')
        except SipParseError:
            pass
        # Malformed header (non-UTF-8 in the header part) still fails
        # closed.
        bad = _inv(b'')
        bad = bad.replace(b'Max-Forwards: 70\r\n',
                          b'\xff\x80 Bad: x\r\nMax-Forwards: 70\r\n')
        with self.assertRaises(WireHeaderError):
            SipMsg.split_wire_datagram(bad)

    # An explicit replacement with a non-latin-1 textual body must
    # serialize as UTF-8 of the current text (no crash, no stale bytes).
    def test_explicit_replacement_nonlatin1(self):
        req = _parse_req(_inv(B3, cl=3))
        req.body = MsgBody('replaced-\u4e2d', req.body.mtype)
        wb = req.body.localStr(as_bytes=True)
        self.assertEqual(wb, 'replaced-\u4e2d'.encode('utf-8'),
                         'an explicit non-latin-1 textual body must '
                         'serialize as UTF-8 of the current text; got %r'
                         % wb)

    # RESPONSE framing policy on the byte path.
    def test_response_framing_cl0_and_trailing(self):
        # CL 0 with a trailing body: the body is discarded (base
        # semantics); the response serializes with CL 0 and no body.
        d0 = ('SIP/2.0 200 OK\r\n'
              'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKfix1-f0\r\n'
              'From: <sip:dst@127.0.0.1>\r\n'
              'To: <sip:a@127.0.0.1>;tag=tf0\r\n'
              'Call-ID: fix1-f0@127.0.0.1\r\n'
              'CSeq: 1 INVITE\r\n'
              'Content-Length: 0\r\n\r\n').encode() + B3
        r0 = SipResponse(d0)
        self.assertIsNone(r0.body,
                          'CL 0 must discard the response body')
        self.assertTrue(r0.localStr(as_bytes=True).endswith(
            b'Content-Length: 0\r\n\r\n'),
            'the response must serialize with CL 0 and no body')
        # CL shorter than the actual body: CL is authoritative -- the
        # body is framed to the declared bytes, trailing bytes dropped
        # (base framing semantics; responses are not answered 4xx).
        dt = ('SIP/2.0 200 OK\r\n'
              'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKfix1-f1\r\n'
              'From: <sip:dst@127.0.0.1>\r\n'
              'To: <sip:a@127.0.0.1>;tag=tf1\r\n'
              'Call-ID: fix1-f1@127.0.0.1\r\n'
              'CSeq: 1 INVITE\r\n'
              'Content-Length: %d\r\n\r\n' % len(B3)).encode() + B3 + b'TRAIL'
        r1 = SipResponse(dt)
        self.assertIsNotNone(r1.body)
        self.assertEqual(_wire_body(r1), B3,
                         'the response body must be framed to the '
                         'declared CL (trailing bytes dropped); got %r'
                         % _wire_body(r1))

    # The string (WS / constructed) path is unchanged: a plain textual
    # MsgBody, no RawBody, wire bytes = UTF-8 of the string form.
    def test_str_path_unchanged(self):
        text = ('INVITE sip:dst@127.0.0.1 SIP/2.0\r\n'
                'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKfix1-2\r\n'
                'From: <sip:a@127.0.0.1>;tag=t1\r\n'
                'To: <sip:dst@127.0.0.1>\r\n'
                'Call-ID: fix1-2@127.0.0.1\r\n'
                'CSeq: 1 INVITE\r\n'
                'Max-Forwards: 70\r\n'
                'Content-Type: application/sdp\r\n'
                'Content-Length: %d\r\n\r\n'
                'v=0\r\nm=audio 1 RTP/AVP 0\r\n') % \
            len('v=0\r\nm=audio 1 RTP/AVP 0\r\n')
        req = SipRequest(text)
        self.assertIsInstance(req.body, MsgBody)
        self.assertFalse(hasattr(req.body, 'raw_octets'))
        self.assertEqual(req.localStr(as_bytes=True),
                         str(req).encode('utf-8'),
                         'string path: byte-mode localStr must be the UTF-8 '
                         'encoding of the string form (historical behavior)')


if __name__ == '__main__':
    unittest.main()
