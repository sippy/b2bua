import unittest

from sippy.MyConfigParser import MyConfigParser
from sippy.SipAddress import SipAddress
from sippy.SipContact import SipContact
from sippy.SipExpires import SipExpires
from sippy.SipFrom import SipFrom
from sippy.SipHeader import SipHeader
from sippy.SipRegistrationServer import SipRegistrationServer
from sippy.SipRequest import SipRequest
from sippy.SipTo import SipTo
from sippy.SipURL import SipURL

class FakeRadius(object):
    calls = None

    def __init__(self):
        self.calls = []

    def do_auth(self, username, caller, callee, sip_cid, remote_ip, res_cb,
      realm = None, nonce = None, uri = None, response = None,
      extra_attributes = None, method = 'INVITE', algorithm = 'MD5'):
        self.calls.append({
            'username': username,
            'caller': caller,
            'callee': callee,
            'method': method,
            'algorithm': algorithm,
        })
        res_cb(((), 0))

class FakeSipTM(object):
    responses = None

    def __init__(self):
        self.responses = []

    def sendResponse(self, resp, sip_t = None, retrans = False, ack_cb = None,
      lossemul = 0):
        self.responses.append((resp, sip_t))

class TestSipRegistrationServer(unittest.TestCase):
    def setUp(self):
        self.global_config = MyConfigParser()
        self.global_config['auth_enable'] = False
        self.server = SipRegistrationServer(self.global_config)

    def make_config(self, auth_enable = False):
        config = MyConfigParser()
        config['auth_enable'] = auth_enable
        return config

    def make_contact(self, uri = 'sip:alice@192.0.2.10:5060', expires = None):
        contact = SipContact(address = SipAddress(url = SipURL(uri)))
        if expires is not None:
            contact.address.setParam('expires', str(expires))
        return contact

    def make_register(self, contacts = (), expires = None):
        aor = SipURL('sip:alice@example.com')
        address = SipAddress(url = aor)
        fr0m = SipFrom(address = address.getCopy())
        fr0m.genTag()
        to = SipTo(address = address.getCopy())
        req = SipRequest(method = 'REGISTER', ruri = SipURL('sip:example.com'),
          fr0m = fr0m, to = to,
          expires = SipExpires(number = expires) if expires is not None else None)
        for contact in contacts:
            req.appendHeader(SipHeader(name = 'contact', body = contact))
        return req

    def test_register_saves_contact_and_returns_binding(self):
        req = self.make_register((self.make_contact(),), expires = 120)

        resp, cancel_cb, noack_cb = self.server.recvRequest(req)

        self.assertEqual(resp.scode, 200)
        self.assertIsNone(cancel_cb)
        self.assertIsNone(noack_cb)
        self.assertIn('sip:alice@example.com', self.server.locations)
        self.assertEqual(len(self.server.locations['sip:alice@example.com']), 1)
        contacts = resp.getHFBodys('contact')
        self.assertEqual(len(contacts), 1)
        self.assertEqual(str(contacts[0].getUrl()), 'sip:alice@192.0.2.10:5060')
        self.assertGreater(int(contacts[0].address.params['expires']), 0)

    def test_register_query_returns_current_bindings(self):
        self.server.recvRequest(self.make_register((self.make_contact(),), expires = 120))

        resp, _, _ = self.server.recvRequest(self.make_register())

        self.assertEqual(resp.scode, 200)
        self.assertEqual(len(resp.getHFBodys('contact')), 1)

    def test_lookup_binding_returns_registered_contact(self):
        self.server.recvRequest(self.make_register((self.make_contact(),), expires = 120))

        binding = self.server.lookupBinding(SipURL('sip:alice@example.com'))

        self.assertIsNotNone(binding)
        self.assertEqual(str(binding.contact.getUrl()), 'sip:alice@192.0.2.10:5060')

    def test_registered_route_aor_prefers_request_uri_domain(self):
        from sippy.b2bua import CallController

        cc = object.__new__(CallController)
        cc.req_target = SipURL('sip:alice@198.51.100.10')

        self.assertEqual(str(cc.getRegisteredAOR('bob')), 'sip:bob@198.51.100.10')

    def test_registered_route_lookup_does_not_use_to_domain(self):
        from sippy.b2bua import CallController

        config = self.make_config()
        config['_registrar'] = self.server
        self.server.recvRequest(self.make_register((self.make_contact(),), expires = 120))
        cc = object.__new__(CallController)
        cc.global_config = config
        cc.req_target = SipURL('sip:alice@198.51.100.10')

        aor, binding = cc.lookupRegisteredBinding('alice')

        self.assertIsNone(aor)
        self.assertIsNone(binding)

    def test_registered_route_lookup_prefers_request_uri_binding(self):
        from sippy.b2bua import CallController

        config = self.make_config()
        config['_registrar'] = self.server
        self.server.recvRequest(self.make_register((self.make_contact(),), expires = 120))
        cc = object.__new__(CallController)
        cc.global_config = config
        cc.req_target = SipURL('sip:alice@example.com')

        aor, binding = cc.lookupRegisteredBinding('alice')

        self.assertEqual(str(aor), 'sip:alice@example.com')
        self.assertIsNotNone(binding)

    def test_unregister_contact_removes_binding(self):
        contact = self.make_contact()
        self.server.recvRequest(self.make_register((contact,), expires = 120))

        resp, _, _ = self.server.recvRequest(self.make_register((contact,), expires = 0))

        self.assertEqual(resp.scode, 200)
        self.assertNotIn('sip:alice@example.com', self.server.locations)
        self.assertEqual(len(resp.getHFBodys('contact')), 0)

    def test_wildcard_unregister_requires_zero_expires(self):
        self.server.recvRequest(self.make_register((self.make_contact(),), expires = 120))

        bad_resp, _, _ = self.server.recvRequest(self.make_register((SipContact(body = '*'),), expires = 120))
        good_resp, _, _ = self.server.recvRequest(self.make_register((SipContact(body = '*'),), expires = 0))

        self.assertEqual(bad_resp.scode, 400)
        self.assertEqual(good_resp.scode, 200)
        self.assertNotIn('sip:alice@example.com', self.server.locations)

    def test_radius_auth_uses_register_method(self):
        config = self.make_config(auth_enable = True)
        config['_radius_client'] = FakeRadius()
        config['_sip_tm'] = FakeSipTM()
        server = SipRegistrationServer(config)

        rval = server.recvRequest(self.make_register((self.make_contact(),), expires = 120), sip_t = object())

        self.assertEqual(rval, (None, None, None))
        self.assertEqual(config['_radius_client'].calls[0]['method'], 'REGISTER')
        self.assertEqual(config['_sip_tm'].responses[0][0].scode, 200)

if __name__ == '__main__':
    unittest.main()
