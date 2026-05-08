import os
import pandas as pd
import streamlit as st
import sqlite3
from datetime import datetime, date
from ai.scheduler import schedule_movies


DB_PATH = "data/movies.db"


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

    def init_saved_schedules_table(self):
        """Initialize the saved_schedules table if it doesn't exist"""
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

    def save_schedule(self, slot_info, movies_list, mood=None):
        """Save a schedule for a slot"""
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
            slot_info.get('slot_id'),
            slot_info.get('date'),
            slot_info.get('start'),
            slot_info.get('end'),
            slot_info.get('duration'),
            movies_json,
            total_runtime,
            remaining_time,
            mood
        ))

        conn.commit()
        conn.close()

    def get_saved_schedules(self):
        """Get all saved schedules"""
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT * FROM saved_schedules ORDER BY created_at DESC", conn)
        conn.close()
        return df

    def get_schedule_by_id(self, schedule_id):
        """Get a specific saved schedule"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM saved_schedules WHERE id = ?", (schedule_id,))
        row = cursor.fetchone()

        conn.close()

        if row:
            import json
            return {
                'id': row[0],
                'slot_id': row[1],
                'slot_date': row[2],
                'slot_start': row[3],
                'slot_end': row[4],
                'slot_duration': row[5],
                'movies': json.loads(row[6]),
                'total_runtime': row[7],
                'remaining_time': row[8],
                'mood': row[9],
                'created_at': row[10]
            }
        return None

    def delete_schedule(self, schedule_id):
        """Delete a saved schedule"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM saved_schedules WHERE id = ?", (schedule_id,))

        conn.commit()
        conn.close()



