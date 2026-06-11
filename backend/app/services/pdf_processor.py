"""
PDF processing and adaptive text chunking service.
"""

import logging
import json
import math
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    import PyPDF2


class PDFProcessor:
    """Service for extracting text from PDF files."""

    @staticmethod
    def extract_text_from_pdf(file_path: str, layout_regions: Optional[List[Dict]] = None) -> Tuple[str, int]:
        try:
            if HAS_PDFPLUMBER:
                return PDFProcessor._extract_with_pdfplumber(file_path, layout_regions=layout_regions)
            return PDFProcessor._extract_with_pypdf2(file_path)
        except Exception as e:
            logger.error(f"Error processing PDF file {file_path}: {e}")
            raise

    @staticmethod
    def _extract_with_pdfplumber(file_path: str, layout_regions: Optional[List[Dict]] = None) -> Tuple[str, int]:
        text = ""
        regions_by_page = PDFProcessor._regions_by_page(layout_regions or [])
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages):
                try:
                    page_number = page_num + 1
                    page_regions = regions_by_page.get(page_number, [])
                    page_text = PDFProcessor._extract_page_text(page, exclude_regions=page_regions)
                    if page_regions:
                        region_text = PDFProcessor._extract_page_regions(page, page_regions)
                        if region_text:
                            page_text = "\n\n".join(part for part in [page_text, region_text] if part).strip()
                    if page_text:
                        text += f"\n--- Page {page_number} ---\n{page_text}"
                except Exception as e:
                    logger.warning(f"Error extracting from page {page_num + 1}: {e}")
                    continue

        logger.info(f"Successfully extracted text from {page_count} pages using pdfplumber")
        return text, page_count

    @staticmethod
    def _regions_by_page(layout_regions: List[Dict]) -> Dict[int, List[Dict]]:
        grouped: Dict[int, List[Dict]] = {}
        for region in layout_regions:
            if not region.get("enabled", True):
                continue
            try:
                page = int(region.get("page", 0))
            except (TypeError, ValueError):
                continue
            if page < 1:
                continue
            grouped.setdefault(page, []).append(region)

        for page, regions in grouped.items():
            regions.sort(key=lambda item: (int(item.get("reading_order") or 1), int(item.get("id") or 0)))
        return grouped

    @staticmethod
    def _extract_page_regions(page, regions: List[Dict]) -> str:
        sections = []
        ignore_boxes = [
            box for box in (
                PDFProcessor._normalized_bbox_to_pdf_box(region.get("bbox") or {}, page.width, page.height)
                for region in regions
                if region.get("enabled", True) and (region.get("region_type") or "rule") == "ignore"
            )
            if box is not None
        ]
        for region in regions:
            if not region.get("enabled", True):
                continue
            if (region.get("region_type") or "rule") == "ignore":
                continue

            bbox = region.get("bbox") or {}
            crop_box = PDFProcessor._normalized_bbox_to_pdf_box(bbox, page.width, page.height)
            if crop_box is None:
                continue

            try:
                ignore_boxes_for_region = [
                    ignore_box for ignore_box in ignore_boxes
                    if PDFProcessor._boxes_overlap(crop_box, ignore_box)
                ]
                region_text = PDFProcessor._extract_region_text_with_exclusions(page, crop_box, ignore_boxes_for_region)
            except Exception as error:
                logger.warning(f"Could not extract layout region {region.get('id')}: {error}")
                continue

            if not region_text:
                continue

            marker = PDFProcessor._layout_region_marker(region)
            label = (region.get("label") or "").strip()
            label_line = label if label and not region_text.lower().startswith(label.lower()) else ""
            sections.append("\n".join(part for part in [marker, label_line, region_text] if part).strip())
        return "\n\n".join(sections).strip()

    @staticmethod
    def _normalized_bbox_to_pdf_box(bbox: Dict, page_width: float, page_height: float) -> Tuple[float, float, float, float] | None:
        if isinstance(bbox, str):
            try:
                bbox = json.loads(bbox)
            except json.JSONDecodeError:
                return None
        if not isinstance(bbox, dict):
            return None
        try:
            x = max(0.0, min(1.0, float(bbox.get("x", 0))))
            y = max(0.0, min(1.0, float(bbox.get("y", 0))))
            width = max(0.0, min(1.0, float(bbox.get("width", 0))))
            height = max(0.0, min(1.0, float(bbox.get("height", 0))))
        except (TypeError, ValueError):
            return None

        left = x * page_width
        top = y * page_height
        right = min(page_width, (x + width) * page_width)
        bottom = min(page_height, (y + height) * page_height)
        if right - left < 4 or bottom - top < 4:
            return None
        return (left, top, right, bottom)

    @staticmethod
    def _extract_region_text(region_page) -> str:
        raw_text = region_page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
        raw_text = TextChunker._normalize_pdf_text(raw_text).strip()
        if raw_text:
            return raw_text
        return PDFProcessor._extract_page_text(region_page)

    @staticmethod
    def _extract_region_text_with_exclusions(page, crop_box: Tuple[float, float, float, float], ignore_boxes: List[Tuple[float, float, float, float]]) -> str:
        words = page.extract_words(
            x_tolerance=1.5,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False,
            extra_attrs=["upright"],
        ) or []
        kept_words = []
        for word in words:
            center_x = (word["x0"] + word["x1"]) / 2
            center_y = (word["top"] + word["bottom"]) / 2
            if not PDFProcessor._point_in_box(center_x, center_y, crop_box):
                continue
            if any(PDFProcessor._point_in_box(center_x, center_y, ignore_box) for ignore_box in ignore_boxes):
                continue
            kept_words.append(word)
        return PDFProcessor._words_to_text(PDFProcessor._prepare_words(kept_words))

    @staticmethod
    def _layout_region_marker(region: Dict) -> str:
        payload = {
            "type": region.get("region_type") or "rule",
            "label": region.get("label") or "",
            "order": int(region.get("reading_order") or 1),
            "id": region.get("id"),
        }
        return f"@@LAYOUT_REGION {json.dumps(payload, ensure_ascii=False)}@@"

    @staticmethod
    def _extract_page_text(page, exclude_regions: Optional[List[Dict]] = None) -> str:
        """Extract text in a reading order that is friendlier to multi-column rulebooks."""
        raw_text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
        words = page.extract_words(
            x_tolerance=1.5,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False,
            extra_attrs=["upright"],
        ) or []
        words = PDFProcessor._filter_page_bounds_words(words, page.width, page.height)
        words = PDFProcessor._exclude_region_words(words, exclude_regions or [], page.width, page.height)
        words = PDFProcessor._prepare_words(words)
        if len(words) < 40:
            word_text = PDFProcessor._words_to_text(words)
            if word_text:
                return word_text
            return "" if exclude_regions else raw_text

        if not words:
            return ""

        if not exclude_regions:
            symbol_overview_text = PDFProcessor._extract_symbol_overview_text(words, raw_text)
            if symbol_overview_text:
                return symbol_overview_text

        column_ranges = PDFProcessor._detect_column_ranges(words, page.width, page.height)
        if len(column_ranges) <= 1:
            return PDFProcessor._words_to_text(words)

        heading_cutoff = PDFProcessor._first_body_top(words, page.height)
        heading_words = [
            word for word in words
            if word["top"] < heading_cutoff and PDFProcessor._spans_multiple_columns(word, column_ranges)
        ]
        body_words = [word for word in words if word not in heading_words]

        sections = []
        heading_text = PDFProcessor._words_to_text(heading_words)
        if heading_text:
            sections.append(heading_text)

        for left, right in column_ranges:
            column_words = [
                word for word in body_words
                if left <= (word["x0"] + word["x1"]) / 2 <= right
            ]
            column_text = PDFProcessor._words_to_text(column_words)
            if column_text:
                sections.append(column_text)

        return "\n\n".join(sections).strip()

    @staticmethod
    def _exclude_region_words(words: List[Dict], regions: List[Dict], page_width: float, page_height: float) -> List[Dict]:
        if not regions:
            return words

        boxes = []
        for region in regions:
            if not region.get("enabled", True):
                continue
            pdf_box = PDFProcessor._normalized_bbox_to_pdf_box(region.get("bbox") or {}, page_width, page_height)
            if pdf_box is not None:
                boxes.append(pdf_box)
        if not boxes:
            return words

        filtered = []
        for word in words:
            center_x = (word["x0"] + word["x1"]) / 2
            center_y = (word["top"] + word["bottom"]) / 2
            if any(PDFProcessor._point_in_box(center_x, center_y, box) for box in boxes):
                continue
            filtered.append(word)
        return filtered

    @staticmethod
    def _filter_page_bounds_words(words: List[Dict], page_width: float, page_height: float) -> List[Dict]:
        filtered = []
        for word in words:
            center_x = (word["x0"] + word["x1"]) / 2
            center_y = (word["top"] + word["bottom"]) / 2
            if 0 <= center_x <= page_width and 0 <= center_y <= page_height:
                filtered.append(word)
        return filtered

    @staticmethod
    def _point_in_box(x: float, y: float, box: Tuple[float, float, float, float]) -> bool:
        left, top, right, bottom = box
        return left <= x <= right and top <= y <= bottom

    @staticmethod
    def _boxes_overlap(left_box: Tuple[float, float, float, float], right_box: Tuple[float, float, float, float]) -> bool:
        left_a, top_a, right_a, bottom_a = left_box
        left_b, top_b, right_b, bottom_b = right_box
        return left_a < right_b and right_a > left_b and top_a < bottom_b and bottom_a > top_b

    @staticmethod
    def _extract_symbol_overview_text(words: List[Dict], raw_text: str) -> str:
        """Keep icon/symbol overview rule tables in natural row order.

        These pages often pair an icon list on the left with explanatory rules
        on the right. Pure column reading can split sentences like "Place a
        creature ... into your forest" across chunks, so preserve the normal
        pdfplumber text and add a focused right-column rule extract.
        """
        normalized_raw = TextChunker._normalize_pdf_text(raw_text or "").lower()
        if not (
            "type symbol" in normalized_raw
            and ("effect and bonus" in normalized_raw or "effects and bonuses" in normalized_raw)
        ):
            return ""

        heading_top = None
        heading_left = None
        sorted_words = sorted(words, key=lambda item: (round(item["top"], 1), item["x0"]))
        for index, word in enumerate(sorted_words):
            if word["text"].lower() != "effect":
                continue
            nearby = [
                candidate for candidate in sorted_words[index + 1:index + 5]
                if abs(candidate["top"] - word["top"]) <= 3
            ]
            if any(candidate["text"].lower() in {"bonus", "bonuses"} for candidate in nearby):
                heading_top = word["top"]
                heading_left = max(0, word["x0"] - 16)
                break

        if heading_top is None or heading_left is None:
            return TextChunker._normalize_pdf_text(raw_text or "").strip()

        lower_heading_tops = []
        for index, word in enumerate(sorted_words):
            if word["top"] <= heading_top + 45 or word["x0"] >= heading_left:
                continue
            text = word["text"].lower()
            if text in {"credits", "credit"}:
                lower_heading_tops.append(word["top"])
                continue
            if text == "tree":
                same_line = [
                    candidate for candidate in sorted_words[index + 1:index + 4]
                    if abs(candidate["top"] - word["top"]) <= 3
                ]
                if any(candidate["text"].lower() == "symbols" for candidate in same_line):
                    lower_heading_tops.append(word["top"])
        bottom = min(lower_heading_tops, default=max(word["bottom"] for word in words))
        effect_words = [
            word for word in words
            if heading_top - 3 <= word["top"] <= bottom
            and (word["x0"] + word["x1"]) / 2 >= heading_left
        ]
        effect_text = PDFProcessor._words_to_text(effect_words)
        full_text = TextChunker._normalize_pdf_text(raw_text or "").strip()
        parts = [part for part in [full_text, "Effect and Bonus Details\n" + effect_text if effect_text else ""] if part]
        return "\n\n".join(parts).strip()

    @staticmethod
    def _prepare_words(words: List[Dict]) -> List[Dict]:
        prepared = []
        for word in words:
            if not PDFProcessor._is_readable_word_orientation(word):
                continue
            text = TextChunker._dedupe_overprinted_text(word.get("text", ""))
            text = TextChunker._normalize_pdf_token(text)
            if not text or PDFProcessor._is_decorative_word(text):
                continue
            prepared.append({**word, "text": text})
        return prepared

    @staticmethod
    def _is_readable_word_orientation(word: Dict) -> bool:
        if word.get("upright") is False:
            return False
        direction = str(word.get("direction") or "").lower()
        if direction in {"ttb", "btt"}:
            return False
        return True

    @staticmethod
    def _detect_column_ranges(words: List[Dict], page_width: float, page_height: float) -> List[Tuple[float, float]]:
        body_words = [
            word for word in words
            if page_height * 0.06 <= word["top"] <= page_height * 0.94
            and len(word["text"]) > 1
        ]
        if len(body_words) < 80:
            return [(0, page_width)]

        line_segment_counts = PDFProcessor._line_segment_counts(body_words)
        multi_segment_lines = sum(1 for count in line_segment_counts if count >= 2)
        three_segment_lines = sum(1 for count in line_segment_counts if count >= 3)

        thirds = [
            (0, page_width / 3),
            (page_width / 3, page_width * 2 / 3),
            (page_width * 2 / 3, page_width),
        ]
        third_counts = [
            sum(1 for word in body_words if left <= (word["x0"] + word["x1"]) / 2 < right)
            for left, right in thirds
        ]
        if three_segment_lines >= 6 and min(third_counts) >= max(30, len(body_words) * 0.12):
            return thirds

        intervals = sorted((word["x0"], word["x1"]) for word in body_words)
        merged = []
        for left, right in intervals:
            if not merged or left - merged[-1][1] > 8:
                merged.append([left, right])
            else:
                merged[-1][1] = max(merged[-1][1], right)

        text_bands = [
            (max(0, left - 3), min(page_width, right + 3))
            for left, right in merged
            if right - left >= 80
        ]
        if 2 <= len(text_bands) <= 3:
            counts = []
            for left, right in text_bands:
                count = sum(1 for word in body_words if left <= (word["x0"] + word["x1"]) / 2 <= right)
                counts.append(count)
            if min(counts) >= max(25, len(body_words) * 0.08):
                return text_bands

        if multi_segment_lines >= 8 and min(third_counts) >= max(30, len(body_words) * 0.14):
            return thirds

        halves = [(0, page_width / 2), (page_width / 2, page_width)]
        half_counts = [
            sum(1 for word in body_words if left <= (word["x0"] + word["x1"]) / 2 < right)
            for left, right in halves
        ]
        if multi_segment_lines >= 6 and min(half_counts) >= max(35, len(body_words) * 0.22):
            return halves

        return [(0, page_width)]

    @staticmethod
    def _line_segment_counts(words: List[Dict]) -> List[int]:
        lines = []
        current = []
        current_top = None
        for word in sorted(words, key=lambda item: (round(item["top"], 1), item["x0"])):
            if current_top is None or abs(word["top"] - current_top) <= 3:
                current.append(word)
                current_top = word["top"] if current_top is None else current_top
                continue
            lines.append(current)
            current = [word]
            current_top = word["top"]
        if current:
            lines.append(current)

        counts = []
        for line in lines:
            line = sorted(line, key=lambda item: item["x0"])
            if len(line) < 4:
                counts.append(1)
                continue
            segments = 1
            previous = line[0]
            for word in line[1:]:
                if word["x0"] - previous["x1"] > 18:
                    segments += 1
                previous = word
            counts.append(segments)
        return counts

    @staticmethod
    def _first_body_top(words: List[Dict], page_height: float) -> float:
        candidates = [
            word["top"]
            for word in words
            if word["top"] > page_height * 0.04 and len(word["text"]) <= 24
        ]
        return min(candidates, default=page_height * 0.12) + 8

    @staticmethod
    def _spans_multiple_columns(word: Dict, column_ranges: List[Tuple[float, float]]) -> bool:
        touched = 0
        for left, right in column_ranges:
            if word["x0"] < right and word["x1"] > left:
                touched += 1
        return touched > 1 or word["x1"] - word["x0"] > 180

    @staticmethod
    def _words_to_text(words: List[Dict]) -> str:
        if not words:
            return ""

        lines = []
        current = []
        current_top = None
        for word in sorted(words, key=lambda item: (round(item["top"], 1), item["x0"])):
            if current_top is None or abs(word["top"] - current_top) <= 3:
                current.append(word)
                current_top = word["top"] if current_top is None else current_top
                continue

            line = PDFProcessor._join_word_line(current)
            if line:
                lines.append(line)
            current = [word]
            current_top = word["top"]

        line = PDFProcessor._join_word_line(current)
        if line:
            lines.append(line)

        cleaned_lines = []
        for line in lines:
            line = TextChunker._normalize_pdf_line(line)
            if not line or TextChunker._looks_like_toc_line(line):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    @staticmethod
    def _join_word_line(words: List[Dict]) -> str:
        words = sorted(words, key=lambda item: item["x0"])
        parts = []
        previous = None
        for word in words:
            text = word["text"]
            if previous is not None and word["x0"] - previous["x1"] > 18:
                parts.append(" ")
            parts.append(text)
            previous = word
        return " ".join(parts)

    @staticmethod
    def _is_decorative_word(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        if re.fullmatch(r"[._~·•\-–—]{4,}", stripped):
            return True
        if re.fullmatch(r"([+\-−]?\d+|[+\-−])([.\s]+[+\-−]?\d+)*[.\s]*", stripped) and len(stripped) > 6:
            return True
        return False

    @staticmethod
    def _extract_with_pypdf2(file_path: str) -> Tuple[str, int]:
        text = ""
        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            page_count = len(pdf_reader.pages)
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text() or ""
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}"
                except Exception as e:
                    logger.warning(f"Error extracting from page {page_num + 1}: {e}")
                    continue

        logger.info(f"Successfully extracted text from {page_count} pages using PyPDF2")
        return text, page_count


