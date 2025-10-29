from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Chatbot API"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://*.vercel.app",  # Allow all Vercel preview deployments
        "https://your-app.vercel.app",  # Replace with your actual domain
    ]
    
    # Database
    DATABASE_URL: str = "sqlite:///./sql_app.db"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    PASSWORD: str = ""
    SUPABASE_STORAGE_BUCKET: str = "documents"
    
    # AI APIs
    DEEPGRAM_API_KEY: str = ""
    SERPER_API_KEY: str = ""  # Serper.dev for web search
    
    # Google AI (Gemini)
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    
    # Embeddings
    EMBEDDING_MODEL: str = "llama-text-embed-v2"
    EMBEDDING_DIMENSIONS: int = 1024
    
    # Vector Database (Pinecone)
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = "us-east-1-aws"
    PINECONE_INDEX_NAME: str = "rag-chatbot"
    
    # Security
    SECRET_KEY: str = "Rag-chatbot-sanket"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App Settings
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
