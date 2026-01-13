"""
Script to encrypt existing API keys in the database.
Run this once after deploying the encryption feature.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from src.crypto_utils import encrypt_api_key, is_encrypted

DATABASE_URL = os.getenv("DATABASE_URL")


def migrate_api_keys():
    """Encrypt all unencrypted API keys in the database"""
    print("=" * 50)
    print("API Keys Encryption Migration")
    print("=" * 50)
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Fetch all API keys
        result = conn.execute(text("SELECT id, user_id, api_key, secret_key FROM api_keys"))
        rows = result.fetchall()
        
        if not rows:
            print("No API keys found in database.")
            return
        
        print(f"Found {len(rows)} API keys to check.\n")
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            key_id, user_id, api_key, secret_key = row
            
            # Check if already encrypted
            api_key_encrypted = is_encrypted(api_key)
            secret_encrypted = is_encrypted(secret_key)
            
            if api_key_encrypted and secret_encrypted:
                print(f"  [SKIP] Key ID {key_id} (User {user_id}) - Already encrypted")
                skipped += 1
                continue
            
            # Encrypt the keys
            print(f"  [ENCRYPT] Key ID {key_id} (User {user_id})...")
            
            new_api_key = api_key if api_key_encrypted else encrypt_api_key(api_key, user_id)
            new_secret = secret_key if secret_encrypted else encrypt_api_key(secret_key, user_id)
            
            conn.execute(
                text("UPDATE api_keys SET api_key = :api_key, secret_key = :secret_key WHERE id = :id"),
                {"api_key": new_api_key, "secret_key": new_secret, "id": key_id}
            )
            
            migrated += 1
        
        conn.commit()
        
        if migrated > 0:
            print(f"\n✅ Successfully encrypted {migrated} API key(s).")
        
        if skipped > 0:
            print(f"⏭️  Skipped {skipped} already-encrypted key(s).")
        
        print("\nMigration complete!")


if __name__ == "__main__":
    migrate_api_keys()
