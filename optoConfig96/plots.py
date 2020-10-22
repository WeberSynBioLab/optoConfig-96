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
Functionality to display plots of Steps and programs.
"""

from .ui import *

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

import math
import numpy as np

from . import utils


class StepPlotHandler(Handler):
    def object_xlimits_updated_changed(self, info):
        """ Update selectable display range when Step settings change. """
        info.xlimits.max = info.object.xlimits_max
        info.xlimits.update_editor()


class StepPlot(utils.Updateable):
    # Matplotlib `Figure` object of the current Step.
    figure = Instance(Figure, ())

    # Matplotlib `axes` object of the current Step figure.
    axes = Instance(Axes)

    # Matplotlib `lines` object of the current Step figure
    lines = List(Instance(Line2D), [])

    _is_updating = Bool(False)

    xdata = List(Instance(np.ndarray, [np.array((0, 1))]))
    xdata_max = Property(depends_on='xdata, xdata[]')

    @cached_property
    def _get_xdata_max(self):
        try:
            return max(np.max(xdata) for xdata in self.xdata)
        except ValueError:
            return 1

    xunit = Enum(*utils.TIME_FACTORS.keys())

    ydata = List(Instance(np.ndarray, [np.array((0, 1))]))
    ydata_max = Property(depends_on='ydata, ydata[]')

    @cached_property
    def _get_ydata_max(self):
        try:
            return max(np.max(ydata) for ydata in self.ydata)
        except ValueError:
            return 1

    xlimits = Range(0.0, 2**32 - 1)

    xlimits_min = Float(0.0)
    xlimits_max = Float(1.0)

    _xmin = Float(0.0)
    _xmax = Float(1.0)
    xlimits_updated = Event

    _ymin = Float(0.0)
    _ymax = Float(1.0)
    ylimits_updated = Event

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axes = self.figure.add_subplot(111)
        self.axes.set_ylabel('Intensity / a.u.')
        self.axes.set_xlabel('Time / %s' % self.xunit)
        self.axes.ticklabel_format(scilimits=(-4, 4), useMathText=True)
        self.arrow_right = None
        self.arrow_left = None

        self._xminmaxdisablelistener = False

    def ms_to_unit(self, values):
        return values / utils.TIME_FACTORS[self.xunit]

    def pltdata(self, n):
        xdata_plt = self.ms_to_unit(self.xdata[n])
        ydata_plt = self.ydata[n]
        return xdata_plt, ydata_plt

    def set_xydata(self, xdatas=None, ydatas=None):
        if xdatas is not None:
            self.xdata = utils.ensure_iterable(xdatas)

        if ydatas is not None:
            self.ydata = utils.ensure_iterable(ydatas)

        for line in self.lines:
            line.remove()

        self.lines = []

        for n in range(len(self.xdata)):
            x, y = self.pltdata(n)
            self.lines.append(self.axes.step(x, y, where='post')[0])

        self.axes.set_xlabel('Time / %s' % self.xunit)
        self.update_limits()
        self.wait_for_update()

    def update_xydata(self, n, xdata=None, ydata=None):
        if xdata is not None:
            self.xdata[n] = xdata
            xdata = self.ms_to_unit(xdata)
            self.lines[n].set_xdata(xdata)

        if ydata is not None:
            self.ydata[n] = ydata
            self.lines[n].set_ydata(ydata)

        self.update_limits()
        self.wait_for_update()

    def draw_line(self, n):
        xdata_plt = self.ms_to_unit(self.xdata[n])
        ydata_plt = self.ydata[n]

        self.lines[n].set_data(xdata_plt, ydata_plt)

    @on_trait_change('xunit')
    def update_unit(self):
        self._is_updating = True
        for n in range(len(self.xdata)):
            x, y = self.pltdata(n)
            self.lines[n].set_data(x, y)
        self.axes.set_xlabel('Time / %s' % self.xunit)
        self.update_limits()
        self.draw()

    def update_xlimits(self):
        xlimits_max = self.ms_to_unit(self.xdata_max)
        if math.isclose(xlimits_max, 0, rel_tol=0, abs_tol=1e-7):
            xlimits_max = 1

        self.xlimits_max = xlimits_max
        xmax_new = xlimits_max

        # # Reset display limits
        self._xmin = 0
        self._xmax = min(xmax_new, xlimits_max)

    def update_ylimits(self):
        self.set_ylim(0, max(1, self.ydata_max * 1.1))

    def update_limits(self):
        self.update_xlimits()
        self.update_ylimits()

    @on_trait_change('_xmin, _xmax')
    def _set_xlim(self):
        if self._xminmaxdisablelistener:
            return
        else:
            self._xminmaxdisablelistener = True
        self.set_xlim()
        self._xminmaxdisablelistener = False
        # Set xlimits immediately without waiting
        self.draw()

    def set_xlim(self, xmin=None, xmax=None):
        self._xminmaxdisablelistener = True
        if xmin is not None:
            self._xmin = xmin

        if xmax is not None:
            self._xmax = xmax

        if math.isclose(self._xmax, self._xmin, rel_tol=0, abs_tol=1e-7):
            xmax += 1e-7
            self._xmax = xmax
        self._xminmaxdisablelistener = False
        self.axes.set_xlim(self._xmin, self._xmax)
        self.xlimits_updated = True

    def _set_ylim(self):
        self.set_ylim(self._ymin, self._ymax)

    def set_ylim(self, ymin=None, ymax=None):
        if ymin is None:
            ymin = self._ymin
        if ymax is None:
            ymax = self._ymax

        self.axes.set_ylim(ymin, ymax)
        self.ylimits_updated = True

    @on_trait_change('xlimits_updated, ylimits_updated')
    def draw_exceed_arrows(self):
        """
        Draw arrows to visually indicate that current x axis limits do not
        include the whole data range.
        """
        xmin, xmax = self._xmin, self._xmax
        xdata_max = self.ms_to_unit(self.xdata_max)

        # remove existing arrows
        if self.arrow_right:
            self.arrow_right.remove()
            self.arrow_right = None

        if self.arrow_left:
            self.arrow_left.remove()
            self.arrow_left = None

        # draw new arrow if data range exceeds limits
        if xmax < xdata_max:
            self.arrow_right = self.exceed_arrow(direction='right')

        if xmin > 0:
            self.arrow_left = self.exceed_arrow(direction='left')

    def exceed_arrow(self, direction):
        """
        Return a FancyArrow to indicate that the data range exceeds the axis
        limits.

        Parameters
        ----------

        direction : str, either `right` or `left`
            Direction of the arrow.

        Returns
        -------
        arrow : FancyArrow
        """
        xmin, xmax = self.axes.get_xlim()
        x_range = xmax - xmin
        ymin, ymax = self.axes.get_ylim()
        y_range = ymax - ymin

        length = 0.09 * x_range

        if direction == 'right':
            xstart = xmin + 0.9 * x_range

        if direction == 'left':
            xstart = xmin + 0.1 * x_range
            length *= -1

        arrow = self.axes.arrow(
            xstart, 0.95 * ymax,  # start
            length, 0,   # length
            width=0.01 * y_range, color='red',
            head_width=0.03 * y_range, head_length=0.05 * x_range,
            length_includes_head=True)
        return arrow

    def wait_for_update(self):
        if not self._is_updating:
            self.draw()

    def draw(self):
        try:
            self.figure.canvas.draw()
            self._is_updating = False
        except RuntimeError:
            # If a draw update is requested from a plot object which is no
            # longer shown in the GUI, but which has not been garbage collected
            # yet, a runtime error is raised because the underlying canvas
            # object has already been destroyed.
            pass

    controls_view = View(
        HGroup(
            UItem(
                'xlimits',
                editor=BoundsEditor(
                    low_name='_xmin',
                    high_name='_xmax',
                    format='%.2f')),
            UItem('xunit')),
        handler=StepPlotHandler())


class ArrayHeatmap(HasTraits):
    array = Instance(np.ndarray)

    figure = Instance(Figure)

    title = Str('')

    def _figure_default(self):
        figure = Figure()
        axis = figure.add_subplot(111)
        axis.set_yticks(np.arange(self.array.shape[0]))
        axis.set_xticks(np.arange(self.array.shape[1]))
        axis.set_yticklabels('ABCDEFGH')
        axis.set_xticklabels(np.arange(self.array.shape[1]) + 1)
        axis.set_title(self.title)
        axis.tick_params(top=True, labeltop=True)
        for idx_y, idx_x in np.ndindex(*self.array.shape):
            value = self.array[idx_y, idx_x]
            if value < 0.5:
                color = 'white'
            else:
                color = 'black'
            axis.text(
                idx_x, idx_y, np.round(value, 2),
                ha='center', va='center', color=color)
        heatmap = axis.imshow(self.array, cmap='Greys_r', vmin=0, vmax=1)
        cbar = figure.colorbar(heatmap, fraction=0.031, pad=0.04)
        cbar.ax.set_ylabel('Correction Factor', rotation=-90, va='bottom')
        return figure

    def default_traits_view(self):
        view = View(
            UItem('figure', editor=MPLFigureEditor()),
            buttons=[OKButton],
            kind='modal',
            title='Correction Factors')
        return view
