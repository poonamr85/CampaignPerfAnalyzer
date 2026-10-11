# Campaign Performance Dashboard

A Streamlit, pandas, and Plotly dashboard with Overview, Platform Comparison,
Campaign Details, and Time Series views. Global date, channel, audience, and goal
filters apply to every view. The default dataset is synthetic sample data.

For an explanation of the dashboard, its data flow, and all four views, open
[the dashboard guide](docs/dashboard-guide.html). It includes a high level
diagram and can be printed or saved as PDF from a browser.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. Upload a CSV in the sidebar, or explore the sample.
The sidebar includes sample and blank-template downloads.

Reusable upload files live in `data/`:

- `sample_campaign_performance.csv`: 240 synthetic records across eight campaigns
  and four channels, covering September 1–30, 2026 in USD. It follows the blank
  template's columns and can be uploaded repeatedly.
  Synthetic lead-generation campaigns have zero booked revenue; every sample row
  has explicit revenue so the default Revenue and Advertising ROI cards calculate.
- `campaign_template.csv`: header-only template for preparing your own data.

Choose `data/sample_campaign_performance.csv` in the sidebar uploader whenever
you want to practice with sample data. The app also loads this file automatically
when Use sample data is enabled. Both dashboard download buttons use these files.

After selecting an upload, click **Load Campaign Data** to validate
and apply it. A pending message means the previous dataset is still displayed;
an up-to-date message confirms the uploaded file is active. Invalid uploads keep
the previous data. Clearing the upload returns to sample data when enabled.

## Replit

Import this folder into a Python Replit project. Install dependencies with
`pip install -r requirements.txt`, then use Run. The included `.replit` starts
Streamlit on `0.0.0.0:8501` and maps it to external port 80. Use the same start
command for a server deployment. Hosting has not been provisioned by this project.

## CSV format

Required columns: `date`, `campaign_id`, `campaign_name`, `channel`, `audience`,
`campaign_goal`, `spend`, `clicks`, `conversions`, `currency`.
Optional: `revenue`, `impressions`. Use YYYY-MM-DD dates and plain numeric values
(no currency symbols or thousands separators). Counts must be whole numbers.
Each row is an additive date/campaign/channel/audience/goal observation; overlapping
totals will be double counted. X is normalized to Twitter. One currency per file.

Missing revenue makes revenue, ROI, and ROAS unavailable for the affected group.
Rates are calculated from group totals. Division by zero displays N/A.
Advertising ROI excludes non-advertising costs. Compare conversions within a
consistent campaign goal and attribution definition. Time buckets with no records
are not treated as zero. Weekly periods start on Monday.

Uploads remain in the running session and are not saved to disk. Do not upload
sensitive data to a public deployment without appropriate access controls.
Report generation and email are outside the current scope.

## Verification

```sh
python -m unittest discover -s tests -v
```

Tests check known sample totals, aggregation, filters, validation, unavailable
metrics, and all four views using Streamlit AppTest.
