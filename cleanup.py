import os, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def human_size(size_bytes):
    for unit in ['B','KB','MB','GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f}TB"

def silent_cleanup():
    print("🧹 Running auto cleanup...")

    for root, dirs, _ in os.walk(BASE_DIR):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)

    uploads_path = os.path.join(BASE_DIR, "static", "uploads")
    if os.path.exists(uploads_path):
        shutil.rmtree(uploads_path, ignore_errors=True)

    if os.path.exists(DB_PATH):
        size = os.path.getsize(DB_PATH)
        print(f"💾 database.db size: {human_size(size)}")
        if size > 50 * 1024 * 1024:
            os.remove(DB_PATH)
            print("⚠️ Database too large — deleted (auto rebuild next run).")

    print("✅ Cleanup complete!\n")

if __name__ == "__main__":
    silent_cleanup()

