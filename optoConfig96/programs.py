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
Define components to handle programs for the optoPlate96 GUI.
"""

from .ui import *
from traitsui.menu import Menu, Action
from traitsui.table_column import ObjectColumn

import numpy as np

from . import utils
from .plots import StepPlot
from .constants import MAX_STEP_DURATION
from .steps import AStep, Step, nullstep
from .steps import StepColumn


ProgramDeleteWarning = utils.ConfirmationDialog()
ProgramDeleteAllWarning = utils.ConfirmationDialog()


class StepInProgram(AStep):
    """ A container for a Step in a Program.

    Its main purpose is to provide a unique instance of a Step in Programs which
    contain multiple copies of the same step. This facilitates selection
    handling while keeping the Step setting centralized.
    """

    step = Instance(Step, ())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # __getattr__ and __setattr__ require _delegated
        # Setting it by doing self._delegated = [] results in infinite recursion
        super().__setattr__('_delegated', [])

        for trait_type in ('trait', 'property', 'event'):
            for trait_name in self.step.trait_names(type=trait_type):
                self.add_trait(trait_name, Delegate('step'))
                self._delegated.append(trait_name)

    def __getattr__(self, name):
        if name not in self._delegated:
            return getattr(self.step, name)

    def __setattr__(self, name, value):
        if name in self._delegated:
            setattr(self.step, name, value)
        else:
            super().__setattr__(name, value)


class ProgramStepColumn(StepColumn):

    def get_menu(self, object):
        menu = Menu(
            Action(
                name='New Step',
                action='info.object.new_step()'),
            Action(
                name='Remove Selected from Program',
                action='info.object.remove_steps(info.object.selected)'))
        return menu


steps_in_program_editor = TableEditor(
    columns=[
        ProgramStepColumn(name='ID', label='ID', editable=False),
        ProgramStepColumn(name='name', label='Name'),
        ProgramStepColumn(name='duration_ui.value_out', label='Dur'),
        ProgramStepColumn(name='intensity', label='Int'),
        ProgramStepColumn(name='is_pulsed', label='Pls'),
        ProgramStepColumn(name='pulse_on_ui.value_out', label='ON'),
        ProgramStepColumn(name='pulse_off_ui.value_out', label='OFF'),
    ],
    # auto_size=True,
    deletable=False,
    sortable=False,
    reorderable=True,
    row_factory='object.row_factory',
    selection_mode='rows',
    selected='selected',
    selected_indices='selected_indices',
    click='click',
    edit_on_first_click=False,
    editable=True
)


class Program(utils.Counted, utils.Updateable):
    """ An optoPlate96 Program.

    A Program is composed of one or more steps. Each Program can be assigned
    to multiple LEDs. The LEDs can be part of the same or different wells.
    """

    # Class variable. Count created instances and assign an ID.
    counter = utils.BackfillID(start=1)

    # --------------------------------------------------------------------------
    # Trait Definitions
    # --------------------------------------------------------------------------

    # Name for information and organization purposes.
    # Programs are uniquely identified by their ID (via `counter`).
    name = Str

    def _name_default(self):
        return "Program%03d" % self.ID

    # The action to take after all Steps of the program are done.
    after_end_display = Enum('Switch off LED', 'Repeat the last step', label='At the end of the program')
    _after_end = Property

    def _get__after_end(self):
        if self.after_end_display == 'Repeat the last step':
            return 'repeat'

        if self.after_end_display == 'Switch off LED':
            return 'off'

    # The Steps which make up this Program.
    steps = List(AStep, [])

    # The unique Steps which make up this Program.
    _unique_steps = Property(List, depends_on='steps')

    # The total duration of this Program's steps.
    total_duration = Property(Int, depends_on='steps.step.duration')

    @cached_property
    def _get_total_duration(self):
        return sum([step.duration for step in self.steps])

    @cached_property
    def _get__unique_steps(self):
        unique_steps = []
        for step_in_program in self.steps:
            step = step_in_program.step
            if step not in unique_steps:
                unique_steps.append(step)
        return unique_steps

    # Input validation
    invalid = Property
    total_duration_invalid = Property
    too_many_steps = Property
    no_steps = Property
    has_invalid_steps = Property

    def _get_invalid(self):
        """ Is this Program definition invalid? """
        return (
            self.total_duration_invalid or
            self.no_steps or
            self.too_many_steps or
            self.has_invalid_steps)

    def _get_total_duration_invalid(self):
        """
        Does the total duration of all steps in the program exceed the maximum?
        """
        return self.total_duration > MAX_STEP_DURATION

    def _get_too_many_steps(self):
        """
        Programs can contain at most 255 steps due to Arduino space limitations.
        """
        return len(self.steps) > 255

    def _get_no_steps(self):
        return len(self.steps) == 0

    def _get_has_invalid_steps(self):
        """ Are any steps in the program invalid?
        """
        for step in self._unique_steps:
            if step.invalid:
                return True

        return False

    def invalid_reasons(self):
        if not self.invalid:
            return None
        else:
            reasons = []
            if self.total_duration_invalid:
                reasons.append('The total duration of all Steps is too long (%d ms, maximum is %d ms).' % (self.total_duration, MAX_STEP_DURATION))
            if self.no_steps:
                reasons.append('The program contains no steps.')
            if self.too_many_steps:
                reasons.append('The program contains more than 255 steps.')
            if self.has_invalid_steps:
                reasons.append('The program contains invalid steps.')

        return '\n'.join(reasons)

    # The Steps selected by the user.
    selected = Any

    # The indices of the Steps selected by the user.
    selected_indices = Any

    assigned_leds = List([])  # TODO: Clean solution to circular dependencies

    # Is this program used in the final Arduino Code?
    is_used = Property

    def _get_is_used(self):
        if self.assigned_leds:
            return True
        else:
            return False

    steps_updated = Event

    @on_trait_change('steps, steps[]')
    def fire_steps_updated(self):
        """ Fire update event, but only if there are no more changes to come. """
        self.fire('steps_updated')

    # Event to indicate that the size requirement on the Arduino changed.
    size_update = Event

    @on_trait_change('steps_updated, after_end_display')
    def fire_size_update(self):
        self.size_update = True

    # Event to indicate any parameter changes
    dirtied = Event

    def __setattr__(self, name, value):
        super().__setattr__('dirtied', True)
        super().__setattr__(name, value)

    # --------------------------------------------------------------------------
    # View
    # --------------------------------------------------------------------------

    view = View(
        Group(Item('name')),
        Item('after_end_display'),
        Group(UItem('steps', editor=steps_in_program_editor, height=100)))

    def __repr__(self):
        string = 'Program #{ID} ({name}) with {steps} steps'
        return string.format(ID=self.ID, name=self.name, steps=len(self.steps))

    def __str__(self):
        return self.name

    def as_dict(self):
        """ Representation for dumping to JSON """
        d = {}
        d['ID'] = self.ID
        d['name'] = self.name
        d['steps'] = [step.ID for step in self.steps]
        d['after_end_display'] = self.after_end_display
        return d

    def row_factory(self):
        """
        Allow adding a Step when empty space in the Step table is right-clicked.
        """
        new_step = Step()
        new_step.in_programs.append(self)
        return StepInProgram(step=new_step)

    def new_step(self):
        """
        Allow adding a Step when a Step in the Step table is right-clicked.
        """
        new_step = Step()
        self.add_steps(new_step)
        return new_step

    def _prepare_step(self, step):
        """ Prepare a Step in order to add it to the program. """
        if isinstance(step, StepInProgram):
            new_step = StepInProgram(step=step.step)
        else:
            new_step = StepInProgram(step=step)
        if self not in new_step.in_programs:
            new_step.in_programs.append(self)
        return new_step

    def add_steps(self, steps):
        """ Add one or multiple steps to the program. """
        self.start_update('steps_updated')
        try:
            # multiple steps
            new_steps = []
            for step in steps:
                new_steps.append(self._prepare_step(step))
            self.steps += new_steps
        except TypeError:
            # one step
            self.add_step(steps)
        self.stop_update('steps_updated')

    def add_step(self, step):
        """ Add a Step to the program and register the Program with the Step. """
        new_step = self._prepare_step(step)
        self.steps.append(new_step)

    def _unregister_step(self, step):
        """ Remove association of the program with a Step. """
        try:
            step.in_programs.remove(self)
        except ValueError:
            pass

    def remove_steps(self, steps):
        """ Remove one or multiple StepInPrograms from the program. """
        self.start_update('steps_updated')
        steps = utils.ensure_iterable(steps)
        steps_to_remove = [step for step in steps]
        new_steps = [step for step in self.steps if step not in steps_to_remove]
        # Update list only once to prevent repeated redraws of the step table
        self.steps = new_steps
        for step_to_remove in steps_to_remove:
            if step_to_remove.step not in self._unique_steps:
                self._unregister_step(step_to_remove)
        self.selected = []
        self.stop_update('steps_updated')

    def delete_step(self, step):
        """
        Delete all instances of a step from the Program.
        """
        # Find relevant StepInProgram objects
        to_remove = [s for s in self.steps if s.ID == step.ID]
        self.remove_steps(to_remove)

    def delete(self):
        """ Free up the used ID und unregister the program from any LEDs. """
        self.remove_steps(self.steps)
        self.start_update('steps_updated')
        self.counter.free(self.ID)
        for led in self.assigned_leds:
            led.program = None
        self.assigned_leds = []
        self.stop_update('steps_updated')

    def duplicate(self):
        """ Return copy of the Program with the same Steps and parameters.
        """
        dup = Program()
        steps = [step.step for step in self.steps]
        dup.add_steps(steps)
        dup.after_end_display = self.after_end_display
        dup.name = "Copy of %s" % self.name
        return dup


class _Nullprogram(Program):
    counter = utils.BackfillID(start=0, maximum=0)
    after_end_display = 'Repeat the last step'


nullprogram = _Nullprogram(name='nullprogram')
nullprogram.add_step(nullstep)


class ProgramPlotData(HasTraits):
    """
    Store plot data for programs and their steps.

    While this could in principle be stored in the Program object, externalizing
    it allows different display modalities at different locations of the GUI
    for the same program.
    """

    program = Instance(Program)

    viewer = Any

    # Which steps to show pulsed? Set by an editor containing ProgramPlotData
    steps_show_pulsed = Property(depends_on='viewer.plot_update, viewer.plot_redraw')

    @cached_property
    def _get_steps_show_pulsed(self):
        return [self.viewer.show_step_pulsed(step) for step in self.program.steps]

    # Which steps ARE pulsed?
    steps_is_pulsed = Property

    def _get_steps_is_pulsed(self):
        return [step.is_pulsed for step in self.program.steps]

    # Colors of steps
    colors = Property

    def _get_colors(self):
        return [step._color for step in self.program.steps]

    # X values for individual steps, ignoring their position in the program.
    _xs = Property(depends_on='viewer.plot_update, viewer.plot_redraw')

    @cached_property
    def _get__xs(self):
        return [self.xs_for_step(step_n) for step_n in range(len(self.program.steps))]

    # X values for individual steps, taking into consideration their position in
    # the program and their start time.
    xs = Property(depends_on='viewer.plot_update, viewer.plot_redraw')

    @cached_property
    def _get_xs(self):
        xs = []
        n_steps = len(self.program.steps)
        for step_n in range(n_steps):
            step_xs = self._xs[step_n].copy()
            # Add data point at the start to continue line from the previous step
            if step_n > 0:
                step_xs = np.append(step_xs[0], step_xs)
                step_start = sum(step.duration for step in self.program.steps[:step_n])
                step_xs += step_start
            xs.append(step_xs)
        return xs

    def xs_for_step(self, step_n):
        """ Return X values for plotting a Step in the Program.


        Parameters
        ----------
        step_n : int
            Index of the Step in `program.steps`.

        Returns
        -------
        xs : ndarray of X values
        """
        step = self.program.steps[step_n]
        xs = step.get_xs(pulsed=self.steps_show_pulsed[step_n])

        return xs

    _ys = Property(depends_on='viewer.plot_update, viewer.plot_redraw')

    @cached_property
    def _get__ys(self):
        return [self.ys_for_step(step_n) for step_n in range(len(self.program.steps))]

    ys = Property(depends_on='viewer.plot_update, viewer.plot_redraw')

    @cached_property
    def _get_ys(self):
        ys = []
        n_steps = len(self.program.steps)
        for step_n in range(n_steps):
            step_ys = self._ys[step_n]
            if step_n > 0:
                # Continue where previous step left off
                step_ys = np.append(self._ys[step_n - 1][-1], step_ys)
            ys.append(step_ys)

        return ys

    def ys_for_step(self, step_n):
        """ Return Y values for plotting a Step in the Program.

        Parameters
        ----------
        step_n : int
            Index of the Step in `program.steps`.

        Returns
        -------
        ys : ndarray of Y values
        """
        step = self.program.steps[step_n]
        ys = step.get_ys(pulsed=self.steps_show_pulsed[step_n])

        return ys


class AProgramEditor(HasTraits):
    """ Base class for Program Editors. """


class MultiProgramViewer(utils.Updateable):
    """ Displays a live plot of a Program. """

    # --------------------------------------------------------------------------
    # Trait Definitions
    # --------------------------------------------------------------------------

    # Is this viewer active?
    active = Bool

    # The Programs to view.
    programs = List(Instance(Program), [])

    # Plot data for the Program and its steps.
    program_plot_datas = Property(depends_on='programs[]')

    @cached_property
    def _get_program_plot_datas(self):
        return [ProgramPlotData(program=program, viewer=self) for program in self.programs]

    # Matplotlib `Figure` object of the current Program.
    plot = Instance(StepPlot, ())

    plot_update = Event
    plot_redraw = Event

    @on_trait_change('programs:_unique_steps:plot_update, programs:name')
    def _fire_plot_update(self, obj, name, old, new):
        # Do not fire a plot update while any programs are still updating
        if self.programs and any(program.is_updating('steps_updated') for program in self.programs):
            return
        if name == 'name':
            signal = (None, name)
        elif name == 'plot_update':
            # If an update is fired from within a Step, relay information about
            # which step it was
            # new is (step_id, trait_name)
            signal = new
        self.plot_update = signal

    @on_trait_change('programs.steps_updated, show_pulsed_display, limit_cycles, max_cycles')
    def _fire_plot_redraw(self):
        # Do not fire a plot redraw while any programs are still updating
        if self.programs and any(program.is_updating('steps_updated') for program in self.programs):
            return
        self.plot_redraw = True

    show_pulsed_display = Enum(
        'All Steps', 'No Steps', 'Define per step',
        label='Show pulsing for',
        tooltip='Which Steps should be shown as pulsed in the Program plot?')

    show_pulsed = Property

    limit_cycles = Bool(True, tooltip='Limit the number of pulsing cycles that can be shown?')
    max_cycles = Int(100, tooltip='Maximum number of pulsing cycles shown across all Steps.')

    total_cycles = Property

    def _get_total_cycles(self):
        total_cycles = 0
        for program in self.programs:
            total_cycles += sum([step.cycles for step in program.steps])
        return total_cycles

    def _get_show_pulsed(self):
        if self.show_pulsed_display == 'All Steps':
            if self.limit_cycles:
                if self.total_cycles > self.max_cycles:
                    return 'none'
                else:
                    return 'all'
            else:
                return 'all'

        if self.show_pulsed_display == 'No Steps':
            return 'none'

        if self.show_pulsed_display == 'Define per step':
            return 'perstep'

    # --------------------------------------------------------------------------
    # View
    # --------------------------------------------------------------------------

    # Allow toggling the legend?
    _enable_show_legend = Bool(False)
    # Should a legend be drawn?
    show_legend = Bool(True)

    def default_traits_view(self, scrollable=False):
        view = View(
            VSplit(
                UItem('object.plot.figure', editor=MPLFigureEditor(), height=300),
                VGroup(
                    VGroup(
                        UItem('plot', editor=InstanceEditor(), style='custom'),
                        VGroup(
                            HGroup(
                                Item('show_pulsed_display'),
                                Item('show_legend', defined_when='_enable_show_legend')),
                            HGroup(
                                Item('limit_cycles', enabled_when='show_pulsed_display=="All Steps"'),
                                Item('max_cycles', enabled_when='limit_cycles'))),
                        show_border=True, label='Display Settings'
                    )
                )
            ),
            resizable=True, scrollable=scrollable
        )
        return view

    def show_step_pulsed(self, step):
        if self.show_pulsed == 'all':
            if step.is_pulsed:
                return True
            else:
                return False

        if self.show_pulsed == 'none':
            return False

        if self.show_pulsed == 'perstep':
            return step._show_pulsed

    def indices(self):
        for i in range(len(self.xs)):
            yield i

    def concatenate_from_plotdata(self, attribute):
        """
        Concatenate list attributes for all steps from all programs

        attribute : str
            A list attribute of `ProgramPlotData`.
        """
        concat = []
        for program_plot_data in self.program_plot_datas:
            concat += getattr(program_plot_data, attribute)
        return concat

    xs = Property

    def _get_xs(self):
        return self.concatenate_from_plotdata('xs')

    ys = Property

    def _get_ys(self):
        """ Concatenate y datas for all steps fromall programs. """
        return self.concatenate_from_plotdata('ys')

    steps_show_pulsed = Property

    def _get_steps_show_pulsed(self):
        return self.concatenate_from_plotdata('steps_show_pulsed')

    steps_is_pulsed = Property

    def _get_steps_is_pulsed(self):
        return self.concatenate_from_plotdata('steps_is_pulsed')

    colors = Property

    def _get_colors(self):
        return self.concatenate_from_plotdata('colors')

    title = Property(depends_on='programs.name')

    @cached_property
    def _get_title(self):
        names = [program.name for program in self.programs]
        return ', '.join(names)

    def line_indices(self, step_id):
        """
        Yield the indices for `xs`, `ys` and `plot.lines` where information
        about the requested step is stored.

        Parameters
        ----------
        step_id : int
            ID of the requested step.
        """
        for prg_n, program in enumerate(self.programs):
            for step_n, step in enumerate(program.steps):
                if step.ID == step_id:
                    start = sum(len(program.steps) for program in self.programs[:prg_n])
                    idx = start + step_n
                    # If this is not a program's last step, informatin about the
                    # next step is necessary: If y values are updated, this will
                    # otherwise lead to gaps in the plot.
                    nxt = None
                    if step_n < len(program.steps) - 1:
                        nxt = idx + 1
                    yield (idx, nxt)

    def step_from_index(self, idx):
        """
        Return the Step object associated with an index for `xs`, `ys` and
        `plot.lines`.
        """
        for program in self.programs:
            if idx < len(program.steps):
                return program.steps[idx]
            else:
                idx -= len(program.steps)

    @on_trait_change('plot_update, plot_redraw')
    def update_figure(self, obj, name, old, signal):
        self.start_update('drawing')
        self.plot._is_updating = True
        if name == 'plot_update':
            step_id, trait = signal
            if trait == 'duration':
                self._fire_plot_redraw()
            else:
                for idx, nxt in self.line_indices(step_id):
                    self._update_figure(idx, nxt)
        elif name == 'plot_redraw':
            self._redraw_figure()
        else:
            self._update_figure(idx=None, nxt=None)
        self.plot.axes.set_title(self.title)
        self.plot.draw()
        self.stop_update('drawing', signal=None)

    def _update_figure(self, idx, nxt):
        """
        Update existing figure if individual steps are modified.
        """
        if idx is not None:
            self.plot.update_xydata(idx, self.xs[idx], self.ys[idx])
            self.plot.lines[idx].set_linestyle(['-', '--'][self.steps_is_pulsed[idx]])
            self.plot.lines[idx].set_color(self.colors[idx])

            # The subsequent step needs to be informed about changes in the
            # y values to prevent gaps in the plot.
            if nxt:
                new_y = self.plot.ydata[nxt]
                new_y[0] = self.ys[idx][-1]
                self.plot.update_xydata(nxt, ydata=new_y)

    def _redraw_figure(self):
        """
        Completely redraw the figure when steps are reordered, added, or deleted,
        or step duration changes.
        """
        self.start_update('drawing')
        self.plot.set_xydata(self.xs, self.ys)
        for idx in self.indices():
            self.plot.lines[idx].set_linestyle(['-', '--'][self.steps_is_pulsed[idx]])
            self.plot.lines[idx].set_color(self.colors[idx])
        self.stop_update('drawing', signal=None)


class SingleProgramViewer(MultiProgramViewer):
    # The interface expects a list of programs
    program = Instance(Program)

    @on_trait_change('program')
    def update_programs(self):
        self.programs = [self.program]


class ProgramEditor(AProgramEditor):
    viewer = Instance(SingleProgramViewer, ())
    program = Instance(Program)

    @on_trait_change('program')
    def update_viewer_program(self):
        self.viewer.program = self.program

    view = View(
        VSplit(
            UItem('viewer', editor=InstanceEditor(), style='custom'),
            UItem('program', editor=InstanceEditor(), style='custom')
        ),
        resizable=True, scrollable=True)


class NoProgramEditor(AProgramEditor):
    """ Empty Program Editor to display when no Program is available. """
    program = None
    view = View(Label('Create or select a Program to show the editor.'))


class ProgramColumn(ObjectColumn):
    """ Defines a column of the ProgramList table. """

    read_only_cell_color = Color(0xCCCCCC)

    def get_cell_color(self, object):
        # Mark invalid rows
        if object.invalid:
            return COLOR_INVALID
        return super().get_cell_color(object)

    def get_value(self, object):
        if self.name == 'invalid':
            return ['No', 'Yes'][getattr(object, self.name)]

        if self.name == 'after_end_display':
            return getattr(object, '_after_end')

        return super().get_value(object)

    def is_editable(self, object):
        if self.name in ('ID', 'invalid'):
            return False

        return True

    def get_tooltip(self, object):
        return object.invalid_reasons()


programlist_editor = TableEditor(
    columns=[
        ProgramColumn(name='ID', label='ID', editable=False),
        ProgramColumn(name='name', label='Name'),
        ProgramColumn(name='after_end_display', label='After End'),
        ProgramColumn(name='invalid', label='Invalid')
    ],
    auto_size=True,
    deletable=False,  # Programs need to unassign themselves from wells when deleted
    reorderable=True,
    row_factory=Program,
    selection_mode='rows',
    selected='selected',
    click='clicked',
    edit_on_first_click=False,
    show_row_labels=False
)


class ProgramListHandler(Controller):
    """ Handler for the ProgramList. """

    # Provided by main application handler at runtime
    app = Any

    def init(self, info):
        # Populate dropdown menu for LED assignment.
        self.app = info.object.app
        return True

    def populate_rightclick_menu(self, info):
        """
        Populate right-click menu to add Program Steps to another Program and
        to assign Programs to Wells.

        Called from the main application handler.
        """
        add_steps_items = []
        for program in sorted(info.object.programs, key=lambda prg: prg.name):
            add_steps_items.append(Action(
                name=program.name,
                action="handler.add_to(info, to_program=%d)" % program.ID))

        led_assign_items = []
        led_bulk_assign_items = []
        for i, led_type in enumerate(self.app.plate.led_types):
            led_assign_items.append(Action(
                name=led_type.name,
                action='handler.assign_to(info, to_led=%d)' % i,
                enabled_when='handler.allow_well_assign(info)'))
            led_bulk_assign_items.append(Action(
                name=led_type.name,
                action='handler.bulk_assign(info, to_led=%d)' % i,
                enabled_when='handler.allow_bulk_assign(info)'))
        for column in info.programs.columns:
            column.menu = Menu(
                Action(name='New Program', action='info.object.new_program()'),
                Action(name='Delete Selected', action='handler.object_delete_changed(info)'),
                Action(name='Duplicate Selected', action='handler.object_duplicate_changed(info)'),
                Action(name='Create dark Step with program duration', action='handler.dark_step(info)'),
                Menu(*add_steps_items, name='Add program steps to ...'),
                Menu(*led_assign_items, name='Assign Program to selected wells ...'),
                Menu(*led_bulk_assign_items, name='Bulk assign selected Programs to selected wells ...'))

    @on_trait_change('app.plate.selected, app.all_programs.selected')
    def _allow_assign(self):
        self.allow_well_assign(self.info)
        self.allow_bulk_assign(self.info)

    def allow_well_assign(self, info):
        selected_wells = self.app.plate.selected
        selected_programs = self.app.all_programs.selected
        if selected_wells and len(selected_programs) == 1:
            allow = True
        else:
            allow = False
        info.assign.enabled = allow
        return allow

    def allow_bulk_assign(self, info):
        plate_sel = self.app.plate.selected
        program_sel = self.app.all_programs.selected
        if len(plate_sel) == len(program_sel) and len(plate_sel) > 0 and len(program_sel) > 0:
            allow = True
        else:
            allow = False
        info.bulk_assign.enabled = allow
        return allow

    def dark_step(self, info):
        for program in info.object.selected:
            duration = sum([step.duration for step in program.steps])
            if duration > MAX_STEP_DURATION:
                msg = 'Dark Step for program %s would exceed maximum duration (%d ms, maximum is %d ms).'
                msg = msg % (program.name, duration, MAX_STEP_DURATION)
                error(msg, 'Cannot create Dark Step')
            name = 'Dark_' + program.name
            new_step = Step(name=name, duration=duration)
            self.app.all_steps.add_step(new_step)

    def object_delete_changed(self, info):
        """ Remove selected Programs from Program list. """
        programs_to_delete = []
        for program in info.object.selected:
            confirm = self.confirm_delete(program)
            if confirm == utils.YES:
                programs_to_delete.append(program)
            elif confirm == utils.CANCEL:
                break
        info.object.delete_programs(programs_to_delete)

    def object_delete_all_changed(self, info):
        if self.confirm_delete_all() == utils.YES:
            # Temporarily prevent redraws of the Plate table for performance
            # reasons.
            # Although there will currently only ever be one plate, handle
            # potential multiple plates.
            for program in info.object.programs:
                plates = [led.well.plate for led in program.assigned_leds]
            for plate in plates:
                plate.start_update('updated')

            info.object.delete_all_programs()
            info.object.selected = []

            for plate in plates:
                plate.stop_update('updated')

    def object_new_changed(self, info):
        info.object.new_program()

    def object_duplicate_changed(self, info):
        new_programs = [program.duplicate() for program in info.object.selected]
        info.object.start_update('updated')
        info.object.add_programs(new_programs)
        info.object.stop_update('updated')

    def confirm_delete(self, program):
        """
        Ask the user to confirm Program deletion if the Program has Steps or is
        assigned to LEDs.
        """
        steps = ['  * ' + step.name for step in program.steps]
        msg_steps = ''
        if steps:
            if len(steps) < 10:
                msg_steps = '\nIt contains the following Steps:\n'
                msg_steps += '\n'.join(steps)
            else:
                msg_steps = '\nIt contains %d Steps.\n' % len(steps)
        msg_leds = ''
        if program.assigned_leds:
            msg_leds = '\nIt is assigned to %d LEDs.\n' % len(program.assigned_leds)

        if steps or program.assigned_leds:
            msg = "Are you sure you want to delete Program '%s'?" % program.name
            msg += msg_steps
            msg += msg_leds
            confirm = ProgramDeleteWarning(message=msg)
        else:
            confirm = utils.YES

        return confirm

    def confirm_delete_all(self):
        """
        Ask the user to confirm deletion of all programs.
        """
        msg = 'Do you really want to delete ALL programs?'
        confirm = ProgramDeleteAllWarning(message=msg)
        return confirm

    def add_to(self, info, to_program):
        """ Add Steps from the selected Program(s) to another Program.

        Parameters
        ----------
        to_program : int
            ID of the Program to add to.
        """
        for dst_program in self.app.all_programs.programs:
            if dst_program.ID == to_program:
                for src_program in info.object.selected:
                    # Avoid infinite loop if src_program is dst_program
                    steps_to_add = [step for step in src_program.steps]
                    dst_program.add_steps(steps_to_add)

    def assign_to(self, info, to_led):
        """
        Assign the first Program in the selection to the specified LED of all
        selected wells.
        """
        plate = self.app.plate
        program = info.object.selected[0]
        plate.assign_to_selected(to_led, program)

    def object_assign_changed(self, info):
        plate = self.app.plate
        program = self.app.current_program.program
        to_led = info.object._assign_to_choices.index(info.object.assign_to)
        plate.assign_to_selected(to_led, program)

    def object_bulk_assign_changed(self, info):
        to_led = info.object._assign_to_choices.index(info.object.assign_to)
        self.bulk_assign_to(info, to_led)

    def bulk_assign_to(self, info, to_led):
        """
        Assign all selected programs to selected wells in the order of selection.
        """
        pairs = zip(self.app.plate.selected_well_groups, info.object.selected)
        for well, program in pairs:
            well.assign_program(to_led, program)


class ProgramList(utils.Updateable):
    """ A list of Programs. """

    # --------------------------------------------------------------------------
    # Trait Definitions
    # --------------------------------------------------------------------------

    # The main application the ProgramList is associated with
    app = Any

    # The Programs to display.
    programs = List(Program, [])

    def _programs_default(self):
        return [Program()]

    updated = Event

    @on_trait_change('programs[], programs:name, selected')
    def _fire_updated(self):
        self.fire('updated')

    # The Programs selected by the user.
    selected = List(Program, [])

    clicked = Program

    delete = Button(tooltip='Delete selected Programs.')
    delete_all = Button(tooltip='Delete all Programs.')
    new = Button(tooltip='Create a new Program.')
    duplicate = Button(tooltip='Duplicate selected Programs.')
    assign = Button(tooltip='Assign selected Program to an LED of selected wells.')
    bulk_assign = Button(tooltip='Assign selected Programs to an LED of selected wells, in the order of selection.')
    assign_to = Enum(values='_assign_to_choices', tooltip='LED to assign to.')
    _assign_to_choices = Property(List, depends_on='app.plate.config.led_types')

    def _get__assign_to_choices(self):
        if self.app is not None:
            return self.app.plate.config.led_types
        else:
            return [None]

    # --------------------------------------------------------------------------
    # View
    # --------------------------------------------------------------------------

    view = View(
        UItem('programs', editor=programlist_editor),
        HGroup(
            VGroup(
                UItem('delete', enabled_when='selected'),
                UItem('delete_all')),
            Spring(),
            VGroup(
                UItem('new'),
                UItem('duplicate', enabled_when='selected')),
            Spring(),
            VGroup(
                HGroup(
                    UItem('assign'), UItem('bulk_assign')),
                HGroup(
                    Spring(), UItem('assign_to'), Spring())),
        ),
        handler=ProgramListHandler())

    def new_program(self):
        """ Add a new Program to the list. """
        new = Program()
        self.programs.append(new)
        return new

    def add_program(self, program):
        """ Add an existing Program to the list. """
        self.programs.append(program)

    def add_programs(self, programs):
        """ Add one or multiple existing Programs to the list. """
        self.start_update('updated')
        programs = utils.ensure_iterable(programs)
        self.programs += programs
        self.stop_update('updated')

    def delete_program(self, program):
        """ Remove an existing Program from the list. """
        self.delete_programs(program)

    def delete_programs(self, programs):
        """ Delete multiple programs from the Program list. """
        self.start_update('updated')
        programs = utils.ensure_iterable(programs)
        programs_to_delete = [program for program in programs]
        for program in programs_to_delete:
            program.delete()
        new_programs = [program for program in self.programs if program not in programs_to_delete]
        self.programs = new_programs
        self.selected = []
        self.stop_update('updated')

    def delete_all_programs(self):
        """ Clear the program list. """
        self.delete_programs(self.programs)
