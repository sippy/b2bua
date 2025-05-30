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

from sippy.Core.Exceptions import dump_exception
from sippy.Time.MonoTime import MonoTime
from sippy.Time.Timeout import Timeout
from sippy.SipHeader import SipHeader
from sippy.SipResponse import SipResponse
from sippy.SipRequest import SipRequest
from sippy.SipAddress import SipAddress
from sippy.SipRoute import SipRoute
from sippy.SipHeader import SipHeader
from sippy.Exceptions.SipParseError import SipParseError
from sippy.Exceptions.SdpParseError import SdpParseError
from sippy.Exceptions.RtpProxyError import RtpProxyError
from sippy.Udp_server import Udp_server, Udp_server_opts
from sippy.Network_server import Remote_address
from datetime import datetime
from hashlib import md5
from functools import reduce
from time import monotonic
import sys, socket

class NETS_1918(object):
    nets = (('10.0.0.0', 0xffffffff << 24), ('172.16.0.0',  0xffffffff << 20), ('192.168.0.0', 0xffffffff << 16))
    nets = [(reduce(lambda z, v: (int(z) << 8) | int(v), x[0].split('.', 4)) & x[1], x[1]) for x in nets]

def check1918(addr):
    try:
        addr = reduce(lambda x, y: (int(x) << 8) | int(y), addr.split('.', 4))
        for naddr, mask in NETS_1918.nets:
            if addr & mask == naddr:
                return True
    except:
        pass
    return False

def check7118(host):
    return host.endswith('.invalid')

class SipTransactionConsumer(object):
    compact = False
    cobj = None

    def __init__(self, cobj, compact):
        self.compact = compact
        self.cobj = cobj

    def cleanup(self):
        self.cobj = None

class SipTransaction(object):
    tout = None
    tid = None
    address = None
    data = None
    checksum = None
    cb_ifver = None
    uack = False
    compact = False
    req_out_cb = None
    res_out_cb = None

    def cleanup(self):
        self.ack = None
        self.cancel = None
        self.resp_cb = None
        self.cancel_cb = None
        self.noack_cb = None
        self.ack_cb = None
        self.r487 = None
        self.address = None
        self.teA = self.teB = self.teC = self.teD = self.teE = self.teF = self.teG = None
        self.tid = None
        self.userv = None
        self.r408 = None
        self.req_out_cb = None
        self.res_out_cb = None

# Symbolic states names
class SipTransactionState(object):
    pass
class TRYING(SipTransactionState):
    # Request sent, but no reply received at all
    pass
class RINGING(SipTransactionState):
    # Provisional reply has been received
    pass
class COMPLETED(SipTransactionState):
    # Transaction already ended with final reply
    pass
class CONFIRMED(SipTransactionState):
    # Transaction already ended with final reply and ACK received (server-only)
    pass
class TERMINATED(SipTransactionState):
    # Transaction ended abnormally (request timeout and such)
    pass
class UACK(SipTransactionState):
    # UAC wants to generate ACK at its own discretion
    pass