class CineSlotUI:
    def __init__(self, db):
        self.db = db
        st.set_page_config(
            page_title="CineSlot",
            page_icon="🎬",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        self._apply_theme()

    def _apply_theme(self):
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap');

        .stApp {
            background-color: black;
            color: white;
            font-family: 'Lato', sans-serif;
        }

        header[data-testid="stHeader"] {
            background-color: black;
        }

        [data-testid="stSidebar"] {
            background-color: #050505;
            border-right: 1px solid #242424;
            padding-left: 0;
            padding-right: 0;
        }
        
        [data-testid="stSidebar"] .stRadio {
            width: 230%;
        }

        [data-testid="stSidebar"] .stRadio > div {
            gap: 10px;
        }

        [data-testid="stSidebar"] .stRadio label {
            width: 100% !important;
            min-height: 60px;
            background: linear-gradient(130deg, #111111, #070707); 
            color: white !important;
            border: 1px solid #242424;
            border-radius: 14px;
            padding: 14px 18px !important;
            margin-bottom: 10px;
            font-size: 17px;
            font-weight: 900;
            cursor: pointer;
            transition: all 0.25s ease-in-out;
        }

        /* DO NOT REMOVE */
        [data-testid="stSidebar"] .stRadio {
            margin-top: -38px;
        }
        
        [data-testid="stSidebar"] .stRadio label:hover {
            background: linear-gradient(130deg, #E5091452, #070707);
            border-color: #db0b15;
            transform: translateX(6px);
            box-shadow: 0 5px 8px rgba(229, 9, 20, 0.25);
        }

        [data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child {
            display: none;
        }

        h1, h2, h3 {
            color: white;
            font-weight: 900;
        }

        .stButton > button {
            background-color: #141414 !important;
            color: white !important;
            border: 1px solid #333333 !important;
            border-radius: 12px !important;
            padding: 10px 18px !important;
            font-weight: 800 !important;
            transition: all 0.25s ease-in-out !important;
        }

        .stButton > button:hover {  
            background: linear-gradient(135deg, #E5091452, black);
            border-color: #e50914 !important;
            color: white !important;
        }

        input {
            background-color: #141414 !important;
            color: white !important;
            border: 1px solid #333333 !important;
            border-radius: 10px !important;
            padding-right: 2px;
        }

        div[data-baseweb="select"] > div {
            background-color: #141414 !important;
            color: white !important;
            border-color: #333333 !important;
            border-radius: 10px !important;
        }

        .hero {
            background: linear-gradient(135deg, #E5091452, #000000F2);
            padding: 42px;
            border-radius: 26px;
            border: 1px solid #2a2a2a;
            margin-bottom: 28px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.45);
        }

        .hero-title {
            font-family: 'Bebas Neue', sans-serif;
            font-size: 78px;
            line-height: 0.9;
            letter-spacing: 3px;
            color: white;
        }

        .hero-subtitle {
            color: #d0d0d0;
            font-size: 18px;
            max-width: 760px;
            margin-top: 16px;
        }

        .section-card {
            background: linear-gradient(145deg, #151515, #080808);
            border: 1px solid #2a2a2a;
            border-radius: 20px;
            padding: 24px;
            margin-bottom: 18px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            transition: all 0.25s ease-in-out;
        }

        .section-card:hover {
            border: 1px solid #db0b15;
            border-left: 5px solid #e50914;
            border-top: 1px solid #2a2a2a;
            border-right: 1px solid #2a2a2a;
            border-bottom: 1px solid #2a2a2a;
            transform: translateX(5px);
            background: linear-gradient(135deg, #E5091452, #000000F2);
            
        }

        .movie-card {
            background: #111111;
            border: 1px solid #252525;
            border-left: 5px solid #e50914;
            border-radius: 18px;
            padding: 22px;
            margin-bottom: 16px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.35);
            transition: all 0.25s ease-in-out;
        }

        .movie-card:hover {
            background: linear-gradient(135deg, #171717, #080808);
            border-color: #e50914;
            transform: translateX(10px);
        }

        .movie-title {
            font-size: 26px;
            font-weight: 900;
            color: white;
            margin-bottom: 8px;
        }

        .movie-meta {
            color: #e50914;
            font-weight: 800;
            margin-bottom: 10px;
        }

        .movie-detail {
            color: #cfcfcf;
            margin-top: 6px;
            line-height: 1.5;
        }

        .slot-card {
            background: linear-gradient(145deg, #141414, #080808);
            padding: 18px 20px;
            border-radius: 16px;
            border-left: 5px solid #e50914;
            border-top: 1px solid #2a2a2a;
            border-right: 1px solid #2a2a2a;
            border-bottom: 1px solid #2a2a2a;
            margin-bottom: 12px;
            box-shadow: 0 8px 22px rgba(0,0,0,0.4);
        }

        .mode-card {
            background: linear-gradient(145deg, #141414, #090909);
            padding: 22px;
            border-radius: 18px;
            border: 1px solid #2a2a2a;
            min-height: 150px;
            margin-bottom: 12px;
            min-width: 300;
            max-width: 300;
            min-height: 200px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.35);
            transition: all 0.25s ease-in-out;
            display: flex;
            flex-direction: column;
        }

        .mode-card:hover {
            border-color: #e50914;
        }

        .red-pill {
            background-color: #250000;
            color: #ff4b4b;
            padding: 8px 14px;
            border-radius: 20px;
            font-weight: 800;
            border: 1px solid #5a0000;
            display: inline-block;
        }

        .empty-box {
            background-color: #111111;
            padding: 18px;
            border-radius: 14px;
            border: 1px dashed #3a3a3a;
            color: #999999;
            margin-top: 18px;
        }
        
        .random-box {
                background: #0c0c0c;
                border: 1px solid #2a2a2a;
                border-radius: 20px;
                padding: 24px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.35);
                margin-bottom: 20px;
        }
        
        </style>
        """, unsafe_allow_html=True)

    def _render_sidebar(self):
        with st.sidebar:
            st.markdown("""
            <div style="padding: 28px 6px 14px 6px;">
                <div style="
                    font-size: 68px;
                    font-weight: 400;
                    color: white;
                    font-family: 'Bebas Neue', sans-serif;
                    line-height: 0.86;
                    letter-spacing: 4px;
                ">
                    CINE<br>SLOT
                </div>
                <div style="
                    font-size: 12px;
                    color: #e50914;
                    letter-spacing: 3px;
                    margin-top: 12px;
                    font-weight: 900;
                ">
                    AI MOVIE SCHEDULER
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<hr style='border-color:#2a2a2a; margin: 18px 0;'>", unsafe_allow_html=True)

            page = st.radio(
                "navigate",
                ["Home", "Browse", "Unwatched", "Schedule", "Saved Schedules", "About"],
                label_visibility="hidden"
            )

            st.markdown("<hr style='border-color:#2a2a2a; margin: 18px 0;'>", unsafe_allow_html=True)
            st.caption("CineSlot v1 <br> Smart movie planning with time-aware scheduling.", unsafe_allow_html=True)

        return page

    def run(self):
        page = self._render_sidebar()

        if not os.path.exists(DB_PATH) or self.db.movies is None:
            st.error("Database not found. Please ensure data/movies.db exists.")
            return

        if page == "Home":
            self._page_home()
        elif page == "Browse":
            self._page_browse()
        elif page == "Unwatched":
            self._page_unwatched()
        elif page == "Schedule":
            self._page_schedule()
        elif page == "Saved Schedules":
            self._page_saved_schedules()
        elif page == "About":
            self._page_about()

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

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            <div class="section-card">
                <h3>Browse</h3>
                <p style="color:#b3b3b3;">Explore clean movie cards from normalized TMDB data.</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown("""
            <div class="section-card">
                <h3>Schedule</h3>
                <p style="color:#b3b3b3;">Add multiple time slots across days and choose a scheduling style.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("## Featured Movies")

        if movies.empty:
            st.warning("No movie data available.")
            return

        featured = movies.sort_values(by="vote_average", ascending=False).head(6)

        for _, movie in featured.iterrows():
            self._render_movie_card(movie)

    def _page_browse(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">BROWSE MOVIES</div>
            <div class="hero-subtitle">
                Search and filter movies from your normalized dataset.
            </div>
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
            (filtered["runtime"] >= runtime_min) &
            (filtered["runtime"] <= runtime_max) &
            (filtered["vote_average"] >= rating_min) &
            (filtered["vote_average"] <= rating_max)
        ]

        st.markdown(f"### Showing {len(filtered)} movies")

        if filtered.empty:
            st.info("No movies match the selected filters.")
            return

        for _, movie in filtered.head(40).iterrows():
            self._render_movie_card(movie)

    def _render_movie_card(self, movie):
        release_year = str(movie["release_date"])[:4] if pd.notna(movie["release_date"]) else "N/A"
        runtime = int(movie["runtime"]) if pd.notna(movie["runtime"]) else 0
        rating = float(movie["vote_average"]) if pd.notna(movie["vote_average"]) else 0.0
        genres = self.db.get_movie_genres(movie["movie_id"])

        st.markdown(f"""
        <div class="movie-card">
            <div class="movie-title">{movie["title"]}</div>
            <div class="movie-meta">{release_year} · {runtime} min · ⭐ {rating:.1f}</div>
            <div class="movie-detail"><b>Genres:</b> {genres or "N/A"}</div>
            <div class="movie-detail"><b>Director:</b> {movie["director"]}</div>
            <div class="movie-detail"><b>Top Cast:</b> {movie["top_cast"]}</div>
            <div class="movie-detail"><b>Overview:</b> {movie["overview"]}</div>
        </div>
        """, unsafe_allow_html=True)

        # Add to unwatched button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("➕ Unwatched", key=f"add_unwatched_{movie['movie_id']}"):
                if "unwatched_ids" not in st.session_state:
                    st.session_state.unwatched_ids = []
                
                if movie["movie_id"] not in st.session_state.unwatched_ids:
                    st.session_state.unwatched_ids.append(movie["movie_id"])
                    st.success(f"Added {movie['title']} to unwatched list!")
                else:
                    st.info(f"{movie['title']} is already in your unwatched list.")

    def _render_movie_card_with_unwatched(self, movie, show_add_button=True):
        release_year = str(movie["release_date"])[:4] if pd.notna(movie["release_date"]) else "N/A"
        runtime = int(movie["runtime"]) if pd.notna(movie["runtime"]) else 0
        rating = float(movie["vote_average"]) if pd.notna(movie["vote_average"]) else 0.0
        genres = self.db.get_movie_genres(movie["movie_id"])

        st.markdown(f"""
        <div class="movie-card">
            <div class="movie-title">{movie["title"]}</div>
            <div class="movie-meta">{release_year} · {runtime} min · ⭐ {rating:.1f}</div>
            <div class="movie-detail"><b>Genres:</b> {genres or "N/A"}</div>
            <div class="movie-detail"><b>Director:</b> {movie["director"]}</div>
            <div class="movie-detail"><b>Top Cast:</b> {movie["top_cast"]}</div>
            <div class="movie-detail"><b>Overview:</b> {movie["overview"]}</div>
        </div>
        """, unsafe_allow_html=True)

        # Remove from unwatched button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("➖ Remove", key=f"remove_unwatched_{movie['movie_id']}"):
                if "unwatched_ids" in st.session_state and movie["movie_id"] in st.session_state.unwatched_ids:
                    st.session_state.unwatched_ids.remove(movie["movie_id"])
                    st.success(f"Removed {movie['title']} from unwatched list!")
                    st.rerun()

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

        unwatched_movies = movies_df[movies_df['movie_id'].isin(unwatched_ids)].copy()

        st.markdown(f"""
        <div class="section-card">
            <h3>{len(unwatched_movies)} Movies in Your Unwatched List</h3>
            <p style="color:#b3b3b3;">These movies will be used when you select "Unwatched List" scheduling mode.</p>
        </div>
        """, unsafe_allow_html=True)

        # Sort by rating for display
        unwatched_movies = unwatched_movies.sort_values('vote_average', ascending=False)

        for _, movie in unwatched_movies.iterrows():
            self._render_movie_card_with_unwatched(movie, show_add_button=False)

    def _page_schedule(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">SCHEDULE</div>
            <div class="hero-subtitle">
                Add your available watch windows. <br> Select a date, start time, and end time. You can add multiple slots.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if "slots" not in st.session_state:
            st.session_state.slots = []

        if "schedule_mode" not in st.session_state:
            st.session_state.schedule_mode = None

        if "selected_mood" not in st.session_state:
            st.session_state.selected_mood = None

        if "unwatched_ids" not in st.session_state:
            # Initialize with random unwatched movies
            random_unwatched = self.db.get_random_unwatched_list(50)
            st.session_state.unwatched_ids = random_unwatched

        if "current_schedule" not in st.session_state:
            st.session_state.current_schedule = None

        if "schedule_generated" not in st.session_state:
            st.session_state.schedule_generated = False

        if "excluded_movie_ids" not in st.session_state:
            st.session_state.excluded_movie_ids = []

        if "last_schedule_context" not in st.session_state:
            st.session_state.last_schedule_context = None

        if "saved_schedules" not in st.session_state:
            st.session_state.saved_schedules = []

        if "regenerate_requested" not in st.session_state:
            st.session_state.regenerate_requested = False


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

                # Check for overlapping slots on the same day
                overlap_found = False
                for existing_slot in st.session_state.slots:
                    if existing_slot["date"] == selected_date.strftime("%A, %d %B"):
                        existing_start = datetime.strptime(existing_slot["start"], "%I:%M %p").time()
                        existing_end = datetime.strptime(existing_slot["end"], "%I:%M %p").time()
                        existing_start_dt = datetime.combine(selected_date, existing_start)
                        existing_end_dt = datetime.combine(selected_date, existing_end)

                        if (start_dt < existing_end_dt and end_dt > existing_start_dt):
                            overlap_found = True
                            break

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


        if len(st.session_state.slots) == 0:
            st.markdown("""
            <div class="empty-box">
                No slots added yet. Add at least one watch window to continue.
            </div>
            """, unsafe_allow_html=True)
            return

        st.markdown("## Your Watch Windows")

        for slot in st.session_state.slots:
            st.markdown(f"""
            <div class="slot-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:22px; font-weight:900; color:white;">
                            {slot["date"]}
                        </div>
                        <div style="color:#b3b3b3; margin-top:5px;">
                            {slot["start"]} → {slot["end"]}
                        </div>
                    </div>
                    <div class="red-pill">
                        {slot["duration"]} min
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("## Select Slots for Scheduling")

        if len(st.session_state.slots) > 0:
            st.markdown("""
            <div style="background-color: #111111; padding: 20px; border-radius: 12px; border: 1px solid #333333; margin-bottom: 20px;">
                <p style="color: #e50914; font-weight: 900; margin-bottom: 15px;">Choose which time slots to schedule movies for:</p>
            </div>
            """, unsafe_allow_html=True)

            # Create checkboxes for each slot
            selected_slots_indices = []
            cols = st.columns(min(2, len(st.session_state.slots)))

            for idx, slot in enumerate(st.session_state.slots):
                col_idx = idx % len(cols)
                with cols[col_idx]:
                    slot_label = f"{slot['slot_id']}: {slot['date']} {slot['start']} → {slot['end']} ({slot['duration']} min)"
                    if st.checkbox(slot_label, key=f"slot_{idx}", value=(idx == 0)):
                        selected_slots_indices.append(idx)

            selected_slots = [st.session_state.slots[i] for i in selected_slots_indices]

            if selected_slots:
                selected_labels = [f"{st.session_state.slots[i]['slot_id']}: {st.session_state.slots[i]['date']} {st.session_state.slots[i]['start']} → {st.session_state.slots[i]['end']}" for i in selected_slots_indices]
                st.markdown(f"""
                <div style="background-color: #0a0a0a; padding: 15px; border-radius: 8px; border-left: 4px solid #e50914; margin-top: 10px;">
                    <strong style="color: #e50914;">Selected {len(selected_slots)} slot(s):</strong><br>
                    {" • ".join(selected_labels)}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("Please select at least one slot to continue.")
        else:
            selected_slots = []

        if st.button("Clear Slots"):
            st.session_state.slots = []
            st.session_state.schedule_mode = None
            st.session_state.selected_mood = None
            if "unwatched_ids" in st.session_state:
                del st.session_state["unwatched_ids"]
            st.session_state.current_schedule = None
            st.session_state.schedule_generated = False
            st.session_state.excluded_movie_ids = []
            st.session_state.last_schedule_context = None
            st.session_state.regenerate_requested = False
            st.rerun()

        st.markdown("## Choose Scheduling Style")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            <div class="mode-card">
                <div style="font-size:26px; font-weight:900; color:white;">Mood-Based</div>
                <div style="color:#b3b3b3; margin-top:8px;">
                    Choose a mood and CineSlot will later filter movies using related genres.
                </div>
                <div style="color:#e50914; margin-top:14px; font-weight:800; margin-top:auto">
                    Example: Excited → Action, Adventure, Sci-Fi
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Choose Mood-Based"):
                st.session_state.schedule_mode = "Mood Based"

        with col2:
            st.markdown("""
            <div class="mode-card">
                <div style="font-size:26px; font-weight:900; color:white;">Unwatched List</div>
                <div style="color:#b3b3b3; margin-top:8px;">
                    CineSlot will later choose from movies the user has not watched yet.
                </div>
                <div style="color:#e50914; margin-top:14px; font-weight:800; margin-top:auto;">
                    Best for personal scheduling
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Choose Unwatched List"):
                st.session_state.schedule_mode = "Unwatched List"

        if st.session_state.schedule_mode is not None:
            st.markdown(f"""
            <div style="
                background-color:#111111;
                padding:16px 20px;
                border-radius:14px;
                border:1px solid #e50914;
                margin-top:22px;
                color:white;
            ">
                Selected Mode:
                <span style="color:#e50914; font-weight:900;">
                    {st.session_state.schedule_mode}
                </span>
            </div>
            """, unsafe_allow_html=True)

            if st.session_state.schedule_mode == "Mood Based":
                mood = st.selectbox(
                    "Select Mood",
                    ["Happy", "Excited", "Romantic", "Scared", "Relaxed", "Thoughtful"]
                )
                st.session_state.selected_mood = mood

            if st.session_state.schedule_mode == "Unwatched List":
                unwatched_count = len(st.session_state.get("unwatched_ids", []))
                if unwatched_count > 0:
                    st.success(f"Using {unwatched_count} movies from your unwatched list")
                else:
                    st.warning("Your unwatched list is empty. Add movies to it first!")

            def perform_schedule_generation(regeneration=False):
                genre_map = self.db.build_genre_map()
                movies_df = self.db.read_all_movies()

                if movies_df.empty:
                    st.error("No movies loaded from database")
                    return False

                if not selected_slots:
                    st.error("Select at least one slot to schedule.")
                    return False

                current_context = {
                    "mode": st.session_state.schedule_mode,
                    "mood": st.session_state.selected_mood if st.session_state.schedule_mode == "Mood Based" else None,
                    "slots": [(slot['slot_id'], slot['date'], slot['start'], slot['end'], slot['duration']) for slot in selected_slots]
                }

                if st.session_state.last_schedule_context != current_context:
                    st.session_state.excluded_movie_ids = []
                    st.session_state.last_schedule_context = current_context

                mood = st.session_state.selected_mood if st.session_state.schedule_mode == "Mood Based" else None
                unwatched_ids = st.session_state.get("unwatched_ids", None)
                excluded_ids = st.session_state.get("excluded_movie_ids", [])

                try:
                    schedule = schedule_movies(
                        movies_df,
                        genre_map,
                        selected_slots,
                        st.session_state.schedule_mode,
                        mood=mood,
                        unwatched_ids=unwatched_ids,
                        excluded_movie_ids=excluded_ids
                    )

                    if schedule:
                        st.session_state.current_schedule = schedule
                        st.session_state.schedule_generated = True
                        st.session_state.regenerate_requested = False
                        return True
                    else:
                        if regeneration:
                            st.warning("No new schedule could be generated with the current excluded movies. Reset exclusions or change the mood/slots.")
                        else:
                            st.error("Scheduler found no valid movies for these slots. Try longer time slots or change the mood.")
                        return False
                except Exception as e:
                    st.error(f"Error generating schedule: {str(e)}")
                    return False

            if st.button("Generate Schedule"):
                perform_schedule_generation(regeneration=False)

            if st.session_state.regenerate_requested:
                perform_schedule_generation(regeneration=True)

        # Display generated schedule
        if st.session_state.get("schedule_generated", False) and "current_schedule" in st.session_state:
            schedule = st.session_state.current_schedule
            
            st.markdown("""
            <div class="section-card">
                <h2 style="color: #e50914;">✓ Schedule Generated</h2>
                <p style="color:#b3b3b3;">Your movies are scheduled using CSP with MRV and LCV heuristics.</p>
            </div>
            """, unsafe_allow_html=True)
            
            for slot_idx, slot_info in sorted(schedule.items()):
                slot = slot_info['slot']
                movies = slot_info['movies']
                total_runtime = slot_info['total_runtime']
                remaining = slot_info['remaining_time']
                
                st.markdown(f"""
                <div class="slot-card" style="border-left: 5px solid #e50914; margin-bottom: 20px;">
                    <div style="font-size:24px; font-weight:900; color:white; margin-bottom:10px;">
                        {slot['date']} • {slot['start']} → {slot['end']}
                    </div>
                    <div style="color:#b3b3b3; margin-bottom:15px;">
                        Total: {total_runtime} min used • {remaining} min remaining
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                for movie in movies:
                    st.markdown(f"""
                    <div class="movie-card" style="margin-left: 20px;">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <div>
                                <div class="movie-title">{movie['title']}</div>
                                <div class="movie-meta">{movie['vote_average']}/10 • {movie['runtime']} min</div>
                                <div class="movie-detail"><strong>Genres:</strong> {movie['genres']}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Schedule", key="save_schedule"):
                    # Initialize saved schedules table
                    self.db.init_saved_schedules_table()

                    # Save each slot's schedule
                    saved_count = 0
                    for slot_idx, slot_info in schedule.items():
                        slot = slot_info.get('slot', {})
                        movies = slot_info['movies']
                        if movies and slot:
                            self.db.save_schedule(slot, movies, st.session_state.get("selected_mood"))
                            saved_count += 1

                    if saved_count > 0:
                        st.success(f"Schedule saved! {saved_count} slot(s) saved to Saved Schedules.")
                    else:
                        st.warning("No movies were scheduled to save.")
            with col2:
                if st.button("Regenerate Schedule", key="regenerate"):
                    if st.session_state.get("current_schedule"):
                        current_movie_ids = [movie['movie_id'] for slot_info in st.session_state.current_schedule.values() for movie in slot_info['movies']]
                        st.session_state.excluded_movie_ids = list(set(st.session_state.get("excluded_movie_ids", []) + current_movie_ids))
                    st.session_state.schedule_generated = False
                    st.session_state.current_schedule = None
                    st.session_state.regenerate_requested = True
                    st.rerun()


    def _page_saved_schedules(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">SAVED SCHEDULES</div>
            <div class="hero-subtitle">
                View and manage your previously saved movie schedules.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Initialize the saved schedules table
        self.db.init_saved_schedules_table()

        # Get all saved schedules
        saved_schedules_df = self.db.get_saved_schedules()

        if saved_schedules_df.empty:
            st.markdown("""
            <div class="empty-box">
                No saved schedules yet. Generate and save a schedule from the Schedule page to see it here.
            </div>
            """, unsafe_allow_html=True)
            return

        # Group schedules by slot
        slot_groups = {}
        for _, row in saved_schedules_df.iterrows():
            slot_key = f"{row['slot_id']}: {row['slot_date']} {row['slot_start']} → {row['slot_end']}"
            if slot_key not in slot_groups:
                slot_groups[slot_key] = []
            slot_groups[slot_key].append({
                'id': row['id'],
                'slot_duration': row['slot_duration'],
                'movies': row['movies_json'],  # This will be parsed later
                'total_runtime': row['total_runtime'],
                'remaining_time': row['remaining_time'],
                'mood': row['mood'],
                'created_at': row['created_at']
            })

        # Display saved slots
        st.markdown("## Your Saved Schedules")

        for slot_key, schedules in slot_groups.items():
            # Show the most recent schedule for this slot
            latest_schedule = max(schedules, key=lambda x: x['created_at'])

            with st.expander(f"📅 {slot_key} ({latest_schedule['slot_duration']} min slot)", expanded=False):
                st.markdown(f"""
                <div style="background-color: #111111; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <div style="color: #e50914; font-weight: 900; margin-bottom: 10px;">Latest Schedule</div>
                    <div style="color: #b3b3b3;">
                        Created: {latest_schedule['created_at']}<br>
                        Mood: {latest_schedule['mood'] or 'None'}<br>
                        Total runtime: {latest_schedule['total_runtime']} min<br>
                        Remaining time: {latest_schedule['remaining_time']} min
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Parse movies JSON
                import json
                try:
                    movies = json.loads(latest_schedule['movies'])
                    for movie in movies:
                        st.markdown(f"""
                        <div class="movie-card" style="margin-left: 10px; margin-bottom: 10px;">
                            <div style="display:flex; justify-content:space-between; align-items:start;">
                                <div>
                                    <div class="movie-title">{movie['title']}</div>
                                    <div class="movie-meta">{movie.get('vote_average', 0)}/10 • {movie['runtime']} min</div>
                                    <div class="movie-detail"><strong>Genres:</strong> {movie.get('genres', 'N/A')}</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                except:
                    st.error("Error loading movie data for this schedule.")

                # Action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("View Details", key=f"view_{latest_schedule['id']}"):
                        st.session_state.view_schedule_id = latest_schedule['id']
                        st.rerun()

                with col2:
                    if st.button("Load This Schedule", key=f"load_{latest_schedule['id']}"):
                        # This would load the schedule back into the current session
                        st.info("Schedule loading feature coming soon!")

                with col3:
                    if st.button("Delete", key=f"delete_{latest_schedule['id']}", type="secondary"):
                        self.db.delete_schedule(latest_schedule['id'])
                        st.success("Schedule deleted!")
                        st.rerun()

        # Show detailed view if requested
        if 'view_schedule_id' in st.session_state and st.session_state.view_schedule_id:
            schedule_details = self.db.get_schedule_by_id(st.session_state.view_schedule_id)
            if schedule_details:
                st.markdown("---")
                st.markdown("## Schedule Details")

                st.markdown(f"""
                <div class="slot-card" style="border-left: 5px solid #e50914; margin-bottom: 20px;">
                    <div style="font-size:24px; font-weight:900; color:white; margin-bottom:10px;">
                        {schedule_details['slot_date']} • {schedule_details['slot_start']} → {schedule_details['slot_end']}
                    </div>
                    <div style="color:#b3b3b3; margin-bottom:15px;">
                        Duration: {schedule_details['slot_duration']} min • Used: {schedule_details['total_runtime']} min • Remaining: {schedule_details['remaining_time']} min
                    </div>
                    <div style="color:#e50914; font-weight:800;">
                        Mood: {schedule_details['mood'] or 'None'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("### Movies Scheduled:")
                for movie in schedule_details['movies']:
                    st.markdown(f"""
                    <div class="movie-card">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <div>
                                <div class="movie-title">{movie['title']}</div>
                                <div class="movie-meta">{movie.get('vote_average', 0)}/10 • {movie['runtime']} min</div>
                                <div class="movie-detail"><strong>Genres:</strong> {movie.get('genres', 'N/A')}</div>
                                <div class="movie-detail" style="margin-top: 8px;">{movie.get('overview', 'No description available.')[:200]}...</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                if st.button("← Back to Saved Schedules"):
                    del st.session_state.view_schedule_id
                    st.rerun()


    def _page_about(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">ABOUT CINESLOT</div>
            <div class="hero-subtitle">
                CineSlot is an AI-powered movie scheduling system using normalized movie data and CSP scheduling.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
                    <div class="random-box">
                        <h3>Team</h3>
                        <p style="color:#b3b3b3;">
                            Jayesha Yamin, Fuzail Raza, Seniya Naeem
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("""
                    <div class="random-box">
                        <h3>AI Goal</h3>
                        <p style="color:#b3b3b3;">
                        MRV will select the most constrained time slot first. LCV will choose the movie that leaves the most flexibility for remaining slots.
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
#
#
if __name__ == "__main__":
    db = CineSlotDB()
    ui = CineSlotUI(db)
    ui.run()
