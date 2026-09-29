"""
hybrid_engine.py

HybridEngine is the core of the "v2" project: it asks recommenders for
scores and blends them into one ranked list.

Three signals, blended:
  1. content_score  -- tag overlap between resident interests & activity
  2. collab_score    -- what residents with similar RATING patterns liked
  3. implicit_score  -- click-through rate from browsing behaviour (no
                        rating needed) -- see implicit_tracker.py

Why blend instead of picking one:
  - Content-based alone never learns from behavior.
  - Collaborative alone fails for brand-new residents with no rating
    history (the cold-start problem).
  - Implicit signals capture interest even from residents who browse but
    never bother to submit a star rating -- a real, common behaviour --
    but they're noisier, so they get a small fixed weight rather than
    competing equally with the other two.

Normalization matters here: content_score is a small integer (tag overlap
count), collab_score is a rating estimate (roughly 1-5), and implicit_score
is already 0-1 (a click-through rate). We min-max scale content and collab
to 0-1 before combining so no signal dominates just because its raw scale
happens to be bigger.
"""

import pandas as pd

# Implicit signals (clicks/views) are real but noisy evidence of interest --
# much weaker than an actual attended+rated visit. Kept intentionally small
# and fixed rather than user-adjustable, unlike content/collab weights.
DEFAULT_IMPLICIT_WEIGHT = 0.15


class HybridEngine:
    def __init__(self, content_recommender, collaborative_recommender,
                 implicit_tracker=None,
                 content_weight=0.5, collab_weight=0.5,
                 implicit_weight=DEFAULT_IMPLICIT_WEIGHT):
        self.content_recommender = content_recommender
        self.collaborative_recommender = collaborative_recommender
        self.implicit_tracker = implicit_tracker
        self.content_weight = content_weight
        self.collab_weight = collab_weight
        self.implicit_weight = implicit_weight

    @staticmethod
    def _min_max_normalize(series):
        if series.empty:
            return series
        min_v, max_v = series.min(), series.max()
        if max_v == min_v:
            # everything tied -- treat as neutral rather than dividing by zero
            return series.apply(lambda x: 0.5)
        return (series - min_v) / (max_v - min_v)

    def recommend(self, resident_row, resident_history_ids, n=5):
        """
        resident_row: pandas Series for this resident (needs 'interests',
                      'mobility_level', 'resident_id').
        resident_history_ids: set of activity_ids this resident already
                      attended, so we don't recommend repeats.
        Returns a DataFrame: activity_id, name, content_score, collab_score,
                implicit_score (0-1 CTR), hybrid_score, source.
        """
        resident_id = resident_row["resident_id"]

        content_df = self.content_recommender.recommend_for_resident(
            resident_row, n=len(self.content_recommender.activities_df),
            exclude_ids=resident_history_ids,
        )[["activity_id", "name", "content_score"]].set_index("activity_id")

        collab_scores = self.collaborative_recommender.recommend_for_resident(
            resident_id, n=len(self.content_recommender.activities_df),
            exclude_ids=resident_history_ids,
        )

        combined = content_df.copy()
        combined["collab_score_raw"] = collab_scores

        # --- implicit (click-through rate) ---
        if self.implicit_tracker is not None:
            ctr_scores = self.implicit_tracker.get_ctr_scores(resident_id)
            combined["implicit_score"] = ctr_scores
        else:
            combined["implicit_score"] = pd.NA
        combined["implicit_score"] = pd.to_numeric(
            combined["implicit_score"], errors="coerce"
        ).fillna(0.0)  # no impressions logged yet for this activity -> neutral 0

        combined["content_score_norm"] = self._min_max_normalize(combined["content_score"])

        has_collab_data = combined["collab_score_raw"].notna().any()
        if has_collab_data:
            rated_mask = combined["collab_score_raw"].notna()
            combined.loc[rated_mask, "collab_score_norm"] = self._min_max_normalize(
                combined.loc[rated_mask, "collab_score_raw"]
            )
            combined["collab_score_norm"] = combined["collab_score_norm"].fillna(0)
            c_weight, k_weight = self.content_weight, self.collab_weight
        else:
            combined["collab_score_norm"] = 0.0
            c_weight, k_weight = 1.0, 0.0  # fall back to content-only for cold-start residents

        # The two "primary" signals (content+collab) share (1 - implicit_weight)
        # of the total, in whatever content/collab split was requested; the
        # implicit signal always gets its own small, fixed slice.
        i_weight = self.implicit_weight
        primary_share = 1.0 - i_weight

        combined["hybrid_score"] = (
            combined["content_score_norm"] * c_weight * primary_share
            + combined["collab_score_norm"] * k_weight * primary_share
            + combined["implicit_score"] * i_weight
        )

        combined["source"] = combined.apply(lambda row: self._label_source(row), axis=1)

        result = combined.sort_values("hybrid_score", ascending=False).head(n).reset_index()

        # Log impressions for exactly the activities we're about to show --
        # this is what lets the NEXT request compute an accurate CTR.
        if self.implicit_tracker is not None and not result.empty:
            self.implicit_tracker.log_impressions(resident_id, result["activity_id"].tolist())

        return result

    @staticmethod
    def _label_source(row):
        has_content = row["content_score"] > 0
        has_collab = row["collab_score_raw"] > 0 if pd.notna(row["collab_score_raw"]) else False
        has_implicit = row.get("implicit_score", 0) > 0

        if has_content and has_collab:
            return "content + collaborative"
        if has_content and has_implicit:
            return "content + browsing interest"
        if has_content:
            return "content-based (interest match)"
        if has_collab:
            return "collaborative (similar residents)"
        if has_implicit:
            return "browsing interest (clicked before)"
        return "exploratory (no strong signal)"

    def explain(self, row):
        """Returns a short, human-readable reason for one recommended row."""
        if row["source"] == "content + collaborative":
            return f"Matches your interests, and residents like you enjoyed {row['name']}."
        if row["source"] == "content + browsing interest":
            return f"Matches your interests, and you've shown interest in {row['name']} before."
        if row["source"] == "content-based (interest match)":
            return "Matches your stated interests."
        if row["source"] == "collaborative (similar residents)":
            return f"Residents with similar tastes to you rated {row['name']} highly."
        if row["source"] == "browsing interest (clicked before)":
            return f"You've clicked into {row['name']} before -- worth a closer look."
        return "Suggested to help you explore something new."