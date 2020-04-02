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
Assistants for creating multiple steps at once.
"""

import numpy as np

from .ui import *
from .steps import BaseStep, Step, StepHandler
from .programs import Program


class InterpolateStepAssistantHandler(Handler):
    def close(self, info, is_ok):
        if is_ok:
            info.object.interpolate_steps()
        return True


class InterpolateStepAssistant(HasTraits):
    """
    Allow automatic interpolation of parameters and automatically create Steps.
    """

    # The step list to modify
    steplist = Any

    # The program list to modify
    programlist = Any

    params = ('intensity', 'duration', 'pulse_on', 'pulse_off')

    # Take initial parameters from template steps
    template_start = Instance(BaseStep, None)
    template_end = Instance(BaseStep, None)

    # Interpolate between parameters for two steps
    step_start = Instance(BaseStep, ())
    step_end = Instance(BaseStep, ())

    # Number of interpolation steps
    n = UInt(1, tooltip='Number of Steps to generate.')

    assign_each_to_program = Bool(False, tooltip='Assign each generated Step to its own program?')

    assign_all_to_program = Bool(False, tooltip='Assign all generated Steps to one common program?')

    # Name prefix for generated steps
    name = Str('Interpolation', tooltip='Prefix for the name of generated Steps.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.template_start is not None:
            self.template_start.copy_params(self.step_start)
        if self.template_end is not None:
            self.template_end.copy_params(self.step_end)

    # --------------------------------------------------------------------------
    # View
    # --------------------------------------------------------------------------

    def default_traits_view(self):
        view = View(
            Item('name'),
            HGroup(
                Group(
                    UItem('step_start', editor=InstanceEditor(view='no_pulsed_view'), style='custom'),
                    label='Start values', show_border=True),
                Group(
                    UItem('step_end', editor=InstanceEditor(view='no_pulsed_view'), style='custom'),
                    label='End values', show_border=True)),
            Item('n', label='Interpolation steps'),
            VGroup(
                Item('assign_all_to_program'),
                Item('assign_each_to_program')),
            buttons=OKCancelButtons,
            handler=InterpolateStepAssistantHandler(),
            kind='livemodal',
            title='Define interpolated Steps'
        )
        return view

    def set_start(self, param, value):
        setattr(self.step_start, param, value)

    def set_end(self, param, value):
        setattr(self.step_end, param, value)

    def interpolate_values(self, param, start, end):
        interpolated = np.linspace(start, end, self.n)

        if param in ('duration', 'pulse_on', 'pulse_off'):
            # Round to nearest multiple of 100 for time parameters
            interpolated = np.round(interpolated / 100) * 100

        interpolated = interpolated.astype(np.int, copy=False)
        return interpolated

    def interpolate_steps(self):
        steps = [Step() for i in range(self.n)]
        interp_params = {}
        for param in self.params:
            start = getattr(self.step_start, param)
            end = getattr(self.step_end, param)
            interp_params[param] = self.interpolate_values(param, start, end)
        for i in range(self.n):
            step = steps[i]
            for param, values in interp_params.items():
                setattr(step, param, values[i])
            if step.pulse_on != 0 or step.pulse_off != 0:
                step.is_pulsed = True
            pad_n = len(str(self.n))
            number = '%0.{n}d'.format(n=pad_n)
            step.name = self.name + '_' + number % (i + 1)
        self.steplist.steps += steps

        if self.assign_all_to_program:
            program = Program()
            program.name = self.name + '_program'
            program.add_steps(steps)
            self.programlist.programs.append(program)

        if self.assign_each_to_program:
            programs = []
            for step in steps:
                program = Program()
                program.name = step.name + '_program'
                program.add_step(step)
                programs.append(program)
            self.programlist.programs += programs


class SetAllAssistantHandler(StepHandler):
    def init(self, info):
        """ Initialize the `_set` attributes to False.

        When creating the window for the Step handler, True booleans are updated,
        which automatically sets the `_set` attribute to True. Because this is
        undesirable, the `_set` attributes are explicitly set to False again.
        """
        for param in info.object.params:
            setattr(info.object, param + '_set', False)
        return True

    def close(self, info, is_ok):
        if is_ok:
            info.object.set()
        return True


class SetAllAssistant(BaseStep):
    # The step list to modify
    steplist = Any

    # Step from which to take initial values
    template = Instance(Step, None)

    params = ('intensity', 'duration', 'is_pulsed', 'pulse_on', 'pulse_off')

    def __init__(self, *args, **kwargs):
        for param in self.params:
            self.add_trait(param + '_set', Bool)
        super().__init__(*args, **kwargs)
        if self.template is not None:
            self.template.copy_params(self)
        for param in self.params:
            setattr(self, param + '_set', False)

    def __setattr__(self, name, value):
        if name in self.params:
            super().__setattr__(name + '_set', True)
        super().__setattr__(name, value)

    def set(self):
        """ Set parameters of selected steps. """
        d = {}
        for param in self.params:
            if getattr(self, param + '_set') is True:
                d[param] = getattr(self, param)
                if param in ('duration', 'pulse_on', 'pulse_off'):
                    d[param + '_unit'] = getattr(self, param + '_unit')
        # Set update states for involved objects, so they only get updated
        # once verything has been set.
        self.steplist.start_update('updated')
        updating_programs = []
        for step in self.steplist.selected:
            for program in step.in_programs:
                updating_programs.append(program)
                program.start_update('steps_updated')
            for param, value in d.items():
                setattr(step, param, value)
        for program in updating_programs:
            program.stop_update('steps_updated')
        self.steplist.stop_update('updated')

    def default_traits_view(self):
        view = View(
            VGroup(
                HGroup(
                    Item(
                        'duration_ui',
                        editor=InstanceEditor(),
                        style='custom',
                        label='Duration'),
                    Spring(),
                    Item('duration_set', label='Set', tooltip='Set Duration?')),
                HGroup(
                    Item(
                        'intensity',
                        editor=RangeEditor(low=0, high=4095),
                        style='custom',
                        label='Intensity'),
                    Spring(),
                    Item('intensity_set', label='Set', tooltip='Set Intensity?')),
                HGroup(
                    Item('is_pulsed'),
                    Spring(),
                    Item('is_pulsed_set', label='Set', tooltip='Set Pulsed state?')),
                HGroup(
                    Item(
                        'pulse_on_ui',
                        editor=InstanceEditor(),
                        style='custom',
                        enabled_when='is_pulsed',
                        label='ON'),
                    Spring(),
                    Item('pulse_on_set', label='Set', tooltip='Set Pulse ON duration?')),
                HGroup(
                    Item(
                        'pulse_off_ui',
                        editor=InstanceEditor(),
                        style='custom',
                        enabled_when='is_pulsed',
                        label='OFF'),
                    Spring(),
                    Item('pulse_off_set', label='Set', tooltip='Set Pulse OFF duration?')),
                layout='normal'),
            handler=SetAllAssistantHandler(),
            kind='livemodal',
            buttons=OKCancelButtons,
            title='Set Parameters for Steps')
        return view


class NameProgramAssistant(HasTraits):
    """
    Allow the user to immediately set a name for a new Program which is created
    from the Step list.
    """

    name = Str
    view = View(
        Item('name'),
        kind='livemodal',
        buttons=OKCancelButtons,
        title='Name for new Program')
