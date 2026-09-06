import os
from tinydb import TinyDB

# Ensure the database file is placed in a consistent location
DB_PATH = os.path.join(os.path.dirname(__file__), "db.json")
db = TinyDB(DB_PATH)

def get_db() -> TinyDB:
    """Returns the TinyDB instance."""
    return db
