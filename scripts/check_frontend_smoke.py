#!/usr/bin/env python3
"""Static smoke checks for the frontend shell."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"

ALLOWED_INLINE_STYLE_IDS = {
    "sec-chart",
    "sec-verdict",
    "sec-rules",
    "cautionCard",
    "cautionVerdict",
}


class FrontendParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, {key: value or "" for key, value in attrs}))


def add(failures: list[str], condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def strip_query(path: str) -> str:
    return urlsplit(path).path


def hash_json_ld(html: str) -> str:
    match = re.search(
        r'<script type="application/ld\+json">\n(.*?)\n\s*</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        return ""
    digest = hashlib.sha256(match.group(1).encode()).digest()
    return "sha256-" + base64.b64encode(digest).decode()


def css_imports(css: str) -> list[tuple[str, str]]:
    return re.findall(r'@import url\("\./css/([^"]+?\.css)\?([^"]+)"\);', css)


def check() -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    html = INDEX.read_text(encoding="utf-8")
    parser = FrontendParser()
    parser.feed(html)

    tags = parser.tags
    ids = {attrs["id"] for _tag, attrs in tags if attrs.get("id")}
    meta_by_name = {
        attrs.get("name"): attrs.get("content", "")
        for tag, attrs in tags
        if tag == "meta" and attrs.get("name")
    }
    meta_by_property = {
        attrs.get("property"): attrs.get("content", "")
        for tag, attrs in tags
        if tag == "meta" and attrs.get("property")
    }

    stylesheets = [
        attrs.get("href", "")
        for tag, attrs in tags
        if tag == "link" and attrs.get("rel") == "stylesheet"
    ]
    module_scripts = [
        attrs.get("src", "")
        for tag, attrs in tags
        if tag == "script" and attrs.get("type") == "module"
    ]
    inline_scripts = [
        attrs
        for tag, attrs in tags
        if tag == "script" and not attrs.get("src")
    ]

    add(failures, len(stylesheets) == 1, "expected exactly one stylesheet")
    add(failures, len(module_scripts) == 1, "expected exactly one module script")
    if stylesheets:
        add(failures, strip_query(stylesheets[0]) == "assets/app.css", "stylesheet must be assets/app.css")
        add(failures, (ROOT / strip_query(stylesheets[0])).is_file(), "stylesheet file is missing")
    if module_scripts:
        add(failures, strip_query(module_scripts[0]) == "assets/app.js", "module script must be assets/app.js")
        add(failures, (ROOT / strip_query(module_scripts[0])).is_file(), "module script file is missing")
    if stylesheets and module_scripts:
        css_version = urlsplit(stylesheets[0]).query
        js_version = urlsplit(module_scripts[0]).query
        add(failures, css_version and css_version == js_version, "CSS and JS asset versions must match")

    add(
        failures,
        len(inline_scripts) == 1 and inline_scripts[0].get("type") == "application/ld+json",
        "only JSON-LD may remain as an inline script",
    )

    required_meta_names = {
        "description",
        "robots",
        "application-name",
        "theme-color",
        "color-scheme",
        "twitter:card",
        "twitter:title",
        "twitter:description",
    }
    for name in sorted(required_meta_names):
        add(failures, bool(meta_by_name.get(name)), f"missing meta name={name}")

    for prop in ("og:type", "og:locale", "og:site_name", "og:title", "og:description", "og:url"):
        add(failures, bool(meta_by_property.get(prop)), f"missing meta property={prop}")

    canonical = [
        attrs.get("href", "")
        for tag, attrs in tags
        if tag == "link" and attrs.get("rel") == "canonical"
    ]
    add(failures, len(canonical) == 1 and canonical[0].startswith("https://"), "missing canonical URL")

    for tag, attrs in tags:
        style = attrs.get("style")
        if not style:
            continue
        element_id = attrs.get("id", "")
        add(
            failures,
            element_id in ALLOWED_INLINE_STYLE_IDS and style.strip().replace(" ", "") == "display:none",
            f"unexpected inline style on <{tag}> id={element_id!r}",
        )

    for tag, attrs in tags:
        if attrs.get("role") == "tab":
            controls = attrs.get("aria-controls", "")
            add(failures, controls in ids, f"tab {attrs.get('id')} controls missing panel {controls}")
            add(failures, attrs.get("aria-selected") in {"true", "false"}, f"tab {attrs.get('id')} missing aria-selected")
        if attrs.get("role") == "tabpanel":
            labelledby = attrs.get("aria-labelledby", "")
            add(failures, labelledby in ids, f"tabpanel {attrs.get('id')} labelledby missing tab {labelledby}")

    add(failures, "searchResults" in ids, "missing searchResults container")
    add(failures, "searchInput" in ids, "missing searchInput")
    add(
        failures,
        'id="searchResults" aria-label="검색 결과" aria-live="polite" aria-busy="false"' in html,
        "searchResults must remain a polite live region",
    )

    json_ld_hash = hash_json_ld(html)
    add(failures, bool(json_ld_hash), "missing JSON-LD hash source")
    if json_ld_hash:
        add(failures, json_ld_hash in (ROOT / "lib/http_utils.py").read_text(encoding="utf-8"), "JSON-LD hash missing from lib/http_utils.py CSP")
        add(failures, json_ld_hash in (ROOT / "vercel.json").read_text(encoding="utf-8"), "JSON-LD hash missing from vercel.json CSP")

    css = (ROOT / "assets/app.css").read_text(encoding="utf-8")
    css_modules: list[str] = []
    imports = css_imports(css)
    add(failures, bool(imports), "app.css must import split CSS modules")
    if stylesheets:
        css_version = urlsplit(stylesheets[0]).query
        for path, version in imports:
            add(failures, version == css_version, f"CSS module version must match app.css: {path}")
            module_path = ROOT / "assets/css" / path
            add(failures, module_path.is_file(), f"CSS module is missing: assets/css/{path}")
            if module_path.is_file():
                css_modules.append(module_path.read_text(encoding="utf-8"))
    css_bundle = css + "\n".join(css_modules)
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    secondary_pages = ROOT / "assets/secondary_pages.js"
    trading_calendar = ROOT / "assets/trading_calendar.js"
    add(failures, secondary_pages.is_file(), "secondary pages module is missing")
    add(failures, trading_calendar.is_file(), "trading calendar module is missing")
    secondary_js = secondary_pages.read_text(encoding="utf-8") if secondary_pages.is_file() else ""
    calendar_js = trading_calendar.read_text(encoding="utf-8") if trading_calendar.is_file() else ""

    # 분할된 sub-modules (assets/app/*.js)
    state_path = ROOT / "assets/app/state.js"
    dom_utils_path = ROOT / "assets/app/dom_utils.js"
    warning_render_path = ROOT / "assets/app/warning_render.js"
    chart_path = ROOT / "assets/app/chart.js"
    search_path = ROOT / "assets/app/search.js"
    calendar_module_path = ROOT / "assets/app/calendar.js"
    sub_module_paths = (
        state_path, dom_utils_path, warning_render_path,
        chart_path, search_path, calendar_module_path,
    )
    for path in sub_module_paths:
        add(failures, path.is_file(), f"sub-module missing: {path.relative_to(ROOT)}")
    state_js = state_path.read_text(encoding="utf-8") if state_path.is_file() else ""
    dom_utils_js = dom_utils_path.read_text(encoding="utf-8") if dom_utils_path.is_file() else ""

    for marker in ("@media (max-width: 767px)", "@media (max-width: 480px)", "@media (prefers-reduced-motion: reduce)"):
        add(failures, marker in css_bundle, f"missing CSS marker {marker}")
    # 부트 모듈은 글로벌 에러 핸들러만 책임
    for marker in ("window.addEventListener('error'", "window.addEventListener('unhandledrejection'"):
        add(failures, marker in js, f"missing JS marker {marker} in app.js")
    # 상태/페치는 분할 모듈에 위치
    add(failures, "export const appState" in state_js, "missing 'export const appState' in app/state.js")
    add(failures, "export async function fetchJson" in dom_utils_js, "missing 'export async function fetchJson' in app/dom_utils.js")

    # 모든 versioned import의 버전이 app.js의 모듈 스크립트 버전과 일치해야 함.
    # urlsplit("?v=20260426-4").query → "v=20260426-4", 캡처는 prefix 없음 → 슬라이스로 정렬.
    raw_version = urlsplit(module_scripts[0]).query if module_scripts else ""
    expected_version = raw_version.removeprefix("v=") if raw_version else ""
    js_versioned_import_re = re.compile(
        r"""(?:from|import)\s+['"]\.{1,2}/[^'"]+?\.js\?v=([^'"]+)['"]"""
    )
    tracked_js_files = [
        ("app.js", js),
        ("secondary_pages.js", secondary_js),
        ("trading_calendar.js", calendar_js),
        *((p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"))
          for p in sub_module_paths if p.is_file()),
    ]
    for label, source in tracked_js_files:
        for match in js_versioned_import_re.finditer(source):
            add(
                failures,
                match.group(1) == expected_version,
                f"asset version mismatch in {label}: {match.group(0)} vs app.js={expected_version}",
            )
    add(failures, bool(js_versioned_import_re.search(js)), "app.js must import sub-modules with versioned URLs")

    for marker in ("function renderFortune", "async function renderPatchNotes"):
        add(failures, marker in secondary_js, f"missing secondary pages marker {marker}")
    for marker in ("function addTradingDays", "function countTradingDays"):
        add(failures, marker in calendar_js, f"missing trading calendar marker {marker}")

    # 원시 fetch( 호출은 fetchJson 내부 1곳에서만 허용 — app.js와 sub-modules 통틀어 1번
    fetch_count = (
        js.count("fetch(")
        + sum(p.read_text(encoding="utf-8").count("fetch(") for p in sub_module_paths if p.is_file())
        + secondary_js.count("fetch(")
    )
    add(failures, fetch_count == 1, "raw fetch() should only appear in fetchJson")
    add(failures, "alert(" not in js, "blocking alert() should not be used for app errors")

    add(failures, (ROOT / "robots.txt").is_file(), "robots.txt is missing")
    add(failures, (ROOT / "sitemap.xml").is_file(), "sitemap.xml is missing")
    try:
        ET.parse(ROOT / "sitemap.xml")
    except ET.ParseError as exc:
        failures.append(f"sitemap.xml is invalid: {exc}")

    summary = {
        "asset_versions": {
            "css": urlsplit(stylesheets[0]).query if stylesheets else "",
            "js": urlsplit(module_scripts[0]).query if module_scripts else "",
        },
        "json_ld_hash": json_ld_hash,
        "ids": len(ids),
        "failures": failures,
    }
    return failures, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run static frontend smoke checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    failures, summary = check()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif failures:
        print("Frontend smoke check failed:")
        for failure in failures:
            print(f"- {failure}")
    else:
        print("Frontend smoke check passed")
        print(f"Asset version: {summary['asset_versions']['css']}")
        print(f"JSON-LD CSP hash: {summary['json_ld_hash']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
