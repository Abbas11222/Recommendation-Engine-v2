from data_loader import DataLoader

loader = DataLoader("data")

df_acticivity = loader.load_activities()
df_residents = loader.load_residents()
df_interactions = loader.load_interactions()

print(f"shape of activities {df_acticivity.shape} and shape of residents is {df_residents.shape} and shape of interactions is {df_interactions.shape}")
print(f"missing values {df_acticivity.isnull().sum()}\n {df_residents.isnull().sum()}\n {df_interactions.isnull().sum()}")
