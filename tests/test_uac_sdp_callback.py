import unittest

from sippy.UA import UA
from sippy.SipResponse import SipResponse
from sippy.SipRequest import SipRequest
from sippy.SipURL import SipURL
from sippy.SipTo import SipTo
from sippy.SipFrom import SipFrom
from sippy.SipAddress import SipAddress
from sippy.SipContact import SipContact
from sippy.SipCallId import SipCallId
from sippy.SipCSeq import SipCSeq
from sippy.SipContentType import SipContentType
from sippy.Time.MonoTime import MonoTime
from sippy.CCEvents import (CCEventRing, CCEventConnect, CCEventFail,
                            CCEventDisconnect, CCEventUpdate)
from sippy.UacStateTrying import UacStateTrying
from sippy.UacStateRinging import UacStateRinging
from sippy.UacStateUpdating import UacStateUpdating
from sippy.UaStateFailed import UaStateFailed
from sippy.UaStateConnected import UaStateConnected
from sippy.UaStateDisconnected import UaStateDisconnected
from sippy.Exceptions.SdpParseError import SdpParseError
from sippy.MsgBody import MsgBody, RawBody
from sippy.SdpBody import SdpBody

SDP = ('v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=session\r\nt=0 0\r\n'
       'c=IN IP4 127.0.0.1\r\nm=audio 1 RTP/AVP 0\r\n')

# A valid-UTF-8 SDP containing non-ASCII (proves a REAL text conversion,
# not a latin-1 pass-through) and an opaque body (not valid UTF-8).
RAW_SDP_TEXT = ('v=0\r\n'
                'o=- 1 1 IN IP4 127.0.0.1\r\n'
                's=session \u4e2d\u597d\r\n'
                't=0 0\r\n'
                'c=IN IP4 127.0.0.1\r\n'
                'm=audio 1 RTP/AVP 0\r\n')
RAW_SDP_B = RAW_SDP_TEXT.encode('utf-8')
OPAQUE_B = b'\x81\xff\x00'


def _ct(text):
    c = SipContentType(text)
    c.parse()
    return c


class FakeTr(object):
    def __init__(self):
        self.uack = False


class FakeTM(object):
    """Records transaction operations instead of talking UDP."""
    def __init__(self):
        self.cancelled = []    # (tr, extra_headers)
        self.new_tx = []       # SipRequest
        self.responses = []    # sent SipResponse (UAS side)
        self.consumers = []

    def regConsumer(self, ua, callid, compact = False):
        self.consumers.append(callid)

    def cancelTransaction(self, tr, extra_headers = None):
        self.cancelled.append((tr, extra_headers))
        return tr

    def newTransaction(self, req, laddress = None, compact = False, **kwa):
        self.new_tx.append(req)
        return FakeTr()

    def sendResponse(self, resp, ack_cb = None, lossemul = None, **kwa):
        self.responses.append(resp)
        return resp


def make_ua(events = None, fail_cbs = None, ring_cbs = None,
            conn_cbs = None, disc_cbs = None):
    """A real UA pre-configured the way UacStateIdle configures it on
    CCEventTry (call leg identity), so the Trying/Ringing/Updating
    states can be driven directly through UA.recvResponse()."""
    if events is None:
        events = []
    tm = FakeTM()
    ua = UA({'_sip_tm': tm}, event_cb = lambda e, u: events.append(e),
            conn_cbs = conn_cbs, disc_cbs = disc_cbs,
            fail_cbs = fail_cbs, ring_cbs = ring_cbs)
    ua.origin = 'callee'
    ua.cId = SipCallId()
    ua.rAddr0 = ('127.0.0.1', 5060)
    ua.rAddr = ua.rAddr0
    ua.rTarget = SipURL(username = 'bob', host = '127.0.0.1', port = 5060,
                        transport = 'udp')
    rurl = SipURL(username = 'bob', host = '127.0.0.1', port = None)
    ua.rUri = SipTo(address = SipAddress(url = rurl, hadbrace = True))
    lurl = SipURL(username = 'alice')
    lurl.port = lurl.transport = None
    ua.lUri = SipFrom(address = SipAddress(url = lurl, hadbrace = True))
    ua.lUri.setTag(ua.lTag)
    ua.lCSeq = SipCSeq.genRandCSeq()
    ua.lContact = SipContact()
    ua.routes = []
    ua.tr = FakeTr()
    return ua, tm, events


