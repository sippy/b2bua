#!/usr/local/bin/python
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

from Rtp_cluster_config import read_cluster_config
from Rtp_cluster import Rtp_cluster
from Rtp_cluster_member import Rtp_cluster_member

import getopt, os
import sys
import signal
from pwd import getpwnam
from grp import getgrnam

from contrib.objgraph import typestats
import operator

from twisted.internet import reactor

sys.path.append('sippy')

from sippy.SipConf import MyAddress
from sippy.Cli_server_local import Cli_server_local
from sippy.SipLogger import SipLogger
from sippy.misc import daemonize

class ClusterCLI(object):
    ccm = None
    rtp_clusters = None
    global_config = None

    def __init__(self, global_config, address):
        sown = global_config.get('_rtpc_sockowner', None)
        self.ccm = Cli_server_local(self.receive_command, address, sown)
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
                    clim.send(    '        address = %s\n' % str(rtpp.address))
                    if rtpp.wan_address != None:
                        clim.send('        wan_address = %s\n' % rtpp.wan_address)
                    if rtpp.lan_address != None:
                        clim.send('        lan_address = %s\n' % rtpp.lan_address)
                    if rtpp.cmd_out_address != None:
                        clim.send('        cmd_out_address = %s\n' % rtpp.cmd_out_address)
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
                        clim.send('        capacity utilization = %f%%\n' % (rtpp.get_caputil() * 100.0))
                        clim.send('        average rtpc delay = %f sec\n' % rtpp.get_rtpc_delay())
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
                    clim.send(    '        address = %s\n' % str(rtpp.address))
                    if rtpp.wan_address != None:
                        clim.send('        wan_address = %s\n' % rtpp.wan_address)
                    if rtpp.lan_address != None:
                        clim.send('        lan_address = %s\n' % rtpp.lan_address)
                    if rtpp.cmd_out_address != None:
                        clim.send('        cmd_out_address = %s\n' % rtpp.cmd_out_address)
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
                    address = tuple(address)
                else:
                    address = rtpp_config['address']
                if rtpp_config.has_key('cmd_out_address'):
                    bind_address = rtpp_config['cmd_out_address']
                else:
                    bind_address = None
                rtpp = Rtp_cluster_member(rtpp_config['name'], global_config, address, bind_address)
                if rtpp_config.has_key('wan_address'):
                    rtpp.wan_address = rtpp_config['wan_address']
                if rtpp_config.has_key('lan_address'):
                    rtpp.lan_address = rtpp_config['lan_address']
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
            config = read_cluster_config(self.global_config, f.read())
            new_rtp_clusters = []
            new_rtpps_count = 0
            for c in config:
                rtp_cluster, idx = self.cluster_by_name(c['name'])
                if rtp_cluster == None:
                    rtp_cluster = Rtp_cluster(global_config, c['name'], c['address'], \
                      dnconfig = c.get('dnconfig', None))
                else:
                    rtp_cluster.update_dnrelay(c.get('dnconfig', None))
                rtp_cluster.capacity_limit_soft = c.get('capacity_limit_soft', True)
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
                        address = tuple(address)
                    else:
                        address = rtpp_config['address']
                    rtpp, idx = rtp_cluster.rtpp_by_name(rtpp_config['name'])
                    if rtpp == None:
                        if rtpp_config.has_key('cmd_out_address'):
                            bind_address = rtpp_config['cmd_out_address']
                        else:
                            bind_address = None
                        rtpp = Rtp_cluster_member(rtpp_config['name'], global_config, address, bind_address)
                        rtpp.weight = rtpp_config['weight']
                        rtpp.capacity = rtpp_config['capacity']
                        if rtpp_config.has_key('wan_address'):
                            rtpp.wan_address = rtpp_config['wan_address']
                        if rtpp_config.has_key('lan_address'):
                            rtpp.lan_address = rtpp_config['lan_address']
                        rtp_cluster.add_member(rtpp)
                    else:
                        if rtpp_config.has_key('cmd_out_address'):
                            rtpp.cmd_out_address = rtpp_config['cmd_out_address']
                        else:
                            rtpp.cmd_out_address = None
                        rtpp.reconnect(address)
                        rtpp.weight = rtpp_config['weight']
                        rtpp.capacity = rtpp_config['capacity']
                        if rtpp_config.has_key('wan_address'):
                            rtpp.wan_address = rtpp_config['wan_address']
                        else:
                            rtpp.wan_address = None
                        if rtpp_config.has_key('lan_address'):
                            rtpp.lan_address = rtpp_config['lan_address']
                        else:
                            rtpp.lan_address = None
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
        if cmd.startswith('objstats'):
            parts = cmd.split(None, 2)
            if len(parts) > 1:
                limit = int(parts[1])
            else:
                limit = 20
            stats = sorted(typestats().items(), key=operator.itemgetter(1),
              reverse=True)
            stats = stats[:limit]
            width = max(len(name) for name, count in stats)
            for name, count in stats[:limit]:
                clim.send('\t%s %d\n' % (name.ljust(width), count))
            return False
        clim.send('ERROR: unknown command\n')
        return False

