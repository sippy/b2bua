#!/usr/local/bin/python
#
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

from Rtp_cluster_config import read_cluster_config
from Rtp_cluster import Rtp_cluster
from Rtp_cluster_member import Rtp_cluster_member

import getopt, os
import sys

from twisted.internet import reactor

sys.path.append('sippy')

from sippy.SipConf import MyAddress
from sippy.Cli_server_local import Cli_server_local

class ClusterCLI(object):
    ccm = None
    rtp_clusters = None
    global_config = None

    def __init__(self, global_config, address = '/var/run/rtp_cluster.sock'):
        self.ccm = Cli_server_local(self.receive_command, address, (80, 80))
        self.rtp_clusters = []
        self.global_config = global_config

    def cluster_by_name(self, name):
        idx = 0
        for rtp_cluster in self.rtp_clusters:
            if rtp_cluster.name == name:
                return (rtp_cluster, idx)
            idx += 1
        return (None, None)

    def receive_command(self, clim, cmd):
        if cmd.startswith('ls'):
            parts = cmd.split(None, 1)
            if len(parts) == 1:
                idx = 0
                for rtp_cluster in self.rtp_clusters:
                    if idx > 0:
                        clim.send('\n')                
                    clim.send('Cluster: #%d\n' % idx)
                    clim.send('    name = %s\n' % rtp_cluster.name)
                    clim.send('    address = %s\n' % str(rtp_cluster.address))
                    clim.send('    active members = %d\n' % len(rtp_cluster.active))
                    clim.send('    inactive members = %d\n' % len(rtp_cluster.pending))
                    idx += 1
            else:
                rtp_cluster, idx = self.cluster_by_name(parts[1])
                if rtp_cluster == None:
                    clim.send('ERROR: %s: cluster not found\n' % parts[1])
                    return False
                clim.send('Active members of the cluster #%d:\n' % idx)
                ridx = 0
                for rtpp in rtp_cluster.active:
                    if ridx > 0:
                        clim.send('\n')
                    clim.send(    '    RTPproxy: #%d\n' % ridx)
                    clim.send(    '        name = %s\n' % rtpp.name)
                    clim.send(    '        address = %s\n' % rtpp.address)
                    if rtpp.wan_address != None:
                        clim.send('        wan_address = %s\n' % rtpp.wan_address)
                    clim.send(    '        weight = %d\n' % rtpp.weight)
                    clim.send(    '        capacity = %d\n' % rtpp.capacity)
                    clim.send(    '        state = ')
                    if rtpp.online:
                        clim.send('online\n')
                        clim.send('        active sessions = ')
                        if rtpp.active_sessions == None:
                            clim.send('UNKNOWN\n')
                        else:
                            clim.send('%d\n' % rtpp.active_sessions)
                    else:
                        clim.send('offline\n')
                    clim.send('        status = %s\n' % rtpp.status)
                    ridx += 1
                clim.send('\nInactive members of the cluster #%d:\n' % idx)
                ridx = 0
                for rtpp in rtp_cluster.pending:
                    if ridx > 0:
                        clim.send('\n')
                    clim.send(    '    RTPproxy: #%d\n' % ridx)
                    clim.send(    '        name = %s\n' % rtpp.name)
                    clim.send(    '        address = %s\n' % rtpp.address)
                    if rtpp.wan_address != None:
                        clim.send('        wan_address = %s\n' % rtpp.wan_address)
                    clim.send(    '        weight = %d\n' % rtpp.weight)
                    clim.send(    '        capacity = %d\n' % rtpp.capacity)
                    clim.send(    '        state = ')
                    if rtpp.online:
                        clim.send('online\n')
                    else:
                        clim.send('offline\n')
                    ridx += 1
                if ridx == 0:
                    clim.send('\n')
            clim.send('OK\n')
            return False
        if cmd.startswith('modify'):
            parts = cmd.split(None, 4)
            rtp_cluster, idx = self.cluster_by_name(parts[1])
            if rtp_cluster == None:
                clim.send('ERROR: %s: cluster not found\n' % parts[1])
                return False
            if parts[2] == 'add':
                kvs = parts[3].split(',')
                rtpp_config = dict([x.split('=') for x in kvs])
                rtpp, idx = rtp_cluster.rtpp_by_name(rtpp_config['name'])
                if rtpp != None:
                    clim.send('ERROR: %s: RTPproxy already exists\n' % rtpp_config['name'])
                    return False
                if rtpp_config['protocol'] not in ('unix', 'udp'):
                    raise Exception('Unsupported RTPproxy protocol: "%s"' % rtpp_config['protocol'])
                if rtpp_config['protocol']  == 'udp':
                    address = rtpp_config['address'].split(':', 1)
                    if len(address) == 1:
                        address.append(22222)
                    else:
                        address[1] = int(address[1])
                else:
                    address = rtpp_config['address']
                rtpp = Rtp_cluster_member(rtpp_config['name'], global_config, address)
                if rtpp_config.has_key('wan_address'):
                    rtpp.wan_address = rtpp_config['wan_address']
                rtpp.weight = int(rtpp_config['weight'])
                rtpp.capacity = int(rtpp_config['capacity'])
                rtp_cluster.add_member(rtpp)
                clim.send('OK\n')
                return False
            if parts[2] in ('remove', 'delete', 'pause', 'resume'):
                rtpp, idx = rtp_cluster.rtpp_by_name(parts[3])
                if rtpp == None:
                    clim.send('ERROR: %s: RTPproxy not found\n' % parts[3])
                    return False
                if parts[2] in ('remove', 'delete'):
                    rtp_cluster.bring_down(rtpp)
                elif parts[2] == 'pause':
                    rtpp.status = 'SUSPENDED'
                elif parts[2] == 'resume':
                    rtpp.status = 'ACTIVE'
                clim.send('OK\n')
                return False
        if cmd in ('h', 'help'):
                clim.send('Supported commands:\n' \
                  '\tls [CLUSTER_NAME]\n' \
                  '\tmodify CLUSTER_NAME [add|remove|delete|pause|resume] ARGS\n' \
                  '\treload\n' \
                  '\tquit\n')
                return False
        if cmd in ('q', 'quit', 'exit'):
            clim.close()
            return False
        if cmd.startswith('reload'):
            f = open(self.global_config['conffile'])
            config = read_cluster_config(f.read())
            new_rtp_clusters = []
            new_rtpps_count = 0
            for c in config:
                rtp_cluster, idx = self.cluster_by_name(c['name'])
                if rtp_cluster == None:
                    rtp_cluster = Rtp_cluster(global_config, c['name'], c['address'])
                new_rtpps = []
                for rtpp_config in c['rtpproxies']:
                    #Rtp_cluster_member('rtpproxy1', global_config, ('127.0.0.1', 22222))
                    if rtpp_config['protocol'] not in ('unix', 'udp'):
                        raise Exception('Unsupported RTPproxy protocol: "%s"' % rtpp_config['protocol'])
                    if rtpp_config['protocol'] == 'udp':
                        address = rtpp_config['address'].split(':', 1)
                        if len(address) == 1:
                            address.append(22222)
                        else:
                            address[1] = int(address[1])
                    else:
                        address = rtpp_config['address']
                    rtpp, idx = rtp_cluster.rtpp_by_name(rtpp_config['name'])
                    if rtpp == None:
                        rtpp = Rtp_cluster_member(rtpp_config['name'], global_config, address)
                        rtpp.weight = rtpp_config['weight']
                        rtpp.capacity = rtpp_config['capacity']
                        if rtpp_config.has_key('wan_address'):
                            rtpp.wan_address = rtpp_config['wan_address']
                        rtp_cluster.add_member(rtpp)
                    else:
                        rtpp.reconnect(address)
                        rtpp.weight = rtpp_config['weight']
                        rtpp.capacity = rtpp_config['capacity']
                        if rtpp_config.has_key('wan_address'):
                            rtpp.wan_address = rtpp_config['wan_address']
                        else:
                            rtpp.wan_address = None
                    new_rtpps.append(rtpp)
                new_rtpps_count += len(new_rtpps)
                for rtpp in [x for x in rtp_cluster.all_members() if x not in new_rtpps]:
                    rtp_cluster.bring_down(rtpp)
                new_rtp_clusters.append(rtp_cluster)
            for rtp_cluster in [x for x in self.rtp_clusters if x not in new_rtp_clusters]:
                rtp_cluster.shutdown()
            self.rtp_clusters = new_rtp_clusters
            clim.send('Loaded %d clusters and %d RTP proxies\n' % (len(self.rtp_clusters), new_rtpps_count))
            clim.send('OK\n')
            return False
        clim.send('ERROR: unknown command\n')
        return False

