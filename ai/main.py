import os
import pandas as pd
import streamlit as st
import sqlite3
from datetime import datetime, date
from scheduler import schedule_movies
import requests
import re
from collections import Counter

DB_PATH = "data/movies.db"


# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────

class CineSlotDB:
    def __init__(self):
        self.movies = None
        self.genres = None
        self.movie_genres = None
        self._load_data()

    def _load_data(self):
        if not os.path.exists(DB_PATH):
            return

        conn = sqlite3.connect(DB_PATH)
        self.movies = pd.read_sql("SELECT * FROM movie", conn)
        self.genres = pd.read_sql("SELECT * FROM genre", conn)
        self.movie_genres = pd.read_sql("SELECT * FROM movie_genre", conn)
        conn.close()

        self.movies["overview"] = self.movies["overview"].fillna("No overview available.")
        self.movies["runtime"] = self.movies["runtime"].fillna(0)
        self.movies["vote_average"] = self.movies["vote_average"].fillna(0)

        if "director" in self.movies.columns:
            self.movies["director"] = self.movies["director"].fillna("Unknown")
        else:
            self.movies["director"] = "Unknown"

        if "top_cast" in self.movies.columns:
            self.movies["top_cast"] = self.movies["top_cast"].fillna("Unknown")
        else:
            self.movies["top_cast"] = "Unknown"

    def read_all_movies(self):
        if self.movies is None:
            return pd.DataFrame()
        return self.movies.copy()

    def get_movie_genres(self, movie_id):
        if self.movie_genres is None or self.genres is None:
            return ""
        genre_ids = self.movie_genres[self.movie_genres["movie_id"] == movie_id]["genre_id"].tolist()
        genre_names = self.genres[self.genres["genre_id"].isin(genre_ids)]["genre_name"].tolist()
        return ", ".join(genre_names)

    def build_genre_map(self):
        if self.movie_genres is None or self.genres is None or self.movies is None:
            return {}
        genre_map = {}
        for movie_id in self.movies["movie_id"].unique():
            genre_map[movie_id] = self.get_movie_genres(movie_id)
        return genre_map

    def get_random_unwatched_list(self, count=50):
        if self.movies is None:
            return []
        import random
        all_movie_ids = self.movies["movie_id"].tolist()
        random.shuffle(all_movie_ids)
        return all_movie_ids[:min(count, len(all_movie_ids))]

    # ── Saved Schedules ──────────────────────────────────────────────────────

    def init_saved_schedules_table(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id TEXT NOT NULL,
                slot_date TEXT NOT NULL,
                slot_start TEXT NOT NULL,
                slot_end TEXT NOT NULL,
                slot_duration INTEGER NOT NULL,
                movies_json TEXT NOT NULL,
                total_runtime INTEGER NOT NULL,
                remaining_time INTEGER NOT NULL,
                mood TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def init_trailers_table(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trailers (
                movie_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                youtube_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def get_cached_trailer(self, movie_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT youtube_id FROM trailers WHERE movie_id = ?", (movie_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def save_trailer(self, movie_id, title, youtube_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO trailers (movie_id, title, youtube_id)
            VALUES (?, ?, ?)
        ''', (movie_id, title, youtube_id))
        conn.commit()
        conn.close()

    def save_schedule(self, slot_info, movies_list, mood=None):
        import json
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        movies_json = json.dumps([{
            'movie_id': m['movie_id'],
            'title': m['title'],
            'runtime': m['runtime'],
            'genres': m.get('genres', ''),
            'overview': m.get('overview', ''),
            'vote_average': m.get('vote_average', 0)
        } for m in movies_list])
        total_runtime = slot_info.get('total_runtime', sum(int(m.get('runtime', 0)) for m in movies_list))
        remaining_time = slot_info.get('remaining_time', max(0, int(slot_info.get('duration', 0)) - total_runtime))
        cursor.execute('''
            INSERT INTO saved_schedules
            (slot_id, slot_date, slot_start, slot_end, slot_duration, movies_json,
             total_runtime, remaining_time, mood)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            slot_info.get('slot_id'), slot_info.get('date'), slot_info.get('start'),
            slot_info.get('end'), slot_info.get('duration'), movies_json,
            total_runtime, remaining_time, mood
        ))
        conn.commit()
        conn.close()

    def get_saved_schedules(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT * FROM saved_schedules ORDER BY created_at DESC", conn)
        conn.close()
        return df

    def get_schedule_by_id(self, schedule_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved_schedules WHERE id = ?", (schedule_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            import json
            return {
                'id': row[0], 'slot_id': row[1], 'slot_date': row[2],
                'slot_start': row[3], 'slot_end': row[4], 'slot_duration': row[5],
                'movies': json.loads(row[6]), 'total_runtime': row[7],
                'remaining_time': row[8], 'mood': row[9], 'created_at': row[10]
            }
        return None

    def delete_schedule(self, schedule_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_schedules WHERE id = ?", (schedule_id,))
        conn.commit()
        conn.close()

    # ── Favorites ────────────────────────────────────────────────────────────

    def init_favorites_table(self):
        """Create the per-user favorites table if it doesn't exist."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                movie_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, movie_id)
            )
        ''')
        conn.commit()
        conn.close()

    def add_favorite(self, user_id: str, movie_id: int):
        """Add a movie to a user's favorites. Silently ignores duplicates."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO favorites (user_id, movie_id) VALUES (?, ?)",
            (user_id, movie_id)
        )
        conn.commit()
        conn.close()

    def remove_favorite(self, user_id: str, movie_id: int):
        """Remove a movie from a user's favorites."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM favorites WHERE user_id = ? AND movie_id = ?",
            (user_id, movie_id)
        )
        conn.commit()
        conn.close()

    def is_favorite(self, user_id: str, movie_id: int) -> bool:
        """Return True if a movie is in a user's favorites."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND movie_id = ?",
            (user_id, movie_id)
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def get_favorites(self, user_id: str) -> list[int]:
        """Return all favorited movie_ids for a user."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT movie_id FROM favorites WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]

    # ── Recommendations ───────────────────────────────────────────────────────

    def get_recommendations(self, user_id: str, top_n: int = 10) -> pd.DataFrame:
        """
        Score every non-favorited movie for a user based on:
          - Genre overlap with favorited movies  (weight 3)
          - Director match with favorited movies (weight 2)
          - Popularity/rating boost              (weight 1)

        Returns a DataFrame of top_n recommended movies sorted by score.
        """
        if self.movies is None:
            return pd.DataFrame()

        fav_ids = self.get_favorites(user_id)
        if not fav_ids:
            # Cold start: return top-rated movies
            return self.movies.sort_values("vote_average", ascending=False).head(top_n).copy()

        fav_movies = self.movies[self.movies["movie_id"].isin(fav_ids)]

        # Build genre frequency from favorites
        genre_counter: Counter = Counter()
        for mid in fav_ids:
            for g in self.get_movie_genres(mid).split(", "):
                if g:
                    genre_counter[g] += 1

        # Build director frequency from favorites
        director_counter: Counter = Counter()
        for _, row in fav_movies.iterrows():
            director = str(row.get("director", "Unknown"))
            if director and director != "Unknown":
                director_counter[director] += 1

        # Max vote for normalisation
        max_vote = self.movies["vote_average"].max() or 1

        candidates = self.movies[~self.movies["movie_id"].isin(fav_ids)].copy()

        def score(row):
            s = 0.0
            # Genre score
            movie_genres = self.get_movie_genres(row["movie_id"]).split(", ")
            for g in movie_genres:
                s += genre_counter.get(g, 0) * 3
            # Director score
            director = str(row.get("director", "Unknown"))
            s += director_counter.get(director, 0) * 2
            # Rating boost
            s += (float(row["vote_average"]) / max_vote) * 1
            return s

        candidates["_rec_score"] = candidates.apply(score, axis=1)
        top = candidates.sort_values("_rec_score", ascending=False).head(top_n)
        return top.drop(columns=["_rec_score"])


# ─────────────────────────────────────────────
#  YOUTUBE
# ─────────────────────────────────────────────

class YouTubeTrailerFinder:
    @staticmethod
    def search_youtube_trailer(movie_title):
        try:
            search_query = f"{movie_title} official trailer"
            url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=5)
            video_ids = re.findall(r'watch\?v=(\w+)', response.text)
            return video_ids[0] if video_ids else None
        except Exception as e:
            print(f"Error searching YouTube: {e}")
            return None


# ─────────────────────────────────────────────
#  UI
# ─────────────────────────────────────────────

class CineSlotUI:
    def __init__(self, db: CineSlotDB):
        self.db = db
        self.trailer_finder = YouTubeTrailerFinder()
        self.db.init_trailers_table()
        self.db.init_favorites_table()
        st.set_page_config(
            page_title="CineSlot",
            page_icon="🎬",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        self._apply_theme()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap');

        .stApp { background-color: black; color: white; font-family: 'Lato', sans-serif; }
        header[data-testid="stHeader"] { background-color: black; }

        [data-testid="stSidebar"] {
            background-color: #050505;
            border-right: 1px solid #242424;
            padding-left: 0; padding-right: 0;
        }
        [data-testid="stSidebar"] .stRadio { width: 230%; }
        [data-testid="stSidebar"] .stRadio > div { gap: 10px; }
        [data-testid="stSidebar"] .stRadio label {
            width: 100% !important; min-height: 60px;
            background: linear-gradient(130deg, #111111, #070707);
            color: white !important; border: 1px solid #242424;
            border-radius: 14px; padding: 14px 18px !important;
            margin-bottom: 10px; font-size: 17px; font-weight: 900;
            cursor: pointer; transition: all 0.25s ease-in-out;
        }
        /* DO NOT REMOVE */
        [data-testid="stSidebar"] .stRadio { margin-top: -38px; }
        [data-testid="stSidebar"] .stRadio label:hover {
            background: linear-gradient(130deg, #E5091452, #070707);
            border-color: #db0b15; transform: translateX(6px);
            box-shadow: 0 5px 8px rgba(229, 9, 20, 0.25);
        }
        [data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child { display: none; }

        h1, h2, h3 { color: white; font-weight: 900; }

        .stButton > button {
            background-color: #141414 !important; color: white !important;
            border: 1px solid #333333 !important; border-radius: 12px !important;
            padding: 10px 18px !important; font-weight: 800 !important;
            transition: all 0.25s ease-in-out !important;
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #E5091452, black);
            border-color: #e50914 !important; color: white !important;
        }
        input {
            background-color: #141414 !important; color: white !important;
            border: 1px solid #333333 !important; border-radius: 10px !important;
            padding-right: 2px;
        }
        div[data-baseweb="select"] > div {
            background-color: #141414 !important; color: white !important;
            border-color: #333333 !important; border-radius: 10px !important;
        }

        .hero {
            background: linear-gradient(135deg, #E5091452, #000000F2);
            padding: 42px; border-radius: 26px; border: 1px solid #2a2a2a;
            margin-bottom: 28px; box-shadow: 0 20px 60px rgba(0,0,0,0.45);
        }
        .hero-title {
            font-family: 'Bebas Neue', sans-serif; font-size: 78px;
            line-height: 0.9; letter-spacing: 3px; color: white;
        }
        .hero-subtitle { color: #d0d0d0; font-size: 18px; max-width: 760px; margin-top: 16px; }

        .section-card {
            background: linear-gradient(145deg, #151515, #080808);
            border: 1px solid #2a2a2a; border-radius: 20px; padding: 24px;
            margin-bottom: 18px; box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            transition: all 0.25s ease-in-out;
        }
        .section-card:hover {
            border: 1px solid #db0b15; border-left: 5px solid #e50914;
            border-top: 1px solid #2a2a2a; border-right: 1px solid #2a2a2a;
            border-bottom: 1px solid #2a2a2a; transform: translateX(5px);
            background: linear-gradient(135deg, #E5091452, #000000F2);
        }

        .movie-card {
            background: #111111; border: 1px solid #252525;
            border-left: 5px solid #e50914; border-radius: 18px;
            padding: 22px; margin-bottom: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.35);
            transition: all 0.25s ease-in-out;
        }
        .movie-card:hover {
            background: linear-gradient(135deg, #171717, #080808);
            border-color: #e50914; transform: translateX(10px);
        }
        .movie-title { font-size: 26px; font-weight: 900; color: white; margin-bottom: 8px; }
        .movie-meta { color: #e50914; font-weight: 800; margin-bottom: 10px; }
        .movie-detail { color: #cfcfcf; margin-top: 6px; line-height: 1.5; }

        /* Favorite badge */
        .fav-badge {
            background: linear-gradient(135deg, #e50914, #8b0000);
            color: white; padding: 4px 12px; border-radius: 20px;
            font-weight: 900; font-size: 13px; display: inline-block;
            margin-left: 10px; vertical-align: middle;
        }

        /* Recommendation score pill */
        .rec-rank {
            background: linear-gradient(135deg, #1a0a00, #3d1500);
            color: #ff6b35; border: 1px solid #5a2000;
            padding: 6px 14px; border-radius: 20px;
            font-weight: 900; font-size: 13px; display: inline-block;
        }

        .slot-card {
            background: linear-gradient(145deg, #141414, #080808);
            padding: 18px 20px; border-radius: 16px; border-left: 5px solid #e50914;
            border-top: 1px solid #2a2a2a; border-right: 1px solid #2a2a2a;
            border-bottom: 1px solid #2a2a2a; margin-bottom: 12px;
            box-shadow: 0 8px 22px rgba(0,0,0,0.4);
        }
        .mode-card {
            background: linear-gradient(145deg, #141414, #090909);
            padding: 22px; border-radius: 18px; border: 1px solid #2a2a2a;
            min-height: 150px; margin-bottom: 12px; min-width: 300;
            max-width: 300; min-height: 200px; box-shadow: 0 20px 50px rgba(0,0,0,0.35);
            transition: all 0.25s ease-in-out; display: flex; flex-direction: column;
        }
        .mode-card:hover { border-color: #e50914; }

        .red-pill {
            background-color: #250000; color: #ff4b4b; padding: 8px 14px;
            border-radius: 20px; font-weight: 800; border: 1px solid #5a0000;
            display: inline-block;
        }
        .empty-box {
            background-color: #111111; padding: 18px; border-radius: 14px;
            border: 1px dashed #3a3a3a; color: #999999; margin-top: 18px;
        }
        .random-box {
            background: #0c0c0c; border: 1px solid #2a2a2a; border-radius: 20px;
            padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.35); margin-bottom: 20px;
        }
        .trailer-container {
            background: #0a0a0a; border: 2px solid #e50914; border-radius: 16px;
            padding: 20px; margin-top: 15px; box-shadow: 0 8px 24px rgba(229, 9, 20, 0.3);
        }
        .trailer-player { width: 100%; aspect-ratio: 16 / 9; border-radius: 12px; border: 1px solid #2a2a2a; }

        /* User identity bar */
        .user-bar {
            background: linear-gradient(135deg, #0f0f0f, #1a0000);
            border: 1px solid #2a2a2a; border-radius: 12px;
            padding: 12px 18px; margin-bottom: 20px;
            display: flex; align-items: center; gap: 12px;
        }
        </style>
        """, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _render_sidebar(self):
        with st.sidebar:
            st.markdown("""
            <div style="padding: 28px 6px 14px 6px;">
                <div style="font-size:68px;font-weight:400;color:white;font-family:'Bebas Neue',sans-serif;line-height:0.86;letter-spacing:4px;">
                    CINE<br>SLOT
                </div>
                <div style="font-size:12px;color:#e50914;letter-spacing:3px;margin-top:12px;font-weight:900;">
                    AI MOVIE SCHEDULER
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<hr style='border-color:#2a2a2a; margin: 18px 0;'>", unsafe_allow_html=True)

            page = st.radio(
                "navigate",
                ["Home", "Browse", "Favorites", "Recommendations", "Unwatched", "Schedule", "Saved Schedules", "About"],
                label_visibility="hidden"
            )

            st.markdown("<hr style='border-color:#2a2a2a; margin: 18px 0;'>", unsafe_allow_html=True)

            # ── User identity (session-based) ──────────────────────────────
            if "cineslot_user" not in st.session_state:
                st.session_state.cineslot_user = None

            if st.session_state.cineslot_user:
                st.markdown(f"""
                <div style="padding:10px 6px; color:#b3b3b3; font-size:13px;">
                    👤 Signed in as<br>
                    <span style="color:#e50914; font-weight:900; font-size:15px;">
                        {st.session_state.cineslot_user}
                    </span>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Sign Out", key="sidebar_signout"):
                    st.session_state.cineslot_user = None
                    st.rerun()
            else:
                st.markdown("<div style='color:#b3b3b3;font-size:13px;padding:6px;'>Sign in to use Favorites</div>", unsafe_allow_html=True)
                username_input = st.text_input("Username", key="sidebar_username_input", placeholder="Enter username…")
                if st.button("Sign In", key="sidebar_signin"):
                    name = username_input.strip()
                    if name:
                        st.session_state.cineslot_user = name
                        st.rerun()
                    else:
                        st.warning("Please enter a username.")

            st.markdown("<hr style='border-color:#2a2a2a; margin: 18px 0;'>", unsafe_allow_html=True)
            st.caption("CineSlot v1 <br> Smart movie planning with time-aware scheduling.", unsafe_allow_html=True)

        return page

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self):
        page = self._render_sidebar()

        if not os.path.exists(DB_PATH) or self.db.movies is None:
            st.error("Database not found. Please ensure data/movies.db exists.")
            return

        if page == "Home":
            self._page_home()
        elif page == "Browse":
            self._page_browse()
        elif page == "Favorites":
            self._page_favorites()
        elif page == "Recommendations":
            self._page_recommendations()
        elif page == "Unwatched":
            self._page_unwatched()
        elif page == "Schedule":
            self._page_schedule()
        elif page == "Saved Schedules":
            self._page_saved_schedules()
        elif page == "About":
            self._page_about()

    # ── Helpers: trailer ──────────────────────────────────────────────────────

    def _get_trailer_id(self, movie_id, movie_title):
        cached_id = self.db.get_cached_trailer(movie_id)
        if cached_id:
            return cached_id
        trailer_id = self.trailer_finder.search_youtube_trailer(movie_title)
        if trailer_id:
            self.db.save_trailer(movie_id, movie_title, trailer_id)
        return trailer_id

    # ── Helpers: movie card ───────────────────────────────────────────────────

    def _render_movie_card(self, movie, card_key_prefix="mc", show_fav_button=True,
                           show_unwatched_button=True, extra_badge_html=""):
        """
        Universal movie card renderer.
        card_key_prefix  – unique prefix for Streamlit widget keys
        show_fav_button  – show ❤️ / 💔 favorite toggle
        show_unwatched_button – show ➕ Unwatched button
        extra_badge_html – optional HTML injected next to the title (e.g. rec rank)
        """
        release_year = str(movie["release_date"])[:4] if pd.notna(movie["release_date"]) else "N/A"
        runtime = int(movie["runtime"]) if pd.notna(movie["runtime"]) else 0
        rating = float(movie["vote_average"]) if pd.notna(movie["vote_average"]) else 0.0
        genres = self.db.get_movie_genres(movie["movie_id"])
        mid = movie["movie_id"]
        user = st.session_state.get("cineslot_user")

        # Is this already a favorite?
        is_fav = user and self.db.is_favorite(user, mid)
        fav_html = '<span class="fav-badge">❤ Favorite</span>' if is_fav else ""

        st.markdown(f"""
        <div class="movie-card">
            <div class="movie-title">{movie["title"]}{fav_html}{extra_badge_html}</div>
            <div class="movie-meta">{release_year} · {runtime} min · ⭐ {rating:.1f}</div>
            <div class="movie-detail"><b>Genres:</b> {genres or "N/A"}</div>
            <div class="movie-detail"><b>Director:</b> {movie["director"]}</div>
            <div class="movie-detail"><b>Top Cast:</b> {movie["top_cast"]}</div>
            <div class="movie-detail"><b>Overview:</b> {movie["overview"]}</div>
        </div>
        """, unsafe_allow_html=True)

        # Build button columns dynamically
        btn_slots = []
        if True:            btn_slots.append("trailer")
        if show_fav_button: btn_slots.append("fav")
        if show_unwatched_button: btn_slots.append("unwatched")

        n = len(btn_slots)
        spacer_cols = st.columns([2] + [1] * n)

        col_map = {name: spacer_cols[i + 1] for i, name in enumerate(btn_slots)}

        # Trailer button
        with col_map["trailer"]:
            if st.button("🎬 Trailer", key=f"trailer_{card_key_prefix}_{mid}", use_container_width=True):
                st.session_state[f"show_trailer_{card_key_prefix}_{mid}"] = True

        # Favorite toggle
        if show_fav_button and "fav" in col_map:
            with col_map["fav"]:
                if not user:
                    st.button("❤️ Fav", key=f"fav_{card_key_prefix}_{mid}",
                              use_container_width=True, disabled=True,
                              help="Sign in to use Favorites")
                elif is_fav:
                    if st.button("💔 Unfav", key=f"fav_{card_key_prefix}_{mid}", use_container_width=True):
                        self.db.remove_favorite(user, mid)
                        st.success(f"Removed '{movie['title']}' from Favorites.")
                        st.rerun()
                else:
                    if st.button("❤️ Fav", key=f"fav_{card_key_prefix}_{mid}", use_container_width=True):
                        self.db.add_favorite(user, mid)
                        st.success(f"Added '{movie['title']}' to Favorites!")
                        st.rerun()

        # Unwatched button
        if show_unwatched_button and "unwatched" in col_map:
            with col_map["unwatched"]:
                if st.button("➕ Unwatched", key=f"unwatched_{card_key_prefix}_{mid}", use_container_width=True):
                    if "unwatched_ids" not in st.session_state:
                        st.session_state.unwatched_ids = []
                    if mid not in st.session_state.unwatched_ids:
                        st.session_state.unwatched_ids.append(mid)
                        st.success(f"Added '{movie['title']}' to unwatched list!")
                    else:
                        st.info(f"'{movie['title']}' is already in your unwatched list.")

        # Trailer embed
        trailer_key = f"show_trailer_{card_key_prefix}_{mid}"
        if st.session_state.get(trailer_key, False):
            with st.spinner("🔍 Searching for trailer..."):
                trailer_id = self._get_trailer_id(mid, movie["title"])
            if trailer_id:
                st.markdown(f"""
                <div class="trailer-container">
                    <div style="color:#e50914;font-weight:900;margin-bottom:15px;">🎬 TRAILER</div>
                    <iframe class="trailer-player" src="https://www.youtube.com/embed/{trailer_id}"
                            frameborder="0"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowfullscreen></iframe>
                </div>
                """, unsafe_allow_html=True)
                if st.button("✕ Close Trailer", key=f"close_{card_key_prefix}_{mid}", use_container_width=True):
                    st.session_state[trailer_key] = False
                    st.rerun()
            else:
                st.warning(f"Trailer not found for '{movie['title']}'. Try searching YouTube directly.")

    def _render_movie_card_with_unwatched(self, movie, show_add_button=True):
        """Legacy wrapper for the Unwatched page (remove button variant)."""
        release_year = str(movie["release_date"])[:4] if pd.notna(movie["release_date"]) else "N/A"
        runtime = int(movie["runtime"]) if pd.notna(movie["runtime"]) else 0
        rating = float(movie["vote_average"]) if pd.notna(movie["vote_average"]) else 0.0
        genres = self.db.get_movie_genres(movie["movie_id"])
        mid = movie["movie_id"]
        user = st.session_state.get("cineslot_user")
        is_fav = user and self.db.is_favorite(user, mid)
        fav_html = '<span class="fav-badge">❤ Favorite</span>' if is_fav else ""

        st.markdown(f"""
        <div class="movie-card">
            <div class="movie-title">{movie["title"]}{fav_html}</div>
            <div class="movie-meta">{release_year} · {runtime} min · ⭐ {rating:.1f}</div>
            <div class="movie-detail"><b>Genres:</b> {genres or "N/A"}</div>
            <div class="movie-detail"><b>Director:</b> {movie["director"]}</div>
            <div class="movie-detail"><b>Top Cast:</b> {movie["top_cast"]}</div>
            <div class="movie-detail"><b>Overview:</b> {movie["overview"]}</div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2, 1, 1])

        with col2:
            if st.button("🎬 Trailer", key=f"trailer_unwatched_{mid}", use_container_width=True):
                st.session_state[f"show_trailer_unwatched_{mid}"] = True

        with col3:
            if st.button("➖ Remove", key=f"remove_unwatched_{mid}", use_container_width=True):
                if "unwatched_ids" in st.session_state and mid in st.session_state.unwatched_ids:
                    st.session_state.unwatched_ids.remove(mid)
                    st.success(f"Removed '{movie['title']}' from unwatched list!")
                    st.rerun()

        trailer_key = f"show_trailer_unwatched_{mid}"
        if st.session_state.get(trailer_key, False):
            with st.spinner("🔍 Searching for trailer..."):
                trailer_id = self._get_trailer_id(mid, movie["title"])
            if trailer_id:
                st.markdown(f"""
                <div class="trailer-container">
                    <div style="color:#e50914;font-weight:900;margin-bottom:15px;">🎬 TRAILER</div>
                    <iframe class="trailer-player" src="https://www.youtube.com/embed/{trailer_id}"
                            frameborder="0"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowfullscreen></iframe>
                </div>
                """, unsafe_allow_html=True)
                if st.button("✕ Close Trailer", key=f"close_trailer_unwatched_{mid}", use_container_width=True):
                    st.session_state[trailer_key] = False
                    st.rerun()
            else:
                st.warning(f"Trailer not found for '{movie['title']}'. Try searching YouTube directly.")

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _page_home(self):
        movies = self.db.read_all_movies()

        st.markdown("""
        <div class="hero">
            <div class="hero-title">YOUR MOVIE NIGHT,<br>PLANNED SMARTER.</div>
            <div class="hero-subtitle">
                Browse movies, create watch windows, and prepare schedules based on time, mood, and movie preferences.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)
        cards = [
            ("Browse", "Explore clean movie cards from normalized TMDB data."),
            ("Schedule", "Add multiple time slots across days and choose a scheduling style."),
            ("Favorites", "Heart movies you love and get personalized recommendations."),
            ("Recommendations", "AI-powered suggestions based on your taste profile."),
        ]
        for col, (title, desc) in zip([col1, col2, col3, col4], cards):
            with col:
                st.markdown(f"""
                <div class="section-card">
                    <h3>{title}</h3>
                    <p style="color:#b3b3b3;">{desc}</p>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("## Featured Movies")
        if movies.empty:
            st.warning("No movie data available.")
            return
        featured = movies.sort_values(by="vote_average", ascending=False).head(6)
        for _, movie in featured.iterrows():
            self._render_movie_card(movie, card_key_prefix="home")

    def _page_browse(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">BROWSE MOVIES</div>
            <div class="hero-subtitle">Search and filter movies from your normalized dataset.</div>
        </div>
        """, unsafe_allow_html=True)

        movies = self.db.read_all_movies()
        if movies.empty:
            st.warning("No movie data available.")
            return

        all_genres = ["All"] + sorted(self.db.genres["genre_name"].dropna().unique().tolist())

        col1, col2 = st.columns([2, 1])
        with col1:
            search = st.text_input("Search by title", "")
        with col2:
            selected_genre = st.selectbox("Genre", all_genres)

        col3, col4 = st.columns(2)
        with col3:
            max_runtime = int(movies["runtime"].max()) if not movies.empty else 300
            runtime_min, runtime_max = st.slider("Runtime", 0, max_runtime, (0, max_runtime))
        with col4:
            rating_min, rating_max = st.slider("Rating", 0.0, 10.0, (0.0, 10.0))

        filtered = movies.copy()
        if search:
            filtered = filtered[filtered["title"].str.contains(search, case=False, na=False)]
        if selected_genre != "All":
            genre_id = self.db.genres[self.db.genres["genre_name"] == selected_genre]["genre_id"].values[0]
            movie_ids = self.db.movie_genres[self.db.movie_genres["genre_id"] == genre_id]["movie_id"].tolist()
            filtered = filtered[filtered["movie_id"].isin(movie_ids)]
        filtered = filtered[
            (filtered["runtime"] >= runtime_min) & (filtered["runtime"] <= runtime_max) &
            (filtered["vote_average"] >= rating_min) & (filtered["vote_average"] <= rating_max)
        ]

        st.markdown(f"### Showing {len(filtered)} movies")
        if filtered.empty:
            st.info("No movies match the selected filters.")
            return
        for _, movie in filtered.head(40).iterrows():
            self._render_movie_card(movie, card_key_prefix="browse")

    # ── Favorites page ────────────────────────────────────────────────────────

    def _page_favorites(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">YOUR FAVORITES</div>
            <div class="hero-subtitle">
                Movies you love — saved to your profile. These power your personalized recommendations.
            </div>
        </div>
        """, unsafe_allow_html=True)

        user = st.session_state.get("cineslot_user")

        if not user:
            st.markdown("""
            <div class="empty-box">
                ❤️ Sign in from the sidebar to save and view your Favorites.
            </div>
            """, unsafe_allow_html=True)
            return

        fav_ids = self.db.get_favorites(user)
        movies_df = self.db.read_all_movies()

        st.markdown(f"""
        <div class="section-card">
            <h3>❤ {user}'s Favorites — {len(fav_ids)} movie{"s" if len(fav_ids) != 1 else ""}</h3>
            <p style="color:#b3b3b3;">Remove movies with 💔 Unfav or browse more in the Browse tab.</p>
        </div>
        """, unsafe_allow_html=True)

        if not fav_ids:
            st.markdown("""
            <div class="empty-box">
                No favorites yet. Hit ❤️ Fav on any movie card to add it here!
            </div>
            """, unsafe_allow_html=True)
            return

        fav_movies = movies_df[movies_df["movie_id"].isin(fav_ids)].copy()
        # Keep user's add-order
        fav_movies["_order"] = fav_movies["movie_id"].map({mid: i for i, mid in enumerate(fav_ids)})
        fav_movies = fav_movies.sort_values("_order").drop(columns=["_order"])

        for _, movie in fav_movies.iterrows():
            self._render_movie_card(movie, card_key_prefix="fav",
                                    show_unwatched_button=False)

        # Genre breakdown
        st.markdown("---")
        st.markdown("## Your Taste Profile")
        genre_counter: Counter = Counter()
        for mid in fav_ids:
            for g in self.db.get_movie_genres(mid).split(", "):
                if g:
                    genre_counter[g] += 1

        if genre_counter:
            top_genres = genre_counter.most_common(8)
            genre_html = " ".join([
                f'<span style="background:#1a0a0a;color:#e50914;border:1px solid #5a0000;'
                f'padding:6px 14px;border-radius:20px;font-weight:800;margin:4px;display:inline-block;">'
                f'{g} <span style="color:#ff6b35">×{c}</span></span>'
                for g, c in top_genres
            ])
            st.markdown(f"""
            <div class="random-box">
                <div style="color:#b3b3b3;font-size:13px;margin-bottom:10px;font-weight:900;letter-spacing:2px;">
                    TOP GENRES FROM YOUR FAVORITES
                </div>
                {genre_html}
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="section-card" style="margin-top:12px;">
                <p style="color:#b3b3b3;">
                    Head to <strong style="color:white;">Recommendations</strong> to see movies
                    CineSlot picked just for you based on this profile.
                </p>
            </div>
            """, unsafe_allow_html=True)

    # ── Recommendations page ──────────────────────────────────────────────────

    def _page_recommendations(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">RECOMMENDED<br>FOR YOU</div>
            <div class="hero-subtitle">
                Movies curated by CineSlot based on your Favorites — genre affinity, directors, and ratings.
            </div>
        </div>
        """, unsafe_allow_html=True)

        user = st.session_state.get("cineslot_user")

        if not user:
            st.markdown("""
            <div class="empty-box">
                Sign in from the sidebar and add some Favorites to get personalized recommendations.
            </div>
            """, unsafe_allow_html=True)
            return

        fav_ids = self.db.get_favorites(user)

        if not fav_ids:
            st.markdown("""
            <div class="section-card">
                <h3>No Favorites yet</h3>
                <p style="color:#b3b3b3;">
                    Go to Browse, heart a few movies you love, then come back here for recommendations.
                    Showing top-rated movies in the meantime.
                </p>
            </div>
            """, unsafe_allow_html=True)

        top_n = st.slider("Number of recommendations", 5, 30, 10, key="rec_top_n")
        recs = self.db.get_recommendations(user, top_n=top_n)

        if recs.empty:
            st.warning("No recommendations found.")
            return

        # Build a quick genre-affinity explanation
        if fav_ids:
            genre_counter: Counter = Counter()
            for mid in fav_ids:
                for g in self.db.get_movie_genres(mid).split(", "):
                    if g:
                        genre_counter[g] += 1
            top3 = [g for g, _ in genre_counter.most_common(3)]
            affinity_str = ", ".join(top3) if top3 else "mixed"

            st.markdown(f"""
            <div class="random-box">
                <div style="color:#b3b3b3;font-size:13px;font-weight:900;letter-spacing:2px;margin-bottom:6px;">
                    WHY THESE MOVIES?
                </div>
                <p style="color:#cfcfcf;margin:0;">
                    Based on your Favorites, CineSlot detected a strong preference for
                    <strong style="color:#e50914;">{affinity_str}</strong> films.
                    Each recommendation below is scored by genre overlap (×3), director match (×2),
                    and overall rating (×1).
                </p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"### {len(recs)} Recommendations")

        for rank, (_, movie) in enumerate(recs.iterrows(), start=1):
            badge = f'<span class="rec-rank">#{rank} Pick</span>'
            self._render_movie_card(movie, card_key_prefix=f"rec{rank}",
                                    show_unwatched_button=True,
                                    extra_badge_html=badge)

    # ── Unwatched page ────────────────────────────────────────────────────────

    def _page_unwatched(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">UNWATCHED LIST</div>
            <div class="hero-subtitle">
                Your personal movie queue. Add movies you want to watch and use this list for scheduling.
            </div>
        </div>
        """, unsafe_allow_html=True)

        unwatched_ids = st.session_state.get("unwatched_ids", [])
        movies_df = self.db.read_all_movies()

        if not unwatched_ids:
            st.markdown("""
            <div class="empty-box">
                Your unwatched list is empty. Browse movies and add them to your list!
            </div>
            """, unsafe_allow_html=True)
            return

        unwatched_movies = movies_df[movies_df["movie_id"].isin(unwatched_ids)].copy()

        st.markdown(f"""
        <div class="section-card">
            <h3>{len(unwatched_movies)} Movies in Your Unwatched List</h3>
            <p style="color:#b3b3b3;">These movies will be used when you select "Unwatched List" scheduling mode.</p>
        </div>
        """, unsafe_allow_html=True)

        unwatched_movies = unwatched_movies.sort_values("vote_average", ascending=False)
        for _, movie in unwatched_movies.iterrows():
            self._render_movie_card_with_unwatched(movie, show_add_button=False)

    # ── Schedule page (unchanged logic, reuses new card renderer) ────────────

    def _page_schedule(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">SCHEDULE</div>
            <div class="hero-subtitle">
                Add your available watch windows. <br> Select a date, start time, and end time. You can add multiple slots.
            </div>
        </div>
        """, unsafe_allow_html=True)

        for key, default in [
            ("slots", []), ("schedule_mode", None), ("selected_mood", None),
            ("current_schedule", None), ("schedule_generated", False),
            ("excluded_movie_ids", []), ("last_schedule_context", None),
            ("saved_schedules", []), ("regenerate_requested", False),
        ]:
            if key not in st.session_state:
                st.session_state[key] = default

        if "unwatched_ids" not in st.session_state:
            st.session_state.unwatched_ids = self.db.get_random_unwatched_list(50)

        col1, col2, col3 = st.columns([1.4, 1, 1])
        with col1:
            selected_date = st.date_input("Select Date", min_value=date.today(), key="date_picker")
        with col2:
            start_time = st.time_input("Start Time", key="start_time")
        with col3:
            end_time = st.time_input("End Time", key="end_time")

        if st.button("Add Time Slot"):
            start_dt = datetime.combine(selected_date, start_time)
            end_dt = datetime.combine(selected_date, end_time)
            if end_dt <= start_dt:
                st.error("End time must be after start time.")
            else:
                duration = int((end_dt - start_dt).total_seconds() / 60)
                overlap_found = any(
                    (start_dt < datetime.combine(selected_date,
                        datetime.strptime(s["end"], "%I:%M %p").time()) and
                     end_dt > datetime.combine(selected_date,
                        datetime.strptime(s["start"], "%I:%M %p").time()))
                    for s in st.session_state.slots
                    if s["date"] == selected_date.strftime("%A, %d %B")
                )
                if overlap_found:
                    st.error("This time slot overlaps with an existing slot on the same day.")
                else:
                    st.session_state.slots.append({
                        "slot_id": len(st.session_state.slots) + 1,
                        "date": selected_date.strftime("%A, %d %B"),
                        "start": start_time.strftime("%I:%M %p"),
                        "end": end_time.strftime("%I:%M %p"),
                        "duration": duration
                    })
                    st.success("Time slot added.")

        if not st.session_state.slots:
            st.markdown('<div class="empty-box">No slots added yet. Add at least one watch window to continue.</div>', unsafe_allow_html=True)
            return

        st.markdown("## Your Watch Windows")
        for slot in st.session_state.slots:
            st.markdown(f"""
            <div class="slot-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-size:22px;font-weight:900;color:white;">{slot["date"]}</div>
                        <div style="color:#b3b3b3;margin-top:5px;">{slot["start"]} → {slot["end"]}</div>
                    </div>
                    <div class="red-pill">{slot["duration"]} min</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("## Select Slots for Scheduling")
        selected_slots_indices = []
        cols = st.columns(min(2, len(st.session_state.slots)))
        for idx, slot in enumerate(st.session_state.slots):
            with cols[idx % len(cols)]:
                label = f"{slot['slot_id']}: {slot['date']} {slot['start']} → {slot['end']} ({slot['duration']} min)"
                if st.checkbox(label, key=f"slot_{idx}", value=(idx == 0)):
                    selected_slots_indices.append(idx)

        selected_slots = [st.session_state.slots[i] for i in selected_slots_indices]
        if selected_slots:
            labels = " • ".join(f"{st.session_state.slots[i]['slot_id']}: {st.session_state.slots[i]['date']} {st.session_state.slots[i]['start']} → {st.session_state.slots[i]['end']}" for i in selected_slots_indices)
            st.markdown(f"""
            <div style="background:#0a0a0a;padding:15px;border-radius:8px;border-left:4px solid #e50914;margin-top:10px;">
                <strong style="color:#e50914;">Selected {len(selected_slots)} slot(s):</strong><br>{labels}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Please select at least one slot to continue.")

        if st.button("Clear Slots"):
            for k in ["slots", "schedule_mode", "selected_mood", "current_schedule",
                      "excluded_movie_ids", "last_schedule_context", "unwatched_ids"]:
                st.session_state.pop(k, None)
            st.session_state.update({"schedule_generated": False, "regenerate_requested": False})
            st.rerun()

        st.markdown("## Choose Scheduling Style")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""<div class="mode-card"><div style="font-size:26px;font-weight:900;color:white;">Mood-Based</div><div style="color:#b3b3b3;margin-top:8px;">Choose a mood and CineSlot will filter movies using related genres.</div><div style="color:#e50914;margin-top:14px;font-weight:800;">Example: Excited → Action, Adventure, Sci-Fi</div></div>""", unsafe_allow_html=True)
            if st.button("Choose Mood-Based"):
                st.session_state.schedule_mode = "Mood Based"
        with col2:
            st.markdown("""<div class="mode-card"><div style="font-size:26px;font-weight:900;color:white;">Unwatched List</div><div style="color:#b3b3b3;margin-top:8px;">CineSlot will choose from movies the user has not watched yet.</div><div style="color:#e50914;margin-top:14px;font-weight:800;">Best for personal scheduling</div></div>""", unsafe_allow_html=True)
            if st.button("Choose Unwatched List"):
                st.session_state.schedule_mode = "Unwatched List"

        if st.session_state.schedule_mode is not None:
            st.markdown(f"""
            <div style="background:#111111;padding:16px 20px;border-radius:14px;border:1px solid #e50914;margin-top:22px;color:white;">
                Selected Mode: <span style="color:#e50914;font-weight:900;">{st.session_state.schedule_mode}</span>
            </div>
            """, unsafe_allow_html=True)

            if st.session_state.schedule_mode == "Mood Based":
                st.session_state.selected_mood = st.selectbox(
                    "Select Mood", ["Happy", "Excited", "Romantic", "Scared", "Relaxed", "Thoughtful"]
                )
            if st.session_state.schedule_mode == "Unwatched List":
                cnt = len(st.session_state.get("unwatched_ids", []))
                (st.success if cnt > 0 else st.warning)(f"Using {cnt} movies from your unwatched list" if cnt > 0 else "Your unwatched list is empty. Add movies to it first!")

            def perform_schedule_generation(regeneration=False):
                genre_map = self.db.build_genre_map()
                movies_df = self.db.read_all_movies()
                if movies_df.empty:
                    st.error("No movies loaded from database"); return False
                if not selected_slots:
                    st.error("Select at least one slot to schedule."); return False

                current_context = {
                    "mode": st.session_state.schedule_mode,
                    "mood": st.session_state.selected_mood if st.session_state.schedule_mode == "Mood Based" else None,
                    "slots": [(s['slot_id'], s['date'], s['start'], s['end'], s['duration']) for s in selected_slots]
                }
                if st.session_state.last_schedule_context != current_context:
                    st.session_state.excluded_movie_ids = []
                    st.session_state.last_schedule_context = current_context

                try:
                    schedule = schedule_movies(
                        movies_df, genre_map, selected_slots, st.session_state.schedule_mode,
                        mood=st.session_state.selected_mood if st.session_state.schedule_mode == "Mood Based" else None,
                        unwatched_ids=st.session_state.get("unwatched_ids"),
                        excluded_movie_ids=st.session_state.get("excluded_movie_ids", [])
                    )
                    if schedule:
                        st.session_state.current_schedule = schedule
                        st.session_state.schedule_generated = True
                        st.session_state.regenerate_requested = False
                        return True
                    else:
                        msg = "No new schedule could be generated." if regeneration else "Scheduler found no valid movies. Try longer slots or a different mood."
                        st.warning(msg) if regeneration else st.error(msg)
                        return False
                except Exception as e:
                    st.error(f"Error generating schedule: {e}"); return False

            if st.button("Generate Schedule"):
                perform_schedule_generation(regeneration=False)
            if st.session_state.regenerate_requested:
                perform_schedule_generation(regeneration=True)

        if st.session_state.get("schedule_generated") and st.session_state.get("current_schedule"):
            schedule = st.session_state.current_schedule
            st.markdown("""<div class="section-card"><h2 style="color:#e50914;">✓ Schedule Generated</h2><p style="color:#b3b3b3;">Your movies are scheduled using CSP with MRV and LCV heuristics.</p></div>""", unsafe_allow_html=True)

            for _, slot_info in sorted(schedule.items()):
                slot = slot_info['slot']
                movies = slot_info['movies']
                st.markdown(f"""
                <div class="slot-card" style="border-left:5px solid #e50914;margin-bottom:20px;">
                    <div style="font-size:24px;font-weight:900;color:white;margin-bottom:10px;">{slot['date']} • {slot['start']} → {slot['end']}</div>
                    <div style="color:#b3b3b3;margin-bottom:15px;">Total: {slot_info['total_runtime']} min used • {slot_info['remaining_time']} min remaining</div>
                </div>
                """, unsafe_allow_html=True)
                for movie in movies:
                    st.markdown(f"""
                    <div class="movie-card" style="margin-left:20px;">
                        <div class="movie-title">{movie['title']}</div>
                        <div class="movie-meta">{movie['vote_average']}/10 • {movie['runtime']} min</div>
                        <div class="movie-detail"><strong>Genres:</strong> {movie['genres']}</div>
                    </div>
                    """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Schedule", key="save_schedule"):
                    self.db.init_saved_schedules_table()
                    saved = sum(1 for slot_info in schedule.values() if slot_info['movies'] and slot_info.get('slot') and (self.db.save_schedule(slot_info['slot'], slot_info['movies'], st.session_state.get("selected_mood")) or True))
                    st.success(f"Schedule saved! {saved} slot(s) saved.")
            with col2:
                if st.button("Regenerate Schedule", key="regenerate"):
                    if st.session_state.get("current_schedule"):
                        new_excl = [m['movie_id'] for si in st.session_state.current_schedule.values() for m in si['movies']]
                        st.session_state.excluded_movie_ids = list(set(st.session_state.get("excluded_movie_ids", []) + new_excl))
                    st.session_state.schedule_generated = False
                    st.session_state.current_schedule = None
                    st.session_state.regenerate_requested = True
                    st.rerun()

    # ── Saved Schedules page ──────────────────────────────────────────────────

    def _page_saved_schedules(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">SAVED SCHEDULES</div>
            <div class="hero-subtitle">View and manage your previously saved movie schedules.</div>
        </div>
        """, unsafe_allow_html=True)

        self.db.init_saved_schedules_table()
        saved_df = self.db.get_saved_schedules()

        if saved_df.empty:
            st.markdown('<div class="empty-box">No saved schedules yet. Generate and save a schedule from the Schedule page.</div>', unsafe_allow_html=True)
            return

        slot_groups = {}
        for _, row in saved_df.iterrows():
            key = f"{row['slot_id']}: {row['slot_date']} {row['slot_start']} → {row['slot_end']}"
            slot_groups.setdefault(key, []).append({
                'id': row['id'], 'slot_duration': row['slot_duration'],
                'movies': row['movies_json'], 'total_runtime': row['total_runtime'],
                'remaining_time': row['remaining_time'], 'mood': row['mood'], 'created_at': row['created_at']
            })

        st.markdown("## Your Saved Schedules")
        for slot_key, schedules in slot_groups.items():
            latest = max(schedules, key=lambda x: x['created_at'])
            with st.expander(f"📅 {slot_key} ({latest['slot_duration']} min slot)", expanded=False):
                st.markdown(f"""
                <div style="background:#111111;padding:15px;border-radius:8px;margin-bottom:15px;">
                    <div style="color:#e50914;font-weight:900;margin-bottom:10px;">Latest Schedule</div>
                    <div style="color:#b3b3b3;">Created: {latest['created_at']}<br>Mood: {latest['mood'] or 'None'}<br>Total runtime: {latest['total_runtime']} min<br>Remaining: {latest['remaining_time']} min</div>
                </div>
                """, unsafe_allow_html=True)
                import json
                try:
                    for movie in json.loads(latest['movies']):
                        st.markdown(f"""
                        <div class="movie-card" style="margin-left:10px;margin-bottom:10px;">
                            <div class="movie-title">{movie['title']}</div>
                            <div class="movie-meta">{movie.get('vote_average',0)}/10 • {movie['runtime']} min</div>
                            <div class="movie-detail"><strong>Genres:</strong> {movie.get('genres','N/A')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                except:
                    st.error("Error loading movie data.")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("View Details", key=f"view_{latest['id']}"):
                        st.session_state.view_schedule_id = latest['id']; st.rerun()
                with c2:
                    if st.button("Delete", key=f"delete_{latest['id']}", type="secondary"):
                        self.db.delete_schedule(latest['id']); st.success("Deleted!"); st.rerun()

        if st.session_state.get("view_schedule_id"):
            details = self.db.get_schedule_by_id(st.session_state.view_schedule_id)
            if details:
                st.markdown("---")
                st.markdown("## Schedule Details")
                st.markdown(f"""
                <div class="slot-card" style="border-left:5px solid #e50914;margin-bottom:20px;">
                    <div style="font-size:24px;font-weight:900;color:white;margin-bottom:10px;">{details['slot_date']} • {details['slot_start']} → {details['slot_end']}</div>
                    <div style="color:#b3b3b3;margin-bottom:15px;">Duration: {details['slot_duration']} min • Used: {details['total_runtime']} min • Remaining: {details['remaining_time']} min</div>
                    <div style="color:#e50914;font-weight:800;">Mood: {details['mood'] or 'None'}</div>
                </div>
                """, unsafe_allow_html=True)
                for movie in details['movies']:
                    st.markdown(f"""
                    <div class="movie-card">
                        <div class="movie-title">{movie['title']}</div>
                        <div class="movie-meta">{movie.get('vote_average',0)}/10 • {movie['runtime']} min</div>
                        <div class="movie-detail"><strong>Genres:</strong> {movie.get('genres','N/A')}</div>
                        <div class="movie-detail" style="margin-top:8px;">{movie.get('overview','')[:200]}...</div>
                    </div>
                    """, unsafe_allow_html=True)
                if st.button("← Back to Saved Schedules"):
                    del st.session_state.view_schedule_id; st.rerun()

    # ── About page ────────────────────────────────────────────────────────────

    def _page_about(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">ABOUT CINESLOT</div>
            <div class="hero-subtitle">CineSlot is an AI-powered movie scheduling system using normalized movie data and CSP scheduling.</div>
        </div>
        """, unsafe_allow_html=True)

        for title, body in [
            ("Team", "Jayesha Yamin, Fuzail Raza, Seniya Naeem"),
            ("AI Goal", "MRV will select the most constrained time slot first. LCV will choose the movie that leaves the most flexibility for remaining slots."),
            ("Favorites & Recommendations", "Sign in with any username to favorite movies. CineSlot scores candidates by genre affinity (×3), director match (×2), and overall rating (×1) derived from your favorites list — giving you a personalized recommendation feed that improves as you add more favorites."),
            ("YouTube Integration", "Click the 🎬 Trailer button on any movie to watch trailers directly inside CineSlot. Trailers are automatically cached for instant loading!"),
        ]:
            st.markdown(f"""<div class="random-box"><h3>{title}</h3><p style="color:#b3b3b3;">{body}</p></div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────

if __name__ == "__main__":
    db = CineSlotDB()
    ui = CineSlotUI(db)
    ui.run()