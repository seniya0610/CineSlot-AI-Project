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

class CineSlotUI:
    def __init__(self, db: CineSlotDB):
        self.db = db
        self._apply_theme()

    def _apply_theme(self):
        st.markdown("""
            <style>
            
            @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap');
            
                /* Background */
                .stApp {
                    background-color: black;
                    color: white;
                }

                /* Sidebar background */
                [data-testid="stSidebar"] {
                    background-color: black;
                    border-right: 1px solid #2a2a2a;
                }

                /* Hide default radio buttons entirely */
                [data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child {
                    display: none;
                }

                /* Each radio option label — make it look like a nav card */
                [data-testid="stSidebar"] .stRadio label {
                    display: flex !important;
                    align-items: left;
                    background-color: #171717;
                    color: #e0e0e0 !important;
                    font-size: 30px;
                    font-weight: 600;
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

                /* Headings */
                h1, h2, h3 {
                    letter-spacing: 1px;
                }
                
                [data-testid="stCaptionContainer"] p {
                    font-size: 16px;
                    color: red;
                    font-weight: 600;
                }
                
        """, unsafe_allow_html=True)

    def _sidebar(self):
        """Sidebar with logo and navigation."""
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

            page = st.radio(
                "navigate",
                ["Home", "Browse", "Schedule", "About"],
                label_visibility="hidden"
            )

            st.markdown("<hr style='border-color:#2a2a2a; margin: 16px 0;'>", unsafe_allow_html=True)
            st.markdown(
                "<div style='color:#555555; font-size:11px; letter-spacing:2px; padding: 0 8px;'>TMDB · 4,800+ FILMS</div>",
                unsafe_allow_html=True
            )

        return page

    def _page_home(self):
        st.title("Welcome to CineSlot")
        st.caption("Your personal movie hub.")

    def _page_browse(self):
        st.title("Browse Movies")
        st.caption("Explore the collection.")

    def _page_schedule(self):
        st.title("Scheduler")
        st.caption("Cooming Soon!")

    def _page_about(self):
        st.title("CineSlot Team")
        st.caption("contact us")

    def render(self):
        st.set_page_config(
            page_title="CineSlot",
            page_icon="🎬",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        self._apply_theme()

        page = self._sidebar()

        if "Home" in page:
            self._page_home()
        elif "Browse" in page:
            self._page_browse()
        elif "Schedule" in page:
            self._page_schedule()
        elif "About" in page:
            self._page_about()

db = CineSlotDB()
ui = CineSlotUI(db)
ui.render()
