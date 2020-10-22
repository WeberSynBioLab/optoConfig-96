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
Arduino code.
"""

import os
import sys
import re
import subprocess
from collections import OrderedDict

import numpy as np

from .ui import *

from . import steps
from . import programs
from . import resources
from . import utils
from . import config

SketchPathExistsWarning = utils.ConfirmationDialog()


def bytesize(integer):
    """ Return the number of bytes required to represent an integer. """
    if integer < 0:
        raise ValueError('Can only convert positive integers to bytes, got %d' % integer)
    if integer < 2 ** 8:
        size = 1
    elif integer < 2 ** 16:
        size = 2
    elif integer < 2 ** 32:
        size = 4
    else:
        raise ValueError('Value %d too large to convert to bytes.' % integer)

    return size


def sizecode(integer):
    """ Return a code to represent a byte size.

    8 bit / 1 byte --> 0
    16 bit / 2 bytes --> 1
    32 bit / 4 bytes --> 2
    """
    d = {1: 0, 2: 1, 4: 2}
    return d[bytesize(integer)]


def to_bytes(integer):
    """ Return a byte sequence representing a number.
    """
    size = bytesize(integer)
    bytes_ = integer.to_bytes(size, 'little')
    return [hex(byte) for byte in bytes_]


def to_array(elements, groupsize=1, spacing=' ', pad=False):
    """ Return elements for assignment to an array.

    Parameters
    ----------
    elements : sequence
        Sequence of prospective array elements. Will be converted to str.
    groupsize : int >= 1
        This many elements are grouped before inserting spacing.
    spacing : str
        Spacing to insert between each group.
    pad : bool
        Pad array elements to the same width?
    """
    elements = [str(element) for element in elements]
    if pad:
        width = len(max(elements, key=lambda x: len(x)))
        elements = [element.rjust(width) for element in elements]
    if not groupsize >= 1:
        raise ValueError('groupsize must be >= 1.')
    out = ['{']
    for n, element in enumerate(elements):
        if n % groupsize == 0:
            out.append(spacing)
        out.append(element)
        if n < len(elements) - 1:
            out.append(', ')
    out.append(spacing)
    out.append('}')
    return ''.join(out)


class ExportValidationError(Exception):
    """ Failed to validate for export to Arduino code. """


class InoMemreq:
    """
    Interface to provide information about memory requirements.
    """

    def progmem(self):
        """ Return bytes required in PROGMEM. """
        raise NotImplementedError

    @staticmethod
    def padding(size, word_size):
        """
        Return padding (in bytes) required to align an element of size `size`
        bytes to `word_size` byte boundaries.
        """
        return (word_size - (size % word_size)) % word_size

    def align(self, elements, word_size=2):
        """
        Return memory requirement (in bytes) required to store `elements` after
        alignment to `word_size` byte boundaries.

        Very (very) approximate calculation.

        Parameters
        ----------
        elements : sequence of integers
            The byte size of each element.
        word_size : int
            Align to boundaries between this many bytes.
        """
        aligned_size = 0
        elements = sorted(elements, reverse=True)
        while elements:
            this_size = elements.pop()
            # Calculate necessary padding
            if self.padding(this_size, word_size) == 0:
                aligned_size += this_size
            else:
                # Check if a suitably sized element is available
                for element in elements:
                    new_size = this_size + element
                    if self.padding(new_size, word_size) == 0:
                        this_size = new_size
                        elements.remove(element)
                        aligned_size += new_size
                        break
                else:
                    aligned_size += this_size + self.padding(this_size, word_size)
        return aligned_size

    def ram(self):
        """ Return bytes required in RAM. """
        raise NotImplementedError


# ------------------------------------------------------------------------------
# STEP EXPORT
# ------------------------------------------------------------------------------


class InoStep(InoMemreq):
    """
    Representation of a Step for the Arduino platform.

    Depending on the magnitude of the Step parameters, different data types are
    necessary for storage. Although all Steps could be stored with the largest
    available types, this would be a waste of the limited Arduino space. Thus,
    a Step is inspected and the relevant data types are determined to create
    a minimally sized byte array.
    """

    def __init__(self, step):
        self.ID = step.ID
        self.name = step.name

        membernames = ('duration', 'pulse_on', 'pulse_off', 'intensity')
        members = OrderedDict()
        for membername in membernames:
            members[membername] = getattr(step, membername)

        # Only store as pulsed step if there actually is pulsing.
        if not step.is_pulsed or step.pulse_on <= 0 or step.pulse_off <= 0:
            members['pulse_on'] = 0
            members['pulse_off'] = 0

        self.members = members

    def size(self):
        """
        Return number of bytes required to store this Step, EXCLUDING the size
        byte.
        """
        sizes = [bytesize(value) for value in self.members.values()]
        return sum(sizes)

    def n_bytes(self):
        """
        Return number of bytes required to store this Step, INCLUDING the size
        byte.
        """

        # 1 byte is required for storing size information for the members:
        # There are 4 members (duration, pulse_on, pulse_off, intensity)
        # Each member can require either 1, 2, or 4 bytes
        # 3 possible options can be stored by 2 bits.
        # 2 bits per member * 4 members = 8 bits = 1 byte to store size information
        n_bytes = 1 + self.size()
        return n_bytes

    def size_byte(self):
        """ Return the byte storing the size information. """
        size_byte = 0

        if len(self.members) > 4:
            raise ValueError('Cannot store more than 4 sizes in one byte.')

        for i, val in enumerate(self.members.values()):
            b = sizecode(val)
            b = b << (6 - i * 2)
            size_byte += b
        return hex(size_byte)

    def arrayname(self):
        """ Variable name of the byte array. """
        return 'step%d' % self.ID

    def comment(self):
        """ A descriptive comment for the step. """
        comment = '// Step {ID} ({name}); Dur: {dur}, ON: {on}, OFF: {off}, INT: {int}'
        comment = comment.format(
            ID=self.ID,
            name=self.name,
            dur=self.members['duration'],
            on=self.members['pulse_on'],
            off=self.members['pulse_off'],
            int=self.members['intensity'])
        return comment

    def definition(self):
        """ Definition of the byte array. """
        step_bytes = [self.size_byte()]
        for val in self.members.values():
            step_bytes += to_bytes(val)

        step_bytes = to_array(step_bytes)
        defin = 'const byte %s[%d] PROGMEM = %s;' % (self.arrayname(), self.n_bytes(), step_bytes)
        defin = self.comment() + '\n' + defin
        return defin

    # --------------------------------------------------------------------------
    # InoMemreq Interface
    # --------------------------------------------------------------------------

    def progmem(self):
        return [self.n_bytes()]

    def ram(self):
        return 0


class InoNullstep(InoStep):
    def __init__(self):
        super().__init__(steps.nullstep)

    def arrayname(self):
        return 'nullstep'


class InoStepCollection(InoMemreq):
    def __init__(self, steps=None, validate=True):
        self.steps = [InoNullstep()]
        for step in steps:
            self.add(step, validate=validate)

    def add(self, step, validate=True):
        if validate and step.invalid:
            msg = '\n'.join([
                'There are invalid Steps in use.',
                'They are highlighted in red in the Steps list.',
                'Hover over the Step to display the cause of invalidity.'
            ])
            raise ExportValidationError(msg)
        else:
            inostep = InoStep(step)
            self.steps.append(inostep)
            return inostep

    def export(self):
        step_export = []
        for step in self.steps:
            step_export.append(step.definition())
        return '\n'.join(step_export)

    # --------------------------------------------------------------------------
    # InoMemreq Interface
    # --------------------------------------------------------------------------

    def progmem(self):
        progmem_steps = []
        for step in self.steps:
            progmem_steps += step.progmem()
        return progmem_steps

    def ram(self):
        return 0


# ------------------------------------------------------------------------------
# PROGRAM EXPORT
# ------------------------------------------------------------------------------


class InoProgram(InoMemreq):
    """
    Representation of an array for storing a Program.

    Depending on the length of the Program, different data types are necessary
    for storage. Although all Programs could be stored with the largest
    available types, this would be a waste of the limited Arduino space. Thus,
    a Program is inspected and the relevant data types are determined.
    """

    def __init__(self, program):
        self.ID = program.ID
        self.name = program.name
        self.steps = []
        for step in program.steps:
            if step.ID == 0:
                step_name = 'nullstep'
            else:
                step_name = 'step%d' % step.ID
            self.steps.append(step_name)

        # By default, the Arduino code will repeat the last step after all steps
        # are complete.
        # To turn off the LED after the end, add the nullstep
        if program._after_end == 'off':
            self.steps.append('nullstep')

    def __len__(self):
        return len(self.steps)

    def arrayname(self):
        return 'program%d' % self.ID

    def comment(self):
        """ Return a descriptive comment for the program. """
        comment = '// Program {ID} ({name}) with {n_steps} steps'
        comment = comment.format(ID=self.ID, name=self.name, n_steps=len(self))
        return comment

    def definition(self):
        defin = 'const byte* const {arrname}[{n_steps}] PROGMEM = {arr};'
        defin = defin.format(
            arrname=self.arrayname(),
            n_steps=len(self),
            arr=to_array([step for step in self.steps]))
        return self.comment() + '\n' + defin

    # --------------------------------------------------------------------------
    # InoMemreq Interface
    # --------------------------------------------------------------------------

    def progmem(self):
        # One pointer (2 bytes) per step
        return [len(self) * 2]

    def ram(self):
        return 0


class InoNullprogram(InoProgram):
    def __init__(self):
        super().__init__(programs.nullprogram)

    def arrayname(self):
        return 'nullprogram'


class InoProgramCollection(InoMemreq):
    def __init__(self, programs=None, validate=True):
        self.programs = [InoNullprogram()]
        if programs is not None:
            for program in programs:
                self.add(program, validate=validate)

    def __len__(self):
        return len(self.programs)

    def program_array(self):
        """ Definition of the array storing the pointers to the Programs. """
        pointers = [program.arrayname() for program in self.programs]
        array = 'const byte* const* const PROGRAMS[N_PROGS] PROGMEM = {arr};'
        array = array.format(arr=to_array(pointers))
        return array

    def size_array(self):
        """
        Definition of the array storing the sizes (number of steps) of the
        Programs.
        """
        sizes = [len(program) for program in self.programs]
        array = 'const uint8_t PROGRAM_SIZES[N_PROGS] PROGMEM = {arr};'
        array = array.format(arr=to_array(sizes))
        return array

    def n_progs_var(self):
        """
        Constant to save number of defined programs. This is necessary to create
        the array which saves information about step advancement.
        """
        n_progs = 'const uint16_t N_PROGS = {n_progs};'
        n_progs = n_progs.format(n_progs=len(self))
        return n_progs

    def add(self, program, validate=True):
        if validate and program.invalid:
            msg = '\n'.join([
                'There are invalid programs in use.',
                'They are highlighted in red in the program list.',
                'Hover over the program to display the cause of invalidity.'
            ])
            raise ExportValidationError(msg)
        else:
            inoprog = InoProgram(program)
            self.programs.append(inoprog)
            return inoprog

    def export(self):
        program_export = []
        for program in self.programs:
            program_export.append(program.definition())
        program_export.append(self.n_progs_var())
        program_export.append(self.program_array())
        program_export.append(self.size_array())
        return '\n'.join(program_export)

    # --------------------------------------------------------------------------
    # InoMemreq Interface
    # --------------------------------------------------------------------------

    def progmem(self):
        progmem_programs = []
        for program in self.programs:
            progmem_programs += program.progmem()
        progmem_prgsizes = len(self)
        progmem_pointers = len(self) * 2
        return progmem_programs + [progmem_prgsizes] + [progmem_pointers]

    def ram(self):
        return 0


# ------------------------------------------------------------------------------
# PLATE EXPORT
# ------------------------------------------------------------------------------


class InoPlate(InoMemreq):
    def __init__(self, plate, index_map, validate=True):
        self.wells = []
        self.n_leds = 0
        self.index_map = index_map
        self.initialized = False
        self.add(plate, validate=validate)

    def plate_array(self):
        """ Definition of the array storing the program for each LED. """
        well_arrays = [to_array(well_prgs) for well_prgs in self.wells]
        well_arrays = to_array(well_arrays, spacing='\n    ')
        array = 'const uint16_t PROGRAM_IDS[96][{n_leds}] PROGMEM = {arr};'
        array = array.format(n_leds=self.n_leds, arr=well_arrays)
        return array

    def add(self, plate, validate=True):
        if self.initialized:
            raise ExportValidationError('Plate was already defined.')

        self.n_leds = len(plate.led_types)
        for well in plate.wells:
            well_prgs = []
            for led in well.leds:
                if led.program:
                    gui_prg_id = led.program.ID
                    arduino_prg_id = self.index_map[gui_prg_id]
                else:
                    arduino_prg_id = 0
                well_prgs.append(arduino_prg_id)
            self.wells.append(well_prgs)
        self.initialized = True

    def export(self):
        return self.plate_array()

    def n_colors_var(self):
        return 'const uint8_t N_COLORS = %d;' % self.n_leds

    # --------------------------------------------------------------------------
    # InoMemreq Interface
    # --------------------------------------------------------------------------

    def progmem(self):
        assign_array = 96 * self.n_leds * 2
        return [assign_array]

    def ram(self):
        return 0


# ------------------------------------------------------------------------------
# LED TYPES EXPORT
# ------------------------------------------------------------------------------


class InoLedType:
    def __init__(self, led_type, led_id):
        self.ID = led_id
        self.name = led_type.name
        self.corrected = led_type.corrected
        self.correction_factors = led_type.correction_factors

    def arrayname(self):
        if self.corrected:
            return 'CORR_FCTRS_LED%d' % self.ID
        else:
            return 'nullptr'

    def correction_array(self):
        if not self.corrected:
            return None
        else:
            values = np.clip(self.correction_factors, 0, 1)
            # Rescale from float to 16 bit integers to save space.
            # The maximum intensity for LEDs is 4095:
            # 4095 / (2^16 -1) < 1, thus, this is enough precision.
            values *= (2**16 - 1)
            values = values.astype(np.uint16)
            values = to_array(values.flatten().tolist(), groupsize=12, spacing='\n    ', pad=True)
            return 'const uint16_t %s[96] PROGMEM = %s;' % (self.arrayname(), values)

    def progmem(self):
        if not self.corrected:
            return [0]
        else:
            return [96 * 2]


class InoLedTypeCollection(InoMemreq):
    def __init__(self, led_types, validate=True):
        self.initialized = False
        self.led_types = []
        for led_id, led_type in enumerate(led_types):
            self.add(led_type, led_id, validate=validate)
        self.any_corrected = any([led.corrected for led in self.led_types])
        self.initialized = True

    def __len__(self):
        return len(self.led_types)

    def add(self, led_type, led_id, validate=True):
        if self.initialized:
            raise ExportValidationError('LEDs were already defined.')
        elif validate and led_type.invalid:
            raise ExportValidationError('There are invalid LED types.')
        else:
            inoled = InoLedType(led_type, led_id)
            self.led_types.append(inoled)
            return inoled

    def export_correction_arrays(self):
            arrays = [led.correction_array() for led in self.led_types if led.correction_array()]
            pointers = [led.arrayname() for led in self.led_types]
            pointer_array = 'const uint16_t* const CORRECTION_FACTORS[{n_leds}] = {arr};'
            pointer_array = pointer_array.format(n_leds=len(self), arr=to_array(pointers))
            return '\n'.join(arrays + [pointer_array])

    def export_correction_function(self):
        if self.any_corrected:
            funcall = """
