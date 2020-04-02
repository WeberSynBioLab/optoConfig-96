# plate.py
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
Configuration of the plate for the optoPlate96 GUI.
"""

import math

from .ui import *
from traitsui.menu import OKCancelButtons

import matplotlib as mpl

import numpy as np

from . import programs
from . import utils
from .plots import ArrayHeatmap

PlateConfigChangeWarning = utils.ConfirmationDialog()
ClearWellWarning = utils.ConfirmationDialog()


class LEDHandler(Handler):
    def object_correction_file_changed(self, info):
        if info.initialized:
            try:
                info.object.correction_factors = info.object.read_correction()
            except ValueError as e:
                error(str(e))
                info.object.correction_file = ''


class LED(HasTraits):
    """ Description of a potential LED type. """

    color = Color

    name = Str('New LED')

    invalid = Property(depends_on='name_invalid, correction_factors_invalid')
    # An LED name must be unique, duplicated names are invalid, but this is
    # determined in the context of the whole plate configuration.
    name_invalid = Bool(False)
    correction_factors_invalid = Property

    def _get_correction_factors_invalid(self):
        if self.correction_factors is None:
            return False
        elif (np.any(self.correction_factors) < 0 or np.any(self.correction_factors) > 1):
            return True
        else:
            return False

    @cached_property
    def _get_invalid(self):
        """ Is this LED type invalid? """
        return self.name_invalid or self.correction_factors_invalid

    # Can Intensity values for this LED be converted to µmol/s?
    can_convert = Bool(False, label='Convert', tooltip='Can arbitrary intensity units be converted to physical units for this LED?')
    # Conversion factor from arbitrary units to µmol/s.
    conversion_factor = Float(1.0, tooltip='Conversion factor from an arbitrary intensity setting to physical units for this LED.')
    # Name of the unit to use
    unit = Str('µmol·m⁻²·s⁻¹', tooltip='The unit to convert to. For display purposes only.')

    # Path to a file storing correction factors for this LED
    correction_file = File('', filter=['*.csv'], tooltip='Path to file storing correction factors. This must be a .csv file using commas as delimiters, periods as decimal separators and no thousands separator.')

    correction_factors = Either(None, Instance(np.ndarray))

    heatmap = Property(Instance(ArrayHeatmap), depends_on='correction_factors', label='Show')

    @cached_property
    def _get_heatmap(self):
        return ArrayHeatmap(array=self.correction_factors, title='Correction Factors for LED %s' % self.name)

    show_array = Button('Show')

    def _show_array_fired(self):
        self.heatmap.edit_traits()

    # Are correction factors applied to this LED?
    corrected = Property(Bool, depends_on='correction_factors')

    @cached_property
    def _get_corrected(self):
        if self.correction_factors is None:
            return False
        else:
            return True

    @staticmethod
    def try_delimiters(file):
        """ Try to read a file to a numpy array with different delimiter options """
        for delimiter in (',', ';', '\t'):
            try:
                return np.loadtxt(file, delimiter=delimiter)
            except ValueError:
                continue
        raise ValueError

    def read_correction(self):
        """ Try to read the provided file and generate a correction matrix. """
        if self.correction_file == '':
            return None
        try:
            factors = self.try_delimiters(self.correction_file)
        except Exception:
            msg = 'Could not read correction factors from file %s.'
            msg = msg % self.correction_file
            raise ValueError(msg)
        rows, cols = factors.shape
        if rows != 8 or cols != 12:
            msg = 'Expected 8 rows (but got %d) and 12 columns (but got %d).'
            msg = msg % (rows, cols)
            raise ValueError(msg)
        if np.any(factors < 0) or np.any(factors > 1):
            msg = 'Correction factors must be within 0 and 1.'
            raise ValueError(msg)
        return factors

    clear_correction = Button('Clear')

    def _clear_correction_fired(self):
        self.correction_file = ''
        self.correction_factors = None

    view = View(
        VGroup(
            HGroup(
                Item('name'),
                Item('color', editor=ColorEditor(), style='simple')),
            HGroup(
                Item('can_convert'),
                Item('conversion_factor', enabled_when='can_convert'),
                Item('unit', enabled_when='can_convert')),
            HGroup(
                Item('correction_file', editor=FileEditor(dialog_style='open')),
                UItem('clear_correction'),
                UItem('show_array', enabled_when='corrected'))
        ),
        handler=LEDHandler()
    )

    def as_dict(self):
        """ Representation for dumping to JSON """
        d = {}
        d['color'] = self.color.name()
        d['name'] = self.name
        d['can_convert'] = self.can_convert
        d['conversion_factor'] = self.conversion_factor
        d['unit'] = self.unit
        d['corrected'] = self.corrected
        if self.correction_factors is None:
            d['correction_factors'] = self.correction_factors
        else:
            d['correction_factors'] = self.correction_factors.tolist()

        return d

    def __str__(self):
        return self.name


class Grouping(HasTraits):
    grouptype = Enum('96-well', '24-well')

    nrows = Property(depends_on='grouptype')

    def _get_nrows(self):
        if self.grouptype == '96-well':
            return 8
        elif self.grouptype == '24-well':
            return 4
        elif self.grouptype == '6-well':
            return 2

    ncols = Property(depends_on='grouptype')

    def _get_ncols(self):
        if self.grouptype == '96-well':
            return 12
        elif self.grouptype == '24-well':
            return 6
        elif self.grouptype == '6-well':
            return 3

    blocksize = Property(depends_on='grouptype')

    def _get_blocksize(self):
        if self.grouptype == '96-well':
            return 96 / 96
        elif self.grouptype == '24-well':
            return 96 / 24
        elif self.grouptype == '6-well':
            return 96 / 6


class LEDColumn(ObjectColumn):

    read_only_cell_color = Color(0xCCCCCC)

    def get_value(self, object):
        if self.name == "color":
            return ''

        if self.name in ('can_convert', 'corrected'):
            return ['No', 'Yes'][getattr(object, self.name)]

        return super().get_value(object)

    def get_cell_color(self, object):
        if self.name == 'color':
            return object.color
        elif object.invalid:
            return COLOR_INVALID
        return super().get_cell_color(object)

    def is_editable(self, object):
        if self.name == 'can_convert':
            return True

        if self.name == 'conversion_factor':
            return object.can_convert

        if self.name == 'unit':
            return object.can_convert

        if self.name == 'name':
            return True

        return False


led_table = TableEditor(
    columns=[
        LEDColumn(name='name'),
        LEDColumn(name='color'),
        LEDColumn(name='can_convert', label='Convert'),
        LEDColumn(name='conversion_factor'),
        LEDColumn(name='unit'),
        LEDColumn(name='corrected')
    ],
    edit_view='object.view',
    selected='selected_led',
    sortable=False,
    reorderable=False,
    deletable=False,
    orientation='vertical'
)


class PlateConfigHandler(Handler):
    def init(self, info):
        info.object.selected_led = info.object.led_types[0]
        return True

    def object__led_types_changed_changed(self, info):
        for led_type in info.object.led_types:
            led_type.name_invalid = info.object.led_types_names_invalid

    def close(self, info, is_ok):
        if is_ok and info.object.invalid:
            msg = 'The plate configuration is invalid:\n'
            msg += info.object.invalid_reasons()
            error(msg)
            return False

        if is_ok and info.object._require_redraw and not info.object._no_redraw_confirm:
            msg = 'Changing the plate configuration will reset all Program assignments.'
            msg += '\nContinue?'
            confirm = PlateConfigChangeWarning(message=msg)
            if confirm == utils.YES:
                return True
        else:
            return True

    def closed(self, info, is_ok):
        info.object._require_redraw = False


class PlateConfig(HasTraits):

    grouptype = Enum('96-well', '24-well')

    grouping = Instance(Grouping, ())

    @on_trait_change('grouptype')
    def update_grouping(self):
        self.grouping = Grouping(grouptype=self.grouptype)

    nrows = Delegate('grouping')
    ncols = Delegate('grouping')

    platetype = Enum('1-Color', '2-Color', '3-Color')

    def _platetype_default(self):
        return '3-Color'

    @on_trait_change('platetype')
    def update_led_types(self):
        self.led_types = self._platetype_led_defaults()
        self.selected_led = self.led_types[0]
        return self.led_types

    def _platetype_led_defaults(self):
        if self.platetype == '1-Color':
            return [LED(color='#0000FF', name='465 nm')]

        if self.platetype == '2-Color':
            return [
                LED(color='#FF0000', name='643 nm'),
                LED(color='#770000', name='780 nm')]

        if self.platetype == '3-Color':
            return [
                LED(color='#0000FF', name='465 nm'),
                LED(color='#FF0000', name='630 nm'),
                LED(color='#770000', name='780 nm')]

    led_types = List(LED)

    def _led_types_default(self):
        return self._platetype_led_defaults()

    selected_led = Instance(LED)

    def _selected_led_default(self):
        return self.led_types[0]

    _led_types_changed = Event

    @on_trait_change('led_types.name')
    def fire__led_types_changed(self):
        self._led_types_changed = True

    led_types_names_invalid = Property(depends_on='led_types[]')

    def _get_led_types_names_invalid(self):
        """ LED types must have a unique name. """
        names = [led_type.name for led_type in self.led_types]
        return len(names) != len(set(names))

    conversion_factors = Property(Dict, depends_on='led_types.conversion_factor')

    @cached_property
    def _get_conversion_factors(self):
        d = {}
        for led_type in self.led_types:
            if led_type.can_convert:
                d[led_type.name] = led_type.conversion_factor
            else:
                d[led_type.name] = 'NA'
        return d

    _require_redraw = Bool(False)

    @on_trait_change('grouping, platetype')
    def update_require_redraw(self):
        self._require_redraw = True

    # Skip asking the user whether resetting all programs is okay?
    _no_redraw_confirm = Bool(False)

    units = Property(Dict, depends_on='led_types.unit')

    @cached_property
    def _get_units(self):
        d = {}
        for led_type in self.led_types:
            d[led_type.name] = led_type.unit
        return d

    @on_trait_change('led_types:unit')
    def sync_units(self, obj, trait, old, new):
        """ Keep units the same across all LED types """
        for led_type in self.led_types:
            led_type.unit = new

    def as_dict(self):
        """ Representation for dumping to JSON """
        d = {}
        d['grouptype'] = self.grouptype
        d['led_types'] = [led.as_dict() for led in self.led_types]
        return d

    invalid = Property

    def _get_invalid(self):
        return self.led_types_names_invalid

    def invalid_reasons(self):
        if not self.invalid:
            return None
        else:
            reasons = []
            if self.led_types_names_invalid:
                reasons.append('LED types must have unique names.')

        return '\n'.join(reasons)

    view = View(
        Item('grouptype', label='Grouping'),
        Item('platetype', label='Plate Colors'),
        Item('led_types', editor=led_table, label='LED Types'),
        title='Plate Configuration',
        buttons=OKCancelButtons,
        kind='modal',
        handler=PlateConfigHandler())


class WellLED(HasTraits):
    """ An actual LED associated with a specific well. """

    # Index of the LED type in self.wells.led_types
    led_type_idx = Int

    # Deferred
    # well = Instance(Well)

    led_type = Property

    def _get_led_type(self):
        return self.well.led_types[self.led_type_idx]

    name = Delegate('led_type')

    program = Instance(programs.Program)

    def as_dict(self):
        """ Representation for dumping to JSON """
        d = {}
        if self.program:
            d['program'] = self.program.ID
        else:
            d['program'] = None
        return d

    def _unassociate_cur_prog(self):
        if self.program:
            try:
                self.program.assigned_leds.remove(self)
            except ValueError:
                pass

    def assign_program(self, program):
        self._unassociate_cur_prog()
        program.assigned_leds.append(self)
        self.program = program

    def unassign_program(self):
        self._unassociate_cur_prog()
        self.program = None


class Well(HasTraits):
    """ A single well. """

    # Deferred
    # plate = Instance(Plate, ())

    led_types = DelegatesTo('plate')

    # Specific LEDs for this well
    leds = List(WellLED)

    # Position of the well on the plate as a string, taking grouping into account
    position = Str('')

    # Position of the well on the plate as indices, without grouping
    pos_row = Int
    pos_col = Int

    def _leds_default(self):
        return [WellLED(led_type_idx=idx, well=self) for idx in range(len(self.led_types))]

    def as_list(self):
        """ Representation for dumping to JSON """
        leds = [led.as_dict() for led in self.leds]
        return leds

    def assign_program(self, led_n, program):
        led = self.leds[led_n]
        led.assign_program(program)


class WellGroup(HasTraits):
    """ A group of multiple wells. """

    # Deferred
    # plate = Instance(Plate, ())

    wells = List(Well)

    leds = Property(List(WellLED))

    # Position of the well on the plate.
    position = Str('')

    @on_trait_change('position, wells[]')
    def update_well_positions(self):
        for well in self.wells:
            well.position = self.position

    def _get_leds(self):
        return self.wells[0].leds

    def assign_program(self, led_n, program):
        for well in self.wells:
            well.assign_program(led_n, program)


class PlateRow(HasTraits):

    columns = List(WellGroup)

    def __len__(self):
        return len(self.columns)

    def __getitem__(self, column):
        """ Return the well groups associated with a column of the row. """
        return self.columns[column]

    def get_wells(self, column):
        """ Return the individual wells associated with a column of the row. """
        return self[column].wells


class PlateRowColumn(ObjectColumn):
    def get_object(self, object):
        return object.columns[int(self.name)]

    def get_label(self):
        return str(int(self.name) + 1)

    def get_value(self, object):
        well = self.get_object(object).wells[0]
        led_programs = []
        for led in well.leds:
            # led_programs = ['Well %s' % well.index]
            led_programs.append('%s: %s' % (led.name, led.program))
        return '\n'.join(led_programs)

    def get_cell_color(self, object):
        well_group = self.get_object(object)
        colors = []
        for led in well_group.leds:
            if led.program:
                led_color = list(led.led_type.color.getRgb())
                # Halve alpha for readability
                led_color[-1] = round(led_color[-1] / 2)
                colors.append(led_color)
        if not colors:
            colors = [(255, 255, 255, 255)]
        blended = utils.blend_colors(colors)
        return QtGui.QColor(*blended)

    def get_menu(self, object):
        menu = Menu(
            Action(
                name='Clear programs from selected wells',
                action='info.handler.clear_selected(info)'))
        return menu


class PlateHandler(Handler):
    def object_updated_changed(self, info):
        """ Redraw the table on changes. """
        info.plate_rows.update_editor()

    def clear_selected(self, info):
        """
        Ask the user to clear selected wells from assigned programs, and do so
        if confirmed.
        """
        wells_to_clear = []
        for well_group in info.object.selected_well_groups:
            # If there is an active grouping, only ask for user confirmation once,
            # and not for each well in the group
            user_asked = False
            for well in well_group.wells:
                if not user_asked:
                    confirm = self.confirm_program_clear(well)
                    user_asked = True
                if confirm == utils.YES:
                    wells_to_clear.append(well)
                else:
                    break
        info.object.clear_programs(wells_to_clear)
        return True

    def confirm_program_clear(self, well):
        if any([led.program for led in well.leds]):
            msg_base = 'The following programs are assigned to well {well}:'
            msg = [msg_base.format(well=well.position)]
            for led in well.leds:
                program_name = None
                if led.program is not None:
                    program_name = led.program.name
                msg.append(' * LED  {led}: {program}'.format(
                    led=led.name, program=program_name))
            msg.append('\nDo you want to unassign all programs from this well?')
            msg = '\n'.join(msg)
            confirm = ClearWellWarning(message=msg)
        else:
            confirm = utils.YES
        return confirm


class Plate(utils.Updateable):
    """ A Plate with wells and LEDs to assign Programs to. """

    # Configuration of the plate: LEDs and well groupings
    config = Instance(PlateConfig, ())

    # Number of rows and columns after grouping
    nrows = Delegate('config')
    ncols = Delegate('config')

    # LEDs and Grouping settings from config
    # These should be Delegate or DelegateTo objects, but they do not trigger
    # listeners when config is updated.
    led_types = Property(depends_on='config')

    def _get_led_types(self):
        return self.config.led_types

    editor = Property(Instance(TableEditor), depends_on='config.grouping')

    def _get_editor(self):
        editor = TableEditor(
            columns=[PlateRowColumn(name=str(i)) for i in range(len(self.plate_rows[0]))],
            sortable=False,
            reorderable=False,
            deletable=False,
            editable=False,
            selection_mode='cells',
            show_row_labels=True,
            selected='selected',
            cell_font="8",
        )
        return editor

    wells = List(Well, resettable=True)

    def _wells_default(self):
        wells = []
        for i in range(96):
            # The absolute position on the physical plate with 12 columns,
            # without grouping
            pos_row = i // 12
            pos_col = i % 12
            wells.append(Well(plate=self, pos_row=pos_row, pos_col=pos_col))
        return wells

    @cached_property
    def _get_well_groups(self):
        sidelen = math.sqrt(self.config.grouping.blocksize)
        if not sidelen.is_integer():
            raise ValueError('Grouping into %d groups is unsupported.' % n_groups)

        n_groups = int(96 / self.config.grouping.blocksize)
        sidelen = int(sidelen)
        groups_per_row = 12 // sidelen
        well_groups = []
        for i in range(n_groups):
            row = i // groups_per_row
            start = i * (sidelen) + row * 12 * (sidelen - 1)
            idcs = [start + c + r * 12 for r in range(sidelen) for c in range(sidelen)]
            well_group = WellGroup(plate=self)
            well_group.position = utils.idx2well(i, self.nrows, self.ncols)
            well_group.wells = [self.wells[idx] for idx in idcs]
            well_groups.append(well_group)
        return well_groups

    # Wells selected by the user. Format (PlateRow, 'idx')
    selected = List(Any, [])

    selected_wells = Property(List, depends_on='selected')

    def _get_selected_wells(self):
        selected_wells = []
        for row, col in self.selected:
            col = int(col)
            wells = row.get_wells(col)
            selected_wells += wells
        return selected_wells

    well_groups = Property(List(WellGroup), depends_on='config.grouping')

    selected_well_groups = Property(List, depends_on='selected')

    def _get_selected_well_groups(self):
        selected_well_groups = []
        for row, col in self.selected:
            col = int(col)
            selected_well_groups.append(row[col])
        return selected_well_groups

    active_well = Instance(Well)

    active_well_changed = Event

    @on_trait_change('selected')
    def _set_active_well(self):
        if self.selected:
            # Treat the first well of the first selected WellGroup as active
            self.active_well = self.selected_well_groups[0].wells[0]
        else:
            self.active_well = None
        self.active_well_changed = True

    plate_rows = Property(List(PlateRow), depends_on='well_groups')

    @cached_property
    def _get_plate_rows(self):
        sidelen = math.sqrt(self.config.grouping.blocksize)
        groups_per_row = int(12 / sidelen)
        n_rows = int(len(self.well_groups) / groups_per_row)
        rows = []
        for i in range(n_rows):
            cols = self.well_groups[i * groups_per_row:i * groups_per_row + groups_per_row]
            rows.append(PlateRow(columns=cols))
        return rows

    # Event to indicate to the handler a redraw of the Table is necessary.
    updated = Event

    @on_trait_change('config, wells.leds, wells.leds.program, wells.leds.program.name')
    def _fire_updated(self):
        self.fire('updated')

    # Event to indicate that the size requirement on the Arduino changed.
    size_update = Event

    @on_trait_change('wells:leds:program, led_types')
    def fire_size_update(self, obj, trait, old, new):
        self.size_update = True

    def default_traits_view(self):
        return View(
            UItem('plate_rows', editor=self.editor),
            handler=PlateHandler(),
            resizable=True)

    def assign_to_selected(self, to_led, program):
        """ Assign program to an LED.

        Parameters
        ----------
        to_led : int
            Index of the LED in well.leds
        program: Program
            Program to assign
        """
        self.start_update('updated')
        for well in self.selected_wells:
            well.assign_program(to_led, program)
        self.stop_update('updated')

    def clear_programs(self, wells):
        """ Remove assigned programs from specified wells. """
        self.start_update('updated')
        for well in wells:
            for led in well.leds:
                led.unassign_program()
        self.stop_update('updated')

    def clear_selected(self):
        """ Remove assigned programs from selected wells. """
        self.clear_programs(self.selected_wells)

    @on_trait_change('config')
    def config_changed(self, obj, trait, old, new):
        # Grouping of wells or number of LEDs changed: complete reset
        if (len(old.led_types) != len(new.led_types) or
            old.grouping.grouptype != new.grouping.grouptype):
                self.reset_traits(resettable=True)
        # Update LED type name and color
        for i, led_type in enumerate(self.led_types):
            self.led_types[i].name = new.led_types[i].name
            self.led_types[i].color = new.led_types[i].color
        self.selected = []

    def done_after(self):
        """
        Return time in ms after which all programs assigned to an LED of the
        plate are done.
        """
        done_after = 0
        for well in self.wells:
            for led in well.leds:
                if led.program is None:
                    continue
                else:
                    done_after = max(done_after, led.program.total_duration)
        return done_after


# Deferred from Well definition due to mutual dependency
Well.add_class_trait('plate', Instance(Plate, ()))

# Deferred from WellGroup definition due to mutual dependency
WellGroup.add_class_trait('plate', Instance(Plate, ()))

# Deferred from WellLED definition due to mutual dependency
WellLED.add_class_trait('well', Instance(Well, ()))


class AWellProgramsViewer(programs.MultiProgramViewer):
    """ Base class for well program viewers. """

    _enable_show_legend = True

    def default_traits_view(self, scrollable=True):
        return super().default_traits_view(scrollable=scrollable)


class WellProgramsViewer(AWellProgramsViewer):
    """ A viewer for multiple programs (assigned to a well) at once. """

    well = Instance(Well)

    # Overwrite colors: Use only LED colors, not step colors
    colors = Property(depends_on='well.leds.program.steps')

    @cached_property
    def _get_colors(self):
        colors = []
        for led in self.well.leds:
            if led.program is not None:
                prg_colors = [utils.qt_color_to_rgb(led.led_type.color)]
                # Repeat the color for each step
                prg_colors = prg_colors * len(led.program.steps)
                colors = colors + prg_colors
        return colors

    # matplotlib patches to use for the legend
    legend = Either(List, None)

    @on_trait_change('well.leds, well.leds.program.steps')
    def update_viewer(self):
        if self.well is not None:
            programs = []

            for led in self.well.leds:
                if led.program is not None:
                    programs.append(led.program)
            if self.programs == programs:
                # If the programs are identical from one well to the next,
                # no plot update is fired, even if they are assigned to different
                # LEDs. In that case, force one.
                self.programs = []
            self.programs = programs
        self.plot.axes.set_title(self.title)
        self.update_legend()

    def led_legend(self, led):
        """
        Create a plot legend for an LED.
        """
        label = '%s: ' % led.led_type.name
        if led.program is None:
            label += 'None'
        else:
            label += '%s (end: %s)'
            label = label % (led.program.name, led.program._after_end)
        patch = mpl.lines.Line2D(
            [], [],
            color=utils.qt_color_to_rgb(led.led_type.color),
            label=label)
        return patch

    @on_trait_change('programs:[name, after_end_display], show_legend')
    def update_legend(self):
        if self.well is None:
            return

        legend = []
        if self.show_legend:
            for led in self.well.leds:
                legend.append(self.led_legend(led))
        self.legend = legend
        self.plot.draw()

    title = Property(depends_on='well, programs.name')

    @cached_property
    def _get_title(self):
        names = [program.name for program in self.programs]
        title = ', '.join(names)
        title = self.well.position + '\n' + title
        return title

    @on_trait_change('legend[]')
    def set_legend(self):
        if not self.legend:
            self.plot.axes.get_legend().remove()
        else:
            self.plot.axes.legend(handles=self.legend, loc=(0, 0))


class NoWellProgramsViewer(AWellProgramsViewer):
    """ Empty Viewer to display when no Well is selected. """
    programs = []

    def default_traits_view(self):
        return View(Label('Select a well to display its associated programs.'))
