# Copyright (c) 2009-2011 Sippy Software, Inc. All rights reserved.
#
# This file is part of SIPPY, a free RFC3261 SIP stack and B2BUA.
#
# SIPPY is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# For a license to use the SIPPY software under conditions
# other than those described here, or to purchase support for this
# software, please contact Sippy Software, Inc. by e-mail at the
# following addresses: sales@sippysoft.com.
#
# SIPPY is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

from twisted.internet import reactor

import sys
sys.path.append('..')

from sippy.Cli_server_local import Cli_server_local
from sippy.Udp_server import Udp_server
from sippy.Rtp_proxy_cmd import Rtp_proxy_cmd

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
        self.address = address
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

    def __init__(self, global_config, name, address = '/var/run/rtpproxy.sock'):
        self.active = []
        self.pending = []
        if len(address) == 2:
            self.ccm = Udp_server(address, self.up_command_udp)
        else:
            self.ccm = Cli_server_local(self.up_command, address, (80, 80))
            self.ccm.protocol.expect_lf = False
        self.global_config = global_config
        self.name = name
        self.address = address

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
                    rtpp.send_command(orig_cmd, self.merge_results, br, rtpp)
                return
        else:
            rtpp = self.active[0]
            #print 'up', cmd
        #print 'rtpp.send_command'
        rtpp.send_command(orig_cmd, self.down_command, clim, cmd, rtpp)

    def down_command(self, result, clim, cmd, rtpp):
        #print 'down', result
        if result == None:
            result = 'E999'
        elif cmd.type in ('U', 'L') and not result[0].upper() == 'E':
            #print 'down', cmd.ul_opts.destination_ip, rtpp.wan_address
            if cmd.ul_opts.destination_ip != None and rtpp.wan_address != None:
               if not is_dst_local(cmd.ul_opts.destination_ip):
                   result_parts = result.strip().split()
                   result = '%s %s' % (result_parts[0], rtpp.wan_address)
        #    result = '%s %s' % (result_parts[0], '192.168.1.22')
        #print 'down clim.send', result
        clim.send(result + '\n')
        clim.close()

    def merge_results(self, result, br, rtpp):
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
        active = list(self.active)
        call_id_hash = hash(call_id)
        while len(active) > 1:
            total_weight = sum([x.weight for x in active])
            idx = call_id_hash % total_weight
            for rtpp in active:
                idx -= rtpp.weight
                if idx < 0:
                    break
            if rtpp.status == 'ACTIVE' and rtpp.online and rtpp.capacity > rtpp.active_sessions:
                return rtpp
            active.remove(rtpp)
        return active[0]

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
