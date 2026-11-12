#!/usr/bin/env python3
"""Copy only public static-site files into _site for GitHub Pages."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "_site"
if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir()
for page in ROOT.glob("*.html"):
    shutil.copy2(page, DEST / page.name)
shutil.copytree(ROOT / "assets", DEST / "assets")
print(f"Built {len(list(DEST.glob('*.html')))} HTML pages into {DEST.name}/")
