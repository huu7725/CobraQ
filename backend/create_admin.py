"""Create an admin using explicit environment configuration; never print credentials."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
from app.services.seed_admin import seed_admin
if __name__ == "__main__":
    email=seed_admin()
    print("Admin configuration applied." if email else "Set ADMIN_EMAIL and ADMIN_PASSWORD before running this command.")
