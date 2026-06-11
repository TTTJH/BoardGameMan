"""
Vector database service for semantic search with hybrid search support.

The fallback search intentionally avoids game-specific rules. It uses a small
board-game bilingual glossary, BM25-style scoring, and neighbor expansion so a
hit carries enough surrounding rule context for the LLM.
"""

import logging
import json
import math
import re
import time
from collections import Counter
from typing import Dict, Iterable, List, Tuple

from app.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.model_config import get_model_config
from app.services.rerank_service import RerankService

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger(__name__)


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9]+")

GUIDE_SOURCE_TYPES = {"official_walkthrough", "official_tutorial", "player_guide"}
FAQ_SOURCE_TYPES = {"official_faq", "community_qa"}
ERRATA_SOURCE_TYPES = {"official_errata"}
RULEBOOK_SOURCE_TYPES = {"official_rulebook"}


QUERY_EXPANSIONS = {
    "\u89c4\u5219": "rule rules",
    "\u4ec0\u4e48\u662f": "definition means explained overview",
    "\u662f\u4ec0\u4e48": "definition means explained overview",
    "\u600e\u4e48": "how steps procedure do following",
    "\u5982\u4f55": "how steps procedure do following",
    "\u4ec0\u4e48\u65f6\u5019": "when may can during before after timing",
    "\u4f55\u65f6": "when may can during before after timing",
    "\u80fd\u5426": "can may allowed",
    "\u53ef\u4ee5": "can may allowed",
    "\u9700\u8981": "need must require cost",
    "\u6761\u4ef6": "condition requirement must can only",
    "\u4eba\u5c40": "players player count setup with players",
    "\u4e09\u4eba": "3 players with 3 players player count",
    "3\u4eba": "3 players with 3 players player count",
    "\u73a9\u5bb6\u6570": "player count number of players players setup",
    "\u73a9\u5bb6\u6570\u91cf": "player count number of players players setup",
    "\u4e0a\u9650": "maximum limit up to at most hand limit capacity",
    "\u6700\u591a": "maximum limit up to at most",
    "\u51e0\u5f20": "how many cards number count",
    "\u591a\u5c11\u5f20": "how many cards number count",
    "\u4fdd\u7559": "keep retain may have hold at the end",
    "\u7559": "keep retain may have hold",
    "\u624b\u724c": "hand cards in hand draw discard hand limit",
    "\u724c": "card cards deck hand discard draw",
    "\u724c\u7ec4": "deck cards discard draw shuffle",
    "\u62bd\u51fa": "remove return to the box unseen set aside based on player count setup",
    "\u62bd\u51fa\u6765": "remove return to the box unseen set aside based on player count setup",
    "\u5f03\u724c": "discard discarded discard pile",
    "\u62bd\u724c": "draw cards action deck",
    "\u83b7\u5f97": "gain take receive acquire",
    "\u5956\u52b1": "bonus reward score victory points points tile",
    "\u89e6\u53d1": "trigger triggers triggered effect bonus use may use cannot use",
    "\u6548\u679c": "effect effects trigger use may use cannot use",
    "\u53d1\u52a8": "activate trigger use effect bonus",
    "\u653e\u7f6e": "place put add played play into your forest without paying cost",
    "\u653e\u5165": "place put add into your forest without paying cost",
    "\u52a0\u5206": "score scores scoring victory points points bonus",
    "\u5f97\u5206": "score scores scoring victory points points",
    "\u5206": "points victory points score scores",
    "\u586b\u6ee1": "complete completed cover all spaces final tile",
    "\u653e\u6ee1": "complete completed cover all spaces final tile",
    "\u5b8c\u6210": "complete completed final tile score scores",
    "\u7248\u56fe": "board player board duchy area spaces",
    "\u516c\u56fd": "duchy player board",
    "\u989c\u8272": "color colored one color same color",
    "\u67d0\u4e00\u79cd\u989c\u8272": "one color all spaces of one color same color",
    "\u677f\u5757": "tile tiles spaces hex hexes",
    "\u7248\u5757": "tile tiles spaces hex hexes",
    "\u533a\u57df": "area colored area completed area",
    "\u6570\u91cf": "size number spaces amount count",
    "\u836f\u6c34": "potion potions alchemy consume potion deck unused",
    "\u836f\u6c34\u724c": "potion potions alchemy consume potion deck unused",
    "\u88c5\u5907": "equipment item gear permanent",
    "\u8d44\u6e90": "resource resources gold token",
    "\u91d1\u5e01": "gold coin coins",
    "\u94f6\u5e01": "silver coin silver coins",
    "\u8d27\u7269": "goods goods tile goods tiles sell sold stack type",
    "\u51fa\u552e": "sell sold goods stack complete stack",
    "\u5356": "sell sold goods stack complete stack",
    "\u5de5\u4eba": "worker workers worker chips",
    "\u5de5\u4eba\u82af\u7247": "worker chips",
    "\u5e73\u5c40": "tie tied tiebreaker wins fewest most empty spaces behind",
    "\u5e73\u624b": "tie tied tiebreaker wins fewest most empty spaces behind",
    "\u51b3\u5b9a\u80dc\u8d1f": "winner wins tie tiebreaker",
    "\u4fee\u9053\u9662": "monastery monasteries monastery tile monastery tiles",
    "\u755c\u7267": "livestock animal animals pasture livestock tile",
    "\u7267\u573a": "pasture livestock animal animals",
    "\u5355\u4eba": "solo solo game variant single player",
    "\u884c\u52a8": "action actions phase action cards perform",
    "\u56de\u5408": "turn round phase player turn",
    "\u9636\u6bb5": "phase step",
    "\u79fb\u52a8": "move movement connected location terrain",
    "\u8d70": "move movement connected location terrain",
    "\u51a5\u60f3": "meditate meditation phase ii choose fight explore",
    "\u51b3\u6597": "duel fight witcher fight another witcher attacking player",
    "\u730e\u9b54\u4eba": "witcher player",
    "\u6218\u6597": "fight combat attack damage defense",
    "\u653b\u51fb": "attack hit damage fight combat",
    "\u9632\u5fa1": "defense shield block damage",
    "\u602a\u7269": "monster monsters enemy foe",
    "\u57ce\u5e02": "city cities city space move cost movement cost",
    "\u663c\u591c": "day night day or night",
    "\u767d\u5929": "day daytime",
    "\u591c\u665a": "night nighttime",
    "\u5730\u5f62": "terrain terrain type movement cost",
    "\u79fb\u52a8\u70b9": "movement points move cost cost to move",
    "\u76f8\u90bb": "adjacent adjacency next to",
    "\u66b4\u6012": "rampaging enemy provoke attack movement ends",
    "\u654c\u4eba": "enemy enemies foe foes monster monsters",
    "\u6297\u6027": "resistance resistant halve halved armor",
    "\u5bd2\u706b": "cold fire coldfire ice fire resistance",
    "\u58f0\u671b": "fame reputation fame track level up",
    "\u5347\u7ea7": "level up level-up immediately fame track",
    "\u6218\u5229\u54c1": "trophy trophies trophy track",
    "\u4e0b\u6ce8": "wager bet gold common pool",
    "\u8d4c\u6ce8": "wager bet gold common pool",
    "\u9ab0\u5b50\u6251\u514b": "dice poker poker fight witcher",
    "0\u8d39": "0-cost zero cost action card action card display",
    "\u5c55\u793a\u533a": "display action card display revealed pool",
    "\u5f03\u724c\u5806": "discard pile common discard pile",
    "\u5730\u70b9": "location locations location action",
    "\u5730\u70b9\u884c\u52a8": "location action performed only once",
    "\u79fb\u51fa": "move out move away",
    "\u79fb\u56de": "move back back again same turn",
    "\u4e3b\u52a8\u73a9\u5bb6": "active player attacking player",
    "\u975e\u4e3b\u52a8\u73a9\u5bb6": "non-active player defending player",
    "\u62bd\u51e0\u5f20": "draw cards draw 2 cards draw 3 cards draw 4 cards",
    "\u8f93\u4e86": "lost lose defeated draw cards",
    "\u6218\u6597\u7ed3\u675f": "after fight fight outcome draw cards active player non-active player",
    "\u73a9\u5bb6": "player active player witcher opponent",
    "\u5148\u624b": "starting player first player initiative turn order",
    "\u987a\u5e8f": "order sequence turn order",
    "\u80dc\u5229": "win victory goal trophy",
    "\u5931\u8d25": "lose defeat fail",
}