class local4remote(object):
    global_config = None
    cache_r2l = None
    cache_r2l_old = None
    cache_l2s = None
    skt = None
    handleIncoming = None
    fixed = False
    ploss_out_rate = 0.0
    pdelay_out_max = 0.0

    def __init__(self, global_config, handleIncoming, usc, usoc):
        self.Udp_server_opts = usoc
        self.udp_server_class = usc
        self.global_config = global_config
        self.cache_r2l = {}
        self.cache_r2l_old = {}
        self.cache_l2s = {}
        self.handleIncoming = handleIncoming
        try:
            # Python can be compiled with IPv6 support, but if kernel
            # has not we would get exception creating the socket.
            # Workaround that by trying create socket and checking if
            # we get an exception.
            socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        except:
            socket.has_ipv6 = False
        if 'my' in dir(global_config['_sip_address']):
            if socket.has_ipv6:
                laddresses = (('0.0.0.0', global_config['_sip_port']), ('[::]', global_config['_sip_port']))
            else:
                laddresses = (('0.0.0.0', global_config['_sip_port']),)
        else:
            laddresses = ((global_config['_sip_address'], global_config['_sip_port']),)
            self.fixed = True
        # Since we are (an)using SO_REUSEXXX do a quick dry run to make
        # sure no existing app is running on the same port.
        for dryr in (True, False):
            for laddress in laddresses:
                self.initServer(laddress, dryr)

    def initServer(self, laddress, dryr=False):
        sopts = self.Udp_server_opts(laddress, self.handleIncoming)
        sopts.ploss_out_rate = self.ploss_out_rate
        sopts.pdelay_out_max = self.pdelay_out_max
        if dryr:
            sopts.flags = 0
        server = self.udp_server_class(self.global_config, sopts)
        if dryr:
            server.shutdown()
            return None
        self.cache_l2s[laddress] = server
        return server

    def getServer(self, address, is_local = False):
        if self.fixed:
            return tuple(self.cache_l2s.items())[0][1]
        if not is_local:
            laddress = self.cache_r2l.get(address[0], None)
            if laddress == None:
                laddress = self.cache_r2l_old.get(address[0], None)
                if laddress != None:
                    self.cache_r2l[address[0]] = laddress
            if laddress != None:
                #print('local4remot-1: local address for %s is %s' % (address[0], laddress[0]))
                return self.cache_l2s[laddress]
            if address[0].startswith('['):
                family = socket.AF_INET6
                lookup_address = address[0][1:-1]
            else:
                family = socket.AF_INET
                lookup_address = address[0]
            self.skt = socket.socket(family, socket.SOCK_DGRAM)
            ai = socket.getaddrinfo(lookup_address, None, family)
            if family == socket.AF_INET:
                _address = (ai[0][4][0], address[1])
            else:
                _address = (ai[0][4][0], address[1], ai[0][4][2], ai[0][4][3])
            self.skt.connect(_address)
            if family == socket.AF_INET:
                laddress = (self.skt.getsockname()[0], self.global_config['_sip_port'])
            else:
                laddress = ('[%s]' % self.skt.getsockname()[0], self.global_config['_sip_port'])
            self.cache_r2l[address[0]] = laddress
        else:
            laddress = address
        server = self.cache_l2s.get(laddress, None)
        if server == None:
            server = self.initServer(laddress)
        #print('local4remot-2: local address for %s is %s' % (address[0], laddress[0]))
        return server

    def rotateCache(self):
        self.cache_r2l_old = self.cache_r2l
        self.cache_r2l = {}

    def shutdown(self):
        for userv in self.cache_l2s.values():
            userv.shutdown()
        self.cache_l2s = {}

class SipTMRetransmitO(object):
    userv = None
    data = None
    address = None
    call_id = None
    lossemul = None

    def __init__(self, userv = None, data = None, address = None,
      call_id = None, lossemul = None):
        self.userv = userv
        self.data = data
        self.address = address
        self.call_id = call_id
        self.lossemul = lossemul

