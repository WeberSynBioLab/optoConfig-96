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

#   This file incorporates work covered by the following copyright and
#   permission notice:

#   Copyright (c) 2005, Enthought, Inc.
#   All rights reserved.

#   This software is provided without warranty under the terms of the BSD
#   license included in enthought/LICENSE.txt and may be redistributed only
#   under the conditions described in the aforementioned license.  The license
#   is also available online at http://www.enthought.com/licenses/BSD.txt

#   Thanks for using Enthought open source!

# ------------------------------------------------------------------------------


from traitsui.qt4.table_editor import TableView as OriginalTableViewQt
from traitsui.qt4.table_model import TableModel as OriginalTableModelQt
from traitsui.api import TableEditor as OriginalTableEditor

from pyface.qt import QtCore, QtGui

is_qt5 = QtCore.__version_info__ >= (5,)

if is_qt5:
    def set_qheader_section_resize_mode(header):
        return header.setSectionResizeMode
else:
    def set_qheader_section_resize_mode(header):
        return header.setResizeMode


class TableViewQt(OriginalTableViewQt):
    """
    Modifications to the Qt Table Editor implemented by TraitsUI.
    """

    def _update_header_sizing(self):
        """
        Identical to the original version, except it respects the show_row_labels
        flag even if the remaining conditions would cause it to be shown in the
        default implementation.
        """

        """ Header section sizing can be done only after a valid model is set.
        Otherwise results in segfault with Qt5.
        """
        editor = self._editor
        factory = editor.factory
        # Configure the row headings.
        vheader = self.verticalHeader()
        set_resize_mode = set_qheader_section_resize_mode(vheader)
        insertable = factory.row_factory is not None
        if ((factory.editable and (insertable or factory.deletable)) or
                factory.reorderable):
            vheader.installEventFilter(self)
            set_resize_mode(QtGui.QHeaderView.ResizeToContents)
        if not factory.show_row_labels:  # modified!
            vheader.hide()
        if factory.row_height > 0:
            vheader.setDefaultSectionSize(factory.row_height)
        self.setAlternatingRowColors(factory.alternate_bg_color)
        self.setHorizontalScrollMode(QtGui.QAbstractItemView.ScrollPerPixel)
        # Configure the column headings.
        # We detect if there are any stretchy sections at all; if not, then
        # we make the last non-fixed-size column stretchy.
        hheader = self.horizontalHeader()
        set_resize_mode = set_qheader_section_resize_mode(hheader)
        resize_mode_map = dict(
            interactive=QtGui.QHeaderView.Interactive,
            fixed=QtGui.QHeaderView.Fixed,
            stretch=QtGui.QHeaderView.Stretch,
            resize_to_contents=QtGui.QHeaderView.ResizeToContents,
        )
        stretchable_columns = []
        for i, column in enumerate(editor.columns):
            set_resize_mode(i, resize_mode_map[column.resize_mode])
            if column.resize_mode in ("stretch", "interactive"):
                stretchable_columns.append(i)
        if not stretchable_columns:
            # Use the behavior from before the "resize_mode" trait was added
            # to TableColumn
            hheader.setStretchLastSection(True)
        else:
            # hheader.setSectionResizeMode(
            #     stretchable_columns[-1], QtGui.QHeaderView.Stretch)
            hheader.setStretchLastSection(False)
        if factory.show_column_labels:
            hheader.setHighlightSections(False)
        else:
            hheader.hide()


class TableModelQt(OriginalTableModelQt):
    """
    Modifications to the Qt Table Model implemented by TraitsUI.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def moveRows(self, current_rows, new_row):
        """
        Identical to the original version, except it does not remove the row
        when the last remaining row is dragged to the empty space in the bottom
        of the table.
        """
        """Moves a sequence of rows (provided as a list of row indexes) to a new
        row."""

        # Sort rows in descending order so they can be removed without
        # invalidating the indices.
        current_rows.sort()
        current_rows.reverse()

        # If the the highest selected row is lower than the destination, do an
        # insertion before rather than after the destination.
        if current_rows[-1] < new_row:
            new_row += 1

        # Remove selected rows...
        items = self._editor.items()
        objects = []
        for row in current_rows:
            if row <= new_row and new_row >= 1:  # < new_row >= 1 is the bugfix
                new_row -= 1
            objects.insert(0, items[row])
            self.removeRow(row)

        # ...and add them at the new location.
        for i, obj in enumerate(objects):
            self.insertRow(new_row + i, obj=obj)

        # Update the selection for the new location.
        self._editor.set_selection(objects)


class TableEditor(OriginalTableEditor):
    table_view_factory = TableViewQt
    source_model_factory = TableModelQt
