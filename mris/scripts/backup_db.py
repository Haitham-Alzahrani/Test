"""Write an online backup of the MRIS SQLite database (keeps MRIS_BACKUP_KEEP newest)."""

from mris.database import backup_database

if __name__ == "__main__":
    print(f"Backup written: {backup_database()}")
