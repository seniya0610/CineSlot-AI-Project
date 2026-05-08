import os
import sqlite3
os.chdir(r'c:\Users\isl-y\OneDrive\Documents\SEMESTER 4\AI\CINESLOT-PROJECT\CineSlot-AI-Project')
conn = sqlite3.connect('data/movies.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(c.fetchall())
c.execute('PRAGMA table_info(saved_schedules)')
print(c.fetchall())
c.execute('SELECT genre_name FROM genre ORDER BY genre_name')
print([row[0] for row in c.fetchall()])
conn.close()
