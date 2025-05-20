# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2016 Sippy Software, Inc. All rights reserved.
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

from sippy.SipHeader import SipHeader
from sippy.SipConf import SipConf
from sippy.B2B.Transforms import getTransProc

try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote
from socket import getaddrinfo, SOCK_STREAM, AF_INET, AF_INET6

SRC_WSS = '[[WSS]]'
SRC_PROXY = '[[PROXY]]'
DST_SIP_UA = 'sip-ua'
DST_WSS_UA = 'wss-ua'

class B2BRoute(object):
    crt_set = False
    params = None
    extra_headers = None
    rnum = None
    _ui_cats = {'auth': 'Outbound Digest Authentication', 'net': 'Network', 'lim': 'Limits',
                      'num': 'Calling / Called Numbers', 'acct': 'Accounting'}
    _ui_hints = {}
#    _ui_hints['rnum'] = {'hidden': True}
    addrinfo = None
#    _ui_hints['addrinfo'] = {'readonly': True, 'category': _ui_cats['net'], 'hidden': True}
    hostonly:str = None
#    _ui_hints['hostonly'] = {'readonly': True, 'category': _ui_cats['net'], 'hidden': True}
    ainfo = None
#    _ui_hints['ainfo'] = {'readonly': True, 'category': _ui_cats['net'], 'hidden': True}
    hostport:str = None
    _ui_hints['hostport'] = {'name': 'Destination', 'description': 'Destination host:port',
                                'category': _ui_cats['net']}
    user:str = None
    _ui_hints['user'] = {'name': 'SIP Username', 'category': _ui_cats['auth'],
                'active': lambda o: not o.pass_auth}
    passw:str = None
    _ui_hints['passw'] = {'name': 'SIP Password', 'category': _ui_cats['auth'], 'password': True,
                 'active': lambda o: not o.pass_auth}
    pass_auth = True
    _ui_hints['pass_auth'] = {'name': 'Mode', 'category': _ui_cats['auth'],
                     'values': {False: 'Normal ("UAC")', True: 'Pass-through ("Proxy")'},}
    _cld:str = None
    _ui_hints['cld'] = {'name': 'Called Party (CLD)', 'description': 'Called party number',
               'category': _ui_cats['num'], 'type': str}
    cld_set = False
    _ui_hints['cld_set'] = {'name': 'CLD Mode', 'description': 'Controls outbound CLD',
                   'category': _ui_cats['num'], 'active': lambda o: not o.cld,
                   'values': lambda o: {True: 'Erase', False: 'Pass-through'}
                               if not o.cld else {True: 'Replace'}}
    _cli:str = None
    _ui_hints['cli'] = {'name': 'Calling Party (CLI)', 'description': 'Caller number',
               'category': _ui_cats['num'], 'type': str}
    cli_set = False
    _ui_hints['cli_set'] = {'name': 'CLI Mode', 'description': 'Controls outbound CLI', 'category':
                   _ui_cats['num'], 'active': lambda o: not o.cli,
                   'values': lambda o: {True: 'Erase', False: 'Pass-through'}
                               if not o.cli else {True: 'Replace'}}
    credit_time:float = None
    _ui_hints['credit_time'] = {'name': 'Credit Time', 'description': 'Allowed call duration, in seconds',
                                   'category': _ui_cats['lim']}
    expires:float = None
    _ui_hints['expires'] = {'name': 'Route Expiry', 'description': 'Time to expire the route, in seconds',
                               'category': _ui_cats['lim']}
    no_progress_expires:float = None
    _ui_hints['no_progress_expires'] = {'name': 'No Progress Timeout', 'category': _ui_cats['lim'],
      'description': 'Time to expire the route if no 180 or 183 provisional response received, in seconds'}
    no_reply_expires:float = None
    _ui_hints['no_reply_expires'] = {'name': 'No Reply Timeout', 'category': _ui_cats['lim'],
      'description': 'Time to expire the route if no provisional response received, in seconds'}
    forward_on_fail = False
    _ui_hints['forward_on_fail'] = {'name': 'Failed Calls', 'category': _ui_cats['acct'],
                           'description': 'Emit accounting on SIP failures'}

    def __init__(self, sroute = None, cself = None):
        if cself != None:
            self.rnum = cself.rnum
            self.addrinfo = cself.addrinfo
            self._cld = cself.cld
            self.cld_set = cself.cld_set
            self.hostport = cself.hostport
            self.hostonly = cself.hostonly
            self.credit_time = cself.credit_time
            self.crt_set = cself.crt_set
            self.expires = cself.expires
            self.no_progress_expires = cself.no_progress_expires
            self.no_reply_expires = cself.no_reply_expires
            self.forward_on_fail = cself.forward_on_fail
            self.user = cself.user
            self.passw = cself.passw
            self.pass_auth = cself.pass_auth
            self._cli = cself.cli
            self.cli_set = cself.cli_set
            self.params = dict(cself.params)
            self.ainfo = cself.ainfo
            if cself.extra_headers is not None:
                self.extra_headers = tuple([x.getCopy() for x in cself.extra_headers])
            return
        route = sroute.split(';')
        if route[0].find('@') != -1:
            self.cld, self.hostport = route[0].split('@', 1)
            if len(self.cld) == 0:
                # Allow CLD to be forcefully removed by sending `Routing:@host' entry,
                # as opposed to the Routing:host, which means that CLD should be obtained
                # from the incoming call leg.
                self.cld = None
        else:
            self.hostport = route[0]
        if not self.hostport.startswith('['):
            hostport = self.hostport.split(':', 1)
            af = 0
            self.hostonly = hostport[0]
        else:
            hostport = self.hostport[1:].split(']', 1)
            if len(hostport) > 1:
                if len(hostport[1]) == 0:
                    del hostport[1]
                else:
                    hostport[1] = hostport[1][1:]
            af = AF_INET6
            self.hostonly = '[%s]' % hostport[0]
        if len(hostport) == 1:
            port = SipConf.default_port
        else:
            port = int(hostport[1])
        if not hostport[0] in (DST_SIP_UA, DST_WSS_UA):
            self.ainfo = getaddrinfo(hostport[0], port, af, SOCK_STREAM)
        self.params = {}
        extra_headers = []
        for a, v in [x.split('=', 1) for x in route[1:]]:
            if a == 'credit-time':
                self.credit_time = int(v)
                if self.credit_time < 0:
                    self.credit_time = None
                self.crt_set = True
            elif a == 'expires':
                self.expires = int(v)
                if self.expires < 0:
                    self.expires = None
            elif a == 'hs_scodes':
                self.params['huntstop_scodes'] = tuple([int(x) for x in v.split(',') if len(x.strip()) > 0])
            elif a == 'np_expires':
                self.no_progress_expires = int(v)
                if self.no_progress_expires < 0:
                    self.no_progress_expires = None
            elif a == 'nr_expires':
                self.no_reply_expires = int(v)
                if self.no_reply_expires < 0:
                    self.no_reply_expires = None
            elif a == 'forward_on_fail':
                self.forward_on_fail = True
            elif a == 'auth':
                self.pass_auth = False
                if v != 'nopass':
                    self.user, self.passw = v.split(':', 1)
            elif a == 'cli':
                self.cli = v
                if len(self.cli) == 0:
                    self.cli = None
            elif a == 'cnam':
                caller_name = unquote(v)
                if len(caller_name) == 0:
                    caller_name = None
                self.params['caller_name'] = caller_name
            elif a == 'ash':
                ash = SipHeader(unquote(v))
                extra_headers.append(ash)
            elif a == 'rtpp':
                self.params['rtpp'] = (int(v) != 0)
            elif a == 'op':
                host_port = v.split(':', 1)
                if len(host_port) == 1:
                    self.params['outbound_proxy'] = (v, 5060)
                else:
                    self.params['outbound_proxy'] = (host_port[0], int(host_port[1]))
            elif a == 'po_proc':
                self.params['po_proc'] = getTransProc(v)
            else:
                self.params[a] = v
        if len(extra_headers) > 0:
            self.extra_headers = tuple(extra_headers)

    def customize(self, rnum, default_cld, default_cli, default_credit_time, \
      pass_headers, max_credit_time):
        self.rnum = rnum
        if not self.cld_set:
            self._cld = default_cld
        if not self.cli_set:
            self._cli = default_cli
        if not self.crt_set:
            self.crt_set = default_credit_time
        if 'gt' in self.params:
            timeout, skip = self.params['gt'].split(',', 1)
            self.params['group_timeout'] = (int(timeout), rnum + int(skip))
        if self.extra_headers is not None:
            self.extra_headers = self.extra_headers + tuple(pass_headers)
        else:
            self.extra_headers = tuple(pass_headers)
        if max_credit_time != None:
            if self.credit_time == None or self.credit_time > max_credit_time:
                self.credit_time = max_credit_time

    def getCopy(self):
        return self.__class__(cself = self)

    def getNHAddr(self, source):
        if source[0].startswith('['):
            af = AF_INET6
        else:
            af = AF_INET
        amatch = [x[4] for x in self.ainfo if x[0] == af]
        same_af = True
        if len(amatch) == 0:
            same_af = False
            amatch = self.ainfo[0][4]
            af = self.ainfo[0][0]
        else:
            amatch = amatch[0]
        if af == AF_INET6:
            return ((('[%s]' % amatch[0], amatch[1]), same_af))
        return (((amatch[0], amatch[1]), same_af))

    @property
    def cli(self):
        return self._cli

    @cli.setter
    def cli(self, value):
        self._cli = value
        self.cli_set = True

    @property
    def cld(self):
        return self._cld

    @cld.setter
    def cld(self, value):
        self._cld = value
        self.cld_set = True
