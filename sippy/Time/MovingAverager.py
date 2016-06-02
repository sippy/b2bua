from math import exp

from sippy.Timeout import Timeout

class MovingAverager(object):
    tick = None
    lastval = 0.0
    ecoef = None
    read_data_cb = None

    def __init__(self, run_period, avg_over_period, read_data_cb):
        self.tick = Timeout(self.update, run_period, -1)
        self.ecoef = exp(-1.0 * run_period / avg_over_period)
        self.read_data_cb = read_data_cb

    def update(self):
        currval = self.read_data_cb()
        if currval == None:
            currval = 0.0
        self.lastval = currval + self.ecoef * (self.lastval - currval)

    def cancel(self):
        self.tick.cancel()
        self.read_data_cb = None
