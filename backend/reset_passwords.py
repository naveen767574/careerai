"""
reset_passwords.py — Emergency password reset utility.

Run from inside the backend folder with the venv active:
    cd backend
    venv\\Scripts\\python reset_passwords.py

Lists all users and lets you set a new password for any of them.
"""

import sys
import os

# Load .env so DATABASE_URL is available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass  # dotenv not installed — rely on system env

try:
    from sqlalchemy import create_engine, text
    from passlib.context import CryptContext
except ImportError:
    print("ERROR: Run this script with the venv active.")
    print("  cd backend")
    print("  venv\\\\Scripts\\\\python reset_passwords.py")
    sys.exit(1)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    # Try reading .env manually
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                DATABASE_URL = line.split("=", 1)[1]
                break

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found. Check your .env file.")
    sys.exit(1)

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
engine  = create_engine(DATABASE_URL)

def list_users(conn):
    rows = conn.execute(text("SELECT id, email, name FROM users ORDER BY id")).fetchall()
    return rows

def reset_password(conn, user_id: int, new_password: str):
    hashed = pwd_ctx.hash(new_password)
    conn.execute(
        text("UPDATE users SET password_hash = :h WHERE id = :id"),
        {"h": hashed, "id": user_id},
    )
    conn.commit()

def main():
    print("\n" + "="*55)
    print("  CareerAI — Password Reset Utility")
    print("="*55)

    with engine.connect() as conn:
        users = list_users(conn)

        if not users:
            print("\nNo users found in the database.")
            return

        print(f"\nFound {len(users)} user(s):\n")
        for u in users:
            print(f"  [{u.id}]  {u.email}  ({u.name})")

        print("\nEnter the user ID to reset, or 'all' to reset all users.")
        choice = input("Choice: ").strip().lower()

        if choice == "all":
            targets = list(users)
        else:
            try:
                uid = int(choice)
                targets = [u for u in users if u.id == uid]
                if not targets:
                    print(f"No user with id={uid}")
                    return
            except ValueError:
                print("Invalid input.")
                return

        for u in targets:
            print(f"\nResetting password for: {u.email}")
            pw = input("  New password (min 6 chars): ").strip()
            if len(pw) < 6:
                print("  Skipped — password too short.")
                continue
            reset_password(conn, u.id, pw)
            print(f"  ✓ Password updated for {u.email}")

    print("\nDone. You can now log in with your new password(s).\n")

if __name__ == "__main__":
    main()
