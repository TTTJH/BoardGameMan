"""
Embedding service using SiliconFlow Qwen3-VL-Embedding-8B
"""

import logging
import requests
from typing import List
from app.services.model_config import get_model_config

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using SiliconFlow"""
    
    def __init__(self):
        """Initialize the embedding service"""
        config = get_model_config()["embedding"]
        self.api_key = config["api_key"]
        self.api_base = config["api_base"]
        self.model = config["model"]
        self.url = f"{self.api_base}/embeddings"
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": text,
                    "encoding_format": "float"
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            embedding = data["data"][0]["embedding"]
            logger.debug(f"Generated embedding for text: {text[:50]}...")
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": texts,
                    "encoding_format": "float"
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            logger.debug(f"Generated embeddings for {len(texts)} texts")
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