def usage():
    print 'usage: rtp_cluster.py [-f] [-P pidfile] [-c conffile]'
    sys.exit(1)

if __name__ == '__main__':
    global_config = {}

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'fP:c:')
    except getopt.GetoptError:
        usage()
    foreground = False
    dsn = 'postgres://ser:secr3tpa33w0rD@/tmp/sippy'
    pidfile = '/var/run/rtp_cluster.pid'
    logfile = '/var/log/rtp_cluster.log'
    global_config['conffile'] = '/usr/local/etc/rtp_cluster.xml'
    global_config['_sip_address'] = MyAddress()
    for o, a in opts:
        if o == '-f':
            foreground = True
            continue
        if o == '-P':
            pidfile = a.strip()
            continue
        if o == 'c':
            global_config['conffile'] = a.strip()
            continue

    f = open(global_config['conffile'])
    config = read_cluster_config(f.read())

    if not foreground:
        #print 'foobar'
        # Fork once
        if os.fork() != 0:
            os._exit(0)
        # Create new session
        os.setsid()
        if os.fork() != 0:
            os._exit(0)
        #os.chdir('/')
        fd = os.open('/dev/null', os.O_RDONLY)
        os.dup2(fd, sys.__stdin__.fileno())
        os.close(fd)
        fd = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        os.dup2(fd, sys.__stdout__.fileno())
        os.dup2(fd, sys.__stderr__.fileno())
        os.close(fd)
        file(pidfile, 'w').write(str(os.getpid()) + '\n')

    cli = ClusterCLI(global_config)
    for c in config:
        #print 'Rtp_cluster', global_config, c['name'], c['address']
        rtp_cluster = Rtp_cluster(global_config, c['name'], c['address'])
        for rtpp_config in c['rtpproxies']:
            #Rtp_cluster_member('rtpproxy1', global_config, ('127.0.0.1', 22222))
            if rtpp_config['protocol'] not in ('unix', 'udp'):
                raise Exception('Unsupported RTPproxy protocol: "%s"' % rtpp_config['protocol'])
            if rtpp_config['protocol'] == 'udp':
                address = rtpp_config['address'].split(':', 1)
                if len(address) == 1:
                    address.append(22222)
                else:
                    address[1] = int(address[1])
            else:
                address = rtpp_config['address']
            rtpp = Rtp_cluster_member(rtpp_config['name'], global_config, address)
            rtpp.weight = rtpp_config['weight']
            rtpp.capacity = rtpp_config['capacity']
            if rtpp_config.has_key('wan_address'):
                rtpp.wan_address = rtpp_config['wan_address']
            rtp_cluster.add_member(rtpp)
        cli.rtp_clusters.append(rtp_cluster)
    #rtp_cluster = Rtp_cluster(global_config, 'supercluster')
    reactor.run(installSignalHandlers = True)

