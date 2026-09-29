"""
hybrid_engine.py

HybridEngine is the core of the "v2" project: it asks BOTH recommenders for
scores and blends them into one ranked list.

Why blend instead of picking one:
  - Content-based alone never learns from behavior (it can't tell you
    "residents like you also loved X" if X shares no tags with your
    interests).
  - Collaborative alone fails for brand-new residents with no rating
    history (the cold-start problem).
  - Blending them covers both weaknesses.

Normalization matters here: content_score is a small integer (tag overlap
count, e.g. 0-3) and collaborative_score is a rating estimate (roughly
1-5). Blending raw values without normalizing would let one signal
dominate just because its numbers happen to be bigger. We min-max scale
both to a 0-1 range before combining.
"""

import pandas as pd


class HybridEngine:
    def __init__(self, content_recommender, collaborative_recommender,
                 content_weight=0.5, collab_weight=0.5):
        self.content_recommender = content_recommender
        self.collaborative_recommender = collaborative_recommender
        self.content_weight = content_weight
        self.collab_weight = collab_weight

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
        Returns a DataFrame: activity_id, name, content_score (0-1),
                collab_score (0-1), hybrid_score, source.
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

        # Start from every mobility-suitable, not-yet-tried activity (content_df
        # already applied the mobility filter), then attach collaborative scores.
        combined = content_df.copy()
        combined["collab_score_raw"] = collab_scores

        combined["content_score_norm"] = self._min_max_normalize(combined["content_score"])
        # Cold-start case: if this resident has NO collaborative scores at all,
        # collab contributes nothing and content carries full weight.
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

        combined["hybrid_score"] = (
            combined["content_score_norm"] * c_weight
            + combined["collab_score_norm"] * k_weight
        )

        combined["source"] = combined.apply(
            lambda row: self._label_source(row), axis=1
        )

        return combined.sort_values("hybrid_score", ascending=False).head(n).reset_index()

    @staticmethod
    def _label_source(row):
        has_content = row["content_score"] > 0
        has_collab = row["collab_score_raw"] > 0 if pd.notna(row["collab_score_raw"]) else False
        if has_content and has_collab:
            return "content + collaborative"
        if has_content:
            return "content-based (interest match)"
        if has_collab:
            return "collaborative (similar residents)"
        return "exploratory (no strong signal)"

    def explain(self, row):
        """Returns a short, human-readable reason for one recommended row."""
        if row["source"] == "content + collaborative":
            return f"Matches your interests, and residents like you enjoyed {row['name']}."
        if row["source"] == "content-based (interest match)":
            return f"Matches your stated interests."
        if row["source"] == "collaborative (similar residents)":
            return f"Residents with similar tastes to you rated {row['name']} highly."
        return "Suggested to help you explore something new."