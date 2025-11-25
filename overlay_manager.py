from __future__ import annotations
import os
from typing import Optional, Tuple, Dict
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtCore import QSize


class EffectManager:
    """Manages selection and fast compositing of PNG frame overlays over base frames.

    Usage:
      - set_effect(path) / clear_effect()
      - compose(base_image, target_size) -> QImage
        If base_image is None, a black background is used under the overlay.
      - on_output_resize(size) to refresh internal caches if needed.
    """

    def __init__(self) -> None:
        self._selected_path: Optional[str] = None
        self._effect_qimage: Optional[QImage] = None
        # Cache of scaled overlay per (w, h)
        self._scaled_cache: Dict[Tuple[int, int], QImage] = {}
        # For each cached size, remember scale result (scaled_w, scaled_h, off_x, off_y)
        self._scaled_geom: Dict[Tuple[int, int], Tuple[int, int, int, int]] = {}
        # Opening rect in normalized coordinates (x, y, w, h) relative to overlay
        self._opening_norm: Optional[Tuple[float, float, float, float]] = None
        # Cached opening mask per output size (alpha-only image with opening = opaque)
        self._mask_cache: Dict[Tuple[int, int], QImage] = {}

    def get_selected(self) -> Optional[str]:
        return self._selected_path

    def set_effect(self, path: str) -> bool:
        """Select an effect. Returns True on success."""
        try:
            if not path or not os.path.exists(path):
                return False
            img = QImage(path)
            if img.isNull():
                return False
            self._selected_path = path
            self._effect_qimage = img
            self._scaled_cache.clear()
            # 1) Try JSON sidecar override
            opening = self._load_opening_override(path)
            if opening is None:
                # 2) Try mask file
                opening = self._detect_opening_from_mask(path)
            if opening is None:
                # 3) Heuristic from alpha with connected components
                opening = self._detect_opening_norm(img)
            self._opening_norm = opening
            return True
        except Exception:
            return False

    def clear_effect(self) -> None:
        self._selected_path = None
        self._effect_qimage = None
        self._scaled_cache.clear()
        self._opening_norm = None
        self._scaled_geom.clear()
        self._mask_cache.clear()

    def on_output_resize(self, size: QSize) -> None:
        # Drop cache for new sizes
        key = (size.width(), size.height())
        if key not in self._scaled_cache:
            # keep small cache; if it grows, we could prune here
            pass
        # Opening mask depends on size as well
        if key in self._mask_cache:
            del self._mask_cache[key]

    def _get_scaled_overlay(self, size: QSize) -> Optional[QImage]:
        if not self._effect_qimage or size.isEmpty():
            return None
        key = (size.width(), size.height())
        cached = self._scaled_cache.get(key)
        if cached is not None and not cached.isNull():
            return cached
        # Scale with aspect preserved; center with offsets. Most frames are 16:9, but we do not assume.
        src = self._effect_qimage
        src_w, src_h = src.width(), src.height()
        dst_w, dst_h = size.width(), size.height()
        # Compute scaled size keeping aspect
        scale = min(dst_w / max(1, src_w), dst_h / max(1, src_h))
        scaled_w = max(1, int(src_w * scale))
        scaled_h = max(1, int(src_h * scale))
        off_x = (dst_w - scaled_w) // 2
        off_y = (dst_h - scaled_h) // 2
        scaled = src.scaled(scaled_w, scaled_h, aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                            transformMode=Qt.TransformationMode.SmoothTransformation)
        # Place scaled image into a full-size canvas to make draw simpler and to keep alpha
        canvas = QImage(size, QImage.Format.Format_ARGB32)
        canvas.fill(QColor(0, 0, 0, 0))
        p = QPainter(canvas)
        p.drawImage(off_x, off_y, scaled)
        p.end()
        self._scaled_cache[key] = canvas
        self._scaled_geom[key] = (scaled_w, scaled_h, off_x, off_y)
        return canvas

    def _get_opening_mask(self, size: QSize) -> Optional[QImage]:
        """Return an alpha mask image where the opening area is opaque (white) and others transparent.
        Cached per output size. Computed from the scaled overlay canvas (using transparency or bright fallback).
        """
        if size.isEmpty():
            return None
        key = (size.width(), size.height())
        cached = self._mask_cache.get(key)
        if cached is not None and not cached.isNull():
            return cached
        overlay_canvas = self._get_scaled_overlay(size)
        if overlay_canvas is None or overlay_canvas.isNull():
            return None
        w, h = size.width(), size.height()
        # Downscale analysis to reduce per-pixel cost
        analysis_w = min(640, max(64, w // 2))
        analysis_h = max(1, int(h * (analysis_w / max(1, w))))
        small = overlay_canvas.scaled(analysis_w, analysis_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        small = small.convertToFormat(QImage.Format.Format_ARGB32)

        # First pass: determine mode (transparent alpha vs bright area)
        alpha_thresh = 10
        transparent_pixels = 0
        for yy in range(small.height()):
            for xx in range(small.width()):
                if small.pixelColor(xx, yy).alpha() < alpha_thresh:
                    transparent_pixels += 1
        use_bright = transparent_pixels < (small.width() * small.height() * 0.02)

        # Build small binary mask
        mask_small = QImage(small.size(), QImage.Format.Format_Alpha8)
        mask_small.fill(0)
        open_pixels = 0
        for yy in range(small.height()):
            for xx in range(small.width()):
                c = small.pixelColor(xx, yy)
                open_here = (c.alpha() < alpha_thresh) if not use_bright else (
                    (max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) <= 20) and
                    (max(c.red(), c.green(), c.blue()) >= 230) and c.alpha() > 200
                )
                if open_here:
                    mask_small.setPixel(xx, yy, 255)
                    open_pixels += 1

        if open_pixels < max(50, int(mask_small.width() * mask_small.height() * 0.005)):
            self._mask_cache[key] = QImage()
            return None

        # Scale mask up to target size with smooth interpolation and threshold to crisp alpha
        mask_up = mask_small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        final_mask = QImage(size, QImage.Format.Format_ARGB32)
        final_mask.fill(QColor(0, 0, 0, 0))
        for y in range(h):
            for x in range(w):
                a = mask_up.pixelColor(x, y).red()  # grayscale
                if a >= 128:
                    final_mask.setPixelColor(x, y, QColor(255, 255, 255, 255))

        self._mask_cache[key] = final_mask
        return final_mask

    def _detect_opening_norm(self, img: QImage) -> Optional[Tuple[float, float, float, float]]:
        """Detect the frame 'hole' by scanning alpha on a downscaled copy.
        Returns normalized rect (x, y, w, h) in [0,1] or None if not found.
        Heuristics:
          - downscale to ~320px width for speed
          - treat alpha < 10 as transparent
          - ignore a border margin to avoid counting outer transparency
        """
        try:
            if img.isNull():
                return None
            target_w = 320
            if img.width() < target_w:
                small = img.convertToFormat(QImage.Format.Format_ARGB32)
            else:
                small = img.scaledToWidth(target_w, transformMode=Qt.TransformationMode.FastTransformation)
                small = small.convertToFormat(QImage.Format.Format_ARGB32)
            w = small.width()
            h = small.height()
            if w <= 10 or h <= 10:
                return None
            margin = max(4, w // 40)  # ~2.5% margin
            alpha_thresh = 10
            # Build binary mask for transparency
            mask = [[0]*w for _ in range(h)]
            for y in range(h):
                for x in range(w):
                    a = small.pixelColor(x, y).alpha()
                    mask[y][x] = 1 if a < alpha_thresh else 0
            # Flood-fill to find connected components; skip ones touching border
            visited = [[False]*w for _ in range(h)]
            best_area = 0
            best_bbox = None
            from collections import deque
            dirs = ((1,0),(-1,0),(0,1),(0,-1))
            for y0 in range(margin, h - margin):
                for x0 in range(margin, w - margin):
                    if mask[y0][x0] == 1 and not visited[y0][x0]:
                        q = deque()
                        q.append((x0,y0))
                        visited[y0][x0] = True
                        min_x=min_y=10**9
                        max_x=max_y=-1
                        area=0
                        touches_border=False
                        while q:
                            x,y = q.popleft()
                            area+=1
                            if x<min_x: min_x=x
                            if y<min_y: min_y=y
                            if x>max_x: max_x=x
                            if y>max_y: max_y=y
                            if x==0 or y==0 or x==w-1 or y==h-1:
                                touches_border=True
                            for dx,dy in dirs:
                                nx_=x+dx; ny_=y+dy
                                if 0<=nx_<w and 0<=ny_<h and not visited[ny_][nx_] and mask[ny_][nx_]==1:
                                    visited[ny_][nx_]=True
                                    q.append((nx_,ny_))
                        if not touches_border and area>best_area:
                            best_area=area
                            best_bbox=(min_x,min_y,max_x,max_y)
            if not best_bbox:
                # Fallback: detect bright, low-saturation region as opening (for frames with white/cream holes)
                def is_bright_low_sat(c):
                    r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
                    if a < 200:
                        return False
                    maxc = max(r, g, b)
                    minc = min(r, g, b)
                    # Low saturation threshold and bright
                    return (maxc - minc) <= 20 and maxc >= 230

                mask2 = [[0]*w for _ in range(h)]
                for yy in range(h):
                    for xx in range(w):
                        c = small.pixelColor(xx, yy)
                        mask2[yy][xx] = 1 if is_bright_low_sat(c) else 0
                visited2 = [[False]*w for _ in range(h)]
                best_area2 = 0
                best_bbox2 = None
                from collections import deque
                dirs = ((1,0),(-1,0),(0,1),(0,-1))
                for y0 in range(margin, h - margin):
                    for x0 in range(margin, w - margin):
                        if mask2[y0][x0] == 1 and not visited2[y0][x0]:
                            q = deque()
                            q.append((x0,y0))
                            visited2[y0][x0] = True
                            min_x=min_y=10**9
                            max_x=max_y=-1
                            area=0
                            touches_border=False
                            while q:
                                x,y = q.popleft()
                                area+=1
                                if x<min_x: min_x=x
                                if y<min_y: min_y=y
                                if x>max_x: max_x=x
                                if y>max_y: max_y=y
                                if x==0 or y==0 or x==w-1 or y==h-1:
                                    touches_border=True
                                for dx,dy in dirs:
                                    nx_=x+dx; ny_=y+dy
                                    if 0<=nx_<w and 0<=ny_<h and not visited2[ny_][nx_] and mask2[ny_][nx_]==1:
                                        visited2[ny_][nx_]=True
                                        q.append((nx_,ny_))
                            if not touches_border and area>best_area2:
                                best_area2=area
                                best_bbox2=(min_x,min_y,max_x,max_y)
                if not best_bbox2:
                    return None
                min_x,min_y,max_x,max_y = best_bbox2
            min_x,min_y,max_x,max_y = best_bbox
            # Normalize
            nx = min_x / float(w)
            ny = min_y / float(h)
            nw = (max_x - min_x + 1) / float(w)
            nh = (max_y - min_y + 1) / float(h)
            # Clamp
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))
            nw = max(0.05, min(1.0, nw))
            nh = max(0.05, min(1.0, nh))
            return (nx, ny, nw, nh)
        except Exception:
            return None

    def _detect_opening_from_mask(self, effect_path: str) -> Optional[Tuple[float, float, float, float]]:
        """If a side-by-side mask file exists (basename + '_mask.png'), use its white area as opening."""
        try:
            base, ext = os.path.splitext(effect_path)
            mask_path = base + '_mask.png'
            if not os.path.exists(mask_path):
                return None
            img = QImage(mask_path)
            if img.isNull():
                return None
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
            w, h = img.width(), img.height()
            # Find white area bbox (value>200 on all channels)
            min_x, min_y = w, h
            max_x, max_y = -1, -1
            for y in range(h):
                for x in range(w):
                    c = img.pixelColor(x, y)
                    if c.red()>200 and c.green()>200 and c.blue()>200 and c.alpha()>200:
                        if x<min_x: min_x=x
                        if y<min_y: min_y=y
                        if x>max_x: max_x=x
                        if y>max_y: max_y=y
            if max_x<=min_x or max_y<=min_y:
                return None
            return (min_x/float(w), min_y/float(h), (max_x-min_x+1)/float(w), (max_y-min_y+1)/float(h))
        except Exception:
            return None

    def _load_opening_override(self, effect_path: str) -> Optional[Tuple[float, float, float, float]]:
        """Load normalized opening rect from JSON sidecar (basename + .json) if present."""
        try:
            import json
            base, _ = os.path.splitext(effect_path)
            json_path = base + '.json'
            if not os.path.exists(json_path):
                return None
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            opening = data.get('opening')
            if (isinstance(opening, (list, tuple)) and len(opening)==4 and
                all(isinstance(v, (int,float)) for v in opening)):
                nx,ny,nw,nh = opening
                # basic clamp
                nx = max(0.0, min(1.0, float(nx)))
                ny = max(0.0, min(1.0, float(ny)))
                nw = max(0.01, min(1.0, float(nw)))
                nh = max(0.01, min(1.0, float(nh)))
                return (nx,ny,nw,nh)
            return None
        except Exception:
            return None

    def compose(self, base: Optional[QImage], target_size: QSize) -> QImage:
        """Return a new QImage of target_size with overlay applied over base.
        If base is None, draw a black background underneath.
        """
        # Prepare canvas
        result = QImage(target_size, QImage.Format.Format_ARGB32)
        result.fill(QColor(0, 0, 0, 255))

        # 1) Draw video into result (either full or inside detected rect)
        p = QPainter(result)
        try:
            if base and not base.isNull():
                # Compute target rect for base: prefer normalized opening rect mapped via scaled geometry
                key = (target_size.width(), target_size.height())
                geom = self._scaled_geom.get(key)
                if geom is None:
                    _ = self._get_scaled_overlay(target_size)
                    geom = self._scaled_geom.get(key)
                rx = ry = 0
                rw, rh = target_size.width(), target_size.height()
                if self._opening_norm is not None and geom is not None:
                    nx, ny, nw, nh = self._opening_norm
                    scaled_w, scaled_h, off_x, off_y = geom
                    rx = off_x + int(nx * scaled_w)
                    ry = off_y + int(ny * scaled_h)
                    rw = max(1, int(nw * scaled_w))
                    rh = max(1, int(nh * scaled_h))
                # Scale base to fit within (rw, rh) and draw centered
                base_scaled = base.scaled(QSize(rw, rh), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                                          transformMode=Qt.TransformationMode.SmoothTransformation)
                x = rx + (rw - base_scaled.width()) // 2
                y = ry + (rh - base_scaled.height()) // 2
                p.drawImage(x, y, base_scaled)
        finally:
            p.end()

        # 2) Clip result strictly to opening via alpha mask
        mask = self._get_opening_mask(target_size)
        if mask and not mask.isNull():
            clipped = QImage(target_size, QImage.Format.Format_ARGB32)
            clipped.fill(QColor(0, 0, 0, 0))
            p2 = QPainter(clipped)
            try:
                # Draw result, then keep only where mask is opaque
                p2.drawImage(0, 0, result)
                p2.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                p2.drawImage(0, 0, mask)
            finally:
                p2.end()
            result = clipped

        # 3) Draw overlay on top
        overlay = self._get_scaled_overlay(target_size)
        if overlay and not overlay.isNull():
            p3 = QPainter(result)
            try:
                p3.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                p3.drawImage(0, 0, overlay)
            finally:
                p3.end()

        return result

try:
    # Late import to avoid circular at module import time
    from PyQt6.QtCore import Qt
except Exception:
    # In case Qt is not available at import time, set a stub; real Qt is required at runtime
    class _QtStub:
        class TransformationMode:
            SmoothTransformation = 0
        class AspectRatioMode:
            KeepAspectRatio = 0
    Qt = _QtStub()  # type: ignore
