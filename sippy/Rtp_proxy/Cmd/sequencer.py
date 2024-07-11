# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2022 Sippy Software, Inc. All rights reserved.
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

class Rtp_proxy_cmd_sequencer(object):
    rtp_proxy_client = None
    comqueue = None
    inflight = None
    deleted = False

    def __init__(self, rtpp_client):
        self.rtp_proxy_client = rtpp_client
        self.comqueue = []

    def send_command(self, command, result_callback = None, *callback_parameters):
        if self.rtp_proxy_client == None:
            return
        if self.inflight != None:
            self.comqueue.append((command, result_callback, callback_parameters))
            return
        self.inflight = (command, result_callback, callback_parameters)
        self.rtp_proxy_client.send_command(command, self.result_callback)

    def result_callback(self, result):
        command, result_callback, callback_parameters = self.inflight
        self.inflight = None
        if self.rtp_proxy_client != None and len(self.comqueue) > 0:
            self.inflight = self.comqueue.pop(0)
            self.rtp_proxy_client.send_command(self.inflight[0], self.result_callback)
        if result_callback != None:
            result_callback(result, *callback_parameters)
        if self.deleted:
            self.delete()
            return

    def delete(self):
        if self.inflight is not None:
            self.deleted = True
            return
        # break the reference loop
        self.rtp_proxy_client = None
