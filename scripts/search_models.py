#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_models.py - Search and extract model information from
https://help.aliyun.com/zh/model-studio/models

Usage:
    python scripts/search_models.py                          # List flagship models (default region: 中国内地)
    python scripts/search_models.py --region 全球              # Switch region
    python scripts/search_models.py --keyword "Qwen3"         # Search/filter models
    python scripts/search_models.py --expand                   # Expand all "更多模型" sections
    python scripts/search_models.py --category "文本生成"      # Filter by category

Output: JSON
"""

import asyncio
import argparse
import json
import re
from shared_browser import acquire_browser_session, cleanup_browser_session


BASE_URL = "https://help.aliyun.com"
MODELS_URL = f"{BASE_URL}/zh/model-studio/models"
REGIONS = ["中国内地", "全球", "国际", "美国"]


async def extract_models(keyword="", region="", expand=False, category=""):
    """Extract model info from the models page."""
    browser, pw, page, is_daemon = await acquire_browser_session(MODELS_URL)
    try:
        await page.goto(MODELS_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Switch region if specified
        if region:
            region_tabs = await page.query_selector_all(".tab-item")
            for tab in region_tabs:
                tab_text = (await tab.inner_text()).strip()
                if tab_text == region:
                    await tab.click()
                    await asyncio.sleep(2)
                    break

        # Click all expandable sections if requested
        expanded_count = 0
        if expand:
            expand_buttons = await page.query_selector_all(".expandable-title-bold, .expandable-title")
            for btn in expand_buttons:
                try:
                    await btn.click()
                    expanded_count += 1
                    await asyncio.sleep(0.3)
                except:
                    pass

        # Get full page text content
        body_text = (await page.inner_text("body")).strip()

        results = {
            "region": region or "中国内地",
            "flagship_models": [],
            "categories": [],
            "raw_text_length": len(body_text)
        }

        lines = body_text.split("\n")

        in_flagship = False
        in_category = False
        current_category = ""
        category_items = []

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            if line in ["旗舰模型", "Qwen3-Max", "Qwen3.6-Plus", "Qwen3.5-Flash"]:
                in_flagship = True

            category_keywords = ["文本生成", "图像生成", "图像编辑", "语音合成与识别",
                               "语音识别", "视频编辑与生成", "文生视频", "图生视频",
                               "向量", "行业", "多模态模型", "领域模型"]
            if any(kw in line for kw in category_keywords) and len(line) < 20:
                in_category = True
                in_flagship = False
                if current_category and category_items:
                    results["categories"].append({
                        "name": current_category,
                        "models": category_items
                    })
                current_category = line
                category_items = []
                continue

            if in_flagship and line.startswith("Qwen"):
                desc = lines[i+1].strip() if i+1 < len(lines) else ""
                results["flagship_models"].append({
                    "name": line,
                    "description": desc if desc and not desc.startswith("适合") else ""
                })

            if in_category:
                if line and len(line) > 2:
                    category_items.append(line)

        if current_category and category_items:
            results["categories"].append({
                "name": current_category,
                "models": category_items
            })

        # Filter by keyword if specified
        if keyword:
            filtered_flagship = [m for m in results["flagship_models"]
                                 if keyword.lower() in m["name"].lower()
                                 or keyword in m.get("description", "").lower()]
            results["flagship_models"] = filtered_flagship

            filtered_categories = []
            for cat in results["categories"]:
                matched_models = [m for m in cat["models"] if keyword in m]
                if matched_models or keyword in cat["name"]:
                    filtered_categories.append({
                        "name": cat["name"],
                        "models": matched_models if matched_models else cat["models"]
                    })
            results["categories"] = filtered_categories

        # Extract pricing tables
        pricing_tables = []
        tables = await page.query_selector_all("table")
        for table in tables:
            rows = await table.query_selector_all("tr")
            if len(rows) >= 3:
                row_texts = []
                for row in rows[:4]:
                    cells = await row.query_selector_all("td, th")
                    vals = [(await c.inner_text()).strip() for c in cells]
                    row_texts.append(vals)
                row_text = " ".join(" ".join(r) for r in row_texts)
                if "上下文" in row_text or "价格" in row_text or "Token" in row_text:
                    pricing_tables.append(row_texts)

        results["pricing_tables"] = pricing_tables[:3]
        results["expanded_sections"] = expanded_count

        return results
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def main():
    parser = argparse.ArgumentParser(description="Search Alibaba Cloud Model Studio models")
    parser.add_argument("--keyword", "-k", default="", help="Filter models by keyword")
    parser.add_argument("--region", "-r", default="", choices=REGIONS, help="Deployment region")
    parser.add_argument("--expand", "-e", action="store_true", help="Expand all '更多模型' sections")
    parser.add_argument("--category", "-c", default="", help="Filter by category name")
    args = parser.parse_args()

    result = await extract_models(
        keyword=args.keyword,
        region=args.region,
        expand=args.expand,
        category=args.category
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
