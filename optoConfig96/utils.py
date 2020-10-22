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
General utility functions.
"""

from .ui import *
from pyface.qt import QtCore, QtGui
from pyface.api import YES, NO, CANCEL

import weakref


class BackfillID():
    """
    A counter that re-assigns IDs which are no longer in use.
    """

    def __init__(self, start=0, maximum=None):
        if maximum:
            assert start <= maximum
        self.maximum = maximum
        self.used = []
        self.instances = []
        self.start = start

    def count(self):
        """
        Return the next free ID and add it to the list of used IDs.

        Raises ValueError if it would be larger than the specified maximum.
        """
        # Counter is empty: begin at start
        if not self.used:
            self.used.append(self.start)
            out = self.start
            return out

        # Counter has values: Find next free number
        for i in range(len(self.used)):
            if i + self.start != self.used[i]:
                out = i + self.start
                self.used.insert(i, out)
                return out

        # No gaps: Increment highest value, unless it exceeds the maximum
        out = self.used[-1] + 1
        if self.maximum is None or out <= self.maximum:
            self.used.append(out)
            return out
        else:
            raise ValueError('Counter reached its maximum (%d)' % self.maximum)

    def register(self, instance):
        instance.ID = self.count()
        # keep weakrefs to created instances, so the Counter does not prevent
        # garbage collection
        self.instances.append(weakref.ref(instance))

    def sequentialize(self):
        self.used = []
        for instance in self.instances:
            if instance():
                instance().ID = self.count()

    def get_instance_ref(self, ID):
        for instance in self.instances:
            if instance() and instance().ID == ID:
                return instance

        return None

    def get_instance(self, ID):
        ref = self.get_instance_ref(ID)
        if ref:
            return ref()

    def free(self, ID):
        """ Explicitly free a used ID and sequentialize instances.

        Has to be called explicity because TraitsUI keeps several
        enigmatic references to objects around, preventing garbage collection
        and deletion.
        """
        instance = self.get_instance_ref(ID)
        try:
            self.used.remove(ID)
        except ValueError:
            pass

        try:
            self.instances.remove(instance)
        except ValueError:
            pass
        self.sequentialize()


class Counted():
    """
    Class that keeps track of ID numbers assigned to its instances.
    """

    counter = None  # has to provide a BackfillID Instance as a class variable.

    def __init__(self, *args, **kwargs):
        self.counter.register(self)
        super().__init__(*args, **kwargs)

    def __del__(self):
        """ Free own ID upon garbage collection.

        Make sure `self` is still in the list of tracked instances. self.ID
        might have been reassigned, which would result in deletion of the wrong
        object.
        """
        if self.counter.get_instance(self.ID) is self:
            self.counter.free(self.ID)
        try:
            super.__del__()
        except AttributeError:
            pass


def _update_busy(fun):
    """
    Decorator to change the cursor state to busy or idle after a function call
    if necessary.
    """
    def wrapped(*args, **kwargs):
        fun(*args, **kwargs)
        if (Updateable._busycounter > 0 and not Updateable._busycursor):
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            Updateable._busycursor = True
        elif (Updateable._busycounter <= 0 and Updateable._busycursor):
            QtGui.QApplication.restoreOverrideCursor()
            Updateable._busycursor = False
    return wrapped


def toggle_busy():
    """ Temporarily pause the busy cursor. """
    if (Updateable._busycounter > 0 and Updateable._busycursor):
        QtGui.QApplication.restoreOverrideCursor()
    elif (Updateable._busycounter > 0 and not Updateable._busycursor):
        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)


class Updateable(HasTraits):
    """
    Class that can provide information about its update status.
    """
    _current_updates = Dict

    # Default update Event
    updated = Event

    _busycounter = 0
    _busycursor = False

    @_update_busy
    def start_update(self, name='updated'):
        if name not in self._current_updates.keys():
            self._current_updates[name] = 0
        self._current_updates[name] += 1
        Updateable._busycounter += 1

    @_update_busy
    def stop_update(self, name='updated', signal=True):
        self._current_updates[name] -= 1
        Updateable._busycounter -= 1
        if signal is not None:
            self.fire(name, signal)

    def fire(self, name='updated', signal=True):
        if not self.is_updating(name):
            setattr(self, name, signal)

    def is_updating(self, name='updated'):
        try:
            return self._current_updates[name] > 0
        except KeyError:
            return False


class Unit(HasTraits):
    value_base = Property(depends_on='value_base_')  # the value in base units
    value_out = Property(depends_on='value_out_, unit')  # the value converted to the display unit
    # Added in __init__
    # value_base_ = Any
    value_out_ = Float
    factors = Dict  # Dict of factors, mapping value_out to value_in. Defined in subclasses.
    unit = Enum(None)  # Enum of available units. Defined in subclasses

    view = View(
        HGroup(
            Item(
                'value_out',
                show_label=False),
            Item('unit', show_label=False)))

    def __init__(self, typ=Int):
        """Allow creation of different type-checked units."""
        super().__init__()
        self.add_trait('value_base_', typ)

    @cached_property
    def _get_value_base(self):
        return self.value_base_

    def _set_value_base(self, value):
        self.value_base_ = value
        self.value_out_ = value / self.factors[self.unit]

    @cached_property
    def _get_value_out(self):
        return self.value_out_

    def _validate_value_out(self, value):
        """ Only allow numerical input """
        try:
            value = float(value)
        except ValueError:
            raise TraitError('invalid input')
        return value

    def _set_value_out(self, value):
        # Try to set value_base_ first. If validation fails, value_out_
        # will not be set either.
        self.value_base_ = int(value * self.factors[self.unit])
        self.value_out_ = value

    @on_trait_change('unit')
    def convert(self):
        """
        When the selected unit changes, update the displayed value and keep
        the underlying base value constant.
        """
        self.value_out_ = self.value_base / self.factors[self.unit]


# Factors for converting time units to milliseconds
TIME_FACTORS = {
    'ms': 1,
    's': 1000,
    'min': 1000 * 60,
    'h': 1000 * 60 * 60,
    'd': 1000 * 60 * 60 * 24
}


class TimeUnit(Unit):
    unit = Enum('ms', 's', 'min', 'h', 'd')

    factors = TIME_FACTORS

    def _get_value_out(self):
        """
        Handle rounding of milliseconds to whole integers.
        """
        val = super()._get_value_out()
        if self.unit == 'ms':
            val = int(val)
        return val

    def _validate_value_out(self, value):
        """
        If units are milliseconds, only allow integers to be entered.
        """
        value = super()._validate_value_out(value)
        if (self.unit == 'ms' and not value.is_integer()):
            raise TraitError('milliseconds must be whole integers')
        return value


class Popup(HasTraits):
    message = Str
    title = Str('Error!')

    def default_traits_view(self):
        view = View(
            HGroup(
                UItem('10'),
                UItem('message', style='readonly'),
                UItem('10')),
            buttons=[OKButton],
            kind='modal',
            title=self.title)
        return view


def error(message, title=None):
    if title is not None:
        title = 'Error: ' + title
    else:
        title = 'Error'
    ui = Popup(message=message, title=title).edit_traits()
    return ui.result


def message(message, title):
    ui = Popup(message=message, title=title).edit_traits()
    return ui.result


class ConfirmationDialogHandler(Handler):

    def yes(self, info):
        info.object.result = YES
        info.ui.dispose()

    def always(self, info):
        info.object.result = YES
        info.object.dontshowagain = True
        info.ui.dispose()

    def no(self, info):
        info.object.result = NO
        info.ui.dispose()

    def cancel(self, info):
        info.object.result = CANCEL
        info.ui.dispose()


class ConfirmationDialog(HasTraits):
    """
    Present a confirmation dialog with a custom message to the user.

    The user has the option to not show instances of the same dialog in the
    future.
    """
    dontshowagain = Bool(False)

    message = Str

    result = Enum(None, YES, NO, CANCEL)

    view = View(
        HGroup(
            UItem('10'),
            UItem('message', style='readonly'),
            UItem('10')),
        buttons=[
            Action(name='Yes', action='yes'),
            Action(name='Yes, do not ask again', action='always'),
            Action(name='No', action='no'),
            Action(name='Cancel ', action='cancel')],
        kind='livemodal',  # must be livemodal to update `result`
        handler=ConfirmationDialogHandler,
        title='Continue?')

    def __call__(self, message, parent=None):
        if self.dontshowagain:
            return YES
        else:
            self.message = message
            # Temporarily disable the busy cursor
            toggle_busy()
            self.edit_traits(parent=parent)
            toggle_busy()
            return self.result


def blend_colors(colors):
    """
    Blend multiple colors.

    Parameters
    ----------
    colors : list of tuples
        Each element is expected to contain a 3- or 4-element tuple (R,G,B,[A])

    Returns
    -------
    color : tuple
        (R,G,B,[A]) tuple of blended color
    """

    # Check if an alpha channel exists
    colors_ = colors
    if not len(colors[0]) == 4:
        colors_ = [color + (255,) for color in colors]

    rgba = list(zip(*colors_))
    r, g, b, a = [round(sum(x) / len(colors)) for x in rgba]

    return (r, g, b, a)


def qt_color_to_rgb(color):
    """
    Convert a Qt color to an RGB(A) tuple in the 0-1 range.
    """
    return [1 / 255 * v for v in color.getRgb()]


def idx2well(idx, n_rows=8, n_cols=12):
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    row = letters[int(idx / n_cols)]
    col = (idx % n_cols) + 1
    return "%s%d" % (row, col)


def ensure_iterable(potential_sequence):
    """
    Return `potential_sequence` as an iterable tuple or list, but not as a string.

    Parameters
    ----------
    potential_sequence : iterable

    Returns
    -------
    sequence : tuple or list
    """
    if isinstance(potential_sequence, (tuple, list)):
        return potential_sequence
    else:
        return [potential_sequence]
