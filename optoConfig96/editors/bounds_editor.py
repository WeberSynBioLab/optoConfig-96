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

    # This file incorporates work covered by the following copyright and
    # permission notice:

    # Copyright (c) 2005, Enthought, Inc.
    # All rights reserved.

    # This software is provided without warranty under the terms of the BSD
    # license included in enthought/LICENSE.txt and may be redistributed only
    # under the conditions described in the aforementioned license.  The license
    # is also available online at http://www.enthought.com/licenses/BSD.txt

    # Thanks for using Enthought open source!

# ------------------------------------------------------------------------------


"""
Re-Implementation of traitsui.qt4.extra.bounds_editor to provide extra
validation: min and max cannot be exceeded by entering values in the text box
Furthermore, this suffers from the same limitation as the range editor:
Entering commas treats the value as tuple, not a decimal number, which
raises an unhandled TypeError - fixed here.
"""

import six

from traitsui.qt4.extra.bounds_editor import _BoundsEditor as _OriginalBoundsEditor
from traitsui.qt4.extra.bounds_editor import BoundsEditor as OriginalBoundsEditor


class _BoundsEditor(_OriginalBoundsEditor):
    def update_low_on_enter(self):
        try:
            text = self._label_lo.text().replace(',', '.')
            self._label_lo.setText(text)
            low = eval(six.text_type(self._label_lo.text()).strip())
            if low < self.min:
                self._label_lo.setText(str(self.min))
        except:
            pass
        super().update_low_on_enter()

    def update_high_on_enter(self):
        try:
            text = self._label_hi.text().replace(',', '.')
            self._label_hi.setText(text)
            high = eval(six.text_type(self._label_hi.text()).strip())
            if high > self.max:
                self._label_hi.setText(str(self.max))
        except:
            pass
        super().update_high_on_enter()


class BoundsEditor(OriginalBoundsEditor):
    def _get_simple_editor_class(self):
        return _BoundsEditor

    def _get_custom_editor_class(self):
        return _BoundsEditor
