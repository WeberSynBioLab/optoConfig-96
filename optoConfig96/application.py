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


from .ui import *
from traitsui.menu import Menu, MenuBar, Action
from traitsui.extras.saving import CanSaveMixin, SaveHandler

from pyface.api import FileDialog, confirm, YES, NO, CANCEL, OK

import os
import json

from . import config
from . import load
from . import steps
from . import programs
from . import plates
from . import export
from . import resources
from . import hardware
from . import utils
from . import experiment_csv
from . import testmode


class ApplicationHandler(Controller, SaveHandler):
    def init(self, info):
        # Build initial Assignment menu for Steps and Programs
        self.object_programs_updated_changed(info)
        # Update step editor initially to display default step.
        self.object_current_step_update_from_all_steps_changed(info)
        self.object_current_program_update_changed(info)

        self.saveObject = self.info.object
        self.saveObject.dirty = False
        return True

    # --------------------------------------------------------------------------
    # Handle the current step to display.
    # --------------------------------------------------------------------------

    def make_step_active(self, info, step):
        """ Ensure there is a proper step editor and make the step active. """
        if isinstance(info.object.current_step, steps.StepEditor):
            info.object.current_step.step = step
        else:
            info.object.current_step = steps.StepEditor(step=step)

    def object_current_step_update_from_all_steps_changed(self, info):
        """ Determine which Step to display in the Step Editor. """
        if info.object.all_steps.selected:
            # There is a step selection.
            self.make_step_active(info, info.object.all_steps.selected[0])
        else:
            # There is no step selection.
            # Is the step shown last no longer available?
            if info.object.current_step.step not in info.object.all_steps.steps:
                try:
                    self.make_step_active(info, info.object.all_steps.steps[0])
                except IndexError:
                    # Nothing there to show.
                    info.object.current_step = steps.NoStepEditor()

    def object_current_step_update_from_current_program_changed(self, info):
        """
        Make selected step from the current program list the active step.
        """
        if info.initialized:
            info.object.current_step.step = info.object.current_program.program.selected[0].step

    # --------------------------------------------------------------------------
    # Handle the current program to display.
    # --------------------------------------------------------------------------

    def make_program_active(self, info, program):
        """ Ensure there is a proper Program editor and make the Program active. """
        if isinstance(info.object.current_program, programs.ProgramEditor):
            info.object.current_program.program = program
        else:
            info.object.current_program = programs.ProgramEditor(program=program)

    def object_current_program_update_changed(self, info):
        """ Determine which Program to display in the Program Editor. """
        if info.object.all_programs.selected:
            # There is a Program selection.
            self.make_program_active(info, info.object.all_programs.selected[0])
        else:
            # There is no Program selection.
            # Is the Program shown last no longer available?
            if info.object.current_program.program not in info.object.all_programs.programs:
                try:
                    self.make_program_active(info, info.object.all_programs.programs[0])
                except IndexError:
                    # Nothing there to show.
                    info.object.current_program = programs.NoProgramEditor()

    # --------------------------------------------------------------------------
    # Handle the current well to display.
    # --------------------------------------------------------------------------

    def make_well_active(self, info, well):
        if isinstance(info.object.current_well, plates.WellProgramsViewer):
            info.object.current_well.well = well
        else:
            info.object.current_well = plates.WellProgramsViewer(well=well)

    def object_current_well_updated_changed(self, info):
        """ Determine which well's programs to display. """
        active_well = info.object.plate.active_well
        if active_well is None:
            info.object.current_well = plates.NoWellProgramsViewer()
        else:
            self.make_well_active(info, active_well)

    def object_programs_updated_changed(self, info):
        """Update right-click menus for the all_steps and all_programs lists."""

        # Menu items for all_steps
        handler_all_steps = info.all_steps._ui.handler
        handler_all_steps.populate_rightclick_menu(info.all_steps._ui.info)

        # Menu items for all_programs
        handler_all_programs = info.all_programs._ui.handler
        handler_all_programs.populate_rightclick_menu(info.all_programs._ui.info)

    def object_steps_in_program_updated_changed(self, info):
        """Add steps which were added in a program to the all_steps list."""
        for program in info.object.all_programs.programs:
            for step_in_prog in program.steps:
                all_step_ids = [step.ID for step in info.object.all_steps.steps]
                if step_in_prog.ID not in all_step_ids:
                    info.object.all_steps.add_step(step_in_prog.step)

    # --------------------------------------------------------------------------
    # Save state maintenance
    # --------------------------------------------------------------------------

    def object_filepath_changed(self, info):
        self.set_title(info)

    def object_dirty_changed(self, info):
        self.set_title(info)

    def set_title(self, info):
        title = 'optoConfig96'
        if info.object.filepath:
            title = title + ' - %s' % os.path.split(info.object.filepath)[-1]
        if info.object.dirty:
            title = title + ' (unsaved changes)'
        info.ui.title = title

    # --------------------------------------------------------------------------
    # Handle Menu Bar actions
    # --------------------------------------------------------------------------

    # FILE Menu
    # *********

    savePromptMessage = Str('There are unsaved changes. Would you like to save?')
    wildcard = Str('optoConfig-96 files (*.op96)|*.op96')
    extension = Str('op96')

    # def save(self, info): specified by SaveHandler

    def promptForSave2(self, info, cancel=True):
        """
        Prompts the user to save the object, if appropriate. Returns the option
        the user picked in the prompt (yes, no, cancel).
        """
        if self.saveObject.dirty:
            code = confirm(info.ui.control, self.savePromptMessage,
                           title="Save now?", cancel=cancel)
            if code == CANCEL:
                return CANCEL
            elif code == YES:
                if not self.save(info):
                    return self.promptForSave(info, cancel)
            elif code == NO:
                return NO
        else:
            return True

    def open(self, info):
        prompt = self.promptForSave2(info)
        if prompt == CANCEL:
            return False

        fileDialog = FileDialog(action='open', title='Open',
                                wildcard=self.wildcard,
                                parent=info.ui.control)
        result = fileDialog.open()

        if result == OK:
            if fileDialog.path == self.saveObject.filepath and not self.saveObject.dirty:
                return True
            else:
                self._open(info, fpath=fileDialog.path)
                return True

    def _open(self, info, fpath):
        fname = os.path.basename(fpath)
        progress = load.OpenProgress()
        progress.filename = fname
        try:
            with open(fpath, 'r') as savefile:
                saved = json.load(savefile)

            info.ui.dispose()
            new = self.saveObject.open(saved, show_progress=True)
            new.dirty = False
            new.filepath = fpath
            new.edit_traits()
            return True
        except Exception:
            error('Could not open file.', title='Could not open file')
            progress.done = True
            self.saveObject.edit_traits()
            return False

    def simulate(self, info):
        player = testmode.ExperimentPlayer(plate=info.object.plate)
        player.edit_traits()

    def export_csv(self, info):
        experiment = experiment_csv.ExperimentCsv(plate=info.object.plate)
        try:
            experiment.export()
        except Exception:
            utils.error('Error: Saving failed!')

    def export(self, info):
        # Close existing export window, if available
        if info.object.code is not None:
            info.object.code.code = None
        try:
            code = export.InoTemplate(
                hardware=info.object.hardware,
                steps=info.object.all_steps.steps,
                programs=info.object.all_programs.programs,
                plate=info.object.plate)
            info.object.sync_trait('filepath', code, '_filepath', mutual=False)
            code.populate_template()
            info.object.code = code
            code.edit_traits(parent=info.ui.control)
            return True
        except export.ExportValidationError as e:
            error(message=str(e), title='Export Error')
            return False

    # CONFIGURATION Menu
    # ******************

    def configure_plate(self, info):
        """
        Show a dialog to configure the plate setting and redraw the UI.
        """
        config = info.object.plate.config.clone_traits()
        # Cloning sets the _require_redraw flag
        config._require_redraw = False
        apply_config = config.edit_traits().result
        if apply_config:
            if config._require_redraw:
                # Updating the plate configuration requires resetting the UI,
                # because the TableEditor changes based on the Grouping setting.
                info.object.plate.selected = []
                info.ui.dispose()
                # Unassign all programs to prevent stray references
                # from programs to assigned wells
                info.object.plate.clear_programs(info.object.plate.wells)
                info.object.plate.config = config
                info.object.edit_traits()
            else:
                info.object.plate.config = config

    def preferences(self, info):
        config.op96Config.options.configure_traits()

    def set_fan_speed(self, info):
        info.object.hardware.edit_traits()

    # HELP Menu
    # **********

    def about(self, info):
        """ Display program information. """
        resources.About().configure_traits()

    def pick_example(self, info):
        """ Let the user pick an example to open. """
        example = resources.Examples()
        result = example.configure_traits()
        if not result:
            return False

        prompt = self.promptForSave2(info)
        if prompt == CANCEL:
            return False

        self._open(info, example.fpath)
        return True

    def user_guide(self, info):
        """ Open the user guide in a browser. """
        import sys, webbrowser
        try:
            if sys.platform == 'darwin':
                fpath = os.path.abspath(resources.USER_GUIDE)
                fpath = 'file://' + fpath
                for browser in ('MacOSX', 'chrome', 'firefox', 'safari'):
                    try:
                        result = webbrowser.get(browser).open(fpath)
                        if result:
                            return True
                    except:
                        continue
                    finally:
                        return False
            else:
                webbrowser.get().open(resources.USER_GUIDE)
                return True
        except:
            utils.error("Opening the user guide failed, but you can find it online on GitHub!")


