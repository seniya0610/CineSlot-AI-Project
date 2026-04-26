import os
import pandas as pd
import streamlit as st
from datetime import datetime, date

MOVIES_NORMALIZED = "data/normalized/movies.csv"
GENRES_NORMALIZED = "data/normalized/genres.csv"
MOVIE_GENRES_NORMALIZED = "data/normalized/movie_genres.csv"

REQUIRED_FILES = [MOVIES_NORMALIZED, GENRES_NORMALIZED, MOVIE_GENRES_NORMALIZED]


class CineSlotDB:
    def __init__(self):
        self.movies = None
        self.genres = None
        self.movie_genres = None
        self._load_data()

    def _load_data(self):
        if not all(os.path.exists(path) for path in REQUIRED_FILES):
            return

        self.movies = pd.read_csv(MOVIES_NORMALIZED)
        self.genres = pd.read_csv(GENRES_NORMALIZED)
        self.movie_genres = pd.read_csv(MOVIE_GENRES_NORMALIZED)

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
            background-color: #000000;
            color: white;
            font-family: 'Lato', sans-serif;
        }

        header[data-testid="stHeader"] {
            background-color: #000000;
        }

        [data-testid="stSidebar"] {
            background-color: #050505;
            border-right: 1px solid #242424;
            padding-left: 0;
            padding-right: 0;
        }

        [data-testid="stSidebar"] .stRadio {
            width: 100%;
        }

        [data-testid="stSidebar"] .stRadio > div {
            gap: 10px;
        }

        [data-testid="stSidebar"] .stRadio label {
            width: 100% !important;
            min-height: 52px;
            background: linear-gradient(145deg, #111111, #070707);
            color: white !important;
            border: 1px solid #242424;
            border-radius: 14px;
            padding: 14px 18px !important;
            margin-bottom: 10px;
            font-weight: 900;
            letter-spacing: 1px;
            cursor: pointer;
            transition: all 0.25s ease-in-out;
        }

        [data-testid="stSidebar"] .stRadio label:hover {
            background: linear-gradient(145deg, #e50914, #7a0007);
            border-color: #e50914;
            transform: translateX(6px);
            box-shadow: 0 8px 24px rgba(229, 9, 20, 0.25);
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
        }

        .stButton > button:hover {
            background-color: #e50914 !important;
            border-color: #e50914 !important;
            color: white !important;
        }

        .stButton > button:active {
            background-color: #b00610 !important;
            border-color: #b00610 !important;
        }

        input {
            background-color: #141414 !important;
            color: white !important;
            border: 1px solid #333333 !important;
            border-radius: 10px !important;
        }

        div[data-baseweb="select"] > div {
            background-color: #141414 !important;
            color: white !important;
            border-color: #333333 !important;
            border-radius: 10px !important;
        }

        .hero {
            background: linear-gradient(135deg, rgba(229,9,20,0.32), rgba(0,0,0,0.95)), linear-gradient(145deg, #151515, #030303);
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
            background: linear-gradient(145deg, #121212, #080808);
            border: 1px solid #2a2a2a;
            border-radius: 20px;
            padding: 24px;
            margin-bottom: 18px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
        }

        .section-card:hover {
            border-color: #e50914;
        }

        .movie-card {
            background: #111111;
            border: 1px solid #252525;
            border-left: 5px solid #e50914;
            border-radius: 18px;
            padding: 22px;
            margin-bottom: 16px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.35);
        }

        .movie-card:hover {
            background: #171717;
            border-color: #e50914;
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
                ["Home", "Browse", "Schedule", "About"],
                label_visibility="hidden"
            )

            st.markdown("<hr style='border-color:#2a2a2a; margin: 18px 0;'>", unsafe_allow_html=True)

            st.markdown("""
            <div style="
                background:#111111;
                border:1px solid #242424;
                border-radius:14px;
                padding:14px;
                color:#777777;
                font-size:12px;
                line-height:1.5;
            ">
                <b style="color:#e50914;">CineSlot v1</b><br>
                Smart movie planning with time-aware scheduling.
            </div>
            """, unsafe_allow_html=True)

        return page

    def run(self):
        page = self._render_sidebar()

        if any(not os.path.exists(path) for path in REQUIRED_FILES):
            st.error("Please run: python scripts/normalize_data.py to prepare the normalized dataset first.")
            return

        if page == "Home":
            self._page_home()
        elif page == "Browse":
            self._page_browse()
        elif page == "Schedule":
            self._page_schedule()
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

    def _page_schedule(self):
        st.markdown("""
        <div class="hero">
            <div class="hero-title">SCHEDULE</div>
            <div class="hero-subtitle">
                Add your available watch windows. These slots will later become CSP variables.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if "slots" not in st.session_state:
            st.session_state.slots = []

        if "schedule_mode" not in st.session_state:
            st.session_state.schedule_mode = None

        if "selected_mood" not in st.session_state:
            st.session_state.selected_mood = None

        st.markdown("""
        <div class="section-card">
            <h2>Add Your Watch Window</h2>
            <p style="color:#b3b3b3;">
                Select a date, start time, and end time. You can add multiple slots.
            </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1.4, 1, 1])

        with col1:
            selected_date = st.date_input("Select Date", min_value=date.today())

        with col2:
            start_time = st.time_input("Start Time")

        with col3:
            end_time = st.time_input("End Time")

        if st.button("Add Time Slot"):
            start_dt = datetime.combine(selected_date, start_time)
            end_dt = datetime.combine(selected_date, end_time)

            if end_dt <= start_dt:
                st.error("End time must be after start time.")
            else:
                duration = int((end_dt - start_dt).total_seconds() / 60)

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

        if st.button("Clear Slots"):
            st.session_state.slots = []
            st.session_state.schedule_mode = None
            st.session_state.selected_mood = None
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
                <div style="color:#e50914; margin-top:14px; font-weight:800;">
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
                <div style="color:#e50914; margin-top:14px; font-weight:800;">
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

            if st.button("Generate Schedule"):
                st.markdown("""
                <div class="section-card">
                    <h2>Schedule Input Ready</h2>
                    <p style="color:#b3b3b3;">
                        These values will be passed to the MRV and LCV scheduler next.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                st.write("Slots:", st.session_state.slots)
                st.write("Mode:", st.session_state.schedule_mode)

                if st.session_state.schedule_mode == "Mood Based":
                    st.write("Mood:", st.session_state.selected_mood)

                st.warning("MRV and LCV scheduling will be connected next.")

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
        <div class="section-card">
            <h2>Team</h2>
            <p style="color:#b3b3b3;">Jayesha Yamin, Fuzail Raza, Seniya Naeem</p>
            <h2>AI Goal</h2>
            <p style="color:#b3b3b3;">
                MRV will select the most constrained time slot first. LCV will choose the movie that leaves the most flexibility for remaining slots.
            </p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    db = CineSlotDB()
    ui = CineSlotUI(db)
    ui.run()