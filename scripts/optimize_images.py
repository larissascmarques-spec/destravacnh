from pathlib import Path
from PIL import Image, ImageOps
import re, io, sys

root = Path(__file__).resolve().parents[1]
html_file = root / "index.html"
html = html_file.read_text(encoding="utf-8")
refs = sorted(set(re.findall(r'assets/[A-Za-z0-9_.-]+\.(?:png|jpe?g|webp)', html, flags=re.I)))
changes = []
for ref in refs:
    path = root / ref
    if not path.exists():
        raise RuntimeError(f"Missing referenced image: {ref}")
    try:
        with Image.open(path) as original:
            if getattr(original, "is_animated", False):
                continue
            image = ImageOps.exif_transpose(original)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
            target = path.with_suffix(".webp")
            buf = io.BytesIO()
            quality = 92 if "43cb0fcc3a5309" in path.name else 88
            image.save(buf, format="WEBP", quality=quality, method=6)
            data = buf.getvalue()
            if len(data) >= path.stat().st_size * 0.97:
                continue
            with Image.open(io.BytesIO(data)) as verify:
                assert verify.size == original.size
            target.write_bytes(data)
            html = html.replace(ref, str(target.relative_to(root)).replace("\\", "/"))
            if path != target:
                path.unlink()
            changes.append((ref, len(data)))
    except Exception as e:
        raise RuntimeError(f"Image optimization failed for {ref}: {e}") from e

# Prevent late-loading images from competing with the main product mockup.
html = re.sub(r'<img(?![^>]*class="hero-mockup")([^>]*?)>', lambda m:
    '<img' + m.group(1).replace('decoding="sync"', 'decoding="async"') + '>' if 'loading=' in m.group(1) else
    '<img loading="lazy" decoding="async"' + m.group(1) + '>', html)
# The hero must be eagerly requested and should never be lazy-loaded.
html = re.sub(r'(<img[^>]*class="hero-mockup"[^>]*)(/?>)', lambda m:
    m.group(1).replace('loading="lazy"', '').replace('decoding="sync"', 'decoding="async"') + m.group(2), html)
html_file.write_text(html, encoding="utf-8")
print(f"Optimized {len(changes)} images")
for name, size in changes:
    print(f"{name}: {size:,} bytes")
