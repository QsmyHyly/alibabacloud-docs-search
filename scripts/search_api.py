#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_api.py - Search and extract API information from
https://help.aliyun.com/zh/model-studio/api-aimiaobi-2023-08-01-dir/

Architecture:
  - API目录 page (-dir/) -> links to category pages (-dir-xxx/)
  - Each category page -> lists individual API endpoints (e.g. "CreateToken - 获取授权token")

Usage:
    python scripts/search_api.py                              # List all API categories
    python scripts/search_api.py --keyword "生成"              # Search API endpoints
    python scripts/search_api.py --category "妙笔"             # Filter by category
    python scripts/search_api.py --detail "<api-url-slug>"     # Get API detail page

Output: JSON
"""

import asyncio
import argparse
import json
from shared_browser import acquire_browser_session, cleanup_browser_session


BASE_URL = "https://help.aliyun.com"
API_DIR_URL = f"{BASE_URL}/zh/model-studio/api-aimiaobi-2023-08-01-dir/"


async def list_apis(keyword="", category="", expand_categories=False):
    """Extract API directory listing."""
    browser, pw, page, is_daemon = await acquire_browser_session(API_DIR_URL)
    try:
        await page.goto(API_DIR_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Find all API category links (href contains api-aimiaobi-2023-08-01-dir- but not just -dir/)
        all_links = await page.query_selector_all("a[href]")
        category_links = []
        for link in all_links:
            href = await link.get_attribute("href")
            text = (await link.inner_text()).strip()
            if (href
                and "/api-aimiaobi-2023-08-01-dir-" in href
                and not href.endswith("/api-aimiaobi-2023-08-01-dir/")
                and text
                and len(text) < 50
            ):
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                category_links.append({"name": text, "url": full_url, "href": href})

        # Deduplicate
        seen = set()
        unique_categories = []
        for cl in category_links:
            if cl["href"] not in seen:
                seen.add(cl["href"])
                unique_categories.append(cl)

        # Build result
        apis = {}
        for cat in unique_categories:
            cat_name = cat["name"]

            # Filter by category keyword
            if category and category not in cat_name:
                continue

            apis[cat_name] = {
                "url": cat["url"],
                "endpoints": []  # Will be populated if expand_categories=True
            }

        # Optionally fetch each category page to get individual endpoints
        if expand_categories:
            for cat_name, cat_info in apis.items():
                try:
                    await page.goto(cat_info["url"], wait_until="networkidle", timeout=15000)
                    await asyncio.sleep(1)
                    body_text = (await page.inner_text("body")).strip()

                    # Extract API endpoints from the page text
                    # Format: "ApiName - 描述" or just lines that look like API names
                    seen_eps = set()
                    for line in body_text.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        # API endpoint lines contain " - " (e.g. "CreateToken - 获取授权token")
                        if " - " in line and len(line) < 100:
                            parts = line.split(" - ", 1)
                            api_name = parts[0].strip()
                            desc = parts[1].strip()
                            ep_key = f"{api_name}-{desc}"
                            if ep_key not in seen_eps:
                                seen_eps.add(ep_key)
                                apis[cat_name]["endpoints"].append({
                                    "api_name": api_name,
                                    "description": desc
                                })
                        # Also catch lines that look like API names (camelCase, starts with uppercase)
                        elif line[0:1].isupper() and len(line) < 50 and not any(c in line for c in ["，", "。", "、"]):
                            # Skip if it's a navigation element
                            skip_words = ["上一篇", "下一篇", "更新时间", "我的收藏", "产品详情",
                                          "为什么选择", "大模型", "通义", "产品", "解决",
                                          "免费", "联系", "法律", "隐私", "Cookie",
                                          "©", "浙公", "阿里", "关注", "登录", "注册"]
                            if not any(w in line for w in skip_words):
                                # Check if it looks like an API name
                                if line.replace("-", "").replace("_", "").replace(" ", "").isalnum() or " - " in line:
                                    continue  # Already handled above
                except:
                    pass

        # Filter by keyword across all categories
        if keyword:
            filtered = {}
            for cat_name, cat_info in apis.items():
                matched_endpoints = []
                for ep in cat_info.get("endpoints", []):
                    if (keyword in ep.get("api_name", "")
                        or keyword in ep.get("description", "")
                        or keyword in cat_name):
                        matched_endpoints.append(ep)
                if matched_endpoints or keyword in cat_name:
                    filtered[cat_name] = {
                        "url": cat_info["url"],
                        "endpoints": matched_endpoints if matched_endpoints else cat_info["endpoints"]
                    }
            apis = filtered

        return {
            "keyword": keyword,
            "category": category,
            "total_categories": len(apis),
            "categories": apis
        }
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def get_api_detail(api_url_slug):
    """Fetch a specific API endpoint detail page."""
    if api_url_slug.startswith("http"):
        url = api_url_slug
    elif "/zh/" in api_url_slug:
        url = f"{BASE_URL}{api_url_slug}"
    else:
        url = f"{BASE_URL}/zh/model-studio/{api_url_slug}"

    browser, pw, page, is_daemon = await acquire_browser_session(url)
    try:
        await page.goto(url, wait_until="networkidle", timeout=15000)
        await asyncio.sleep(1)
        title = await page.title()
        content = (await page.inner_text("body")).strip()[:5000]
        final_url = page.url

        return {
            "url": final_url,
            "title": title,
            "content": content[:3000]
        }
    except Exception as e:
        return {
            "error": f"Failed to fetch: {str(e)}",
            "suggestion": f"Visit {API_DIR_URL} to find the correct API endpoint URL"
        }
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def main():
    parser = argparse.ArgumentParser(description="Search Alibaba Cloud Model Studio APIs")
    parser.add_argument("--keyword", "-k", default="", help="Search API endpoints by keyword")
    parser.add_argument("--category", "-c", default="", help="Filter by API category")
    parser.add_argument("--expand", "-e", action="store_true", help="Expand categories to show individual API endpoints")
    parser.add_argument("--detail", "-d", default="", help="Get detail of specific API (URL slug or full URL)")
    args = parser.parse_args()

    if args.detail:
        result = await get_api_detail(args.detail)
    else:
        result = await list_apis(
            keyword=args.keyword,
            category=args.category,
            expand_categories=args.expand
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
