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
Show animated heatmaps to simulate an experiment in silico.
"""

import time
from threading import Thread
import matplotlib as mpl
from matplotlib.axes import Axes
from matplotlib.figure import Figure

import numpy as np

from .ui import *
from .plates import Plate

from . import utils


class TimeUnitSliderHandler(Handler):
    def object_unit_changed(self, info):
        if info.object.unit == 'ms':
            info.value_out.format = '%d'
            info.object.value_out = 0
            info.value_out._label_lo.setText('0')
            info.value_out._label_hi.setText('%d' % info.object._slider_max)
        else:
            info.value_out.format = '%.3f'
            info.object.value_out = 0.0
            info.value_out._label_lo.setText('0')
            info.value_out._label_hi.setText('%.3f' % info.object._slider_max)

        info.value_out.update_editor()


class TimeUnitSlider(utils.TimeUnit):

    _slider_max = Property(depends_on='unit')

    _time_max = Int

    @cached_property
    def _get__slider_max(self):
        slider_max = self._time_max / self.factors[self.unit]
        # Round up to a precision of 3 decimal places
        slider_max = np.round(slider_max + 0.5 * 10**(-3), 3)
        return slider_max

    def _validate_value_out(self, value):
        return super(utils.TimeUnit, self)._validate_value_out(value)

    view = View(
        HGroup(
            Item(
                'value_out',
                editor=RangeEditor(low=0.0, high_name='_slider_max', mode='slider'),
                show_label=False),
            Item('unit', show_label=False)),
        handler=TimeUnitSliderHandler())


class SliderUpdate:
    def __init__(self, player):
        self._running = True
        self.player = player
        self.lastframe = None

    def stop(self):
        self._running = False

    def update(self):
        while self._running:
            if not self.lastframe:
                self.lastframe = time.time()
                increment = 0
            else:
                # elapsed seconds since last frame
                elapsed = time.time() - self.lastframe
                elapsed_ms = elapsed * 1000
                increment = round(elapsed_ms * self.player.timefactor)
                if increment <= 0:
                    continue
            self.lastframe = time.time()
            new_value = self.player.time + increment
            if new_value >= self.player.time_ui._time_max:
                self.player.time = self.player.time_ui._time_max
                self.stop()
            else:
                self.player.time = new_value


class ExperimentPlayerHandler(Handler):
    def object_startstop_changed(self, info):
        if info.object.updatethread is None:
            info.startstop.control.setText("Start")
        else:
            info.startstop.control.setText("Stop")

    def close(self, info, is_ok):
        if info.object.updatethread is not None:
            info.object.updatethread.stop()
            info.object.updathread = None
        return True


class ExperimentPlayer(HasTraits):
    """
    Display and play animations of optoConfig illumination schemes.
    """

    # The plate to simulate.
    plate = Instance(Plate)

    time = Int

    time_ui = Instance(TimeUnitSlider, args=(Int,))

    def _sync_internals(self):
        self.sync_trait('time', self.time_ui, 'value_base')
        self.sync_trait('time_end', self.time_ui, '_time_max', mutual=False)

    time_end = Property

    def _get_time_end(self):
        return self.plate.done_after()

    maxslider = Range(1, 4095, value=4095, label='Intensity Limit', tooltip='The intensity set here is displayed as the fully saturated LED color.')

    # Factor to speed up time during the simulation
    timefactor = Float(100.0, label='Time Factor', tooltip='Speed of the animation. 1 is real time, less or more than 1 is slower or faster, respectively.')

    startstop = Button('Start')
    updatethread = Instance(SliderUpdate)

    increment = Event

    # Checkboxes to define which LEDs to show.
    led_boxes = []

    # Checkbox to define if corrections should be applied to the shown values.
    apply_corrections = Bool(True, label='Apply Corrections', tooltip='If LEDs have associated correction factors, should they be applied in the simulation?')

    figure = Instance(Figure)
    axis = Instance(Axes)

    def _figure_default(self):
        figure = Figure()
        axis = figure.add_subplot(111)
        self.axis = axis
        n = len(self.plate.config.led_types)
        rowspergroup = 8 / self.plate.nrows
        colspergroup = 12 / self.plate.ncols
        axis.set_yticks(np.arange((n * rowspergroup - 1) * 0.5, 8 * n, n * rowspergroup))
        axis.set_yticklabels('ABCDEFGH')
        axis.set_xticks(np.arange((colspergroup - 1) * 0.5, 12, colspergroup))
        axis.set_xticklabels(np.arange(12) + 1)
        grid_y = np.arange(-0.5, 8 * n, n * rowspergroup)[1::]
        grid_x = np.arange(colspergroup - 1 + 0.5, 12.5, colspergroup)[:-1]
        # Draw gridlines manually; axis.grid gets lost with blitting
        self.gridlines = []
        for y in grid_y:
            self.gridlines.append(axis.axhline(y, color='white', linewidth=2))
            self.gridlines.append(axis.axhline(y, color='black', linewidth=1))
        for x in grid_x:
            self.gridlines.append(axis.axvline(x, color='white', linewidth=2))
            self.gridlines.append(axis.axvline(x, color='black', linewidth=1))
        axis.tick_params(top=True, labeltop=True)
        self.heatmap = self.axis.imshow(
            self.heatmap_data(),
            aspect=1 / len(self.plate.led_types),
            interpolation='nearest')
        return figure

    cmaps = List

    def _cmaps_default(self):
        """ The colormaps to use for the LEDs. """
        cmaps = []
        for led_type in self.plate.config.led_types:
            name = led_type.name
            # Create a cmap from black to the defined LED color
            led_color_end = utils.qt_color_to_rgb(led_type.color)
            led_color_start = (1, 1, 1, 1)
            colors = [led_color_start, led_color_end]
            cmap = mpl.colors.LinearSegmentedColormap.from_list(name, colors, 4095)
            cmaps.append(cmap)
        return cmaps

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Checkboxes to show LED types
        for i, led_type in enumerate(self.plate.config.led_types):
            name = 'ledbox_%d' % i
            self.add_trait(name, Bool(True, label='Show ' + led_type.name))
        self._sync_internals()
        self.plotinit = False

    def get_show_led(self, led_n):
        """ Return True if the specified LED is shown in the heatmap. """
        return getattr(self, 'ledbox_%d' % led_n)

    @on_trait_change('time, maxslider, ledbox+, apply_corrections')
    def update_plot(self):
        self.heatmap.set_data(self.heatmap_data())
        self.axis.draw_artist(self.heatmap)
        for gridline in self.gridlines:
            self.axis.draw_artist(gridline)
        self.figure.canvas.update()

    def timedata(self, led_n, time):
        data = np.zeros((8, 12))
        if not self.get_show_led(led_n):
            return data
        for well in self.plate.wells:
            led = well.leds[led_n]
            data[well.pos_row, well.pos_col] = self.cur_intensity(led, time)
        return data

    def interleave(self, arrays):
        """
        Interleave multiple arrays into one.

        Parameters
        ----------

        arrays : iterable of np.ndarrays of the same shape

        Returns
        -------
        interleaved : `arrays`, interleaved along their first dimension.
        """
        n = len(arrays)
        new_shape = list(arrays[0].shape)
        new_shape[0] = new_shape[0] * n
        interleaved = np.zeros(new_shape, arrays[0].dtype)
        for i, array in enumerate(arrays):
            interleaved[i::n] = array
        return interleaved

    def heatmap_data(self):
        """
        Get the heatmap_data for the current settings.
        """
        arrays = []
        for led_n in range(len(self.plate.led_types)):
            array = self.timedata(led_n, self.time)
            # Apply correction factors, if applicable
            if self.apply_corrections and self.plate.config.led_types[led_n].correction_factors is not None:
                array = array * self.plate.led_types[led_n].correction_factors
            # Colorize
            array = self.cmaps[led_n](array / self.maxslider)
            arrays.append(array)
        n = self.interleave(arrays)
        return n

    def cur_intensity(self, led, time):
        if not led.program:
            return 0
        if led.program:
            step_start = 0
            next_start = 0
            for step_n, step in enumerate(led.program.steps):
                next_start += step.duration
                if time < next_start:
                    break
                if step_n < len(led.program.steps) - 1:
                    step_start = next_start
            else:
                if led.program._after_end == 'off':
                    # The program is over and is not set to repeat the last step
                    return 0

        # There is an active step
        t_step = time - step_start  # time the step was active
        # is_on requires an array of times
        t_step = np.array([t_step])
        if step.is_on(t_step)[0]:
            return step.intensity
        else:
            return 0

    def _startstop_changed(self):
        if self.updatethread is None:
            self.updatethread = SliderUpdate(player=self)
            t = Thread(target=self.updatethread.update)
            t.setDaemon(True)
            t.start()
        else:
            self.updatethread.stop()
            self.updatethread = None

    def _increment_changed(self, old, new):
        self.time_ui.value_out = new

    def default_traits_view(self):
        led_box_items = []
        for i, led_type in enumerate(self.plate.config.led_types):
            led_box_items.append(Item('ledbox_%d' % i))
        view = View(
            VSplit(
                UItem('figure', editor=MPLFigureEditor(), width=500, height=500),
                VGroup(
                    VGroup(
                        Item('time_ui', editor=InstanceEditor(), enabled_when='updatethread is None', style='custom', label='Time'),
                        HGroup(
                            Spring(),
                            Item('timefactor', width=100),
                            UItem('startstop'),
                            Spring(),
                        ),
                        show_border=True, label='Simulation'
                    ),
                    VGroup(
                        Item('maxslider', editor=RangeEditor(mode='slider', low=1, high=4095)),
                        HGroup(*led_box_items),
                        Item('apply_corrections'),
                        show_border=True, label='Display Settings'
                    )
                )
            ),
            buttons=[OKButton],
            kind='livemodal', resizable=True,
            title='Simulate Experiment',
            handler=ExperimentPlayerHandler()
        )
        return view
