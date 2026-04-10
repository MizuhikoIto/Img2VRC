#!/usr/bin/env python3
"""Build a static slideshow from a recursive image directory."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

try:
    from PIL import Image, ImageOps
    PIL_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - depends on runtime setup
    Image = None
    ImageOps = None
    PIL_IMPORT_ERROR = exc


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class Config:
    gallery_dir: Path
    staging_dir: Path
    publish_dir: Path
    log_dir: Path
    state_dir: Path
    slide_count: int
    max_edge_px: int
    jpeg_quality: int
    public_base_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Randomly select photos and build a static slideshow."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Select files and validate configuration without writing output.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible selection.",
    )
    parser.add_argument(
        "--gallery-dir",
        type=Path,
        default=None,
        help="Override PIWIGO_GALLERY_DIR.",
    )
    parser.add_argument(
        "--publish-dir",
        type=Path,
        default=None,
        help="Override OUTPUT_PUBLISH_DIR.",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=None,
        help="Override OUTPUT_STAGING_DIR.",
    )
    return parser.parse_args()


def getenv_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def load_config(args: argparse.Namespace) -> Config:
    gallery_input = args.gallery_dir or os.environ.get("PIWIGO_GALLERY_DIR")
    if not gallery_input:
        raise ValueError("PIWIGO_GALLERY_DIR is required.")

    gallery_dir = Path(gallery_input).expanduser().resolve()
    staging_dir = (
        args.staging_dir or getenv_path("OUTPUT_STAGING_DIR", "output/staging")
    ).resolve()
    publish_dir = (
        args.publish_dir or getenv_path("OUTPUT_PUBLISH_DIR", "public")
    ).resolve()
    log_dir = getenv_path("LOG_DIR", "logs").resolve()
    state_dir = getenv_path("STATE_DIR", "state").resolve()

    slide_count = int(os.environ.get("SLIDE_COUNT", "15"))
    max_edge_px = int(os.environ.get("MAX_EDGE_PX", "2048"))
    jpeg_quality = int(os.environ.get("JPEG_QUALITY", "85"))
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "").strip()

    return Config(
        gallery_dir=gallery_dir,
        staging_dir=staging_dir,
        publish_dir=publish_dir,
        log_dir=log_dir,
        state_dir=state_dir,
        slide_count=slide_count,
        max_edge_px=max_edge_px,
        jpeg_quality=jpeg_quality,
        public_base_url=public_base_url,
    )


def setup_logging(log_dir: Path) -> tuple[logging.Logger, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"build_random_slides-{timestamp}.log"

    logger = logging.getLogger("build_random_slides")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger, log_path


def source_label(source_path: Path, gallery_dir: Path) -> str:
    try:
        return source_path.relative_to(gallery_dir).as_posix()
    except ValueError:
        return source_path.name


def iter_images(gallery_dir: Path) -> Iterable[Path]:
    for path in gallery_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def select_candidates(
    gallery_dir: Path, slide_count: int, rng: random.Random
) -> List[Path]:
    images = list(iter_images(gallery_dir))
    if len(images) < slide_count:
        raise RuntimeError(
            f"Not enough source images. required={slide_count} found={len(images)}"
        )
    rng.shuffle(images)
    return images


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def resize_and_save(
    source_path: Path, destination_path: Path, max_edge_px: int, jpeg_quality: int
) -> None:
    if PIL_IMPORT_ERROR is not None:
        raise RuntimeError(
            "Pillow is required for image conversion. Install it with "
            "`python3 -m pip install Pillow`."
        ) from PIL_IMPORT_ERROR

    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image.thumbnail((max_edge_px, max_edge_px), Image.Resampling.LANCZOS)
        image.save(
            destination_path,
            format="JPEG",
            quality=jpeg_quality,
            optimize=True,
            progressive=True,
        )


def write_manifest(
    output_dir: Path,
    generated_at: str,
    image_names: List[str],
    public_base_url: str,
) -> None:
    manifest = {
        "generated_at": generated_at,
        "count": len(image_names),
        "images": image_names,
    }
    if public_base_url:
        manifest["public_base_url"] = public_base_url

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "updated_at.txt").write_text(generated_at + "\n", encoding="utf-8")


def write_index_html(output_dir: Path, image_names: List[str], generated_at: str) -> None:
    images_json = json.dumps(image_names, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VRC World Travel Slideshow</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg-a: #07111f;
      --bg-b: #11253d;
      --fg: #f3f6fb;
      --muted: rgba(243, 246, 251, 0.72);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      color: var(--fg);
      background:
        radial-gradient(circle at top, rgba(140, 187, 255, 0.18), transparent 32%),
        linear-gradient(160deg, var(--bg-a), var(--bg-b));
      display: grid;
      place-items: center;
    }}
    main {{
      width: min(96vw, 1440px);
      padding: 24px;
    }}
    .frame {{
      position: relative;
      aspect-ratio: 16 / 9;
      border-radius: 18px;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.06);
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
    }}
    img {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: contain;
      opacity: 0;
      transition: opacity 900ms ease-in-out;
      background: rgba(0, 0, 0, 0.28);
    }}
    img.active {{ opacity: 1; }}
    .meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-top: 12px;
      font-size: 14px;
      color: var(--muted);
    }}
    @media (max-width: 700px) {{
      main {{ padding: 12px; }}
      .frame {{ aspect-ratio: 4 / 3; }}
      .meta {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="frame" id="frame"></div>
    <div class="meta">
      <span id="counter"></span>
      <span>Generated at {generated_at}</span>
    </div>
  </main>
  <script>
    const images = {images_json};
    const frame = document.getElementById("frame");
    const counter = document.getElementById("counter");
    const nodes = images.map((src, index) => {{
      const img = document.createElement("img");
      img.src = src;
      img.alt = `Slide ${{index + 1}}`;
      frame.appendChild(img);
      return img;
    }});

    let current = 0;
    const render = () => {{
      nodes.forEach((node, index) => {{
        node.classList.toggle("active", index === current);
      }});
      counter.textContent = `${{current + 1}} / ${{images.length}}`;
    }};

    render();
    if (nodes.length > 1) {{
      setInterval(() => {{
        current = (current + 1) % nodes.length;
        render();
      }}, 5000);
    }}
  </script>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def publish_directory(staging_dir: Path, publish_dir: Path, logger: logging.Logger) -> None:
    publish_parent = publish_dir.parent
    publish_parent.mkdir(parents=True, exist_ok=True)

    tmp_publish = Path(
        tempfile.mkdtemp(prefix=".publish-next-", dir=str(publish_parent))
    )
    backup_publish = publish_parent / f".publish-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    try:
        shutil.copytree(staging_dir, tmp_publish, dirs_exist_ok=True)

        if publish_dir.exists():
            logger.info("moving current publish to backup directory")
            publish_dir.rename(backup_publish)

        logger.info("promoting staged output to publish directory")
        tmp_publish.rename(publish_dir)

        if backup_publish.exists():
            shutil.rmtree(backup_publish)
    except Exception:
        logger.exception("failed while promoting staged output")
        if publish_dir.exists() and backup_publish.exists():
            shutil.rmtree(publish_dir)
            backup_publish.rename(publish_dir)
        elif (not publish_dir.exists()) and backup_publish.exists():
            backup_publish.rename(publish_dir)
        raise
    finally:
        if tmp_publish.exists():
            shutil.rmtree(tmp_publish)


def build_slideshow(config: Config, dry_run: bool, seed: int | None) -> int:
    logger, log_path = setup_logging(config.log_dir)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    rng = random.Random(seed)

    logger.info("build started")
    logger.info("slide_count=%s max_edge_px=%s jpeg_quality=%s", config.slide_count, config.max_edge_px, config.jpeg_quality)
    logger.info("log_file=%s", log_path.name)

    if not config.gallery_dir.is_dir():
        raise RuntimeError("gallery directory not found")

    candidates = select_candidates(config.gallery_dir, config.slide_count, rng)
    logger.info("candidate_count=%s", len(candidates))

    selected_sources: List[Path] = []
    planned_names = [f"{index:02d}.jpg" for index in range(1, config.slide_count + 1)]

    for source in candidates:
        selected_sources.append(source)
        if len(selected_sources) >= config.slide_count:
            break

    if dry_run:
        logger.info("dry-run selected sources:")
        for index, source in enumerate(selected_sources, start=1):
            logger.info(
                "%02d source=%s",
                index,
                source_label(source, config.gallery_dir),
            )
        logger.info("dry-run completed")
        return 0

    config.staging_dir.mkdir(parents=True, exist_ok=True)
    config.state_dir.mkdir(parents=True, exist_ok=True)

    run_staging_dir = config.staging_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
    ensure_clean_dir(run_staging_dir)

    image_names: List[str] = []
    converted_sources: List[str] = []
    candidate_iter = iter(candidates)

    try:
        while len(image_names) < config.slide_count:
            source = next(candidate_iter)
            destination_name = planned_names[len(image_names)]
            destination_path = run_staging_dir / destination_name
            logger.info(
                "processing source=%s destination=%s",
                source_label(source, config.gallery_dir),
                destination_name,
            )
            try:
                resize_and_save(
                    source,
                    destination_path,
                    max_edge_px=config.max_edge_px,
                    jpeg_quality=config.jpeg_quality,
                )
            except Exception:
                logger.exception(
                    "conversion failed for source=%s",
                    source_label(source, config.gallery_dir),
                )
                continue

            image_names.append(destination_name)
            converted_sources.append(source_label(source, config.gallery_dir))
    except StopIteration as exc:
        raise RuntimeError(
            f"unable to build {config.slide_count} slides from available images"
        ) from exc

    write_manifest(run_staging_dir, generated_at, image_names, config.public_base_url)
    write_index_html(run_staging_dir, image_names, generated_at)

    source_list_path = config.state_dir / "last_selected_sources.json"
    source_list_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "sources": converted_sources,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    publish_directory(run_staging_dir, config.publish_dir, logger)

    logger.info("selected_count=%s", len(converted_sources))
    for index, source in enumerate(converted_sources, start=1):
        logger.info("%02d selected=%s", index, source)
    logger.info("build completed successfully")
    return 0


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args)
        return build_slideshow(config, dry_run=args.dry_run, seed=args.seed)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
