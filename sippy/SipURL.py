# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2014 Sippy Software, Inc. All rights reserved.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from sippy.SipConf import SipConf
try:
    from urllib import quote, unquote
except ImportError:
    from urllib.parse import quote, unquote

RFC3261_USER_UNRESERVED = '&=+$,;?/#'
# Quote from RFC-3261:
# Several rules are incorporated from RFC 2396 [5] but are updated to
# make them compliant with RFC 2234
RFC3261_MARK = '-_.!~*\'()'

USERNAME_SAFE = RFC3261_USER_UNRESERVED + RFC3261_MARK

class SipURL(object):
    scheme = None
    username = None
    userparams = None
    password = None
    host = None
    port = None
    headers = None
    usertype = None
    transport = None
    ttl = None
    maddr = None
    method = None
    tag = None
    other = None
    lr = False

    def __init__(self, url = None, username = None, password = None, host = None, port = None, headers = None, \
      usertype = None, transport = None, ttl = None, maddr = None, method = None, tag = None, other = None, \
      userparams = None, lr = False, relaxedparser = False, scheme = "sip"):
        self.original_uri = url
        self.other = []
        self.userparams = []
        if url == None:
            self.scheme = scheme
            self.username = username
            if userparams != None:
                self.userparams = userparams
            self.password = password
            if host == None:
                self.host = SipConf.my_address
                self.port = SipConf.my_port
                self.transport = SipConf.my_transport
            else:
                self.host = host
                self.port = port
                self.transport = transport
            self.headers = headers
            self.usertype = usertype
            self.ttl = ttl
            self.maddr = maddr
            self.method = method
            self.tag = tag
            if other != None:
                self.other = other
            self.lr = lr
            return
        parts = url.split(':', 1)
        if len(parts) < 2:
            # scheme is missing, assume sip:
            parts.insert(0, 'sip')
        parts[0] = parts[0].lower()
        if parts[0] not in ('sip', 'sips', 'tel'):
            raise ValueError('unsupported scheme: %s:' % parts[0])
        self.scheme, url = parts
        if self.scheme == 'tel':
            if SipConf.autoconvert_tel_url:
                self.convertTelURL(url, relaxedparser)
            else:
                raise ValueError('tel: scheme is not supported')
        else:
            self.parseSipURL(url, relaxedparser)

    def convertTelURL(self, url, relaxedparser):
        self.scheme = 'sip'
        if relaxedparser:
            self.host = ''
        else:
            self.host = SipConf.my_address
            self.port = SipConf.my_port
            self.transport = SipConf.my_transport
        parts = url.split(';')
        self.username = unquote(parts[0])
        if len(parts) > 1:
            # parse userparams
            self.userparams = []
            for part in parts[1:]:
                # The RFC-3261 suggests the user parameter keys should
                # be converted to lower case.
                k, v = part.split('=')
                self.userparams.append(k.lower() + '=' + v)

    def parseSipURL(self, url, relaxedparser):
        ear = url.find('@') + 1
        parts = url[ear:].split(';')
        userdomain, params = url[0:ear] + parts[0], parts[1:]
        if len(params) == 0 and '?' in userdomain[ear:]:
            self.headers = {}
            userdomain_suff, headers = userdomain[ear:].split('?', 1)
            userdomain = userdomain[:ear] + userdomain_suff
            for header in headers.split('&'):
                k, v = header.split('=')
                self.headers[k] = unquote(v)
        if ear > 0:
            userpass = userdomain[:ear - 1]
            hostport = userdomain[ear:]
            upparts = userpass.split(':', 1)
            if len(upparts) > 1:
                self.password = upparts[1]
            uparts = upparts[0].split(';')
            if len(uparts) > 1:
                self.userparams = uparts[1:]
            self.username = unquote(uparts[0])
        else:
            hostport = userdomain
        parseport = None
        if relaxedparser and len(hostport) == 0:
            self.host = ''
        elif hostport[0] == '[':
            # IPv6 host
            hpparts = hostport.split(']', 1)
            self.host = hpparts[0] + ']'
            if len(hpparts[1]) > 0:
                hpparts = hpparts[1].split(':', 1)
                if len(hpparts) > 1:
                    parseport = hpparts[1]
        else:
            # IPv4 host
            hpparts = hostport.split(':', 1)
            if len(hpparts) == 1:
                self.host = hpparts[0]
            else:
                self.host = hpparts[0]
                parseport = hpparts[1]

        if parseport != None:
            try:
                self.port = int(parseport)
            except Exception as e:
                # Can't parse port number, check why
                port = parseport.strip()
                if len(port) == 0:
                    # Bug on the other side, work around it
                    print('WARNING: non-compliant URI detected, empty port number, ' \
                      'assuming default: "%s"' % str(self.original_uri))
                elif port.find(':') > 0:
                    pparts = port.split(':', 1)
                    if pparts[0] == pparts[1]:
                        # Bug on the other side, work around it
                        print('WARNING: non-compliant URI detected, duplicate port number, ' \
                          'taking "%s": %s' % (pparts[0], str(self.original_uri)))
                        self.port = int(pparts[0])
                    else:
                        raise e
                else:
                    raise e
        if len(params) > 0:
            last_param = params[-1]
            arr = last_param.split('?', 1)
            params[-1] = arr[0]
            self.setParams(params)
            if len(arr) == 2:
                self.headers = {}
                for header in arr[1].split('&'):
                    k, v = header.split('=')
                    self.headers[k] = unquote(v)

    def setParams(self, params):
        self.usertype = None
        self.transport = None
        self.ttl = None
        self.maddr = None
        self.method = None
        self.tag = None
        self.other = []
        self.lr = False

        for p in params:
            nv = p.split('=', 1)
            if len(nv) == 1:
                if p == 'lr':
                    self.lr = True
                else:
                    self.other.append(p)
                continue
            name, value = nv
            if name == 'user':
                self.usertype = value
            elif name == 'transport':
                self.transport = value
            elif name == 'ttl':
                self.ttl = int(value)
            elif name == 'maddr':
                self.maddr = value
            elif name == 'method':
                self.method = value
            elif name == 'tag':
                self.tag = value
            elif name == 'lr':
                # RFC 3261 doesn't allow lr parameter to have a value,
                # but many stupid implementation do it anyway
                self.lr = True
            else:
                self.other.append(p)

    def __str__(self):
        return self.localStr()

    def localStr(self, local_addr = None):
        if local_addr is not None:
            (local_addr, local_port), local_transport = local_addr
        else:
            local_addr = local_port = local_transport = None
        l = []; w = l.append
        w(self.scheme + ':')
        if self.username != None:
            w(quote(self.username, USERNAME_SAFE))
            for v in self.userparams:
                w(';%s' % v)
            if self.password != None:
                w(':%s' % self.password)
            w('@')
        if local_addr != None and 'my' in dir(self.host):
            w(local_addr)
        else:
            w(str(self.host))

        def port_needed(port):
            return SipConf.port_needed(port, self.transport, local_transport)

        if self.port != None:
            if local_port is not None and 'my' in dir(self.port):
                if port_needed(local_port):
                    w(':%d' % local_port)
            elif port_needed(self.port):
                w(':%d' % self.port)
        for p in self.getParams(local_transport):
            w(';%s' % p)
        if self.headers:
            w('?')
            w('&'.join([('%s=%s' % (h, quote(v))) for (h, v) in self.headers.items()]))
        return ''.join(l)

    def getParams(self, local_transport=None):
        res = []; w = res.append
        if self.usertype != None:
            w('user=%s' % self.usertype)
        for n in ('transport', 'ttl', 'maddr', 'method', 'tag'):
            v = getattr(self, n)
            if v is None: continue
            if n == 'transport' and 'my' in dir(v):
                if local_transport in (None, SipConf.default_transport):
                    continue
                v = local_transport
            w('%s=%s' % (n, v))
        for v in self.other:
            w(v)
        if self.lr:
            w('lr')
        return res

    def getCopy(self):
        return SipURL(username = self.username, password = self.password, host = self.host, port = self.port, \
          headers = self.headers, usertype = self.usertype, transport = self.transport, ttl = self.ttl, \
          maddr = self.maddr, method = self.method, tag = self.tag, other = list(self.other), \
          userparams = list(self.userparams), lr = self.lr)

    def getHost(self):
        return self.host

    def getPort(self):
        if self.port != None:
            return self.port
        else:
            return SipConf.default_port

    def getAddr(self):
        if self.port != None:
            return (self.host, self.port)
        else:
            return (self.host, SipConf.default_port)

    def getTAddr(self):
        _t = self.transport if self.transport is not None else SipConf.default_transport
        return (self.getAddr(), _t)

    def setAddr(self, addr):
        self.host, self.port = addr

