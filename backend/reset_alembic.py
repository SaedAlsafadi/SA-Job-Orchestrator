import sqlite3
c = sqlite3.connect('data/db/autoapply.db')
c.execute('DELETE FROM alembic_version')
c.execute("INSERT INTO alembic_version VALUES ('0006')")
c.commit()
