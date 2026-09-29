"""
data_loader.py

DataLoader is the ONLY place in the project that touches the CSV files.
Every other class asks DataLoader for data instead of reading files itself.
This keeps data access in one place, so if the data source ever changes
(e.g. a real database instead of CSVs), only this file needs to change.

LIVE DATA: alongside the original synthetic dataset, the Flask app writes
new interactions/residents to data/live_interactions.csv and
data/live_residents.csv as people use the dashboard. DataLoader merges
these in automatically if present, so the recommender always sees the
full picture (synthetic baseline + real usage) without the two ever being
mixed together on disk -- keeping a clean, honest data lineage.
"""

import os
import pandas as pd


class DataLoader:
    LIVE_INTERACTIONS_FILE = "live_interactions.csv"
    LIVE_RESIDENTS_FILE = "live_residents.csv"

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.residents_df = None
        self.activities_df = None
        self.interactions_df = None

    def load_all(self):
        """Reads all CSVs (base + live, if present) into DataFrames."""
        self.residents_df = pd.read_csv(f"{self.data_dir}/residents.csv")
        self.activities_df = pd.read_csv(f"{self.data_dir}/activities.csv")
        base_interactions = pd.read_csv(f"{self.data_dir}/interactions.csv")

        live_residents_path = f"{self.data_dir}/{self.LIVE_RESIDENTS_FILE}"
        if os.path.exists(live_residents_path):
            live_residents = pd.read_csv(live_residents_path)
            self.residents_df = pd.concat(
                [self.residents_df, live_residents], ignore_index=True
            )

        live_interactions_path = f"{self.data_dir}/{self.LIVE_INTERACTIONS_FILE}"
        if os.path.exists(live_interactions_path):
            live_interactions = pd.read_csv(live_interactions_path)
            self.interactions_df = pd.concat(
                [base_interactions, live_interactions], ignore_index=True
            )
        else:
            self.interactions_df = base_interactions

        # 'rating' loads as float automatically because of the blank cells,
        # and blanks become NaN -- which is exactly what we want, since a
        # missing rating means "didn't attend", not "rating unknown".
        self.interactions_df["rating"] = pd.to_numeric(
            self.interactions_df["rating"], errors="coerce"
        )
        # 'attended' should be a real boolean, not the string "True"/"False"
        self.interactions_df["attended"] = self.interactions_df["attended"].astype(bool)

        return self

    def get_resident(self, resident_id):
        """Returns a single resident's row as a pandas Series, or None if not found."""
        row = self.residents_df[self.residents_df["resident_id"] == resident_id]
        return row.iloc[0] if not row.empty else None

    def get_activity(self, activity_id):
        """Returns a single activity's row as a pandas Series, or None if not found."""
        row = self.activities_df[self.activities_df["activity_id"] == activity_id]
        return row.iloc[0] if not row.empty else None

    def get_resident_history(self, resident_id):
        """Returns all interaction rows (attended or not) for one resident."""
        return self.interactions_df[self.interactions_df["resident_id"] == resident_id]

    def get_attended_only(self):
        """Returns only the rows where the resident actually attended (has a real rating)."""
        return self.interactions_df[self.interactions_df["attended"] == True]  # noqa: E712