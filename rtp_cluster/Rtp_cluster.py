# Copyright (c) 2009-2011 Sippy Software, Inc. All rights reserved.
#
# Copyright (c) 2009-2014 Sippy Software, Inc. All rights reserved.
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

from twisted.internet import reactor

import sys
sys.path.append('..')

from sippy.Cli_server_local import Cli_server_local
from sippy.Udp_server import Udp_server
from sippy.Rtp_proxy_cmd import Rtp_proxy_cmd

from random import random

def is_dst_local(destination_ip):
    #if destination_ip == '192.168.22.11':
    #    return True
    return False

class Broadcaster(object):
    bcount = None
    results = None
    clim = None
    cmd = None

    def __init__(self, bcount, clim, cmd):
        self.results = []
        self.bcount = bcount
        self.clim = clim
        self.cmd = cmd

class UdpCLIM(object):
    cookie = None
    address = None

    def __init__(self, address, cookie, server):
        self.cookie = cookie
        self.address = tuple(address)
        self.server = server

    def send(self, data):
        self.server.send_to('%s %s' % (self.cookie, data), self.address)

    def close(self):
        self.server = None

class Rtp_cluster(object):
    global_config = None
    address = None
    name = None
    active = None
    pending = None
    ccm = None
    commands_inflight = None

    def __init__(self, global_config, name, address = '/var/run/rtpproxy.sock'):
        self.active = []
        self.pending = []
        if len(address) == 2:
            self.ccm = Udp_server(global_config, address, self.up_command_udp)
        else:
            self.ccm = Cli_server_local(self.up_command, address, (80, 80))
            self.ccm.protocol.expect_lf = False
        self.global_config = global_config
        self.name = name
        self.address = address
        self.commands_inflight = []

    def add_member(self, member):
        member.on_state_change = self.rtpp_status_change
        if member.online:
            self.active.append(member)
        else:
            self.pending.append(member)

    def up_command_udp(self, data, address, server):
        dataparts = data.split(None, 1)
        if len(dataparts) == 1:
            return
        cookie, cmd = dataparts
        if cookie in self.commands_inflight:
            return
        self.commands_inflight.append(cookie)
        clim = UdpCLIM(address, cookie, server)
        return self.up_command(clim, cmd)

    def up_command(self, clim, orig_cmd):
        #print 'up_command', orig_cmd
        cmd = Rtp_proxy_cmd(orig_cmd)
        #print cmd
        if len(self.active) == 0:
            self.down_command('E999', clim, cmd, None)
            return
        if cmd.type in ('U', 'L', 'D', 'P', 'S', 'R', 'C', 'Q'):
            #print 'up', cmd.call_id, str(cmd)
            for rtpp in self.active:
                if rtpp.isYours(cmd.call_id):
                    if cmd.type == 'D':
                        rtpp.unbind_session(cmd.call_id)
                    break
            else:
                rtpp = None
            if rtpp == None and cmd.type == 'U' and len(cmd.args.split()) == 3:
                # New session
                rtpp = self.pick_proxy(cmd.call_id)
                rtpp.bind_session(cmd.call_id, cmd.type)
            elif rtpp == None:
                # Existing session we know nothing about
                if cmd.type == 'U':
                    # Do a forced lookup
                    orig_cmd = 'L%s %s' % (cmd.ul_opts, cmd.call_id)
                    u_args = cmd.args.split(None, 4)
                    from_tag = u_args[2]
                    u_args[2] = u_args[3]
                    u_args[3] = from_tag
                    if len(u_args) == 4:
                        orig_cmd += '%s %s %s %s' % tuple(u_args)
                    else:
                        orig_cmd += '%s %s %s %s %s' % tuple(u_args)
                active = [x for x in self.active if x.online]
                br = Broadcaster(len(active), clim, cmd)
                for rtpp in active:
                    if cmd.type in ('U', 'L') and rtpp.lan_address != None:
                        out_cmd = Rtp_proxy_cmd(orig_cmd)
                        out_cmd.ul_opts.local_ip = rtpp.lan_address
                        out_cmd = str(out_cmd)
                    else:
                        out_cmd = orig_cmd
                    rtpp.send_command(out_cmd, self.merge_results, br, rtpp)
                return
        elif cmd.type == 'I' and cmd.command_opts == 'b':
            active = [x for x in self.active if x.online]
            sessions_created = active_sessions = active_streams = preceived = ptransmitted = 0
            for rtpp in active:
                if rtpp.active_sessions == None:
                    # There might be some time between "online" and heartbeat reply,
                    # when stats are still empty, or when proxy goes from offline
                    # to online, skip it
                    continue
                sessions_created += rtpp.sessions_created
                active_sessions += rtpp.active_sessions
                active_streams += rtpp.active_streams
                preceived += rtpp.preceived
                ptransmitted += rtpp.ptransmitted
            reply = 'sessions created: %d\nactive sessions: %d\nactive streams: %d\npackets received: %d\npackets transmitted: %d' % \
              (sessions_created, active_sessions, active_streams, preceived, ptransmitted)
            self.down_command(reply, clim, cmd, None)
            return
        else:
            rtpp = self.active[0]
            #print 'up', cmd
        #print 'rtpp.send_command'
        if cmd.type in ('U', 'L') and rtpp.lan_address != None:
            out_cmd = Rtp_proxy_cmd(orig_cmd)
            out_cmd.ul_opts.local_ip = rtpp.lan_address
            out_cmd = str(out_cmd)
        else:
            out_cmd = orig_cmd
        rtpp.send_command(out_cmd, self.down_command, clim, cmd, rtpp)

    def down_command(self, result, clim, cmd, rtpp):
        if isinstance(clim, UdpCLIM) and clim.cookie in self.commands_inflight:
            self.commands_inflight.remove(clim.cookie)
        #print 'down', result
        if result == None:
            result = 'E999'
        elif cmd.type in ('U', 'L') and not result[0].upper() == 'E' and \
          rtpp.wan_address != None:
            #print 'down', cmd.ul_opts.destination_ip, rtpp.wan_address
            req_dip = cmd.ul_opts.destination_ip
            req_lip = cmd.ul_opts.local_ip
            if req_dip != None and not is_dst_local(req_dip) and \
              req_lip != rtpp.lan_address:
                result_parts = result.strip().split()
                result = '%s %s' % (result_parts[0], rtpp.wan_address)
            elif req_lip == None:
                result_parts = result.strip().split()
                result = '%s %s' % (result_parts[0], rtpp.wan_address)
        #    result = '%s %s' % (result_parts[0], '192.168.1.22')
        #print 'down clim.send', result
        clim.send(result + '\n')
        clim.close()

    def merge_results(self, result, br, rtpp):
        if result == None:
            result = 'E999'
        if br != None and not result[0].upper() == 'E' and not \
          (br.cmd.type in ('U', 'L') and result == '0'):
            br.results.append(result)
        br.bcount -= 1
        if br.bcount > 0:
            # More results to come
            return
        if len(br.results) == 1:
            rtpp.bind_session(br.cmd.call_id, br.cmd.type)
            self.down_command(br.results[0], br.clim, br.cmd, rtpp)
        else:
            # No results or more than one proxy returns positive
            # XXX: more than one result can probably be handled
            if br.cmd.type in ('U', 'L'):
                self.down_command('0', br.clim, br.cmd, rtpp)
            else:
                self.down_command('E999', br.clim, br.cmd, rtpp)

    def pick_proxy(self, call_id):
        active = [(rtpp, rtpp.weight * (1 - rtpp.get_caputil())) \
          for rtpp in self.active if rtpp.status == 'ACTIVE' and rtpp.online]
        available = [(rtpp, weight) for rtpp, weight in active if weight > 0]
        if len(available) > 0:
            # Normal case, there are some proxies that are loaded below their capacities
            total_weight = sum([x[1] for x in available])
            thr_weight = (random() * total_weight) % total_weight
            #print total_weight, thr_weight
            for rtpp, weight in available:
                thr_weight -= weight
                if thr_weight < 0:
                    break
            #print 'pick_proxyNG: picked up %s for the call %s (normal)' % (rtpp.name, call_id)
            return rtpp
        elif len(active) > 0:
            max_rtpp, max_weight = active[0] 
            for rtpp, weight in active[1:]:
                if weight > max_weight:
                    max_rtpp, max_weight = rtpp, weight
            #print 'pick_proxyNG: picked up %s for the call %s (overload)' % (max_rtpp.name, call_id)
            return max_rtpp
        print 'pick_proxyNG: OUCH, no proxies to pickup from for the call %s' % (call_id,)
        return None

    def rtpp_status_change(self, rtpp, online):
        #print 'rtpp_status_change', self, rtpp, online
        if online and rtpp in self.pending:
            self.pending.remove(rtpp)
            self.active.append(rtpp)
        if not online and rtpp in self.active:
            self.active.remove(rtpp)
            self.pending.append(rtpp)

    def bring_down(self, rtpp):
        if rtpp in self.active:
            if rtpp.active_sessions in (0, None):
                self.active.remove(rtpp)
                return
            rtpp.status = 'DRAINING'
            rtpp.on_active_update = self.rtpp_active_change
            return
        self.pending.remove(rtpp)

    def rtpp_active_change(self, rtpp, active_sessions):
        if rtpp.status == 'DRAINING' and active_sessions == 0:
            if rtpp in self.pending:
                self.pending.remove(rtpp)
            else:
                self.active.remove(rtpp)
            rtpp.shutdown = True

    def rtpp_by_name(self, name):
        idx = 0
        for rtpp in self.active + self.pending:
            if rtpp.name == name:
                return (rtpp, idx)
            idx += 1
        return (None, None)

    def shutdown(self):
        for rtpp in self.active + self.pending:
            rtpp.shutdown = True
        self.ccm.shutdown()
        self.active = None
        self.pending = None
        self.ccm = None

    def all_members(self):
        return tuple(self.active + self.pending)

if __name__ == '__main__':
    global_config = {}
    rtp_cluster = Rtp_cluster(global_config, 'supercluster')
    reactor.run(installSignalHandlers = True)
