#!/usr/bin/env python3
import os
import sys
import json
import requests

# Try to load COMICVINE_API_KEY from a .env if present
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore

    load_dotenv(find_dotenv())
except Exception:
    pass

# Optional Simyan support
try:
    from simyan.comicvine import Comicvine  # type: ignore
    from simyan.sqlite_cache import SQLiteCache  # type: ignore
    from simyan.exceptions import ServiceError as SimyanServiceError  # type: ignore
except Exception:
    Comicvine = None  # type: ignore
    SQLiteCache = None  # type: ignore

    class SimyanServiceError(Exception):  # type: ignore
        pass


API = "https://comicvine.gamespot.com/api/issue/4000-{}/"
HEADERS = {"User-Agent": "weeklypulls/1.0"}

ORDER = [
    "medium_url",
    "super_url",
    "original_url",
    "screen_url",
    "small_url",
    "large_screen_url",
    "screen_large_url",
    "thumbnail",
    "thumb_url",
    "thumbnail_url",
    "tiny_url",
    "icon_url",
]


def pick_image_url(img: dict) -> str | None:
    if not isinstance(img, dict):
        return None
    for k in ORDER:
        url = img.get(k)
        if url:
            return url
    return None


# Helper that works with dicts or Simyan objects
def pick_image_url_any(img_obj) -> str | None:
    if not img_obj:
        return None
    # dict payload
    if isinstance(img_obj, dict):
        return pick_image_url(img_obj)
    # object payload
    for k in ORDER:
        try:
            val = getattr(img_obj, k, None)
        except Exception:
            val = None
        if val:
            return val
    return None


def main():
    api_key = os.environ.get("COMICVINE_API_KEY")
    if not api_key:
        print("Set COMICVINE_API_KEY in your environment")
        sys.exit(1)

    issue_id = sys.argv[1] if len(sys.argv) > 1 else "37099"
    params = {
        "api_key": api_key,
        "format": "json",
        "field_list": "id,name,issue_number,store_date,cover_date,site_detail_url,image,volume",
    }
    r = requests.get(API.format(issue_id), headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    payload = r.json()
    results = payload.get("results", {})

    out = {
        "id": results.get("id"),
        "name": results.get("name"),
        "issue_number": results.get("issue_number"),
        "store_date": results.get("store_date"),
        "cover_date": results.get("cover_date"),
        "site_detail_url": results.get("site_detail_url"),
        "volume": results.get("volume"),
        "image": results.get("image"),
    }
    out["best_image_url"] = pick_image_url(out.get("image") or {})

    print(json.dumps(out, indent=2))

    # Also fetch via Simyan (if available)
    try:
        if Comicvine is None or SQLiteCache is None:
            print(
                "\n[Simyan] Skipped (package not installed). Install with: python -m pip install simyan",
                file=sys.stderr,
            )
            return

        try:
            sid = int(issue_id)
        except ValueError:
            print(f"\n[Simyan] Invalid issue id: {issue_id}", file=sys.stderr)
            return

        cv = Comicvine(api_key=api_key, cache=SQLiteCache())
        issue = None
        # Prefer a direct get_issue if available
        if hasattr(cv, "get_issue"):
            try:
                issue = cv.get_issue(sid)
            except SimyanServiceError as e:
                print(f"\n[Simyan] get_issue failed: {e}", file=sys.stderr)
                issue = None
        # Fallback to listing by id filter
        if issue is None:
            try:
                items = cv.list_issues(params={"filter": f"id:{sid}"})
                issue = items[0] if items else None
            except Exception as e:
                print(f"\n[Simyan] list_issues fallback failed: {e}", file=sys.stderr)
                issue = None

        if not issue:
            print("\n[Simyan] No issue found", file=sys.stderr)
            return

        img_obj = getattr(issue, "image", None)
        simyan_out = {
            "id": getattr(issue, "id", None),
            "name": getattr(issue, "name", None),
            "number": getattr(issue, "number", None),
            "store_date": getattr(issue, "store_date", None),
            "cover_date": getattr(issue, "cover_date", None),
            "site_url": getattr(issue, "site_url", None),
            # Only extract simple image URL fields to keep JSON serializable
            "image": {k: getattr(img_obj, k, None) if img_obj else None for k in ORDER},
            "best_image_url": pick_image_url_any(img_obj),
        }

        print("\n# Simyan")
        print(json.dumps(simyan_out, indent=2, default=str))

    except Exception as e:
        print(f"\n[Simyan] Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