def make_response(code, reason, body = None, to_tag = None):
    hdrs = [
        'SIP/2.0 %d %s' % (code, reason),
        'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest1',
        'From: <sip:alice@127.0.0.1>;tag=alice1',
        'To: <sip:bob@127.0.0.1>' + (';tag=%s' % to_tag if to_tag else ''),
        'Call-ID: test-call-id-1',
        'CSeq: 1 INVITE',
        'Contact: <sip:bob@127.0.0.1:5060>',
    ]
    msg = '\r\n'.join(hdrs) + '\r\n\r\n'
    if body is not None:
        hdrs += ['Content-Type: application/sdp',
                 'Content-Length: %d' % len(body)]
        msg = '\r\n'.join(hdrs) + '\r\n\r\n' + body
    resp = SipResponse(msg)
    resp.rtime = MonoTime()
    return resp


def make_raw_response(code, reason, body_bytes, ctype = 'application/sdp',
                      to_tag = None):
    """Build a response from the same wire bytes STM passes to SipResponse."""
    hdrs = [
        'SIP/2.0 %d %s' % (code, reason),
        'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest1',
        'From: <sip:alice@127.0.0.1>;tag=alice1',
        'To: <sip:bob@127.0.0.1>' + (';tag=%s' % to_tag if to_tag else ''),
        'Call-ID: test-call-id-1',
        'CSeq: 1 INVITE',
        'Contact: <sip:bob@127.0.0.1:5060>',
        'Content-Type: %s' % ctype,
        'Content-Length: %d' % len(body_bytes),
    ]
    resp = SipResponse(('\r\n'.join(hdrs) + '\r\n\r\n').encode('utf-8') + body_bytes)
    resp.rtime = MonoTime()
    return resp


def make_reinvite(tm, ua):
    """A body-less re-INVITE (the 'put session on hold' hack trigger),
    with the UA.recvRequest request-response binding (req.sendResponse
    -> tm.sendResponse via req.genResponse) installed on it."""
    hdrs = [
        'INVITE sip:bob@127.0.0.1:5060 SIP/2.0',
        'Via: SIP/2.0/UDP 127.0.0.1:5060;branch=z9hG4bKtest2',
        'From: <sip:alice@127.0.0.1>;tag=alice1',
        'To: <sip:bob@127.0.0.1>;tag=bob1',
        'Call-ID: test-call-id-2',
        'CSeq: 2 INVITE',
    ]
    req = SipRequest('\r\n'.join(hdrs) + '\r\n')
    req.rtime = MonoTime()
    def sendResponse(*rcode):
        resp = req.genResponse(*rcode, server = ua.local_ua)
        tm.sendResponse(resp)
    req.sendResponse = sendResponse
    return req


def fail_events(events):
    return [e for e in events if isinstance(e, CCEventFail)]


class TestUacSdpCallbackBase(unittest.TestCase):
    pass


class TestSdpCallbackInvoked(TestUacSdpCallbackBase):
    """The callback is invoked for 1xx and 200 with an SDP body (five
    UAC response sites via filter_remote_sdp)."""

    def test_180_trying(self):
        calls = []
        def cb(body, c):
            calls.append(body)
            return body
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_response(180, 'Ringing', SDP), ua.tr)
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(ua.state, UacStateRinging)
        self.assertIsNotNone(ua.rSDP)
        self.assertTrue(any(isinstance(e, CCEventRing) for e in events))

    def test_200_trying(self):
        calls = []
        def cb(body, c):
            calls.append(body)
            return body
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_response(200, 'OK', SDP, to_tag = 'bob1'), ua.tr)
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(ua.state, UaStateConnected)
        self.assertIsNotNone(ua.rSDP)
        self.assertTrue(any(isinstance(e, CCEventConnect) for e in events))

    def test_200_ringing(self):
        calls = []
        def cb(body, c):
            calls.append(body)
            return body
        ua, tm, events = make_ua()
        ua.state = UacStateRinging(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_response(200, 'OK', SDP, to_tag = 'bob1'), ua.tr)
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(ua.state, UaStateConnected)
        self.assertIsNotNone(ua.rSDP)


class TestSdpCallbackAbort(TestUacSdpCallbackBase):
    """Returning None from the callback still means 'abort the SDP
    update' (no failure), as before."""

    def test_200_trying_abort(self):
        def cb(body, c):
            return None
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_response(200, 'OK', SDP, to_tag = 'bob1'), ua.tr)
        self.assertIsInstance(ua.state, UaStateConnected)
        self.assertIsNone(ua.rSDP)
        self.assertEqual(fail_events(events), [])

    def test_180_trying_abort(self):
        def cb(body, c):
            return None
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_response(180, 'Ringing', SDP), ua.tr)
        self.assertIsInstance(ua.state, UacStateRinging)
        self.assertEqual(fail_events(events), [])


