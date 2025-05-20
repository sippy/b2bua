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

from datetime import datetime
from collections import OrderedDict
from traceback import format_exc
from functools import wraps

from html import escape as html_escape
from flask import jsonify, request

from sippy.Core.EventDispatcher import ED2

class UIError(Exception):
    scode:int = 500
    def __init__(self, message, scode=scode):
        super().__init__(message)
        self.scode = scode

class CallNotFound(UIError):
    scode = 404
class RecordingNotPossible(UIError):
    pass

def catch_jerror(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as ex:
            if isinstance(ex, UIError):
                return jsonify({'status': 'error', 'message': str(ex)}), ex.scode
            return jsonify({'status': 'error', 'message': format_exc()[-400:]}), 500
    return wrapper

class InThreadCaller():
    def __call__(self, func, *args):
        return ED2.callFromThreadSync(func, *args)

    @catch_jerror
    def jcall(self, rfunc, func, *args):
        result = self(func, *args)
        return rfunc(result)

    def jcall_b(self, func, jname=None):
        if jname is None:
            data = request.get_json(force=True)
        else:
            data = request.json.get(jname)
        print(f"Received {func} data: {data}")
        def render(result): return jsonify({'status': 'ok'})
        return self.jcall(render, func, data)

    def jcall_callid(self, func):
        return self.jcall_b(func, jname='callid')

    def hcall(self, rfunc, func, *args):
        try:
            result = self(func, *args)
        except Exception as ex:
            return f"<pre>Error: {ex}</pre>", 500
        return rfunc(result)

def make_html_table(rows, headers=None):
    html = ['<table border="1">']
    if headers:
        html.append('<tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr>')
    for row in rows:
        html.append('<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>')
    html.append('</table>')
    return '\n'.join(html)

def append_column(rows, transform_f):
    res = [row + (transform_f(row),) for row in rows]
    return res

def escape_column(rows, col):
    res = tuple(tuple(row[:col] + (html_escape(row[col], quote=True),) + row[col+1:])
                for row in rows)
    return res

def render_action_func(row, action='data-callid', name='Disconnect',
                       aurl='/api/disconnect', when=None):
    daction = html_escape(row[0], quote=True)
    if when is not None and not when(row):
        return ''
    return f'''
        <form {action}="{daction}" class="action-form" style="margin:0" action="{aurl}">
            <button type="submit">{name}</button>
        </form>
    '''

def object_to_html_table(obj):
    html = ['<table border="1">']
    html.append('<tr><th>Name</th><th>Value</th><th>Type</th></tr>')
    for attr in dir(obj):
        if attr.startswith('_') or callable(getattr(obj, attr, None)):
            continue
        try:
            value = getattr(obj, attr)
            typename = type(value).__name__
        except Exception as ex:
            value = f"<error: {ex}>"
            typename = "error"
        html.append(
            f'<tr>'
            f'<td>{html_escape(attr)}</td>'
            f'<td>{html_escape(str(value))}</td>'
            f'<td>{html_escape(typename)}</td>'
            f'</tr>'
        )
    html.append('</table>')
    return '\n'.join(html)

def object_to_html_etable(obj, uaction, celement='edit-config-table', no_th=True):
    type_hints = getattr(obj.__class__, '__annotations__', {})
    ui_hints = getattr(obj.__class__, '_ui_hints', {})
    onsubmit = f"submitChanges('{celement}', '{uaction}')"

    fields_ordered = OrderedDict(ui_hints)

    html = [f'<div class="config-box"><div id="{celement}">']
    current_category = None

    for attr, hints in fields_ordered.items():
        if hints.get('hidden', False):
            continue

        category = hints.get('category', 'Miscellaneous')
        if category != current_category:
            if current_category is not None:
                html.append('</table>')
            html.append(f'<h3>{html_escape(category)}</h3>')
            html.append('<table border="1" class="config-table">')
            if not no_th:
                html.append('<tr><th>Name</th><th>Type</th><th>Value</th></tr>')
            current_category = category

        readonly = hints.get('readonly', False)
        active = hints.get('active')
        if callable(active):
            readonly |= not active(obj)
        display_name = hints.get('name', attr)
        description = hints.get('description', '')

        value = getattr(obj, attr, '')
        hint_type = type_hints.get(attr, type(value))
        if 'type' in hints:
            hint_type = hints['type']
        type_name = hint_type.__name__ if hasattr(hint_type, '__name__') else str(hint_type)

        escaped_name = html_escape(attr)

        disabled_attr = ' disabled' if readonly else ''

        if 'values' in hints:
            # Dropdown selector
            values = hints['values']
            if callable(values):
                values = values(obj)
            input_field = f'<select name="{escaped_name}" data-original="{html_escape(str(value))}" data-type="{type_name}"{disabled_attr}>'
            for opt_value, opt_label in values.items():
                selected = 'selected' if str(opt_value) == str(value) else ''
                input_field += f'<option value="{html_escape(str(opt_value))}" {selected}>{html_escape(opt_label)}</option>'
            input_field += '</select>'
        elif hint_type == str:
            val_str = value or ''
            escaped_val = html_escape(val_str)
            input_type = 'password' if hints.get('password', False) else 'text'
            input_field = (f'<input type="{input_type}" name="{escaped_name}" '
                           f'value="{escaped_val}" data-original="{escaped_val}"{disabled_attr}>')
        elif hint_type == int:
            val_str = str(value) if value is not None else ''
            input_field = (f'<input type="number" step="1" name="{escaped_name}" '
                           f'value="{val_str}" data-original="{val_str}"{disabled_attr}>')
        elif hint_type == float:
            val_str = str(value) if value is not None else ''
            input_field = (f'<input type="number" step="any" name="{escaped_name}" '
                           f'value="{val_str}" data-original="{val_str}"{disabled_attr}>')
        elif hint_type == bool:
            checked = 'checked ' if value else ''
            original = 'true' if value else 'false'
            input_field = (f'<input type="checkbox" name="{escaped_name}" '
                           f'{checked}data-original="{original}"{disabled_attr}>')
        else:
            input_field = html_escape(str(value))

        html.append(f'''
            <tr>
                <td title="{html_escape(description)}">{html_escape(display_name)}</td>
                <td>{html_escape(type_name)}</td>
                <td>{input_field}</td>
            </tr>
        ''')

    html.append('</table>')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html.append(f'''
        <div id="save-status" style="margin-top:10px;">
            ✅ Loaded at {timestamp}
        </div>
        <br/><button id="save-changes-btn" onclick="{onsubmit}" disabled>Save Changes</button>
    ''')
    html.append('</div></div>')

    return '\n'.join(html)

def update_with_json(obj, data):
    type_hints = getattr(obj.__class__, '__annotations__', {})

    for key, value in data.items():
        hint_type = type_hints.get(key, type(getattr(obj, key)))
        # Perform basic type casting from JSON (string) to expected type
        try:
            if hint_type == bool and type(value) is not bool:
                casted_value = bool(value)
            elif hint_type == int and type(value) is not int:
                casted_value = int(value)
            elif hint_type == str and type(value) is not str:
                casted_value = str(value)
            else:
                casted_value = value  # or add custom handling
            print(f"Setting '{key}' to '{casted_value} of {type(casted_value)}'")
            setattr(obj, key, casted_value)
        except (ValueError, TypeError) as ex:
            print(f"Error setting '{key}' to '{value}': {ex}")
    oname = obj.__class__.__name__
    print(f"Updated configuration for {oname}: {obj=}")
