import pandas as pd
import json
import os

# Create directories if they don't exist
os.makedirs("data/normalized", exist_ok=True)

# Read raw data
movies_df = pd.read_csv("data/raw/tmdb_5000_movies.csv")
credits_df = pd.read_csv("data/raw/tmdb_5000_credits.csv")

# Merge movies and credits on id and movie_id
merged_df = pd.merge(movies_df, credits_df, left_on='id', right_on='movie_id', how='left', suffixes=('_movies', '_credits'))

# Function to safely parse JSON
def safe_json_loads(text):
    if pd.isna(text) or text == '':
        return []
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []

# Normalize movies.csv
movies_normalized = pd.DataFrame()
movies_normalized['movie_id'] = merged_df['id']
movies_normalized['title'] = merged_df['title_movies']
movies_normalized['overview'] = merged_df['overview'].fillna("No overview available.")
movies_normalized['release_date'] = merged_df['release_date']
movies_normalized['runtime'] = merged_df['runtime'].fillna(0)
movies_normalized['vote_average'] = merged_df['vote_average']
movies_normalized['vote_count'] = merged_df['vote_count']
movies_normalized['popularity'] = merged_df['popularity']
movies_normalized['original_language'] = merged_df['original_language']

# Extract director from crew
def get_director(crew_json):
    crew = safe_json_loads(crew_json)
    for member in crew:
        if member.get('job') == 'Director':
            return member.get('name', '')
    return ''

movies_normalized['director'] = merged_df['crew'].apply(get_director)

# Extract top 3 cast
def get_top_cast(cast_json):
    cast = safe_json_loads(cast_json)
    top_cast = [member.get('name', '') for member in cast[:3]]
    return ', '.join(top_cast)

movies_normalized['top_cast'] = merged_df['cast'].apply(get_top_cast)

# Save movies.csv
movies_normalized.to_csv("data/normalized/movies.csv", index=False)

# Normalize genres.csv and movie_genres.csv
genres_list = []
movie_genres_list = []

for _, row in merged_df.iterrows():
    movie_id = row['id']
    genres = safe_json_loads(row['genres'])
    for genre in genres:
        genre_id = genre.get('id')
        genre_name = genre.get('name')
        if genre_id and genre_name:
            genres_list.append({'genre_id': genre_id, 'genre_name': genre_name})
            movie_genres_list.append({'movie_id': movie_id, 'genre_id': genre_id})

genres_df = pd.DataFrame(genres_list).drop_duplicates()
movie_genres_df = pd.DataFrame(movie_genres_list).drop_duplicates()

genres_df.to_csv("data/normalized/genres.csv", index=False)
movie_genres_df.to_csv("data/normalized/movie_genres.csv", index=False)

# Normalize keywords.csv and movie_keywords.csv
keywords_list = []
movie_keywords_list = []

for _, row in merged_df.iterrows():
    movie_id = row['id']
    keywords = safe_json_loads(row['keywords'])
    for keyword in keywords:
        keyword_id = keyword.get('id')
        keyword_name = keyword.get('name')
        if keyword_id and keyword_name:
            keywords_list.append({'keyword_id': keyword_id, 'keyword_name': keyword_name})
            movie_keywords_list.append({'movie_id': movie_id, 'keyword_id': keyword_id})

keywords_df = pd.DataFrame(keywords_list).drop_duplicates()
movie_keywords_df = pd.DataFrame(movie_keywords_list).drop_duplicates()

keywords_df.to_csv("data/normalized/keywords.csv", index=False)
movie_keywords_df.to_csv("data/normalized/movie_keywords.csv", index=False)

print("Data normalization complete!")