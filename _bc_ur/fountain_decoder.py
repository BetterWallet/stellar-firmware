#
# fountain_decoder.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from .fountain_utils import choose_fragments, contains, is_strict_subset, set_difference
from .utils import join_bytes, crc32_int, xor_with, take_first


class InvalidChecksum(Exception):
    pass


class FountainDecoder:
    class Part:
        def __init__(self, indexes, data):
            self.indexes = frozenset(indexes)
            self.data    = data

        @classmethod
        def from_encoder_part(cls, p):
            return cls(choose_fragments(p.seq_num, p.seq_len, p.checksum), bytearray(p.data))

        def is_simple(self):
            return len(self.indexes) == 1

        def index(self):
            return next(iter(self.indexes))

    def __init__(self):
        self.received_part_indexes  = set()
        self.last_part_indexes      = None
        self.processed_parts_count  = 0
        self.result                 = None
        self.expected_part_indexes  = None
        self.expected_fragment_len  = None
        self.expected_message_len   = None
        self.expected_checksum      = None
        self.simple_parts           = {}
        self.mixed_parts            = {}
        self.queued_parts           = []

    def expected_part_count(self):
        return len(self.expected_part_indexes) if self.expected_part_indexes else 0

    def is_success(self):
        return self.result is not None and not isinstance(self.result, Exception)

    def is_failure(self):
        return isinstance(self.result, Exception)

    def is_complete(self):
        return self.result is not None

    def result_message(self):
        return self.result

    def estimated_percent_complete(self):
        if self.is_complete():
            return 1.0
        if self.expected_part_indexes is None:
            return 0.0
        estimated = self.expected_part_count() * 1.75
        return min(0.99, self.processed_parts_count / estimated)

    def receive_part(self, encoder_part):
        if self.is_complete():
            return False
        if not self._validate_part(encoder_part):
            return False

        p = FountainDecoder.Part.from_encoder_part(encoder_part)
        self.last_part_indexes = p.indexes
        self.queued_parts.append(p)

        while not self.is_complete() and self.queued_parts:
            self._process_queue_item()

        self.processed_parts_count += 1
        return True

    def _validate_part(self, p):
        if self.expected_part_indexes is None:
            self.expected_part_indexes  = set(range(p.seq_len))
            self.expected_message_len   = p.message_len
            self.expected_checksum      = p.checksum
            self.expected_fragment_len  = len(p.data)
        else:
            if (self.expected_part_count() != p.seq_len
                    or self.expected_message_len != p.message_len
                    or self.expected_checksum    != p.checksum
                    or self.expected_fragment_len != len(p.data)):
                return False
        return True

    def _process_queue_item(self):
        part = self.queued_parts.pop(0)
        if part.is_simple():
            self._process_simple_part(part)
        else:
            self._process_mixed_part(part)

    def _reduce_part_by_part(self, a, b):
        if is_strict_subset(b.indexes, a.indexes):
            new_indexes = set_difference(a.indexes, b.indexes)
            new_data    = xor_with(bytearray(a.data), b.data)
            return FountainDecoder.Part(new_indexes, new_data)
        return a

    def _reduce_mixed_by(self, p):
        new_mixed = {}
        for r in self.mixed_parts.values():
            reduced = self._reduce_part_by_part(r, p)
            if reduced.is_simple():
                self.queued_parts.append(reduced)
            else:
                new_mixed[reduced.indexes] = reduced
        self.mixed_parts = new_mixed

    def _process_simple_part(self, p):
        idx = p.index()
        if contains(self.received_part_indexes, idx):
            return
        self.simple_parts[p.indexes] = p
        self.received_part_indexes.add(idx)

        if self.received_part_indexes == self.expected_part_indexes:
            sorted_parts = sorted(self.simple_parts.values(), key=lambda x: x.index())
            message = take_first(join_bytes(x.data for x in sorted_parts), self.expected_message_len)
            if crc32_int(message) == self.expected_checksum:
                self.result = bytes(message)
            else:
                self.result = InvalidChecksum()
        else:
            self._reduce_mixed_by(p)

    def _process_mixed_part(self, p):
        if p.indexes in self.mixed_parts:
            return
        p2 = p
        for r in self.simple_parts.values():
            p2 = self._reduce_part_by_part(p2, r)
        for r in self.mixed_parts.values():
            p2 = self._reduce_part_by_part(p2, r)

        if p2.is_simple():
            self.queued_parts.append(p2)
        else:
            self._reduce_mixed_by(p2)
            self.mixed_parts[p2.indexes] = p2
