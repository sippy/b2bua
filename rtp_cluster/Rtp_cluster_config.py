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

from os.path import dirname
from xml.sax import make_parser
from xml.sax.handler import feature_namespaces, feature_validation
from xml.sax.handler import ContentHandler
from xml.sax.saxutils import escape

RTP_CLUSTER_CONFIG_DTD = "Rtp_cluster_config.dtd"

class DisconnectNotify(object):
    section_name = None
    in_address = None
    dest_sprefix = None

    def __init__(self, section_name = 'disconnect_notify'):
        self.section_name = section_name

    def set_in_address(self, in_address_str):
        in_address = in_address_str.split(':', 1)
        self.in_address = (in_address[0], int(in_address[1]))

    def __str__(self, ident = '', idlevel = 1):
        return ('%s<%s>\n%s<inbound_address>%s:%d</inbound_address>\n' \
          '%s<dest_socket_prefix>%s</dest_socket_prefix>\n%s</%s>' % \
          (ident * idlevel, self.section_name, ident * (idlevel + 1), \
          self.in_address[0], self.in_address[1], ident * (idlevel + 1), \
          self.dest_sprefix, ident * idlevel, self.section_name))

class ValidateHandler(ContentHandler):
    def __init__(self, config):
        self.config = config
        self.element = None
        self.warnings = []
        self.errors = []
        self.rtp_cluster = None
        self.rtpproxy = None
        self.dnconfig = None
        self.ctx = []

    def startElement(self, name, attrs):
        self.element = name

        if self.element == 'rtp_cluster':
            self.rtp_cluster = {'rtpproxies': []}
            self.config.append(self.rtp_cluster)
            self.ctx.append('rtp_cluster')

        elif self.element == 'rtpproxy':
            self.rtpproxy = {}
            self.rtp_cluster['rtpproxies'].append(self.rtpproxy)
            self.ctx.append('rtpproxy')

        elif self.element == 'disconnect_notify':
            self.dnconfig = DisconnectNotify(self.element)
            self.rtp_cluster['dnconfig'] = self.dnconfig
            self.ctx.append('dnconfig')

        elif self.element == 'capacity_limit' and self.ctx[-1] == 'rtp_cluster':
            cl_type = attrs.getValue('type')
            if cl_type == 'soft':
                self.rtp_cluster['capacity_limit_soft'] = True
            else:
                self.rtp_cluster['capacity_limit_soft'] = False

    def characters(self, content):
        if self.ctx[-1] == 'rtp_cluster':
            if self.element == 'name':
                for c in self.config:
                    if c.has_key('name'):
                        if c['name'] == content:
                            raise Exception('rtp_cluster name should be unique: %s' % (content))
                self.rtp_cluster['name'] = content
            elif self.element == 'protocol':
                self.rtp_cluster['protocol'] = content.lower()
                if self.rtp_cluster['protocol'] != 'udp' and self.rtp_cluster['protocol'] != 'unix':
                    raise Exception("rtp_cluster protocol should be either 'udp' or 'unix'")
            elif self.element == 'address':
                if self.rtp_cluster['protocol'] == 'udp':
                    content = content.split(':', 1)
                    if len(content) == 1:
                        self.rtp_cluster['address'] = (content[0], 22222)
                    else:
                        self.rtp_cluster['address'] = (content[0], int(content[1]))
                else:
                    self.rtp_cluster['address'] = content

        elif self.ctx[-1] == 'rtpproxy':
            if self.element == 'name':
                for c in self.rtp_cluster['rtpproxies']:
                    if c.has_key('name'):
                         if c['name'] == content:
                             raise Exception('rtpproxy name should be unique within rtp_cluster: %s' % (content))
                self.rtpproxy['name'] = content
            elif self.element == 'protocol':
                self.rtpproxy['protocol'] = content.lower()
                if self.rtpproxy['protocol'] != 'udp' and self.rtpproxy['protocol'] != 'unix':
                    raise Exception("rtpproxy protocol should be either 'udp' or 'unix'")
            elif self.element == 'address':
                self.rtpproxy['address'] = content
            elif self.element == 'wan_address':
                self.rtpproxy['wan_address'] = content
            elif self.element == 'lan_address':
                self.rtpproxy['lan_address'] = content
            elif self.element == 'cmd_out_address':
                self.rtpproxy['cmd_out_address'] = content
            elif self.element == 'weight':
                try:
                    self.rtpproxy['weight'] = int(content)
                except Exception:
                    raise Exception("wrong rtpproxy weight value, an integer is expected: %s" % (content))
                if self.rtpproxy['weight'] <= 0:
                    raise Exception("rtpproxy weight should > 0: %s" % (content))
            elif self.element == 'capacity':
                try:
                    self.rtpproxy['capacity'] = int(content)
                except Exception:
                    raise Exception("wrong rtpproxy capacity value, an integer is expected: %s" % (content))
                if self.rtpproxy['capacity'] <= 0:
                    raise Exception("rtpproxy capacity should > 0: %s" % (content))
            elif self.element == 'status':
                self.rtpproxy['status'] = content.lower()
                if self.rtpproxy['status'] != 'suspended' and self.rtpproxy['status'] != 'active':
                    raise Exception("rtpproxy status should be either 'suspended' or 'active'")

        if self.ctx[-1] == 'dnconfig':
            if self.element == 'inbound_address':
                self.dnconfig.set_in_address(content)
            elif self.element == 'dest_socket_prefix':
                self.dnconfig.dest_sprefix = content

    def endElement(self, name):
        if name == 'rtp_cluster':
            self.rtp_cluster = None
            self.ctx.pop()

        elif name == 'rtpproxy':
            self.rtpproxy = None
            self.ctx.pop()

        elif name == 'disconnect_notify':
            self.dnconfig = None
            self.ctx.pop()

    def warning(self, exception):
        self.warnings.append(exception)

    def error(self, exception):
        self.errors.append(exception)

    def fatalError(self, exception):
        self.errors.append(exception)

