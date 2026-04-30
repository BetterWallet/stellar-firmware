#
# ur_encoder.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from .fountain_encoder import FountainEncoder
from .bytewords import Bytewords, Bytewords_Style_minimal


class UREncoder:
    def __init__(self, ur, max_fragment_len, first_seq_num=0, min_fragment_len=10):
        self.ur = ur
        self.fountain_encoder = FountainEncoder(
            ur.cbor, max_fragment_len, first_seq_num, min_fragment_len
        )

    @staticmethod
    def encode(ur):
        body = Bytewords.encode(Bytewords_Style_minimal, ur.cbor)
        return UREncoder._encode_ur([ur.type, body])

    def is_complete(self):
        return self.fountain_encoder.is_complete()

    def is_single_part(self):
        return self.fountain_encoder.is_single_part()

    def expected_part_count(self):
        return self.fountain_encoder.expected_part_count()

    def next_part(self):
        if self.is_single_part():
            return UREncoder.encode(self.ur)
        part = self.fountain_encoder.next_part()
        seq  = f"{part.seq_num}-{part.seq_len}"
        body = Bytewords.encode(Bytewords_Style_minimal, bytes(part.cbor()))
        return UREncoder._encode_ur([self.ur.type, seq, body])

    @staticmethod
    def _encode_ur(path_components):
        return "ur:" + "/".join(path_components)
