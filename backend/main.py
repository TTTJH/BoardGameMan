"""
Board Game Rulebook AI Assistant - Backend
Main FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from app.config import settings
from app.routes import games, documents, chat, evals, glossary, assets, settings as settings_routes
from app.database import init_db, get_db_connection
from app.services.vector_store import VectorStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("Starting Board Game Rulebook AI Assistant...")
    init_db()
    
    # Initialize vector store collections for existing games
    try:
        vector_store = VectorStore()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM games")
        games_list = cursor.fetchall()
        conn.close()
        
        for game_row in games_list:
            game_id = game_row['id']
            try:
                vector_store.create_collection(game_id)
            except Exception as e:
                logger.warning(f"Could not create collection for game {game_id}: {e}")
    except Exception as e:
        logger.warning(f"Error initializing vector store collections: {e}")
    
    yield
    # Shutdown
    logger.info("Shutting down Board Game Rulebook AI Assistant...")


app = FastAPI(
    title="Board Game Rulebook AI Assistant",
    description="AI-powered assistant for board game rulebook queries",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path(settings.UPLOAD_DIR, "covers").mkdir(parents=True, exist_ok=True)
Path(settings.UPLOAD_DIR, "rule_pages").mkdir(parents=True, exist_ok=True)
Path(settings.UPLOAD_DIR, "visual_refs").mkdir(parents=True, exist_ok=True)
Path(settings.UPLOAD_DIR, "game_assets").mkdir(parents=True, exist_ok=True)
app.mount("/covers", StaticFiles(directory=str(Path(settings.UPLOAD_DIR, "covers"))), name="covers")
app.mount("/rule-pages", StaticFiles(directory=str(Path(settings.UPLOAD_DIR, "rule_pages"))), name="rule-pages")
app.mount("/visual-refs", StaticFiles(directory=str(Path(settings.UPLOAD_DIR, "visual_refs"))), name="visual-refs")
app.mount("/game-assets", StaticFiles(directory=str(Path(settings.UPLOAD_DIR, "game_assets"))), name="game-assets")

# Include routers
app.include_router(games.router, prefix="/api/games", tags=["games"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(evals.router, prefix="/api/evals", tags=["evals"])
app.include_router(glossary.router, prefix="/api/glossary", tags=["glossary"])
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Board Game Rulebook AI Assistant API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
