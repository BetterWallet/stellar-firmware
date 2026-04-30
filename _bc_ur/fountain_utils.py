#
# fountain_utils.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from .random_sampler import RandomSampler
from .utils import int_to_bytes
from .xoshiro256 import Xoshiro256


def _shuffled(items, rng):
    remaining = list(items)
    result = []
    while remaining:
        index = rng.next_int(0, len(remaining) - 1)
        result.append(remaining.pop(index))
    return result


def _choose_degree(seq_len, rng):
    probs = [1.0 / i for i in range(1, seq_len + 1)]
    return RandomSampler(probs).next(lambda: rng.next_double()) + 1


def choose_fragments(seq_num, seq_len, checksum):
    if seq_num <= seq_len:
        return {seq_num - 1}
    seed = int_to_bytes(seq_num) + int_to_bytes(checksum)
    rng = Xoshiro256.from_bytes(seed)
    degree = _choose_degree(seq_len, rng)
    indexes = list(range(seq_len))
    shuffled = _shuffled(indexes, rng)
    return set(shuffled[:degree])


def contains(set_or_list, el):
    return el in set_or_list

def is_strict_subset(a, b):
    return a.issubset(b)

def set_difference(a, b):
    return a.difference(b)
