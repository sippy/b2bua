from __future__ import print_function

from threading import Thread
from serial import Serial
from time import time, sleep

class PELIO(Thread):
    default_timeout = 60.0
    sdev = '/dev/cuau0'
    brate = 9600
    lfile = None

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