// Get pointer to correction factors. If it is a nullptr, no
// correction is performed.
const uint16_t* const corr_fctr_ptr = CORRECTION_FACTORS[color];
if (corr_fctr_ptr)
{
    new_int = correct_intensity(new_int, well, corr_fctr_ptr);
}""".strip()
            return funcall
        else:
            return '// No LED correction applied'

    # --------------------------------------------------------------------------
    # InoMemreq Interface
    # --------------------------------------------------------------------------

    def progmem(self):
        corrections_pointers = 2 * len(self)
        corrections_base = 0
        if self.any_corrected:
            corrections_base = 1049
        correction_arrays = []
        for led in self.led_types:
            correction_arrays += led.progmem()
        return correction_arrays + [corrections_base, corrections_pointers]

    def ram(self):
        return 0


# ------------------------------------------------------------------------------
# HARDWARE EXPORT
# ------------------------------------------------------------------------------


class InoHardware:
    def __init__(self, hardware, validate=True):
        self.initialized = False
        self.fan_speed = 0
        self.add(hardware, validate=validate)

    def hardware_settings(self):
        code = '// Fan Speed\n'
        code += 'pinMode(11, OUTPUT);\n'
        code += 'analogWrite(11, {fan_speed});'.format(fan_speed=self.fan_speed)
        return code

    def add(self, hardware, validate=True):
        if self.initialized:
            raise ExportValidationError('Hardware was already defined.')

        self.fan_speed = hardware.fan_speed
        self.initialized = True

    def export(self):
        return self.hardware_settings()

# ------------------------------------------------------------------------------
# OUTPUT ARDUINO CODE
# ------------------------------------------------------------------------------


class InoTemplateHandler(Handler):
    def object_code_changed(self, info):
        """ Close the window when it is no longer needed. """
        if info.initialized:
            if info.object.code is None:
                info.ui.dispose()


class InoTemplate(utils.Updateable, InoMemreq):
    # The generated Arduino code
    code = Either(Code, None)

    hardware = Instance(InoHardware)
    steps = Instance(InoStepCollection)
    programs = Instance(InoProgramCollection)
    plate = Instance(InoPlate)

    def __init__(self, hardware, steps, programs, plate, validate=True):
        self.hardware = InoHardware(hardware, validate=validate)
        # Only export programs which are actually used
        exp_programs = []
        for program in programs:
            if program.is_used:
                exp_programs.append(program)
        self.programs = InoProgramCollection(exp_programs, validate=validate)
        # Re-assign IDs, because they are actually used for indexing.
        # Build an index map to update IDs for LED assignments
        # index_map[id_before] = id_final
        index_map = {}
        for i, ino_prog in enumerate(self.programs.programs):
            index_map[ino_prog.ID] = i
            ino_prog.ID = i

        # Only export steps which are actually used
        exp_steps = []
        for step in steps:
            if step.is_used:
                exp_steps.append(step)
        self.steps = InoStepCollection(exp_steps, validate=validate)
        self.plate = InoPlate(plate, index_map, validate=validate)
        self.led_types = InoLedTypeCollection(plate.led_types, validate=validate)
        self.done_after = plate.done_after()

    # Path to the Arduino IDE executable
    ide_path = Property

    def _get_ide_path(self):
        options_path = config.op96Config['arduino_path']
        if sys.platform == 'win32':
            return os.path.join(os.path.split(options_path)[0], 'arduino_debug.exe')
        if sys.platform == 'darwin':
            return os.path.join(options_path, 'Contents', 'MacOS', 'Arduino')
        else:
            return options_path

    # Version information about a path.
    path_versions = Dict

    def query_version(self):
        """
        Query the version of an Arduino executable and store it in
        `self.path_versions`.
        """
        try:
            version = self.path_versions[self.ide_path]
            if version is None:
                raise KeyError
        except KeyError:
            self.start_update()
            try:
                result = self.get_arduino_output(['--version'])
                version = re.search(r'Arduino.*(\d+\.\d+.\d+)', result).groups()[0]
                version = version.split('.')
                version = tuple([int(x) for x in version])
                self.path_versions[self.ide_path] = version
            except (FileNotFoundError, PermissionError, OSError):
                msg = 'Could not determine the version of the Arduino IDE. Check if the correct path is set under Configuration > Preferences.'
                msg += '\nIf correcting the path does not resolve the problem, please open the Arduino IDE manually and copy the code into a new sketch.'
                utils.error(message=msg, title='Could not open IDE')
                version = None
            finally:
                self.stop_update()

        return version

    @staticmethod
    def version_valid(version):
        # Skip version check for now.
        # return version in constants.ARDUINO_TESTED_VERSIONS
        return True

    def get_arduino_output(self, cli_options):
        """
        Get output from the Arduino executable.

        Parameters
        ----------
        cli_options : list
            Command line options to pass to the arduino executable.
        """
        cmd = [self.ide_path] + cli_options
        result = subprocess.check_output(cmd).decode('ascii')

        # The result may contain log4j output. Try to get rid of those
        # disturbances.
        result = result.splitlines()
        result = [line for line in result if 'log4j' not in line]

        if len(result) == 1:
            return result[0].strip()
        else:
            # ambivalent or no result
            return ''

    # Path to the Arduino Sketchbook
    sketchbook_path = Property

    @cached_property
    def _get_sketchbook_path(self):
        result = self.get_arduino_output(['--get-pref', 'sketchbook.path'])
        sketchbook_path = os.path.normpath(result)
        if not os.path.exists(sketchbook_path):
            msg = "The Arduino Sketchbook path was detected at '%s', but it does not exist." % sketchbook_path
            msg += '\nPlease open the Arduino IDE manually and copy the generated code into a new sketch.'
            error(msg, 'Sketchbook path not found.')
            return None
        else:
            return sketchbook_path

    # Path to the underlying .op96 file, if available.
    _filepath = Str

    to_ide = Button(
        label='Open in IDE',
        tooltip='Open the generated Code in the Arduino IDE.')

    view = View(
        UItem('code', editor=CodeEditor(lexer='cpp'), style='readonly'),
        HGroup(
            UItem('to_ide')),
        handler=InoTemplateHandler(),
        title='Arduino Code')

    @staticmethod
    def replace_tag(line, tag, replacement):
        indent = ' ' * line.find(tag)
        replaced = []
        for rpl_line in replacement.splitlines():
            replaced.append(indent + rpl_line)
        return '\n'.join(replaced) + '\n'

    def populate_template(self):
        template = os.path.join(resources.search_path, 'arduino_template.cpp')

        tag_replace = {
            '// OPTOPLATE_CONFIG_HARDWARE': self.hardware.export(),
            '// OPTOPLATE_CONFIG_STEPS': self.steps.export(),
            '// OPTOPLATE_CONFIG_PROGRAMS': self.programs.export(),
            '// OPTOPLATE_CONFIG_WELLS': self.plate.export(),
            '// OPTOPLATE_CONFIG_CORRECTION_FACTORS': self.led_types.export_correction_arrays(),
            '// OPTOPLATE_CONFIG_PERFORM_INTENSITY_CORRECTION': self.led_types.export_correction_function(),
            '// OPTOPLATE_CONFIG_DONE_AFTER': self.done_after_var(),
            '// OPTOPLATE_CONFIG_N_ADVANCED_ARR_SIZE': self.n_advanced_arr_size_var(),
            '// OPTOPLATE_CONFIG_N_COLORS': self.plate.n_colors_var()
        }
        populated = []
        with open(template, 'r') as tmpl:
            for line in tmpl.readlines():
                for tag, replacement in tag_replace.items():
                    if tag in line:
                        line = self.replace_tag(line, tag, replacement)
                populated.append(line)

        populated = ''.join(populated)
        self.code = populated

        return tmpl

    def inopath(self):
        """
        Build an Arduino sketch path from the _filepath attribute, or make one
        from scratch.
        """
        if self.sketchbook_path is None:
            return None

        if self._filepath:
            ino_basename = os.path.split(os.path.splitext(self._filepath)[0])[-1]
            ino_path = os.path.join(self.sketchbook_path, ino_basename)

            if os.path.exists(ino_path):
                msg = 'An Arduino sketch already exists at %s.' % ino_path
                msg += '\nOverwrite?'
                if SketchPathExistsWarning(message=msg) == utils.YES:
                    return ino_path
                else:
                    return None
            else:
                return ino_path

        else:
            i = 1
            while True:
                ino_basename = 'optoplate96_config_%04d' % i
                ino_path = os.path.join(self.sketchbook_path, ino_basename)
                if not os.path.exists(ino_path):
                    return ino_path
                i += 1

    def _to_ide_changed(self):
        """ Try to send the code to the Arduino IDE. """
        # Skip version check, just make sure we find the IDE
        version = self.query_version()
        if version is None:
            return False

        try:
            inopath = self.inopath()
            if inopath is not None:
                self.start_update()
                try:
                    os.makedirs(inopath)
                except FileExistsError:
                    pass
                fname = os.path.split(inopath)[-1] + '.ino'
                fpath = os.path.join(inopath, fname)
                with open(fpath, 'w') as f:
                    f.write(self.code)
                ide_path = config.op96Config['arduino_path']
                subprocess.Popen([ide_path, os.path.join(inopath, fname)])
        except PermissionError:
            msg = 'The Arduino IDE could not be opened due to a permission error.'
            msg += '\nPlease open the Arduino IDE manually and copy the code into a new sketch.'
            utils.error(message=msg, title='Could not open IDE')
        except Exception:
            raise
            msg = 'The Arduino IDE could not be opened. Check if the correct path is set under Configuration > Preferences.'
            msg += '\nIf correcting the path does not resolve the problem, please open the Arduino IDE manually and copy the code into a new sketch.'
            utils.error(message=msg, title='Could not open IDE')
        finally:
            self.stop_update()
        return True

    def done_after_var(self):
        return 'static const uint32_t s_done_after = %d;' % self.done_after

    def n_advanced_arr_size_var(self):
        """
        Create a constant to store the size of an array representing whether a
        step was advanced in the current loop.

        To save memory, this is done in a bit array. The required number of bytes
        is given by the stored programs (which will never exceed 289 -- at most
        288 programs (one per well and led), plus the nullprogram.)
        """
        x = int(np.ceil(len(self.programs) / 8))
        return 'const uint16_t N_ADVANCED_ARR_SIZE = %d;' % x

    # --------------------------------------------------------------------------
    # InoMemreq Interface
    # --------------------------------------------------------------------------

    def progmem(self):
        # Base without any Steps or programs defined
        base = [6705]
        # If floating point division is included, this will also raise the sketch
        # size
        float_required = False
        if self.hardware.fan_speed not in (0, 255):
            # Setting anything than 0 or 255 requires massively more space?
            base.append(296)
        base.append(bytesize(self.done_after))
        return base + self.steps.progmem() + self.programs.progmem() + self.plate.progmem() + self.led_types.progmem()

    def space_requirement(self):
        return self.align(self.progmem())

    def ram(self):
        return self.steps.ram() + self.programs.ram() + self.plate.ram()