class TestSdpCallbackUpdating(TestUacSdpCallbackBase):
    """Re-INVITE (Updating) refresh-failure behaviour is the CLASSIC
    inline handling (502 fail event + BYE + disconnect + Disconnected),
    preserved verbatim by the filter_remote_sdp bridge."""

    def test_200_updating_valueerror(self):
        def cb(body, c):
            raise ValueError('boom')
        self._fc = []
        ua, tm, events = make_ua(
            fail_cbs = (lambda u, r, o, c: self._fc.append(c),))
        ua.state = UacStateUpdating(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_response(200, 'OK', SDP, to_tag = 'bob1'), ua.tr)
        self.assertIsInstance(ua.state, UaStateDisconnected)
        byes = [r for r in tm.new_tx if r.getMethod() == 'BYE']
        self.assertEqual(len(byes), 1)
        fails = fail_events(events)
        self.assertEqual(len(fails), 1)
        self.assertEqual(fails[0].getData()[0], 502)
        self.assertIsNotNone(fails[0].warning)
        self.assertIn('boom', fails[0].warning.body.text)
        self.assertTrue(any(isinstance(e, CCEventDisconnect) for e in events))

    def test_200_updating_sdperror(self):
        def cb(body, c):
            raise SdpParseError('malformed sdp')
        self._fc = []
        ua, tm, events = make_ua(
            fail_cbs = (lambda u, r, o, c: self._fc.append(c),))
        ua.state = UacStateUpdating(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_response(200, 'OK', SDP, to_tag = 'bob1'), ua.tr)
        self.assertIsInstance(ua.state, UaStateDisconnected)
        byes = [r for r in tm.new_tx if r.getMethod() == 'BYE']
        self.assertEqual(len(byes), 1)
        fails = fail_events(events)
        self.assertEqual(len(fails), 1)
        self.assertEqual(fails[0].getData()[0], 502)
        self.assertIsNotNone(fails[0].reason_rfc3326)
        # The BYE carries the SDP error reason (bye_reason).
        self.assertEqual(byes[0].countHFs('reason'), 1)


class TestSdpCallbackWireBody(TestUacSdpCallbackBase):
    """Media callbacks get parsed SDP; opaque bodies bypass processing."""

    def test_local_update_checks_parsed_type_only_when_update_is_needed(self):
        ua, _, _ = make_ua()
        ua.on_local_sdp_change = lambda *args: None
        body = MsgBody(OPAQUE_B, _ct('application/octet-stream'))
        self.assertTrue(body.needs_update)
        self.assertFalse(ua.should_update_local_sdp(body))
        self.assertIsInstance(body.content, RawBody)
        body = MsgBody(RAW_SDP_B)
        body.needs_update = False
        self.assertFalse(ua.should_update_local_sdp(body))
        self.assertFalse(body.parsed)
        body.needs_update = True
        self.assertTrue(ua.should_update_local_sdp(body))
        self.assertIsInstance(body.content, SdpBody)

    def test_200_received_sdp_uses_legacy_api_without_callback(self):
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.recvResponse(make_raw_response(200, 'OK', RAW_SDP_B, to_tag='bob1'),
                        ua.tr)
        self.assertIsInstance(ua.state, UaStateConnected)
        ua.rSDP.parse()
        self.assertEqual(len(ua.rSDP.content.sections), 1)

    def test_180_trying_callback_receives_parsed_sdp(self):
        calls = []
        def cb(body, c):
            calls.append(body)
            return body
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_raw_response(180, 'Ringing', RAW_SDP_B), ua.tr)
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(calls[0], MsgBody)
        self.assertIsInstance(calls[0].content, SdpBody)
        self.assertIsInstance(ua.state, UacStateRinging)
        self.assertIsNotNone(ua.rSDP)

    def test_200_trying_callback_receives_parsed_sdp(self):
        calls = []
        def cb(body, c):
            calls.append(body)
            return body
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_raw_response(200, 'OK', RAW_SDP_B, to_tag = 'bob1'),
                        ua.tr)
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(calls[0].content, SdpBody)
        self.assertIsInstance(ua.state, UaStateConnected)
        self.assertIsNotNone(ua.rSDP)

    def test_200_trying_opaque_bypasses_callback(self):
        calls = []
        def cb(body, c):
            calls.append(body)
            return body
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_raw_response(200, 'OK', OPAQUE_B,
                                          ctype = 'application/x-private',
                                          to_tag = 'bob1'), ua.tr)
        self.assertEqual(calls, [],
                         'an opaque body must bypass the callback '
                         '(no coercion to text, no abort)')
        self.assertIsInstance(ua.state, UaStateConnected)
        self.assertEqual(fail_events(events), [])
        self.assertIsInstance(ua.rSDP.content, RawBody,
                              'the opaque bytes stay authoritative')
        self.assertEqual(ua.rSDP.localStr(as_bytes=True), OPAQUE_B)

    def test_180_trying_octet_stream_bypasses_callback(self):
        calls = []
        def cb(body, c):
            calls.append(body)
            return body
        ua, tm, events = make_ua()
        ua.state = UacStateTrying(ua)
        ua.late_media = False
        ua.on_remote_sdp_change = cb
        ua.recvResponse(make_raw_response(180, 'Ringing', b'WXYZ',
                                          ctype = 'application/octet-stream'),
                        ua.tr)
        self.assertEqual(calls, [],
                         'an explicit application/octet-stream body never '
                         'converts to text')
        self.assertIsInstance(ua.state, UacStateRinging)
        self.assertEqual(fail_events(events), [])
        self.assertEqual(ua.rSDP.localStr(as_bytes=True), b'WXYZ')


