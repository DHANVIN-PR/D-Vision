
import pandas as pd
from sklearn.cluster import KMeans

def cluster_tutors_by_category(course_data, categories, n_clusters=3):
    # Build feature matrix
    df = pd.DataFrame(columns=['tutor_id'] + categories)

    for data in course_data:
        tutor_id = data['tutor_id']
        category = data['category']
        if tutor_id not in df['tutor_id'].values:
            df = pd.concat([df, pd.DataFrame([[tutor_id] + [0]*len(categories)], columns=['tutor_id'] + categories)], ignore_index=True)
        df.loc[df['tutor_id'] == tutor_id, category] += 1

    df.fillna(0, inplace=True)

    if len(df) < n_clusters:
        return {row['tutor_id']: 0 for _, row in df.iterrows()}

    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    df['cluster'] = kmeans.fit_predict(df[categories])

    return dict(zip(df['tutor_id'], df['cluster']))