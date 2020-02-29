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
from pyface.api import ImageResource
from traits.api import *
from traitsui.api import *

search_path = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'resources')

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


class About(HasTraits):

    info = Str

    license = Str

    def _info_default(self):
        from . import version
        ver = version.__version__
        info = 'optoConfig-96, version %s' % ver
        info += '\n\noptoConfig-96 is made available under the GPLv3 license.'
        return info

    def _license_default(self):
        with open(os.path.join(search_path, 'LICENSE.txt')) as flic:
            license = flic.read()
        return license

    view = opView(
        UItem('info', style='readonly'),
        UItem('license', style='custom', width=500, height=500),
        buttons=[OKButton],
        title='About optoConfig-96'
        )
