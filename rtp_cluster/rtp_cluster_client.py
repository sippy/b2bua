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
