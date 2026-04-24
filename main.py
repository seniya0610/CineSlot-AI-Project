import pandas as pd
import sqlite3
import streamlit as st

MOVIES_CSV = "tmdb_5000_movies.csv"
CREDITS_CSV = "tmdb_5000_credits.csv"

pd.set_option('display.expand_frame_repr', False)
pd.set_option('display.max_colwidth', None)

class CineSlotDB:
    def __init__(self):
        self.database = sqlite3.connect(':memory:')
        self._load_and_sync_data()

    def _load_and_sync_data(self):
        movies = pd.read_csv(MOVIES_CSV)
        credits = pd.read_csv(CREDITS_CSV)

        movies.to_sql('movies', self.database, if_exists='replace', index=False)
        credits.to_sql('credits', self.database, if_exists='replace', index=False)

    def read_all(self):
        # We select specific columns and rename 'vote_average' to 'rating'
        query = """
            SELECT 
                movies.id, 
                movies.title, 
                movies.genres, 
                movies.vote_average AS rating
            FROM movies
            JOIN credits ON movies.id = credits.movie_id
        """
        df = pd.read_sql_query(query, self.database)
        return df

# Initialize and test
db = CineSlotDB()
combined_df = db.read_all()

print("Success! Data joined with specific columns.")
print(combined_df.head())
