"""
collaborative_recommender.py

CollaborativeRecommender finds residents with SIMILAR TASTE (based on how
they rated activities they actually attended) and recommends activities
those similar residents rated highly, which this resident hasn't tried yet.

Key Pandas technique: pivot_table() turns long-format interaction rows into
a wide resident x activity matrix, which is the standard shape for
collaborative filtering.

Handling missing ratings:
  - A resident who never attended an activity has NO rating for it -- this
    is NOT the same as a bad rating, so we must not fill it with 0 directly
    (0 would look like "hated it").
  - Standard fix: mean-center each resident's ratings (subtract their own
    average rating) BEFORE filling missing values with 0. After centering,
    0 means "neutral / unknown" rather than "worst possible", and residents
    who rate everything generously vs. harshly become comparable.
"""

import numpy as np
import pandas as pd


class CollaborativeRecommender:
    def __init__(self):
        self.interactions_df = None
        self.resident_item_matrix = None       # raw ratings, NaN where not rated
        self.centered_matrix = None            # mean-centered, 0-filled (for similarity math)
        self.resident_means = None

    def fit(self, interactions_df):
        """Builds the resident x activity ratings matrix from attended interactions only."""
        self.interactions_df = interactions_df.copy()
        attended = self.interactions_df[self.interactions_df["attended"] == True]  # noqa: E712

        # pivot_table: rows = resident_id, columns = activity_id, values = rating
        self.resident_item_matrix = attended.pivot_table(
            index="resident_id", columns="activity_id", values="rating"
        )

        # Mean-center: subtract each resident's own average rating so a
        # "generous rater" and a "harsh rater" become comparable.
        self.resident_means = self.resident_item_matrix.mean(axis=1)
        self.centered_matrix = self.resident_item_matrix.sub(self.resident_means, axis=0)
        self.centered_matrix = self.centered_matrix.fillna(0)

        return self

    def _cosine_similarity_row(self, target_vector, matrix):
        """
        Computes cosine similarity between one resident's rating vector and
        every row in the matrix. Cosine similarity measures the ANGLE
        between two vectors (ignoring magnitude), which is standard for
        rating-pattern comparison: two residents who both rate everything
        +1 above or -1 below their own average, in the same activities,
        count as similar even if their raw numbers differ.
        """
        target_norm = np.linalg.norm(target_vector)
        if target_norm == 0:
            return pd.Series(0, index=matrix.index)

        matrix_norms = np.linalg.norm(matrix.values, axis=1)
        dot_products = matrix.values @ target_vector
        # avoid divide-by-zero for residents with an all-zero (fully unrated) row
        denom = (matrix_norms * target_norm)
        denom[denom == 0] = 1e-9
        similarities = dot_products / denom
        return pd.Series(similarities, index=matrix.index)

    def recommend_for_resident(self, resident_id, n=5, exclude_ids=None, top_k_neighbors=8):
        """
        Returns a Series of activity_id -> collaborative_score for the given
        resident, based on similar residents' ratings. Returns an empty
        Series if this resident has no ratings yet (cold-start case --
        this is exactly why HybridEngine also needs ContentRecommender).
        """
        exclude_ids = exclude_ids or set()

        if resident_id not in self.centered_matrix.index:
            return pd.Series(dtype=float)  # no history at all -- cold start

        target_vector = self.centered_matrix.loc[resident_id].values
        similarities = self._cosine_similarity_row(target_vector, self.centered_matrix)
        similarities = similarities.drop(index=resident_id, errors="ignore")

        top_neighbors = similarities.sort_values(ascending=False).head(top_k_neighbors)
        top_neighbors = top_neighbors[top_neighbors > 0]  # ignore dissimilar/negative residents

        if top_neighbors.empty:
            return pd.Series(dtype=float)

        # Weighted average of neighbors' RAW ratings (not centered), weighted
        # by how similar each neighbor is -- this is the actual "collaborative" step.
        neighbor_ratings = self.resident_item_matrix.loc[top_neighbors.index]
        weights = top_neighbors  # similarity scores, already > 0

        weighted_sum = neighbor_ratings.mul(weights, axis=0).sum()
        weight_total = neighbor_ratings.notna().mul(weights, axis=0).sum()

        scores = (weighted_sum / weight_total.replace(0, np.nan)).dropna()
        scores = scores.drop(index=[a for a in exclude_ids if a in scores.index], errors="ignore")

        return scores.sort_values(ascending=False).head(n)