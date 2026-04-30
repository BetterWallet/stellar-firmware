#
# random_sampler.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

class RandomSampler:
    def __init__(self, probs):
        n = len(probs)
        total = sum(probs)
        assert total > 0
        P = [(p * n) / total for p in probs]
        S, L = [], []
        for i in reversed(range(n)):
            (S if P[i] < 1 else L).append(i)

        _probs   = [0.0] * n
        _aliases = [0]   * n
        while S and L:
            a, g = S.pop(), L.pop()
            _probs[a]   = P[a]
            _aliases[a] = g
            P[g] += P[a] - 1
            (S if P[g] < 1 else L).append(g)
        for i in L: _probs[i] = 1.0
        for i in S: _probs[i] = 1.0

        self.probs   = _probs
        self.aliases = _aliases

    def next(self, rng_func):
        r1, r2 = rng_func(), rng_func()
        n = len(self.probs)
        i = int(float(n) * r1)
        return i if r2 < self.probs[i] else self.aliases[i]