class TestBodylessReinviteRawSdp(TestUacSdpCallbackBase):
    """Use a copy of the prior SDP on hold, or respond 488 without SDP."""

    def _make_uas(self, rSDP):
        ua, tm, events = make_ua()
        ua.state = UaStateConnected(ua)
        ua.rSDP = rSDP
        ua.lSDP = None
        ua.local_ua = 'TestSIP'
        ua.uasResp = make_response(200, 'OK', to_tag = 'bob1')
        return ua, tm, events

    def test_bodyless_reinvite_raw_sdp_hold_edit(self):
        rbody = MsgBody(RAW_SDP_B, _ct('application/sdp'))
        ua, tm, events = self._make_uas(rbody)
        rval = ua.state.recvRequest(make_reinvite(tm, ua))
        # The 100 Trying was sent; no final response yet (the refresh
        # goes through the normal Updating path).
        self.assertEqual([r.getSCode()[0] for r in tm.responses], [100])
        self.assertIsNotNone(rval)
        self.assertIs(rval[0], ua.UasStateUpdating)
        self.assertEqual(len(ua.equeue), 1)
        ev = ua.equeue[0]
        self.assertIsInstance(ev, CCEventUpdate)
        body = ev.getData()
        body.parse()
        self.assertEqual([s.c_header.addr for s in body.content.sections],
                         ['0.0.0.0'])
        self.assertEqual(ua.rSDP.content.sections[0].c_header.addr,
                         '0.0.0.0')
        # The prior wire body was never mutated.
        self.assertEqual(rbody.localStr(as_bytes=True), RAW_SDP_B)

    def test_bodyless_reinvite_no_prior_sdp_answers_488(self):
        ua, tm, events = self._make_uas(None)
        rval = ua.state.recvRequest(make_reinvite(tm, ua))
        self.assertIsNone(rval, 'stay Connected')
        self.assertEqual([r.getSCode()[0] for r in tm.responses],
                         [100, 488])
        self.assertIsNone(tm.responses[-1].getBody(),
                          'a failure response carries no offer')
        # Dialog-correct: the 488 echoes the re-INVITE's CSeq.
        self.assertEqual(tm.responses[-1].getHFBody('cseq').getCSeqNum(), 2)
        self.assertEqual(ua.equeue, [], 'no spurious update event')
        self.assertIsNone(ua.rSDP)

    def test_bodyless_reinvite_opaque_body_answers_488(self):
        rbody = MsgBody(OPAQUE_B, _ct('application/octet-stream'))
        ua, tm, events = self._make_uas(rbody)
        rval = ua.state.recvRequest(make_reinvite(tm, ua))
        self.assertIsNone(rval,
                          'an opaque remote body cannot be put on hold')
        self.assertEqual([r.getSCode()[0] for r in tm.responses],
                         [100, 488])
        self.assertIsNone(tm.responses[-1].getBody())
        self.assertEqual(ua.equeue, [])
        self.assertIs(ua.rSDP, rbody, 'the opaque body is untouched')

    def test_bodyless_reinvite_text_sdp_hold_edit_unchanged(self):
        """Classic (textual) prior SDP: the hold hack behaves exactly as
        before the raw-SDP change."""
        body = MsgBody(RAW_SDP_TEXT, _ct('application/sdp'))
        ua, tm, events = self._make_uas(body)
        rval = ua.state.recvRequest(make_reinvite(tm, ua))
        self.assertIsNotNone(rval)
        self.assertIs(rval[0], ua.UasStateUpdating)
        ebody = ua.equeue[0].getData()
        ebody.parse()
        self.assertEqual([s.c_header.addr for s in ebody.content.sections],
                         ['0.0.0.0'])


if __name__ == '__main__':
    unittest.main()
