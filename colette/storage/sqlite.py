import sqlite3


@dataclass(frozen=True)
class Person:
    name: str
    organisation: str
    active: bool
    email: str


conn = sqlite3.connect("colette.db")

with conn:
    c.execute(
        """CREATE TABLE users (name text, email text, organisation text, active boolean)"""
    )
    c.execute("INSERT INTO users VALUES ('2006-01-05','BUY','RHAT',100,35.14)")


conn.close()
