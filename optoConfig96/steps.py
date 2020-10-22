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
Define components to handle steps for the optoPlate96 GUI.
"""

from .ui import *

from traitsui.menu import Menu, Action
from traitsui.table_column import ObjectColumn

import numpy as np

from .plots import StepPlot
from . import utils
from .constants import MAX_STEP_DURATION


StepDeleteWarning = utils.ConfirmationDialog()
StepDeleteAllWarning = utils.ConfirmationDialog()


class StepHandler(Handler):
    """ Handler for the Step view. """

    def object_pulse_on_changed(self, info):
        """
        Sync the invalid flag of the pulse_on editor with the Step's
        pulse_on_invalid flag.
        """
        info.pulse_on_ui._ui._editors[0].invalid = info.object.pulse_on_invalid

    def object_duration_changed(self, info):
        info.pulse_on_ui._ui._editors[0].invalid = info.object.pulse_on_invalid
        info.duration_ui._ui._editors[0].invalid = info.object.duration_short_invalid or info.object.duration_long_invalid


class AStep(utils.Updateable):
    """ Base class for a Step-like object. """

    # Event to indicate any parameter changes
    dirtied = Event

    # Core parameters for definition of a Step
    _core_params = (
            'intensity',
            'duration', 'duration_unit',
            'is_pulsed',
            'pulse_on', 'pulse_on_unit',
            'pulse_off', 'pulse_off_unit')

    # Parameters which set the dirty flag, in addition to the _core_params
    _dirty_params = (
            'color',
            'name'
        )

    def __setattr__(self, name, value):
        if name in self._core_params or name in self._dirty_params:
            super().__setattr__('dirtied', True)
        super().__setattr__(name, value)

    # Event to indicate that the size requirement on the Arduino changed.
    size_update = Event

    @on_trait_change('intensity, duration, is_pulsed, pulse_on, pulse_off')
    def fire_size_update(self):
        self.size_update = True


class BaseStep(AStep):
    """
    Uncounted Steps without a counter and no logic for plot calculations.
    Only allows setting parameters.
    """

    name = Str('Step')

    # Parameters of the Step
    duration = UInt32Div100  # milliseconds
    pulse_on = UInt32Div100  # milliseconds
    pulse_off = UInt32Div100  # milliseconds
    intensity = UInt12(tooltip='Intensity from 0 (off) to 4095 (maximum intensity).')  # arbitrary units from 0-4095
    is_pulsed = Bool(False, label='Pulsed')

    # Values for the user interface, with unit conversion. The 'ground truth'
    # value is stored as milliseconds in the variables defined above.
    duration_ui = Instance(utils.TimeUnit, args=(UInt32Div100,))
    pulse_on_ui = Instance(utils.TimeUnit, args=(UInt32Div100,))
    pulse_off_ui = Instance(utils.TimeUnit, args=(UInt32Div100,))

    def _sync_internals(self):
        """ Hook up internal traits to display traits. """
        self.sync_trait('duration', self.duration_ui, 'value_base')
        self.sync_trait('pulse_on', self.pulse_on_ui, 'value_base')
        self.sync_trait('pulse_off', self.pulse_off_ui, 'value_base')

        # The units traits do not really have to be synced. However, if they are
        # not, a change of the unit in the step editor is not immediately
        # reflected in the all_steps table. Syncing solves this issue.
        for to_sync in ('pulse_on', 'pulse_off', 'duration'):
            self.add_trait(to_sync + '_unit', Any)
            target = getattr(self, to_sync + '_ui')
            target.sync_trait('unit', self, to_sync + '_unit')

    def copy_params(self, to):
        """ Copy one step's parameters to another step. """
        for param in (self._core_params):
                setattr(to, param, getattr(self, param))

    # Input validation
    invalid = Property
    pulse_on_invalid = Property
    duration_long_invalid = Property
    duration_short_invalid = Property

    def _get_invalid(self):
        """ Is this Step definition invalid? """
        return self.pulse_on_invalid or self.duration_long_invalid or self.duration_short_invalid

    def _get_pulse_on_invalid(self):
        """
        The pulse ON duration should be lower than or equal to the Step duration.
        """
        return self.is_pulsed and self.duration < self.pulse_on

    def _get_duration_long_invalid(self):
        """ Step duration cannot exceed the maximum allowed duration.
        """
        return self.duration > MAX_STEP_DURATION

    def _get_duration_short_invalid(self):
        return self.duration < 100

    def invalid_reasons(self):
        if not self.invalid:
            return None
        else:
            reasons = []
            if self.pulse_on_invalid:
                reasons.append('Pulse ON duration cannot exceed Step duration.')
            if self.duration_long_invalid:
                reasons.append('Step duration is too long (%d ms, maximum is %d ms).' % (self.duration, MAX_STEP_DURATION))
            if self.duration_short_invalid:
                reasons.append('Step duration must be at least 100 ms.')

        return '\n'.join(reasons)

    # Conversion factors from arbitrary units to physical units, if available.
    conversion_factors = Dict()

    units = Dict()

    converted_units = Property(depends_on='intensity, conversion_factors, units')

    @cached_property
    def _get_converted_units(self):
        units = []
        for led, factor in self.conversion_factors.items():
            try:
                value = self.intensity / factor
                unit = self.units[led]
                value = '%.1f %s' % (value, unit)
            except (TypeError, KeyError):
                value = 'NA'
            text = '{name}: {value}'.format(name=led, value=value)
            units.append(text)
        return '\n'.join(units)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sync_internals()

    def default_traits_view(self):
        view = View(
            Item(
                'duration_ui',
                editor=InstanceEditor(),
                style='custom',
                label='Duration'),
            Item(
                'intensity',
                editor=RangeEditor(low=0, high=4095),
                style='custom',
                label='Intensity'),
            Group(UItem(
                'converted_units',
                style='readonly',
                tooltip='Intensity converted to physical units. Set the conversion factor in the plate configuration.')),
            HGroup(
                VGroup(
                    Item(' '),
                    Item('is_pulsed')),
                VGroup(
                    Item(
                        'pulse_on_ui',
                        editor=InstanceEditor(),
                        style='custom',
                        enabled_when='is_pulsed',
                        label='ON'),
                    Item(
                        'pulse_off_ui',
                        editor=InstanceEditor(),
                        style='custom',
                        enabled_when='is_pulsed',
                        label='OFF'))),
            handler=StepHandler(),
            kind='modal',
            buttons=OKCancelButtons)
        return view

    no_pulsed_view = View(
        Item(
            'duration_ui',
            editor=InstanceEditor(),
            style='custom',
            label='Duration'),
        Item(
            'intensity',
            editor=RangeEditor(low=0, high=4095),
            style='custom',
            label='Intensity'),
        Group(UItem(
            'converted_units',
            style='readonly',
            tooltip='Intensity converted to physical units. Set the conversion factor in the plate configuration.')),
        VGroup(
            Item(
                'pulse_on_ui',
                editor=InstanceEditor(),
                style='custom',
                label='Pulse ON'),
            Item(
                'pulse_off_ui',
                editor=InstanceEditor(),
                style='custom',
                label='Pulse OFF')),
        handler=StepHandler())


