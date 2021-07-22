# Implementation of an MPL Figure Editor, after instructions provided by
# Gael Varoquaux at https://docs.enthought.com/traitsui/tutorials/traits_ui_scientific_app.html
# Also takes into account information provided by Brendan Griffin at
# https://www.brendangriffen.com/post/python-gui/ and https://github.com/bgriffen/Python3GUITemplate

from pyface.qt import QtGui

import matplotlib as mpl
mpl.rcParams['backend'] = 'Qt5Agg'
# We want matplotlib to use a QT5 backend
mpl.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from traitsui.qt4.editor import Editor
from traitsui.basic_editor_factory import BasicEditorFactory


class OptoPlateCanvas(FigureCanvas):
    def resizeEvent(self, event):
        """ Keep labels in view on resize. """
        super().resizeEvent(event)
        try:
            self.figure.tight_layout()
        except ValueError:
            # Resize not possible
            pass


class _MPLFigureEditor(Editor):
    scrollable  = True

    def init(self, parent):
        self.control = self._create_canvas(parent)
        self.set_tooltip()

    def update_editor(self):
        pass

    def _create_canvas(self, parent):
        """ Create the MPL canvas. """
        frame = QtGui.QWidget()
        mpl_canvas = OptoPlateCanvas(self.value)
        mpl_canvas.setParent(frame)

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(mpl_canvas)
        frame.setLayout(vbox)

        return frame

class MPLFigureEditor(BasicEditorFactory):

    klass = _MPLFigureEditor
