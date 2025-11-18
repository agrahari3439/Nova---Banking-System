import sqlite3
import os

DB_NAME = "database.db"

def init_db():
    # Delete old database ONLY if user confirms
    if os.path.exists(DB_NAME):
        confirm = input("⚠️ Delete existing database? Type YES to confirm: ")
        if confirm != "YES":
            print("❌ Operation cancelled. Old database kept.")
            return
        os.remove(DB_NAME)
        print("🗑️ Old database removed successfully!")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # USERS TABLE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            account_number TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            dob TEXT NOT NULL,
            age INTEGER NOT NULL,
            address TEXT,
            profile TEXT DEFAULT 'default.png',
            balance REAL DEFAULT 0.0 NOT NULL,
            upi_pin TEXT
        );
        """)

        # TRANSACTIONS TABLE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            receiver TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (account_number) REFERENCES users(account_number)
        );
        """)

        conn.commit()
        print("✅ Database and tables created successfully!")


def verify_db_structure():
    """Ensure all required columns exist."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()

        required = {
            'account_number', 'username', 'password', 'name', 'email',
            'phone', 'dob', 'age', 'address', 'profile',
            'balance', 'upi_pin'
        }

        cur.execute("PRAGMA table_info(users)")
        current = {row[1] for row in cur.fetchall()}

        missing = required - current

        def add(column, dtype, default=None):
            sql = f"ALTER TABLE users ADD COLUMN {column} {dtype}"
            if default is not None:
                sql += f" DEFAULT {default}"
            cur.execute(sql)
            print(f"🩵 Added column: {column}")

        for col in missing:
            if col == "profile":
                add("profile", "TEXT", "'default.png'")
            elif col == "balance":
                add("balance", "REAL", "0.0")
            else:
                add(col, "TEXT")

        conn.commit()
        print("🔍 Database verified and updated.")
        
if __name__ == "__main__":
    print("⚙️ Setting up database…")
    init_db()
    verify_db_structure()
    print("🚀 Done!")