class Step(utils.Counted, BaseStep):
    """ A Step for an optoPlate96 Program.

    A Step is a part of a program. Each Step can be used in multiple Programs.
    Steps are defined by their:
        * Duration: How long does the Step last?
        * Pulsing behaviour: Does the Step pulse between an on and off state?
        * Pulse ON duration: Duration of the ON phase in each pulsing cycle.
        * Pulse OFF duration: Duration of the OFF phase in each pulsing cycle.
        * Intensity: The LED intensity during the ON phase. During the OFF
            phase, the intensity is 0.
    """

    # Class variable. Count created instances and assign an ID.
    # ID 0 is reserved for the nullstep.
    counter = utils.BackfillID(start=1)

    # --------------------------------------------------------------------------
    # Trait Definitions
    # --------------------------------------------------------------------------

    # Name for information and organization purposes.
    # Steps are uniquely identified by their ID (via `counter`).
    name = Str

    def _name_default(self):
        return "Step%03d" % self.ID

    # Programs this Step is assigned to.
    in_programs = List([])  # TODO: Clean solution to circular dependencies

    # Is this step used in the final Arduino Code?
    is_used = Property

    def _get_is_used(self):
        for program in self.in_programs:
            if program.is_used:
                return True
        return False

    # Display settings
    # show as pulsed, or constant?
    # Very long steps with pulsing may be visually cluttered.
    show_pulsed = Bool(True)
    _show_pulsed = Property(depends_on='is_pulsed, show_pulsed')

    @cached_property
    def _get__show_pulsed(self):
        pulsed = self.show_pulsed and self.is_pulsed
        return pulsed

    cycles = Property(depends_on='duration, is_pulsed, pulse_on, pulse_off')

    @cached_property
    def _get_cycles(self):
        if not self.is_pulsed:
            return 1
        else:
            try:
                return self.duration / (self.pulse_on + self.pulse_off)
            except ZeroDivisionError:
                return 0

    # Color for plotting. Set in __init__ because default is not picked up by
    # the editor when set here.
    color = Color
    _color = Property

    def _get__color(self):
        return utils.qt_color_to_rgb(self.color)

    # Event to fire when the plot needs updating.
    plot_update = Event

    # --------------------------------------------------------------------------
    # View
    # --------------------------------------------------------------------------

    def default_traits_view(self):
        view = View(
            Item('name'),
            Item(
                'duration_ui',
                editor=InstanceEditor(),
                style='custom',
                label='Duration'),
            Item(
                'intensity',
                editor=RangeEditor(low=0, high=4095),
                style='custom',
                label='Intensity'),
            Group(UItem(
                'converted_units',
                style='readonly',
                tooltip='Intensity converted to physical units. Set the conversion factor in the plate configuration.')),
            HGroup(
                VGroup(
                    Item(' '),
                    Item('is_pulsed')),
                VGroup(
                    Item(
                        'pulse_on_ui',
                        editor=InstanceEditor(),
                        style='custom',
                        enabled_when='is_pulsed',
                        label='ON'),
                    Item(
                        'pulse_off_ui',
                        editor=InstanceEditor(),
                        style='custom',
                        enabled_when='is_pulsed',
                        label='OFF'))),
            handler=StepHandler())
        return view

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = tuple(np.random.randint(0, 256, 3))

    def __repr__(self):
        string = 'Step #{ID} ({name}) '
        string += 'Dur: {duration}, ON: {pulse_on}, OFF: {pulse_off}, INT: {intensity}'
        return string.format(
            ID=self.ID,
            duration=self.duration,
            pulse_on=self.pulse_on,
            pulse_off=self.pulse_off,
            intensity=self.intensity)

    def as_dict(self):
        """ Representation for dumping to JSON """
        d = {}
        for key in (
            'ID',
            'name',
            'color',
            'duration',
            'duration_unit',
            'intensity',
            'is_pulsed',
            'pulse_on',
            'pulse_on_unit',
            'pulse_off',
            'pulse_off_unit'):
                if key == 'color':
                    d[key] = self.color.name()
                else:
                    d[key] = getattr(self, key)
        return d

    xs = Property(depends_on='plot_update')

    @cached_property
    def _get_xs(self):
        return self.get_xs()

    def get_xs(self, pulsed=None):
        """ Return X values for plotting the Step (milliseconds).

        Parameters:
        -----------
        pulsed : bool or None
            Should pulsing be considered? If False, the intensity is plotted as
            constant. If None, figure out automatically whether to plot the
            Step with pulsing or not.

        Returns
        -------
        xs : ndarray of X values
        """
        if pulsed is None:
            pulsed = self._show_pulsed

        if not pulsed:
            # Step is not pulsed, or pulse duration was not specified.
            return np.array((0, self.duration))
        else:
            # Step is pulsed, and is displayed as pulsed.
            return self._xs_pulsed

    _xs_pulsed = Property(depends_on='duration, is_pulsed, pulse_on, pulse_off')

    @cached_property
    def _get__xs_pulsed(self):
        if not self.is_pulsed or self.pulse_on == 0 or self.pulse_off == 0 or self.duration == 0:
            return np.array((0, self.duration))
        else:
            xs = [0]
            on = False  # LED is initially off.

            while xs[-1] < self.duration:
                if not on:
                    nxt = xs[-1] + self.pulse_on
                if on:
                    nxt = xs[-1] + self.pulse_off
                xs.append(min(nxt, self.duration))
                on = not on  # swap state
        return np.array(xs)

    ys = Property(depends_on='plot_update')

    @cached_property
    def _get_ys(self):
        return self.get_ys()

    def get_ys(self, pulsed=None):
        """ Return Y values for plotting the Step (arbitrary units).

        Parameters
        ----------
        pulsed : bool or None
            Should pulsing be considered? If False, the intensity is plotted as
            constant. If None, figure out automatically whether to plot the
            Step with pulsing or not.

        Returns
        -------
        ys : ndarray of Y values
        """
        if pulsed is None:
            pulsed = self._show_pulsed

        if not pulsed:
            # Step is not shown as pulsed
            # Delegate to handle edge cases
            xs = self.get_xs(pulsed)
            ys = np.zeros_like(xs)
            ys[self.is_on(xs)] = self.intensity
            return ys
        else:
            # Step is shown as pulsed
            return self._ys_pulsed

    _ys_pulsed = Property(depends_on='duration, pulse_on, pulse_off, intensity')

    @cached_property
    def _get__ys_pulsed(self):
        xs = self._xs_pulsed
        ys = np.zeros_like(xs)
        ys[self.is_on(xs)] = self.intensity

        return ys

    def is_on(self, times):
        """Return if the Step is ON at `times`.

        Assumes the Step starts at time 0.
        Used to define y values of the Step plot.

        Parameters
        ----------
        times : ndarray
            The times to check.

        Returns
        -------
        is_on : ndarray (dtype bool)
            True for elements of `times` which are in the ON phase.
        """
        # Edge cases:
        if not self.is_pulsed:
            return np.ones_like(times).astype(np.bool)

        if self.pulse_on == 0 and self.pulse_off == 0:
            # ON is 0 and OFF is 0: not pulsed, always on
            return np.ones_like(times).astype(np.bool)
        elif self.pulse_on == 0 and self.pulse_off > 0:
            # Only ON is 0: always off
            return np.zeros_like(times).astype(np.bool)
        elif self.pulse_off == 0 and self.pulse_on > 0:
            # Only OFF is 0: always on
            return np.ones_like(times).astype(np.bool)

        period = self.pulse_on + self.pulse_off
        cycles = (times / period).astype(np.int)
        is_on = times < period * cycles + self.pulse_on
        # If the step is switching at the end of its duration, do not show this:
        # the next step will start
        if is_on.shape[0] > 1:
            if is_on[-2] != is_on[-1]:
                is_on[-1] = is_on[-2]

        return is_on

    @on_trait_change('name, duration, intensity, show_pulsed, is_pulsed, pulse_on, pulse_off, color')
    def fire_plot_update(self, obj, name, old, new):
        signal = (self.ID, name)
        self.fire('plot_update', signal)

    def delete(self):
        """
        Delete an existing Step and remove it from all its associated programs.
        """
        assigned_programs = [program for program in self.in_programs]
        for program in assigned_programs:
            program.delete_step(self)
        self.counter.free(self.ID)

    def duplicate(self):
        """
        Return copy of the Step with the same parameters.
        """
        dup = Step()
        self.copy_params(dup)
        dup.name = "Copy of %s" % self.name
        return dup


