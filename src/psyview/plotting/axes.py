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



def _nice_linear_step(raw_step):
    """Round a positive linear step to a readable 1/2/2.5/5/10 sequence."""
    raw_step = float(raw_step)
    if not finite(raw_step) or raw_step <= 0:
        return 1.0

    exponent = math.floor(math.log10(raw_step))
    fraction = raw_step / (10.0 ** exponent)

    for candidate in (1.0, 2.0, 2.5, 5.0, 10.0):
        if fraction <= candidate:
            return candidate * (10.0 ** exponent)

    return 10.0 ** (exponent + 1)


def _nice_log_floor(value):
    """Largest readable 1/2/5 × 10^n value not above value."""
    value = float(value)
    exponent = math.floor(math.log10(value))

    candidates = [
        multiplier * (10.0 ** exponent)
        for multiplier in (1.0, 2.0, 5.0)
    ]

    valid = [
        candidate
        for candidate in candidates
        if candidate <= value * (1.0 + 1e-12)
    ]

    if valid:
        return max(valid)

    return 5.0 * (10.0 ** (exponent - 1))


def _nice_log_ceil(value):
    """Smallest readable 1/2/5 × 10^n value not below value."""
    value = float(value)
    exponent = math.floor(math.log10(value))

    candidates = [
        multiplier * (10.0 ** exponent)
        for multiplier in (1.0, 2.0, 5.0, 10.0)
    ]

    valid = [
        candidate
        for candidate in candidates
        if candidate >= value * (1.0 - 1e-12)
    ]

    if valid:
        return min(valid)

    return 10.0 ** (exponent + 1)


def nice_y_limits(values, scale='linear'):
    """Readable outward limits based only on the CURRENT plot row.

    Linear axes:
        use a small data-relative margin, then round outward using a readable
        1/2/2.5/5 × 10^n interval.

    Log axes:
        for broad ranges, use surrounding powers of ten (e.g. CSF 10–1000);
        for tighter ranges, use surrounding 1/2/5 × 10^n values (e.g.
        threshold contrasts 0.02–0.05).

    This makes condition-to-condition scale changes explicit without using a
    global dataset range.
    """
    values = [
        float(value)
        for value in values
        if finite(value)
    ]

    if not values:
        return (
            (1.0, 10.0)
            if scale == 'log'
            else (0.0, 1.0)
        )

    lo = min(values)
    hi = max(values)

    if scale == 'log':
        positive = [
            value
            for value in values
            if value > 0
        ]

        if not positive:
            return nice_y_limits(values, 'linear')

        lo = min(positive)
        hi = max(positive)

        if math.isclose(
            lo,
            hi,
            rel_tol=1e-12,
            abs_tol=0.0,
        ):
            lower = _nice_log_floor(lo / 1.12)
            upper = _nice_log_ceil(hi * 1.12)
            if lower >= upper:
                lower = lo / 1.5
                upper = hi * 1.5
            return lower, upper

        decades = math.log10(hi / lo)

        # Broad log rows (especially CSFs) read most naturally using decade
        # boundaries: e.g. 17..730 -> 10..1000.
        if decades >= 0.75:
            lower = 10.0 ** math.floor(math.log10(lo))
            upper = 10.0 ** math.ceil(math.log10(hi))

            # If both extrema happen to sit exactly on those boundaries, keep
            # the readable boundaries rather than expanding by a whole decade.
            return lower, upper

        # Tight log rows (e.g. four staircase thresholds) stay local while
        # using human-readable bounds.
        lower_probe = lo * 0.95
        upper_probe = hi * 1.05

        lower = _nice_log_floor(lower_probe)
        upper = _nice_log_ceil(upper_probe)

        if lower >= lo:
            lower = _nice_log_floor(lo * 0.9)
        if upper <= hi:
            upper = _nice_log_ceil(hi * 1.1)

        return lower, upper

    # Linear row-local limits.
    if math.isclose(
        lo,
        hi,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        reference = max(abs(lo), 1.0)
        raw_half_span = reference * 0.08
        step = _nice_linear_step(raw_half_span)
        return lo - step, hi + step

    span = hi - lo
    padded_lo = lo - 0.05 * span
    padded_hi = hi + 0.05 * span

    step = _nice_linear_step(
        (padded_hi - padded_lo) / 4.0
    )

    lower = math.floor(
        padded_lo / step
    ) * step
    upper = math.ceil(
        padded_hi / step
    ) * step

    if math.isclose(lower, upper):
        upper = lower + step

    # Avoid negative zero in labels/metadata.
    if math.isclose(lower, 0.0, abs_tol=1e-15):
        lower = 0.0
    if math.isclose(upper, 0.0, abs_tol=1e-15):
        upper = 0.0

    return lower, upper

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
        and any(
            value <= 0
            for value in values + override_values
        )
    )
    if fallback:
        scale = 'linear'

    if (
        override is not None
        and len(override_values) == 2
        and override_values[0] < override_values[1]
    ):
        limits = tuple(override_values)

    elif axis == 'y':
        # Y limits are always derived from the values visible in THIS plot
        # row/selection and rounded outward to readable limits.
        limits = nice_y_limits(
            values,
            scale,
        )

    else:
        # Preserve the existing x-axis policy unless an adapter explicitly
        # provides xlim.
        limits = padded_limits(
            values,
            scale,
        )

    return scale, limits, fallback




