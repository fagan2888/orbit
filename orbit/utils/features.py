import numpy as np
import pandas as pd
from datetime import datetime


def make_fourier_series(dates, period, order=3):
    """ Given dates array, cyclical period and order.  Return a set of fourier series.
    Parameters
    ----------
    dates: 1D array-like
        Array of datetime stamp
    period: int
        Number of days of the period.
    order: int
        Number of components for each sin() or cos() series.
    Returns
    -------
    2D array-like
        2D array where each column represents the series with a specific order fourier constructed by sin() or cos().
    Notes
    -----
        1. See https://otexts.com/fpp2/complexseasonality.html
        2. Original idea from https://github.com/facebook/prophet under
    """
    t = np.array(
        (dates - datetime(1950, 1, 1))
            .dt.total_seconds()
            .astype(np.float)
    ) / (3600 * 24.)
    out = list()
    for i in range(1, order + 1):
        x = 2.0 * i * np.pi * t / period
        out.append(np.sin(x))
        out.append(np.cos(x))
    out = np.column_stack(out)
    return out


def make_fourier_series_df(df, date_col, period, order=3):
    """ Given a data-frame, cyclical period and order.  Return a set of fourier series in a dataframe.
    Parameters
    ----------
    df: pd.DataFrame
        Input dataframe to supply datetime array in order to
    date_col: str
        Label of the date column supply for generating series
    Returns
    -------
    out: pd.DataFrame
        data with computed fourier series attached
    fs_cols: list
        list of labels derived from fourier series
    Notes
    -----
        This is calling :func:`make_fourier_series`
    """
    fs = make_fourier_series(df[date_col], period, order=order)
    fs_cols = []
    for i in range(1, order + 1):
        fs_cols.append('fs_cos{}'.format(i))
        fs_cols.append('fs_sin{}'.format(i))
    fs_df = pd.DataFrame(fs, columns=fs_cols)
    out = pd.concat([df.reset_index(drop=True), fs_df], axis=1)
    return out, fs_cols


def make_seasonal_dummies(df, date_col, freq, sparse=True, drop_first=True):
    if freq == 'weekday':
        dummies = pd.get_dummies(df[date_col].dt.weekday, prefix='wd', sparse=sparse, drop_first=drop_first)
    elif freq == 'month':
        dummies = pd.get_dummies(df[date_col].dt.month, prefix='m', sparse=sparse, drop_first=drop_first)
    elif freq == 'week':
        dummies = pd.get_dummies(df[date_col].dt.week, prefix='w', sparse=sparse, drop_first=drop_first)
    cols = dummies.columns.tolist()
    out = pd.concat([df, dummies], axis=1)
    return out, cols
