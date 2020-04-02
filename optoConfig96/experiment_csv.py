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
Utilities for handling export of a GUI-defined optoPlate configuration to
a csv file for later reference of the illumination parameters.
"""

import csv

from .ui import *
from pyface.api import FileDialog, CANCEL

from . import plates


class ExperimentCsv(HasTraits):
    """
    Allow exporting a csv with information about the experiment's illumination
    parameters
    """

    # The plate with the defined experiment
    plate = Instance(plates.Plate)

    filepath = File()

    def generate_csv(self):
        pass

    def export(self):
        dialog = FileDialog(action='save as', title='Export Experiment',
                                wildcard='csv files (*.csv)|*.csv')
        dialog.open()
        path = dialog.path
        if not path.endswith('.csv'):
            path += '.csv'
        with open(path, 'w') as f:
            fieldnames = [
                'well',
                'led',
                'program',
                'program_id',
                'total_steps',
                'step',
                'step_no',
                'step_id',
                'step_start_time',
                'step_duration',
                'step_intensity',
                'step_pulsed',
                'step_pulse_on',
                'step_pulse_off',
                'step_repeat']
            writer = csv.DictWriter(f, fieldnames=fieldnames, restval='None')
            writer.writeheader()

            for well_group in self.plate.well_groups:
                led_row = {'well': well_group.position}
                well = well_group.wells[0]
                for led in well.leds:
                    led_row['led'] = led.name
                    if led.program:
                        program_row = {}
                        program_row['program'] = led.program.name
                        program_row['program_id'] = led.program.ID
                        program_row['total_steps'] = len(led.program.steps)
                        prg_does_repeat = led.program._after_end == 'repeat'
                        program_row.update(led_row)
                        if len(led.program.steps) == 0:
                            # Program has no Steps, write now
                            writer.writerow(program_row)
                        for step_no, step in enumerate(led.program.steps):
                            program_row['step'] = step.name
                            program_row['step_no'] = step_no + 1
                            program_row['step_id'] = step.ID
                            step_start = sum(step.duration for step in led.program.steps[:step_no])
                            program_row['step_start_time'] = step_start
                            program_row['step_duration'] = step.duration
                            program_row['step_intensity'] = step.intensity
                            program_row['step_pulsed'] = ['no', 'yes'][step.is_pulsed]
                            program_row['step_pulse_on'] = step.pulse_on
                            program_row['step_pulse_off'] = step.pulse_off
                            is_last_step = step_no == len(led.program.steps) - 1
                            step_does_repeat = prg_does_repeat and is_last_step
                            program_row['step_repeat'] = ['no', 'yes'][step_does_repeat]
                            writer.writerow(program_row)
                    else:
                        writer.writerow(led_row)



