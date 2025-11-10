import sqlite3
import os

DB_NAME = "database.db"

def init_db():
    # Delete old database if needed
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print("🗑️ Old database removed successfully!")

    # Create new database
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # ---------------- USERS TABLE ---------------- #
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            account_number TEXT PRIMARY KEY,          -- 10-digit system generated
            username TEXT UNIQUE NOT NULL,            -- unique username for login
            password TEXT NOT NULL,                   -- login password
            name TEXT NOT NULL,                       -- full name
            email TEXT UNIQUE NOT NULL,               -- unique email
            phone TEXT UNIQUE NOT NULL,               -- 10-digit phone number
            dob TEXT NOT NULL,                        -- date of birth
            age INTEGER NOT NULL,                     -- must be >= 18
            address TEXT,                             -- optional address field
            profile TEXT DEFAULT 'default.png',       -- profile picture (future use)
            balance REAL DEFAULT 0.0 NOT NULL,        -- balance cannot be NULL
            upi_pin TEXT                              -- 6-digit UPI PIN for secure transactions
        );
        """)

        # ---------------- TRANSACTIONS TABLE ---------------- #
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT NOT NULL,             -- linked to sender account
            type TEXT NOT NULL,                       -- Deposit / Withdraw / Transfer / Received
            amount REAL NOT NULL,                     -- transaction amount
            receiver TEXT,                            -- receiver account name or number
            date TEXT NOT NULL,                       -- timestamp
            FOREIGN KEY (account_number) REFERENCES users(account_number)
        );
        """)

        conn.commit()
        print("✅ Database and tables created successfully!")

def verify_db_structure():
    """Verifies that all required columns exist, adds missing ones automatically."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()

        # Expected user columns
        expected_user_cols = {
            'account_number', 'username', 'password', 'name', 'email',
            'phone', 'dob', 'age', 'address', 'profile', 'balance', 'upi_pin'
        }

        cur.execute("PRAGMA table_info(users)")
        current_cols = {row[1] for row in cur.fetchall()}

        missing_cols = expected_user_cols - current_cols
        for col in missing_cols:
            if col == 'upi_pin':
                cur.execute("ALTER TABLE users ADD COLUMN upi_pin TEXT;")
                print("🩵 Added missing column: upi_pin")
            elif col == 'balance':
                cur.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0;")
                print("🩵 Added missing column: balance")
            elif col == 'profile':
                cur.execute("ALTER TABLE users ADD COLUMN profile TEXT DEFAULT 'default.png';")
                print("🩵 Added missing column: profile")
            elif col == 'address':
                cur.execute("ALTER TABLE users ADD COLUMN address TEXT;")
                print("🩵 Added missing column: address")

        conn.commit()
        print("🔍 Database structure verified and repaired (if needed).")

if __name__ == "__main__":
    print("⚙️ Setting up Banking Management System database...")
    init_db()
    verify_db_structure()
    print("🚀 Setup complete. You can now run app.py")