class _Nullstep(Step):
    counter = utils.BackfillID(start=0, maximum=0)


nullstep = _Nullstep(name='nullstep')


class AStepEditor(HasTraits):
    """ Base class for Step Editors. """


class StepEditor(AStepEditor):
    """ Allows editing of Step parameters and displays a live plot. """

    # --------------------------------------------------------------------------
    # Trait Definitions
    # --------------------------------------------------------------------------

    # The Step to edit.
    step = Instance(AStep)

    plot = Instance(StepPlot, ())

    # --------------------------------------------------------------------------
    # View
    # --------------------------------------------------------------------------

    view = View(
        VSplit(
            UItem('object.plot.figure', editor=MPLFigureEditor(), height=300),
            VGroup(
                VGroup(
                    HGroup(UItem('plot', editor=InstanceEditor(), style='custom')),
                    HGroup(Item('object.step.show_pulsed'), Item('object.step.color', editor=ColorEditor())),
                    show_border=True, label='Display Settings')
            ),
            UItem('step', editor=InstanceEditor(), style='custom')
        ),
        resizable=True, scrollable=True
    )

    @on_trait_change('step.plot_update')
    def update_figure(self):
        self._update_figure()

    def _update_figure(self):
        self.plot._is_updating = True
        self.plot.set_xydata(self.step.xs, self.step.ys)
        self.plot.lines[0].set_color(self.step._color)
        self.plot.axes.set_title(self.step.name)
        self.plot.draw()


