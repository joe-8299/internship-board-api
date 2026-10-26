"""Reset the database and reload seed.json:  python seed.py"""
import os, server
if os.path.exists(server.DB_PATH):
    os.remove(server.DB_PATH)
server.init_db()
print("Database reset and seeded:", server.DB_PATH)
