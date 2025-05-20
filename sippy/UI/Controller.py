# Copyright (c) 2025 Sippy Software, Inc. All rights reserved.
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

from threading import Thread
from os.path import join as path_join, dirname
from html import escape as html_escape
from functools import partial
from weakref import WeakSet
from hashlib import sha256
from secrets import token_hex

from flask import Flask, jsonify, render_template, redirect, url_for, request
from flask_login import LoginManager, current_user, login_user, login_required, logout_user

from sippy.B2B.States import CCStateConnected
from sippy.SIPRec.UAC import SIPRecUAC, SRSTarget
from sippy.Exceptions.RtpProxyError import RtpProxyError

from .SystemConfiguration import SystemConfiguration
from .Lib import InThreadCaller, make_html_table, append_column, escape_column, \
  render_action_func, object_to_html_etable, update_with_json, catch_jerror
from .Lib import CallNotFound, RecordingNotPossible, UIError
from .Auth import User, Auth

class UIController(Thread):
    menu = {
        '/sysconfig': {'name':'System Configuration', 'order': 10},
        '/active_calls': {'name':'Active Calls', 'order': 0},
        '/routing': {'name':'Routing', 'order': 20},
        '/logout': {'name':'Logout', 'order': 30},
        '/restart': {'name':'Restart', 'order': 40},
        '/shutdown': {'name':'Shutdown', 'order': 50},
        '/login': {'methods': ['GET']},
        '/setup': {'methods': ['GET']},
        '/api/update_route': {'methods': ['POST']},
        '/api/update_sysconfig': {'methods': ['POST']},
        '/api/disconnect': {'methods': ['POST']},
        '/api/start_recording': {'methods': ['POST']},
        '/api/active_stats': {},
        '/api/login': {'methods': ['POST']},
        '/api/setup': {'methods': ['POST']},
    }
    daemon = True
    app_name:str
    customizer = None
    def __init__(self, global_config, app_name='Sippy B2BUA'):
        uiparams = global_config['uiparams']
        uiparams = dict(x.split('=', 1) for x in uiparams.split(';'))
        if 'ssl_context' in uiparams:
            uiparams['ssl_context'] = tuple(uiparams['ssl_context'].split(','))
        self.global_config = global_config
        self.kwargs = uiparams
        customizer = self.kwargs.get('customizer')
        if customizer:
            self.customizer = self._import_customizer(customizer)
            del self.kwargs['customizer']
        self.app_name = app_name
        self.siprec_uas = WeakSet()
        super().__init__()
        self.start()

    def _import_customizer(self, import_path):
        try:
            mod_path, func_name = import_path.split(':', 1)
            module = __import__(mod_path, fromlist=[''])
            func = getattr(module, func_name)
        except Exception as e:
            raise Exception(f"[UIController] Failed to run customizer '{import_path}'") from e
        return func

    def style(self):
        return '''
            <style>
                table { border-collapse: collapse; margin: auto; }
                th, td { padding: 8px 12px; }
                th { background-color: #f0f0f0; }
                body {{
                    margin: 0;
                    font-family: sans-serif;
                }}
            </style>
        '''

    def listActiveCalls(self):
        return self.global_config['_cmap'].listActiveCalls()

    def listRecordableCalls(self):
        if '_siprec_target' not in self.global_config:
            return None
        calls = self.global_config['_cmap'].getActiveCalls()
        condition = lambda x: x.state == CCStateConnected and x.rtp_proxy_session is not None
        recordable = tuple(str(x.cId) for x in calls if condition(x))
        return recordable

    def listRecordingCalls(self):
        return tuple(str(x.cId) for x in self.siprec_uas)

    def getActiveStats(self):
        calls = self.global_config['_cmap'].getActiveCalls()
        nconnected = len([x for x in calls if x.state == CCStateConnected])
        return nconnected, len(calls)

    def getRouting(self):
        routing = self.global_config['_static_routes'][''].getCopy()
        return routing

    def updateRouting(self, data):
        routing = self.global_config['_static_routes']['']
        update_with_json(routing, data)

    def getSysConfig(self):
        return SystemConfiguration()

    def updateSysConfig(self, data):
        sysconfig = SystemConfiguration()
        update_with_json(sysconfig, data)

    def getCallsById(self, callid):
        dlist = tuple(x for x in self.global_config['_cmap'].ccmap if str(x.cId) == callid)
        if len(dlist) == 0:
            raise CallNotFound(f"Call ID {callid} not found")
        return dlist

    def disconnectCall(self, callid):
        dlist = self.getCallsById(callid)
        for cc in dlist:
            cc.disconnect()

    def startRecording(self, callid):
        print(f"Recording call {callid}")
        dlist = self.getCallsById(callid)
        starget = self.global_config['_siprec_target']
        for cc in dlist:
            if cc.state != CCStateConnected:
                raise RecordingNotPossible(f"Call {callid} is not connected")
            if cc.rtp_proxy_session is None:
                raise RecordingNotPossible(f"Call {callid} is not using RTP proxy")
            try:
                src_ua = SIPRecUAC(self.global_config, cc.uaA, cc.uaO, cc.rtp_proxy_session, cId = cc.cId)
                src_ua.record(SRSTarget(starget))
            except RtpProxyError as e:
                raise RecordingNotPossible(f"SIPREC initializatin failed: {e}") from e
            self.siprec_uas.add(src_ua)

    def doShutdown(self):
        self.global_config['_cmap'].safeStop(signum=666)
        return len(self.listActiveCalls())

    def doRestart(self):
        self.global_config['_cmap'].safeRestart(signum=667)
        return len(self.listActiveCalls())

    def get_menu_items(self):
        return tuple((url, mi) for url, mi in self.menu.items() if 'name' in mi)

    def get_ordered_menu_items(self):
        named_items = self.get_menu_items()
        max_order = max((mi.get('order', 0) for _, mi in named_items if 'order' in mi), default=0)
        default_order = max_order + 1
        sorted_items = sorted(named_items, key=lambda x: x[1].get('order', default_order))
        return sorted_items

    def gen_menu(self):
        menu_pre = ['<div class="sidebar">', '<h2>Menu</h2>']
        menu_post = ['</div>',]
        sorted_items = self.get_ordered_menu_items()
        menu_items = [f'<a href="{html_escape(url)}">{html_escape(mi["name"])}</a>'
                      for url, mi in sorted_items]
        return '\n'.join(menu_pre + menu_items + menu_post)

    def render_page(self, content, style=None):
        return f'''
            <html>
                <head>
                    <title>{self.app_name} Management Console</title>
                    <link rel="stylesheet" href="/static/ui.css">
                    {style if style else self.style()}
                    <script src="/static/lib.js"></script>
                    <script src="/static/active_calls.js"></script>
                </head>
                <body>
                    <div id="call-status" class="call-status">
                        Calls: --
                    </div>
                    <div class="container">
                        {self.gen_menu()}
                        <div class="content">
                            {content}
                        </div>
                    </div>
                </body>
            </html>
        '''

    def render_active_calls(self, result):
        def blank_none(x):
            return x[0] if x is not None else '---'
        results = tuple((cid, blank_none(uaa), blank_none(uao))
                         for cid, _, uaa, uao in result if uaa or uao)

        headers = ['Call ID', 'Caller State', 'Callee State', 'Action1']
        when_disc = lambda row: all(r not in ('Failed', 'Dead', 'Disconnected') for r in row[1:3])
        render_disc = partial(render_action_func, when=when_disc)
        result = append_column(results, render_disc)
        def bundle():
            return (self.listRecordingCalls(), self.listRecordableCalls())
        recording, recordable = self.main_call(bundle)
        if recordable is not None:
            when_rec = lambda row: (row[0] in recordable) and (row[0] not in recording)
            render_rec = partial(render_action_func, action='data-callid', name='Record',
                                 aurl='/api/start_recording', when=when_rec)
            result = append_column(result, render_rec)
            headers.append('Call Recording')
        table_html = make_html_table(escape_column(result, 0), headers=headers)
        content = f'''
                    <h1>Active Calls ({len(results)})</h1>
                    {table_html}
                '''
        return self.render_page(content)

    def render_std(self, result, title, onsubmit):
        style = '<link rel="stylesheet" href="/static/config_box.css">'
        content = f'''
                    <h1>{title}</h1>
                    {object_to_html_etable(result, onsubmit)}
                '''
        return self.render_page(content, style)

    def render_shutdown(self, result):
        msg = f'Calls remaining {result}. Shutting down...'
        if result == 0:
            return self.render_logout(title='Shutting down...', message=msg)
        return self.render_page(f'<h1>{msg}</h1>')

    def render_restart(self, result):
        return self.render_page(f'<h1>Calls remaining {result}. Restarting...</h1>')

    def render_template(self, template_name, **kwa):
        title = f"{self.app_name} Management Console"
        return render_template(template_name, title=f"{self.app_name} Management Console", **kwa)

    def render_login(self):
        if current_user.is_authenticated:
            return redirect(url_for('/'))
        return self.render_template('login.html', page='Login', header=f'{self.app_name} Login',
          button_text='Login', action='/api/login', on_success='/')

    def render_logout(self, title='Logging out...', message='Logout Sucessful. Please login.'):
        username = current_user.id
        logout_user()
        return render_template('redir2login.html', title=title, message=message, username=username)

    @catch_jerror
    def api_login(self):
        data = request.get_json(force=True)
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            raise UIError('Missing username or password', 400)

        auth = Auth.load(self.app_name)
        if auth is None:
            raise UIError('Authentication not initialized', 403)
        if auth.verify(username,  password):
            login_user(User(username))
            return jsonify({'status': 'ok'})
        raise UIError('Invalid credentials', 401)

    def render_setup(self):
        login_url = '/login'
        if Auth.load(self.app_name) is not None:
            return redirect(url_for(login_url))
        return self.render_template('login.html', page='Initial Setup', header=f'Create Admin User',
          button_text='Create User', action='/api/setup', on_success=login_url)

    @catch_jerror
    def api_setup(self):
        if Auth.load(self.app_name) is not None:
            raise UIError('Already configured', 403)

        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            raise UIError('Username and password required', 400)

        auth = Auth.create(self.app_name, data['username'], data['password'])
        auth.save()
        return jsonify({'status': 'ok'})

    def run(self):
        self.main_call = main_call = InThreadCaller()
        sysconfig_rend = partial(self.render_std, title='System Configuration', onsubmit='/api/update_sysconfig')
        self.menu['/sysconfig']['app_route'] = partial(main_call.hcall, sysconfig_rend, self.getSysConfig)
        self.menu['/active_calls']['app_route'] = partial(main_call.hcall, self.render_active_calls, self.listActiveCalls)
        route_rend = partial(self.render_std, title='Routing Configuration', onsubmit='/api/update_route')
        self.menu['/routing']['app_route'] = partial(main_call.hcall, route_rend, self.getRouting)
        self.menu['/restart']['app_route'] = partial(main_call.hcall, self.render_restart, self.doRestart)
        self.menu['/shutdown']['app_route'] = partial(main_call.hcall, self.render_shutdown, self.doShutdown)
        self.menu['/api/disconnect']['app_route'] = partial(main_call.jcall_callid, self.disconnectCall)
        self.menu['/api/start_recording']['app_route'] = partial(main_call.jcall_callid, self.startRecording)
        self.menu['/api/update_route']['app_route'] = partial(main_call.jcall_b, self.updateRouting)
        def active_stats():
            def render(result):
                connected, total = result
                return jsonify({'connected': connected, 'total': total})
            return main_call.jcall(render, self.getActiveStats)
        self.menu['/api/active_stats']['app_route'] = active_stats
        self.menu['/api/update_sysconfig']['app_route'] = partial(main_call.jcall_b, self.updateSysConfig)
        self.menu['/login']['app_route'] = self.render_login
        self.menu['/api/login']['app_route'] = self.api_login
        self.menu['/logout']['app_route'] = self.render_logout
        self.menu['/setup']['app_route'] = self.render_setup
        self.menu['/api/setup']['app_route'] = self.api_setup

        static_path = path_join(dirname(__file__), 'static')
        template_path = path_join(dirname(__file__), 'templates')
        print(f"Serving static files from {static_path}")
        def make_app():
            return Flask(self.app_name, static_folder=static_path, template_folder=template_path)
        app = self.customizer(self, make_app) if self.customizer else make_app()

        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.login_view = "/login"
        @login_manager.user_loader
        def load_user(user_id):
            # In your case, the ID *is* the username
            return User(user_id)
        @app.before_request
        def ensure_auth_setup():
            if request.endpoint in ('/setup', '/api/setup', 'static'):
                return
            if Auth.load(self.app_name) is None:
                return redirect(url_for('/setup'))

        app.secret_key = token_hex(32)

        default_methods = ['GET']
        for url, meta in self.menu.items():
            handler = meta.get('app_route')
            if not handler:
                continue
            methods = meta.get('methods', default_methods)
            if url not in ('/setup', '/api/setup', '/login', '/api/login'):
                handler = login_required(handler)
            app.add_url_rule(url, endpoint=url, view_func=handler, methods=methods)
        if '/' not in self.menu:
            _, root_item = self.get_ordered_menu_items()[0]
            url = '/'
            root_app = root_item['app_route']
            root_methods = root_item.get('methods', default_methods)
            app.add_url_rule(url, endpoint=url, view_func=login_required(root_app), methods=root_methods)

        app.run(**self.kwargs)

if __name__ == '__main__':
    from sippy.Core.EventDispatcher import ED2
    uiparams = 'ssl_context:cert.pem,key.pem;host=0.0.0.0;port=4430'
    uc = UIController({'uiparams':uiparams})
    ED2.loop()
