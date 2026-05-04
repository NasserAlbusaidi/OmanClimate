"""Wet-bulb temperature from Stull 2011.

Stull, R., 2011: Wet-Bulb Temperature from Relative Humidity and Air
Temperature. J. Appl. Meteor. Climatol., 50, 2267-2269.
DOI: 10.1175/JAMC-D-11-0143.1

Empirical fit valid for:
    - air pressures near sea level (101.325 kPa)
    - air temperature  -20 .. +50 °C
    - relative humidity   5 .. 99 %

Outside the validity envelope the function still returns a value but
results should be treated with caution.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def stull_wet_bulb(
    temperature_c: ArrayLike,
    relative_humidity_pct: ArrayLike,
) -> NDArray[np.float64]:
    """Compute wet-bulb temperature in °C using Stull 2011.

    Parameters
    ----------
    temperature_c
        Dry-bulb air temperature in degrees Celsius.
    relative_humidity_pct
        Relative humidity in percent (0-100), NOT 0-1.

    Returns
    -------
    Wet-bulb temperature in degrees Celsius, same shape as inputs.
    NaN propagates from either input.
    """
    t = np.asarray(temperature_c, dtype=np.float64)
    rh = np.asarray(relative_humidity_pct, dtype=np.float64)

    return (
        t * np.arctan(0.151977 * np.sqrt(rh + 8.313659))
        + np.arctan(t + rh)
        - np.arctan(rh - 1.676331)
        + 0.00391838 * np.power(rh, 1.5) * np.arctan(0.023101 * rh)
        - 4.686035
    )
