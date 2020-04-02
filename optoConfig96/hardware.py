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
Settings for the optoPlate96 hardware. Currently only fan speed.
"""

from .ui import *


def truncate_entered(value):
    """
    Truncate values entered into the RangeEditor box to prevent popup of
    validation error messages.
    """
    if value < 0:
        return 0
    elif value > 255:
        return 255
    else:
        return value


class Optoplate(HasTraits):
    fan_speed = UInt8(255, tooltip='Fan speed, from 0 (off) to 255 (maximum).')

    def as_dict(self):
        return {'fan_speed': self.fan_speed}

    view = View(
        Item(
            'fan_speed',
            editor=RangeEditor(
                low=0, high=255, evaluate=truncate_entered, mode='slider'),
            style='custom'
        ),
        title='Hardware Configuration',
        kind='modal',
        buttons=OKCancelButtons
    )
