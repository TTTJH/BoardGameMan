# Backend Setup Instructions

## Prerequisites
- Python 3.8 or higher
- pip package manager
- OpenAI API key

## Installation Steps

### 1. Create Virtual Environment
```bash
python -m venv venv
source venv/Scripts/activate  # Windows
# or
source venv/bin/activate      # macOS/Linux
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 4. Run the Application
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### 5. Access API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

- `main.py` - Application entry point
- `app/config.py` - Configuration management
- `app/database.py` - Database initialization
- `app/models.py` - Pydantic models
- `app/routes/` - API route handlers
- `app/services/` - Business logic services

## Key Services

- **AIService** - Generates responses using OpenAI API
- **PDFProcessor** - Extracts text from PDF files
- **TextChunker** - Splits text into manageable chunks
- **VectorStore** - Manages embeddings and semantic search

## Database

SQLite database with the following tables:
- `games` - Board game records
- `documents` - Uploaded PDF files
- `chunks` - Text chunks from documents
- `chat_history` - User conversations

## Troubleshooting

### Import Errors
Make sure you're in the virtual environment and all dependencies are installed.

### API Key Issues
Verify your OpenAI API key is correctly set in the `.env` file.

### Database Errors
Delete `boardgames.db` and restart the application to reinitialize the database.
