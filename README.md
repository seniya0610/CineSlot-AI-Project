# CineSlot
### AI-Powered Personalized Movie Scheduling System

## Overview

CineSlot is an AI-powered movie scheduling assistant that intelligently plans your movie-watching sessions around your real-world time availability, personal taste, and viewing history. Unlike traditional recommendation engines, CineSlot treats movie selection as a **constraint-satisfaction problem** — scheduling the right film into the right time slot while respecting franchise chronological order, mood consistency, subscription availability, and prime-time preferences.

## Problem Statement

Today's streaming landscape is overwhelming. Users face:

- Hundreds of movies across multiple subscriptions with no unified viewing plan
- Franchise fatigue — not knowing which movie to watch next in a universe or series
- Poor time awareness — starting a 3-hour film when only 2 hours are free
- Repetitive recommendations surfacing the same titles over and over
- No scheduling intelligence — recommendations exist, but fitting them into a real day does not

CineSlot solves all of this by acting not just as a recommender, but as an **intelligent personal movie scheduler**.

## Features

### Time Slot Management
- Define available time windows per day (e.g., Saturday 8 PM – 11 PM)
- Movies are matched to slots based on runtime — no overruns

### Constraint-Based Scheduling (AI Heuristics)
- **LCV (Least Constraining Value):** Selects movies that maximize remaining scheduling flexibility
- **MRV (Minimum Remaining Values):** Fills the hardest-to-satisfy slots first
- **Prime-Time Consistency:** Highest-rated unwatched films are assigned to your preferred prime slots

### Franchise & Universe Awareness
- Detects MCU, DCEU, Harry Potter, Star Wars, and more
- Enforces chronological viewing order automatically
- Inference engine: if you've watched *Iron Man 1*, only post-Iron Man 1 entries are considered

### Personalized Recommendation Engine
- **Recommended For You** — based on watch history, ratings, and genre preferences
- **Try Something New** — surfaces highly rated films outside your comfort zone
- Real-time filtering as you type
- already-watched films are never resurfaced

### Watch History & Ratings
- Mark films as watched after each viewing
- Star/upvote ratings feed back into the recommendation model in real time

### Mood Consistency
- Prevents emotionally mismatched films back-to-back (e.g., no two heavy dramas in one day)
- Toggleable by the user

### Trailer Integration
- Trailers fetched via **YouTube Data API v3**
- Plays the most engaging segment — not just the full trailer

### Subscription Awareness *(Optional)*
- Filter recommendations by your active subscriptions (Netflix, Prime, Disney+, etc.)
- Can be disabled at any time

### Explainable AI
Every scheduling decision comes with a human-readable explanation:
> *"I placed The Avengers on Saturday night because it is your highest-rated remaining MCU film, and you prefer high-rated films for night slots."*

### Manual Override
- AI generates the initial schedule, but you can drag, swap, and remove films freely

## AI & Algorithmic Design

### Constraint Satisfaction Problem (CSP)
- **Variables:** Each available time slot
- **Domain:** Unwatched candidate movies that fit within the slot duration
- **Constraints:** Runtime ≤ slot duration · franchise order · mood consistency · subscription filter · uniqueness · prime-time preference

### Recommendation Model
- Content-based filtering using genre, director, cast, tone, and franchise data
- User-based collaborative filtering that learns from ratings and history over time
- Hybrid model handles both cold-start and returning users

### Inference Engine
- Rule-based logic derived from watch history
- Completion component selects an optimal franchise subset ranked by predicted rating
