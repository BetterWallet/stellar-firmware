#
# ur_decoder.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from .ur import UR
from .fountain_encoder import Part as FountainEncoderPart
from .fountain_decoder import FountainDecoder
from .bytewords import Bytewords, Bytewords_Style_minimal
from .utils import drop_first, is_ur_type


class InvalidScheme(Exception):
    pass

class InvalidType(Exception):
    pass

class InvalidPathLength(Exception):
    pass

class InvalidSequenceComponent(Exception):
    pass


class URDecoder:
    def __init__(self):
        self.fountain_decoder = FountainDecoder()
        self._expected_type   = None
        self.result           = None

    @staticmethod
    def decode(s):
        type_, components = URDecoder._parse(s)
        if not components:
            raise InvalidPathLength()
        return URDecoder._decode_by_type(type_, components[0])

    @staticmethod
    def _decode_by_type(type_, body):
        cbor = Bytewords.decode(Bytewords_Style_minimal, body)
        return UR(type_, cbor)

    @staticmethod
    def _parse(s):
        lowered = s.lower()
        if not lowered.startswith('ur:'):
            raise InvalidScheme()
        path       = drop_first(lowered, 3)
        components = path.split('/')
        if len(components) < 2:
            raise InvalidPathLength()
        type_ = components[0]
        if not is_ur_type(type_):
            raise InvalidType()
        return type_, components[1:]

    @staticmethod
    def _parse_seq(s):
        parts = s.split('-')
        if len(parts) != 2:
            raise InvalidSequenceComponent()
        seq_num = int(parts[0])
        seq_len = int(parts[1])
        if seq_num < 1 or seq_len < 1:
            raise InvalidSequenceComponent()
        return seq_num, seq_len

    def _validate_type(self, type_):
        if self._expected_type is None:
            if not is_ur_type(type_):
                return False
            self._expected_type = type_
        return type_ == self._expected_type

    def receive_part(self, s):
        try:
            if self.result is not None:
                return False
            type_, components = URDecoder._parse(s)
            if not self._validate_type(type_):
                return False

            # Single-part
            if len(components) == 1:
                self.result = self._decode_by_type(type_, components[0])
                return True

            if len(components) != 2:
                raise InvalidPathLength()

            seq_num, seq_len = self._parse_seq(components[0])
            cbor = Bytewords.decode(Bytewords_Style_minimal, components[1])
            part = FountainEncoderPart.from_cbor(cbor)
            if seq_num != part.seq_num or seq_len != part.seq_len:
                return False

            if not self.fountain_decoder.receive_part(part):
                return False

            if self.fountain_decoder.is_success():
                self.result = UR(type_, self.fountain_decoder.result_message())
            elif self.fountain_decoder.is_failure():
                self.result = self.fountain_decoder.result_message()

            return True
        except Exception:
            return False

    def is_complete(self):
        return self.result is not None

    def is_success(self):
        return self.result is not None and not isinstance(self.result, Exception)

    def estimated_percent_complete(self):
        return self.fountain_decoder.estimated_percent_complete()

    def result_ur(self):
        return self.result