def read_cluster_config(global_config, config, debug = False):
    parsed_config = []

    parser = make_parser('xml.sax.drivers2.drv_xmlproc')
    parser.setFeature(feature_namespaces, False)
    parser.setFeature(feature_validation, True)

    h = ValidateHandler(parsed_config)
    parser.setContentHandler(h)
    parser.setErrorHandler(h)

    try:
        dir_name = dirname(__file__)
        if dir_name == '':
            dtd = RTP_CLUSTER_CONFIG_DTD
        else:
            dtd = dir_name + '/' + RTP_CLUSTER_CONFIG_DTD
        f = open(dtd)
        dtd = f.read()
        parser.feed(dtd)

        parser.feed(config)
        parser.close()
    except Exception, detail:
        raise Exception('parsing failed: %s' % (detail))

    if h.warnings:
        for warning in h.warnings:
            if debug:
                global_config['_sip_logger'].write('read_cluster_config:warning: %s' % str(warning))

    if h.errors:
        for error in h.errors:
            global_config['_sip_logger'].write('read_cluster_config:error: %s' % str(error))
        raise Exception('validation failed')

    if debug:
        global_config['_sip_logger'].write('Parsed:\n%s' % parsed_config[0]['rtpproxies'][0])
    return parsed_config

def gen_cluster_config(config):
    xml = '<rtp_cluster_config>\n\n'

    for cluster in config:
        xml += '  <rtp_cluster>\n'
        xml += '    <name>%s</name>\n' % escape(cluster['name'])
        xml += '    <protocol>%s</protocol>\n' % escape(cluster['protocol'])

        address = cluster['address']
        if cluster['protocol'] == 'udp':
            xml += '    <address>%s:%d</address>\n\n' % (escape(address[0]), address[1])
        else:
            xml += '    <address>%s</address>\n\n' % escape(address)

        dnconfig = cluster.get('dnconfig', None)
        if dnconfig != None:
            xml += dnconfig.__str__('  ', 2) + '\n\n'

        cl_type = cluster.get('capacity_limit_soft', True)
        if cl_type:
            cl_type = 'soft'
        else:
            cl_type = 'hard'
        xml += '    <capacity_limit type="%s" />\n\n' % escape(cl_type)

        for proxy in cluster['rtpproxies']:
            xml += '    <rtpproxy>\n'
            xml += '      <name>%s</name>\n' % escape(proxy['name'])
            xml += '      <protocol>%s</protocol>\n' % escape(proxy['protocol'])
            xml += '      <address>%s</address>\n' % escape(proxy['address'])
            xml += '      <weight>%s</weight>\n' % escape(str(proxy['weight']))
            xml += '      <capacity>%s</capacity>\n' % escape(str(proxy['capacity']))
            xml += '      <status>%s</status>\n' % escape(proxy['status'])
            for key_name in ('wan_address', 'lan_address', 'cmd_out_address'):
                if proxy.has_key(key_name):
                    xml += '      <%s>%s</%s>\n' % (key_name, escape(proxy[key_name]), key_name)
            xml += '    </rtpproxy>\n'

        xml += '  </rtp_cluster>\n\n'

    xml += '</rtp_cluster_config>\n'

    return xml

if __name__ == '__main__':
    import sys, traceback

    sys.path.append('sippy')

    from sippy.SipLogger import SipLogger

    global_config = {}
    global_config['_sip_logger'] = SipLogger('Rtp_cluster_config::selftest')
    try:
        global_config['_sip_logger'].write('Reading config...')
        f = open('rtp_cluster.xml')
        config = read_cluster_config(global_config, f.read(), True)

        global_config['_sip_logger'].write('Generating config...')
        config = gen_cluster_config(config)
        
        global_config['_sip_logger'].write('Reading generated config...')
        config = read_cluster_config(global_config, config, True)
        
    except Exception, detail:
        global_config['_sip_logger'].write('error: %s' % detail)
        traceback.print_exc(file = sys.stderr)
