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
Application and entry point for the optoPlate96 GUI.
"""
from traits.etsconfig.api import ETSConfig
ETSConfig.toolkit = 'qt4'

from optoConfig96.application import Application
from optoConfig96.plates import PlateConfig

def main():
    app = Application()
    # When opening the application, the user selects the plate configuration
    # for the first time. No programs are assigned, and asking whether
    # resetting them is okay is not required.
    config = PlateConfig()
    config._no_redraw_confirm = True
    result = config.edit_traits().result
    config._no_redraw_confirm = False
    app.plate.config = config
    if result:
        app.configure_traits()
    return app


if __name__ == '__main__':
    app = main()
