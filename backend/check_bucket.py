"""
Script to check and fix Supabase bucket permissions
"""

from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
BUCKET_NAME = os.getenv("SUPABASE_STORAGE_BUCKET", "documents")

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print(f"Checking bucket: {BUCKET_NAME}")
print(f"Supabase URL: {SUPABASE_URL}")
print()

try:
    # List all buckets
    buckets = client.storage.list_buckets()
    print("All buckets:")
    for bucket in buckets:
        print(f"  - {bucket.name} (public: {bucket.public})")
    print()
    
    # Find our bucket
    target_bucket = next((b for b in buckets if b.name == BUCKET_NAME), None)
    
    if target_bucket:
        print(f"Found bucket '{BUCKET_NAME}':")
        print(f"  Public: {target_bucket.public}")
        print(f"  ID: {target_bucket.id}")
        
        if not target_bucket.public:
            print(f"\n⚠️  Bucket is NOT public!")
            print(f"Updating bucket to make it public...")
            
            # Update bucket to be public
            client.storage.update_bucket(
                BUCKET_NAME,
                {"public": True}
            )
            print("✓ Bucket updated to public")
        else:
            print(f"\n✓ Bucket is already public")
            
        # Test URL construction
        test_path = "pdfs/287f63f4/sanketessay.pdf"
        public_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{BUCKET_NAME}/{test_path}"
        print(f"\nTest URL format:")
        print(f"  {public_url}")
        
    else:
        print(f"❌ Bucket '{BUCKET_NAME}' not found!")
        print(f"Creating bucket...")
        client.storage.create_bucket(
            BUCKET_NAME,
            options={"public": True}
        )
        print(f"✓ Bucket created as public")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
