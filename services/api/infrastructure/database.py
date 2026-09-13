import os
from tinydb import TinyDB

_db_instances = {}

def get_db() -> TinyDB:
    """Dependency injection for TinyDB"""
    db_path = os.environ.get("TINYDB_PATH", os.path.join(os.path.dirname(__file__), "db.json"))
    if db_path not in _db_instances:
        _db_instances[db_path] = TinyDB(db_path)
    return _db_instances[db_path]


def get_incidents_table(db_instance: TinyDB = None):
    """Returns the incidents table from TinyDB."""
    target_db = db_instance if db_instance is not None else get_db()
    return target_db.table("incidents")

