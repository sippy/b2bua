# Copyright (c) 2006-2014 Sippy Software, Inc. All rights reserved.
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

import ctypes, os
import ctypes.util

CLOCK_REALTIME = 0
CLOCK_MONOTONIC = 4 # see <linux/time.h> / <include/time.h>
CLOCK_UPTIME = 5 # FreeBSD-specific. 
CLOCK_UPTIME_PRECISE = 7 # FreeBSD-specific.
CLOCK_UPTIME_FAST = 8 # FreeBSD-specific.

class timespec(ctypes.Structure):
    _fields_ = [
        ('tv_sec', ctypes.c_long),
        ('tv_nsec', ctypes.c_long)
    ]

def find_libc():
    spaths = ('/usr/lib/libc.so', '/lib/libc.so')
    for path in spaths:
        if os.path.islink(path):
            libcname = os.readlink(path)
            return (libcname)
        elif os.path.isfile(path):
            for line in file(path, 'r').readlines():
                parts = line.split(' ')
                if parts[0] != 'GROUP':
                    continue
                libcname = parts[2]
                return (libcname)
    return None

libname = find_libc()
if libname == None:
    libname = ctypes.util.find_library('c')
libc = ctypes.CDLL(libname, use_errno = True)
clock_gettime = libc.clock_gettime
clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(timespec)]

def clock_getdtime(type):
    t = timespec()
    if clock_gettime(type, ctypes.pointer(t)) != 0:
        errno_ = ctypes.get_errno()
        raise OSError(errno_, os.strerror(errno_))
    return float(t.tv_sec) + float(t.tv_nsec * 1e-09)

if __name__ == "__main__":
    print '%.10f' % (clock_getdtime(CLOCK_REALTIME),)
    print '%.10f' % (clock_getdtime(CLOCK_REALTIME) - clock_getdtime(CLOCK_UPTIME),)
    print '%.10f' % (clock_getdtime(CLOCK_REALTIME) - clock_getdtime(CLOCK_UPTIME_PRECISE),)
    print '%.10f' % (clock_getdtime(CLOCK_REALTIME) - clock_getdtime(CLOCK_UPTIME_FAST),)
    print '%.10f' % (clock_getdtime(CLOCK_REALTIME) - clock_getdtime(CLOCK_MONOTONIC),)
