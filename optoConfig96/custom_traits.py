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


from traits.api import BaseInt


class UInt(BaseInt):
    default_value = 0

    info_text = 'a positive integer or 0'

    def validate(self, object, name, value):
        value = super().validate(object, name, value)
        if value >= 0:
            return value

        self.error(object, name, value)


class UInt8(BaseInt):
    default_value = 0

    info_text = 'an integer in the range of 0-255'

    def validate(self, object, name, value):
        value = super().validate(object, name, value)
        if (value >= 0 and value <= 255):
            return value

        self.error(object, name, value)


class UInt12(BaseInt):
    default_value = 0

    info_text = 'an integer in the range of 0-4095'

    def validate(self, object, name, value):
        value = super().validate(object, name, value)
        if (value >= 0 and value <= 4095):
            return value

        self.error(object, name, value)


class UInt16(BaseInt):
    default_value = 0

    info_text = 'an integer in the range of 0-65535'

    def validate(self, object, name, value):
        value = super().validate(object, name, value)
        if (value >= 0 and value <= 65535):
            return value

        self.error(object, name, value)


class UInt32(BaseInt):
    default_value = 0

    info_text = 'an integer in the range of 0-4294967295'

    def validate(self, object, name, value):
        value = super().validate(object, name, value)
        if (value >= 0 and value <= 4294967295):
            return value

        self.error(object, name, value)


class UInt32Div100(UInt32):
    default_value = 0

    info_text = 'an integer in the range of 0-4294967295 which is divisible by 100'

    def validate(self, object, name, value):
        value = super().validate(object, name, value)
        if value % 100 == 0:
            return value
        self.error(object, name, value)
