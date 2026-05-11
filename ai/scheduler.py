import pandas as pd
from typing import List, Dict, Optional
from ortools.sat.python import cp_model
import re

TOKEN_PATTERN = re.compile(r'\b\w+\b')


class MovieSchedulerCSP:
    def __init__(self, movies_df: pd.DataFrame, movie_genres_map: Dict[int, str]):
        self.movies_df = movies_df
        self.movie_genres_map = movie_genres_map
        self.movie_lookup = (
            movies_df
            .set_index('movie_id')
            .to_dict('index')
        )

    def _get_valid_movies(self, duration: int, mood: Optional[str] = None,
                          unwatched_ids: Optional[List[int]] = None,
                          exclude_ids: Optional[List[int]] = None) -> List[int]:
        movies = self.movies_df.copy()
        if movies.empty:
            return []

        movies['runtime'] = pd.to_numeric(movies['runtime'], errors='coerce').fillna(0)
        valid = movies[movies['runtime'] <= duration].copy()

        filtered = valid
        if mood:
            filtered = self._filter_by_mood(valid, mood)

        if unwatched_ids is not None:
            filtered = filtered[filtered['movie_id'].isin(unwatched_ids)]

        if exclude_ids is not None:
            filtered = filtered[~filtered['movie_id'].isin(exclude_ids)]

        return filtered['movie_id'].tolist()

    def _filter_by_mood(self, movies: pd.DataFrame, mood: str) -> pd.DataFrame:

        MOOD_PROFILES = {
            "Comedy": {
                "genres": {
                    "Comedy": 5,
                    "Animation": 4,
                    "Family": 4,
                    "Music": 3,
                    "Fantasy": 2
                },
                "keywords": {
                    "happy": 3,
                    "joy": 3,
                    "laugh": 3,
                    "fun": 2,
                    "heartwarming": 3,
                    "uplift": 2,
                    "feel good": 2,
                    "warm": 1,
                    "cheer": 2
                },
                "negative": {
                    "Horror": -5,
                    "War": -4,
                    "Crime": -3,
                    "Thriller": -3
                }
            },

            "Action": {
                "genres": {
                    "Action": 5,
                    "Adventure": 4,
                    "Thriller": 3,
                    "Science Fiction": 3,
                    "Crime": 2,
                    "Mystery": 2
                },
                "keywords": {
                    "battle": 4,
                    "explosion": 4,
                    "chase": 3,
                    "mission": 3,
                    "hero": 2,
                    "war": 3,
                    "fight": 2,
                    "race": 2,
                    "thrill": 3,
                    "adventure": 2
                },
                "negative": {
                    "Romance": -3,
                    "Documentary": -4,
                    "Family": -2
                }
            },

            "Romantic": {
                "genres": {
                    "Romance": 5,
                    "Comedy": 3,
                    "Drama": 2
                },
                "keywords": {
                    "love": 4,
                    "romance": 4,
                    "romantic": 4,
                    "kiss": 3,
                    "relationship": 3,
                    "couple": 3,
                    "heart": 2,
                    "date": 2,
                    "wedding": 3,
                    "passion": 3
                },
                "negative": {
                    "Horror": -5,
                    "War": -4,
                    "Action": -2
                }
            },

            "Scary": {
                "genres": {
                    "Horror": 5,
                    "Thriller": 4,
                    "Mystery": 3,
                    "Crime": 2
                },
                "keywords": {
                    "fear": 4,
                    "terror": 4,
                    "ghost": 4,
                    "nightmare": 4,
                    "horror": 3,
                    "scary": 3,
                    "dark": 2,
                    "evil": 3,
                    "death": 2,
                    "haunted": 4
                },
                "negative": {
                    "Comedy": -4,
                    "Family": -5,
                    "Animation": -4,
                    "Romance": -3
                }
            },

            "Relaxed": {
                "genres": {
                    "Documentary": 5,
                    "Animation": 3,
                    "Family": 3,
                    "Music": 4,
                    "History": 3,
                    "Comedy": 2
                },
                "keywords": {
                    "calm": 4,
                    "peaceful": 4,
                    "gentle": 3,
                    "quiet": 3,
                    "journey": 2,
                    "nature": 3,
                    "relax": 4,
                    "soothing": 4,
                    "easy": 2,
                    "soft": 2
                },
                "negative": {
                    "Horror": -5,
                    "Thriller": -4,
                    "Action": -3,
                    "Crime": -3
                }
            },

            "Thoughtful": {
                "genres": {
                    "Drama": 5,
                    "Documentary": 4,
                    "History": 4,
                    "Science Fiction": 3,
                    "War": 3,
                    "Foreign": 3
                },
                "keywords": {
                    "philosophy": 4,
                    "meaning": 3,
                    "identity": 3,
                    "truth": 3,
                    "moral": 3,
                    "society": 3,
                    "human": 2,
                    "war": 2,
                    "history": 3,
                    "discovery": 2,
                    "question": 2
                },
                "negative": {
                    "Comedy": -3,
                    "Animation": -3,
                    "Family": -2
                }
            }
        }

        THRESHOLD = 5

        profile = MOOD_PROFILES.get(mood)

        if not profile:
            return movies

        genre_weights = profile["genres"]
        keyword_weights = profile["keywords"]
        negative_weights = profile.get("negative", {})

        mood_scores = []

        for _, row in movies.iterrows():

            score = 0

            # -------------------------
            # GENRES
            # -------------------------
            genres_raw = self.movie_genres_map.get(row['movie_id'], '')

            genres = [
                g.strip()
                for g in genres_raw.split(',')
                if g.strip()
            ]

            for genre in genres:
                score += genre_weights.get(genre, 0)
                score += negative_weights.get(genre, 0)

            # -------------------------
            # TEXT PROCESSING
            # -------------------------
            text = (
                    str(row.get('title', '')) + ' ' +
                    str(row.get('overview', ''))
            ).lower()

            words = TOKEN_PATTERN.findall(text)

            word_set = set(words)

            # -------------------------
            # KEYWORD SCORING
            # -------------------------
            for keyword, weight in keyword_weights.items():

                # Multi-word phrase
                if ' ' in keyword:
                    if keyword in text:
                        score += weight

                # Single token
                else:
                    if keyword in word_set:
                        score += weight

            # -------------------------
            # NORMALIZATION
            # -------------------------
            word_count = max(len(words), 1)

            score = max(score, 0)
            normalized_score = score / (1 + word_count * 0.015)

            mood_scores.append(round(normalized_score, 2))

        # -------------------------
        # SAVE SCORES
        # -------------------------
        filtered_movies = movies.copy()

        filtered_movies['mood_score'] = mood_scores

        # -------------------------
        # FILTER + SORT
        # -------------------------
        filtered_movies = filtered_movies[
            filtered_movies['mood_score'] >= THRESHOLD
            ]

        filtered_movies = filtered_movies.sort_values(
            by='mood_score',
            ascending=False
        )

        return filtered_movies

    def schedule(self, slots: List[Dict], mood: Optional[str] = None,
                 unwatched_ids: Optional[List[int]] = None,
                 exclude_ids: Optional[List[int]] = None,
                 avoid_duplicates: bool = True) -> Dict[int, Dict]:

        if not slots:
            return {}

        def count_valid(slot):
            return len(self._get_valid_movies(slot['duration'], mood, unwatched_ids, exclude_ids))

        indexed_slots = sorted(enumerate(slots), key=lambda x: count_valid(x[1]))

        model = cp_model.CpModel()
        slot_index_vars = []
        slot_movie_vars = []
        slot_runtime_vars = []
        slot_movie_options = []

        for i, slot in indexed_slots:
            valid_movie_ids = self._get_valid_movies(slot['duration'], mood, unwatched_ids, exclude_ids)
            if not valid_movie_ids:
                return {}

            def slots_count(movie_id):
                rt = int(self.movies_df[self.movies_df['movie_id'] == movie_id].iloc[0].get('runtime', 0))
                return sum(1 for _, s in indexed_slots if s['duration'] >= rt)

            valid_movie_ids = sorted(valid_movie_ids, key=slots_count)

            runtime_values = []
            for movie_id in valid_movie_ids:
                movie_info = self.movie_lookup[movie_id]
                runtime_values.append(int(movie_info.get('runtime', 0)))

            index_var = model.NewIntVar(0, len(valid_movie_ids) - 1, f'slot_idx_{i}')
            movie_var = model.NewIntVarFromDomain(cp_model.Domain.FromValues(valid_movie_ids), f'slot_movie_{i}')
            runtime_var = model.NewIntVar(0, slot['duration'], f'slot_runtime_{i}')

            model.AddElement(index_var, valid_movie_ids, movie_var)
            model.AddElement(index_var, runtime_values, runtime_var)
            model.Add(runtime_var <= slot['duration'])

            slot_index_vars.append(index_var)
            slot_movie_vars.append(movie_var)
            slot_runtime_vars.append(runtime_var)
            slot_movie_options.append(valid_movie_ids)

        if avoid_duplicates and len(slot_movie_vars) > 1:
            model.AddAllDifferent(slot_movie_vars)

        model.Maximize(sum(slot_runtime_vars))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 15
        solver.parameters.num_search_workers = 8
        solver.parameters.log_search_progress = False

        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {}

        result = {}
        used_movie_ids = list(exclude_ids) if exclude_ids is not None else []

        for pos, (i, slot) in enumerate(indexed_slots):
            movie_id = solver.Value(slot_movie_vars[pos])
            movie_info = self.movies_df[self.movies_df['movie_id'] == movie_id].iloc[0]
            movie_runtime = int(movie_info.get('runtime', 0))

            movies_for_slot = [{
                'movie_id': int(movie_id),
                'title': movie_info.get('title', 'Unknown'),
                'runtime': movie_runtime,
                'vote_average': float(movie_info.get('vote_average', 0)),
                'genres': self.movie_genres_map.get(movie_id, ''),
                'overview': movie_info.get('overview', '')
            }]

            used_movie_ids.append(movie_id)
            remaining_time = slot['duration'] - movie_runtime

            while remaining_time >= 30:
                additional_candidates = self._get_additional_movies(
                    remaining_time, mood, unwatched_ids, used_movie_ids
                )
                if not additional_candidates:
                    break

                best_movie_id = None
                best_runtime = 0
                best_score = -1
                for add_movie_id in additional_candidates:
                    add_movie_info = self.movies_df[self.movies_df['movie_id'] == add_movie_id].iloc[0]
                    add_runtime = int(add_movie_info.get('runtime', 0))
                    if add_runtime > remaining_time:
                        continue
                    score = add_runtime * 100 + int(add_movie_info.get('vote_average', 0) * 10)
                    if score > best_score:
                        best_score = score
                        best_movie_id = add_movie_id
                        best_runtime = add_runtime

                if not best_movie_id or best_runtime <= 0:
                    break

                movie_info = self.movies_df[self.movies_df['movie_id'] == best_movie_id].iloc[0]
                movies_for_slot.append({
                    'movie_id': int(best_movie_id),
                    'title': movie_info.get('title', 'Unknown'),
                    'runtime': best_runtime,
                    'vote_average': float(movie_info.get('vote_average', 0)),
                    'genres': self.movie_genres_map.get(best_movie_id, ''),
                    'overview': movie_info.get('overview', '')
                })
                used_movie_ids.append(best_movie_id)
                remaining_time -= best_runtime

            result[i] = {
                'slot': slot,
                'movies': movies_for_slot,
                'total_runtime': sum(m['runtime'] for m in movies_for_slot),
                'remaining_time': slot['duration'] - sum(m['runtime'] for m in movies_for_slot)
            }

        return result

    def _get_additional_movies(self, max_duration: int, mood: Optional[str] = None,
                               unwatched_ids: Optional[List[int]] = None,
                               exclude_ids: Optional[List[int]] = None) -> List[int]:
        movies = self.movies_df.copy()
        if movies.empty:
            return []

        movies['runtime'] = pd.to_numeric(movies['runtime'], errors='coerce').fillna(0)
        valid = movies[movies['runtime'] <= max_duration].copy()

        if mood:
            valid = self._filter_by_mood(valid, mood)

        if unwatched_ids is not None:
            valid = valid[valid['movie_id'].isin(unwatched_ids)]

        if exclude_ids:
            valid = valid[~valid['movie_id'].isin(exclude_ids)]

        valid = valid.sort_values(['vote_average', 'runtime'], ascending=[False, False])
        return valid['movie_id'].tolist()[:30]


def schedule_movies(movies_df: pd.DataFrame, movie_genres_map: Dict[int, str],
                    slots: List[Dict], mode: str, mood: Optional[str] = None,
                    unwatched_ids: Optional[List[int]] = None,
                    excluded_movie_ids: Optional[List[int]] = None) -> Dict:
    scheduler = MovieSchedulerCSP(movies_df, movie_genres_map)

    if mode == "Mood Based":
        return scheduler.schedule(slots, mood=mood, exclude_ids=excluded_movie_ids, avoid_duplicates=True)

    return scheduler.schedule(slots, unwatched_ids=unwatched_ids, exclude_ids=excluded_movie_ids, avoid_duplicates=True)
