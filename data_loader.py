import pandas as pd

class DataLoader:
   
   def __init__(self,data_dir="data"):
      self.data_dir = data_dir

      self.df_activities = None
      self.df_residents = None
      self.df_interactions = None

   def load_all(self):

      self.df_activities = pd.read_csv(f"{self.data_dir}/activities.csv")
      self.df_residents = pd.read_csv(f"{self.data_dir}/residents.csv")
      self.df_interactions = pd.read_csv(f"{self.data_dir}/interactions.csv")

      return self.df_activities,self.df_residents,self.df_interactions

   def load_activities(self):
      self.df_activities = pd.read_csv(f"{self.data_dir}/activities.csv")
      return self.df_activities

   def load_residents(self):
      self.df_residents = pd.read_csv(f"{self.data_dir}/residents.csv")
      return self.df_residents

   def load_interactions(self):
      self.df_interactions = pd.read_csv(f"{self.data_dir}/interactions.csv")
      return self.df_interactions

   

   
