"""
Pydantic models for request/response validation
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List, Union
from datetime import datetime


class GameCreate(BaseModel):
    """Model for creating a new game"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class GameUpdate(BaseModel):
    """Model for updating a game"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class GameResponse(BaseModel):
    """Model for game response"""
    id: int
    name: str
    description: Optional[str]
    cover_url: Optional[str] = None
    rulebook_count: int = 0
    is_ready: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    """Model for document response"""
    id: int
    game_id: int
    filename: str
    file_size: int
    pages: Optional[int]
    status: str
    source_type: str = "official_rulebook"
    processing_report: Optional[Dict[str, Any]] = None
    created_at: datetime


class DocumentUpdate(BaseModel):
    """Manual document metadata corrections."""
    source_type: str = Field("official_rulebook", max_length=50)


class ChunkResponse(BaseModel):
    """Model for chunk response"""
    id: int
    document_id: int
    chunk_index: int
    content: str
    rule_type: str = "text"
    enabled: bool = True
    keywords: Optional[str] = None
    section_title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    rule_scope: str = "base"
    source_kind: str = "rule"
    metadata: Optional[Dict[str, Any]] = None


class ChunkUpdate(BaseModel):
    """Model for manual chunk corrections."""
    content: str = Field(..., min_length=1)
    rule_type: str = Field("text", max_length=50)
    enabled: bool = True
    keywords: Optional[str] = Field(None, max_length=1000)
    section_title: Optional[str] = Field(None, max_length=255)
    rule_scope: str = Field("base", max_length=50)


class ChunkSplitRequest(BaseModel):
    """Model for splitting one chunk into two chunks."""
    split_at: int = Field(..., gt=0)


class GlossaryTermResponse(BaseModel):
    """Game-specific rulebook glossary term."""
    id: int
    game_id: int
    term: str
    aliases: List[str] = []
    term_type: str = "term"
    description: Optional[str] = None
    source_pages: List[int] = []
    chunk_refs: List[int] = []
    related_terms: List[str] = []
    search_terms: List[str] = []
    enabled: bool = True
    importance: float = 0


class GlossaryTermUpdate(BaseModel):
    """Manual glossary term corrections."""
    term: str = Field(..., min_length=1, max_length=255)
    aliases: List[str] = []
    term_type: str = Field("term", max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    related_terms: List[str] = []
    search_terms: List[str] = []
    enabled: bool = True


class GlossaryMatchResponse(BaseModel):
    """Potential glossary match used for query rewriting."""
    term: str
    aliases: List[str] = []
    term_type: str = "term"
    description: Optional[str] = None
    score: float


class ChatMessage(BaseModel):
    """Model for chat message"""
    message: str = Field(..., min_length=1, max_length=2000)
    display_message: Optional[str] = Field(None, min_length=1, max_length=240)
    retrieval_message: Optional[str] = Field(None, min_length=1, max_length=500)
    answer_mode: str = Field("concise", pattern="^(concise|detailed|auto)$")


class SourceResponse(BaseModel):
    """Rulebook source excerpt with optional visual page context."""
    excerpt: str
    page: Optional[int] = None
    image_url: Optional[str] = None
    highlight_regions: Optional[List[Dict[str, float]]] = None
    filename: Optional[str] = None
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None
    source_type: Optional[str] = None
    source_label: Optional[str] = None


class VisualReference(BaseModel):
    """Visual context for a referenced rulebook component or page."""
    title: str
    subtitle: Optional[str] = None
    image_url: str
    matched_terms: List[str] = Field(default_factory=list)
    page: Optional[int] = None
    filename: Optional[str] = None
    document_id: Optional[int] = None
    source_type: Optional[str] = None
    source_label: Optional[str] = None


class AssetBBox(BaseModel):
    """Normalized crop box on a rendered PDF page."""
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    width: float = Field(..., gt=0, le=1)
    height: float = Field(..., gt=0, le=1)


class GameAssetCreate(BaseModel):
    """Create a manually curated visual asset."""
    document_id: int
    page: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    asset_type: str = Field("component", max_length=50)
    keywords: List[str] = []
    bbox: AssetBBox
    enabled: bool = True


class GameAssetUpdate(BaseModel):
    """Update manually curated visual asset metadata."""
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    asset_type: str = Field("component", max_length=50)
    keywords: List[str] = []
    enabled: bool = True


class GameAssetResponse(BaseModel):
    """Manually curated visual asset."""
    id: int
    game_id: int
    document_id: Optional[int] = None
    page: Optional[int] = None
    name: str
    display_name: Optional[str] = None
    asset_type: str = "component"
    keywords: List[str] = []
    image_url: str
    source_bbox: Optional[Dict[str, float]] = None
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class LayoutRegionCreate(BaseModel):
    """Create a manually curated PDF layout region for text extraction."""
    page: int = Field(..., ge=1)
    label: Optional[str] = Field(None, max_length=255)
    region_type: str = Field("rule", max_length=50)
    reading_order: int = Field(1, ge=1)
    bbox: AssetBBox
    enabled: bool = True


class LayoutRegionUpdate(BaseModel):
    """Update a manually curated PDF layout region."""
    label: Optional[str] = Field(None, max_length=255)
    region_type: str = Field("rule", max_length=50)
    reading_order: int = Field(1, ge=1)
    bbox: AssetBBox
    enabled: bool = True


class LayoutRegionResponse(BaseModel):
    """Manually curated PDF layout region."""
    id: int
    document_id: int
    page: int
    label: Optional[str] = None
    region_type: str = "rule"
    reading_order: int = 1
    bbox: Dict[str, float]
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class ChatResponse(BaseModel):
    """Model for chat response"""
    id: int
    user_message: str
    assistant_response: str
    sources: Optional[List[Union[str, SourceResponse]]]
    visual_refs: Optional[List[VisualReference]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    detailed_response: Optional[str] = None
    detailed_sources: Optional[List[Union[str, SourceResponse]]] = None
    detailed_visual_refs: Optional[List[VisualReference]] = None
    detailed_performance_metrics: Optional[Dict[str, Any]] = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Model for chat history"""
    messages: List[ChatResponse]
    total: int


class ProviderConfig(BaseModel):
    """Model provider settings"""
    api_base: str = Field(..., min_length=1, max_length=500)
    api_key: str = Field("", max_length=5000)
    model: str = Field(..., min_length=1, max_length=255)
    thinking_enabled: bool = False
    reasoning_effort: str = Field("high", pattern="^(low|medium|high|max)$")


class RerankConfig(BaseModel):
    """Reranker settings. API key/base are shared with embedding."""
    enabled: bool = False
    model: str = Field(..., min_length=1, max_length=255)
    candidates: int = Field(30, ge=8, le=80)
    top_n: int = Field(8, ge=1, le=30)


class ModelConfigResponse(BaseModel):
    """Model provider settings returned to the client"""
    chat: ProviderConfig
    embedding: ProviderConfig
    rerank: RerankConfig


class ModelConfigUpdate(BaseModel):
    """Model provider settings update"""
    chat: ProviderConfig
    embedding: ProviderConfig
    rerank: RerankConfig
