#
# fountain_encoder.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

import math

from .cbor_lite import CBORDecoder, CBOREncoder
from .fountain_utils import choose_fragments
from .utils import split, crc32_int, xor_into
from .constants import MAX_UINT32, MAX_UINT64


class InvalidHeader(Exception):
    pass


class Part:
    def __init__(self, seq_num, seq_len, message_len, checksum, data):
        self.seq_num     = seq_num
        self.seq_len     = seq_len
        self.message_len = message_len
        self.checksum    = checksum
        self.data        = data

    @staticmethod
    def from_cbor(cbor_buf):
        try:
            decoder = CBORDecoder(cbor_buf)
            array_size, _ = decoder.decodeArraySize()
            if array_size != 5:
                raise InvalidHeader()
            seq_num,     _ = decoder.decodeUnsigned()
            seq_len,     _ = decoder.decodeUnsigned()
            message_len, _ = decoder.decodeUnsigned()
            checksum,    _ = decoder.decodeUnsigned()
            data,        _ = decoder.decodeBytes()
            return Part(seq_num, seq_len, message_len, checksum, data)
        except Exception as exc:
            raise InvalidHeader() from exc

    def cbor(self):
        enc = CBOREncoder()
        enc.encodeArraySize(5)
        enc.encodeInteger(self.seq_num)
        enc.encodeInteger(self.seq_len)
        enc.encodeInteger(self.message_len)
        enc.encodeInteger(self.checksum)
        enc.encodeBytes(self.data)
        return enc.get_bytes()


class FountainEncoder:
    def __init__(self, message, max_fragment_len, first_seq_num=0, min_fragment_len=10):
        assert len(message) <= MAX_UINT32
        self.message_len  = len(message)
        self.checksum     = crc32_int(message)
        self.fragment_len = FountainEncoder.find_nominal_fragment_length(
            self.message_len, min_fragment_len, max_fragment_len
        )
        self.fragments = FountainEncoder.partition_message(message, self.fragment_len)
        self.seq_num   = first_seq_num

    @staticmethod
    def find_nominal_fragment_length(message_len, min_fragment_len, max_fragment_len):
        assert message_len > 0 and min_fragment_len > 0 and max_fragment_len >= min_fragment_len
        max_fragment_count = message_len // min_fragment_len
        fragment_len = None
        for fragment_count in range(1, max_fragment_count + 1):
            fragment_len = math.ceil(message_len / fragment_count)
            if fragment_len <= max_fragment_len:
                break
        return fragment_len

    @staticmethod
    def partition_message(message, fragment_len):
        remaining = bytearray(message)
        fragments = []
        while remaining:
            fragment, remaining = split(remaining, fragment_len)
            fragment = bytearray(fragment)
            while len(fragment) < fragment_len:
                fragment.append(0)
            fragments.append(fragment)
        return fragments

    def seq_len(self):
        return len(self.fragments)

    def is_complete(self):
        return self.seq_num >= self.seq_len()

    def is_single_part(self):
        return self.seq_len() == 1

    def expected_part_count(self):
        return self.seq_len()

    def next_part(self):
        self.seq_num = (self.seq_num + 1) % MAX_UINT32
        indexes = choose_fragments(self.seq_num, self.seq_len(), self.checksum)
        mixed = bytearray([0] * self.fragment_len)
        for i in indexes:
            xor_into(mixed, self.fragments[i])
        return Part(self.seq_num, self.seq_len(), self.message_len, self.checksum, bytes(mixed))
