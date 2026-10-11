from pathlib import Path
import hashlib
import time
from html import escape
import pandas as pd
import plotly.express as px
import streamlit as st
from analytics import REQUIRED, aggregate, filter_data, load_csv, summarize

st.set_page_config(page_title='Ad Campaign Performance Dashboard', page_icon='📊', layout='wide')
COLORS = {'Facebook': '#2563EB', 'Instagram': '#DB2777', 'Pinterest': '#DC2626', 'Twitter': '#0D9488'}
DATA_DIR = Path(__file__).with_name('data')
SAMPLE = DATA_DIR / 'sample_campaign_performance.csv'
LOGO = Path(__file__).with_name('assets') / 'growth-logo.svg'
st.markdown('''<style>
.stApp { background-color: #F8FAFC; }
.data-status { background: white; border: 1px solid #E2E8F0;
 border-left: 4px solid #6366F1; border-radius: 10px; padding: 14px 18px;
 margin: 8px 0 20px; color: #475569; display: flex; flex-wrap: wrap;
 align-items: center; gap: 8px 12px; }
.data-status strong { color: #4338CA; overflow-wrap: anywhere; }
.data-status small { flex-basis: 100%; color: #64748B; }
.performance-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
 gap: 16px; margin: 8px 0 16px; }
.summary-card { background: white; border: 1px solid #E2E8F0;
 border-top: 4px solid #6366F1; border-radius: 14px; padding: 20px;
 box-shadow: 0 4px 16px rgba(23,32,51,.04); }
.summary-label { color: #475569; font-size: 15px; font-weight: 600; }
.summary-value { color: #4338CA; font-size: clamp(20px, 2.2vw, 30px);
 font-weight: 750; font-variant-numeric: tabular-nums; margin: 10px 0;
 overflow-wrap: anywhere; }
.summary-context { color: #64748B; font-size: 12px; }
.summary-card:last-child { border-top-color: #0D9488; }
.summary-card:last-child .summary-value { color: #0F766E; }
@media (max-width: 1000px) {
 .performance-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
 .performance-summary { grid-template-columns: 1fr; }
}
</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def parse(content):
    return load_csv(content)


def chart(fig):
    fig.update_layout(margin=dict(l=10, r=10, t=35, b=10), legend_title_text='',
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, width='stretch')


def reset_filters():
    for key in ['dates', 'channels', 'audiences', 'goals']:
        st.session_state.pop(key, None)


with st.sidebar:
    st.image(str(LOGO), width=64)
    st.title('Campaign Analytics')
    st.caption('Turn advertising data into decisions.')
    upload = st.file_uploader('Upload campaign CSV', type=['csv'])
    refresh = st.button('Load Campaign Data', type='primary', disabled=upload is None)
    st.caption('After uploading a file, click Load Campaign Data to update the dashboard.')
    sample = st.toggle('Use sample data', value=True, disabled=upload is not None)
    st.download_button('Download sample CSV', SAMPLE.read_bytes(), file_name=SAMPLE.name, mime='text/csv')
    template = (DATA_DIR / 'campaign_template.csv').read_bytes()
    st.download_button('Download blank template', template, file_name='campaign_template.csv', mime='text/csv')

brand, heading = st.columns([1, 12], vertical_alignment='center')
with brand:
    st.image(str(LOGO), width=72)
with heading:
    st.title('Ad Campaign Performance Dashboard')
st.caption('Compare investment, results, and efficiency across your advertising channels.')
if refresh or upload is None:
    st.session_state.pop('load_confirmation_until', None)
if upload is not None:
    candidate = upload.getvalue()
    candidate_id = hashlib.sha256(candidate).hexdigest()
    if refresh:
        try:
            parse(candidate)
        except ValueError as exc:
            st.error(f'Dashboard was not refreshed: {exc}')
        else:
            st.session_state['active_upload'] = candidate
            st.session_state['active_upload_name'] = upload.name
            st.session_state['load_confirmation_until'] = time.monotonic() + 3
    active = st.session_state.get('active_upload')
    if active is None or hashlib.sha256(active).hexdigest() != candidate_id:
        st.warning('Upload pending. Click Load Campaign Data to update the dashboard. The dashboard below still shows the previous data.')
else:
    st.session_state.pop('active_upload', None)
    st.session_state.pop('active_upload_name', None)

confirmation_until = st.session_state.get('load_confirmation_until', 0)


@st.fragment(run_every=0.2 if confirmation_until > time.monotonic() else None)
def load_confirmation():
    deadline = st.session_state.get('load_confirmation_until')
    if deadline is None:
        return
    if time.monotonic() >= deadline:
        st.session_state.pop('load_confirmation_until', None)
        st.rerun()
    st.success('Performance dashboard refreshed successfully.')
    st.success(f'Dashboard is up to date with {st.session_state["active_upload_name"]}.')


load_confirmation()

active_upload = st.session_state.get('active_upload')
if active_upload is None and not sample:
    st.info('Upload a campaign CSV or turn on sample data to get started.')
    st.stop()
content = active_upload if active_upload is not None else SAMPLE.read_bytes()
try:
    data = parse(content)
except ValueError as exc:
    st.error(str(exc))
    st.info('Download the blank template or sample CSV to check the expected format.')
    st.stop()
fingerprint = hashlib.sha256(content).hexdigest()
if st.session_state.get('dataset') != fingerprint:
    reset_filters()
    st.session_state['dataset'] = fingerprint
currency = data.currency.iloc[0]

with st.sidebar:
    st.divider()
    st.subheader('Global filters')
    st.button('Reset filters', on_click=reset_filters)
    dates = st.date_input('Date range', value=(data.date.min().date(), data.date.max().date()),
                          min_value=data.date.min().date(), max_value=data.date.max().date(), key='dates')
    channels = st.multiselect('Channel', sorted(data.channel.unique()), default=sorted(data.channel.unique()), key='channels')
    audiences = st.multiselect('Audience', sorted(data.audience.unique()), default=sorted(data.audience.unique()), key='audiences')
    goals = st.multiselect('Campaign goal', sorted(data.campaign_goal.unique()), default=sorted(data.campaign_goal.unique()), key='goals')
    st.caption('All four views use these filters. Clearing a selection returns no matches.')
if len(dates) != 2:
    st.info('Select an end date to complete the date range.')
    st.stop()
filtered = filter_data(data, dates, channels, audiences, goals)
source_label = 'Sample data' if active_upload is None else f'Loaded: {st.session_state["active_upload_name"]}'
period_label = f'{dates[0]:%b} {dates[0].day}, {dates[0].year} – {dates[1]:%b} {dates[1].day}, {dates[1].year}'
record_label = f'{len(filtered):,} records' if len(filtered) == len(data) else f'{len(filtered):,} of {len(data):,} records match filters'
sample_note = '<small>Synthetic data for demonstration.</small>' if active_upload is None else ''
st.markdown(f'<div class="data-status" role="status"><strong>{escape(source_label)}</strong>'
            f'<span>· {escape(period_label)}</span><span>· {record_label}</span>'
            f'<span>· {escape(currency)}</span>{sample_note}</div>', unsafe_allow_html=True)
view = st.radio('Select the View', ['Overview', 'Platform Comparison', 'Campaign Details', 'Time Series'], horizontal=True)
if filtered.empty:
    st.info('No data matches your selected filters. Adjust your selections or reset filters.')
    st.stop()


def fmt(value, unit=''):
    if pd.isna(value):
        return 'N/A'
    if unit == '%':
        return f'{value:,.1f}%'
    if unit == '×':
        return f'{value:,.2f}×'
    return f'{currency} {value:,.2f}' if unit == 'money' else f'{value:,.0f}'


def table(frame):
    renamed = frame.rename(columns={
        'spend': f'Spend ({currency})', 'revenue': f'Revenue ({currency})',
        'CPC': f'CPC ({currency}/click)', 'CPA': f'CPA ({currency}/conversion)',
        'ROI': 'Advertising ROI (%)', 'ROAS': 'ROAS (×)',
        'CTR': 'CTR (%)', 'Conversion rate': 'Conversion rate (%)',
    })
    numeric = renamed.select_dtypes('number').columns
    st.dataframe(renamed.style.format({c: '{:,.2f}' if any(x in c for x in ['(', 'rate']) else '{:,.0f}' for c in numeric}, na_rep='N/A'),
                 width='stretch', hide_index=True)


if view == 'Overview':
    metrics = summarize(filtered)
    cards = ''.join(
        f'<div class="summary-card"><div class="summary-label">{label}</div>'
        f'<div class="summary-value">{escape(fmt(metrics[key], unit))}</div>'
        f'<div class="summary-context">{escape(description)}</div></div>'
        for key, label, unit, description in [
            ('spend', 'Spend', 'money', f'{currency} · advertising investment'),
            ('conversions', 'Conversions', '', 'Count · recorded outcomes'),
            ('revenue', 'Revenue', 'money', f'{currency} · attributed revenue'),
            ('ROI', 'Advertising ROI', '%', '% · return after advertising spend'),
        ]
    )
    st.subheader('Performance summary')
    st.markdown(f'<div class="performance-summary">{cards}</div>', unsafe_allow_html=True)
    st.caption(f'Clicks: {fmt(metrics["clicks"])} · All values reflect your global filters.')
    st.subheader('Spend and conversion trends')
    daily = aggregate(filtered, ['date'])
    left, right = st.columns(2)
    with left:
        chart(px.line(daily, x='date', y='spend', markers=True, labels={'date': 'Date', 'spend': f'Spend ({currency})'}))
    with right:
        chart(px.line(daily, x='date', y='conversions', markers=True, labels={'date': 'Date', 'conversions': 'Conversions (count)'}))
    left, right = st.columns([1, 2])
    with left:
        st.subheader('Budget by channel')
        platform = aggregate(filtered, ['channel'])
        if platform.spend.sum() > 0:
            chart(px.pie(platform, names='channel', values='spend', hole=.65, color='channel', color_discrete_map=COLORS))
        else:
            st.info('No spend recorded for the current selection.')
    with right:
        st.subheader('Top campaigns by conversions')
        top = aggregate(filtered, ['campaign_id', 'campaign_name', 'channel', 'campaign_goal']).nlargest(5, 'conversions')
        table(top[['campaign_name', 'channel', 'campaign_goal', 'spend', 'conversions', 'CPA', 'ROAS']])

elif view == 'Platform Comparison':
    st.subheader('Channel performance')
    platform = aggregate(filtered, ['channel'])
    options = {'Spend': ('spend', currency), 'Clicks': ('clicks', 'count'), 'Conversions': ('conversions', 'count'),
               'CPA': ('CPA', f'{currency}/conversion'), 'Advertising ROI': ('ROI', '%'), 'ROAS': ('ROAS', '×')}
    metric = st.selectbox('Comparison metric', list(options))
    key, unit = options[metric]
    available = platform.dropna(subset=[key])
    if available.empty:
        st.info(f'{metric} is unavailable for the selected data.')
    else:
        chart(px.bar(available, x='channel', y=key, color='channel', color_discrete_map=COLORS,
                     labels={'channel': 'Channel', key: f'{metric} ({unit})'}))
    table(platform)
    st.subheader('Investment versus results')
    chart(px.scatter(platform, x='spend', y='conversions', color='channel', color_discrete_map=COLORS,
                     hover_data=['clicks', 'CPA'], labels={'spend': f'Spend ({currency})', 'conversions': 'Conversions (count)'}, size_max=35))

elif view == 'Campaign Details':
    st.subheader('Campaign details')
    search = st.text_input('Search campaign name or ID', placeholder='Search within the globally filtered results')
    campaigns = aggregate(filtered, ['campaign_id', 'campaign_name', 'channel', 'audience', 'campaign_goal'])
    if search:
        campaigns = campaigns.loc[campaigns.campaign_name.str.contains(search, case=False, regex=False)
                                  | campaigns.campaign_id.str.contains(search, case=False, regex=False)]
    if campaigns.empty:
        st.info('No campaigns match your search. Clear or change your search.')
    else:
        st.caption(f'{len(campaigns):,} campaign / channel / audience / goal combinations. Click column headers to sort.')
        table(campaigns)
        st.download_button('Download campaign results', campaigns.to_csv(index=False, na_rep='N/A'),
                           file_name='campaign_results.csv', mime='text/csv')

else:
    st.subheader('Performance over time')
    a, b, c = st.columns(3)
    grain = a.selectbox('Time interval', ['Daily', 'Weekly', 'Monthly'])
    metric = b.selectbox('Metric', ['spend', 'clicks', 'conversions', 'revenue', 'CPA', 'ROI', 'ROAS'],
                         format_func=lambda x: {'ROI': 'Advertising ROI', 'spend': 'Spend', 'clicks': 'Clicks', 'conversions': 'Conversions', 'revenue': 'Revenue'}.get(x, x))
    breakdown = c.selectbox('Breakdown', ['Total', 'Channel', 'Campaign'])
    frame = filtered.copy()
    frame['period'] = frame.date if grain == 'Daily' else frame.date.dt.to_period('W-SUN' if grain == 'Weekly' else 'M').dt.start_time
    groups = ['period']
    color = None
    if breakdown != 'Total':
        color = 'channel' if breakdown == 'Channel' else 'campaign'
        if color == 'campaign':
            frame[color] = frame.campaign_name + ' [' + frame.campaign_id + ']'
        groups.append(color)
    series = aggregate(frame, groups)
    unit = currency if metric in ['spend', 'revenue'] else f'{currency}/conversion' if metric == 'CPA' else '%' if metric == 'ROI' else '×' if metric == 'ROAS' else 'count'
    if series[metric].notna().any():
        chart(px.line(series, x='period', y=metric, color=color, markers=True, color_discrete_map=COLORS,
                      labels={'period': 'Period start', metric: f'{metric} ({unit})'}))
        st.caption('Missing periods are not assumed to be zero. Weekly buckets start Monday; boundary periods may be partial.')
    else:
        st.info('This metric is unavailable for the selected data.')
    table(series)

with st.expander('Metric definitions and data notes'):
    st.markdown('''**CPC:** spend ÷ clicks. **CPA:** spend ÷ conversions. **Conversion rate:** conversions ÷ clicks × 100.

**Advertising ROI:** (attributed revenue − spend) ÷ spend × 100. **ROAS:** attributed revenue ÷ spend. These exclude product costs and other business expenses.

**CTR:** clicks ÷ impressions × 100. Rates use totals for each group, never averages of row percentages. Zero denominators and incomplete revenue/impressions display N/A.

Each CSV row should represent one date, campaign, channel, audience, and goal. All rows are additive; upload aggregated exports without overlapping totals. Attribution and conversion definitions come from your source data.''')
