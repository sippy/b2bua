# Copyright (c) 2018 Sippy Software, Inc. All rights reserved.
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

from __future__ import print_function

from threading import Thread
from serial import Serial
from time import time, sleep

from sippy.Core.EventDispatcher import ED2

class PELIO(Thread):
    default_timeout = 60.0
    sdev = '/dev/cuau0'
    brate = 9600
    lfile = None
    sstart_cb = None
    send_cb = None

    def __init__(self, lfile):
        Thread.__init__(self)
        self.setDaemon(True)
        self.lfile = lfile

    def run(self):
        rfile = None
        session_timeout = self.default_timeout
        ctime = None
        count = 0
        port = Serial(self.sdev, baudrate = self.brate, timeout=0.1)
        while True:
            try:
                data = port.read(256)
            except Exception as e:
                self.lfile.write('Session exception: %s\n' % str(e))
                self.lfile.flush()
                if rfile != None:
                    #rfile.flush()
                    rfile.close()
                rfile = None
                sleep(1)
                port = Serial(self.sdev, baudrate = self.brate, timeout=0.1)
                continue
            atime = time()
            if rfile != None and atime - ctime > session_timeout:
                self.lfile.write('Session timeout: %f\n' % (atime - ctime))
                self.lfile.flush()
                #rfile.flush()
                rfile.close()
                rfile = None
                if self.send_cb != None:
                    ED2.callFromThread(self.send_cb)
            if len(data) == 0:
                continue
            previous_ctime = ctime
            ctime = atime

            if rfile == None:
                fname = '/tmp/%s.csv' % int(ctime)
                rfile = open(fname, 'w')
                session_timeout = self.default_timeout
                previous_ctime = None
                count = 0
                self.lfile.write('Starting recording %s\n' % fname)
                self.lfile.flush()
                if self.sstart_cb != None:
                    ED2.callFromThread(self.sstart_cb)
            if previous_ctime != None and session_timeout > (ctime - previous_ctime) * 2 and count > 2:
                session_timeout = (ctime - previous_ctime) * 2
                self.lfile.write(' Updating session timeout to %f sec\n' % session_timeout)
                self.lfile.flush()
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
