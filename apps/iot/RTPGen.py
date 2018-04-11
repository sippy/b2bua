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

from threading import Thread, Lock

#import sys
#sys.path.append('../..')

from math import floor

from elperiodic.ElPeriodic import ElPeriodic

import sys
sys.path.append('/home/sobomax/librtpsynth/python')
from RtpSynth import RtpSynth

from sippy.Core.EventDispatcher import ED2
from sippy.Time.clock_dtime import clock_getdtime, CLOCK_MONOTONIC

RTPGenInit = 0
RTPGenRun = 1
RTPGenStop = 2

class RTPGen(Thread):
    ptime = 0.030
    elp = None
    rsth = None
    state_lock = Lock()
    state = RTPGenInit
    userv = None
    target = None

    def __init__(self):
        Thread.__init__(self)
        self.setDaemon(True)

    def start(self, userv, target):
        pfreq = 1.0 / self.ptime
        self.userv = userv
        self.target = target
        self.elp = ElPeriodic(pfreq)
        self.rsth = RtpSynth(8000, 30)
        Thread.start(self)

    def run(self):
        stime = clock_getdtime(CLOCK_MONOTONIC)
        self.state_lock.acquire()
        if self.state == RTPGenStop:
            self.state_lock.release()
            return
        self.state = RTPGenRun
        self.state_lock.release()
        last_npkt = -1
        while True:
            self.state_lock.acquire()
            if self.state == RTPGenStop:
                self.state_lock.release()
                return
            self.state_lock.release()
            ntime = clock_getdtime(CLOCK_MONOTONIC)
            npkt = floor((ntime - stime) / self.ptime)
            rp = self.rsth.next_pkt(170, 0)
            self.userv.send_to(b'ping!', self.target)
            self.rsth.pkt_free(rp)
            #print(npkt - last_npkt)
            last_npkt = npkt
            self.elp.procrastinate()

    def stop(self):
        self.state_lock.acquire()
        pstate = self.state
        if self.state == RTPGenRun:
            self.state = RTPGenStop
        self.state_lock.release()
        if pstate == RTPGenRun:
            self.join()
        self.userv = None
        self.state_lock.acquire()
        self.state = RTPGenInit
        self.state_lock.release()

if __name__ == '__main__':
    r = RTPGen()
    r.start()
    from time import sleep
    sleep(5)
    r.stop()
