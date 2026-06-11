# Board Game Rulebook AI Assistant - Development Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                         │
│  - Game Management                                           │
│  - Document Upload                                           │
│  - Chat Interface                                            │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
┌────────────────────────▼────────────────────────────────────┐
│                  Backend (FastAPI)                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Routes Layer                                         │   │
│  │ - /api/games                                         │   │
│  │ - /api/documents                                     │   │
│  │ - /api/chat                                          │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Services Layer                                       │   │
│  │ - AIService (LLM)                                    │   │
│  │ - PDFProcessor                                       │   │
│  │ - VectorStore (ChromaDB)                             │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Data Layer                                           │   │
│  │ - SQLite Database                                    │   │
│  │ - Vector Database (ChromaDB)                         │   │
│  │ - File Storage                                       │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
    ┌───▼──┐        ┌────▼────┐    ┌─────▼──┐
    │OpenAI│        │ChromaDB  │    │SQLite  │
    │ API  │        │(Vectors) │    │(Data)  │
    └──────┘        └──────────┘    └────────┘
```

## Data Flow

### 1. Document Upload Flow
```
User uploads PDF
    ↓
FastAPI receives file
    ↓
PDFProcessor extracts text
    ↓
TextChunker splits into chunks
    ↓
Store in SQLite + ChromaDB
    ↓
Return success to frontend
```

### 2. Question Answering Flow
```
User asks question
    ↓
VectorStore searches for relevant chunks
    ↓
AIService generates response using LLM
    ↓
Store conversation in SQLite
    ↓
Return response + sources to frontend
```

## Key Design Decisions

1. **Chunking Strategy**: Text is split into 1000-character chunks with 200-character overlap to maintain context.

2. **Vector Storage**: ChromaDB provides fast semantic search without requiring a separate vector database server.

3. **SQLite**: Lightweight database suitable for single-server deployment, easy to backup and migrate.

4. **LangChain**: Simplifies LLM integration and provides utilities for text processing.

5. **React + Zustand**: Lightweight state management without Redux complexity.

## Development Workflow

### Adding a New Feature

1. **Backend**:
   - Add database schema changes to `app/database.py`
   - Create new service in `app/services/` if needed
   - Add route handler in `app/routes/`
   - Add Pydantic models in `app/models.py`

2. **Frontend**:
   - Create new component in `src/components/`
   - Add store state in `src/store/` if needed
   - Add API client method in `src/api/client.js`
   - Update main App component

### Testing

Backend:
```bash
# Run with debug mode
DEBUG=True python main.py

# Check API docs
curl http://localhost:8000/docs
```

Frontend:
```bash
# Development with hot reload
npm run dev

# Build and preview
npm run build
npm run preview
```

## Performance Considerations

1. **PDF Processing**: Large PDFs are processed synchronously. Consider async processing for production.

2. **Vector Search**: ChromaDB is in-memory by default. For large datasets, use persistent storage.

3. **API Rate Limiting**: Add rate limiting for production deployment.

4. **Caching**: Consider caching frequently asked questions.

## Security Considerations

1. **API Key**: Never commit `.env` file with real API keys.

2. **File Upload**: Validate file types and sizes on both frontend and backend.

3. **CORS**: Configure CORS properly for production domains.

4. **Input Validation**: All user inputs are validated using Pydantic.

5. **SQL Injection**: Using parameterized queries prevents SQL injection.

## Deployment

### Backend Deployment

1. Set environment variables on server
2. Install dependencies: `pip install -r requirements.txt`
3. Use production ASGI server: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app`
4. Set up reverse proxy (nginx)
5. Enable HTTPS

### Frontend Deployment

1. Build: `npm run build`
2. Deploy `dist/` folder to static hosting
3. Configure API endpoint for production backend
4. Enable gzip compression

## Monitoring and Logging

- Backend logs to console (configure logging in `main.py`)
- Frontend errors logged to browser console
- Database queries can be logged for debugging

## Future Enhancements

1. **User Authentication**: Add user accounts and game sharing
2. **Async Processing**: Use Celery for background PDF processing
3. **Advanced Search**: Implement filters and advanced query syntax
4. **Multi-language Support**: Support for multiple languages
5. **Mobile App**: React Native mobile application
6. **Analytics**: Track popular questions and improve responses
7. **Custom Models**: Support for custom LLM models
8. **Batch Processing**: Process multiple PDFs at once
