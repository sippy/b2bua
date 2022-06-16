# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2019 Sippy Software, Inc. All rights reserved.
#
# Warning: This computer program is protected by copyright law and
# international treaties. Unauthorized reproduction or distribution of this
# program, or any portion of it, may result in severe civil and criminal
# penalties, and will be prosecuted under the maximum extent possible under
# law.

from SdpOrigin import SdpOrigin

class SdpSession:
    last_origin = None
    origin      = None

    def __init__(self, origin = None):
        if origin != None:
            self.origin = origin
        else:
            self.origin = SdpOrigin()

    def fixup_version(self, event):
        body = event.getBody()
        if body == None:
            return # no SDP so there is nothing to do
        try:
            body.parse()
        except:
            # not an SDP
            return
        new_origin = body.content.o_header.getCopy()
        if self.last_origin != None:
            if self.last_origin.session_id != new_origin.session_id or \
                    self.last_origin.version != new_origin.version:
                self.origin.version += 1
        self.last_origin = new_origin
        body.content.o_header = self.origin.getCopy()
        body.needs_update = False
