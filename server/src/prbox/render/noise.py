"""Tiny value-noise generator.

Cheap enough to evaluate per-pixel per-frame on a Raspberry Pi: an integer hash
over a lattice plus smoothstep interpolation, no external dependencies.
"""

import math
import random

_MASK = 0xFFFFFFFF


class ValueNoise:
    """Animated 2D value noise, sampled as noise(x, y, t)."""

    def __init__(self, seed: int | None = None) -> None:
        self._seed = random.Random(seed).getrandbits(32) if seed is None else seed

    def _hash(self, x: int, y: int, z: int) -> float:
        """Deterministic 0..1 value for a lattice point."""
        n = (x * 374761393 + y * 668265263 + z * 2147483647 + self._seed) & _MASK
        n = (n ^ (n >> 13)) * 1274126177 & _MASK
        return ((n ^ (n >> 16)) & _MASK) / _MASK

    def __call__(self, x: float, y: float, z: float) -> float:
        """Smoothly interpolated noise in 0..1."""
        xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
        xf, yf, zf = x - xi, y - yi, z - zi

        # Smoothstep the fractional parts so the lattice never shows as creases.
        u = xf * xf * (3.0 - 2.0 * xf)
        v = yf * yf * (3.0 - 2.0 * yf)
        w = zf * zf * (3.0 - 2.0 * zf)

        def plane(dz: int) -> float:
            z0 = zi + dz
            n00 = self._hash(xi, yi, z0)
            n10 = self._hash(xi + 1, yi, z0)
            n01 = self._hash(xi, yi + 1, z0)
            n11 = self._hash(xi + 1, yi + 1, z0)
            top = n00 + (n10 - n00) * u
            bottom = n01 + (n11 - n01) * u
            return top + (bottom - top) * v

        near = plane(0)
        return near + (plane(1) - near) * w

    def fbm(self, x: float, y: float, z: float, octaves: int = 2) -> float:
        """Fractional Brownian motion: stacked octaves, normalised to 0..1."""
        total = 0.0
        amplitude = 1.0
        frequency = 1.0
        norm = 0.0
        for _ in range(octaves):
            total += self(x * frequency, y * frequency, z * frequency) * amplitude
            norm += amplitude
            amplitude *= 0.5
            frequency *= 2.0
        return total / norm if norm else 0.0
