from pathlib import Path
import sqlite3


DB_PATH = Path("data") / "slopeforge.db"


class Database:

    def __init__(self):

        DB_PATH.parent.mkdir(exist_ok=True)

        self.connection = sqlite3.connect(DB_PATH)
        self.connection.row_factory = sqlite3.Row

        self.create_tables()

    def create_tables(self):

        cursor = self.connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS deposits(

            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
        """)

        self.connection.commit()

    def add_deposit(self, name, description):

        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT INTO deposits(name, description)
            VALUES(?, ?)
            """,
            (name, description),
        )

        self.connection.commit()

    def get_deposits(self):

        cursor = self.connection.cursor()

        cursor.execute("""
        SELECT *
        FROM deposits
        ORDER BY name
        """)

        return cursor.fetchall()

