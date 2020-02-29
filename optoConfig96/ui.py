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
Expose UI elements.
"""

from traits.api import *
from .custom_traits import *

from traitsui.api import *
from .editors.MPLFigureEditor import MPLFigureEditor
from .editors.bounds_editor import BoundsEditor
from .editors.color_editor import ColorEditor
from .editors.range_editor import RangeEditor
from .editors.table_editor import TableEditor

from .resources import opView as View

from .utils import error, message

from pyface.qt import QtGui

COLOR_INVALID = QtGui.QColor(*(255, 100, 100))
