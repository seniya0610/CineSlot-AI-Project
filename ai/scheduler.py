import pandas as pd
from typing import List, Dict, Optional
from ortools.sat.python import cp_model

class MovieSchedulerCSP:
    def __init__(self, movies_df: pd.DataFrame, movie_genres_map: Dict[int, str]):
        self.movies_df = movies_df
        self.movie_genres_map = movie_genres_map

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
        mood_genres = {
            "Happy": ["Animation", "Comedy", "Family", "Fantasy", "Music"],
            "Excited": ["Action", "Adventure", "Comedy", "Crime", "Drama", "Fantasy", "Music", "Mystery", "Science Fiction", "Thriller"],
            "Romantic": ["Romance", "Comedy"],
            "Scared": ["Crime", "Horror", "Mystery", "Thriller"],
            "Relaxed": ["Animation", "Comedy", "Documentary", "Family", "Fantasy", "History", "Music"],
            "Thoughtful": ["Adventure", "Animation", "Documentary", "Family", "Fantasy", "Foreign", "History", "Drama", "Science Fiction", "War"]
        }

        mood_keywords = {
            "Happy": ["feel good", "feel-good", "happy", "joy", "laugh", "uplift", "fun", "heartwarming", "warm"],
            "Excited": ["thrill", "adventure", "action", "explosion", "fast", "race", "battle", "hero", "mystery"],
            "Romantic": ["love", "romance", "romantic", "date", "heart", "kiss", "relationship", "romcom", "couple"],
            "Scared": ["fear", "scary", "horror", "terror", "nightmare", "ghost", "mystery", "crime"],
            "Relaxed": ["calm", "relax", "easy", "gentle", "soft", "peace", "quiet", "soothing"],
            "Thoughtful": ["mind", "think", "mystery", "crime", "history", "drama", "war", "science"]
        }

        target_genres = {g.strip().lower() for g in mood_genres.get(mood, [])}
        target_keywords = mood_keywords.get(mood, [])
        if not target_genres and not target_keywords:
            return movies

        def matches_mood(row):
            genres = [g.strip().lower() for g in self.movie_genres_map.get(row['movie_id'], '').split(',') if g.strip()]
            overview = str(row.get('overview', '')).lower()
            title = str(row.get('title', '')).lower()

            genre_match = bool(target_genres.intersection(genres))
            keyword_match = any(k in overview or k in title for k in target_keywords)
            return genre_match or keyword_match

        return movies[movies.apply(matches_mood, axis=1)]

    def schedule(self, slots: List[Dict], mood: Optional[str] = None,
                 unwatched_ids: Optional[List[int]] = None,
                 exclude_ids: Optional[List[int]] = None,
                 avoid_duplicates: bool = True) -> Dict[int, Dict]:
        if not slots:
            return {}

        model = cp_model.CpModel()
        slot_index_vars = []
        slot_movie_vars = []
        slot_runtime_vars = []
        slot_movie_options = []

        for i, slot in enumerate(slots):
            valid_movie_ids = self._get_valid_movies(slot['duration'], mood, unwatched_ids, exclude_ids)
            if not valid_movie_ids:
                return {}

            runtime_values = []
            for movie_id in valid_movie_ids:
                movie_info = self.movies_df[self.movies_df['movie_id'] == movie_id].iloc[0]
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

        for i, slot in enumerate(slots):
            movie_id = solver.Value(slot_movie_vars[i])
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
