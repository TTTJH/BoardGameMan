"""
Database initialization and management
"""

import sqlite3
import os
from app.config import settings


def init_db():
    """Initialize the SQLite database with required tables"""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create games table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            cover_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(games)")
    game_columns = {row[1] for row in cursor.fetchall()}
    if "cover_url" not in game_columns:
        cursor.execute("ALTER TABLE games ADD COLUMN cover_url TEXT")
    
    # Create documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            pages INTEGER,
            status TEXT DEFAULT 'processing',
            source_type TEXT DEFAULT 'official_rulebook',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("PRAGMA table_info(documents)")
    document_columns = {row[1] for row in cursor.fetchall()}
    if "source_type" not in document_columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN source_type TEXT DEFAULT 'official_rulebook'")
    
    # Create chunks table for storing processed document chunks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER,
            content TEXT NOT NULL,
            embedding_id TEXT,
            rule_type TEXT DEFAULT 'text',
            enabled INTEGER DEFAULT 1,
            keywords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("PRAGMA table_info(chunks)")
    chunk_columns = {row[1] for row in cursor.fetchall()}
    if "rule_type" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN rule_type TEXT DEFAULT 'text'")
    if "enabled" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN enabled INTEGER DEFAULT 1")
    if "keywords" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN keywords TEXT")
    if "section_title" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN section_title TEXT")
    if "page_start" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN page_start INTEGER")
    if "page_end" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN page_end INTEGER")
    if "rule_scope" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN rule_scope TEXT DEFAULT 'base'")
    if "source_kind" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN source_kind TEXT DEFAULT 'rule'")
    if "metadata_json" not in chunk_columns:
        cursor.execute("ALTER TABLE chunks ADD COLUMN metadata_json TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            report_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_processing_reports_document
        ON processing_reports(document_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS glossary_terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            term TEXT NOT NULL,
            aliases TEXT,
            term_type TEXT DEFAULT 'term',
            description TEXT,
            source_pages TEXT,
            chunk_refs TEXT,
            related_terms TEXT,
            search_terms TEXT,
            enabled INTEGER DEFAULT 1,
            importance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_glossary_terms_game
        ON glossary_terms(game_id)
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_glossary_terms_game_term
        ON glossary_terms(game_id, term)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eval_cases (
            id TEXT PRIMARY KEY,
            game_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            expected_pages TEXT,
            expected_terms TEXT,
            evidence_quote TEXT,
            category TEXT DEFAULT 'action',
            notes TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("PRAGMA table_info(eval_cases)")
    eval_case_columns = {row[1] for row in cursor.fetchall()}
    if "failure_type" not in eval_case_columns:
        cursor.execute("ALTER TABLE eval_cases ADD COLUMN failure_type TEXT DEFAULT 'unreviewed'")
    if "review_notes" not in eval_case_columns:
        cursor.execute("ALTER TABLE eval_cases ADD COLUMN review_notes TEXT")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_eval_cases_game
        ON eval_cases(game_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            case_count INTEGER NOT NULL,
            passed_count INTEGER NOT NULL,
            pass_rate REAL NOT NULL,
            source_hit_rate REAL NOT NULL,
            term_coverage_avg REAL NOT NULL,
            summary_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("PRAGMA table_info(eval_runs)")
    eval_run_columns = {row[1] for row in cursor.fetchall()}
    if "mode" not in eval_run_columns:
        cursor.execute("ALTER TABLE eval_runs ADD COLUMN mode TEXT DEFAULT 'retrieval'")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_eval_runs_game
        ON eval_runs(game_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            case_id TEXT NOT NULL,
            passed INTEGER NOT NULL,
            source_hit INTEGER NOT NULL,
            term_coverage REAL NOT NULL,
            expected_pages TEXT,
            found_pages TEXT,
            missing_terms TEXT,
            top_sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES eval_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (case_id) REFERENCES eval_cases(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("PRAGMA table_info(eval_results)")
    eval_result_columns = {row[1] for row in cursor.fetchall()}
    if "assistant_answer" not in eval_result_columns:
        cursor.execute("ALTER TABLE eval_results ADD COLUMN assistant_answer TEXT")
    if "answer_term_coverage" not in eval_result_columns:
        cursor.execute("ALTER TABLE eval_results ADD COLUMN answer_term_coverage REAL")
    if "answer_missing_terms" not in eval_result_columns:
        cursor.execute("ALTER TABLE eval_results ADD COLUMN answer_missing_terms TEXT")
    if "cited_source_hit" not in eval_result_columns:
        cursor.execute("ALTER TABLE eval_results ADD COLUMN cited_source_hit INTEGER")

    # Create chunk embeddings table for SQLite-backed vector search fallback.
    # This is used when ChromaDB is unavailable in the local environment.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            embedding_id TEXT PRIMARY KEY,
            game_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            vector_norm REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_game
        ON chunk_embeddings(game_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_document
        ON chunk_embeddings(document_id)
    """)
    
    # Create chat history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            user_message TEXT NOT NULL,
            assistant_response TEXT NOT NULL,
            sources TEXT,
            visual_refs TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("PRAGMA table_info(chat_history)")
    chat_history_columns = {row[1] for row in cursor.fetchall()}
    if "visual_refs" not in chat_history_columns:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN visual_refs TEXT")
    if "performance_metrics" not in chat_history_columns:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN performance_metrics TEXT")
    if "detailed_response" not in chat_history_columns:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN detailed_response TEXT")
    if "detailed_sources" not in chat_history_columns:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN detailed_sources TEXT")
    if "detailed_visual_refs" not in chat_history_columns:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN detailed_visual_refs TEXT")
    if "detailed_performance_metrics" not in chat_history_columns:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN detailed_performance_metrics TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            document_id INTEGER,
            page INTEGER,
            name TEXT NOT NULL,
            display_name TEXT,
            asset_type TEXT DEFAULT 'component',
            keywords TEXT,
            image_path TEXT NOT NULL,
            source_bbox TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_assets_game
        ON game_assets(game_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_assets_enabled
        ON game_assets(game_id, enabled)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_layout_regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            page INTEGER NOT NULL,
            label TEXT,
            region_type TEXT DEFAULT 'rule',
            reading_order INTEGER DEFAULT 1,
            bbox TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_layout_regions_document_page
        ON document_layout_regions(document_id, page, reading_order)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_layout_regions_enabled
        ON document_layout_regions(document_id, enabled)
    """)

    # Create application settings table for user-editable model providers.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


def get_db_connection():
    """Get a database connection"""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
