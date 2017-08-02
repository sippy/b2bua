# Copyright (c) 2012 Sippy Software, Inc. All rights reserved.
#
# Warning: This computer program is protected by copyright law and
# international treaties. Unauthorized reproduction or distribution of this
# program, or any portion of it, may result in severe civil and criminal
# penalties, and will be prosecuted under the maximum extent possible under
# law.

class ESipParseException(Exception):
    sip_response = None
    arg = None

    def __init__(self, arg, sip_response = None):
        self.arg = arg
        self.sip_response = sip_response

    def __str__(self):
        return str(self.arg)
