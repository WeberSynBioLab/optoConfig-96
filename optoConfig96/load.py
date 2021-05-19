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
Functions for restoring the application state from save data.
"""

from .ui import *
from traitsui.editors.api import ProgressEditor

import numpy as np

from . import steps
from . import programs
from . import plates
from . import hardware


def load_hardware(saved):
    """ Load a saved hardware configuration.

    Parameters
    ----------
    saved : dict
        Output of Optoplate.as_dict(), restored from a JSON dump.
    """
    hw = hardware.Optoplate()
    hw.fan_speed = saved['fan_speed']
    return hw


def load_config(saved):
    """ Load a saved plate configuration.

    Parameters
    ----------
    saved : dict
        Output of PlateConfig.as_dict(), restored from a JSON dump.
    """
    newconfig = plates.PlateConfig()
    newconfig.grouptype = saved['grouptype']
    led_types = []
    for led_type in saved['led_types']:
        correction_factors = led_type['correction_factors']
        if correction_factors is not None:
            correction_factors = np.array(correction_factors)
        led_types.append(plates.LED(
            color=led_type['color'],
            name=led_type['name'],
            correction_factors=correction_factors))

    newconfig.led_types = led_types

    return newconfig


def load_steps(saved):
    """ Load saved steps.

    Parameters
    ----------
    saved : list
        List of outputs of Step.as_dict(), restored from a JSON dump.
    """
    # Order by IDs due to sequetial generation
    saved = sorted(saved, key=lambda step: int(step['ID']))
    for step in saved:
        newstep = steps.Step()
        for key in step.keys():
            if key == 'ID':
                if newstep.ID != step['ID']:
                    raise ValueError('IDs of loaded and generated Step do not match.')

            setattr(newstep, key, step[key])

        yield newstep


def load_programs(saved):
    """ Load saved programs.

    Parameters
    ----------
    saved : list
        List of outputs of Program.as_dict(), restored from a JSON dump.
    """
    # Order by IDs due to sequetial generation
    saved = sorted(saved, key=lambda prog: int(prog['ID']))
    for program in saved:
        newprogram = programs.Program()
        for key in program.keys():
            if key == 'ID':
                if newprogram.ID != program['ID']:
                    raise ValueError('IDs of loaded and generated program do not match.')

            if key == 'steps':
                for step_id in program['steps']:
                    step = steps.Step.counter.get_instance(step_id)
                    newprogram.add_steps(step)
            else:
                setattr(newprogram, key, program[key])

        yield newprogram


def load_wells(saved, plate):
    """ Restore program assignment to wells.

    Parameters
    ----------
    saved : list
        List of outputs of Well.as_list(), restored from a JSON dump.
    plate : Plate
        The Plate instance for which state should be restored.
    """
    for well_n, saved_well in enumerate(saved):
        yield well_n
        newwell = plate.wells[well_n]
        for led_n, led_type in enumerate(plate.led_types):
            program_id = saved_well[led_n]['program']
            if program_id:
                program = programs.Program.counter.get_instance(program_id)
                newwell.assign_program(led_n, program)


class ProgressHandler(Handler):
    def object_done_changed(self, info):
        if info.initialized:
            if info.object.done:
                info.ui.dispose()


class OpenProgress(HasTraits):
    filename = Str

    step = Int(0)
    n_steps = Int

    program = Int(0)
    n_programs = Int

    well = Int(0)
    n_wells = Int

    done = Bool(False)

    def default_traits_view(self):
        view = View(
            Label('Loading %s' % self.filename),
            Item(
                'step', show_label=False, editor=ProgressEditor(
                    message='Loading steps', min=0, max=self.n_steps)),
            Item(
                'program', show_label=False, editor=ProgressEditor(
                    message='Loading programs', min=0, max=self.n_programs)),
            Item(
                'well', show_label=False, editor=ProgressEditor(
                    message='Assigning programs to wells', min=0, max=self.n_wells)),
            title='Loading ...', resizable=True, width=100, handler=ProgressHandler())

        return view
