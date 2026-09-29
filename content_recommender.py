"""
content_recommender.py

ContentRecommender scores activities purely by comparing an activity's tags
to a resident's stated interests. It never looks at other residents'
behavior, which is exactly why it still works for a brand-new resident with
zero interaction history (the "cold-start problem" that collaborative
filtering alone cannot solve).

Also applies a simple, non-medical MOBILITY FILTER: an activity's
physical_intensity is checked against the resident's mobility_level so we
never recommend something logistically unsuitable. This is a practical
filter, not a clinical judgment -- consistent with the project scope, which
excludes medical/clinical recommendations.
"""

# Simple lookup: which activity intensities are appropriate for each
# mobility level. This is intentionally simple and documented, not a
# black-box rule.
MOBILITY_INTENSITY_LIMIT = {
    "independent": {"low", "medium", "high"},
    "uses_cane": {"low", "medium"},
    "uses_walker": {"low", "medium"},
    "wheelchair": {"low"},
}


class ContentRecommender:
    def __init__(self):
        self.activities_df = None

    def fit(self, activities_df):
        """Stores the activity catalog this recommender will score against."""
        self.activities_df = activities_df.copy()
        return self

    @staticmethod
    def _tag_overlap_score(resident_interests, activity_tags):
        """
        Counts how many tags a resident's interests share with an activity's
        tags. Both are comma-separated strings, e.g. "yoga,cards,music".
        Returns an integer: 0 means no overlap, higher = more relevant.
        """
        resident_set = set(str(resident_interests).split(","))
        activity_set = set(str(activity_tags).split(","))
        return len(resident_set & activity_set)

    def is_mobility_suitable(self, mobility_level, physical_intensity):
        """Logistical check only -- not a medical judgment."""
        allowed = MOBILITY_INTENSITY_LIMIT.get(mobility_level, {"low"})
        return physical_intensity in allowed

    def recommend_for_resident(self, resident_row, n=5, exclude_ids=None):
        """
        resident_row: a pandas Series with at least 'interests' and
                      'mobility_level'.
        exclude_ids: activity_ids to skip (e.g. ones already attended).
        Returns a DataFrame of the top-n activities with a 'content_score' column.
        """
        exclude_ids = exclude_ids or set()
        candidates = self.activities_df[
            ~self.activities_df["activity_id"].isin(exclude_ids)
        ].copy()

        candidates = candidates[
            candidates["physical_intensity"].apply(
                lambda intensity: self.is_mobility_suitable(
                    resident_row["mobility_level"], intensity
                )
            )
        ]

        candidates["content_score"] = candidates["tags"].apply(
            lambda tags: self._tag_overlap_score(resident_row["interests"], tags)
        )

        return candidates.sort_values("content_score", ascending=False).head(n)