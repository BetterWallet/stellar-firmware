#
# ur.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from .utils import is_ur_type


class InvalidType(Exception):
    pass


class UR:
    def __init__(self, type, cbor):
        if not is_ur_type(type):
            raise InvalidType(f"invalid UR type: {type!r}")
        self.type = type
        self.cbor = cbor

    def __eq__(self, other):
        if other is None:
            return False
        return self.type == other.type and self.cbor == other.cbor
