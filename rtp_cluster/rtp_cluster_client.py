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

import socket, sys, getopt

def cli_client(address, argv, tcp = False):
    if not tcp:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(address)
    command = reduce(lambda x, y: x + ' ' + y, argv)
    s.send(command + '\nquit\n')
    while True:
        data = s.recv(1024)
        if len(data) == 0:
            break
        sys.stdout.write(data)

def usage():
    print 'usage: rtp_cluster_client.py [-s cmdfile]'
    sys.exit(1)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 's:')
    except getopt.GetoptError:
        usage()
    if len(args) == 0:
        usage()
    cmdfile = 'unix:/var/run/rtp_cluster.sock'
    for o, a in opts:
        if o == '-s':
            cmdfile = a.strip()
            continue

    if cmdfile.startswith('tcp:'):
        parts = cmdfile[4:].split(':', 1)
        if len(parts) == 1:
            address = (parts[0], 12345)
        else:
            address = (parts[0], int(parts[1]))
        cli_client(address, args, tcp = True)
    else:
        if cmdfile.startswith('unix:'):
            cmdfile = cmdfile[5:]
        cli_client(cmdfile, args)
