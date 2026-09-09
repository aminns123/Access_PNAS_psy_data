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
        margin = fraction * (hi - lo) if hi > lo else .1
        return 10 ** (lo - margin), 10 ** (hi + margin)

    margin = fraction * (hi - lo) if hi > lo else max(abs(lo) * fraction, .5)
    return lo - margin, hi + margin


def axis_policy(spec, axis):
    values = [
        value
        for series in spec.series
        for value in getattr(series, axis)
        if finite(value)
    ]

    scale = getattr(spec, axis + 'scale')
    override = getattr(spec, axis + 'lim', None)

    override_values = (
        [float(value) for value in override if finite(value)]
        if override is not None
        else []
    )

    fallback = (
        scale == 'log'
        and any(value <= 0 for value in values + override_values)
    )
    if fallback:
        scale = 'linear'

    if (
        override is not None
        and len(override_values) == 2
        and override_values[0] < override_values[1]
    ):
        limits = tuple(override_values)
    else:
        limits = padded_limits(values, scale)

    return scale, limits, fallback


def tick_label(value):
    if value == 0:
        return '0'
    if abs(value) < .0001 or abs(value) >= 1e6:
        return f'{value:g}'
    return f'{value:.6f}'.rstrip('0').rstrip('.')


def log_ticks(limits, maximum=7):
    lo, hi = limits
    ticks = [
        m * 10. ** exponent
        for exponent in range(
            math.floor(math.log10(lo)),
            math.ceil(math.log10(hi)) + 1,
        )
        for m in (1, 2, 3, 5)
        if lo <= m * 10. ** exponent <= hi
    ]
    stride = max(1, math.ceil(len(ticks) / maximum))
    return ticks[::stride]
