# ------------------------------------------------------------------------------
# Copyright (c) 2020 Oliver Thomas

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------


"""
Utilities to handle the configuration file.
"""

from .ui import *
import os
import sys
import json


class Options(HasTraits):
    arduino_path = File(label='Path to Arduino IDE')

    def _arduino_path_default(self):
        if sys.platform == 'linux':
            return 'arduino'
        if sys.platform == 'darwin':
            return os.path.join(os.sep, 'Applications', 'Arduino.app')
        if sys.platform == 'win32':
            return os.path.join('C:', os.sep, 'Program Files (x86)', 'Arduino', 'arduino_debug.exe')

    changed = Event

    @on_trait_change('+')
    def _fire_changed(self):
        self.changed = True

    view = View(
        VGroup(
            Item('arduino_path', editor=FileEditor(dialog_style='open')),
        ),
        kind='modal',
        title='Preferences',
        buttons=OKCancelButtons)

    def to_dict(self):
        d = {}
        for attr in ('arduino_path',):
            d[attr] = getattr(self, attr)
        return d


class Config(HasTraits):

    options = Instance(Options, ())
    path = Str

    _cannotwriteinformed = Bool(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init()

    def init(self):
        if not self.path:
            self.path = os.path.join(os.path.expanduser('~'), 'optoPlate96')
        if not os.path.exists(self.path):
            self.create_cfg_path()

        self.cfg_file = os.path.join(self.path, 'op96_config.cfg')
        if os.path.exists(self.cfg_file):
            self.options = self.read_cfg()
        else:
            self.write_cfg()

    def __getitem__(self, key):
        return getattr(self.options, key)

    def __setitem__(self, key, value):
        setattr(self.options, key, value)

    def create_cfg_path(self):
        """
        Try to create a configuration directory at `self.path`.

        Returns
        -------
        success : bool
            True if the directory was created successfully, False otherwise.
        """
        try:
            os.makedirs(self.path)
            message(
                message='Configuration files will be saved in %s.' % self.path,
                title='Configuration paths')
            return True
        except PermissionError:
            error(
                message='Could not create configuration directory at %s.' % self.path)
        return False

    def read_cfg(self):
        try:
            with open(self.cfg_file, 'r') as cfg_file:
                cfg = Options(**json.load(cfg_file))
        except Exception:
            error(
                message='Could not read configuration file.')
            cfg = Options()
        return cfg

    @on_trait_change('options.changed')
    def write_cfg(self):
        try:
            with open(self.cfg_file, 'w') as cfg_file:
                cfg_file.write(json.dumps(self.options.to_dict()))
        except Exception:
            if not self._cannotwriteinformed:
                error('Could not write configuration file at %s.' % self.cfg_file)
                self._cannotwriteinformed = True


op96Config = Config()
