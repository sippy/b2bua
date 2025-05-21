# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2018 Sippy Software, Inc. All rights reserved.
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

from functools import partial
from datetime import datetime
from heapq import heappush, heappop, heapify
from threading import Lock, local as t_local
from random import random
import sys, traceback, signal
from _thread import get_ident
from sippy.Time.MonoTime import MonoTime
from sippy.Core.Exceptions import dump_exception, StdException
from queue import Queue

from elperiodic.ElPeriodic import ElPeriodic

class EventListener(object):
    etime = None
    cb_with_ts = False
    randomize_runs = None

    def __lt__(self, other):
        return self.etime < other.etime

    def cancel(self):
        if self.ed != None:
            # Do not crash if cleanup() has already been called
            self.ed.twasted += 1
        self.cleanup()

    def cleanup(self):
        self.cb_func = None
        self.cb_params = None
        self.cb_kw_args = None
        self.ed = None
        self.randomize_runs = None

    def get_randomizer(self, p):
        def randomizer(p, x): return x * (1.0 + p * (1.0 - 2.0 * random()))
        return partial(randomizer, p)

    def spread_runs(self, p):
        self.randomize_runs = self.get_randomizer(p)

    def go(self):
        if self.ed.my_ident != get_ident():
            print(datetime.now(), 'EventDispatcher2: Timer.go() from wrong thread, expect Bad Stuff[tm] to happen')
            print('-' * 70)
            traceback.print_stack(file = sys.stdout)
            print('-' * 70)
            sys.stdout.flush()
        if not self.abs_time:
            if self.randomize_runs != None:
                ival = self.randomize_runs(self.ival)
            else:
                ival = self.ival
            self.etime = self.itime.getOffsetCopy(ival)
        else:
            self.etime = self.ival
            self.ival = None
            self.nticks = 1
        heappush(self.ed.tlisteners, self)
        return

class Singleton(object):
    '''Use to create a singleton'''
    __state_lock = Lock()

    def __new__(cls, *args, **kwds):
        '''
        >>> s = Singleton()
        >>> p = Singleton()
        >>> id(s) == id(p)
        True
        '''
        sself = '__self__'
        cls.__state_lock.acquire()
        if not hasattr(cls, sself):
            instance = object.__new__(cls)
            instance.__sinit__(*args, **kwds)
            setattr(cls, sself, instance)
        cls.__state_lock.release()
        return getattr(cls, sself)

    def __sinit__(self, *args, **kwds):
        pass

