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

from os.path import expanduser, join as path_join
from os import makedirs
from secrets import token_hex
from hashlib import sha256
from flask_login import UserMixin

AUTH_DIR = expanduser(f'~/.sippy')
AUTH_FILE = lambda app_name: path_join(AUTH_DIR, f'{app_name.replace(" ", "_").lower()}.auth')

class User(UserMixin):
    def __init__(self, username):
        self.id = username

class Auth:
    def __init__(self, app_name, salt, hashed):
        self.app_name = app_name
        self.salt = salt
        self.hashed = hashed

    def save(self):
        makedirs(AUTH_DIR, exist_ok=True)
        with open(AUTH_FILE(self.app_name), 'w') as f:
            f.write(f"{self.salt}:{self.hashed}\n")

    def verify(self, username, password):
        return self.hashed == sha256(f"{username}:{self.salt}:{password}".encode()).hexdigest()

    @classmethod
    def create(cls, app_name, username, password):
        salt = token_hex(16)
        pwd_hash = sha256(f"{username}:{salt}:{password}".encode()).hexdigest()
        return cls(app_name, salt, pwd_hash)

    @classmethod
    def load(cls, app_name):
        try:
            with open(AUTH_FILE(app_name)) as f:
                salt, hashed = f.read().strip().split(':', 1)
                return cls(app_name, salt, hashed)
        except FileNotFoundError:
            return None
