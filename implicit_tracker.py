"""
implicit_tracker.py

Tracks IMPLICIT feedback -- signals inferred from behaviour rather than a
deliberate rating. Two event types:

  - "impression": an activity was actually shown to a resident as a
    recommendation. Logged automatically server-side, the moment
    /api/recommendations returns a result.
  - "click": the resident's card was clicked/opened. Logged from the
    frontend the instant it happens.

WHY CLICK-THROUGH RATE (CTR), NOT RAW CLICK COUNTS:
An activity shown 20 times and clicked twice (10% CTR) reflects real
interest more accurately than an activity shown once and clicked once
(100% CTR looks the same as "clicked every single time it appeared" only
if we don't account for how often it was shown). Dividing clicks by
impressions makes activities comparable regardless of how often each one
happened to be recommended.

WHY THIS IS A SMALL-WEIGHT SIGNAL, NOT A REPLACEMENT:
A click is a weak, noisy proxy for interest -- someone might click by
accident, out of curiosity, or while just browsing. An explicit "attended
+ rated 5 stars" is much stronger evidence. HybridEngine therefore blends
this in at a low weight (see IMPLICIT_WEIGHT in hybrid_engine.py) rather
than treating it as equal to content or collaborative scores.
"""

import os
from datetime import datetime
import pandas as pd


class ImplicitTracker:
    def __init__(self, data_dir="data"):
        self.path = os.path.join(data_dir, "live_implicit_events.csv")

    def log_impressions(self, resident_id, activity_ids):
        """Call this AFTER ranking is computed, for the activities actually shown."""
        if not activity_ids:
            return
        rows = pd.DataFrame([{
            "resident_id": resident_id,
            "activity_id": activity_id,
            "event_type": "impression",
            "timestamp": datetime.now().isoformat(),
        } for activity_id in activity_ids])
        self._append(rows)

    def log_click(self, resident_id, activity_id):
        row = pd.DataFrame([{
            "resident_id": resident_id,
            "activity_id": activity_id,
            "event_type": "click",
            "timestamp": datetime.now().isoformat(),
        }])
        self._append(row)

    def _append(self, rows_df):
        file_exists = os.path.exists(self.path)
        rows_df.to_csv(self.path, mode="a", header=not file_exists, index=False)

    def get_ctr_scores(self, resident_id):
        """
        Returns a pandas Series: activity_id -> click-through rate (0-1),
        for every activity this resident has actually been shown at least
        once. Activities never shown to this resident are simply absent
        from the result (not zero) -- HybridEngine treats "absent" as
        "no implicit signal yet" and fills with 0 itself.
        """
        if not os.path.exists(self.path):
            return pd.Series(dtype=float)

        events = pd.read_csv(self.path)
        events = events[events["resident_id"] == resident_id]
        if events.empty:
            return pd.Series(dtype=float)

        counts = events.pivot_table(
            index="activity_id", columns="event_type",
            values="timestamp", aggfunc="count", fill_value=0
        )
        if "impression" not in counts.columns:
            return pd.Series(dtype=float)
        if "click" not in counts.columns:
            counts["click"] = 0

        ctr = (counts["click"] / counts["impression"]).clip(upper=1.0)
        return ctr