#!/usr/bin/env python3
"""Sync frontend asset versions and JSON-LD CSP hashes."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
APP_CSS = ROOT / "assets/app.css"
APP_JS = ROOT / "assets/app.js"
HTTP_UTILS = ROOT / "lib/http_utils.py"
VERCEL = ROOT / "vercel.json"

# app.js, secondary_pages.js, trading_calendar.js, app/*.js 모두 자동 추적
JS_TRACKED_FILES = (
    APP_JS,
    ROOT / "assets/secondary_pages.js",
    ROOT / "assets/trading_calendar.js",
    *sorted((ROOT / "assets/app").glob("*.js")),
)

CSS_ASSET_RE = re.compile(
    r'(?P<prefix><link rel="stylesheet" href="assets/app\.css)'
    r'(?:\?v=(?P<version>[^"]+))?'
    r'(?P<suffix>" />)'
)
JS_ASSET_RE = re.compile(
    r'(?P<prefix><script type="module" src="assets/app\.js)'
    r'(?:\?v=(?P<version>[^"]+))?'
    r'(?P<suffix>"></script>)'
)
# JS 파일 안의 모든 versioned 모듈 import (정적/동적, 같은 폴더/상위 폴더)
JS_VERSIONED_IMPORT_RE = re.compile(
    r"""(?P<prefix>(?:from|import)\s+['"]\.{1,2}/[^'"]+?\.js)"""
    r"""(?:\?v=(?P<version>[^'"]+))?"""
    r"""(?P<suffix>['"])"""
)
CSS_IMPORT_RE = re.compile(
    r'(?P<prefix>@import url\("\./css/[^"]+?\.css)'
    r'(?:\?v=(?P<version>[^"]+))?'
    r'(?P<suffix>"\);)'
)
JSON_LD_RE = re.compile(
    r'<script type="application/ld\+json">\n(.*?)\n\s*</script>',
    flags=re.DOTALL,
)
CSP_HASH_RE = re.compile(r"sha256-[A-Za-z0-9+/=]+")


def json_ld_hash(html: str) -> str:
    match = JSON_LD_RE.search(html)
    if not match:
        raise ValueError("index.html JSON-LD script was not found")
    digest = hashlib.sha256(match.group(1).encode()).digest()
    return "sha256-" + base64.b64encode(digest).decode()


def _asset_version_key(version: str) -> tuple[int, int, int, str]:
    match = re.fullmatch(r"(\d{8})-(\d+)", version)
    if match:
        return (2, int(match.group(1)), int(match.group(2)), version)
    return (1, 0, 0, version)


def choose_asset_version(versions: list[str], override: str | None) -> str:
    if override:
        return override.removeprefix("v=").strip()
    versions = [v for v in versions if v]
    if not versions:
        raise ValueError("asset version is missing; pass --version YYYYMMDD-N")
    return max(versions, key=_asset_version_key)


def sync_assets(
    html: str,
    app_css: str,
    js_sources: dict[Path, str],
    version: str | None,
) -> tuple[str, str, dict[Path, str], str]:
    css_match = CSS_ASSET_RE.search(html)
    js_match = JS_ASSET_RE.search(html)
    css_import_matches = list(CSS_IMPORT_RE.finditer(app_css))
    if not css_match:
        raise ValueError("assets/app.css link was not found in index.html")
    if not js_match:
        raise ValueError("assets/app.js module script was not found in index.html")
    if not css_import_matches:
        raise ValueError("CSS module imports were not found in assets/app.css")

    js_versions = []
    for path, source in js_sources.items():
        js_versions.extend(match.group("version") or "" for match in JS_VERSIONED_IMPORT_RE.finditer(source))

    next_version = choose_asset_version(
        [
            css_match.group("version") or "",
            js_match.group("version") or "",
            *[match.group("version") or "" for match in css_import_matches],
            *js_versions,
        ],
        version,
    )

    def replace_asset(match: re.Match[str]) -> str:
        return f'{match.group("prefix")}?v={next_version}{match.group("suffix")}'

    html = CSS_ASSET_RE.sub(replace_asset, html, count=1)
    html = JS_ASSET_RE.sub(replace_asset, html, count=1)
    app_css = CSS_IMPORT_RE.sub(replace_asset, app_css)

    updated_js: dict[Path, str] = {}
    for path, source in js_sources.items():
        updated_js[path] = JS_VERSIONED_IMPORT_RE.sub(replace_asset, source)
    return html, app_css, updated_js, next_version


def sync_http_utils(text: str, csp_hash: str) -> str:
    next_text, count = CSP_HASH_RE.subn(csp_hash, text, count=1)
    if count != 1:
        raise ValueError("CSP hash was not found in lib/http_utils.py")
    return next_text


def sync_vercel(text: str, csp_hash: str) -> str:
    data = json.loads(text)
    found = False
    for block in data.get("headers", []):
        for header in block.get("headers", []):
            if header.get("key") == "Content-Security-Policy":
                found = True
                value = header.get("value", "")
                if CSP_HASH_RE.search(value):
                    return text.replace(
                        value,
                        CSP_HASH_RE.sub(csp_hash, value, count=1),
                        1,
                    )
    if not found:
        raise ValueError("Content-Security-Policy header was not found in vercel.json")
    raise ValueError("CSP hash was not found in vercel.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync index.html asset versions and JSON-LD CSP hashes.",
    )
    parser.add_argument(
        "--version",
        help="Set both app.css and app.js to this asset version, e.g. 20260425-8.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with status 1 if any file would be changed.",
    )
    args = parser.parse_args()

    js_paths = list(JS_TRACKED_FILES)
    original = {
        INDEX: INDEX.read_text(encoding="utf-8"),
        APP_CSS: APP_CSS.read_text(encoding="utf-8"),
        HTTP_UTILS: HTTP_UTILS.read_text(encoding="utf-8"),
        VERCEL: VERCEL.read_text(encoding="utf-8"),
        **{p: p.read_text(encoding="utf-8") for p in js_paths},
    }

    html, app_css, updated_js, asset_version = sync_assets(
        original[INDEX],
        original[APP_CSS],
        {p: original[p] for p in js_paths},
        args.version,
    )
    csp_hash = json_ld_hash(html)
    updated = {
        INDEX: html,
        APP_CSS: app_css,
        HTTP_UTILS: sync_http_utils(original[HTTP_UTILS], csp_hash),
        VERCEL: sync_vercel(original[VERCEL], csp_hash),
        **updated_js,
    }

    changed = [path for path, text in updated.items() if text != original[path]]
    if args.check:
        if changed:
            print("Frontend metadata is out of sync:")
            for path in changed:
                print(f"- {path.relative_to(ROOT)}")
            return 1
        print("Frontend metadata is in sync")
        return 0

    for path in changed:
        path.write_text(updated[path], encoding="utf-8")

    if changed:
        print("Synced frontend metadata:")
        for path in changed:
            print(f"- {path.relative_to(ROOT)}")
    else:
        print("Frontend metadata already in sync")
    print(f"Asset version: v={asset_version}")
    print(f"JSON-LD CSP hash: {csp_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
