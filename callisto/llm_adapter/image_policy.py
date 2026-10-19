"""Bounded inference-only transforms; original images and normalized coordinates stay intact.

EXIF rotation is removed, not applied: device coordinates use stored pixels.
No crop/rotation is introduced. Pixel consumers can map via ImageGeometry.
"""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
from io import BytesIO
import threading
import warnings

from PIL import Image

from callisto.llm_adapter.errors import CLIProtocolError

PRESETS = {"off": (None, None), "balanced": (1920, 80), "quality": (2560, 90), "economy": (1440, 75)}
MIMES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
MAX_PIXELS = 32_000_000
MAX_EDGE = 32768
CACHE_BYTES = 16_000_000
_CACHE = OrderedDict()
_LOCK = threading.Lock()


@dataclass(frozen=True)
class ImageGeometry:
    original: tuple[int, int]
    transmitted: tuple[int, int]

    def original_point(self, x, y):
        w, h = self.transmitted
        if not 0 <= x <= w or not 0 <= y <= h:
            raise CLIProtocolError("Image coordinate lies outside the transmitted frame")
        return x * self.original[0] / w, y * self.original[1] / h


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime: str
    geometry: ImageGeometry
    original_mime: str
    original_bytes: int
    exif_orientation: int

    def metrics(self):
        return {"original_size": list(self.geometry.original), "size": list(self.geometry.transmitted),
                "original_bytes": self.original_bytes, "bytes": len(self.data),
                "original_mime": self.original_mime, "mime": self.mime,
                "exif_orientation": self.exif_orientation, "orientation": "stored_pixel_frame"}


def prepare_image(raw: bytes, policy="balanced"):
    if policy not in PRESETS:
        raise CLIProtocolError("Unknown image policy")
    key = (hashlib.sha256(raw).digest(), policy)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached:
            _CACHE.move_to_end(key)
            return cached
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                mime = MIMES.get(source.format)
                if mime is None or getattr(source, "n_frames", 1) != 1:
                    raise CLIProtocolError("Unsupported or animated image input")
                w, h = source.size
                if w * h > MAX_PIXELS or max(w, h) > MAX_EDGE:
                    raise CLIProtocolError("Image pixel/memory limit exceeded")
                orientation = source.getexif().get(274, 1)
                if orientation not in range(1, 9):
                    raise CLIProtocolError("Invalid image EXIF orientation")
                source.load()
                limit, quality = PRESETS[policy]
                if limit is None:
                    if orientation == 1:
                        data, out_mime, size = raw, mime, source.size
                    else:
                        output = BytesIO()
                        clean = Image.new("RGBA", source.size)
                        clean.paste(source.convert("RGBA"))
                        clean.save(output, format="PNG")
                        data, out_mime, size = output.getvalue(), "image/png", source.size
                else:
                    source.thumbnail((limit, limit), Image.Resampling.LANCZOS)
                    image = source.convert("RGBA")
                    background = Image.new("RGBA", image.size, "white")
                    background.alpha_composite(image)
                    image = background.convert("RGB")
                    image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
                    output = BytesIO()
                    image.save(output, format="JPEG", quality=quality)
                    data, out_mime, size = output.getvalue(), "image/jpeg", image.size
                result = PreparedImage(data, out_mime, ImageGeometry((w, h), size), mime, len(raw), orientation)
    except CLIProtocolError:
        raise
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise CLIProtocolError("Invalid image input; no attachment was omitted") from None
    with _LOCK:
        if len(result.data) <= CACHE_BYTES:
            _CACHE[key] = result
            while sum(len(v.data) for v in _CACHE.values()) > CACHE_BYTES or len(_CACHE) > 128:
                _CACHE.popitem(last=False)
    return result
