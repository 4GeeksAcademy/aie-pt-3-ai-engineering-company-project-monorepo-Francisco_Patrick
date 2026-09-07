import os
from tinydb import TinyDB

# Ensure the db file is in the same directory or a specified path
DB_PATH = os.environ.get("TINYDB_PATH", os.path.join(os.path.dirname(__file__), "db.json"))

# Initialize TinyDB instance
db = TinyDB(DB_PATH)

def get_db() -> TinyDB:
    """Dependency injection for TinyDB"""
    return db
