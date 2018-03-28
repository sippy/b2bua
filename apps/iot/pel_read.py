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

from serial import Serial
from time import time, sleep
from getopt import getopt, GetoptError
import os, sys

sys.path.append('../..')

from sippy.misc import daemonize

if __name__ == '__main__':
    try:
        opts, args = getopt(sys.argv[1:], 'fl:p:n:L:')
    except GetoptError:
        print('usage: pel_read.py [-l addr] [-p port] [-n addr] [-f] [-L logfile]')
        sys.exit(1)
    laddr = None
    lport = None
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

    if logfile == '-':
        lfile = sys.stdout
    #daemonize(logfile)
    if logfile == '-':
        lfile = sys.stdout
    else:
        lfile = open(logfile, 'a')
    rfile = None
    default_timeout = 60.0
    session_timeout = default_timeout
    ctime = None
    count = 0
    sdev = '/dev/cuau1'
    brate = 9600
    port = Serial(sdev, baudrate=brate, timeout=0.1)
    while True:
        try:
            data = port.read(256)
        except Exception as e:
            lfile.write('Session exception: %s\n' % str(e))
            lfile.flush()
            if rfile != None:
                #rfile.flush()
                rfile.close()
            rfile = None
            sleep(1)
            port = Serial(sdev, baudrate=brate, timeout=0.1)
            continue
        atime = time()
        if rfile != None and atime - ctime > session_timeout:
            lfile.write('Session timeout: %f\n' % (atime - ctime))
            lfile.flush()
            #rfile.flush()
            rfile.close()
            rfile = None
        if len(data) == 0:
            continue
        previous_ctime = ctime
        ctime = atime

        if rfile == None:
            fname = '/tmp/%s.csv' % int(ctime)
            rfile = open(fname, 'w')
            session_timeout = default_timeout
            previous_ctime = None
            count = 0
            lfile.write('Starting recording %s\n' % fname)
            lfile.flush()
        if previous_ctime != None and session_timeout > (ctime - previous_ctime) * 2 and count > 2:
            session_timeout = (ctime - previous_ctime) * 2
            lfile.write(' Updating session timeout to %f sec\n' % session_timeout)
            lfile.flush()
        parts = [x.strip() for x in data.decode('ascii').split(' ', 3)]
        try:
            volts = float(parts[1][:-1])
            amps = float(parts[2][:-1])
        except:
            count += 1
            continue
        rfile.write('%d,%f,%f\n' % (count, volts, amps))
        #rfile.flush()
        count += 1
