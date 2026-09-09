"""Shared display policy; scientific coordinates remain unchanged."""
import math


def finite(value):
    return value is not None and math.isfinite(float(value))


def padded_limits(values, scale='linear', fraction=.07):
    values = [float(v) for v in values if finite(v)]
    if scale == 'log' and any(v <= 0 for v in values):
        raise ValueError('Log axis requires positive values.')
    if not values:
        return (1., 10.) if scale == 'log' else (0., 1.)
    lo, hi = min(values), max(values)
    if scale == 'log':
        lo, hi = math.log10(lo), math.log10(hi)
        margin = fraction * (hi-lo) if hi > lo else .1
        return 10 ** (lo-margin), 10 ** (hi+margin)
    margin = fraction * (hi-lo) if hi > lo else max(abs(lo)*fraction, .5)
    return lo-margin, hi+margin


def axis_policy(spec, axis):
    values = [v for s in spec.series for v in getattr(s, axis) if finite(v)]
    scale = getattr(spec, axis+'scale')
    fallback = scale == 'log' and any(v <= 0 for v in values)
    if fallback:
        scale = 'linear'
    return scale, padded_limits(values, scale), fallback


def tick_label(value):
    if value == 0:
        return '0'
    if abs(value) < .0001 or abs(value) >= 1e6:
        return f'{value:g}'
    return f'{value:.6f}'.rstrip('0').rstrip('.')


def log_ticks(limits, maximum=7):
    lo, hi = limits
    ticks = [m*10.**e for e in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi))+1)
             for m in (1, 2, 3, 5) if lo <= m*10.**e <= hi]
    stride = max(1, math.ceil(len(ticks)/maximum))
    return ticks[::stride]
