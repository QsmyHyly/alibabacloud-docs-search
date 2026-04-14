#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_help_center.py - Search Alibaba Cloud help documentation using the
SideSearch component's global search panel.

Usage:
    python scripts/search_help_center.py --keyword "千问 图像编辑"
    python scripts/search_help_center.py --keyword "千问 图像编辑" --product "大模型服务平台百炼"
    python scripts/search_help_center.py --keyword "知识库" --max-results 20

Output: JSON
"""

import asyncio
import argparse
import json
from shared_browser import acquire_browser_session, cleanup_browser_session
from urllib.parse import quote


PRODUCT_IDS = {
    "大模型服务平台百炼": "2400256",
    "对象存储": "2400004",
    "云服务器 ECS": "2400008",
    "云数据库 RDS": "2400012",
    "日志服务": "2400016",
    "云效": "2400100",
    "阿里邮箱": "2400020",
    "大数据开发治理平台 DataWorks": "2400024",
    "移动开发平台 mPaaS": "2400028",
    "云原生大数据计算服务 MaxCompute": "2400032",
    "物联网平台": "2400036",
    "容器服务 ACK": "2400040",
    "函数计算": "2400044",
    "专有网络 VPC": "2400048",
    "负载均衡 SLB": "2400052",
    "云安全中心": "2400056",
}


async def search_help_center(keyword="", product="", max_results=10):
    """Search help documentation via www.aliyun.com/search/ with scene=helpdoc."""
    encoded_keyword = quote(keyword)
    search_url = f"https://www.aliyun.com/search/?k={encoded_keyword}&scene=helpdoc"
    if product and product in PRODUCT_IDS:
        filter_json = quote(json.dumps({"helpProductId": PRODUCT_IDS[product]}))
        search_url += f"&filter={filter_json}"

    browser, pw, page, is_daemon = await acquire_browser_session(search_url)
    try:
        await page.goto(search_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)

        results = []
        js_results = await page.evaluate(r"""() => {
            const results = [];
            const seen = new Set();
            const allLinks = document.querySelectorAll('a');
            for (const link of allLinks) {
                const href = link.href || link.getAttribute('href') || '';
                const text = (link.textContent || '').trim().replace(/\s+/g, ' ');

                if (href.includes('/zh/') && href.includes('help.aliyun.com') && !seen.has(href)) {
                    seen.add(href);

                    let card = link.closest('[class*="card"], [class*="item"], [class*="result"], li);
                    let source = '';
                    let summary = '';

                    if (card) {
                        const cardLinks = card.querySelectorAll('a');
                        for (const cl of cardLinks) {
                            const ct = (cl.textContent || '').trim();
                            if (ct && ct.length < 30 && ct !== text && !ct.includes('http')) {
                                source = ct;
                                break;
                            }
                        }
                        const snippet = card.querySelector('[class*="summary"], [class*="desc"], [class*="content"], p');
                        if (snippet) {
                            summary = snippet.textContent.trim().substring(0, 300);
                        }
                    }

                    if (text.length > 3 && text.length < 200) {
                        results.push({
                            title: text,
                            url: href,
                            source_product: source,
                            summary: summary
                        });
                    }
                }

                if (results.length >= 50) break;
            }
            return results;
        }""")

        for item in js_results:
            if len(results) >= max_results:
                break
            results.append({
                "title": item["title"],
                "source_product": item.get("source_product", ""),
                "summary": item.get("summary", ""),
                "url": item["url"]
            })

        return {
            "keyword": keyword,
            "product_filter": product,
            "search_url": search_url,
            "total_results": len(results),
            "results": results
        }
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def main():
    parser = argparse.ArgumentParser(description="Search Alibaba Cloud help documentation via SideSearch")
    parser.add_argument("--keyword", "-k", default="", help="Search keyword")
    parser.add_argument("--product", "-p", default="", help="Filter by product name")
    parser.add_argument("--max-results", "-m", type=int, default=10, help="Max results to return")
    args = parser.parse_args()

    if not args.keyword:
        parser.print_help()
        return

    result = await search_help_center(
        keyword=args.keyword,
        product=args.product,
        max_results=args.max_results
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
