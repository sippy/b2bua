#!/usr/bin/env python3.6
#
# Copyright (c) 2015-2018 Sippy Software, Inc. All rights reserved.
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

from getopt import getopt, GetoptError
import os, sys

from os.path import dirname, abspath
from inspect import getfile, currentframe
currentdir = dirname(abspath(getfile(currentframe())))
_parentdir = dirname(currentdir)
parentdir = dirname(_parentdir)
sys.path.insert(0, parentdir)

#sys.path.append('../..')

from sippy.misc import daemonize
from sippy.Core.EventDispatcher import ED2
from sippy.SipConf import SipConf
from sippy.SipLogger import SipLogger

from PELIO import PELIO
from PELUA import PELUA

if __name__ == '__main__':
    try:
        opts, args = getopt(sys.argv[1:], 'fl:p:n:L:s:u:P:')
    except GetoptError:
        print('usage: pel_read.py [-l addr] [-p port] [-n addr] [-f] [-L logfile] [-s serial] [-u authname [-P authpass]]')
        sys.exit(1)
    laddr = None
    lport = None
    sdev = None
    authname = None
    authpass = None
    logfile = '/var/log/pel_read.log'
    global_config = {'nh_addr':['192.168.0.102', 5060]}
    foreground = False
    for o, a in opts:
        if o == '-f':
            foreground = True
            continue
        if o == '-l':
            laddr = a
            continue
        if o == '-p':
            lport = int(a)
            continue
        if o == '-L':
            logfile = a
        if o == '-n':
            if a.startswith('['):
                parts = a.split(']', 1)
                global_config['nh_addr'] = [parts[0] + ']', 5060]
                parts = parts[1].split(':', 1)
            else:
                parts = a.split(':', 1)
                global_config['nh_addr'] = [parts[0], 5060]
            if len(parts) == 2:
                global_config['nh_addr'][1] = int(parts[1])
            continue
        if o == '-s':
            sdev = a
            continue
        if o == '-u':
            authname = a
            continue
        if o == '-P':
            authpass = a
            continue

    if not foreground:
        daemonize(logfile)
    if logfile == '-':
        lfile = sys.stdout
    else:
        lfile = open(logfile, 'a')

    global_config['_sip_address'] = SipConf.my_address
    global_config['_sip_port'] = SipConf.my_port
    if laddr != None:
        global_config['_sip_address'] = laddr
    if lport != None:
        global_config['_sip_port'] = lport
    global_config['_sip_logger'] = SipLogger('pel_read')

    pua = PELUA(global_config)
    if authname != None:
        pua.authname = authname
        pua.authpass = authpass
    pio = PELIO(lfile)
    if sdev != None:
        pio.sdev = sdev
    pio.sstart_cb = pua.sess_started
    pio.send_cb = pua.sess_ended
    pio.start()
    ED2.loop()
