import os

import pandas as pd
import streamlit as st

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

    def read_all_movies(self):
        return self.movies.copy() if self.movies is not None else pd.DataFrame()

    def get_movie_genres(self, movie_id):
        if self.movie_genres is None or self.genres is None:
            return ""

        genre_ids = self.movie_genres[self.movie_genres["movie_id"] == movie_id]["genre_id"].tolist()
        genre_names = self.genres[self.genres["genre_id"].isin(genre_ids)]["genre_name"].tolist()
        return ", ".join(genre_names)


class CineSlotUI:
    def __init__(self, db: CineSlotDB):
        self.db = db
        st.set_page_config(page_title="CineSlot", page_icon="🎬", layout="wide")
        self._apply_theme()

    def _apply_theme(self):
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');
            @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&display=swap');
            
            .stApp {
                background-color: black;
                color: white;
                font-family: 'Lato', sans-serif !important;
            }
            
            [data-testid="stSidebar"] {
                background-color: black;
                border-right: 1px solid #2a2a2a;
                min-width: 290px !important;
                max-width: 290px !important;
                transform: none !important;
                visibility: visible !important;
            }
            
            header[data-testid="stHeader"]{
                background-color: #171717;
                height: 20px !important;
                padding: 0 !important
            }
            
            /* Hide default radio buttons */
            [data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child {
                display: none;
            }
            
            /* Radio options */
            [data-testid="stSidebar"] .stRadio label {
                display: flex !important;
                align-items: flex-start;
                background-color: #171717;
                color: #e0e0e0 !important;
                font-size: 40px;
                font-weight: 700;
                padding: 12px 16px;
                border-radius: 10px;
                margin-bottom: 8px;
                cursor: pointer;
                border: 1px solid #2a2a2a;
                transition: background 0.2s;
                width: 200%;
            }
            
            [data-testid="stSidebar"] .stRadio label:hover {
                background-color: #2a2a2a;
                border-color: red;
                color: #ffffff !important;
            }
            
            [data-testid="stSidebar"] .stRadio {
                margin-top: -30px;
            }
            
            h1, h2, h3 {
                letter-spacing: 1px;
            }
            
            [data-testid="stCaptionContainer"] p {
                font-size: 16px;
                color: red;
                font-weight: 600;
            }
            
            .movie-card {
                border: 1px solid #2a2a2a;
                padding: 18px;
                border-radius: 18px;
                background-color: #111111;
                margin-bottom: 20px;
            }
            
            .movie-card h2 {
                margin: 0 0 8px 0;
            }
            
            .movie-meta {
                color: #bdbdbd;
                margin-bottom: 12px;
                font-size: 14px;
            }
            
            .movie-detail {
                margin-bottom: 8px;
                line-height: 1.5;
            }
            </style>
        """, unsafe_allow_html=True)

    def _render_sidebar(self):
        with st.sidebar:
            st.markdown("""
                <div style="padding: 24px 8px 8px 8px;">
                    <div style="font-size: 55px; font-weight: 400; color: #ffffff; font-family: 'Bebas Neue', sans serif; line-height: 1.1; letter-spacing: 2px;">
                        CINE<br>SLOT
                    </div>
                    <div style="font-size: 11px; color: red; letter-spacing: 3px; margin-top: 6px; font-weight: 600;">
                        AI MOVIE SCHEDULER
                    </div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("<hr style='border-color:#2a2a2a; margin: 16px 0;'>", unsafe_allow_html=True)
            page = st.radio("navigate", ["Home", "Browse", "Schedule", "About"], label_visibility="hidden")
            st.markdown("<hr style='border-color:#2a2a2a; margin: 16px 0;'>", unsafe_allow_html=True)
            st.markdown("<div style='color:#555555; font-size:11px; letter-spacing:2px; padding: 0 8px;'>v1 · AI Powered Engine</div>", unsafe_allow_html=True)

        return page

    def run(self):
        page = self._render_sidebar()

        if any(not os.path.exists(path) for path in REQUIRED_FILES):
            st.error("Please run:\npython scripts/normalize_data.py\nto prepare the normalized dataset first.")
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
        st.title("Welcome to CineSlot")
        st.caption("Your personal movie hub.")
        st.write("Browse normalized movie data with clean, beginner-friendly cards.")

        movies = self.db.read_all_movies()
        if movies.empty:
            st.warning("No movie data available. Run the normalization script first.")
            return

        st.markdown("### Featured movies")
        featured = movies.sort_values(by="vote_average", ascending=False).head(4)
        for _, movie in featured.iterrows():
            self._render_movie_card(movie)

    def _page_browse(self):
        st.title("Browse Movies")
        st.caption("Explore the collection.")

        movies = self.db.read_all_movies()
        if movies.empty:
            st.warning("No movie data available. Run the normalization script first.")
            return

        all_genres = ["All"] + sorted(self.db.genres["genre_name"].unique().tolist())
        search = st.text_input("Search by title", "")
        selected_genre = st.selectbox("Filter by genre", all_genres)
        col1, col2 = st.columns(2)
        with col1:
            runtime_min, runtime_max = st.slider("Runtime (minutes)", 0, int(movies["runtime"].max() or 300), (0, int(movies["runtime"].max() or 300)))
        with col2:
            rating_min, rating_max = st.slider("Rating", 0.0, 10.0, (0.0, 10.0))

        filtered = movies.copy()
        if search:
            filtered = filtered[filtered["title"].str.contains(search, case=False, na=False)]

        if selected_genre != "All":
            genre_id = self.db.genres[self.db.genres["genre_name"] == selected_genre]["genre_id"].squeeze()
            movie_ids = self.db.movie_genres[self.db.movie_genres["genre_id"] == genre_id]["movie_id"].tolist()
            filtered = filtered[filtered["movie_id"].isin(movie_ids)]

        filtered = filtered[
            (filtered["runtime"] >= runtime_min) &
            (filtered["runtime"] <= runtime_max) &
            (filtered["vote_average"] >= rating_min) &
            (filtered["vote_average"] <= rating_max)
        ]

        if filtered.empty:
            st.info("No movies match the selected filters.")
            return

        for _, movie in filtered.iterrows():
            self._render_movie_card(movie)

    def _render_movie_card(self, movie):
        release_year = str(movie["release_date"])[:4] if pd.notna(movie["release_date"]) else "N/A"
        runtime = int(movie["runtime"]) if pd.notna(movie["runtime"]) else 0
        rating = float(movie["vote_average"]) if pd.notna(movie["vote_average"]) else 0.0
        genres = self.db.get_movie_genres(movie["movie_id"])

        st.markdown(f"""
            <div class='movie-card'>
                <h2 style='margin-bottom: 6px; color: white;'>{movie['title']}</h2>
                <div class='movie-meta'>Year: {release_year} · Runtime: {runtime} min · Rating: {rating:.1f}</div>
                <div class='movie-detail'><strong>Genres:</strong> {genres or 'N/A'}</div>
                <div class='movie-detail'><strong>Director:</strong> {movie['director'] or 'Unknown'}</div>
                <div class='movie-detail'><strong>Top Cast:</strong> {movie['top_cast'] or 'Unknown'}</div>
                <div class='movie-detail'><strong>Overview:</strong> {movie['overview']}</div>
            </div>
        """, unsafe_allow_html=True)

    def _page_schedule(self):
        st.title("Scheduler")
        st.caption("Coming Soon!")

    def _page_about(self):
        st.title("CineSlot Team")
        st.caption("Contact us for more information.")


if __name__ == "__main__":
    db = CineSlotDB()
    ui = CineSlotUI(db)
    ui.run()