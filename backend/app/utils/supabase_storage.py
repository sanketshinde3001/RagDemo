"""
Supabase Storage Utility
Handles file uploads to Supabase Storage bucket
"""

from supabase import create_client, Client
from app.core.config import settings
import logging
from pathlib import Path
from typing import Optional, Dict
import mimetypes

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """
    Handle file uploads to Supabase Storage
    """
    
    def __init__(self):
        """Initialize Supabase client"""
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY  # Use service key for admin operations
        )
        self.bucket_name = settings.SUPABASE_STORAGE_BUCKET
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the storage bucket exists"""
        try:
            # Try to get bucket info
            buckets = self.client.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            
            if self.bucket_name not in bucket_names:
                # Create bucket if it doesn't exist
                self.client.storage.create_bucket(
                    self.bucket_name,
                    options={"public": True}
                )
                logger.info(f"Created Supabase storage bucket: {self.bucket_name}")
            else:
                logger.info(f"Using existing bucket: {self.bucket_name}")
        except Exception as e:
            logger.warning(f"Could not verify/create bucket: {e}")
    
    def upload_file(
        self, 
        file_path: str, 
        storage_path: str,
        content_type: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Upload a file to Supabase Storage
        
        Args:
            file_path: Local file path to upload
            storage_path: Path in storage bucket (e.g., "pdfs/doc123.pdf")
            content_type: MIME type (auto-detected if not provided)
            
        Returns:
            Dict with 'path' and 'url' of uploaded file
        """
        try:
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Auto-detect content type if not provided
            if content_type is None:
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = 'application/octet-stream'
            
            # Upload to Supabase Storage
            response = self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            
            # Construct public URL manually to ensure it's correct
            # Format: {SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}
            base_url = settings.SUPABASE_URL.rstrip('/')
            public_url = f"{base_url}/storage/v1/object/public/{self.bucket_name}/{storage_path}"
            
            logger.info(f"✓ Uploaded to Supabase: {storage_path}")
            logger.info(f"  Public URL: {public_url}")
            
            return {
                'path': storage_path,
                'url': public_url,
                'bucket': self.bucket_name
            }
            
        except Exception as e:
            logger.error(f"Error uploading to Supabase: {e}")
            raise
    
    def upload_bytes(
        self,
        file_bytes: bytes,
        storage_path: str,
        content_type: str = 'application/octet-stream'
    ) -> Dict[str, str]:
        """
        Upload bytes directly to Supabase Storage
        
        Args:
            file_bytes: File content as bytes
            storage_path: Path in storage bucket
            content_type: MIME type
            
        Returns:
            Dict with 'path' and 'url' of uploaded file
        """
        try:
            # Upload to Supabase Storage
            response = self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            
            # Construct public URL manually
            base_url = settings.SUPABASE_URL.rstrip('/')
            public_url = f"{base_url}/storage/v1/object/public/{self.bucket_name}/{storage_path}"
            
            logger.info(f"✓ Uploaded bytes to Supabase: {storage_path}")
            
            return {
                'path': storage_path,
                'url': public_url,
                'bucket': self.bucket_name
            }
            
        except Exception as e:
            logger.error(f"Error uploading bytes to Supabase: {e}")
            raise
    
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from Supabase Storage
        
        Args:
            storage_path: Path in storage bucket
            
        Returns:
            True if successful
        """
        try:
            self.client.storage.from_(self.bucket_name).remove([storage_path])
            logger.info(f"✓ Deleted from Supabase: {storage_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from Supabase: {e}")
            return False
    
    def get_public_url(self, storage_path: str) -> str:
        """
        Get public URL for a file
        
        Args:
            storage_path: Path in storage bucket
            
        Returns:
            Public URL string (cleaned)
        """
        url = self.client.storage.from_(self.bucket_name).get_public_url(storage_path)
        return url.rstrip('?')  # Remove trailing ? if present


# Convenience functions
_storage_client = None

def get_storage_client() -> SupabaseStorage:
    """Get or create Supabase storage client singleton"""
    global _storage_client
    if _storage_client is None:
        _storage_client = SupabaseStorage()
    return _storage_client


def upload_to_supabase(file_path: str, storage_path: str) -> Dict[str, str]:
    """
    Quick upload function
    
    Args:
        file_path: Local file to upload
        storage_path: Destination path in storage
        
    Returns:
        Upload result with URL
    """
    client = get_storage_client()
    return client.upload_file(file_path, storage_path)
