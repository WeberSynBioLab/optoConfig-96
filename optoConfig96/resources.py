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
Handle image and file resources.
"""

import os
import pkg_resources
from pyface.api import ImageResource
from traits.api import *
from traitsui.api import *

search_path = pkg_resources.resource_filename("optoConfig96", "resources")

APPICON = ImageResource(name='appicon.png', search_path=search_path)

USER_GUIDE = os.path.join(search_path, 'docs', 'optoConfig96_guide.html')


class opView(View):
    """
    Set the default icon.
    """

    icon = Instance(ImageResource, APPICON)


class Examples(HasTraits):
    _available_examples = Property

    def _get__available_examples(self):
        examples_path = os.path.join(search_path, 'examples')
        examples = {}
        for fname in os.listdir(examples_path):
            if fname.endswith('.op96'):
                examples[fname] = (os.path.join(examples_path, fname))
        return examples

    # The user may pick an example to open
    picked = Enum(values='_example_choices', tooltip='Pick an example file to open.')

    _example_choices = Property

    def _get__example_choices(self):
        return list(self._available_examples.keys())

    fpath = Property(depends_on='picked')

    def _get_fpath(self):
        return self._available_examples[self.picked]

    view = opView(
        UItem('picked'),
        title='Pick an example',
        kind='modal',
        buttons=OKCancelButtons
    )


class License(HasTraits):

    license = Str

    def _license_default(self):
        with open(os.path.join(search_path, 'LICENSE.txt')) as flic:
            license = flic.read()
        return license

    view = opView(
        UItem('license', style='readonly'), scrollable=True)


class About(HasTraits):

    info = Str

    license = Instance(License)

    citation = Str('If optoConfig-96 was useful to you, please consider citing the paper:')
    authors = Str('Thomas, OS, Hörner, M & Weber, W:')
    title = Str('A graphical user interface to design high-throughput optogenetic experiments with the optoPlate-96')
    journal = Str('Nat Protoc (2020)')
    doi = Str('https://doi.org/10.1038/s41596-020-0349-x')

    def _info_default(self):
        from . import version
        ver = version.__version__
        info = 'optoConfig-96, version %s' % ver
        info += '\n\noptoConfig-96 is made available under the GPLv3 license.'
        return info

    def _license_default(self):
        return License()

    view = opView(
        UItem('info', style='readonly'),
        Group(
            UItem('citation', style='readonly'),
            UItem('authors', style='readonly', style_sheet='*{font-weight:bold}'),
            UItem('title', style='readonly', style_sheet='*{font-style:italic}'),
            UItem('journal', style='readonly', style_sheet='*{font-style:italic}'),
            UItem('doi'),
            show_border=True
        ),
        UItem('license', editor=InstanceEditor(), style='custom'),
        buttons=[OKButton],
        title='About optoConfig-96',
        resizable=True,
        width=600,
        height=700
)
