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
Fix a bug with the TraitsUI RangeEditor, which results in a crash when numbers
are entered with a comma as a decimal separator.
This is treated as a tuple and falls through the default RangeEditor's input
checks.
Also provides extra validation: max cannot be exceeded by entering values in the
text box.
"""
import six

from traitsui.api import RangeEditor as OriginalRangeEditor
from traitsui.qt4.range_editor import SimpleSliderEditor


class FixedQtRangeEditor(SimpleSliderEditor):
    def update_object_on_enter(self):
        """ Overloaded for further error handling.
        """
        try:
            text = self.control.text.text().replace(',', '.')
            self.control.text.setText(text)
            value = eval(six.text_type(self.control.text.text()).strip())
            if value > self.high:
                self.control.text.setText(str(self.high))
        except Exception:
            pass
        super().update_object_on_enter()


class RangeEditor(OriginalRangeEditor):
    def _get_simple_editor_class(self):
        return FixedQtRangeEditor

    def _get_custom_editor_class(self):
        return FixedQtRangeEditor
