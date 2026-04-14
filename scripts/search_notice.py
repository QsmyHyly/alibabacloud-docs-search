#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_notice.py - Search and retrieve Alibaba Cloud announcements

Usage:
    python scripts/search_notice.py                    # List first page notices
    python scripts/search_notice.py --keyword "百炼"    # Search by keyword
    python scripts/search_notice.py --category "升级公告" --page 2  # Filter by category + page
    python scripts/search_notice.py --keyword "百炼" --max-pages 3  # Search across multiple pages
    python scripts/search_notice.py --detail 118177     # Get detail of specific notice

Output: JSON
"""

import asyncio
import argparse
import json
import re
from shared_browser import acquire_browser_session, cleanup_browser_session


BASE_URL = "https://www.aliyun.com"
NOTICE_URL = f"{BASE_URL}/notice/"
CATEGORIES = ["全部", "备案公告", "升级公告", "安全公告", "其他"]


async def get_notices(keyword="", category="", page=1):
    """Fetch notice list from aliyun announcement page using Playwright."""
    browser, pw, page_obj, is_daemon = await acquire_browser_session(NOTICE_URL)
    try:
        await page_obj.goto(NOTICE_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Get total count from page text
        total_count = 0
        total_el = await page_obj.query_selector('[class*="notice-list-wrapper"]')
        if total_el:
            total_text = (await total_el.inner_text()).strip()
            count_match = re.search(r"展示\s*(\d+)\s*条", total_text)
            if count_match:
                total_count = int(count_match.group(1))

        # Filter by category if specified
        if category and category != "全部":
            tabs = await page_obj.query_selector_all('[class*="custom-tab-button"]')
            for tab in tabs:
                tab_text = (await tab.inner_text()).strip()
                if tab_text == category:
                    await tab.click()
                    await asyncio.sleep(2)
                    if total_el:
                        total_text = (await total_el.inner_text()).strip()
                        count_match = re.search(r"展示\s*(\d+)\s*条", total_text)
                        if count_match:
                            total_count = int(count_match.group(1))
                    break

        # Enter keyword in search box if specified
        if keyword:
            search_input = await page_obj.query_selector('input[placeholder="请输入公告标题"]')
            if search_input:
                await search_input.fill(keyword)
                await asyncio.sleep(1)
                await search_input.press("Enter")
                await asyncio.sleep(3)
                if total_el:
                    total_text = (await total_el.inner_text()).strip()
                    count_match = re.search(r"展示\s*(\d+)\s*条", total_text)
                    if count_match:
                        total_count = int(count_match.group(1))

        # Navigate to specified page
        if page > 1:
            page_links = await page_obj.query_selector_all('li.ant-pagination-item > a')
            clicked = False
            for link in page_links:
                text = (await link.inner_text()).strip()
                if text == str(page):
                    await link.click()
                    clicked = True
                    await asyncio.sleep(3)
                    break
            if not clicked:
                jump_input = await page_obj.query_selector('[class*="quick-jumper-input"]')
                if jump_input:
                    await jump_input.fill(str(page))
                    await asyncio.sleep(0.5)
                    await jump_input.press("Enter")
                    await asyncio.sleep(3)

        # Extract notice items
        notice_links = await page_obj.query_selector_all('a[href*="/notice/"]')
        notices = []
        seen = set()

        for link in notice_links:
            href = await link.get_attribute("href")
            notice_match = re.match(r".*/notice/(\d+)(?:[?#/].*)?$", href)
            if not notice_match:
                continue

            notice_id = notice_match.group(1)
            if notice_id in seen:
                continue
            seen.add(notice_id)

            is_in_list = await link.evaluate("""el => {
                let p = el.parentElement;
                while (p) {
                    const cls = p.className || '';
                    if (typeof cls === 'string' && cls.includes('notice-info-container')) return true;
                    p = p.parentElement;
                }
                return false;
            }""")
            if not is_in_list:
                continue

            text = (await link.inner_text()).strip()
            lines = text.split("\n")
            title = lines[0].strip() if lines else ""
            date = lines[-1].strip() if len(lines) > 1 else ""

            notices.append({
                "id": notice_id,
                "title": title,
                "date": date,
                "url": href if href.startswith("http") else f"{BASE_URL}{href}"
            })

        current_page = page
        active_page = await page_obj.query_selector('li.ant-pagination-item-active > a')
        if active_page:
            active_text = (await active_page.inner_text()).strip()
            if active_text.isdigit():
                current_page = int(active_text)

        total_pages = 0
        all_page_links = await page_obj.query_selector_all('li.ant-pagination-item > a')
        for link in all_page_links:
            text = (await link.inner_text()).strip()
            if text.isdigit():
                total_pages = max(total_pages, int(text))

        return {
            "keyword": keyword,
            "category": category,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": current_page,
            "notices": notices
        }
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def get_notice_detail(notice_id):
    """Fetch a single notice detail page."""
    url = f"{NOTICE_URL}{notice_id}"
    browser, pw, page_obj, is_daemon = await acquire_browser_session(url)
    try:
        await page_obj.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        title = await page_obj.title()
        content_selectors = ['[class*="notice-detail"]', '[class*="detail-content"]', 'article', '.content']
        detail_text = ""
        for selector in content_selectors:
            el = await page_obj.query_selector(selector)
            if el:
                detail_text = (await el.inner_text()).strip()
                break
        if not detail_text:
            detail_text = (await page_obj.inner_text("body")).strip()

        return {
            "id": notice_id,
            "url": url,
            "title": title,
            "content": detail_text[:10000]
        }
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def main():
    parser = argparse.ArgumentParser(description="Search Alibaba Cloud announcements")
    parser.add_argument("--keyword", "-k", default="", help="Search keyword (notice title)")
    parser.add_argument("--category", "-c", default="", help=f"Category: {' | '.join(CATEGORIES)}")
    parser.add_argument("--page", "-p", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--max-pages", "-m", type=int, default=1, help="Max pages to search across")
    parser.add_argument("--detail", "-d", default="", help="Get detail of specific notice by ID")
    args = parser.parse_args()

    if args.detail:
        result = await get_notice_detail(args.detail)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.max_pages > 1:
        for p in range(1, args.max_pages + 1):
            data = await get_notices(
                keyword=args.keyword,
                category=args.category,
                page=p
            )
            print(json.dumps({
                "keyword": args.keyword,
                "category": args.category,
                "page": p,
                "total_count": data["total_count"],
                "total_pages": data["total_pages"],
                "notices": data["notices"]
            }, ensure_ascii=False, indent=2))
    else:
        result = await get_notices(
            keyword=args.keyword,
            category=args.category,
            page=args.page
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
