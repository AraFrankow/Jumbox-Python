import sqlite3
conn = sqlite3.connect("jumbox.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(cliente)")
for col in cursor.fetchall():
    print(col)
conn.close()