class SipTransactionManager(object):
    global_config = None
    l4r = None
    tclient = None
    tserver = None
    req_cb = None
    l1rcache = None
    l2rcache = None
    nat_traversal = False
    req_consumers = None
    provisional_retr = 0
    ploss_out_rate = 0.0
    pdelay_out_max = 0.0
    model_udp_server = (Udp_server, Udp_server_opts)
    cp_timer = None
    init_time = None

    def __init__(self, global_config, req_cb = None):
        self.global_config = global_config
        self.l4r = local4remote(global_config, self.handleIncoming, *self.model_udp_server)
        self.l4r.ploss_out_rate = self.ploss_out_rate
        self.l4r.pdelay_out_max = self.pdelay_out_max
        self.tclient = {}
        self.tserver = {}
        self.req_cb = req_cb
        self.l1rcache = {}
        self.l2rcache = {}
        self.req_consumers = {}
        self.cp_timer = Timeout(self.rCachePurge, 32, -1)
        self.init_time = monotonic()

    def handleIncoming(self, data_in, ra:Remote_address, server, rtime):
        if len(data_in) < 32:
            return
        if isinstance(data_in, bytes):
            lmsg = data_in.decode(errors = 'backslashreplace')
        else:
            lmsg = data_in
        self.global_config['_sip_logger'].write(f'RECEIVED message from {ra}:\n', \
          lmsg, ltime = rtime.realt)
        if isinstance(data_in, bytes):
            data = data_in.decode()
            checksum = md5(data_in).digest()
        else:
            data = data_in
            checksum = md5(data_in.encode('utf-8')).digest()
        retrans = self.l1rcache.get(checksum, None)
        if retrans == None:
            retrans = self.l2rcache.get(checksum, None)
        if retrans != None:
            if retrans.data == None:
                return
            self.transmitData(retrans.userv, retrans.data, retrans.address, \
              lossemul = retrans.lossemul)
            return
        if data.startswith('SIP/2.0 '):
            try:
                resp = SipResponse(data)
                tid = resp.getTId(True, True)
            except Exception as exception:
                dump_exception(f'can\'t parse SIP response from {ra}', extra = data)
                self.l1rcache[checksum] = SipTMRetransmitO()
                return
            if resp.getSCode()[0] < 100 or resp.getSCode()[0] > 999:
                print(datetime.now(), f'invalid status code in SIP response from {ra}:')
                print(data)
                sys.stdout.flush()
                self.l1rcache[checksum] = SipTMRetransmitO()
                return
            resp.rtime = rtime
            if not tid in self.tclient:
                #print('no transaction with tid of %s in progress' % str(tid))
                self.l1rcache[checksum] = SipTMRetransmitO()
                return
            t = self.tclient[tid]
            if self.nat_traversal and resp.countHFs('contact') > 0 and not check1918(t.address[0]):
                cbody = resp.getHFBody('contact')
                if not cbody.asterisk:
                    curl = cbody.getUrl()
                    if check1918(curl.host):
                        curl.host, curl.port = ra.address
            if ra.transport == 'wss' and resp.countHFs('contact') > 0:
                cbody = resp.getHFBody('contact')
                if not cbody.asterisk:
                    curl = cbody.getUrl()
                    curl.host = ra.received
            resp.setSource(ra)
            self.incomingResponse(resp, t, checksum)
        else:
            try:
                req = SipRequest(data)
                tids = req.getTIds()
            except Exception as exception:
                if isinstance(exception, SipParseError):
                    resp = exception.getResponse()
                    if resp is not None:
                        self.transmitMsg(server, resp, ra.address, checksum)
                dump_exception(f'can\'t parse SIP request from {ra}', extra = data)
                self.l1rcache[checksum] = SipTMRetransmitO()
                return
            call_id = tids[0][0]
            req.rtime = rtime
            via0 = req.getHFBody('via')
            ahost, aport = via0.getAddr()
            rhost, rport = ra.address
            if ra.transport != 'wss' and self.nat_traversal and rport != aport \
              and (check1918(ahost) or check7118(ahost)):
                req.nated = True
            if ahost != rhost:
                via0.params['received'] = ra.received
            if 'rport' in via0.params or req.nated:
                via0.params['rport'] = str(rport)

            def usable_contact():
                return req.countHFs('contact') > 0 and req.countHFs('via') == 1

            def get_contact():
                try:
                    return req.getHFBody('contact')
                except Exception as exception:
                    dump_exception(f'can\'t parse SIP request from {ra}', extra = data)
                    self.l1rcache[checksum] = SipTMRetransmitO()
                    return None

            if self.nat_traversal and usable_contact():
                if (cbody:=get_contact()) is None: return
                if not cbody.asterisk:
                    curl = cbody.getUrl()
                    if check1918(curl.host) or curl.port == 0 or curl.host == '255.255.255.255':
                        curl.host, curl.port = ra.address
                        req.nated = True
            if ra.transport == 'wss' and usable_contact():
                if (cbody:=get_contact()) is None: return
                if not cbody.asterisk:
                    curl = cbody.getUrl()
                    curl.host = ra.received
            req.setSource(ra)
            def ex_sendResponse(r):
                self.transmitMsg(server, r, r.getHFBody('via').getTAddr(), checksum, call_id)
            try:
                self.incomingRequest(req, checksum, tids, server)
            except RtpProxyError as ex:
                resp = ex.getResponse(req)
                self.sendResponse(resp)
                # Give RTP proxy some time to warm up
                if monotonic() - self.init_time > 5: raise
            except SdpParseError as ex:
                resp = ex.getResponse(req)
                self.sendResponse(resp)
            except SipParseError as ex:
                resp = ex.getResponse(req)
                if resp is None:
                    raise ex
                ex_sendResponse(resp)

    # 1. Client transaction methods
    def newTransaction(self, msg, resp_cb = None, laddress = None, userv = None, \
      cb_ifver = 1, compact = False, t = None):
        if t == None:
            t = SipTransaction()
        t.rtime = MonoTime()
        t.compact = compact
        t.method = msg.getMethod()
        t.cb_ifver = cb_ifver
        t.tid = msg.getTId(True, True)
        if t.tid in self.tclient:
            raise ValueError('BUG: Attempt to initiate transaction with the same TID as existing one!!!')
        t.tout = 0.5
        t.fcode = None
        t.address, transport = msg.getTarget()
        if userv == None:
            transport = str(transport)
            if transport == 'udp':
                if laddress == None:
                    t.userv = self.l4r.getServer(t.address)
                else:
                    t.userv = self.l4r.getServer(laddress, is_local = True)
            elif transport in ('ws', 'wss'):
                t.userv = self.global_config['_wss_server']
            else:
                raise RuntimeError(f'BUG: newTransaction() to unsupported transport: {transport}')
        else:
            t.userv = userv
        t.data = msg.localStr(t.userv.getSIPaddr(), compact = t.compact)
        if t.method == 'INVITE':
            try:
                t.expires = msg.getHFBody('expires').getNum()
                if t.expires <= 0:
                    t.expires = 300
            except IndexError:
                t.expires = 300
            t.needack = True
            t.ack = msg.genACK()
            t.cancel = msg.genCANCEL()
        else:
            t.expires = 32
            t.needack = False
            t.ack = None
            t.cancel = None
        t.cancelPending = False
        t.resp_cb = resp_cb
        t.teA = Timeout(self.timerA, t.tout, 1, t)
        if resp_cb != None:
            t.r408 = msg.genResponse(408, 'Request Timeout')
        t.teB = Timeout(self.timerB, 32.0, 1, t)
        t.teC = None
        t.state = TRYING
        self.tclient[t.tid] = t
        self.transmitData(t.userv, t.data, t.address)
        if t.req_out_cb != None:
            t.req_out_cb(msg)
        return t

    def cancelTransaction(self, t, extra_headers = None):
        # If we got at least one provisional reply then (state == RINGING)
        # then start CANCEL transaction, otherwise deffer it
        if t.state != RINGING:
            t.cancelPending = True
        else:
            if extra_headers is not None:
                t.cancel.appendHeaders(extra_headers)
            self.newTransaction(t.cancel, userv = t.userv)

    def incomingResponse(self, msg, t, checksum):
        # In those two states upper level already notified, only do ACK retransmit
        # if needed
        if t.state == TERMINATED:
            return

        if t.state == TRYING:
            # Stop timers
            if t.teA != None:
                t.teA.cancel()
                t.teA = None

        if t.state in (TRYING, RINGING):
            if t.teB != None:
                t.teB.cancel()
                t.teB = None

            if msg.getSCode()[0] < 200:
                # Privisional response - leave everything as is, except that
                # change state and reload timeout timer
                if t.state == TRYING:
                    t.state = RINGING
                    if t.cancelPending:
                        self.newTransaction(t.cancel, userv = t.userv)
                        t.cancelPending = False
                t.teB = Timeout(self.timerB, t.expires, 1, t)
                self.l1rcache[checksum] = SipTMRetransmitO()
                if t.resp_cb != None:
                    if t.cb_ifver == 1:
                        t.resp_cb(msg)
                    else:
                        t.resp_cb(msg, t)
            else:
                # Final response - notify upper layer and remove transaction
                if t.needack:
                    # Prepare and send ACK if necessary
                    fcode = msg.getSCode()[0]
                    tag = msg.getHFBody('to').getTag()
                    if tag != None:
                        t.ack.getHFBody('to').setTag(tag)
                    rAddr = None
                    if msg.getSCode()[0] >= 200 and msg.getSCode()[0] < 300:
                        # Some hairy code ahead
                        if msg.countHFs('contact') > 0:
                            rTarget = msg.getHFBody('contact').getUrl().getCopy()
                        else:
                            rTarget = None
                        routes = [x.getCopy() for x in msg.getHFBodys('record-route')]
                        routes.reverse()
                        if len(routes) > 0:
                            if not routes[0].getUrl().lr:
                                if rTarget != None:
                                    routes.append(SipRoute(address = SipAddress(url = rTarget)))
                                rTarget = routes.pop(0).getUrl()
                                rAddr = rTarget.getTAddr()
                            else:
                                rAddr = routes[0].getTAddr()
                        elif rTarget != None:
                            rAddr = rTarget.getTAddr()
                        if rTarget != None:
                            t.ack.setRURI(rTarget)
                        if rAddr != None:
                            t.ack.setTarget(rAddr)
                        t.ack.delHFs('route')
                        t.ack.appendHeaders([SipHeader(name = 'route', body = x) for x in routes])
                    if fcode >= 200 and fcode < 300:
                        t.ack.getHFBody('via').genBranch()
                    if rAddr == None:
                        rAddr = (t.address, t.userv.transport)
                    if not t.uack:
                        self.transmitMsg(t.userv, t.ack, rAddr[0], checksum, t.compact)
                        if t.req_out_cb != None:
                            t.req_out_cb(t.ack)
                    else:
                        t.state = UACK
                        t.ack_rAddr = rAddr
                        t.ack_checksum = checksum
                        self.l1rcache[checksum] = SipTMRetransmitO()
                        t.teG = Timeout(self.timerG, 64, 1, t)
                else:
                    self.l1rcache[checksum] = SipTMRetransmitO()
                if t.resp_cb != None:
                    if t.cb_ifver == 1:
                        t.resp_cb(msg)
                    else:
                        t.resp_cb(msg, t)
                if t.state == UACK:
                    return
                del self.tclient[t.tid]
                t.cleanup()

    def timerA(self, t):
        #print('timerA', t)
        self.transmitData(t.userv, t.data, t.address)
        t.tout *= 2
        t.teA = Timeout(self.timerA, t.tout, 1, t)

    def timerB(self, t):
        #print('timerB', t)
        t.teB = None
        if t.teA != None:
            t.teA.cancel()
            t.teA = None
        t.state = TERMINATED
        #print('2: Timeout(self.timerC, 32.0, 1, t)', t)
        t.teC = Timeout(self.timerC, 32.0, 1, t)
        if t.resp_cb == None:
            return
        t.r408.rtime = MonoTime()
        if t.cb_ifver == 1:
            t.resp_cb(t.r408)
        else:
            t.resp_cb(t.r408, t)
        #try:
        #    t.resp_cb(SipRequest(t.data).genResponse(408, 'Request Timeout'))
        #except:
        #    print('SipTransactionManager: unhandled exception when processing response!')

    def timerC(self, t):
        #print('timerC', t)
        #print(self.tclient)
        t.teC = None
        del self.tclient[t.tid]
        t.cleanup()

    # 2. Server transaction methods
    def incomingRequest(self, msg, checksum, tids, server):
        for tid in tids:
            if tid in self.tclient:
                t = self.tclient[tid]
                resp = msg.genResponse(482, 'Loop Detected')
                self.transmitMsg(server, resp, resp.getHFBody('via').getTAddr(), checksum, \
                  t.compact)
                return
        if  msg.getMethod() != 'ACK':
            tid = msg.getTId(wBRN = True)
        else:
            tid = msg.getTId(wTTG = True)
        t = self.tserver.get(tid, None)
        if t != None:
            #print('existing transaction')
            if msg.getMethod() == t.method:
                # Duplicate received, check that we have sent any response on this
                # request already
                if t.data != None:
                    self.transmitData(t.userv, t.data, t.address, checksum)
                return
            elif msg.getMethod() == 'CANCEL':
                # RFC3261 says that we have to reply 200 OK in all cases if
                # there is such transaction
                resp = msg.genResponse(200, 'OK')
                self.transmitMsg(t.userv, resp, resp.getHFBody('via').getTAddr(), checksum, \
                  t.compact)
                if t.state in (TRYING, RINGING):
                    self.doCancel(t, msg.rtime, msg)
            elif msg.getMethod() == 'ACK' and t.state == COMPLETED:
                t.state = CONFIRMED
                if t.teA != None:
                    t.teA.cancel()
                    t.teA = None
                t.teD.cancel()
                # We have done with the transaction, no need to wait for timeout
                del self.tserver[t.tid]
                if t.ack_cb != None:
                    t.ack_cb(msg)
                t.cleanup()
                self.l1rcache[checksum] = SipTMRetransmitO()
        elif msg.getMethod() == 'ACK':
            # Some ACK that doesn't match any existing transaction.
            # Drop and forget it - upper layer is unlikely to be interested
            # to seeing this anyway.
            #print(datetime.now(), 'unmatched ACK transaction - ignoring')
            #sys.stdout.flush()
            self.l1rcache[checksum] = SipTMRetransmitO()
        elif msg.getMethod() == 'CANCEL':
            resp = msg.genResponse(481, 'Call Leg/Transaction Does Not Exist')
            self.transmitMsg(server, resp, resp.getHFBody('via').getTAddr(), checksum)
        else:
            #print('new transaction', msg.getMethod())
            t = SipTransaction()
            t.tid = tid
            t.state = TRYING
            t.teA = None
            t.teD = None
            t.teE = None
            t.teF = None
            t.teG = None
            t.method = msg.getMethod()
            t.rtime = msg.rtime
            t.data = None
            t.address = None
            t.noack_cb = None
            t.ack_cb = None
            t.cancel_cb = None
            t.checksum = checksum
            if not server.uopts.isWildCard():
                t.userv = server
            else:
                # For messages received on the wildcard interface find
                # or create more specific server.
                t.userv = self.l4r.getServer(msg.getSource())
            if msg.getMethod() == 'INVITE':
                t.r487 = msg.genResponse(487, 'Request Terminated')
                t.needack = True
                t.branch = msg.getHFBody('via').getBranch()
                try:
                    e = msg.getHFBody('expires').getNum()
                    if e <= 0:
                        e = 300
                except IndexError:
                    e = 300
                t.teE = Timeout(self.timerE, e, 1, t)
            else:
                t.r487 = None
                t.needack = False
                t.branch = None
            self.tserver[t.tid] = t
            for consumer in self.req_consumers.get(t.tid[0], ()):
                cobj = consumer.cobj.isYours(msg)
                if cobj != None:
                    t.compact = consumer.compact
                    rval = cobj.recvRequest(msg, t)
                    break
            else:
                if self.req_cb == None:
                    self.l1rcache[checksum] = SipTMRetransmitO()
                    return
                rval = self.req_cb(msg, t)
            if rval == None:
                if t.teA != None or t.teD != None or t.teE != None or t.teF != None:
                    return
                if t.tid in self.tserver:
                    del self.tserver[t.tid]
                t.cleanup()
                return
            resp, t.cancel_cb, t.noack_cb = rval
            if resp != None:
                self.sendResponse(resp, t, lossemul = resp.lossemul)

    def regConsumer(self, consumer, call_id, compact = False):
        cons = SipTransactionConsumer(consumer, compact)
        self.req_consumers.setdefault(call_id, []).append(cons)

    def unregConsumer(self, consumer, call_id):
        # Usually there will be only one consumer per call_id, so that
        # optimize management for this case
        consumers = self.req_consumers.pop(call_id)
        for cons in consumers:
            if cons.cobj != consumer:
                continue
            consumers.remove(cons)
            cons.cleanup()
            if len(consumers) > 0:
                self.req_consumers[call_id] = consumers
            break
        else:
            self.req_consumers[call_id] = consumers
            raise IndexError('unregConsumer: consumer %s for call-id %s is not registered' % \
              (str(consumer), call_id))

    def sendResponse(self, resp, t = None, retrans = False, ack_cb = None,
      lossemul = 0):
        #print(self.tserver)
        if t == None:
            tid = resp.getTId(wBRN = True)
            t = self.tserver[tid]
        if t.state not in (TRYING, RINGING) and not retrans:
            raise ValueError('BUG: attempt to send reply on already finished transaction!!!')
        scode = resp.getSCode()[0]
        toHF = resp.getHFBody('to')
        if scode > 100 and toHF.getTag() == None:
            toHF.genTag()
        t.data = resp.localStr(t.userv.getSIPaddr(), compact = t.compact)
        t.address = resp.getHFBody('via').getTAddr()
        self.transmitData(t.userv, t.data, t.address, t.checksum, lossemul)
        if t.res_out_cb != None:
            t.res_out_cb(resp)
        if scode < 200:
            t.state = RINGING
            if self.provisional_retr > 0 and scode > 100:
                if t.teF != None:
                    t.teF.cancel()
                t.teF = Timeout(self.timerF, self.provisional_retr, 1, t)
        else:
            t.state = COMPLETED
            if t.teE != None:
                t.teE.cancel()
                t.teE = None
            if t.teF != None:
                t.teF.cancel()
                t.teF = None
            if t.needack:
                # Schedule removal of the transaction
                t.ack_cb = ack_cb
                t.teD = Timeout(self.timerD, 32.0, 1, t)
                if scode >= 200:
                    # Black magick to allow proxy send us another INVITE
                    # same branch and From tag. Use To tag to match
                    # ACK transaction after this point. Branch tag in ACK
                    # could differ as well.
                    del self.tserver[t.tid]
                    t.tid = list(t.tid[:-1])
                    t.tid.append(resp.getHFBody('to').getTag())
                    t.tid = tuple(t.tid)
                    self.tserver[t.tid] = t
                # Install retransmit timer if necessary
                t.tout = 0.5
                t.teA = Timeout(self.timerA, t.tout, 1, t)
            else:
                # We have done with the transaction
                del self.tserver[t.tid]
                t.cleanup()

    def doCancel(self, t, rtime = None, req = None):
        if rtime == None:
            rtime = MonoTime()
        if t.r487 != None:
            self.sendResponse(t.r487, t, True)
        if t.cancel_cb != None:
            t.cancel_cb(rtime, req)

    def timerD(self, t):
        #print('timerD')
        t.teD = None
        if t.teA != None:
            t.teA.cancel()
            t.teA = None
        if t.noack_cb != None and t.state != CONFIRMED:
            t.noack_cb()
        del self.tserver[t.tid]
        t.cleanup()

    def timerE(self, t):
        #print('timerE')
        t.teE = None
        if t.teF != None:
            t.teF.cancel()
            t.teF = None
        if t.state in (TRYING, RINGING):
            if t.r487 != None:
                t.r487.reason = 'Request Expired'
            self.doCancel(t)

    # Timer to retransmit the last provisional reply every
    # 2 seconds
    def timerF(self, t):
        #print('timerF', t.state)
        t.teF = None
        if t.state == RINGING and self.provisional_retr > 0:
            self.transmitData(t.userv, t.data, t.address)
            t.teF = Timeout(self.timerF, self.provisional_retr, 1, t)

    def timerG(self, t):
        #print('timerG', t.state)
        t.teG = None
        if t.state == UACK:
            print(datetime.now(), 'INVITE transaction stuck in the UACK state, possible UAC bug')

    def rCachePurge(self):
        self.l2rcache = self.l1rcache
        self.l1rcache = {}
        self.l4r.rotateCache()

    def transmitMsg(self, userv, msg, address, cachesum, compact = False):
        data = msg.localStr(userv.getSIPaddr(), compact = compact)
        self.transmitData(userv, data, address, cachesum)

    def transmitData(self, userv, data, address, cachesum = None, \
      lossemul = 0):
        if lossemul == 0:
            userv.send_to(data, address)
            logop = 'SENDING'
        else:
            logop = 'DISCARDING'
        paddr = userv.addr2str(address)
        msg = f'{logop} message to {paddr}:\n'
        self.global_config['_sip_logger'].write(msg, data)
        if cachesum != None:
            if lossemul > 0:
                lossemul -= 1
            self.l1rcache[cachesum] = SipTMRetransmitO(userv, data, address, \
              None, lossemul)

    def sendACK(self, t):
        #print('sendACK', t.state)
        if t.teG != None:
            t.teG.cancel()
            t.teG = None
        self.transmitMsg(t.userv, t.ack, t.ack_rAddr[0], t.ack_checksum, t.compact)
        if t.req_out_cb != None:
            t.req_out_cb(t.ack)
        del self.tclient[t.tid]
        t.cleanup()

    def shutdown(self):
        self.cp_timer.cancel()
        self.l4r.shutdown()
        self.l1rcache = self.l2rcache = self.req_cb = self.req_consumers = None
        self.global_config = self.cp_timer = self.tclient = self.tserver = None