class fakecli(object):
    rtp_clusters = None

    def __init__(self):
        self.rtp_clusters = []

def usage():
    print('usage: rtp_cluster.py [-fd] [-P pidfile] [-c conffile] [-L logfile] [-s cmd_socket]\n' \
          '        [-o uname:gname]')
    sys.exit(1)

def debug_signal(signum, frame):
    import sys, traceback
    for thread_id, stack in sys._current_frames().iteritems():
        print 'Thread id: %s\n%s' % (thread_id, ''.join(traceback.format_stack(stack)))

if __name__ == '__main__':
    global_config = {}

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'fP:c:L:s:o:dD')
    except getopt.GetoptError:
        usage()

    sip_logger = SipLogger('rtp_cluster')

    sip_logger.write('Starting up...')

    foreground = False
    dry_run = False
    debug_threads = False
    pidfile = '/var/run/rtp_cluster.pid'
    logfile = '/var/log/rtp_cluster.log'
    csockfile = '/var/run/rtp_cluster.sock'
    global_config['conffile'] = '/usr/local/etc/rtp_cluster.xml'
    global_config['_sip_address'] = MyAddress()
    for o, a in opts:
        if o == '-f':
            foreground = True
            continue
        if o == '-P':
            pidfile = a.strip()
            continue
        if o == '-c':
            global_config['conffile'] = a.strip()
            continue
        if o == '-L':
            logfile = a.strip()
            continue
        if o == '-s':
            csockfile = a.strip()
            continue
        if o == '-o':
            sown_user, sown_gpr = a.split(':', 1)
            sown_uid = getpwnam(sown_user).pw_uid
            sown_gid = getgrnam(sown_gpr).gr_gid
            global_config['_rtpc_sockowner'] = (sown_uid, sown_gid)
            continue
        if o == '-d':
            dry_run = True
            foreground = True
            continue
        if o == '-D':
            debug_threads = True
            continue

    sip_logger.write(' o reading config "%s"...' % \
      global_config['conffile'])

    global_config['_sip_logger'] = sip_logger
    f = open(global_config['conffile'])
    config = read_cluster_config(global_config, f.read())

    if not foreground:
        # Shut down the logger and reopen it again to make sure it's worker
        # thread won't be affected by the fork()
        sip_logger.shutdown()
        daemonize(logfile = logfile)
        file(pidfile, 'w').write(str(os.getpid()) + '\n')
        sip_logger = SipLogger('rtp_cluster')
        global_config['_sip_logger'] = sip_logger

    sip_logger.write(' o initializing CLI...')

    if not dry_run:
        cli = ClusterCLI(global_config, address = csockfile)
    else:
        cli = fakecli()

    for c in config:
        #print 'Rtp_cluster', global_config, c['name'], c['address']
        sip_logger.write(' o initializing cluster "%s" at <%s>' % (c['name'], c['address']))
        rtp_cluster = Rtp_cluster(global_config, c['name'], c['address'], \
          dnconfig = c.get('dnconfig', None), dry_run = dry_run)
        rtp_cluster.capacity_limit_soft = c.get('capacity_limit_soft', True)
        for rtpp_config in c['rtpproxies']:
            sip_logger.write('  - adding RTPproxy member %s at <%s>' % (rtpp_config['name'], rtpp_config['address']))
            #Rtp_cluster_member('rtpproxy1', global_config, ('127.0.0.1', 22222))
            if rtpp_config['protocol'] not in ('unix', 'udp'):
                raise Exception('Unsupported RTPproxy protocol: "%s"' % rtpp_config['protocol'])
            if rtpp_config['protocol'] == 'udp':
                address = rtpp_config['address'].split(':', 1)
                if len(address) == 1:
                    address.append(22222)
                else:
                    address[1] = int(address[1])
                address = tuple(address)
            else:
                address = rtpp_config['address']
            if rtpp_config.has_key('cmd_out_address'):
                bind_address = rtpp_config['cmd_out_address']
            else:
                bind_address = None
            rtpp = Rtp_cluster_member(rtpp_config['name'], global_config, address, bind_address)
            rtpp.weight = rtpp_config['weight']
            rtpp.capacity = rtpp_config['capacity']
            if rtpp_config.has_key('wan_address'):
                rtpp.wan_address = rtpp_config['wan_address']
            if rtpp_config.has_key('lan_address'):
                rtpp.lan_address = rtpp_config['lan_address']
            rtp_cluster.add_member(rtpp)
        cli.rtp_clusters.append(rtp_cluster)
    #rtp_cluster = Rtp_cluster(global_config, 'supercluster', dry_run = dry_run)
    if dry_run:
        sip_logger.write('Configuration check is complete, no errors found')
        for rtp_cluster in cli.rtp_clusters:
            rtp_cluster.shutdown()
        sip_logger.shutdown()
        from time import sleep
        # Give worker threads some time to cease&desist
        sleep(0.1)
        sys.exit(0)
    if debug_threads:
        signal.signal(signal.SIGINFO, debug_signal)
    sip_logger.write('Initialization complete, have a good flight.')
    reactor.run(installSignalHandlers = True)
