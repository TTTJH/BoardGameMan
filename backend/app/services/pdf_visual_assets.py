"""
Visual assets extracted from uploaded PDF rulebooks.
"""

from pathlib import Path
import logging
import re

import pypdfium2 as pdfium
from PIL import Image, ImageFilter

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

from app.config import settings

logger = logging.getLogger(__name__)


class PDFVisualAssets:
    """Render rulebook pages so source citations can preserve visual context."""

    PAGE_PREVIEW_SCALE = 1.35
    ASSET_MANAGER_PREVIEW_SCALE = 4.0

    ASSET_RENDER_SCALE = {
        "icon": 10.0,
        "token": 10.0,
        "component": 10.0,
        "tile": 4.5,
        "card": 4.0,
        "reference": 4.0,
        "board": 2.5,
    }

    ASSET_MIN_EDGE = {
        "icon": 384,
        "token": 384,
        "component": 384,
        "tile": 420,
        "card": 640,
        "reference": 640,
        "board": 900,
    }

    @staticmethod
    def render_pages(
        game_id: int,
        document_id: int,
        file_path: str,
        scale: float = PAGE_PREVIEW_SCALE,
    ) -> None:
        output_dir = PDFVisualAssets.page_dir(game_id, document_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        pdf = pdfium.PdfDocument(file_path)
        try:
            for index in range(len(pdf)):
                page_number = index + 1
                output_path = output_dir / f"page_{page_number}.png"
                if output_path.exists():
                    continue

                page = pdf[index]
                try:
                    bitmap = page.render(scale=scale)
                    image = bitmap.to_pil()
                    image.save(output_path, "PNG", optimize=True)
                finally:
                    page.close()
        finally:
            pdf.close()

        logger.info(f"Rendered PDF visual pages for game={game_id} document={document_id}")

    @staticmethod
    def render_page_preview(
        game_id: int,
        document_id: int,
        file_path: str,
        page_number: int,
        scale: float = ASSET_MANAGER_PREVIEW_SCALE,
    ) -> Path:
        """Render one high-resolution page preview for manual asset selection."""
        output_path = PDFVisualAssets.page_preview_path(game_id, document_id, page_number, scale)
        if output_path.exists():
            return output_path

        image = PDFVisualAssets.render_page_image(file_path, page_number, scale)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, "PNG", optimize=True)
            return output_path
        finally:
            image.close()

    @staticmethod
    def render_page_image(file_path: str, page_number: int, scale: float) -> Image.Image:
        """Render one PDF page to a PIL image at the requested scale."""
        pdf = pdfium.PdfDocument(file_path)
        try:
            if page_number < 1 or page_number > len(pdf):
                raise ValueError("Page is out of range")
            page = pdf[page_number - 1]
            try:
                bitmap = page.render(scale=scale)
                return bitmap.to_pil()
            finally:
                page.close()
        finally:
            pdf.close()

    @staticmethod
    def crop_normalized_asset(
        file_path: str,
        page_number: int,
        bbox: dict,
        asset_type: str,
        output_path: Path,
    ) -> tuple[int, int]:
        """Crop a manually selected asset from a high-resolution PDF render.

        The frontend stores normalized coordinates from the preview image. We
        apply the same normalized box to a higher DPI render, then upscale only
        when the selected symbol is still too small for chat display.
        """
        asset_kind = asset_type or "component"
        scale = PDFVisualAssets.ASSET_RENDER_SCALE.get(asset_kind, 5.0)
        image = PDFVisualAssets.render_page_image(file_path, page_number, scale)
        try:
            crop_box = PDFVisualAssets._normalized_crop_box(bbox, image.width, image.height, asset_kind)
            if crop_box[2] - crop_box[0] < 12 or crop_box[3] - crop_box[1] < 12:
                raise ValueError("Selected area is too small")

            cropped = image.crop(crop_box)
            cropped = PDFVisualAssets._prepare_asset_image(cropped, asset_kind)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cropped.save(output_path, "PNG", optimize=True)
            return cropped.size
        finally:
            image.close()

    @staticmethod
    def _normalized_crop_box(
        bbox: dict,
        image_width: int,
        image_height: int,
        asset_type: str,
    ) -> tuple[int, int, int, int]:
        x = max(0.0, min(1.0, float(bbox.get("x", 0))))
        y = max(0.0, min(1.0, float(bbox.get("y", 0))))
        width = max(0.0, min(1.0, float(bbox.get("width", 0))))
        height = max(0.0, min(1.0, float(bbox.get("height", 0))))

        left = x * image_width
        top = y * image_height
        right = min(image_width, (x + width) * image_width)
        bottom = min(image_height, (y + height) * image_height)

        if asset_type in {"icon", "token", "component"}:
            pad_ratio = 0.08
        elif asset_type in {"tile", "card"}:
            pad_ratio = 0.035
        else:
            pad_ratio = 0.02

        crop_width = right - left
        crop_height = bottom - top
        pad_x = max(4, crop_width * pad_ratio)
        pad_y = max(4, crop_height * pad_ratio)
        return (
            max(0, int(left - pad_x)),
            max(0, int(top - pad_y)),
            min(image_width, int(right + pad_x)),
            min(image_height, int(bottom + pad_y)),
        )

    @staticmethod
    def _prepare_asset_image(image: Image.Image, asset_type: str) -> Image.Image:
        min_edge = PDFVisualAssets.ASSET_MIN_EDGE.get(asset_type or "", 256)
        width, height = image.size
        shortest = min(width, height)
        if shortest and shortest < min_edge:
            factor = min_edge / shortest
            width = int(round(width * factor))
            height = int(round(height * factor))
            image = image.resize((width, height), Image.Resampling.LANCZOS)

        if asset_type in {"icon", "token", "component"}:
            image = image.filter(ImageFilter.UnsharpMask(radius=0.8, percent=125, threshold=3))
        return image

    @staticmethod
    def page_dir(game_id: int, document_id: int) -> Path:
        return Path(settings.UPLOAD_DIR) / "rule_pages" / f"game_{game_id}" / f"doc_{document_id}"

    @staticmethod
    def page_url(game_id: int, document_id: int, page_number: int) -> str:
        return f"/rule-pages/game_{game_id}/doc_{document_id}/page_{page_number}.png"

    @staticmethod
    def page_path(game_id: int, document_id: int, page_number: int) -> Path:
        return PDFVisualAssets.page_dir(game_id, document_id) / f"page_{page_number}.png"

    @staticmethod
    def page_preview_filename(page_number: int, scale: float = ASSET_MANAGER_PREVIEW_SCALE) -> str:
        return f"page_{page_number}_asset_preview_{int(round(scale * 100))}.png"

    @staticmethod
    def page_preview_path(
        game_id: int,
        document_id: int,
        page_number: int,
        scale: float = ASSET_MANAGER_PREVIEW_SCALE,
    ) -> Path:
        return PDFVisualAssets.page_dir(game_id, document_id) / PDFVisualAssets.page_preview_filename(page_number, scale)

    @staticmethod
    def page_preview_url(
        game_id: int,
        document_id: int,
        page_number: int,
        scale: float = ASSET_MANAGER_PREVIEW_SCALE,
    ) -> str:
        return f"/rule-pages/game_{game_id}/doc_{document_id}/{PDFVisualAssets.page_preview_filename(page_number, scale)}"

    @staticmethod
    def crop_dir(game_id: int, document_id: int) -> Path:
        return Path(settings.UPLOAD_DIR) / "visual_refs" / f"game_{game_id}" / f"doc_{document_id}"

    @staticmethod
    def crop_url(game_id: int, document_id: int, filename: str) -> str:
        return f"/visual-refs/game_{game_id}/doc_{document_id}/{filename}"

    @staticmethod
    def crop_term_on_page(
        game_id: int,
        document_id: int,
        file_path: str,
        page_number: int,
        term: str,
    ) -> str | None:
        """Crop the area around a term on a rendered PDF page, falling back silently."""
        if not HAS_PDFPLUMBER or not term or page_number < 1:
            return None

        safe_term = PDFVisualAssets._safe_filename(term)
        if not safe_term:
            return None

        output_dir = PDFVisualAssets.crop_dir(game_id, document_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"page_{page_number}_{safe_term}_v6.png"
        output_path = output_dir / output_filename
        if output_path.exists():
            return PDFVisualAssets.crop_url(game_id, document_id, output_filename)

        page_image_path = PDFVisualAssets.page_path(game_id, document_id, page_number)
        if not page_image_path.exists():
            PDFVisualAssets.render_pages(game_id, document_id, file_path)
        if not page_image_path.exists():
            return None

        try:
            with pdfplumber.open(file_path) as pdf:
                if page_number > len(pdf.pages):
                    return None
                page = pdf.pages[page_number - 1]
                bbox = PDFVisualAssets._find_term_bbox(page, term)
                if not bbox:
                    return None

                with Image.open(page_image_path) as image:
                    scale_x = image.width / page.width
                    scale_y = image.height / page.height
                    left, top, right, bottom = PDFVisualAssets._component_crop_bbox(page, bbox)
                    crop_box = (
                        max(0, int(left * scale_x)),
                        max(0, int(top * scale_y)),
                        min(image.width, int(right * scale_x)),
                        min(image.height, int(bottom * scale_y)),
                    )
                    if crop_box[2] - crop_box[0] < 40 or crop_box[3] - crop_box[1] < 30:
                        return None
                    image.crop(crop_box).save(output_path, "PNG", optimize=True)
                    return PDFVisualAssets.crop_url(game_id, document_id, output_filename)
        except Exception as error:
            logger.warning(
                "Could not crop term visual for game=%s document=%s page=%s term=%s: %s",
                game_id,
                document_id,
                page_number,
                term,
                error,
            )
            return None

    @staticmethod
    def _find_term_bbox(page, term: str) -> tuple[float, float, float, float] | None:
        words = page.extract_words(
            x_tolerance=2,
            y_tolerance=4,
            keep_blank_chars=False,
            use_text_flow=False,
        ) or []
        normalized_words = [
            {**word, "norm": PDFVisualAssets._normalize_token(word.get("text", ""))}
            for word in words
        ]
        normalized_words = [word for word in normalized_words if word["norm"]]
        term_tokens = [
            token for token in (
                PDFVisualAssets._normalize_token(token)
                for token in re.findall(r"[A-Za-z0-9]+", term)
            )
            if token
        ]
        if not term_tokens:
            return None

        max_window = min(len(term_tokens) + 2, 10)
        target = "".join(term_tokens)
        for index in range(len(normalized_words)):
            for size in range(len(term_tokens), max_window + 1):
                window = normalized_words[index:index + size]
                if len(window) < len(term_tokens):
                    continue
                joined = "".join(word["norm"] for word in window)
                if joined == target or target in joined:
                    return (
                        min(word["x0"] for word in window),
                        min(word["top"] for word in window),
                        max(word["x1"] for word in window),
                        max(word["bottom"] for word in window),
                    )
        return None

    @staticmethod
    def _component_crop_bbox(page, bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        visual_bbox = PDFVisualAssets._nearby_visual_bbox(page, bbox)
        if visual_bbox:
            left = min(bbox[0], visual_bbox[0])
            top = min(bbox[1], visual_bbox[1])
            right = max(bbox[2], visual_bbox[2])
            bottom = max(bbox[3], visual_bbox[3])
            width = right - left
            height = bottom - top
            if (width * height) > (page.width * page.height * 0.16):
                return PDFVisualAssets._expanded_bbox(
                    bbox=bbox,
                    page_width=page.width,
                    page_height=page.height,
                )
            return PDFVisualAssets._clamp_bbox(
                (
                    left - max(18, width * 0.08),
                    top - max(18, height * 0.08),
                    right + max(18, width * 0.08),
                    bottom + max(18, height * 0.08),
                ),
                page.width,
                page.height,
            )

        return PDFVisualAssets._expanded_bbox(
            bbox=bbox,
            page_width=page.width,
            page_height=page.height,
        )

    @staticmethod
    def _nearby_visual_bbox(page, text_bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float] | None:
        text_left, text_top, text_right, text_bottom = text_bbox
        text_center_x = (text_left + text_right) / 2
        text_center_y = (text_top + text_bottom) / 2
        text_width = max(1, text_right - text_left)
        text_height = max(1, text_bottom - text_top)
        page_area = page.width * page.height
        candidates = []

        for item in PDFVisualAssets._page_visual_objects(page):
            visual_bbox = PDFVisualAssets._object_bbox(item)
            if not visual_bbox:
                continue
            left, top, right, bottom = visual_bbox
            width = right - left
            height = bottom - top
            area = width * height
            if width < 12 or height < 12 or area < 180:
                continue
            if area > page_area * 0.86:
                continue
            if width > page.width * 0.68 or height > page.height * 0.58:
                continue
            if width > page.width * 0.42 and height < 34:
                continue
            if PDFVisualAssets._bbox_overlap_ratio(visual_bbox, text_bbox) > 0.65:
                continue

            center_x = (left + right) / 2
            center_y = (top + bottom) / 2
            horizontal_gap = max(left - text_right, text_left - right, 0)
            vertical_gap = max(top - text_bottom, text_top - bottom, 0)
            distance = ((center_x - text_center_x) ** 2 + (center_y - text_center_y) ** 2) ** 0.5

            nearby = (
                horizontal_gap <= max(220, text_width * 4)
                and vertical_gap <= max(240, text_height * 18)
            )
            same_band = (
                vertical_gap <= max(80, text_height * 7)
                and horizontal_gap <= max(360, text_width * 8)
            )
            above_label = (
                bottom <= text_top
                and vertical_gap <= max(160, text_height * 12)
                and abs(center_x - text_center_x) <= max(260, text_width * 6)
            )
            if not (nearby or same_band or above_label):
                continue

            score = distance + horizontal_gap * 0.9 + vertical_gap * 1.4
            if area < text_width * text_height * 2.5:
                score += 140
            candidates.append((score, visual_bbox))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        selected = [candidates[0][1]]
        best = candidates[0][1]
        for _, candidate in candidates[1:5]:
            if PDFVisualAssets._bbox_gap(best, candidate) <= 28:
                selected.append(candidate)

        return (
            min(item[0] for item in selected),
            min(item[1] for item in selected),
            max(item[2] for item in selected),
            max(item[3] for item in selected),
        )

    @staticmethod
    def _page_visual_objects(page) -> list[dict]:
        objects = []
        for name in ("images", "rects", "curves"):
            objects.extend(getattr(page, name, None) or [])
        return objects

    @staticmethod
    def _object_bbox(item: dict) -> tuple[float, float, float, float] | None:
        try:
            left = item.get("x0")
            right = item.get("x1")
            top = item.get("top")
            bottom = item.get("bottom")
            if top is None or bottom is None:
                y0 = item.get("y0")
                y1 = item.get("y1")
                if y0 is None or y1 is None:
                    return None
                top = min(y0, y1)
                bottom = max(y0, y1)
            if left is None or right is None:
                return None
            left, right = min(float(left), float(right)), max(float(left), float(right))
            top, bottom = min(float(top), float(bottom)), max(float(top), float(bottom))
            if right <= left or bottom <= top:
                return None
            return (left, top, right, bottom)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _bbox_overlap_ratio(
        a: tuple[float, float, float, float],
        b: tuple[float, float, float, float],
    ) -> float:
        left = max(a[0], b[0])
        top = max(a[1], b[1])
        right = min(a[2], b[2])
        bottom = min(a[3], b[3])
        if right <= left or bottom <= top:
            return 0
        overlap = (right - left) * (bottom - top)
        smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
        return overlap / max(1, smaller)

    @staticmethod
    def _bbox_gap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
        horizontal = max(a[0] - b[2], b[0] - a[2], 0)
        vertical = max(a[1] - b[3], b[1] - a[3], 0)
        return (horizontal ** 2 + vertical ** 2) ** 0.5

    @staticmethod
    def _clamp_bbox(
        bbox: tuple[float, float, float, float],
        page_width: float,
        page_height: float,
    ) -> tuple[float, float, float, float]:
        left, top, right, bottom = bbox
        return (
            max(0, left),
            max(0, top),
            min(page_width, right),
            min(page_height, bottom),
        )

    @staticmethod
    def _expanded_bbox(
        bbox: tuple[float, float, float, float],
        page_width: float,
        page_height: float,
    ) -> tuple[float, float, float, float]:
        left, top, right, bottom = bbox
        width = right - left
        height = bottom - top
        return PDFVisualAssets._clamp_bbox(
            (
                left - max(105, width * 1.15),
                top - max(60, height * 4.5),
                right + max(150, width * 1.35),
                bottom + max(135, height * 8),
            ),
            page_width,
            page_height,
        )

    @staticmethod
    def _normalize_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (value or "").lower())

    @staticmethod
    def _safe_filename(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
        return normalized[:64]
