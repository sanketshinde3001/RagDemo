# FastAPI Template

A production-ready FastAPI template with a clean, modular structure.

## Features

- ✅ FastAPI framework
- ✅ Pydantic for data validation
- ✅ CORS middleware configured
- ✅ Environment-based configuration
- ✅ RESTful API example (CRUD operations)
- ✅ Modular structure (routes, schemas, models)
- ✅ API documentation (Swagger UI & ReDoc)

## Project Structure

```
backend/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── env.example            # Example environment variables
├── .gitignore             # Git ignore rules
└── app/
    ├── __init__.py
    ├── api/
    │   ├── __init__.py
    │   └── routes.py      # API routes
    ├── core/
    │   ├── __init__.py
    │   └── config.py      # Configuration settings
    ├── models/            # Database models (for SQLAlchemy)
    │   └── __init__.py
    └── schemas/           # Pydantic schemas
        ├── __init__.py
        └── item.py
```

## Setup Instructions

### 1. Create Virtual Environment

```powershell
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment

```powershell
# Copy example environment file
copy env.example .env

# Edit .env file with your settings
```

### 4. Run the Application

```powershell
# Development mode with auto-reload
uvicorn main:app --reload

# Or specify host and port
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Documentation

Once the server is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Root endpoint**: http://localhost:8000/
- **Health check**: http://localhost:8000/health

## Example API Endpoints

### Items CRUD

- `GET /api/v1/items` - Get all items
- `GET /api/v1/items/{item_id}` - Get specific item
- `POST /api/v1/items` - Create new item
- `PUT /api/v1/items/{item_id}` - Update item
- `DELETE /api/v1/items/{item_id}` - Delete item

### Example Request

```bash
# Create an item
curl -X POST "http://localhost:8000/api/v1/items" \
  -H "Content-Type: application/json" \
  -d '{"name": "Laptop", "description": "Gaming laptop", "price": 1299.99}'
```

## Development

### Adding New Routes

1. Create new route handlers in `app/api/routes.py` or create a new file in `app/api/`
2. Define Pydantic schemas in `app/schemas/`
3. Add database models in `app/models/` (if using a database)
4. Include the router in `main.py`

### Configuration

Edit `app/core/config.py` to add new configuration options. Use environment variables in `.env` file.

## Database Integration

To add database support:

1. Install database driver (e.g., `pip install asyncpg` for PostgreSQL)
2. Create database models in `app/models/`
3. Set up database connection in `app/core/config.py`
4. Use SQLAlchemy or other ORM

## Testing

To add tests:

```powershell
pip install pytest pytest-asyncio httpx
```

Create a `tests/` directory and write your test cases.

## Deployment

For production deployment:

1. Set `DEBUG=False` in environment variables
2. Use a production ASGI server
3. Configure proper CORS origins
4. Set up database connection pooling
5. Use environment secrets management

```powershell
# Production run
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## License

MIT License
