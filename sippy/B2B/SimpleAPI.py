# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2025 Sippy Software, Inc. All rights reserved.
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

from ..CLIManager import CLIConnectionManager, CLIManager
from ..Time.MonoTime import MonoTime
from .States import CCStateConnected, CCStateARComplete

class B2BSimpleAPI(CLIConnectionManager):
    global_config = None

    def __init__(self, global_config):
        cmdfile = global_config['b2bua_socket']
        self.global_config = global_config
        if cmdfile.startswith('tcp:'):
            parts = cmdfile[4:].split(':', 1)
            if len(parts) == 1:
                address = (parts[0], 12345)
            else:
                address = (parts[0], int(parts[1]))
            super().__init__(self.recvCommand, address, tcp = True)
        else:
            if cmdfile.startswith('unix:'):
                cmdfile = cmdfile[5:]
            super().__init__(self.recvCommand, cmdfile)

    def recvCommand(self, clim, cmd):
        ccm = self.global_config['_cmap']
        args = cmd.split()
        cmd = args.pop(0).lower()
        if cmd == 'q':
            clim.close()
            return False
        if cmd == 'l':
            res = 'In-memory calls:\n'
            total = 0
            for (cid, sname), uaast, uaost in ccm.listActiveCalls():
                res += f'{cid}: {sname} ('
                if uaast is not None:
                    _s, _t, _h, _p, _cld, _cli = uaast
                    res += f'{_s} {_t}:{_h}:{_p} {_cld} {_cli} -> '
                else:
                    res += 'N/A -> '
                if uaost is not None:
                    _s, _t, _h, _p, _cld, _cli = uaost
                    res += f'{_s} {_t}:{_h}:{_p} {_cld} {_cli})\n'
                else:
                    res += 'N/A)\n'
                total += 1
            res += 'Total: %d\n' % total
            clim.send(res)
            return False
        if cmd == 'lt':
            res = 'In-memory server transactions:\n'
            for tid, t in self.global_config['_sip_tm'].tserver.iteritems():
                res += '%s %s %s\n' % (tid, t.method, t.state)
            res += 'In-memory client transactions:\n'
            for tid, t in self.global_config['_sip_tm'].tclient.iteritems():
                res += '%s %s %s\n' % (tid, t.method, t.state)
            clim.send(res)
            return False
        if cmd in ('lt', 'llt'):
            if cmd == 'llt':
                mindur = 60.0
            else:
                mindur = 0.0
            ctime = MonoTime()
            res = 'In-memory server transactions:\n'
            for tid, t in self.global_config['_sip_tm'].tserver.iteritems():
                duration = ctime - t.rtime
                if duration < mindur:
                    continue
                res += '%s %s %s %s\n' % (tid, t.method, t.state, duration)
            res += 'In-memory client transactions:\n'
            for tid, t in self.global_config['_sip_tm'].tclient.iteritems():
                duration = ctime - t.rtime
                if duration < mindur:
                    continue
                res += '%s %s %s %s\n' % (tid, t.method, t.state, duration)
            clim.send(res)
            return False
        if cmd == 'd':
            if len(args) != 1:
                clim.send('ERROR: syntax error: d <call-id>\n')
                return False
            if args[0] == '*':
                self.discAll()
                clim.send('OK\n')
                return False
            dlist = [x for x in ccm.ccmap if str(x.cId) == args[0]]
            if len(dlist) == 0:
                clim.send('ERROR: no call with id of %s has been found\n' % args[0])
                return False
            for cc in dlist:
                cc.disconnect()
            clim.send('OK\n')
            return False
        if cmd == 'r':
            if len(args) != 1:
                clim.send('ERROR: syntax error: r [<id>]\n')
                return False
            idx = int(args[0])
            dlist = [x for x in ccm.ccmap if x.id == idx]
            if len(dlist) == 0:
                clim.send('ERROR: no call with id of %d has been found\n' % idx)
                return False
            for cc in dlist:
                if not cc.proxied:
                    continue
                if cc.state == CCStateConnected:
                    cc.disconnect(MonoTime().getOffsetCopy(-60), origin = 'media_timeout')
                    continue
                if cc.state == CCStateARComplete:
                    cc.uaO.disconnect(MonoTime().getOffsetCopy(-60), origin = 'media_timeout')
                    continue
            clim.send('OK\n')
            return False
        clim.send('ERROR: unknown command\n')
        return False

    def set_rtp_io_socket(self, rtpp_nsock, rtpp_nsock_spec):
        CLIManager(rtpp_nsock, self.recvCommand)