class TextChunker:
    """Section-aware chunking for rulebooks and other structured PDFs."""

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 900, overlap: int = 180) -> List[Dict]:
        chunks, _ = TextChunker.chunk_text_with_stats(text, chunk_size, overlap)
        return chunks

    @staticmethod
    def chunk_text_with_stats(text: str, chunk_size: int = 900, overlap: int = 180) -> Tuple[List[Dict], Dict]:
        chunks = []
        current_section: Optional[str] = None
        low_quality_chunks = []
        page_chunk_counts: Dict[str, int] = {}
        page_type_counts: Dict[str, Dict[str, int]] = {}

        for page_num, page_text in TextChunker._iter_pages(text):
            blocks, current_section = TextChunker._page_blocks(page_text, current_section)
            for chunk in TextChunker._pack_blocks(blocks, chunk_size, overlap):
                chunk_text = chunk["text"].strip()
                if not chunk_text:
                    continue
                low_quality_reasons = TextChunker._low_quality_reasons(chunk_text)
                if low_quality_reasons:
                    chunk_type = chunk.get("type") or TextChunker._detect_chunk_type(chunk_text)
                    low_quality_chunks.append({
                        "page": page_num,
                        "section": chunk.get("section") or current_section or "",
                        "type": chunk_type,
                        "source_kind": chunk.get("source_kind") or TextChunker._detect_source_kind(chunk_text, chunk_type),
                        "reasons": low_quality_reasons,
                        "preview": TextChunker._preview_text(chunk_text),
                    })
                    continue

                section = chunk.get("section") or current_section or ""
                chunk_type = chunk.get("type") or TextChunker._detect_chunk_type(chunk_text)
                rule_scope = TextChunker._detect_rule_scope(chunk_text, chunk_type)
                source_kind = chunk.get("source_kind") or TextChunker._detect_source_kind(chunk_text, chunk_type)
                prefix = f"[Page {page_num}]"
                if section:
                    prefix += f" [Section: {section}]"

                chunks.append({
                    "text": f"{prefix}\n{chunk_text}",
                    "page": page_num,
                    "metadata": {
                        **(chunk.get("metadata") or {}),
                        "page": page_num,
                        "section": section,
                        "type": chunk_type,
                        "rule_scope": rule_scope,
                        "source_kind": source_kind,
                    },
                })
                page_chunk_counts[page_num] = page_chunk_counts.get(page_num, 0) + 1
                page_type_counts.setdefault(page_num, {})
                page_type_counts[page_num][chunk_type] = page_type_counts[page_num].get(chunk_type, 0) + 1

        logger.info(f"Created {len(chunks)} adaptive chunks")
        return chunks, {
            "low_quality_chunk_count": len(low_quality_chunks),
            "low_quality_chunks": low_quality_chunks,
            "page_chunk_counts": page_chunk_counts,
            "page_type_counts": page_type_counts,
        }

    @staticmethod
    def clean_text(text: str) -> str:
        text = text.replace("\x00", "")
        text = TextChunker._dedupe_overprinted_text(text)
        text = TextChunker._normalize_pdf_text(text)

        lines = text.split("\n")
        cleaned_lines = []
        prev_blank = False
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
                prev_blank = False
            elif not prev_blank:
                cleaned_lines.append("")
                prev_blank = True

        return "\n".join(cleaned_lines)

    @staticmethod
    def _iter_pages(text: str) -> List[Tuple[str, str]]:
        pages = []
        for page_info in text.split("--- Page ")[1:]:
            lines = page_info.split("\n")
            page_num = lines[0].replace("---", "").strip()
            page_text = "\n".join(lines[1:])
            pages.append((page_num, page_text))
        return pages

    @staticmethod
    def _page_blocks(text: str, current_section: Optional[str]) -> Tuple[List[Dict], Optional[str]]:
        text = TextChunker._normalize_pdf_text(text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        blocks = []
        buffer = []
        current_region_type: Optional[str] = None
        current_source_kind = "paragraph"
        current_region_section: Optional[str] = None
        current_region_metadata: Optional[Dict] = None

        def flush_buffer():
            nonlocal buffer, current_region_type, current_source_kind, current_region_section, current_region_metadata
            if buffer:
                block_text = TextChunker._join_wrapped_lines(buffer)
                if block_text:
                    blocks.append({
                        "text": block_text,
                        "section": current_region_section if current_source_kind == "layout_region" else current_section,
                        "source_kind": current_source_kind,
                        "type": TextChunker._region_type_to_chunk_type(current_region_type),
                        "metadata": current_region_metadata or {},
                    })
                buffer = []
            if current_source_kind == "layout_region":
                current_region_type = None
                current_region_section = None
                current_region_metadata = None
                current_source_kind = "paragraph"

        for line in lines:
            layout_region = TextChunker._parse_layout_region_marker(line)
            if layout_region is not None:
                flush_buffer()
                label = (layout_region.get("label") or "").strip()
                order = layout_region.get("order") or layout_region.get("id") or len(blocks) + 1
                current_region_type = layout_region.get("type") or "rule"
                current_source_kind = "layout_region"
                current_region_section = label or f"Manual layout region {order}"
                current_region_metadata = {
                    "layout_region_id": layout_region.get("id"),
                    "layout_region_label": label,
                    "layout_region_type": current_region_type,
                    "layout_region_order": order,
                }
                continue

            if current_source_kind == "layout_region":
                buffer.append(line)
                continue

            if TextChunker._looks_like_heading(line):
                flush_buffer()
                current_section = TextChunker._clean_heading(line)
                blocks.append({
                    "text": current_section,
                    "section": current_section,
                    "source_kind": "heading",
                    "type": TextChunker._region_type_to_chunk_type(current_region_type),
                })
                continue

            if TextChunker._looks_like_list_item(line):
                flush_buffer()
                blocks.append({
                    "text": line,
                    "section": current_section,
                    "source_kind": "list_item",
                    "type": TextChunker._region_type_to_chunk_type(current_region_type),
                })
                continue

            buffer.append(line)
            if TextChunker._ends_sentence(line):
                flush_buffer()

        flush_buffer()
        return blocks, current_section

    @staticmethod
    def _pack_blocks(blocks: List[Dict], chunk_size: int, overlap: int) -> List[Dict]:
        chunks = []
        current = []
        current_len = 0
        current_section = ""
        current_kinds = []
        current_types = []
        current_metadata = {}

        for block in blocks:
            block_kind = block.get("source_kind", "paragraph")
            block_section = block.get("section") or current_section
            if current and (
                block_kind == "layout_region"
                or ("layout_region" in current_kinds and block_kind != "layout_region")
                or ("layout_region" in current_kinds and block_section != current_section)
            ):
                chunk_text = "\n".join(current).strip()
                chunks.append({
                    "text": chunk_text,
                    "section": current_section,
                    "source_kind": TextChunker._dominant_source_kind(current_kinds),
                    "type": TextChunker._dominant_block_type(current_types),
                    "metadata": current_metadata,
                })
                current = []
                current_len = 0
                current_kinds = []
                current_types = []
                current_metadata = {}

            pieces = (
                TextChunker._split_long_text(block["text"], chunk_size)
                if len(block["text"]) > chunk_size
                else [block["text"]]
            )
            for piece in pieces:
                piece_len = len(piece)
                if current and current_len + piece_len + 2 > chunk_size:
                    chunk_text = "\n".join(current).strip()
                    chunks.append({
                        "text": chunk_text,
                        "section": current_section,
                        "source_kind": TextChunker._dominant_source_kind(current_kinds),
                        "type": TextChunker._dominant_block_type(current_types),
                        "metadata": current_metadata,
                    })
                    overlap_text = TextChunker._tail_at_word_boundary(chunk_text, overlap)
                    current = [overlap_text] if overlap_text else []
                    current_len = len(overlap_text)
                    current_kinds = ["overlap"] if overlap_text else []
                    current_types = []
                    current_metadata = {}

                current.append(piece)
                current_len += piece_len + 1
                current_section = block.get("section") or current_section
                current_kinds.append(block.get("source_kind", "paragraph"))
                if block.get("type"):
                    current_types.append(block["type"])
                if block.get("metadata"):
                    current_metadata.update(block["metadata"])

        if current:
            chunks.append({
                "text": "\n".join(current).strip(),
                "section": current_section,
                "source_kind": TextChunker._dominant_source_kind(current_kinds),
                "type": TextChunker._dominant_block_type(current_types),
                "metadata": current_metadata,
            })

        return chunks

    @staticmethod
    def _parse_layout_region_marker(line: str) -> Optional[Dict]:
        match = re.match(r"^@@LAYOUT_REGION\s+(.+)@@$", line)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(1))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _region_type_to_chunk_type(region_type: Optional[str]) -> Optional[str]:
        mapping = {
            "rule": None,
            "table": "component",
            "ignore": "text",
            "setup": "setup",
            "action": "action",
            "scoring": "scoring",
            "example": "example",
            "component": "component",
            "variant": "variant",
        }
        return mapping.get(region_type or "", None)

    @staticmethod
    def _dominant_block_type(types: List[str]) -> Optional[str]:
        useful = [item for item in types if item]
        if not useful:
            return None
        counts = {item: useful.count(item) for item in set(useful)}
        return sorted(counts.items(), key=lambda item: item[1], reverse=True)[0][0]

    @staticmethod
    def _split_long_text(text: str, chunk_size: int) -> List[str]:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return []

        units = re.split(r"(?<=[.!?\u3002\uff01\uff1f])\s+", normalized)
        pieces = []
        current = ""

        for unit in units:
            if not unit:
                continue

            if len(unit) > chunk_size:
                words = unit.split()
                for word in words:
                    if len(current) + len(word) + 1 <= chunk_size:
                        current = f"{current} {word}".strip()
                    else:
                        if current:
                            pieces.append(current)
                        current = word
            elif len(current) + len(unit) + 1 <= chunk_size:
                current = f"{current} {unit}".strip()
            else:
                if current:
                    pieces.append(current)
                current = unit

        if current:
            pieces.append(current)
        return pieces

    @staticmethod
    def _is_low_quality_chunk(text: str) -> bool:
        return bool(TextChunker._low_quality_reasons(text))

    @staticmethod
    def _low_quality_reasons(text: str) -> List[str]:
        stripped = text.strip()
        if not stripped:
            return ["empty_text"]

        pipe_count = stripped.count("|")
        alpha_chars = sum(1 for ch in stripped if ch.isalpha())
        repeated_symbol_runs = len([
            run for run in re.findall(r"[^\w\s]{4,}", stripped)
            if not re.fullmatch(r"[.·\s]+", run)
        ])
        reversed_terms = [
            term for term in ["htaP", "lliks", "eltiT", "gnitratS", "wodahS"]
            if term in stripped
        ]
        toc_lines = sum(1 for line in stripped.splitlines() if TextChunker._looks_like_toc_line(line))
        content_lines = sum(1 for line in stripped.splitlines() if line.strip())

        reasons = []
        if pipe_count > 35:
            reasons.append(f"many_table_pipes:{pipe_count}")
        if len(reversed_terms) >= 3:
            reasons.append(f"reversed_text:{','.join(reversed_terms)}")
        if repeated_symbol_runs >= 4:
            reasons.append(f"repeated_symbol_runs:{repeated_symbol_runs}")
        if content_lines and toc_lines / content_lines > 0.65:
            reasons.append(f"toc_like_lines:{toc_lines}/{content_lines}")
        if len(stripped) > 160 and alpha_chars / max(len(stripped), 1) < 0.20:
            reasons.append(f"low_alpha_ratio:{alpha_chars / max(len(stripped), 1):.2f}")
        return reasons

    @staticmethod
    def _preview_text(text: str, limit: int = 360) -> str:
        preview = re.sub(r"\s+", " ", text).strip()
        return preview[:limit]

    @staticmethod
    def _detect_chunk_type(text: str) -> str:
        normalized = text.lower()
        if re.search(r"\b(variant|solo|team game|advanced|optional|expansion)\b", normalized):
            return "variant"
        if re.search(r"\b(example|for example|e\.g\.)\b", normalized):
            return "example"
        if re.search(r"\b(end of the game|game ends|final scoring|winner|wins the game|tie)\b", normalized):
            return "end_game"
        if re.search(r"\b(setup|set up|preparation|prepare|components|contents|each player receives|player count)\b", normalized):
            return "setup"
        if re.search(r"\bwith\s+\d+\s+players?\b", normalized) and re.search(r"\b(cards?|tokens?|pieces?|tiles?)\b", normalized):
            return "setup"
        if re.search(r"\bset\s+(?:the\s+)?\d+\b.*\b(cards?|tokens?|pieces?|tiles?)\b", normalized):
            return "setup"
        if re.search(r"\b(score|scores|scoring|victory point|victory points|points|bonus|final scoring)\b", normalized):
            return "scoring"
        if re.search(r"\b(action|actions|you may|may choose|choose one|perform|take a|place|move|buy|sell|discard|draw)\b", normalized):
            return "action"
        if re.search(r"\b(turn order|on your turn|player turn|phase|round|take turns|before|after)\b", normalized):
            return "turn_structure"
        if re.search(r"\b(component|components|token|tokens|tile|tiles|card|cards|board|marker|miniature)\b", normalized):
            return "component"
        if TextChunker._looks_like_heading(text.strip()):
            return "component"
        if TextChunker._looks_like_list_item(text.strip()):
            return "action"
        return "text"

    @staticmethod
    def _detect_rule_scope(text: str, chunk_type: str) -> str:
        normalized = text.lower()
        if chunk_type == "variant" or re.search(r"\b(variant|solo|optional|advanced|expansion|team game)\b", normalized):
            return "variant"
        if chunk_type == "example" or re.search(r"\b(example|for example|e\.g\.)\b", normalized):
            return "example"
        return "base"

    @staticmethod
    def _detect_source_kind(text: str, chunk_type: str) -> str:
        stripped = text.strip()
        if TextChunker._looks_like_heading(stripped):
            return "heading"
        if TextChunker._looks_like_list_item(stripped):
            return "list_item"
        if chunk_type == "example":
            return "example"
        if chunk_type == "variant":
            return "variant"
        return "rule"

    @staticmethod
    def _dominant_source_kind(kinds: List[str]) -> str:
        useful = [kind for kind in kinds if kind != "overlap"]
        if not useful:
            return "rule"
        counts = {kind: useful.count(kind) for kind in set(useful)}
        return sorted(counts.items(), key=lambda item: item[1], reverse=True)[0][0]

    @staticmethod
    def _normalize_pdf_text(text: str) -> str:
        text = text.replace("\x00", "")
        text = TextChunker._dedupe_overprinted_text(text)
        text = re.sub(r"([A-Za-z])-\s*\n\s*([a-z])", r"\1\2", text)
        text = re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", text)
        text = text.replace("\u2022", "\n\u2022 ")
        text = text.replace("\u0083", "\n\u2022 ")
        text = TextChunker._fix_pdf_ligature_splits(text)
        text = re.sub(r"[ \t]+", " ", text)
        return text

    @staticmethod
    def _normalize_pdf_token(text: str) -> str:
        text = TextChunker._dedupe_overprinted_text(text)
        text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
        text = re.sub(r"([()])\1{2,}", r"\1", text)
        return text.strip()

    @staticmethod
    def _normalize_pdf_line(line: str) -> str:
        line = TextChunker._dedupe_overprinted_text(line)
        line = TextChunker._fix_pdf_ligature_splits(line)
        line = re.sub(r"\b([A-Z])\s+([a-z]{2,})\b", r"\1\2", line)
        line = re.sub(r"\s*([.,;:!?])", r"\1", line)
        line = re.sub(r"\s+", " ", line).strip()
        return line

    @staticmethod
    def _fix_pdf_ligature_splits(text: str) -> str:
        replacements = {
            r"\bfi\s+rst\b": "first",
            r"\bfi\s+nal\b": "final",
            r"\bfi\s+nd\b": "find",
            r"\bfi\s+ght\b": "fight",
            r"\bfi\s+re\b": "fire",
            r"\bfi\s+t\b": "fit",
            r"\bfi\s+ed\b": "fied",
            r"\bfl\s+ip\b": "flip",
            r"\bfl\s+ips\b": "flips",
            r"\bfl\s+ipped\b": "flipped",
            r"\bfl\s+ipping\b": "flipping",
            r"\beff\s+ect\b": "effect",
            r"\beff\s+ects\b": "effects",
            r"\boff\s+er\b": "offer",
            r"\boff\s+ers\b": "offers",
            r"\bdiff\s+erent\b": "different",
            r"\bdiff\s+icult\b": "difficult",
            r"\bbenefi\s+t\b": "benefit",
            r"\bbenefi\s+ts\b": "benefits",
            r"\bfortifi\s+ed\b": "fortified",
            r"\bfulfi\s+ll\b": "fulfill",
            r"\bShuffl\s+es\b": "Shuffles",
            r"\bShuffl\s+e\b": "Shuffle",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _looks_like_toc_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if re.search(r"\.{4,}\s*\d{1,3}\s*$", stripped):
            return True
        if stripped.count(".") >= 8 and re.search(r"\d{1,3}\s*$", stripped):
            return True
        return False

    @staticmethod
    def _join_wrapped_lines(lines: List[str]) -> str:
        text = " ".join(lines)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _looks_like_heading(line: str) -> bool:
        clean = TextChunker._clean_heading(line)
        if len(clean) < 3 or len(clean) > 90:
            return False
        if re.search(r"[.!?\u3002\uff01\uff1f]$", clean):
            return False

        words = re.findall(r"[A-Za-z]+", clean)
        if not words:
            return False

        alpha_count = sum(1 for ch in clean if ch.isalpha())
        upper_ratio = sum(1 for ch in clean if ch.isupper()) / max(alpha_count, 1)
        title_words = sum(1 for word in words if word[:1].isupper())
        return upper_ratio > 0.55 or title_words >= max(2, len(words) - 1)

    @staticmethod
    def _clean_heading(line: str) -> str:
        return re.sub(r"^\d+(\.\d+)*\s*", "", line).strip(" -:\t")

    @staticmethod
    def _looks_like_list_item(line: str) -> bool:
        return bool(re.match(r"^(\u2022|\*|-|[0-9]+[.)]|[a-zA-Z][.)])\s+", line))

    @staticmethod
    def _ends_sentence(line: str) -> bool:
        return bool(re.search(r"[.!?\u3002\uff01\uff1f:]$|[.;]\s*$", line))

    @staticmethod
    def _tail_at_word_boundary(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        tail = text[-max_chars:]
        boundary = max(tail.find(". "), tail.find("\n"))
        if 0 <= boundary < len(tail) - 20:
            return tail[boundary + 1:].strip()
        first_space = tail.find(" ")
        return tail[first_space + 1:].strip() if first_space > 0 else tail.strip()

    @staticmethod
    def _dedupe_overprinted_text(text: str) -> str:
        def collapse_repeated_chars(token: str) -> str:
            if len(token) < 4:
                return token

            runs = []
            index = 0
            repeated_runs = 0
            repeated_chars = 0
            while index < len(token):
                char = token[index]
                end = index + 1
                while end < len(token) and token[end] == char:
                    end += 1
                run_length = end - index
                runs.append((char, run_length))
                if run_length > 1:
                    repeated_runs += 1
                    repeated_chars += run_length
                index = end

            single_runs = sum(1 for _, run_length in runs if run_length == 1)
            if (
                repeated_runs >= 2
                and repeated_chars / max(len(token), 1) >= 0.65
                and single_runs <= max(1, len(runs) // 5)
            ):
                multiplier = 0
                for _, run_length in runs:
                    multiplier = run_length if multiplier == 0 else math.gcd(multiplier, run_length)
                if multiplier >= 2:
                    candidate = "".join(char * max(1, round(run_length / multiplier)) for char, run_length in runs)
                    if len(candidate) >= 2:
                        return candidate

            candidate = "".join(char for char, _ in runs)
            if repeated_runs >= 3 and single_runs == 0 and len(candidate) >= 2:
                return candidate
            return token

        def fix_token(match):
            token = match.group(0)
            collapsed = collapse_repeated_chars(token)
            if collapsed != token:
                return collapsed
            if len(token) < 4 or len(token) % 2 != 0:
                return token
            pairs = [token[i:i + 2] for i in range(0, len(token), 2)]
            if all(len(pair) == 2 and pair[0] == pair[1] for pair in pairs):
                return "".join(pair[0] for pair in pairs)
            return token

        text = re.sub(r"[A-Za-z]{4,}", fix_token, text)
        return re.sub(r"([~._·•\-–—])\1{3,}", "", text)