def shared_axis_limits(specs, axis):
    """Return one limit pair encompassing every sibling plot in a row.

    Each sibling first gets its normal local axis policy.  The shared row
    limits are then the union of those resolved limits.  This preserves the
    existing readable rounding/padding while guaranteeing that left/right
    navigation within one hierarchy row never changes the displayed range.
    """
    resolved = []

    for spec in specs:
        try:
            _, limits, _ = axis_policy(
                spec,
                axis,
            )
        except (TypeError, ValueError, OverflowError):
            continue

        if (
            limits is not None
            and len(limits) == 2
            and finite(limits[0])
            and finite(limits[1])
            and float(limits[0]) < float(limits[1])
        ):
            resolved.append(
                (
                    float(limits[0]),
                    float(limits[1]),
                )
            )

    if not resolved:
        return None

    return (
        min(item[0] for item in resolved),
        max(item[1] for item in resolved),
    )


def raw_axis_values(specs, axis, scale=None):
    """Collect physical plotted values across sibling specs.

    Limits are derived from the actual plotted coordinates, not from another
    round of already-padded limits. This avoids cumulative expansion.

    Guide lines in the orthogonal direction do not define a data extent:
      - a vertical line does not define Y range;
      - a horizontal line does not define X range.
    """
    values = []

    for spec in specs:
        for series in spec.series:
            if axis == 'y' and series.kind == 'vline':
                continue
            if axis == 'x' and series.kind == 'hline':
                continue

            for value in getattr(series, axis):
                if finite(value):
                    value = float(value)
                    if scale == 'log' and value <= 0:
                        continue
                    values.append(value)

    return values


def limits_from_values(values, axis, scale):
    """One readable limit calculation from a union of raw sibling values."""
    values = [
        float(value)
        for value in values
        if finite(value)
        and (
            scale != 'log'
            or float(value) > 0
        )
    ]

    if not values:
        return None

    if axis == 'y':
        return nice_y_limits(
            values,
            scale,
        )

    return padded_limits(
        values,
        scale,
    )


def apply_declared_limit_policy(
    limits,
    scale,
    policy=None,
):
    """Apply an optional YAML display policy without ever clipping data.

    preferred_min/preferred_max are SOFT display bounds: they may enlarge the
    range, never shrink it past the data-containing range.

    For log + `rounding: decades`, limits move outward to powers of ten.

    Examples:
        row data 18..850 + preferred 10..1000 -> 10..1000
        row data 8..850  + preferred 10..1000 -> 1..1000
        row data 18..1800                     -> 10..10000
    """
    if limits is None:
        return None

    lo, hi = map(float, limits)
    policy = (
        policy
        if isinstance(policy, dict)
        else {}
    )

    preferred_min = policy.get(
        'preferred_min'
    )
    preferred_max = policy.get(
        'preferred_max'
    )

    if (
        preferred_min is not None
        and finite(preferred_min)
    ):
        preferred_min = float(
            preferred_min
        )
        if (
            scale != 'log'
            or preferred_min > 0
        ):
            lo = min(
                lo,
                preferred_min,
            )

    if (
        preferred_max is not None
        and finite(preferred_max)
    ):
        preferred_max = float(
            preferred_max
        )
        if (
            scale != 'log'
            or preferred_max > 0
        ):
            hi = max(
                hi,
                preferred_max,
            )

    rounding = str(
        policy.get(
            'rounding',
            'auto',
        )
    ).lower()

    if scale == 'log':
        if lo <= 0 or hi <= 0:
            return limits

        if rounding == 'decades':
            lo = 10.0 ** math.floor(
                math.log10(lo)
            )
            hi = 10.0 ** math.ceil(
                math.log10(hi)
            )

        elif rounding == 'nice':
            lo = _nice_log_floor(lo)
            hi = _nice_log_ceil(hi)

    elif rounding in ('nice', 'decades'):
        # If a user temporarily changes a configured log axis to linear,
        # do normal linear rounding; never reuse decade semantics.
        if hi > lo:
            step = _nice_linear_step(
                (hi - lo) / 4.0
            )
            lo = math.floor(
                lo / step
            ) * step
            hi = math.ceil(
                hi / step
            ) * step

    if not lo < hi:
        return limits

    return lo, hi


def shared_axis_limits_for_scale(
    specs,
    axis,
    scale,
    policy=None,
):
    """Resolve one fixed row range directly from all sibling raw values."""
    values = raw_axis_values(
        specs,
        axis,
        scale,
    )

    limits = limits_from_values(
        values,
        axis,
        scale,
    )

    return apply_declared_limit_policy(
        limits,
        scale,
        policy,
    )

def anchor_ticks(limits, scale='linear'):
    """Return guaranteed lower / middle / upper display ticks.

    The middle tick is the visual midpoint of the axis:
      - arithmetic midpoint on a linear scale
      - geometric midpoint on a logarithmic scale

    These ticks describe the ACTUAL displayed limits, so when a user cycles
    conditions they can immediately see whether the y-axis scale changed.
    """
    lo, hi = map(float, limits)

    if not (
        finite(lo)
        and finite(hi)
        and lo < hi
    ):
        return []

    if scale == 'log':
        if lo <= 0 or hi <= 0:
            return []
        middle = math.sqrt(lo * hi)
    else:
        middle = (lo + hi) / 2.0

    ticks = [lo, middle, hi]

    # Defensive de-duplication for extremely tiny floating-point ranges.
    result = []
    for value in ticks:
        if not result or not math.isclose(
            value,
            result[-1],
            rel_tol=1e-12,
            abs_tol=1e-15,
        ):
            result.append(value)

    return result

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
