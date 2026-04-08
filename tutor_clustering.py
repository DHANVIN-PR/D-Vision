import sqlite3
import pandas as pd
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

# Connect to database
conn = sqlite3.connect("dvision.db")

# Load tutor data
df = pd.read_sql_query("""
SELECT t.id, t.fees, t.rating, t.mode, t.subject, t.location
FROM tutors t
""", conn)

ids = df['id'].tolist()

# Preprocess
df['mode'] = df['mode'].map({'online': 0, 'offline': 1})
df = pd.get_dummies(df, columns=['subject', 'location'])
df = df.fillna(0)

# Perform Clustering
kmeans = KMeans(n_clusters=3, random_state=42)
clusters = kmeans.fit_predict(df.drop(columns=['id']))
df['cluster'] = clusters

# Add cluster column if it doesn't exist
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE tutors ADD COLUMN cluster INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass  # already exists

# Save back to DB
for idx, cluster in zip(ids, clusters):
    cursor.execute("UPDATE tutors SET cluster = ? WHERE id = ?", (int(cluster), idx))

conn.commit()
conn.close()

# Optional: Visualize
plt.scatter(df['fees'], df['rating'], c=df['cluster'], cmap='viridis')
plt.xlabel("Fees")
plt.ylabel("Rating")
plt.title("Tutor Clustering (Fees vs Rating)")
plt.show()