class NoStepEditor(AStepEditor):
    """ Empty Step Editor to display when no Step is available. """
    step = None
    view = View(Label('Create or select a Step to show the editor.'))


class StepColumn(ObjectColumn):
    """ Defines a column of the StepList table. """

    read_only_cell_color = Color(0xCCCCCC)

    def get_cell_color(self, object):
        # Mark invalid rows
        if object.invalid:
            return COLOR_INVALID
        return super().get_cell_color(object)

    def get_value(self, object):
        if self.name == 'in_programs':
            return ", ".join([prg.name for prg in object.in_programs]) or 'None'

        if self.name in ('is_pulsed', 'invalid'):
            return ['No', 'Yes'][getattr(object, self.name)]

        if 'value_out' in self.name:
            attr = self.name.split('.')
            obj = getattr(object, attr[0])
            value = getattr(obj, 'value_out')
            unit = getattr(obj, 'unit')
            return '%d %s' % (value, unit)

        return super().get_value(object)

    def get_raw_value(self, object):
        if 'value_out' in self.name:
            attr = self.name.split('.')[0]
            attr = attr.replace('_ui', '')
            return getattr(object, attr)

        if self.name == 'in_programs':
            return [prg.name for prg in getattr(object, 'in_programs')]

        return super().get_raw_value(object)

    def is_editable(self, object):
        if self.name in ('pulse_on_ui.value_out', 'pulse_off_ui.value_out'):
            return object.is_pulsed

        if self.name in ('ID', 'in_programs', 'invalid'):
            return False

        return True

    def get_tooltip(self, object):
        return object.invalid_reasons()


