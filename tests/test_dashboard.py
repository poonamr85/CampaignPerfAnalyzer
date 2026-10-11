import unittest
from unittest.mock import patch
from io import BytesIO
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from analytics import aggregate, filter_data, load_csv, summarize

ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.df = load_csv((ROOT / 'data' / 'sample_campaign_performance.csv').read_bytes())

    def test_known_sales_totals(self):
        metrics = summarize(self.df[self.df.campaign_goal == 'Sales'])
        self.assertAlmostEqual(metrics['spend'], 17527.88)
        self.assertAlmostEqual(metrics['revenue'], 70773.32)
        self.assertEqual(metrics['conversions'], 787)
        self.assertAlmostEqual(metrics['ROAS'], 70773.32 / 17527.88)
        self.assertFalse(pd.isna(summarize(self.df)['ROI']))
        self.assertAlmostEqual(summarize(self.df)['revenue'], self.df.revenue.sum())
        incomplete = self.df.copy()
        incomplete.loc[0, 'revenue'] = float('nan')
        self.assertTrue(pd.isna(summarize(incomplete)['revenue']))
        self.assertTrue(pd.isna(summarize(incomplete)['ROI']))

    def test_filters_and_group_totals(self):
        filtered = filter_data(self.df, ('2026-09-05', '2026-09-10'), ['Facebook'], ['New Customers'], ['Sales'])
        self.assertEqual(len(filtered), 6)
        self.assertEqual(aggregate(filtered, ['channel']).spend.sum(), filtered.spend.sum())
        self.assertTrue(filter_data(self.df, ('2026-09-01', '2026-09-30'), [], [], []).empty)

    def test_validation_and_zero_denominators(self):
        for column, value in [('spend', -1), ('clicks', 1.5), ('date', 'bad'), ('channel', 'unknown')]:
            changed = self.df.copy()
            changed[column] = changed[column].astype(object)
            changed.loc[0, column] = value
            with self.assertRaises(ValueError):
                load_csv(changed.to_csv(index=False).encode())
        zero = self.df.iloc[:1].copy()
        zero[['spend', 'clicks', 'conversions']] = 0
        self.assertTrue(pd.isna(summarize(zero)['CPA']))
        self.assertTrue(pd.isna(summarize(zero)['ROI']))

    def test_all_views_and_global_empty_state(self):
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
        self.assertFalse(app.exception)
        for view in ['Platform Comparison', 'Campaign Details', 'Time Series', 'Overview']:
            app.radio[0].set_value(view).run(timeout=30)
            self.assertFalse(app.exception, view)
        app.multiselect(key='channels').set_value(['Facebook']).run()
        expected = summarize(self.df[self.df.channel == 'Facebook'])['spend']
        self.assertTrue(any(f'USD {expected:,.2f}' in item.value and 'performance-summary' in item.value
                            for item in app.markdown))
        app.multiselect(key='channels').set_value([]).run()
        for view in ['Overview', 'Platform Comparison', 'Campaign Details', 'Time Series']:
            app.radio[0].set_value(view).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('No data matches' in message.value for message in app.info))
        next(button for button in app.button if button.label == 'Reset filters').click().run()
        self.assertEqual(len(app.multiselect(key='channels').value), 4)
        for interval in ['Weekly', 'Monthly']:
            app.selectbox[0].set_value(interval).run()
            app.selectbox[2].set_value('Campaign').run()
            self.assertFalse(app.exception)
        app.radio[0].set_value('Campaign Details').run()
        app.text_input[0].set_value('no such campaign').run()
        self.assertTrue(any('No campaigns match' in message.value for message in app.info))

    def test_upload_requires_refresh_and_rejects_invalid_data(self):
        upload = BytesIO(self.df[self.df.channel == 'Facebook'].to_csv(index=False).encode())
        upload.name = 'facebook.csv'
        app = AppTest.from_file(str(ROOT / 'app.py')).run()
        with patch('streamlit.file_uploader', return_value=upload):
            app.run()
            self.assertTrue(any('Upload pending' in item.value for item in app.warning))
            self.assertNotIn('active_upload', app.session_state)
            next(b for b in app.button if b.label == 'Load Campaign Data').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['active_upload'], upload.getvalue())
            self.assertTrue(any('up to date' in item.value for item in app.success))
            # Simulate the three-second deadline without slowing the test suite.
            app.session_state['load_confirmation_until'] = 0
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.success), 0)
            self.assertNotIn('load_confirmation_until', app.session_state)
            self.assertEqual(app.session_state['active_upload'], upload.getvalue())
        invalid = BytesIO(b'bad,columns\n1,2\n')
        invalid.name = 'invalid.csv'
        with patch('streamlit.file_uploader', return_value=invalid):
            app.run()
            next(b for b in app.button if b.label == 'Load Campaign Data').click().run()
            self.assertTrue(any('was not refreshed' in item.value for item in app.error))
            self.assertEqual(app.session_state['active_upload'], upload.getvalue())


if __name__ == '__main__':
    unittest.main()
