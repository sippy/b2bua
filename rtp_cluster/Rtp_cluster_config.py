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

from os.path import dirname
from xml.sax import make_parser
from xml.sax.handler import feature_namespaces, feature_validation
from xml.sax.handler import ContentHandler
from xml.sax.saxutils import escape

RTP_CLUSTER_CONFIG_DTD = "Rtp_cluster_config.dtd"

class ValidateHandler(ContentHandler):
    def __init__(self, config):
        self.config = config
        self.element = None
        self.warnings = []
        self.errors = []
        self.rtp_cluster = None
        self.rtpproxy = None
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

    def endElement(self, name):
        if name == 'rtp_cluster':
            self.rtp_cluster = None
            self.ctx.pop()

        elif name == 'rtpproxy':
            self.rtpproxy = None
            self.ctx.pop()

    def warning(self, exception):
        self.warnings.append(exception)

    def error(self, exception):
        self.errors.append(exception)

    def fatalError(self, exception):
        self.errors.append(exception)

def read_cluster_config(config, debug = False):
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
                print 'warning: %s' % str(warning)

    if h.errors:
        for error in h.errors:
            if debug:
                print 'error: %s' % str(error)
        raise Exception('validation failed')

    if debug:
        print 'Parsed:'
        print parsed_config[0]['rtpproxies'][0]
    return parsed_config

def gen_cluster_config(config):
    xml = '<rtp_cluster_config>\n\n'

    for cluster in config:
        xml += '  <rtp_cluster>\n'
        xml += '    <name>%s</name>\n' % escape(cluster['name'])
        xml += '    <protocol>%s</protocol>\n' % escape(cluster['protocol'])
        xml += '    <address>%s</address>\n\n' % escape(cluster['address'])

        for proxy in cluster['rtpproxies']:
            xml += '    <rtpproxy>\n'
            xml += '      <name>%s</name>\n' % escape(proxy['name'])
            xml += '      <protocol>%s</protocol>\n' % escape(proxy['protocol'])
            xml += '      <address>%s</address>\n' % escape(proxy['address'])
            if proxy['wan_address'] != None:
                xml += '      <wan_address>%s</wan_address>\n' % escape(proxy['wan_address'])
            xml += '      <weight>%s</weight>\n' % escape(str(proxy['weight']))
            xml += '      <capacity>%s</capacity>\n' % escape(str(proxy['capacity']))
            xml += '      <status>%s</status>\n' % escape(proxy['status'])
            xml += '    </rtpproxy>\n'

        xml += '  </rtp_cluster>\n\n'

    xml += '</rtp_cluster_config>\n'

    return xml

if __name__ == '__main__':
    import sys
    try:
        print 'Reading config...'
        f = open('rtp_cluster.xml')
        config = read_cluster_config(f.read(), True)

        print 'Generating config...'
        config = gen_cluster_config(config)
        
        print 'Reading generated config...'
        config = read_cluster_config(config, True)
        
    except Exception, detail:
        print >> sys.stderr, 'error: %s' % detail

