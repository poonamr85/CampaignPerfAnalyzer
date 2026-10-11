"""CSV validation and shared campaign calculations."""
from io import BytesIO
import numpy as np
import pandas as pd

CHANNELS = ['Facebook', 'Instagram', 'Pinterest', 'Twitter']
REQUIRED = ['date', 'campaign_id', 'campaign_name', 'channel', 'audience',
            'campaign_goal', 'spend', 'clicks', 'conversions', 'currency']


def load_csv(content: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(BytesIO(content))
    except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
        raise ValueError('Unable to read CSV. Use a UTF-8 CSV with a header row.') from exc
    df.columns = df.columns.str.strip().str.lower()
    if df.columns.duplicated().any():
        raise ValueError('Column names must be unique.')
    missing = sorted(set(REQUIRED) - set(df.columns))
    if missing:
        raise ValueError('Missing required columns: ' + ', '.join(missing))
    if df.empty:
        raise ValueError('The CSV has no data rows.')
    dates = pd.to_datetime(df.date, errors='coerce', format='mixed')
    if dates.isna().any():
        raise ValueError('Every row needs a valid date (recommended format: YYYY-MM-DD).')
    df['date'] = dates.dt.normalize()
    for col in ['campaign_id', 'campaign_name', 'channel', 'audience', 'campaign_goal', 'currency']:
        if df[col].isna().any() or df[col].astype(str).str.strip().eq('').any():
            raise ValueError(f'{col} cannot be blank.')
        df[col] = df[col].astype(str).str.strip()
    df['channel'] = df.channel.str.lower().map({**{c.lower(): c for c in CHANNELS}, 'x': 'Twitter'})
    if df.channel.isna().any():
        raise ValueError('Channels must be Facebook, Instagram, Pinterest, or Twitter (X).')
    df['currency'] = df.currency.str.upper()
    if df.currency.nunique() != 1:
        raise ValueError('Use one currency per upload. Convert mixed currencies before uploading.')
    for col in ['spend', 'clicks', 'conversions', 'revenue', 'impressions']:
        optional = col in ['revenue', 'impressions']
        if col not in df:
            df[col] = np.nan
        raw = df[col]
        numbers = pd.to_numeric(raw, errors='coerce')
        invalid = (~np.isfinite(numbers) & numbers.notna()) | (numbers < 0)
        invalid |= numbers.isna() & (raw.notna() if optional else True)
        if invalid.any():
            raise ValueError(f'{col} must contain finite, nonnegative numbers' + (' or blanks.' if optional else '.'))
        if col in ['clicks', 'conversions', 'impressions'] and (numbers.dropna() % 1 != 0).any():
            raise ValueError(f'{col} must contain whole-number counts.')
        df[col] = numbers
    return df


def summarize(df: pd.DataFrame) -> dict:
    result = {c: df[c].sum() for c in ['spend', 'clicks', 'conversions']}
    result['revenue'] = df.revenue.sum() if df.revenue.notna().all() and len(df) else np.nan
    result['impressions'] = df.impressions.sum() if df.impressions.notna().all() and len(df) else np.nan
    for name, numerator, denominator, scale in [
        ('CPC', result['spend'], result['clicks'], 1),
        ('CPA', result['spend'], result['conversions'], 1),
        ('Conversion rate', result['conversions'], result['clicks'], 100),
        ('ROI', result['revenue'] - result['spend'], result['spend'], 100),
        ('ROAS', result['revenue'], result['spend'], 1),
        ('CTR', result['clicks'], result['impressions'], 100),
    ]:
        result[name] = numerator / denominator * scale if denominator > 0 else np.nan
    return result


def aggregate(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    rows = []
    for keys, frame in df.groupby(groups, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        rows.append({**dict(zip(groups, keys)), **summarize(frame)})
    return pd.DataFrame(rows)


def filter_data(df, dates, channels, audiences, goals):
    return df.loc[df.date.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))
                  & df.channel.isin(channels) & df.audience.isin(audiences)
                  & df.campaign_goal.isin(goals)].copy()