class Application(CanSaveMixin):
    """ The optoConfig-96 GUI. """

    # --------------------------------------------------------------------------
    # Trait Definitions
    # --------------------------------------------------------------------------

    # All Steps defined by the user, assignable to Programs.
    all_steps = Instance(steps.StepList)

    def _all_steps_default(self):
        return steps.StepList(app=self)

    # The Step currently edited by the user.
    current_step = Instance(steps.AStepEditor)

    def _current_step_default(self):
        return steps.NoStepEditor()

    # All Programs defined by the user, assignable to Wells/LEDs.
    all_programs = Instance(programs.ProgramList)

    def _all_programs_default(self):
        return programs.ProgramList(app=self)

    # The Program currently edited by the user.
    current_program = Instance(programs.AProgramEditor)

    def _current_program_default(self):
        return programs.NoProgramEditor()

    plate = Instance(plates.Plate, ())

    current_well = Instance(plates.AWellProgramsViewer, plates.NoWellProgramsViewer())

    current_well_updated = Event

    @on_trait_change('plate.active_well_changed')
    def fire_current_well_updated(self):
        self.current_well_updated = True

    def _plate_editor_default(self):
        return plates.PlateEditor(plate=self.plate)

    # Hardware configuration of the optoPlate
    hardware = Instance(hardware.Optoplate, ())

    # Template to export to the Arduino
    code = Instance(export.InoTemplate, None)

    # Event to indicate an update of the program list.
    programs_updated = Event

    @on_trait_change('all_programs.updated')
    def fire_programs_updated(self):
        self.programs_updated = True

    # Event to indicate an update in the Steps of a Program.
    steps_in_program_updated = Event

    @on_trait_change('all_programs.programs.steps_updated')
    def fire_steps_in_program_update(self):
        self.steps_in_program_updated = True

    # Event to indicate update of the current step from the all steps list.
    current_step_update_from_all_steps = Event

    @on_trait_change('all_steps.updated')
    def fire_current_step_update_from_all_steps(self):
        # if self.all_steps.selected:
        self.current_step_update_from_all_steps = True

    # Event to indicate update of the current step from the current Program.
    current_step_update_from_current_program = Event

    @on_trait_change('current_program.program.selected')
    def fire_current_step_update_from_current_program(self):
        try:
            if self.current_program.program.selected:
                self.current_step_update_from_current_program = True
        except AttributeError:
            # current_program is a NoProgramEditor
            pass

    # Event to indicate update of the current Program.
    current_program_update = Event

    @on_trait_change('all_programs.updated')
    def fire_current_program_update(self):
        self.current_program_update = True

    # --------------------------------------------------------------------------
    # Save state maintenance
    # --------------------------------------------------------------------------

    dirty = Bool(False)

    @on_trait_change('all_steps.steps.dirtied, all_programs.programs.dirtied, plate.config, plate.wells.leds.program, hardware.fan_speed')
    def set_dirty(self, obj, trait, old, new):
        self.dirty = True

    def save(self):
        hardware = self.hardware.as_dict()
        plateconfig = self.plate.config.as_dict()
        steps = [step.as_dict() for step in self.all_steps.steps]
        programs = [program.as_dict() for program in self.all_programs.programs]
        wells = [well.as_list() for well in self.plate.wells]

        save = {}
        save['hardware'] = hardware
        save['plateconfig'] = plateconfig
        save['steps'] = steps
        save['programs'] = programs
        save['wells'] = wells

        try:
            with open(self.filepath, 'w') as savefile:
                savefile.write(json.dumps(save))
            self.dirty = False
        except Exception:
            utils.error('Error: Saving failed!')

    def open(self, saved, show_progress=True):
        """
        Restore state from a saved file.

        Parameters
        ----------
        saved : dict
            Dictionary with relevant settings, created via `save()`.
        """
        old_step_counter = steps.Step.counter
        steps.Step.counter = utils.BackfillID(start=1)
        old_program_counter = programs.Program.counter
        programs.Program.counter = utils.BackfillID(start=1)

        new = Application()

        if show_progress:
            progress = load.OpenProgress()
            progress.n_steps = len(saved['steps'])
            progress.n_programs = len(saved['programs'])
            progress.n_wells = len(saved['wells'])
            progress.configure_traits()

        try:
            new.hardware = load.load_hardware(saved['hardware'])

            # Because the plate config is updated on loading a saved file, the UI
            # needs to be redrawn. This is done in the handler!
            new.plate.config = load.load_config(saved['plateconfig'])

            new.all_steps.delete_all_steps()
            for i, step in enumerate(load.load_steps(saved['steps'])):
                new.all_steps.add_step(step)
                progress.step = i + 1

            new.all_programs.delete_all_programs()
            for i, program in enumerate(load.load_programs(saved['programs'])):
                new.all_programs.add_program(program)
                progress.program = i + 1

            for i in load.load_wells(saved['wells'], new.plate):
                progress.well = i + 1

            return new
        except Exception:
            # Restore previous counters
            steps.Step.counter = old_step_counter
            programs.Program.counter = old_program_counter
            raise
        finally:
            if show_progress:
                progress.done = True

    # --------------------------------------------------------------------------
    # Status Bar
    # --------------------------------------------------------------------------

    memreqs = Property(depends_on='all_steps.steps.size_update, all_programs.programs.size_update, plate.size_update, hardware.fan_speed')

    @cached_property
    def _get_memreqs(self):
        """ Update memory requirements regularly. """
        try:
            ino = export.InoTemplate(
                hardware=self.hardware,
                steps=self.all_steps.steps,
                programs=self.all_programs.programs,
                plate=self.plate)
            cur = ino.space_requirement()
            total = 28672
            prc = cur / total * 100
            if prc >= 80:
                warn = '[ ! ]'
            elif prc >= 100:
                warn = '[!!!]'
            else:
                warn = ''
            base = 'Memory requirements: approx. {cur} / {total} bytes ({prc:.1f}%) {warn}'
            base = base.format(cur=cur, total=total, prc=prc, warn=warn)
            return base
        except Exception:
            return 'Could not calculate memory requirements. Are there invalid Steps or programs in use?'

    corrections = Property(depends_on='plate.led_types')

    def _get_corrections(self):
        msg = ['Corrections:']
        for led_type in self.plate.led_types:
            led_corrected = '[{name}: {yn}]'.format(
                name=led_type.name,
                yn=('No', 'Yes')[led_type.corrected])
            msg.append(led_corrected)
        return ' '.join(msg)

    fan_speed = Property(depends_on='hardware.fan_speed')

    def _get_fan_speed(self):
        return 'Fan speed: %d' % self.hardware.fan_speed

    # --------------------------------------------------------------------------
    # View
    # --------------------------------------------------------------------------

    def default_traits_view(self):
        menu_file = Menu(
            Action(name='Open ...', action='open'),
            Action(name='Save', action='save', enabled_when='dirty'),
            Action(name='Save As ...', action='saveAs'),
            Action(name='Simulate Experiment ...', action='simulate'),
            Action(name='Export Illumination Scheme (csv) ...', action='export_csv'),
            Action(name='Export Code ...', action='export'),
            # Exitting does not actually terminate the application.
            # Remove the option for now - the user will need to use the OS
            # capabilities to close.
            # Action(name='Exit', action='exit'),
            name='File')

        menu_config = Menu(
            Action(name=' Preferences ...', action='preferences'),
            Action(name=' Configure Plate ...', action='configure_plate'),
            Action(name=' Set Fan Speed ...', action='set_fan_speed'),
            name='Configuration')

        menu_help = Menu(
            Action(name='About optoConfig-96', action='about'),
            Action(name='Examples ...', action='pick_example'),
            Action(name='User Guide ...', action='user_guide'),
            name='Help')

        menubar = MenuBar(menu_file, menu_config, menu_help)
        statusbar = [
            StatusItem(name='memreqs', width=0.5),
            StatusItem(name='corrections', width=0.25),
            StatusItem(name='fan_speed', width=0.0)]

        view = View(
            VSplit(
                HSplit(
                    UItem(
                        'all_steps',
                        editor=InstanceEditor(),
                        style='custom'),
                    Group(
                        UItem('current_step', style='custom')),
                    Group(
                        UItem('current_program', style='custom')),
                    Group(
                        UItem(
                            'all_programs',
                            editor=InstanceEditor(),
                            style='custom'))
                ),
                HSplit(
                    UItem('plate', editor=InstanceEditor(), style='custom'),
                    UItem('current_well', editor=InstanceEditor(), style='custom'))
            ),
            title='optoPlate96 Configurator',
            resizable=True,
            menubar=menubar,
            statusbar=statusbar,
            handler=ApplicationHandler(),
            icon=resources.APPICON
        )
        return view