steplist_editor = TableEditor(
    columns=[
        StepColumn(name='ID', label='ID'),
        StepColumn(name='name', label='Name'),
        StepColumn(name='duration_ui.value_out', label='Dur'),
        StepColumn(name='intensity', label='Int'),
        StepColumn(name='is_pulsed', label='Pls'),
        StepColumn(name='pulse_on_ui.value_out', label='ON'),
        StepColumn(name='pulse_off_ui.value_out', label='OFF'),
        StepColumn(name='in_programs', label='Prgs'),
        StepColumn(name='invalid', label='Invalid')
    ],
    deletable=False,  # Steps need to un-assign themselves from programs. FIXME: breaks reorderable
    reorderable=True,
    sortable=True,
    row_factory=Step,
    selection_mode='rows',
    selected='selected',
    edit_on_first_click=False,
    editable=True,
    show_row_labels=False
)


class StepListHandler(Controller):
    """ Handler for the StepList. """

    # Provided by main application handler at runtime
    app = Any

    def init(self, info):
        self.app = info.object.app
        return True

    @on_trait_change('app:plate.config+, app:all_steps.updated, app.current_step')
    def update_step_config(self):
        """
        Provide steps with information about the current plate configuration, in
        particular conversion factors for physical units.
        """
        for step in self.info.object.steps:
            self.app.plate.config.conversion_factors
            step.conversion_factors = self.app.plate.config.conversion_factors
            step.units = self.app.plate.config.units

    def populate_rightclick_menu(self, info):
        """
        Populate the right-click menu with options to add and delete Steps, and
        to assign Steps to available programs.

        Called from the main application handler.
        """
        assign_items = []
        assign_items.append(Action(
            name='New Program',
            action='handler.assign(info, to_program="new")'))
        for program in sorted(self.app.all_programs.programs, key=lambda prg: prg.name):
            assign_items.append(Action(
                name=program.name,
                action='handler.assign(info, to_program=%d)' % program.ID))

        menu = Menu(
            Action(name='New Step', action='info.object.new_step()'),
            Action(name='Delete Selected', action='handler.object_delete_changed(info)'),
            Action(name='Duplicate Selected', action='handler.object_duplicate_changed(info)'),
            Action(name='Set Parameters for All Selected ...', action='handler.set_all(info)'),
            Action(name='Interpolate ...', action='handler.interpolate(info)'),
            Menu(*assign_items, name="Assign Selected to Program ..."))
        for column in info.steps.columns:
            column.menu = menu

    def object_delete_changed(self, info):
        """ Remove selected steps from Steps list. """
        steps_to_delete = []
        for step in info.object.selected:
            confirm = self.confirm_delete(step)
            if confirm == utils.YES:
                steps_to_delete.append(step)
            elif confirm == utils.CANCEL:
                break
        info.object.delete_steps(steps_to_delete)

    def object_delete_all_changed(self, info):
        if self.confirm_delete_all() == utils.YES:
            info.object.delete_all_steps()

    def object_new_changed(self, info):
        info.object.new_step()

    def object_duplicate_changed(self, info):
        new_steps = [step.duplicate() for step in info.object.selected]
        info.object.start_update('updated')
        info.object.add_steps(new_steps)
        info.object.stop_update('updated')

    def confirm_delete(self, step):
        """
        Ask the user to confirm Step deletion if the Step is part of a Program.
        """
        isin = ['  * ' + program.name for program in step.in_programs]
        if isin:
            if len(isin) < 10:
                msg = "The Step '{step}' is assigned to the following Programs:\n"
                msg += '\n'.join(isin)
            else:
                msg = "The Step '{step}' as assigned to {n} programs.\n"
            msg += "\nAre you sure you want to delete Step '{step}'?"
            msg = msg.format(step=step.name, n=len(isin))
            confirm = StepDeleteWarning(message=msg)
        else:
            confirm = utils.YES

        return confirm

    def confirm_delete_all(self):
        """
        Ask the user to confirm deletion of all steps.
        """
        msg = 'Do you really want to delete ALL steps?'
        confirm = StepDeleteAllWarning(message=msg)
        return confirm

    def assign(self, info, to_program):
        """Assign selected Steps to a Program.

        Parameters
        ----------
        to_program : int
            ID of the program to assign to.
        """
        if to_program == 'new':
            from .programs import Program
            prg = Program()
            to_program = prg.ID
            from .assistants import NameProgramAssistant
            assistant = NameProgramAssistant()
            assistant.name = prg.name
            result = assistant.edit_traits().result
            if not result:
                return
            else:
                prg.name = assistant.name
                self.app.all_programs.add_program(prg)

        for program in self.app.all_programs.programs:
            if program.ID == to_program:
                program.add_steps(info.object.selected)

    def object_assign_changed(self, info):
        program = self.app.current_program.program
        if program:
            program.add_steps(info.object.selected)

    def set_all(self, info):
        """ Set parameters for all selected Steps at once. """
        from .assistants import SetAllAssistant
        assistant = SetAllAssistant(
            template=info.object.selected[0],
            steplist=self.app.all_steps)
        assistant.configure_traits()

    def interpolate(self, info):
        """ Generate interpolated steps. """
        from .assistants import InterpolateStepAssistant
        # Interpolate from first to last in selection by default
        template_start = BaseStep()
        template_end = BaseStep()
        if info.object.selected:
            info.object.selected[0].copy_params(template_start)
            info.object.selected[-1].copy_params(template_end)
        assistant = InterpolateStepAssistant(
            steplist=self.app.all_steps,
            programlist=self.app.all_programs,
            template_start=template_start,
            template_end=template_end)
        assistant.configure_traits()


