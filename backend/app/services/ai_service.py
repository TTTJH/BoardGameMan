"""
AI service for generating responses using LLM
"""

import logging
import re
import time
from typing import Generator, List, Tuple
from openai import OpenAI
from app.services.model_config import get_model_config

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESPONSE_TOKENS = 2400
DETAILED_MAX_RESPONSE_TOKENS = 2400
THINKING_MAX_RESPONSE_TOKENS = 5200
CONTINUATION_MAX_TOKENS = 1000
FAST_CONTEXT_DOCUMENTS = 8
DETAILED_CONTEXT_DOCUMENTS = 8
FAST_CONTEXT_CHARS = 1800
DETAILED_CONTEXT_CHARS = 1800


class AIService:
    """Service for AI-powered responses"""
    
    def __init__(self):
        """Initialize the AI service"""
        config = get_model_config()["chat"]
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=config["api_base"],
        )
        self.api_base = config["api_base"]
        self.model = config["model"]
        self.thinking_enabled = bool(config.get("thinking_enabled"))
        self.reasoning_effort = config.get("reasoning_effort") or "high"
        self.last_timing = {}
    
    def generate_response(
        self,
        user_query: str,
        context_documents: List[str],
        game_name: str,
        answer_mode: str = "concise",
    ) -> Tuple[str, List[str]]:
        """
        Generate an AI response based on user query and context documents
        
        Args:
            user_query: User's question
            context_documents: List of relevant document chunks
            game_name: Name of the board game
            
        Returns:
            Tuple of (response, source_indices)
        """
        self.last_timing = {
            "model": self.model,
            "llm_ms": 0,
            "continuation_ms": 0,
            "completion_calls": 0,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "finish_reason": None,
            "thinking_enabled": self.thinking_enabled,
            "reasoning_effort": self.reasoning_effort,
            "thinking_payload_applied": self._supports_deepseek_thinking(),
            "reasoning_content_present": False,
            "reasoning_content_chars": 0,
            "empty_content_retry": False,
            "answer_mode": answer_mode,
        }
        try:
            context, active_documents = self._build_context(user_query, context_documents, answer_mode)
            
            # Enhanced system prompt for rulebook analysis
            system_prompt = self._build_system_prompt(game_name, context, user_query, answer_mode)
            
            # Generate response
            started = time.perf_counter()
            response = self.client.chat.completions.create(
                **self._completion_kwargs(
                    messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                    ],
                    max_tokens=self._max_response_tokens(user_query, answer_mode),
                )
            )
            self.last_timing["llm_ms"] = round((time.perf_counter() - started) * 1000)
            self.last_timing["completion_calls"] = 1
            response_text = self._extract_message_content(response.choices[0].message)
            finish_reason = response.choices[0].finish_reason
            self.last_timing["finish_reason"] = finish_reason
            if getattr(response, "usage", None):
                self.last_timing["prompt_tokens"] = getattr(response.usage, "prompt_tokens", None)
                self.last_timing["completion_tokens"] = getattr(response.usage, "completion_tokens", None)
                self.last_timing["total_tokens"] = getattr(response.usage, "total_tokens", None)

            if self._supports_deepseek_thinking() and not response_text.strip():
                response_text, finish_reason = self._retry_without_thinking(
                    system_prompt=system_prompt,
                    user_query=user_query,
                    previous_finish_reason=finish_reason,
                )
                self.last_timing["finish_reason"] = finish_reason

            if finish_reason == "length" or self._looks_incomplete(response_text):
                response_text = self._complete_truncated_response(
                    system_prompt=system_prompt,
                    user_query=user_query,
                    partial_response=response_text,
                )
            
            logger.info(f"Generated response for query: {user_query[:50]}...")
            
            source_indices = self.select_source_indices(response_text, active_documents)
            return response_text, source_indices
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    def stream_response(
        self,
        user_query: str,
        context_documents: List[str],
        game_name: str,
        answer_mode: str = "concise",
    ) -> Generator[str, None, Tuple[str, List[int]]]:
        """Stream user-facing response text and return final text plus selected source indices."""
        self.last_timing = {
            "model": self.model,
            "llm_ms": 0,
            "continuation_ms": 0,
            "completion_calls": 0,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "finish_reason": None,
            "thinking_enabled": self.thinking_enabled,
            "reasoning_effort": self.reasoning_effort,
            "thinking_payload_applied": self._supports_deepseek_thinking(),
            "streaming": True,
            "answer_mode": answer_mode,
            "ttfb_ms": None,
            "stream_duration_ms": None,
            "delta_count": 0,
            "output_chars": 0,
        }
        context, active_documents = self._build_context(user_query, context_documents, answer_mode)
        system_prompt = self._build_system_prompt(game_name, context, user_query, answer_mode)
        chunks: List[str] = []
        started = time.perf_counter()
        first_delta_at = None
        finish_reason = None
        response = self.client.chat.completions.create(
            **self._completion_kwargs(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                max_tokens=self._max_response_tokens(user_query, answer_mode),
            ),
            stream=True,
        )
        self.last_timing["completion_calls"] = 1
        for event in response:
            choice = event.choices[0] if getattr(event, "choices", None) else None
            if not choice:
                continue
            delta = getattr(choice, "delta", None)
            text = getattr(delta, "content", None) if delta else None
            if text:
                if first_delta_at is None:
                    first_delta_at = time.perf_counter()
                    self.last_timing["ttfb_ms"] = round((first_delta_at - started) * 1000)
                chunks.append(text)
                self.last_timing["delta_count"] += 1
                self.last_timing["output_chars"] += len(text)
                yield text
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason

        ended = time.perf_counter()
        self.last_timing["llm_ms"] = round((ended - started) * 1000)
        if first_delta_at is not None:
            self.last_timing["stream_duration_ms"] = round((ended - first_delta_at) * 1000)
        self.last_timing["finish_reason"] = finish_reason
        response_text = "".join(chunks)
        source_indices = self.select_source_indices(response_text, active_documents)
        return response_text, source_indices

    def _build_system_prompt(self, game_name: str, context: str, user_query: str, answer_mode: str = "concise") -> str:
        answer_style = (
            "Balanced concise mode is active. Prioritize correctness over brevity: direct conclusion first, then enough supporting detail to avoid losing rule conditions or timing. "
            "Do not omit a relevant clause just to be short. If excerpts partially answer the question, explain the supported part and clearly mark any unsupported uncertainty."
            if not self._answer_needs_detail(user_query, answer_mode)
            else "Detailed mode is active or the user asked for a broader guide. Be complete, but avoid repeating the same rule twice."
        )
        return f"""You are an expert rules consultant for the board game "{game_name}".
Your expertise is in interpreting and explaining game rules clearly and accurately.

CRITICAL INSTRUCTIONS:
1. ONLY answer based on the provided rulebook excerpts
2. If information is not in the rulebook, explicitly state: "This information is not covered in the provided rulebook excerpts."
3. For complex rules, provide step-by-step explanations with examples
4. Always cite the specific rule or section when possible
5. If there are multiple interpretations, explain each one
6. For ambiguous rules, suggest the most reasonable interpretation based on game balance
7. Use clear formatting with bullet points and numbered lists
8. Highlight important keywords and rule names in bold
9. Answer in the same language as the user's question
10. If the context contains a direct rule sequence, state it directly instead of saying it is missing
11. For turn-order questions, carefully compare excerpts containing "Foe Turn", "Exile Turn", "before", and "after"
12. Quote the exact supporting English sentence when it determines the answer
13. Do not cite noisy examples, card stat blocks, or unrelated index text unless they are needed
14. For "how many" questions, answer the default/base value first; only mention optional modifiers if the user asks or they are essential
15. If excerpts describe multiple scoring or reward clauses triggered by the same placement/completion, combine all applicable clauses. Do not reject an additional clause unless the excerpts explicitly say it is excluded.
16. Carefully distinguish related rule objects such as completing one area/group and completing all spaces/items of one type or color; explain both when the user's wording could include both.
17. Prefer primary base-rule excerpts over examples, variants, solo rules, and cross-references when they conflict or are less direct.
18. Do not leave a section heading or bullet point without explanatory content. If the question is broad, be concise but complete.
19. {answer_style}
20. Do not answer "not covered" when the excerpts contain adjacent timing/trigger rules that can support a cautious conclusion. In that case, answer what is supported and name the missing piece separately.
21. Preserve action verbs exactly. Do not treat "place", "put", "add", "tuck", "gain", or "draw" as "play" unless an excerpt explicitly says they count as playing. Trigger rules tied to "the card you just played" apply only to cards that were actually played.
22. If a more specific rule says a card is placed/put without paying and you may use neither its effect nor its bonus, that specific restriction overrides the general rule for a card just played.
23. For setup and quantity details, do not use vague phrases like "a few", "several", "some", "\u51e0\u4e2a", "\u51e0\u5f20", or "\u51e0\u5757" when the excerpts contain an exact count. Use the exact count and cite it. If only vague wording is present, explicitly say the excerpt is vague.

RESPONSE FORMAT:
- Start with a direct answer to the question
- Provide supporting details from the rulebook
- Include exact quoted rule text when available
- Include relevant examples if applicable
- Cite support inline as "Document N" when needed
- Do not add a separate final Sources section; the application shows sources separately

Rulebook Context:
{context}"""

    def _build_context(self, user_query: str, context_documents: List[str], answer_mode: str = "concise") -> Tuple[str, List[str]]:
        detailed = self._answer_needs_detail(user_query, answer_mode)
        doc_limit = DETAILED_CONTEXT_DOCUMENTS if detailed else FAST_CONTEXT_DOCUMENTS
        char_limit = DETAILED_CONTEXT_CHARS if detailed else FAST_CONTEXT_CHARS
        active_documents = context_documents[:doc_limit]
        context = "\n\n".join([
            f"[Document {i+1}]\n{self._trim_context_document(doc, char_limit)}"
            for i, doc in enumerate(active_documents)
        ])
        self.last_timing["context_documents"] = len(active_documents)
        self.last_timing["context_chars"] = len(context)
        return context, active_documents

    @staticmethod
    def _trim_context_document(doc: str, char_limit: int) -> str:
        cleaned = AIService.clean_context_document(doc)
        if len(cleaned) <= char_limit:
            return cleaned
        cut = cleaned[:char_limit]
        boundary = max(cut.rfind(". "), cut.rfind("; "), cut.rfind("\n"))
        if boundary > char_limit * 0.65:
            cut = cut[:boundary + 1]
        return cut.rstrip() + "..."

    @staticmethod
    def _wants_detailed_answer(user_query: str, answer_mode: str = "concise") -> bool:
        if answer_mode == "detailed":
            return True
        lowered = (user_query or "").lower()
        markers = [
            "first-play", "walkthrough", "setup", "beginner", "detail", "详细", "详解",
            "新手", "开局", "入门", "设置", "摆放", "怎么开始", "流程", "完整",
        ]
        return any(marker in lowered for marker in markers) or len(user_query or "") > 220

    @staticmethod
    def _answer_needs_detail(user_query: str, answer_mode: str = "concise") -> bool:
        if answer_mode == "detailed":
            return True
        lowered = (user_query or "").lower()
        markers = [
            "first-play", "walkthrough", "setup", "beginner", "detail",
            "\u8be6\u7ec6", "\u8be6\u89e3", "\u65b0\u624b", "\u5f00\u5c40",
            "\u5165\u95e8", "\u8bbe\u7f6e", "\u6446\u653e",
            "\u600e\u4e48\u5f00\u59cb", "\u6d41\u7a0b", "\u5b8c\u6574",
        ]
        return any(marker in lowered for marker in markers) or len(user_query or "") > 220

    @staticmethod
    def select_source_indices(response_text: str, active_documents: List[str]) -> List[int]:
        cited = sorted({int(match) - 1 for match in re.findall(r"Document\s+(\d+)", response_text or "")})
        source_indices = [idx for idx in cited if 0 <= idx < len(active_documents)]
        if not source_indices:
            source_indices = list(range(min(len(active_documents), 3)))
        return source_indices

    def _complete_truncated_response(
        self,
        system_prompt: str,
        user_query: str,
        partial_response: str,
    ) -> str:
        """Ask the model to finish a clipped or dangling response without restarting."""
        try:
            started = time.perf_counter()
            continuation = self.client.chat.completions.create(
                **self._completion_kwargs(
                    messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                    {"role": "assistant", "content": partial_response},
                    {
                        "role": "user",
                        "content": (
                            "Continue exactly from where the previous answer stopped. "
                            "Finish any incomplete heading or bullet. Do not repeat completed sections. "
                            "Keep citing Document N when citing support."
                        ),
                    },
                    ],
                    max_tokens=CONTINUATION_MAX_TOKENS,
                )
            )
            self.last_timing["continuation_ms"] = round((time.perf_counter() - started) * 1000)
            self.last_timing["completion_calls"] = self.last_timing.get("completion_calls", 1) + 1
            continuation_text = self._extract_message_content(continuation.choices[0].message).strip()
            if not continuation_text:
                return partial_response
            return f"{partial_response.rstrip()}\n\n{continuation_text}"
        except Exception as error:
            logger.warning(f"Failed to complete truncated response: {error}")
            return partial_response

    def _retry_without_thinking(
        self,
        system_prompt: str,
        user_query: str,
        previous_finish_reason: str | None,
    ) -> Tuple[str, str | None]:
        """Retry once without thinking mode if the provider returned only reasoning/no final text."""
        try:
            started = time.perf_counter()
            response = self.client.chat.completions.create(
                **self._completion_kwargs(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"{user_query}\n\n"
                                "Return only the final user-facing answer. Do not include hidden reasoning."
                            ),
                        },
                    ],
                    max_tokens=DEFAULT_MAX_RESPONSE_TOKENS,
                    allow_thinking=False,
                )
            )
            self.last_timing["continuation_ms"] = round((time.perf_counter() - started) * 1000)
            self.last_timing["completion_calls"] = self.last_timing.get("completion_calls", 1) + 1
            self.last_timing["empty_content_retry"] = True
            text = self._extract_message_content(response.choices[0].message).strip()
            if getattr(response, "usage", None):
                self.last_timing["retry_prompt_tokens"] = getattr(response.usage, "prompt_tokens", None)
                self.last_timing["retry_completion_tokens"] = getattr(response.usage, "completion_tokens", None)
                self.last_timing["retry_total_tokens"] = getattr(response.usage, "total_tokens", None)
            return text, response.choices[0].finish_reason
        except Exception as error:
            logger.warning(f"Failed to retry empty thinking response without thinking: {error}")
            return "", previous_finish_reason

    def _completion_kwargs(self, messages: List[dict], max_tokens: int, allow_thinking: bool = True) -> dict:
        """Build chat completion kwargs, including provider-specific reasoning switches."""
        kwargs = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if allow_thinking and self._supports_deepseek_thinking():
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            if self.reasoning_effort:
                kwargs["reasoning_effort"] = self.reasoning_effort
        return kwargs

    def _max_response_tokens(self, user_query: str = "", answer_mode: str = "concise") -> int:
        if self._supports_deepseek_thinking():
            return THINKING_MAX_RESPONSE_TOKENS
        if self._answer_needs_detail(user_query, answer_mode):
            return DETAILED_MAX_RESPONSE_TOKENS
        return DEFAULT_MAX_RESPONSE_TOKENS

    def _extract_message_content(self, message) -> str:
        """Return only user-facing content while tracking hidden reasoning presence."""
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content is None and hasattr(message, "model_extra"):
            reasoning_content = (message.model_extra or {}).get("reasoning_content")
        if reasoning_content:
            self.last_timing["reasoning_content_present"] = True
            self.last_timing["reasoning_content_chars"] = len(str(reasoning_content))
        return getattr(message, "content", None) or ""

    def _supports_deepseek_thinking(self) -> bool:
        """Only apply DeepSeek thinking payload when the selected provider looks compatible."""
        if not self.thinking_enabled:
            return False
        marker = f"{self.api_base} {self.model}".lower()
        return "deepseek" in marker

    @staticmethod
    def _looks_incomplete(text: str) -> bool:
        """Detect obvious dangling Markdown/list endings such as a bare heading."""
        stripped = (text or "").strip()
        if not stripped:
            return False

        tail_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        if not tail_lines:
            return False

        last_line = tail_lines[-1]
        if len(last_line) <= 80 and re.search(r"[:：]\s*$", last_line):
            return True
        if re.match(r"^#{1,6}\s+\S", last_line):
            return True
        if re.match(r"^(\d+[.)]|[-*])\s+\S.{0,60}$", last_line) and not re.search(r"[。.!?？)]$", last_line):
            return True
        return False

    @staticmethod
    def clean_context_document(source: str) -> str:
        """Lightly clean PDF artifacts before using a chunk as LLM context."""
        return AIService._normalize_pdf_noise(AIService.strip_source_metadata(source))

    @staticmethod
    def clean_source_excerpt(source: str, query: str = "", max_chars: int = 650) -> str:
        """Return a readable, relevant source excerpt for UI display."""
        cleaned = AIService._normalize_pdf_noise(AIService.strip_source_metadata(source))
        lowered = cleaned.lower()
        anchors = AIService._query_anchors(query)

        anchor_pos = -1
        for anchor in anchors:
            anchor_pos = lowered.find(anchor)
            if anchor_pos >= 0:
                break

        if anchor_pos >= 0 and len(cleaned) > max_chars:
            start = max(anchor_pos - 180, 0)
            end = min(start + max_chars, len(cleaned))
            excerpt = cleaned[start:end]
            if start > 0:
                first_boundary = max(excerpt.find(". "), excerpt.find("\n"))
                if 0 <= first_boundary < 120:
                    excerpt = excerpt[first_boundary + 2:]
                excerpt = "…" + excerpt.strip()
            if end < len(cleaned):
                excerpt = excerpt.rstrip() + "…"
            return excerpt

        return cleaned[:max_chars].rstrip() + ("…" if len(cleaned) > max_chars else "")

    @staticmethod
    def strip_source_metadata(source: str) -> str:
        return re.sub(r"^\[SourceMeta:[^\]]+\]\s*", "", source or "").strip()

    @staticmethod
    def parse_source_metadata(source: str) -> dict:
        match = re.search(r"^\[SourceMeta:\s*document_id=(\d+)\s+chunk_index=(\d+)\]", source or "")
        if not match:
            return {}
        return {
            "document_id": int(match.group(1)),
            "chunk_index": int(match.group(2)),
        }

    @staticmethod
    def _query_anchors(query: str) -> List[str]:
        """Build generic excerpt anchors from the user's question."""
        lowered = query.lower()
        anchors = []
        expansion_groups = [
            (["\u4e0a\u9650", "\u6700\u591a", "\u4fdd\u7559", "limit", "maximum"], ["maximum", "limit", "up to", "at most"]),
            (["\u624b\u724c", "hand"], ["hand", "cards in hand", "hand-limit"]),
            (["\u836f\u6c34", "potion"], ["potion", "potions"]),
            (["\u79fb\u52a8", "move", "movement"], ["to move:", "discard a card", "discard cards", "movement", "connected location", "terrain"]),
            (["\u884c\u52a8", "action"], ["action", "actions", "phase"]),
            (["\u6218\u6597", "fight", "combat"], ["fight", "combat", "attack", "damage"]),
            (["\u602a\u7269", "monster"], ["monster", "monsters", "foe"]),
        ]
        for triggers, terms in expansion_groups:
            if any(trigger in lowered for trigger in triggers):
                anchors.extend(terms)

        anchors.extend(re.findall(r"[a-z0-9]{3,}", lowered))
        return list(dict.fromkeys(anchors))

    @staticmethod
    def _normalize_pdf_noise(text: str) -> str:
        """Normalize common pdfplumber extraction noise from card/layout-heavy rulebooks."""
        if not text:
            return ""

        text = text.replace("\x00", "")
        text = AIService._dedupe_overprinted_text(text)
        text = re.sub(r"\s+", " ", text).strip()

        # Fix overprinted words embedded inside neighboring OCR fragments.
        embedded_replacements = {
            r"[A-Za-z]*PPrraatcctteiiccee[A-Za-z]*": " ",
            r"[A-Za-z]*SSdhhiirrtt[A-Za-z]*": " ",
            r"[A-Za-z]*PPaannmttss[A-Za-z]*": " ",
            r"[A-Za-z]*PPrraaccrrttiiccooee[A-Za-z]*": " ",
            r"Prac\s+e\s+tice\s+r\s+Pa\s+s\s+nts": " ",
        }
        for pattern, replacement in embedded_replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Remove obvious reversed/rotated card-layout fragments that are not useful as citations.
        noisy_tokens = [
            "ecitcarP", "roniM", "efinK", "gnitnuH", "raepS", "cotsE",
            "SSSIIIWWW", "SSSTTTRRR", "XXXEEEDDD", "DDDNNNEEE", "CCCHHHAAA",
        ]
        for token in noisy_tokens:
            text = text.replace(token, " ")

        # Collapse repeated headings produced by overlapping PDF layers.
        text = re.sub(r"\b(\w{3,})\b(?:\s+\1\b){2,}", r"\1", text, flags=re.IGNORECASE)

        # Remove common card-equipment captions when they are interleaved into rules prose.
        card_noise = [
            "Practice Shirt", "Practice Pants", "Practice Kit", "Practice Staff",
            "Practice Knife", "Practice Shortbow", "Practice Quiver", "Practice Shield",
            "Practice Lute", "Practice Spear", "Practice Tanto", "Practice Trap",
        ]
        for phrase in card_noise:
            text = re.sub(rf"\b{re.escape(phrase)}\b", " ", text, flags=re.IGNORECASE)

        text = re.sub(r"\bRP\b", " ", text)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _dedupe_overprinted_text(text: str) -> str:
        """Fix tokens like 'RRuulleebbooookk' caused by overprinted PDF fonts."""
        def fix_token(match):
            token = match.group(0)
            if len(token) < 4 or len(token) % 2 != 0:
                return token
            pairs = [token[i:i + 2] for i in range(0, len(token), 2)]
            if all(len(pair) == 2 and pair[0] == pair[1] for pair in pairs):
                return ''.join(pair[0] for pair in pairs)
            return token

        return re.sub(r"[A-Za-z]{4,}", fix_token, text)
    
    @staticmethod
    def format_response_with_sources(
        response: str,
        sources: List[str]
    ) -> str:
        """
        Format response with source citations
        
        Args:
            response: AI-generated response
            sources: List of source documents
            
        Returns:
            Formatted response with sources
        """
        formatted = response
        if sources:
            formatted += "\n\n**Sources:**\n"
            for i, source in enumerate(sources, 1):
                formatted += f"{i}. {source[:100]}...\n"
        return formatted