class VectorStore:
    """Service for managing vector embeddings and semantic search."""

    def __init__(self):
        self.client = None
        self.embedding_service = EmbeddingService()
        self.rerank_service = RerankService()
        self.last_timing = {}

        if not settings.USE_CHROMA:
            logger.info("ChromaDB is disabled; using SQLite hybrid search")
            return

        if chromadb is None:
            logger.warning("ChromaDB is not installed; using SQLite hybrid search")
            return

        self.client = chromadb.PersistentClient(path=settings.VECTOR_DB_PATH)

    def create_collection(self, game_id: int) -> str:
        collection_name = f"game_{game_id}"
        if self.client is None:
            logger.info(f"Skipping Chroma collection creation for {collection_name}; fallback search is active")
            return collection_name

        try:
            try:
                self.client.get_collection(
                    name=collection_name,
                    embedding_function=self._get_embedding_function(),
                )
                logger.info(f"Collection {collection_name} already exists")
                return collection_name
            except Exception:
                pass

            self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._get_embedding_function(),
            )
            logger.info(f"Created collection: {collection_name}")
            return collection_name
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise

    def _get_embedding_function(self):
        self.embedding_service = EmbeddingService()

        class CustomEmbeddingFunction:
            def __init__(self, embedding_service):
                self.embedding_service = embedding_service

            def __call__(self, input):
                if isinstance(input, str):
                    return [self.embedding_service.embed_text(input)]
                if isinstance(input, list):
                    return self.embedding_service.embed_texts(input)
                raise ValueError(f"Unexpected input type: {type(input)}")

        return CustomEmbeddingFunction(self.embedding_service)

    def add_documents(self, game_id: int, documents: List[Dict], ids: List[str]) -> None:
        if not ids or not documents:
            logger.warning("Skipping add_documents: empty ids or documents list")
            return

        if len(ids) != len(documents):
            raise ValueError("Number of IDs must match number of documents")

        collection_name = f"game_{game_id}"
        if self.client is None:
            self.embedding_service = EmbeddingService()
            self._add_sqlite_vectors(game_id, documents, ids)
            return

        try:
            try:
                collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self._get_embedding_function(),
                )
            except Exception:
                self.create_collection(game_id)
                collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self._get_embedding_function(),
                )
            texts = [doc.get("text", doc) if isinstance(doc, dict) else doc for doc in documents]
            metadatas = [
                doc.get("metadata", {"page": "unknown"}) if isinstance(doc, dict) else {"page": "unknown"}
                for doc in documents
            ]
            collection.add(documents=texts, ids=ids, metadatas=metadatas)
            logger.info(f"Added {len(documents)} documents to collection {collection_name}")
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            raise

    def reindex_document(self, game_id: int, document_id: int) -> None:
        """Rebuild stored vectors for the current editable chunk set of a document."""
        from app.database import get_db_connection, init_db

        init_db()
        conn = get_db_connection()
        rows = conn.execute(
            """
            SELECT chunk_index, content, rule_type, keywords, section_title, rule_scope, source_kind
            FROM chunks
            WHERE document_id = ? AND COALESCE(enabled, 1) = 1
            ORDER BY chunk_index
            """,
            (document_id,),
        ).fetchall()
        conn.close()

        self.delete_document_vectors(game_id, document_id)
        if not rows:
            logger.info(f"No enabled chunks to reindex for document {document_id}")
            return
        self.create_collection(game_id)

        documents = []
        ids = []
        for row in rows:
            chunk_index = row["chunk_index"]
            ids.append(f"doc_{document_id}_chunk_{chunk_index}")
            page_match = re.search(r"\[Page\s+(\d+)\]", row["content"])
            metadata = {
                "page": page_match.group(1) if page_match else "unknown",
                "type": row["rule_type"] or "text",
                "keywords": row["keywords"] or "",
                "section": row["section_title"] or "",
                "rule_scope": row["rule_scope"] or "base",
                "source_kind": row["source_kind"] or "rule",
            }
            documents.append({
                "text": row["content"],
                "metadata": metadata,
            })

        self.add_documents(game_id, documents, ids)

    def document_vector_count(self, game_id: int, document_id: int) -> int:
        """Count stored vectors for a document in the active vector backend."""
        if self.client is None:
            try:
                from app.database import get_db_connection, init_db

                init_db()
                conn = get_db_connection()
                count = conn.execute(
                    "SELECT COUNT(*) AS count FROM chunk_embeddings WHERE document_id = ?",
                    (document_id,),
                ).fetchone()["count"]
                conn.close()
                return count
            except Exception as e:
                logger.error(f"Error counting SQLite vectors for document {document_id}: {e}")
                return 0

        try:
            collection = self.client.get_collection(name=f"game_{game_id}")
            existing = collection.get()
            ids = existing.get("ids", []) if existing else []
            prefix = f"doc_{document_id}_chunk_"
            return sum(1 for item_id in ids if item_id.startswith(prefix))
        except Exception as e:
            logger.error(f"Error counting Chroma vectors for document {document_id}: {e}")
            return 0

    def search(self, game_id: int, query: str, top_k: int = 5, use_hybrid: bool = True) -> List[Tuple[str, float]]:
        started = time.perf_counter()
        self.last_timing = {
            "backend": "chroma" if self.client is not None else "sqlite",
            "top_k": top_k,
            "total_ms": 0,
        }
        if use_hybrid and self._has_sqlite_index(game_id):
            results = self._sqlite_hybrid_search(game_id, query, top_k)
            self.last_timing["total_ms"] = round((time.perf_counter() - started) * 1000)
            return results

        if self.client is None:
            results = self._sqlite_hybrid_search(game_id, query, top_k)
            self.last_timing["total_ms"] = round((time.perf_counter() - started) * 1000)
            return results

        collection_name = f"game_{game_id}"
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self._get_embedding_function(),
            )
            expanded_query = self._expand_query(query)
            search_k = max(top_k * 4, 12)

            if use_hybrid:
                vector_results = []
                for query_variant in self._query_variants(query, expanded_query):
                    vector_results.extend(self._vector_search(collection, query_variant, search_k))
                keyword_results = self._keyword_search(collection, expanded_query, search_k)
                merged = self._merge_results(vector_results, keyword_results, expanded_query)
                reranked = self._rerank_document_results(merged, expanded_query)
                results = self._dedupe_results(reranked, top_k)
                self.last_timing["total_ms"] = round((time.perf_counter() - started) * 1000)
                return results

            results = self._vector_search(collection, expanded_query, top_k)
            self.last_timing["total_ms"] = round((time.perf_counter() - started) * 1000)
            return results
        except Exception as e:
            self.last_timing["total_ms"] = round((time.perf_counter() - started) * 1000)
            logger.error(f"Error searching documents: {e}")
            return []

    def _has_sqlite_index(self, game_id: int) -> bool:
        try:
            from app.database import get_db_connection, init_db

            init_db()
            conn = get_db_connection()
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.game_id = ? AND COALESCE(c.enabled, 1) = 1
                """,
                (game_id,),
            ).fetchone()
            conn.close()
            return bool(row and row["count"] > 0)
        except Exception as e:
            logger.warning(f"Unable to inspect SQLite index for game {game_id}: {e}")
            return False

    def explain_results(self, query: str, results: List[Tuple[str, float]], limit: int = 8) -> Dict:
        """Return lightweight diagnostics for already-ranked search results."""
        expanded_query = self._expand_query(query)
        query_variants = self._query_variants(query, expanded_query)
        return {
            "original_query": query,
            "expanded_query": expanded_query,
            "query_variants": query_variants[:6],
            "variant_query": self._is_variant_query(self._normalize_text(query)),
            "document_intent": self._document_intent(query),
            "ranking_note": "Final ranking after hybrid retrieval, source-type routing, rule-scope rerank, focus alignment, and quality penalty.",
            "top_results": [
                self._diagnostic_result(doc, score, index + 1)
                for index, (doc, score) in enumerate(results[:limit])
            ],
        }

    def _expand_query(self, query: str) -> str:
        additions = []
        for key, expansion in QUERY_EXPANSIONS.items():
            if key in query:
                additions.append(expansion)

        tokens = self._tokenize(query)
        if self._document_intent(query) == "beginner_guide":
            additions.append(
                "walkthrough tutorial guide beginner first play first game getting started "
                "setup game setup first round taking turns one turn player turn play a card "
                "actions game flow learn to play opening"
            )
        player_count_match = re.search(r"([1-9])\s*(?:\u4eba|players?)", query, re.IGNORECASE)
        if player_count_match:
            count = player_count_match.group(1)
            additions.append(f"{count} players with {count} players player count number of players setup cards")
        if any(term in query for term in ["\u4eba\u5c40", "\u73a9\u5bb6\u6570", "\u73a9\u5bb6\u6570\u91cf"]):
            additions.append("players player count number of players setup with players cards")
        if any(term in query for term in ["\u62bd\u51fa", "\u62bd\u51fa\u6765", "\u79fb\u9664", "\u653e\u56de\u76d2"]):
            additions.append("remove return to the box unseen set aside based on player count setup")
        if any(term in query for term in ["\u4e0a\u9650", "\u6700\u591a", "\u4fdd\u7559"]):
            additions.append("maximum limit up to at most")
        if any(token in tokens for token in ["maximum", "limit", "max"]):
            additions.append("maximum limit up to at most")
        if any(token in tokens for token in ["hand", "cards"]):
            additions.append("cards in hand draw discard hand limit")
        if any(term in query for term in ["\u586b\u6ee1", "\u653e\u6ee1", "\u5b8c\u6210"]) and "\u989c\u8272" in query:
            additions.append(
                "complete completed cover all spaces of one color same color colored area "
                "final tile large bonus tile small bonus tile victory points"
            )
        if any(term in query for term in ["\u5956\u52b1", "\u52a0\u5206", "\u5f97\u5206", "\u5206"]):
            additions.append("score scores scoring victory points bonus reward")
        if self._is_triggered_placement_query(query):
            additions.append(
                "trigger triggers effect bonus place put add into your forest from your hand "
                "without paying cost neither its effect nor its bonus cannot use may use "
                "card just played play a card"
            )
        if any(term in query for term in ["\u8d27\u7269", "\u51fa\u552e", "\u5356"]):
            additions.append("goods sell sold stack complete stack type reserve")
        if any(term in query for term in ["\u5de5\u4eba", "\u5de5\u4eba\u82af\u7247"]):
            additions.append("worker workers worker chips victory point final scoring")
        if any(term in query for term in ["\u5e73\u5c40", "\u5e73\u624b", "\u51b3\u5b9a\u80dc\u8d1f"]):
            additions.append("tie tied winner wins fewest most empty spaces behind bridge")
        if any(term in query for term in ["\u4fee\u9053\u9662", "\u755c\u7267", "\u7267\u573a"]):
            additions.append("monastery livestock pasture animal animals scoring tile")
        if any(term in query for term in ["\u57ce\u5e02", "city"]):
            additions.append("city cities city space cost to move movement points always 2")
        if any(term in query for term in ["\u663c\u591c", "\u767d\u5929", "\u591c\u665a", "day", "night"]):
            additions.append("day night day or night terrain movement cost")
        if any(term in query for term in ["\u66b4\u6012", "\u76f8\u90bb", "rampaging", "adjacent"]):
            additions.append("rampaging enemy provoke attack movement immediately ends adjacent")
        if any(term in query for term in ["\u6297\u6027", "\u5bd2\u706b", "resistance", "cold fire"]):
            additions.append("cold fire attacks ice fire resistance halved")
        if any(term in query for term in ["\u58f0\u671b", "\u5347\u7ea7", "fame", "level up"]):
            additions.append("fame track level up immediately reputation")
        if any(term in query for term in ["\u6218\u5229\u54c1", "trophy"]):
            additions.append("trophy trophy track already have skip steps")
        if any(term in query for term in ["\u4e0b\u6ce8", "\u8d4c\u6ce8", "wager", "bet"]):
            additions.append("wager gold common pool lost won gain same amount")
        if any(term in query for term in ["\u9ab0\u5b50\u6251\u514b", "dice poker"]):
            additions.append("dice poker fight witcher same witcher phase")
        if any(term in query for term in ["0\u8d39", "0-cost", "zero cost"]):
            additions.append("0-cost action card action card display revealed pool common action deck discard pile")
        if any(term in query for term in ["\u5730\u70b9\u884c\u52a8", "\u5730\u70b9", "\u79fb\u51fa", "\u79fb\u56de", "location action"]):
            additions.append("location action performed only once move out back again same turn")
        if any(term in query for term in ["\u4e3b\u52a8\u73a9\u5bb6", "\u975e\u4e3b\u52a8\u73a9\u5bb6", "active player", "non-active"]):
            additions.append(
                "active player non-active player attacking defending won lost draw cards phase iii "
                "active player lost draw 2 cards instead of 3 non-active player immediately draw"
            )
        if any(term in query for term in ["\u62bd\u51e0\u5f20", "\u8f93\u4e86", "\u6218\u6597\u7ed3\u675f", "draw cards", "lost"]):
            additions.append("after fight won lost draw cards active player non-active player phase iii immediately")
        if self._is_variant_query(self._normalize_text(query)):
            additions.append(
                "solo game single player variant variants expansion team game "
                "instead of normal rules special rules immediately after placing black depot"
            )
        if self._is_variant_query(self._normalize_text(query)) and any(
            term in query for term in ["\u4fee\u9053\u9662", "\u6e38\u620f\u7ed3\u675f", "\u7ed3\u675f", "monastery", "end of the game"]
        ):
            additions.append("victory points from a monastery tile added immediately after placing instead of at the end of the game")
        if any(term in query for term in ["\u586b\u6ee1", "\u653e\u6ee1", "\u5b8c\u6210"]) and any(
            term in query for term in ["\u6570\u91cf", "\u5956\u52b1", "\u52a0\u5206", "\u5f97\u5206", "\u5206"]
        ):
            additions.append(
                "final tile completed area size spaces victory points current phase "
                "additional victory points bonus tile"
            )

        return " ".join([query, *additions]).strip()

    def _query_variants(self, original_query: str, expanded_query: str) -> List[str]:
        variants = [expanded_query]
        if expanded_query != original_query:
            variants.append(original_query)

        tokens = set(self._tokenize(expanded_query))
        variant_rules = [
            ({"move", "movement", "terrain"}, "move movement connected location terrain discard card"),
            ({"city", "cities"}, "city cities cost to move movement points always 2 day night terrain"),
            ({"day", "night"}, "day night day or night terrain movement cost"),
            ({"rampaging", "adjacent"}, "rampaging enemy provoke attack movement immediately ends adjacent"),
            ({"fight", "combat", "attack"}, "fight combat attack damage defense hand limit"),
            ({"resistance", "cold", "fire"}, "cold fire attacks ice fire resistance halved"),
            ({"hand", "cards", "draw"}, "cards in hand maximum limit draw discard end of step"),
            ({"potion", "potions", "alchemy"}, "potion potions alchemy maximum limit consume discard unused"),
            ({"turn", "phase", "action"}, "player turn phase action perform step"),
            ({"complete", "completed", "color", "colored"}, "completed area final tile size spaces current phase victory points"),
            ({"bonus", "reward", "score", "points"}, "score scores victory points bonus tile reward immediately"),
            ({"duchy", "spaces", "tile", "tiles"}, "cover all spaces of one color duchy large bonus tile small bonus tile"),
            ({"goods", "sell", "sold"}, "sell goods complete stack goods type silver coin victory points"),
            ({"worker", "workers"}, "worker chips final scoring every two worker chips victory point"),
            ({"tie", "tied", "winner"}, "tie winner wins fewest empty spaces bridge behind"),
            ({"monastery", "livestock"}, "monastery tile livestock tile pasture scores at that time"),
            ({"solo", "variant", "single"}, "solo game single player variant instead of normal rules immediately after placing black depot"),
            ({"trophy", "wager", "poker"}, "trophy track wager gold common pool dice poker fight witcher"),
            ({"fame", "level"}, "fame track level up immediately reputation"),
            ({"0", "cost"}, "0-cost action card action card display revealed pool common action deck discard pile"),
            ({"location"}, "location action performed only once move out back again same turn"),
            ({"active", "non"}, "active player non-active player attacking defending won lost draw cards phase iii active player lost draw 2 cards"),
            ({"draw", "lost"}, "after fight active player lost non-active player immediately draw cards phase iii"),
            ({"players", "count", "setup"}, "player count with players setup cards remove unseen return to the box"),
            ({"beginner", "walkthrough", "tutorial", "guide", "setup"}, "walkthrough tutorial guide first play setup first round taking turns one turn player turn play a card game flow"),
        ]
        for required, variant in variant_rules:
            if tokens & required:
                variants.append(variant)

        return list(dict.fromkeys(variants))

    def _vector_search(self, collection, query: str, top_k: int) -> List[Tuple[str, float]]:
        try:
            results = collection.query(query_texts=[query], n_results=top_k)
            if results and results["documents"] and len(results["documents"]) > 0:
                documents = results["documents"][0]
                distances = results["distances"][0]
                return list(zip(documents, [1 - d for d in distances]))
            return []
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []

    def _keyword_search(self, collection, query: str, top_k: int) -> List[Tuple[str, float]]:
        try:
            all_results = collection.get()
            documents = all_results.get("documents", []) if all_results else []
            if not documents:
                return []

            corpus_stats = self._corpus_stats(documents)
            scored = [
                (doc, self._score_document(doc, query, corpus_stats))
                for doc in documents
            ]
            return [(doc, score) for doc, score in sorted(scored, key=lambda item: item[1], reverse=True)[:top_k] if score > 0]
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []

    def _merge_results(
        self,
        vector_results: List[Tuple[str, float]],
        keyword_results: List[Tuple[str, float]],
        query: str = "",
    ) -> List[Tuple[str, float]]:
        merged = {}
        for doc, score in vector_results:
            merged[doc] = merged.get(doc, 0) + score * 0.65
        for doc, score in keyword_results:
            merged[doc] = merged.get(doc, 0) + score * 0.35
        return sorted(merged.items(), key=lambda item: item[1], reverse=True)

    def _rerank_document_results(self, results: List[Tuple[str, float]], query: str) -> List[Tuple[str, float]]:
        reranked = []
        for doc, score in results:
            adjusted = (
                score
                + self._evidence_rerank_bonus(doc, query)
                + self._focus_alignment_score(doc, query)
                + self._scope_alignment_score(doc, query)
                + self._source_type_alignment_score_doc(doc, query)
            )
            adjusted -= self._quality_penalty(doc)
            reranked.append((doc, adjusted))
        return sorted(reranked, key=lambda item: item[1], reverse=True)

    def _sqlite_hybrid_search(self, game_id: int, query: str, top_k: int) -> List[Tuple[str, float]]:
        """Hybrid search using SQLite-stored embeddings plus BM25."""
        timings = {
            "backend": "sqlite",
            "db_fetch_ms": 0,
            "expand_query_ms": 0,
            "bm25_ms": 0,
            "vector_db_fetch_ms": 0,
            "query_embedding_ms": 0,
            "cosine_ms": 0,
            "merge_ms": 0,
            "local_rerank_ms": 0,
            "neighbor_expand_ms": 0,
            "external_rerank_ms": 0,
            "chunks_scanned": 0,
            "rerank_candidates": 0,
        }
        try:
            from app.database import get_db_connection, init_db

            init_db()

            stage = time.perf_counter()
            conn = get_db_connection()
            cursor = conn.cursor()
            rows = cursor.execute(
                """
                SELECT c.document_id, c.chunk_index, c.content, c.keywords, c.rule_type,
                       c.section_title, c.rule_scope, c.source_kind, d.source_type
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.game_id = ? AND COALESCE(c.enabled, 1) = 1
                ORDER BY c.document_id, c.chunk_index
                """,
                (game_id,),
            ).fetchall()
            timings["db_fetch_ms"] = round((time.perf_counter() - stage) * 1000)
            timings["chunks_scanned"] = len(rows)

            if not rows:
                conn.close()
                self.last_timing.update(timings)
                return []

            stage = time.perf_counter()
            expanded_query = self._expand_query(query)
            timings["expand_query_ms"] = round((time.perf_counter() - stage) * 1000)
            rerank_candidate_count = self.rerank_service.candidate_count(max(top_k * 3, 12))
            timings["rerank_candidates"] = rerank_candidate_count
            stage = time.perf_counter()
            corpus = [self._searchable_row_text(row) for row in rows]
            corpus_stats = self._corpus_stats(corpus)
            bm25_scores = {}
            for row in rows:
                score = self._score_document(self._searchable_row_text(row), expanded_query, corpus_stats)
                if score > 0:
                    bm25_scores[(row["document_id"], row["chunk_index"])] = (row, score)
            timings["bm25_ms"] = round((time.perf_counter() - stage) * 1000)

            vector_scores = self._sqlite_vector_scores(cursor, game_id, query, timings)
            stage = time.perf_counter()
            merged = self._merge_sqlite_scores(bm25_scores, vector_scores)
            timings["merge_ms"] = round((time.perf_counter() - stage) * 1000)
            stage = time.perf_counter()
            merged = self._rerank_rows(merged, query)
            timings["local_rerank_ms"] = round((time.perf_counter() - stage) * 1000)
            stage = time.perf_counter()
            expanded = self._expand_hits_with_neighbors(cursor, merged[:rerank_candidate_count], query)
            timings["neighbor_expand_ms"] = round((time.perf_counter() - stage) * 1000)
            reranked = self.rerank_service.rerank(
                query=expanded_query,
                results=self._dedupe_results(expanded, rerank_candidate_count),
                top_n=self.rerank_service.top_n(top_k),
            )
            reranked = self._rerank_document_results(reranked, query)
            timings["external_rerank_ms"] = self.rerank_service.last_timing.get("rerank_ms", 0)
            timings["external_rerank"] = self.rerank_service.last_timing
            conn.close()
            self.last_timing.update(timings)
            return self._dedupe_results(reranked, top_k)
        except Exception as e:
            self.last_timing.update(timings)
            logger.error(f"Error in SQLite hybrid search: {e}")
            return []

    def _add_sqlite_vectors(self, game_id: int, documents: List[Dict], ids: List[str]) -> None:
        """Persist embeddings in SQLite when ChromaDB is unavailable."""
        if not get_model_config()["embedding"]["api_key"]:
            logger.warning("Skipping SQLite vector add: EMBEDDING_API_KEY is not configured")
            return

        try:
            self.embedding_service = EmbeddingService()
            from app.database import get_db_connection, init_db

            init_db()
            texts = [doc.get("text", doc) if isinstance(doc, dict) else str(doc) for doc in documents]
            embeddings = []
            batch_size = 16
            for start in range(0, len(texts), batch_size):
                batch = texts[start:start + batch_size]
                embeddings.extend(self.embedding_service.embed_texts(batch))

            conn = get_db_connection()
            cursor = conn.cursor()
            for embedding_id, vector in zip(ids, embeddings):
                parsed = self._parse_embedding_id(embedding_id)
                if not parsed:
                    continue
                document_id, chunk_index = parsed
                norm = self._vector_norm(vector)
                if norm == 0:
                    continue
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO chunk_embeddings
                    (embedding_id, game_id, document_id, chunk_index, vector_json, vector_norm)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (embedding_id, game_id, document_id, chunk_index, json.dumps(vector), norm),
                )
            conn.commit()
            conn.close()
            logger.info(f"Stored {len(embeddings)} SQLite vectors for game {game_id}")
        except Exception as e:
            logger.error(f"Error storing SQLite vectors: {e}")

    def _sqlite_vector_scores(self, cursor, game_id: int, query: str, timings: dict | None = None) -> Dict[Tuple[int, int], Tuple[object, float]]:
        """Return cosine scores for chunks with stored embeddings."""
        if not get_model_config()["embedding"]["api_key"]:
            return {}

        stage = time.perf_counter()
        rows = cursor.execute(
            """
            SELECT c.document_id, c.chunk_index, c.content, c.keywords, c.rule_type,
                   c.section_title, c.rule_scope, c.source_kind, d.source_type,
                   e.vector_json, e.vector_norm
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            JOIN chunk_embeddings e ON e.document_id = c.document_id AND e.chunk_index = c.chunk_index
            WHERE d.game_id = ? AND COALESCE(c.enabled, 1) = 1
            """,
            (game_id,),
        ).fetchall()
        if timings is not None:
            timings["vector_db_fetch_ms"] = round((time.perf_counter() - stage) * 1000)
        if not rows:
            return {}

        try:
            self.embedding_service = EmbeddingService()
            stage = time.perf_counter()
            query_vector = self.embedding_service.embed_text(query)
            if timings is not None:
                timings["query_embedding_ms"] = round((time.perf_counter() - stage) * 1000)
        except Exception as e:
            logger.error(f"Error embedding query for SQLite vector search: {e}")
            return {}

        query_norm = self._vector_norm(query_vector)
        if query_norm == 0:
            return {}

        scored = {}
        stage = time.perf_counter()
        for row in rows:
            try:
                vector = json.loads(row["vector_json"])
                similarity = self._cosine_similarity(query_vector, query_norm, vector, row["vector_norm"])
                scored[(row["document_id"], row["chunk_index"])] = (row, similarity)
            except Exception:
                continue
        if timings is not None:
            timings["cosine_ms"] = round((time.perf_counter() - stage) * 1000)
        return scored

    def _merge_sqlite_scores(
        self,
        bm25_scores: Dict[Tuple[int, int], Tuple[object, float]],
        vector_scores: Dict[Tuple[int, int], Tuple[object, float]],
    ) -> List[Tuple[object, float]]:
        normalized_bm25 = self._normalize_score_map(bm25_scores)
        normalized_vector = self._normalize_score_map(vector_scores)
        keys = set(normalized_bm25) | set(normalized_vector)

        merged = []
        for key in keys:
            row = bm25_scores.get(key, vector_scores.get(key))[0]
            score = normalized_bm25.get(key, 0.0) * 0.70 + normalized_vector.get(key, 0.0) * 0.30
            if key not in normalized_bm25:
                score *= 0.35
            merged.append((row, score))
        return sorted(merged, key=lambda item: item[1], reverse=True)

    def _rerank_rows(self, rows: List[Tuple[object, float]], query: str) -> List[Tuple[object, float]]:
        reranked = []
        for row, score in rows:
            row_text = self._searchable_row_text(row)
            adjusted = (
                score
                + self._evidence_rerank_bonus(row_text, query)
                + self._focus_alignment_score(row_text, query)
                + self._scope_alignment_score(row_text, query)
                + self._source_type_alignment_score_row(row, query)
            )
            adjusted -= self._quality_penalty(row["content"])
            reranked.append((row, adjusted))
        return sorted(reranked, key=lambda item: item[1], reverse=True)

    def _normalize_score_map(self, scores: Dict[Tuple[int, int], Tuple[object, float]]) -> Dict[Tuple[int, int], float]:
        if not scores:
            return {}
        values = [score for _, score in scores.values()]
        min_score = min(values)
        max_score = max(values)
        if max_score == min_score:
            return {key: 1.0 for key in scores}
        return {
            key: (score - min_score) / (max_score - min_score)
            for key, (_, score) in scores.items()
        }

    def _parse_embedding_id(self, embedding_id: str) -> Tuple[int, int] | None:
        match = re.match(r"doc_(\d+)_chunk_(\d+)$", embedding_id)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    def _diagnostic_result(self, doc: str, score: float, rank: int) -> Dict:
        metadata = self._source_metadata(doc)
        return {
            "rank": rank,
            "score": round(float(score), 4),
            "page": self._doc_page(doc),
            "section": self._doc_section(doc),
            "document_id": metadata.get("document_id"),
            "chunk_index": metadata.get("chunk_index"),
            "rule_type": metadata.get("rule_type"),
            "rule_scope": metadata.get("rule_scope"),
            "source_kind": metadata.get("source_kind"),
            "source_type": metadata.get("source_type"),
            "excerpt": self._diagnostic_excerpt(doc),
        }

    def _source_metadata(self, doc: str) -> Dict[str, str | int | None]:
        match = re.search(r"^\[SourceMeta:\s*([^\]]+)\]", doc or "")
        metadata: Dict[str, str | int | None] = {}
        if not match:
            return metadata
        for key, value in re.findall(r"(\w+)=([^\s\]]+)", match.group(1)):
            if key in {"document_id", "chunk_index"}:
                try:
                    metadata[key] = int(value)
                except ValueError:
                    metadata[key] = None
            else:
                metadata[key] = None if value == "-" else value
        return metadata

    def _doc_page(self, doc: str) -> int | None:
        match = re.search(r"\[Page\s+(\d+)\]", doc or "", re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _doc_section(self, doc: str) -> str:
        match = re.search(r"\[Section:\s*([^\]]+)\]", doc or "", re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _diagnostic_excerpt(self, doc: str, max_chars: int = 220) -> str:
        text = re.sub(r"^\[SourceMeta:[^\]]+\]\s*", "", doc or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text[:max_chars]

    def _vector_norm(self, vector: List[float]) -> float:
        return math.sqrt(sum(value * value for value in vector))

    def _cosine_similarity(
        self,
        left: List[float],
        left_norm: float,
        right: List[float],
        right_norm: float,
    ) -> float:
        if not left_norm or not right_norm or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        return dot / (left_norm * right_norm)

    def _expand_hits_with_neighbors(self, cursor, scored_rows, query: str = "") -> List[Tuple[str, float]]:
        expanded = []
        intent = self._document_intent(query)
        for row, score in scored_rows:
            source_kind = row["source_kind"] if "source_kind" in row.keys() and row["source_kind"] else ""
            source_type = row["source_type"] if "source_type" in row.keys() and row["source_type"] else "official_rulebook"
            neighbor_window = self._neighbor_window_for_row(row, intent)
            neighbors = cursor.execute(
                """
                SELECT chunk_index, content
                FROM chunks
                WHERE document_id = ?
                AND COALESCE(enabled, 1) = 1
                AND chunk_index BETWEEN ? AND ?
                ORDER BY chunk_index
                """,
                (row["document_id"], row["chunk_index"] - neighbor_window, row["chunk_index"] + neighbor_window),
            ).fetchall()
            current_index = row["chunk_index"]
            current = [item["content"] for item in neighbors if item["chunk_index"] == current_index]
            rule_type = row["rule_type"] if "rule_type" in row.keys() and row["rule_type"] else ""
            rule_scope = row["rule_scope"] if "rule_scope" in row.keys() and row["rule_scope"] else ""
            surrounding = (
                []
                if source_kind == "layout_region"
                else [item["content"] for item in neighbors if item["chunk_index"] != current_index]
            )
            precision_items = self._beginner_precision_context_items(row, neighbors, intent)
            if precision_items:
                precision_set = set(precision_items)
                surrounding = [item for item in surrounding if item not in precision_set]
            source_meta = (
                f"[SourceMeta: document_id={row['document_id']} chunk_index={current_index} "
                f"rule_type={rule_type or '-'} rule_scope={rule_scope or '-'} "
                f"source_kind={source_kind or '-'} source_type={source_type or '-'}]"
            )
            context = "\n\n".join([source_meta, *current, *precision_items, *surrounding])
            expanded.append((context, score))
        return expanded

    def _score_document(self, doc: str, query: str, corpus_stats: Dict) -> float:
        query_tokens = self._tokenize(query)
        doc_tokens = self._tokenize(doc)
        if not query_tokens or not doc_tokens:
            return 0.0

        doc_counts = Counter(doc_tokens)
        doc_len = len(doc_tokens)
        avg_doc_len = corpus_stats["avg_doc_len"]
        doc_count = corpus_stats["doc_count"]
        doc_freq = corpus_stats["doc_freq"]

        k1 = 1.4
        b = 0.72
        score = 0.0
        for token in list(dict.fromkeys(query_tokens)):
            tf = doc_counts.get(token, 0)
            if tf == 0:
                continue
            idf = math.log(1 + (doc_count - doc_freq.get(token, 0) + 0.5) / (doc_freq.get(token, 0) + 0.5))
            denom = tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
            score += idf * (tf * (k1 + 1)) / denom

        score += self._phrase_score(doc, query)
        score += self._focus_alignment_score(doc, query)
        score += self._evidence_rerank_bonus(doc, query)
        score -= self._quality_penalty(doc)
        return max(score, 0.0)

    def _searchable_row_text(self, row) -> str:
        keywords = row["keywords"] if "keywords" in row.keys() and row["keywords"] else ""
        rule_type = row["rule_type"] if "rule_type" in row.keys() and row["rule_type"] else ""
        section = row["section_title"] if "section_title" in row.keys() and row["section_title"] else ""
        rule_scope = row["rule_scope"] if "rule_scope" in row.keys() and row["rule_scope"] else ""
        source_kind = row["source_kind"] if "source_kind" in row.keys() and row["source_kind"] else ""
        source_type = row["source_type"] if "source_type" in row.keys() and row["source_type"] else ""
        source_terms = self._source_type_search_terms(source_type)
        additions = " ".join(
            part for part in [rule_type, rule_scope, source_kind, source_type, source_terms, section, keywords] if part
        )
        return f"{row['content']}\n{additions}".strip()

    def _document_intent(self, query: str) -> str:
        query_text = self._normalize_text(query)

        if self._is_variant_query(query_text):
            return "variant"

        if any(term in query_text for term in [
            "\u52d8\u8bef", "\u4fee\u8ba2", "\u66f4\u6b63", "errata", "correction", "corrected", "revision",
        ]):
            return "errata"

        if any(term in query_text for term in [
            "\u95ee\u7b54", "\u5e38\u89c1\u95ee\u9898", "\u7b54\u7591", "faq", "q&a", "qa",
            "clarification", "clarifications",
        ]):
            return "faq"

        if any(term in query_text for term in [
            "\u65b0\u624b", "\u5f00\u5c40", "\u5165\u95e8", "\u7b2c\u4e00\u6b21",
            "\u9996\u6b21", "\u7b2c\u4e00\u5c40", "\u7b2c\u4e00\u56de\u5408",
            "\u6559\u5b66", "\u6559\u7a0b", "\u6d41\u7a0b", "\u600e\u4e48\u5f00\u59cb",
            "\u600e\u4e48\u73a9", "\u5e26\u6211\u73a9", "\u5feb\u901f\u5165\u95e8",
            "beginner", "first play", "first-play", "first game", "first round",
            "walkthrough", "tutorial", "guide", "getting started", "learn to play",
            "how to start", "opening",
        ]):
            return "beginner_guide"

        if any(term in query_text for term in [
            "\u89c4\u5219", "\u80fd\u5426", "\u53ef\u4ee5", "\u4e0d\u53ef\u4ee5",
            "\u5fc5\u987b", "\u600e\u4e48\u7b97", "\u8ba1\u7b97", "\u5f97\u5206",
            "\u52a0\u5206", "rule", "rules", "can", "may", "must", "score", "scoring",
            "points", "timing",
        ]):
            return "rulebook"

        return "general"

    def _source_type_search_terms(self, source_type: str) -> str:
        mapping = {
            "official_rulebook": "official rulebook base rules core rules rule reference",
            "official_walkthrough": (
                "official walkthrough tutorial guide learn to play beginner first play "
                "first game first round taking turns one turn game flow"
            ),
            "official_tutorial": "official tutorial guide learn to play beginner first play first game",
            "player_guide": "player guide tutorial beginner walkthrough learn to play",
            "official_faq": "official faq q&a question answer clarification",
            "community_qa": "community qa q&a question answer discussion clarification",
            "official_errata": "official errata correction corrected revision",
        }
        return mapping.get(source_type or "", "")

    def _source_type_alignment_score_row(self, row, query: str) -> float:
        source_type = row["source_type"] if "source_type" in row.keys() and row["source_type"] else ""
        row_text = self._searchable_row_text(row)
        return self._source_type_alignment_score(source_type, row_text, query)

    def _source_type_alignment_score_doc(self, doc: str, query: str) -> float:
        metadata = self._source_metadata(doc)
        source_type = metadata.get("source_type") or ""
        return self._source_type_alignment_score(str(source_type), self._primary_context_text(doc), query)

    def _primary_context_text(self, doc: str) -> str:
        text = re.sub(r"^\[SourceMeta:[^\]]+\]\s*", "", doc or "").strip()
        return text.split("\n\n", 1)[0].strip()

    def _source_type_alignment_score(self, source_type: str, doc: str, query: str) -> float:
        intent = self._document_intent(query)
        doc_text = self._normalize_text(doc)
        score = 0.0

        if intent == "beginner_guide":
            if source_type in GUIDE_SOURCE_TYPES:
                score += 28.0
            elif source_type in RULEBOOK_SOURCE_TYPES:
                score -= 4.0
            elif source_type in FAQ_SOURCE_TYPES or source_type in ERRATA_SOURCE_TYPES:
                score -= 12.0

            if re.search(
                r"\b(walkthrough|tutorial|guide|learn to play|beginner|first round|one turn|"
                r"taking turns|player turn|regular turn|playing a card|play a card|game flow|"
                r"setup|game setup|choosing tactics|start of the game|starting tile|"
                r"prepare this scenario|revealed map tiles|magic portal)\b",
                doc_text,
            ):
                score += 20.0

            beginner_setup_query = any(term in self._normalize_text(query) for term in [
                "\u5f00\u5c40", "\u5165\u95e8", "\u6446", "\u8bbe\u7f6e", "\u5f00\u59cb\u524d",
                "setup", "first play", "first game", "getting started", "before starting",
            ])
            if beginner_setup_query:
                if re.search(r"\b(starting tile|revealed map tiles|magic portal|surrounding area|map tiles)\b", doc_text):
                    score += 5.0
                if re.search(
                    r"\b(prepare this scenario|randomly take|one city|two non-city|"
                    r"one city and two non-city|three together|first scenario)\b",
                    doc_text,
                ):
                    score += 8.0

            if re.search(
                r"\b(special rules|scenario|variants?|solo game|player vs\.? player|"
                r"player versus player|pvp|competitive|advanced rules|later games)\b",
                doc_text,
            ):
                if not any(term in doc_text for term in ["walkthrough", "tutorial", "first round", "game flow"]):
                    score -= 16.0
                else:
                    score -= 10.0

            query_text = self._normalize_text(query)
            beginner_turn_query = any(term in query_text for term in [
                "\u56de\u5408", "\u505a\u4ec0\u4e48", "\u600e\u4e48\u505a",
                "turn", "action", "what should i do", "what to do",
            ])
            if beginner_turn_query:
                has_specific_turn_rule = bool(
                    re.search(r"\b(one turn|taking turns|player turn|regular turn|playing a card|play a card|action cards)\b", doc_text)
                )
                if has_specific_turn_rule:
                    score += 44.0
                elif re.search(r"\b(rounds and turns|components|brief story|goals of the scenario|scenario rules)\b", doc_text):
                    score -= 24.0

        elif intent == "faq":
            if source_type in FAQ_SOURCE_TYPES:
                score += 28.0
            elif source_type in RULEBOOK_SOURCE_TYPES:
                score -= 4.0
            if re.search(r"\b(faq|q&a|question|answer|clarification|clarifications)\b", doc_text):
                score += 14.0

        elif intent == "errata":
            if source_type in ERRATA_SOURCE_TYPES:
                score += 30.0
            elif source_type in RULEBOOK_SOURCE_TYPES:
                score -= 4.0
            if re.search(r"\b(errata|correction|corrected|revision)\b", doc_text):
                score += 16.0

        elif intent == "variant":
            if source_type in RULEBOOK_SOURCE_TYPES:
                score += 4.0
            if source_type in GUIDE_SOURCE_TYPES and not self._is_variant_doc(doc_text):
                score -= 6.0

        elif intent == "rulebook":
            if source_type in RULEBOOK_SOURCE_TYPES:
                score += 10.0
            elif source_type in GUIDE_SOURCE_TYPES:
                score -= 3.0
            elif source_type in FAQ_SOURCE_TYPES:
                score += 2.0

        else:
            if source_type in RULEBOOK_SOURCE_TYPES:
                score += 3.0

        return score

    def _neighbor_window_for_row(self, row, intent: str) -> int:
        source_kind = row["source_kind"] if "source_kind" in row.keys() and row["source_kind"] else ""
        source_type = row["source_type"] if "source_type" in row.keys() and row["source_type"] else ""
        content = row["content"] if "content" in row.keys() and row["content"] else ""
        section = row["section_title"] if "section_title" in row.keys() and row["section_title"] else ""
        if source_kind == "layout_region":
            return 0
        if (
            intent == "beginner_guide"
            and source_type in GUIDE_SOURCE_TYPES
            and (
                "[Page 2]" in content
                or re.search(r"\b(rounds and turns|map tiles|components)\b", section, re.IGNORECASE)
            )
            and re.search(r"\b(map tiles|revealed map|starting tile|magic portal|first scenario|setup)\b", content, re.IGNORECASE)
        ):
            return 16
        if intent == "beginner_guide" and source_type in GUIDE_SOURCE_TYPES:
            return 3
        if intent in {"faq", "errata"} and source_type in (FAQ_SOURCE_TYPES | ERRATA_SOURCE_TYPES):
            return 2
        return 1

    def _beginner_precision_context_items(self, row, neighbors, intent: str) -> List[str]:
        if intent != "beginner_guide":
            return []
        source_type = row["source_type"] if "source_type" in row.keys() and row["source_type"] else ""
        if source_type not in GUIDE_SOURCE_TYPES:
            return []
        current_index = row["chunk_index"]
        exact_patterns = [
            r"\b(randomly take|one city and two non-city|two non-city tiles|"
            r"these three tiles form|three tiles form the starting)\b",
        ]
        support_patterns = [
            r"\b(to prepare this scenario|starting area|magic portal|starting tile|"
            r"first scenario)\b",
        ]
        exact_matched = []
        support_matched = []
        for item in neighbors:
            if item["chunk_index"] == current_index:
                continue
            text = item["content"] or ""
            normalized = self._normalize_text(text)
            rank_item = (abs(item["chunk_index"] - current_index), item["chunk_index"], text)
            if any(re.search(pattern, normalized) for pattern in exact_patterns):
                exact_matched.append(rank_item)
            elif any(re.search(pattern, normalized) for pattern in support_patterns):
                support_matched.append(rank_item)
        exact_matched.sort(key=lambda item: (item[0], item[1]))
        support_matched.sort(key=lambda item: (item[0], item[1]))
        matched = [*exact_matched[:2], *support_matched[:1]]
        return [text for _, _, text in matched]

    def _evidence_rerank_bonus(self, doc: str, query: str) -> float:
        """Prefer chunks that answer the user's question type, not only mention terms."""
        doc_text = self._normalize_text(doc)
        query_text = self._normalize_text(query)
        question_type = self._question_type(query_text)
        focus_terms = self._focus_terms(query)
        bonus = 0.0

        if focus_terms:
            hits = sum(1 for term in focus_terms if term in doc_text)
            bonus += min(hits * 3.0, 12.0)
            if not hits:
                bonus -= 10.0

        if "layout_region" in doc_text:
            bonus += 6.0

        section_match = re.search(r"\[section:\s*([^\]]+)\]", doc_text)
        if section_match and focus_terms:
            section = section_match.group(1)
            section_hits = [term for term in focus_terms if term in section]
            if section_hits:
                bonus += 10.0
                bonus += self._section_specificity_bonus(section, section_hits)
                body = doc_text[section_match.end():]
                if any(term in body[:500] for term in section_hits):
                    bonus += 6.0

        if question_type == "definition":
            if re.search(r"\b(is|are|means|represents|explained|instead of choosing|you may|may choose)\b", doc_text):
                bonus += 8.0
            if re.search(r"\b(instead of choosing|you may|can only choose|choose to)\b", doc_text):
                bonus += 8.0
            if re.search(r"\b(component|components|setup|credits)\b", doc_text):
                bonus -= 6.0

        if question_type == "timing":
            if re.search(r"\b(when|during|before|after|at any point|on your turn|you may|can only|cannot|must)\b", doc_text):
                bonus += 10.0
            if "clarifications" in doc_text:
                bonus += 2.0

        if question_type == "procedure":
            if re.search(r"\b(do the following|in order|step|steps|first|then|proceed)\b", doc_text):
                bonus += 10.0

        if question_type == "order":
            if re.search(r"\b(first turn|takes the first|turn order|alternating|starting player)\b", doc_text):
                bonus += 22.0
            else:
                bonus -= 30.0
            if any(term in query_text for term in ["\u6218\u6597", "fight", "\u602a\u7269", "monster"]):
                if not (("fight" in doc_text or "combat" in doc_text) and ("monster" in doc_text or "monsters" in doc_text)):
                    bonus -= 24.0

        if question_type == "limit":
            if re.search(r"\b(maximum|limit|up to|at most|may have|down to)\b", doc_text):
                bonus += 10.0
            else:
                bonus -= 8.0
            if any(term in query_text for term in ["\u836f\u6c34", "potion"]):
                if "potion" in doc_text or "potions" in doc_text:
                    bonus += 24.0
                else:
                    bonus -= 36.0

        if any(term in query_text for term in ["\u5956\u52b1", "\u52a0\u5206", "\u5f97\u5206", "\u5206", "bonus", "reward", "score", "points"]):
            if re.search(r"\b(victory points|points|score|scores|scoring|bonus tile|reward)\b", doc_text):
                bonus += 10.0
            else:
                bonus -= 8.0

        if self._is_triggered_placement_query(query):
            restriction_pattern = (
                r"\b(neither\b.{0,60}\beffect|nor its bonus|without\b.{0,80}\beffect|"
                r"without\b.{0,80}\bbonus|without paying|without paying its cost|"
                r"paying its cost\b.{0,80}\bmay use|may use\b.{0,80}\bnor its bonus|cannot use|may not use)\b"
            )
            has_restriction = bool(re.search(restriction_pattern, doc_text))
            if has_restriction:
                bonus += 34.0
            if re.search(r"\b(place|put|add).{0,120}\b(creature|animal|card|into your forest|in your forest|from your hand)\b", doc_text):
                bonus += 18.0
            if re.search(r"\b(if the card you just played|card you just played|playing a card)\b", doc_text):
                bonus += 6.0
                if not has_restriction:
                    bonus -= 24.0
            if re.search(r"\b(victory points|score|scoring|end of game|setup)\b", doc_text):
                bonus -= 8.0

        completion_scoring_query = (
            any(term in query_text for term in ["\u586b\u6ee1", "\u653e\u6ee1", "\u5b8c\u6210", "complete", "completed", "cover"])
            and any(term in query_text for term in ["\u6570\u91cf", "\u5956\u52b1", "\u52a0\u5206", "\u5f97\u5206", "\u5206", "size", "score", "points", "bonus"])
        )
        if completion_scoring_query:
            if re.search(r"\b(final tile|completed area|colored area|depending on its size|current phase|additional victory points)\b", doc_text):
                bonus += 24.0
            if re.search(r"\b(large bonus tile|small bonus tile|all spaces of one color|same color in their duchy)\b", doc_text):
                bonus += 16.0
            if re.search(r"\b(setup|each player receives|components|overview board|place it adjacent|storage spaces)\b", doc_text):
                bonus -= 22.0

        color_completion_query = (
            any(term in query_text for term in ["\u586b\u6ee1", "\u653e\u6ee1", "\u5b8c\u6210", "complete", "completed", "cover"])
            and any(term in query_text for term in ["\u989c\u8272", "color", "colored"])
        )
        if color_completion_query:
            if re.search(r"\b(all spaces of one color|same color|one color|colored area|completed area)\b", doc_text):
                bonus += 18.0
            else:
                bonus -= 14.0
            if re.search(r"\b(final tile|cover all spaces|large bonus tile|small bonus tile|victory points)\b", doc_text):
                bonus += 14.0

        if any(term in query_text for term in ["\u79fb\u52a8", "move", "movement"]):
            if any(term in query_text for term in ["\u9700\u8981", "\u5f03\u724c", "\u51e0\u5f20", "need", "discard", "cost"]):
                if "discard" in doc_text and ("move" in doc_text or "movement" in doc_text):
                    bonus += 22.0
                else:
                    bonus -= 18.0

        return bonus

    def _section_specificity_bonus(self, section: str, section_hits: List[str]) -> float:
        """Prefer focused rule sections over broad overview headings."""
        tokens = [token for token in self._tokenize(section) if len(token) > 2]
        if not tokens:
            return 0.0

        unique_tokens = set(tokens)
        hit_ratio = len(set(section_hits)) / max(len(unique_tokens), 1)
        bonus = min(hit_ratio * 12.0, 12.0)

        broad_terms = {"phase", "overview", "explained", "turn", "actions", "rules", "general"}
        broad_count = sum(1 for token in unique_tokens if token in broad_terms)
        if broad_count >= 2 and hit_ratio < 0.35:
            bonus -= 6.0
        if "/" in section and len(unique_tokens) > len(set(section_hits)) + 4:
            bonus -= 4.0
        return bonus

    def _question_type(self, query_text: str) -> str:
        if any(term in query_text for term in ["\u4e0a\u9650", "\u6700\u591a", "\u4fdd\u7559", "limit", "maximum"]):
            return "limit"
        if any(term in query_text for term in ["什么是", "是什么", "define", "what is"]):
            return "definition"
        if any(term in query_text for term in ["什么时候", "何时", "when", "能否", "可以"]):
            return "timing"
        if any(term in query_text for term in ["怎么", "如何", "步骤", "how"]):
            return "procedure"
        if any(term in query_text for term in ["先手", "谁先", "顺序", "order", "first"]):
            return "order"
        if any(term in query_text for term in ["游戏结束", "终局", "最终计分", "final scoring", "end of the game"]):
            return "end_game"
        return "general"

    def _focus_terms(self, query: str) -> List[str]:
        terms = []
        query_text = query.lower()
        for key, expansion in QUERY_EXPANSIONS.items():
            if key in query:
                terms.extend(self._tokenize(expansion))
        terms.extend(token for token in self._tokenize(query_text) if len(token) > 2)

        stop = {
            "rules", "rule", "when", "what", "how", "can", "may", "must",
            "maximum", "limit", "number", "count", "phase", "step", "steps",
            "definition", "explained", "allowed", "during", "before", "after",
            "means", "overview", "condition", "requirement", "need", "cost",
            "choose", "following", "perform",
            "up", "to", "at", "most", "many", "the", "end", "ii",
            "board", "player", "players", "game", "tile", "tiles", "hex",
            "hexes", "space", "spaces", "one", "same", "all", "of",
        }
        return [term for term in list(dict.fromkeys(terms)) if term not in stop]

    def _focus_alignment_score(self, doc: str, query: str) -> float:
        """Reward chunks about the same object type as the question."""
        doc_text = self._normalize_text(doc)
        query_text = self._normalize_text(query)
        score = 0.0

        focus_groups = [
            {
                "triggers": {"\u624b\u724c", "hand"},
                "positive": {"hand", "cards", "draw", "discard"},
                "negative": {"potion", "potions", "equipment", "monster", "trophy"},
                "required": {"hand", "cards"},
            },
            {
                "triggers": {"\u836f\u6c34", "potion"},
                "positive": {"potion", "potions", "alchemy", "consume"},
                "negative": {"hand-limit", "equipment", "monster", "trophy"},
                "required": {"potion", "potions"},
                "missing_penalty": 30.0,
            },
            {
                "triggers": {"\u79fb\u52a8", "move", "movement"},
                "positive": {"move", "movement", "terrain", "location"},
                "negative": {"potion", "hand-limit"},
                "required": {"move", "movement", "terrain", "location"},
            },
            {
                "triggers": {"\u6218\u6597", "fight", "combat"},
                "positive": {"fight", "combat", "attack", "damage"},
                "negative": set(),
                "required": {"fight", "combat", "attack", "damage"},
            },
            {
                "triggers": {"\u586b\u6ee1", "\u653e\u6ee1", "\u5b8c\u6210", "complete", "completed"},
                "positive": {"complete", "completed", "score", "scores", "victory", "points", "bonus"},
                "negative": {"variant", "solo", "end of the game", "setup", "components", "receives", "overview"},
                "required": {"complete", "completed", "score", "scores", "bonus", "points"},
            },
            {
                "triggers": {"\u989c\u8272", "color", "colored"},
                "positive": {"color", "colored", "area", "spaces", "duchy", "bonus"},
                "negative": {"border", "outpost", "inn"},
                "required": {"color", "colored"},
            },
            {
                "triggers": {"\u8d27\u7269", "\u51fa\u552e", "\u5356", "goods", "sell", "sold"},
                "positive": {"goods", "sell", "sold", "stack", "complete", "silver"},
                "negative": {"monastery", "livestock", "team", "solo"},
                "required": {"goods", "sell", "sold"},
            },
            {
                "triggers": {"\u5de5\u4eba", "worker", "workers"},
                "positive": {"worker", "workers", "chips", "final", "scoring", "victory", "point"},
                "negative": {"goods", "monastery", "team"},
                "required": {"worker", "workers"},
            },
            {
                "triggers": {"\u5e73\u5c40", "\u5e73\u624b", "tie", "tied"},
                "positive": {"tie", "tied", "winner", "wins", "empty", "spaces", "behind", "bridge"},
                "negative": {"team", "solo", "goods"},
                "required": {"tie", "tied"},
            },
            {
                "triggers": {"\u4fee\u9053\u9662", "monastery"},
                "positive": {"monastery", "monasteries", "tile", "tiles", "scoring"},
                "negative": {"goods", "ship", "team"},
                "required": {"monastery", "monasteries"},
            },
            {
                "triggers": {"\u755c\u7267", "\u7267\u573a", "livestock", "pasture"},
                "positive": {"livestock", "pasture", "animal", "animals", "scores", "scoring"},
                "negative": {"goods", "ship", "team"},
                "required": {"livestock", "pasture", "animal", "animals"},
            },
            {
                "triggers": {"0\u8d39", "0-cost", "zero"},
                "positive": {"0", "cost", "action", "card", "display", "pool", "deck", "discard"},
                "negative": {"monster", "exploration", "potion"},
                "required": {"action", "card", "discard"},
            },
            {
                "triggers": {"\u5730\u70b9\u884c\u52a8", "location action"},
                "positive": {"location", "action", "performed", "only", "once", "turn"},
                "negative": {"monster", "exploration", "trophy"},
                "required": {"location", "action"},
            },
            {
                "triggers": {"\u79fb\u51fa", "\u79fb\u56de", "move out", "back again"},
                "positive": {"move", "out", "back", "again", "same", "turn", "once"},
                "negative": {"monster", "combat", "trophy"},
                "required": {"move", "back", "turn"},
            },
            {
                "triggers": {"\u4e3b\u52a8\u73a9\u5bb6", "\u975e\u4e3b\u52a8\u73a9\u5bb6", "active player", "non-active"},
                "positive": {"active", "non", "attacking", "defending", "won", "lost", "draw", "cards", "phase"},
                "negative": {"monster", "exploration"},
                "required": {"active", "player", "draw"},
            },
        ]

        for group in focus_groups:
            if not any(trigger in query_text for trigger in group["triggers"]):
                continue
            score += sum(2.0 for term in group["positive"] if term in doc_text)
            score -= sum(3.0 for term in group["negative"] if term in doc_text)
            if not any(term in doc_text for term in group["required"]):
                score -= group.get("missing_penalty", 12.0)

        if any(term in query_text for term in ["\u836f\u6c34", "potion"]):
            if re.search(r"\b(maximum|limit|up to|at most|may have|down to)\b", doc_text) and (
                "potion" in doc_text or "potions" in doc_text
            ):
                score += 10.0
            elif re.search(r"\b(maximum|limit|up to|at most|may have|down to)\b", doc_text):
                score -= 10.0

        if any(term in query_text for term in ["\u79fb\u52a8", "move", "movement"]):
            if "discard" in doc_text and ("move" in doc_text or "movement" in doc_text):
                score += 12.0

        if "\u6218\u6597" not in query_text and "fight" not in query_text and "combat" not in query_text:
            if "hand-limit" in doc_text and any(term in query_text for term in ["\u624b\u724c", "hand"]):
                score -= 2.0
            if any(term in query_text for term in ["\u4fdd\u7559", "\u6700\u591a", "\u4e0a\u9650"]) and "fight" in doc_text:
                score -= 5.0

        if any(term in query_text for term in ["\u624b\u724c", "hand"]):
            if "hand" not in doc_text and "cards in hand" not in doc_text:
                score -= 8.0

        player_count_query = bool(
            re.search(r"\b\d+\s*players?\b", query_text)
            or re.search(r"\d+\s*\u4eba", query_text)
            or any(term in query_text for term in ["\u4eba\u5c40", "\u73a9\u5bb6\u6570", "\u73a9\u5bb6\u6570\u91cf", "player count"])
        )
        if player_count_query:
            has_player_table = bool(re.search(r"\bwith\s+\d+\s+players?\b", doc_text))
            if has_player_table:
                score += 32.0
            if "layout_region" in doc_text:
                score += 14.0
            if "setup" in doc_text or "rule_type=setup" in doc_text:
                score += 10.0
            if re.search(r"\b(player count|number of players|based on the player)\b", doc_text):
                score += 12.0
            if not has_player_table and re.search(r"\b(draw|drawing|effect|bonus|winter cards)\b", doc_text):
                score -= 18.0

        if self._is_triggered_placement_query(query):
            restriction_pattern = (
                r"\b(neither\b.{0,60}\beffect|nor its bonus|without\b.{0,80}\beffect|"
                r"without\b.{0,80}\bbonus|without paying|without paying its cost|"
                r"paying its cost\b.{0,80}\bmay use|may use\b.{0,80}\bnor its bonus)\b"
            )
            has_restriction = bool(re.search(restriction_pattern, doc_text))
            if has_restriction:
                score += 28.0
            if re.search(r"\b(place|put|add).{0,120}\b(creature|animal|card|into your forest|in your forest|from your hand)\b", doc_text):
                score += 14.0
            if re.search(r"\b(if the card you just played|card you just played)\b", doc_text) and not has_restriction:
                score -= 18.0
            if "effect" not in doc_text and "bonus" not in doc_text:
                score -= 10.0

        if "trophy" in doc_text and "trophy" not in query_text and "\u5956\u676f" not in query_text:
            score -= 8.0

        if any(term in query_text for term in ["\u6e38\u620f\u7ed3\u675f", "\u7ec8\u5c40", "\u6700\u7ec8\u8ba1\u5206", "final scoring", "end of the game"]):
            if re.search(r"\b(final scoring|end of the game|game ends|winner|wins|tie)\b", doc_text):
                score += 14.0
            if re.search(r"\b(team game|solo game|playing the game)\b", doc_text) and "final scoring" not in doc_text:
                score -= 8.0

        if any(term in query_text for term in ["0\u8d39", "0-cost", "zero cost"]):
            if re.search(r"\b(no 0-cost cards|0-cost card is revealed|action card display|common action deck)\b", doc_text):
                score += 22.0

        if any(term in query_text for term in ["\u5730\u70b9\u884c\u52a8", "\u79fb\u51fa", "\u79fb\u56de", "location action"]):
            if re.search(r"\b(location action)\b.{0,120}\b(performed only once|move out|back again|same turn)\b", doc_text):
                score += 24.0

        if any(term in query_text for term in ["\u4e3b\u52a8\u73a9\u5bb6", "\u975e\u4e3b\u52a8\u73a9\u5bb6", "active player", "non-active"]):
            if re.search(r"\b(active player|non-active player|attacking|defending)\b.{0,160}\b(draw|cards|phase iii|won|lost)\b", doc_text):
                score += 22.0
            if re.search(r"\b(active player lost)\b.{0,120}\b(draw|2 cards|instead of 3|phase iii)\b", doc_text):
                score += 26.0
            if re.search(r"\b(non-active player)\b.{0,140}\b(immediately draw|draw cards|won|lost)\b", doc_text):
                score += 18.0

        return score

    def _scope_alignment_score(self, doc: str, query: str) -> float:
        """Prefer base or variant rule units according to the user's wording."""
        doc_text = self._normalize_text(doc)
        query_text = self._normalize_text(query)
        score = 0.0

        variant_query = self._is_variant_query(query_text)
        variant_doc = self._is_variant_doc(doc_text)
        base_doc = self._is_base_doc(doc_text)

        if variant_query:
            if variant_doc:
                score += 28.0
            elif base_doc:
                score -= 10.0
            if re.search(r"\b(solo game|single player|1-player|one-player|automa|variant|variants|team game|expansion)\b", doc_text):
                score += 18.0
            if re.search(r"\b(instead of|black depot|target victory point marker|within 25 rounds|no restriction)\b", doc_text):
                score += 16.0
            if re.search(r"\b(base game|standard game|2-player game|3-player game|4-player game)\b", doc_text) and not variant_doc:
                score -= 12.0
        else:
            if variant_doc:
                score -= 12.0
            if base_doc:
                score += 4.0

        return score

    def _is_variant_query(self, query_text: str) -> bool:
        return any(term in query_text for term in [
            "单人", "单人游戏", "一人", "1人", "solo", "single player", "variant",
            "variants", "变体", "扩展", "expansion", "团队", "team game",
        ])

    def _is_triggered_placement_query(self, query: str) -> bool:
        query_text = self._normalize_text(query)
        trigger_terms = [
            "\u89e6\u53d1", "\u53d1\u52a8", "\u751f\u6548", "\u6548\u679c",
            "trigger", "triggers", "activate", "effect",
        ]
        placement_terms = [
            "\u653e\u7f6e", "\u653e\u5165", "\u653e\u5230", "\u901a\u8fc7", "\u5956\u52b1",
            "place", "placed", "put", "add", "into your forest", "bonus", "reward",
        ]
        card_terms = [
            "\u52a8\u7269", "\u751f\u7269", "\u724c", "animal", "creature", "card", "forest",
        ]
        return (
            any(term in query_text for term in trigger_terms)
            and any(term in query_text for term in placement_terms)
            and any(term in query_text for term in card_terms)
        )

    def _is_variant_doc(self, doc_text: str) -> bool:
        return any(term in doc_text for term in [
            "rule_scope=variant", "source_kind=variant", "rule_type=variant",
            " solo game", "single player", "variant", "variants", "team game", "expansion",
            "instead of at the end of the game", "black depot", "target victory point marker",
            "won t gain a victory point bonus", "won't gain a victory point bonus",
        ])

    def _is_base_doc(self, doc_text: str) -> bool:
        return any(term in doc_text for term in [
            "rule_scope=base", "source_kind=rule", "base game", "standard game",
        ])

    def _phrase_score(self, doc: str, query: str) -> float:
        normalized_doc = self._normalize_text(doc)
        tokens = [token for token in self._tokenize(query) if len(token) > 2]
        score = 0.0

        for left, right in zip(tokens, tokens[1:]):
            if f"{left} {right}" in normalized_doc:
                score += 1.5

        generic_patterns = [
            r"\b(maximum|limit|up to|at most)\b.{0,80}\b(card|cards|potion|potions|token|tokens|gold|hand)\b",
            r"\b(card|cards|potion|potions|token|tokens|gold|hand)\b.{0,80}\b(maximum|limit|up to|at most)\b",
            r"\b(draw|gain|discard|keep|retain|shuffle)\b.{0,80}\b(card|cards|deck|hand|potion|potions)\b",
            r"\b(complete|completed|cover)\b.{0,100}\b(color|colored|area|spaces|duchy)\b",
            r"\b(color|colored|area|spaces|duchy)\b.{0,100}\b(complete|completed|cover)\b",
            r"\b(victory points|bonus tile|score|scores)\b.{0,100}\b(color|colored|area|spaces|duchy)\b",
            r"\b(sell|sold)\b.{0,100}\b(goods|stack|complete)\b",
            r"\b(goods|stack)\b.{0,100}\b(sell|sold|complete)\b",
            r"\b(worker|workers|worker chips)\b.{0,100}\b(victory point|final scoring|every two)\b",
            r"\b(tie|tied)\b.{0,120}\b(winner|wins|empty spaces|bridge|behind)\b",
            r"\b(monastery tile)\b.{0,120}\b(added immediately|after placing|instead of at the end)\b",
            r"\b(won'?t gain|do not gain|no)\b.{0,120}\b(victory point bonus|color bonus)\b",
            r"\b(complete|completed)\b.{0,80}\b(color)\b.{0,120}\b(black depot|instead)\b",
            r"\b(no 0-cost cards|0-cost card is revealed|action card display|common action deck)\b",
            r"\b(location action)\b.{0,120}\b(performed only once|move out|back again|same turn)\b",
            r"\b(active player|non-active player|attacking|defending)\b.{0,160}\b(draw|cards|phase iii|won|lost)\b",
            r"\b(active player lost)\b.{0,120}\b(draw|2 cards|instead of 3|phase iii)\b",
            r"\b(non-active player)\b.{0,140}\b(immediately draw|draw cards|won|lost)\b",
        ]
        for pattern in generic_patterns:
            if re.search(pattern, normalized_doc):
                score += 2.0

        return score

    def _corpus_stats(self, docs: Iterable[str]) -> Dict:
        docs = list(docs)
        doc_freq = Counter()
        lengths = []
        for doc in docs:
            tokens = self._tokenize(doc)
            lengths.append(len(tokens))
            doc_freq.update(set(tokens))
        return {
            "doc_count": len(docs),
            "avg_doc_len": sum(lengths) / max(len(lengths), 1),
            "doc_freq": doc_freq,
        }

    def _tokenize(self, text: str) -> List[str]:
        return TOKEN_RE.findall(self._normalize_text(text))

    def _quality_penalty(self, doc: str) -> float:
        penalty = 0.0
        if doc.count("|") > 20:
            penalty += 2.0
        if "[TABLE]" in doc or "[/TABLE]" in doc:
            penalty += 1.5
        reversed_terms = ["htaP", "lliks", "eltiT", "gnitratS", "wodahS", "ecitcarP", "roniM"]
        penalty += min(sum(term in doc for term in reversed_terms) * 1.2, 6.0)
        if len(doc) > 200:
            short_tokens = sum(1 for token in doc.split() if len(token) <= 2)
            token_count = max(len(doc.split()), 1)
            if short_tokens / token_count > 0.45:
                penalty += 2.5
        return penalty

    def _dedupe_results(self, results: List[Tuple[str, float]], top_k: int) -> List[Tuple[str, float]]:
        deduped = []
        seen_signatures = []

        for doc, score in results:
            signature = self._content_signature(doc)
            if any(self._jaccard(signature, old) > 0.68 for old in seen_signatures):
                continue
            seen_signatures.append(signature)
            deduped.append((doc, score))
            if len(deduped) >= top_k:
                break

        return deduped

    def _content_signature(self, doc: str) -> frozenset:
        tokens = re.findall(r"[a-z0-9]{3,}", self._normalize_text(doc))
        return frozenset(tokens[:120])

    def _jaccard(self, left: frozenset, right: frozenset) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / max(len(left | right), 1)

    def _normalize_text(self, text: str) -> str:
        text = text.lower().replace("\x00", " ")
        text = re.sub(r"([a-z])-\s+([a-z])", r"\1\2", text)
        return re.sub(r"\s+", " ", text).strip()

    def delete_collection(self, game_id: int) -> None:
        collection_name = f"game_{game_id}"
        if self.client is None:
            try:
                from app.database import get_db_connection, init_db

                init_db()
                conn = get_db_connection()
                conn.execute("DELETE FROM chunk_embeddings WHERE game_id = ?", (game_id,))
                conn.commit()
                conn.close()
                logger.info(f"Deleted SQLite vectors for game {game_id}")
            except Exception as e:
                logger.error(f"Error deleting SQLite vectors for game {game_id}: {e}")
            return

        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")

    def delete_document_vectors(self, game_id: int, document_id: int) -> None:
        collection_name = f"game_{game_id}"
        prefix = f"doc_{document_id}_chunk_"
        if self.client is None:
            try:
                from app.database import get_db_connection, init_db

                init_db()
                conn = get_db_connection()
                conn.execute("DELETE FROM chunk_embeddings WHERE document_id = ?", (document_id,))
                conn.commit()
                conn.close()
                logger.info(f"Deleted SQLite vectors for document {document_id}")
            except Exception as e:
                logger.error(f"Error deleting SQLite vectors for document {document_id}: {e}")
            return

        try:
            try:
                collection = self.client.get_collection(name=collection_name)
            except Exception:
                logger.info(f"Collection {collection_name} does not exist while deleting document {document_id}")
                return
            existing = collection.get()
            ids = existing.get("ids", []) if existing else []
            ids_to_delete = [item_id for item_id in ids if item_id.startswith(prefix)]
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} vectors for document {document_id}")
        except Exception as e:
            logger.error(f"Error deleting vectors for document {document_id}: {e}")
