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

import sys
sys.path.append('..')

from sippy.Rtp_proxy_client import Rtp_proxy_client
from sippy.Timeout import Timeout

class Rtp_cluster_member(Rtp_proxy_client):
    name = None
    status = 'ACTIVE'
    capacity = 4000
    weight = 100
    wan_address = None
    call_id_map = None
    call_id_map_old = None
    on_state_change = None
    on_active_update = None
    timer = None

    def __init__(self, name, *args, **kwargs):
        self.call_id_map = []
        self.call_id_map_old = []
        self.name = name
        Rtp_proxy_client.__init__(self, *args, **kwargs)
        self.timer = Timeout(self.call_id_map_aging, 600, -1)

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
        if not self.online and self.on_state_change != None:
            self.on_state_change(self, True)
        Rtp_proxy_client.go_online(self)

    def go_offline(self):
        #print 'go_offline', self
        if self.online and self.on_state_change != None:
            self.on_state_change(self, False)
        Rtp_proxy_client.go_offline(self)

    def update_active(self, active_sessions):
        if self.active_sessions != active_sessions and self.on_active_update != None:
            self.on_active_update(self, active_sessions)
        Rtp_proxy_client.update_active(self, active_sessions)

    def call_id_map_aging(self):
        if self.shutdown:
            self.timer.cancel()
            return
        if len(self.call_id_map) < 1000:
            # Do not age if there are less than 1000 calls in the list
            self.call_id_map_old = []
            return
        self.call_id_map_old = self.call_id_map[len(self.call_id_map) / 2:]
        del self.call_id_map[len(self.call_id_map) / 2:]