class StepList(utils.Updateable):
    """ A list of Steps. """

    # --------------------------------------------------------------------------
    # Trait Definitions
    # --------------------------------------------------------------------------

    # The main application the StepList is associated with
    app = Any

    # The Steps to display.
    steps = List(Step, [])

    def _steps_default(self):
        return [Step()]

    # The Steps selected by the user.
    selected = List(Step, [])

    updated = Event

    @on_trait_change('selected, steps[]')
    def _fire_updated(self):
        self.fire('updated')

    delete = Button(tooltip='Delete selected Steps.')
    delete_all = Button(tooltip='Delete all Steps.')
    new = Button(tooltip='Create a new Step.')
    duplicate = Button(tooltip='Duplicate selected Steps.')
    assign = Button(tooltip='Assign the selected steps to the active Program.')

    # --------------------------------------------------------------------------
    # View
    # --------------------------------------------------------------------------

    view = View(
        UItem('steps', editor=steplist_editor),
        HGroup(
            VGroup(
                UItem('delete', enabled_when='selected'),
                UItem('delete_all', enabled_when='steps')),
            Spring(),
            VGroup(
                UItem('new'),
                UItem('duplicate', enabled_when='selected')),
            Spring(),
            UItem('assign', enabled_when='selected'),
        ),
        handler=StepListHandler())

    def new_step(self):
        """ Add a new Step to the list. """
        new = Step()
        self.steps.append(new)
        return new

    def add_step(self, step):
        """ Add an existing Step to the list. """
        self.add_steps(step)

    def add_steps(self, steps):
        """ Add one or multiple existing Steps to the list. """
        self.start_update('updated')
        steps = utils.ensure_iterable(steps)
        self.steps += steps
        self.stop_update('updated')

    def delete_step(self, step):
        """
        Remove an existing Step from the list and from all its associated
        programs.
        """
        self.delete_steps(step)

    def delete_steps(self, steps):
        """
        Delete multiple Steps from the Step list.
        """
        self.start_update('updated')
        steps = utils.ensure_iterable(steps)
        steps_to_delete = [step for step in steps]
        # Set the updating flag for all programs the steps are associated with
        updating_programs = []
        for step in steps_to_delete:
            for program in step.in_programs:
                program.start_update('steps_updated')
                updating_programs.append(program)
        new_steps = [step for step in self.steps if step not in steps_to_delete]
        for step in steps_to_delete:
            step.delete()
        for program in updating_programs:
            program.stop_update('steps_updated')
        self.steps = new_steps
        self.selected = []
        self.stop_update('updated')

    def delete_all_steps(self):
        """ Clear the Step list. """
        self.delete_steps(self.steps)
