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

import sys
sys.path.append('..')

from sippy.Rtp_proxy_client import Rtp_proxy_client
from sippy.Timeout import Timeout

class rc_filter(object):
    a = None
    b = None
    lastval = None

    def __init__(self, fcoef, initval = 0.0):
        self.lastval = initval
        self.a = 1.0 - fcoef
        self.b = fcoef

    def apply(self, x):
        self.lastval = (self.a * x) + (self.b * self.lastval)
        return self.lastval

    def get(self):
        return self.lastval

class Rtp_cluster_member(Rtp_proxy_client):
    name = None
    status = 'ACTIVE'
    capacity = 4000
    weight = 100
    wan_address = None
    lan_address = None
    call_id_map = None
    call_id_map_old = None
    on_state_change = None
    on_active_update = None
    timer = None
    global_config = None
    asess_filtered = None
    cmd_out_address = None
    stats_cache = None

    def __init__(self, name, global_config, address, cmd_out_address):
        self.call_id_map = []
        self.call_id_map_old = []
        self.name = name
        self.global_config = global_config
        self.asess_filtered = rc_filter(0.9)
        self.cmd_out_address = cmd_out_address
        self.stats_cache = {}
        if cmd_out_address != None:
            bind_address = (cmd_out_address, 0)
        else:
            bind_address = None
        Rtp_proxy_client.__init__(self, global_config, address, bind_address = bind_address)
        self.timer = Timeout(self.call_id_map_aging, 600, -1)

    def reconnect(self, address):
        if self.cmd_out_address != None:
            bind_address = (self.cmd_out_address, 0)
        else:
            bind_address = None
        Rtp_proxy_client.reconnect(self, address, bind_address = bind_address)

    def isYours(self, call_id):
        if call_id in self.call_id_map:
            self.call_id_map.remove(call_id)
            self.call_id_map.insert(0, call_id)
            return True
        if call_id not in self.call_id_map_old:
            return False
        self.call_id_map_old.remove(call_id)
        self.call_id_map.insert(0, call_id)
        return True

    def bind_session(self, call_id, cmd_type):
        if cmd_type != 'D':
            self.call_id_map.insert(0, call_id)
        else:
            self.call_id_map_old.insert(0, call_id)

    def unbind_session(self, call_id):
        self.call_id_map.remove(call_id)
        self.call_id_map_old.insert(0, call_id)

    def go_online(self):
        #print 'go_online', self
        if not self.online:
            self.global_config['_sip_logger'].write('RTPproxy "%s" has changed ' \
              'status from offline to online' % self.name)
            if self.on_state_change != None:
                self.on_state_change(self, True)
        Rtp_proxy_client.go_online(self)

    def go_offline(self):
        #print 'go_offline', self
        if self.online:
            self.global_config['_sip_logger'].write('RTPproxy "%s" has changed ' \
              'status from online to offline' % self.name)
            self.stats_cache = {}
            if self.on_state_change != None:
                self.on_state_change(self, False)
        Rtp_proxy_client.go_offline(self)

    def update_active(self, active_sessions, *more_args):
        self.asess_filtered.apply(active_sessions)
        if self.active_sessions != active_sessions and self.on_active_update != None:
            self.on_active_update(self, active_sessions)
        Rtp_proxy_client.update_active(self, active_sessions, *more_args)

    def call_id_map_aging(self):
        if self.shut_down:
            self.timer.cancel()
            return
        if len(self.call_id_map) < 1000:
            # Do not age if there are less than 1000 calls in the list
            self.call_id_map_old = []
            return
        self.call_id_map_old = self.call_id_map[len(self.call_id_map) / 2:]
        del self.call_id_map[len(self.call_id_map) / 2:]

    def get_caputil(self):
        return (self.asess_filtered.get() / self.capacity)
