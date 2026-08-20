import sqlite3
c = sqlite3.connect('data/db/autoapply.db')
for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(row[0])

for row in c.execute("PRAGMA table_info(jobs)"):
    print(row)