class EventDispatcher2(Singleton):
    tlisteners = None
    slisteners = None
    endloop = False
    el_rval = None
    signals_pending = None
    twasted = 0
    tcbs_lock = None
    last_ts = None
    my_ident = None
    state_lock = Lock()
    ed_inum = 0
    elp = None
    bands = None
    _exception = None
    tloc_data = None

    def __init__(self, freq = 100.0):
        EventDispatcher2.state_lock.acquire()
        if EventDispatcher2.ed_inum != 0:
            EventDispatcher2.state_lock.release()
            raise StdException('BZZZT, EventDispatcher2 has to be singleton!')
        EventDispatcher2.ed_inum = 1
        EventDispatcher2.state_lock.release()
        self.tcbs_lock = Lock()
        self.tlisteners = []
        self.slisteners = []
        self.signals_pending = []
        self.last_ts = MonoTime()
        self.my_ident = get_ident()
        self.elp = ElPeriodic(freq)
        self.elp.CFT_enable(signal.SIGURG)
        self.bands = [(freq, 0),]
        self.tloc_data = t_local()

    def signal(self, signum, frame):
        self.signals_pending.append(signum)

    def regTimer(self, timeout_cb, ival, nticks = 1, abs_time = False, *cb_params):
        self.last_ts = MonoTime()
        if nticks == 0:
            return
        if abs_time and not isinstance(ival, MonoTime):
            raise TypeError('ival is not MonoTime')
        el = EventListener()
        el.itime = self.last_ts.getCopy()
        el.cb_func = timeout_cb
        el.ival = ival
        el.nticks = nticks
        el.abs_time = abs_time
        el.cb_params = cb_params
        el.ed = self
        return el

    def dispatchTimers(self):
        while len(self.tlisteners) != 0:
            el = self.tlisteners[0]
            if el.cb_func != None and el.etime > self.last_ts:
                # We've finished
                return
            el = heappop(self.tlisteners)
            if el.cb_func == None:
                # Skip any already removed timers
                self.twasted -= 1
                continue
            if el.nticks == -1 or el.nticks > 1:
                # Re-schedule periodic timer
                if el.nticks > 1:
                    el.nticks -= 1
                if el.randomize_runs != None:
                    ival = el.randomize_runs(el.ival)
                else:
                    ival = el.ival
                el.etime.offset(ival)
                heappush(self.tlisteners, el)
                cleanup = False
            else:
                cleanup = True
            try:
                if not el.cb_with_ts:
                    el.cb_func(*el.cb_params)
                else:
                    el.cb_func(self.last_ts, *el.cb_params)
            except Exception as ex:
                if isinstance(ex, SystemExit):
                    raise
                dump_exception('EventDispatcher2: unhandled exception when processing timeout event')
            if self.endloop:
                return
            if cleanup:
                el.cleanup()

    def regSignal(self, signum, signal_cb, *cb_params, **cb_kw_args):
        sl = EventListener()
        if len([x for x in self.slisteners if x.signum == signum]) == 0:
            signal.signal(signum, self.signal)
        sl.signum = signum
        sl.cb_func = signal_cb
        sl.cb_params = cb_params
        sl.cb_kw_args = cb_kw_args
        self.slisteners.append(sl)
        return sl

    def unregSignal(self, sl):
        self.slisteners.remove(sl)
        if len([x for x in self.slisteners if x.signum == sl.signum]) == 0:
            signal.signal(sl.signum, signal.SIG_DFL)
        sl.cleanup()

    def dispatchSignals(self):
        while len(self.signals_pending) > 0:
            signum = self.signals_pending.pop(0)
            for sl in [x for x in self.slisteners if x.signum == signum]:
                if sl not in self.slisteners:
                    continue
                try:
                    sl.cb_func(*sl.cb_params, **sl.cb_kw_args)
                except Exception as ex:
                    if isinstance(ex, SystemExit):
                        raise
                    dump_exception('EventDispatcher2: unhandled exception when processing signal event')
                if self.endloop:
                    return

    def dispatchThreadCallback(self, thread_cb, cb_params):
        try:
            thread_cb(*cb_params)
        except BaseException as ex:
            if isinstance(ex, (SystemExit, KeyboardInterrupt)):
                self._exception = ex
                return
            dump_exception('EventDispatcher2: unhandled exception when processing from-thread-call')

    def dispatchThreadCallbackSync(self, res_cb_q, thread_cb, cb_params):
        try:
            res = thread_cb(*cb_params)
        except BaseException as ex:
            rval = (None, ex)
        else:
            rval = (res, None)
        res_cb_q.put(rval)

    def callFromThread(self, thread_cb, *cb_params):
        self.elp.call_from_thread(self.dispatchThreadCallback, thread_cb, cb_params)
        #print('EventDispatcher2.callFromThread completed', str(self), thread_cb, cb_params)

    def callFromThreadSync(self, thread_cb, *cb_params):
        if not hasattr(self.tloc_data, 'res_cb_q'):
            self.tloc_data.res_cb_q = Queue()
        res_cb_q = self.tloc_data.res_cb_q
        self.elp.call_from_thread(self.dispatchThreadCallbackSync, res_cb_q, thread_cb, cb_params)
        res, ex = res_cb_q.get()
        if ex is not None:
            raise ex
        return res

    def loop(self, timeout = None, freq = None):
        if freq != None and self.bands[0][0] != freq:
            for fb in self.bands:
                if fb[0] == freq:
                    self.bands.remove(fb)
                    break
            else:
                fb = (freq, self.elp.addband(freq))
            self.elp.useband(fb[1])
            self.bands.insert(0, fb)
        self.endloop = False
        self.last_ts = MonoTime()
        etime = None if timeout is None else self.last_ts.getOffsetCopy(timeout)
        while True:
            if len(self.signals_pending) > 0:
                self.dispatchSignals()
            if self.endloop:
                break
            self.dispatchTimers()
            if self.endloop:
                break
            if self.twasted * 2 > len(self.tlisteners):
                # Clean-up removed timers when their share becomes more than 50%
                self.tlisteners = [x for x in self.tlisteners if x.cb_func != None]
                heapify(self.tlisteners)
                self.twasted = 0
            if (timeout != None and self.last_ts > etime) or self.endloop:
                self.endloop = False
                break
            self.elp.procrastinate()
            self.last_ts = MonoTime()
            if self._exception is not None:
                ex = self._exception
                self._exception = None
                raise ex
        return self.el_rval

    def breakLoop(self, rval=0):
        self.endloop = True
        self.el_rval = rval
        #print('breakLoop')
        #import traceback
        #import sys
        #traceback.print_stack(file = sys.stdout)

ED2 = EventDispatcher2()