if __name__ == '__main__':
    import sys

    test_set = (('sip:user;par=u%40example.net@example.com', ()), \
      ('sip:user@example.com?Route=%3Csip%3Aexample.com%3E', ()), \
      ('sip:[2001:db8::10]', ()), \
      ('sip:[2001:db8::10]:5070', ()), \
      ('sip:user@example.net;tag=9817--94', ('tag=9817--94',)), \
      ('sip:alice@atlanta.com;ttl=15;maddr=239.255.255.1', ('ttl=15', 'maddr=239.255.255.1')), \
      ('sip:alice:secretword@atlanta.com;transport=tcp', ('transport=tcp',)), \
      ('sip:alice@atlanta.com?subject=project%20x&priority=urgent', ()), \
      ('sip:+1-212-555-1212:1234@gateway.com;user=phone', ('user=phone',)), \
      ('sip:atlanta.com;method=REGISTER?to=alice%40atlanta.com', ('method=REGISTER',)), \
      ('sip:alice;day=tuesday@atlanta.com', ()), \
      ('sip:+611234567890@ims.mnc000.mcc000.3gppnetwork.org;user=phone;npdi', ('user=phone', 'npdi')), \
      ('sip:1234#567890@example.com', ()), \
      ('sip:foo@1.2.3.4:', ()), \
      ('sip:foo@1.2.3.4:5060:5060', ()))
    for u, mp in test_set:
        su = SipURL(u)
        sp = su.getParams()
        print(tuple(sp), mp, su.getHost(), su.getPort())
        if str(su) != u:
            sys.stderr.write('URI cannot be reconstructed precisely: expected \'%s\' got \'%s\'\n' % (u, str(su)))
