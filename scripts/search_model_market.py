#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_model_market.py - Search Alibaba Cloud Bailian Model Market.

Extracts 6 modules from model detail page:
1. 模型介绍 (Model Introduction)
2. 模型能力 (Model Capabilities)
3. 模型价格 (Model Pricing)
4. 免费额度 (Free Quota)
5. 模型限流与上下文 (Rate Limits & Context)
6. API代码示例 (API Code Examples - all SDK/API combinations)

Also supports filtering models by author, provider, and modality using
the left sidebar filter panel.

Usage:
    python scripts/search_model_market.py --list                              # List all models
    python scripts/search_model_market.py --keyword "qwen3"                   # Search by keyword
    python scripts/search_model_market.py --author "千问"                     # Filter by author
    python scripts/search_model_market.py --provider "阿里云百炼"             # Filter by provider
    python scripts/search_model_market.py --modality "文本生成"               # Filter by modality
    python scripts/search_model_market.py --detail "qwen-image-2.0"           # Get model detail
    python scripts/search_model_market.py --filters                           # List all available filters

Output: JSON
"""

import asyncio
import argparse
import json
import re
from shared_browser import acquire_browser_session, cleanup_browser_session

JS_EXTRACT_BASIC = r"""() => {
    const output = {};
    const modelName = document.querySelector('.currentModelName__nn_Rt');
    if (modelName) output.model_name = modelName.textContent.trim();
    const modelCode = document.querySelector('.modelSelect__hUMIV .efm_ant-select-selection-item');
    if (modelCode) output.model_code = modelCode.textContent.trim();
    const descEl = document.querySelector('.description__GS13E');
    if (descEl) output.model_intro = descEl.textContent.trim();
    const tagEl = document.querySelector('.sectionHeader__vqTA8 .efm_ant-tag');
    if (tagEl) output.model_tag = tagEl.textContent.trim();
    const equivEl = document.querySelector('.equivalentSnapshot__LAVuV');
    if (equivEl) output.equivalent_snapshot = equivEl.textContent.trim();
    const capabilities = {};
    const capItems = document.querySelectorAll('.capabilityItem__pLsZZ');
    for (const item of capItems) {
        const labelEl = item.querySelector('.capabilityLabel__Rp6PI span');
        if (!labelEl) continue;
        const name = labelEl.textContent.trim();
        const modalityIcons = item.querySelectorAll('.modalityIcons__nRsi3 .capabilityIcon__w6Y4T');
        if (modalityIcons.length > 0) {
            const supported = [];
            const unsupported = [];
            for (const icon of modalityIcons) {
                const ariaLabel = icon.getAttribute('aria-label') || '';
                const type = ariaLabel.replace('spark-', '').replace('-line', '');
                if (icon.classList.contains('supportedIcon__Ahgy3')) supported.push(type);
                else if (icon.classList.contains('unsupportedIcon__ZHuU0')) unsupported.push(type);
            }
            capabilities[name] = { supported: supported, unsupported: unsupported };
            continue;
        }
        const hasCheck = item.querySelector('.successIcon__C4HND') !== null;
        const hasError = item.querySelector('.errorIcon__Fz70v') !== null;
        capabilities[name] = hasCheck ? '支持' : hasError ? '不支持' : '未知';
    }
    output.capabilities = capabilities;
    const pricing = [];
    const pricingItems = document.querySelectorAll('.pricingItem___NhHX');
    for (const item of pricingItems) {
        const label = item.querySelector('.pricingLabel__eW13m');
        const value = item.querySelector('.price__N6NAa');
        const unit = item.querySelector('.unit__lUJDd');
        if (label && value) {
            pricing.push({
                item: label.textContent.trim(),
                price: value.textContent.trim(),
                unit: unit ? unit.textContent.trim() : ''
            });
        }
    }
    output.pricing = pricing;
    const quotaSection = document.querySelector('.quotaProgress__Biw3E');
    if (quotaSection) {
        const pct = quotaSection.querySelector('.quotaPercentage__apZAu');
        const expiry = quotaSection.querySelector('.quotaExpiry__rJDWI');
        const details = quotaSection.querySelector('.quotaDetails__uiJ4g');
        output.free_quota = {
            remaining: pct ? pct.textContent.trim() : '',
            expiry: expiry ? expiry.textContent.trim() : '',
            details: details ? details.textContent.trim() : ''
        };
    }
    const limits = {};
    const limitItems = document.querySelectorAll('.limitItem__x52wk');
    for (const item of limitItems) {
        const label = item.querySelector('.limitLabel__J2fSu span');
        const value = item.querySelector('.limitValue__VXYvM');
        if (label && value) {
            limits[label.textContent.trim()] = value.textContent.trim();
        }
    }
    output.rate_limits = limits;
    return output;
}"""

JS_EXTRACT_CODE = r"""() => {
    const codeLines = document.querySelectorAll('.cm-line');
    const codeParts = [];
    for (const line of codeLines) {
        const t = line.textContent.trim();
        if (t) codeParts.push(t);
    }
    const langSelect = document.querySelector('.codeLanguage__K13LV .efm_ant-select-selection-item');
    return {
        code: codeParts.join('\n'),
        language: langSelect ? langSelect.textContent.trim() : 'unknown'
    };
}"""

JS_DETECT_TABS = r"""() => {
    const sdkTabs = [];
    const sdkItems = document.querySelectorAll('.efm_ant-segmented-group .efm_ant-segmented-item');
    for (const item of sdkItems) {
        const label = item.querySelector('.efm_ant-segmented-item-label');
        if (!label) continue;
        const title = label.getAttribute('title') || label.textContent.trim();
        const skipLabels = ['中国内地', '全球', '国际', '美国', '新加坡'];
        if (skipLabels.includes(title)) continue;
        sdkTabs.push({
            title: title,
            selected: item.classList.contains('efm_ant-segmented-item-selected')
        });
    }
    const apiTabs = [];
    const apiTabBtns = document.querySelectorAll('.apiStyleTabs__KcMI1 .apiStyleTab__LPxQn');
    for (const btn of apiTabBtns) {
        apiTabs.push({
            title: btn.textContent.trim(),
            selected: !btn.classList.contains('apiStyleTabInactive__ZIurL')
        });
    }
    return { sdkTabs: sdkTabs, apiTabs: apiTabs };
}"""

JS_GET_FILTERS = r"""() => {
    const filters = { authors: [], providers: [], modalities: [] };
    const allLabels = document.querySelectorAll('.option__2njXd .label__MJHUc');
    const authorNames = ['千问', '万相', '领域模型', 'DeepSeek', '月之暗面', '智谱AI', 'MiniMax', 'PixVerse', '可灵AI', 'Vidu'];
    const providerNames = ['阿里云百炼', '硅基流动', 'Kimi', 'MiniMax', 'PixVerse', '可灵AI', 'Vidu'];
    const modalityNames = ['全模态', '文本生成', '深度思考', '视觉理解', '图片生成',
        '视频生成', '语音识别', '语音合成', '多模态向量', '文本向量',
        '实时全模态', '实时语音合成', '实时语音识别', '实时语音翻译'];
    for (const label of allLabels) {
        const text = label.textContent.trim();
        if (authorNames.includes(text) && !filters.authors.includes(text)) filters.authors.push(text);
        if (providerNames.includes(text) && !filters.providers.includes(text)) filters.providers.push(text);
        if (modalityNames.includes(text) && !filters.modalities.includes(text)) filters.modalities.push(text);
    }
    return filters;
}"""


async def click_filter(page, label_text):
    """Click a filter option in the left sidebar."""
    options = await page.query_selector_all('.option__2njXd .label__MJHUc')
    for opt in options:
        text = (await opt.inner_text()).strip()
        if text == label_text:
            await opt.click()
            await asyncio.sleep(2)
            return True
    return False


async def list_models(keyword="", author="", provider="", modality="", region="cn-beijing"):
    """List models from Bailian console model market page with filters."""
    url = f"https://bailian.console.aliyun.com/{region}/?tab=model#/model-market/all"
    browser, pw, page, is_daemon = await acquire_browser_session(url)
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)

        applied_filters = []
        if author:
            if await click_filter(page, author):
                applied_filters.append(f"author={author}")
        if provider:
            if await click_filter(page, provider):
                applied_filters.append(f"provider={provider}")
        if modality:
            if await click_filter(page, modality):
                applied_filters.append(f"modality={modality}")

        body_text = (await page.inner_text("body")).strip()
        has_model_data = any(kw in body_text for kw in ["Qwen3", "qwen", "Wan", "深度思考", "视觉理解"])

        if not has_model_data:
            return {"error": "需要登录百炼控制台查看模型列表", "console_url": url}

        lines = body_text.split("\n")
        model_list_start = -1
        for idx, line in enumerate(lines):
            if line.strip().startswith("模型") and any(c.isdigit() for c in line.strip()):
                model_list_start = idx
                break
            if "全部 上下文长度" in line or "全部 模型能力" in line:
                model_list_start = idx + 1
                break

        if model_list_start < 0:
            return {"error": "无法定位模型列表区域", "console_url": url}

        models = []
        model_names = set()
        valid_prefixes = ["Qwen3.", "Qwen-", "qwen", "QwQ", "QVQ", "Wan2.", "wan",
                         "GLM-", "GLM4", "MiniMax-", "PixVerse-", "Vidu",
                         "DeepSeek-", "Kimi-", "kimi"]
        tag_kw = ["深度思考", "视觉理解", "文本生成", "图片生成",
                 "视频生成", "语音合成", "语音识别", "实时全模态", "全模态"]
        skip_items = ["DeepSeek", "Kimi", "MiniMax", "PixVerse", "Vidu", "智谱AI", "月之暗面",
                     "立即体验", "API 参考", "New", "最新版本",
                     "大模型特惠活动", "AI通用节省计划", "特惠资源包",
                     "千问", "万相", "领域模型",
                     "Qwen3", "Qwen3.6", "Qwen3.5", "Qwen3.5开源模型"]

        i = model_list_start
        while i < len(lines):
            line = lines[i].strip()
            is_model_name = False
            for prefix in valid_prefixes:
                if line.startswith(prefix) and len(line) < 60:
                    is_model_name = True
                    break
            if re.match(r"^[A-Za-z][A-Za-z0-9-]+$", line) and len(line) > 3 and len(line) < 60:
                if not any(skip in line for skip in skip_items):
                    is_model_name = True

            if is_model_name and line not in model_names and line not in skip_items:
                model_names.add(line)
                model = {"name": line, "description": "", "capabilities": [], "date": None}
                j = i + 1
                while j < len(lines) and j < i + 10:
                    next_line = lines[j].strip()
                    if not next_line:
                        j += 1
                        continue
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", next_line):
                        model["date"] = next_line
                        j += 1
                        break
                    if next_line in tag_kw:
                        model["capabilities"].append(next_line)
                        j += 1
                        continue
                    if next_line in ["立即体验", "API 参考", "New", "最新版本"]:
                        j += 1
                        continue
                    if re.match(r"^\d+$", next_line) and len(next_line) < 3:
                        j += 1
                        continue
                    if 10 < len(next_line) < 500 and not model["description"]:
                        model["description"] = next_line
                    j += 1

                if model["description"] or model["capabilities"]:
                    model["console_url"] = f"https://bailian.console.aliyun.com/{region}/?tab=model#/model-market/detail/{line.lower()}?serviceSite=asia-pacific-china"
                    models.append(model)
                i = j
            else:
                i += 1

        if keyword:
            kw = keyword.lower()
            models = [m for m in models if kw in m["name"].lower() or kw in m.get("description", "").lower()]

        return {
            "source": "bailian.console.aliyun.com (模型广场)",
            "filters_applied": applied_filters if applied_filters else "none",
            "total_models": len(models),
            "models": models
        }
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def get_filters(region="cn-beijing"):
    """Get all available filter options from the sidebar."""
    url = f"https://bailian.console.aliyun.com/{region}/?tab=model#/model-market/all"
    browser, pw, page, is_daemon = await acquire_browser_session(url)
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)
        filters = await page.evaluate(JS_GET_FILTERS)
        return filters
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def extract_code_block(page):
    """Extract current visible code block."""
    await asyncio.sleep(1.5)
    return await page.evaluate(JS_EXTRACT_CODE)


async def get_model_detail(model_name, region="cn-beijing"):
    """Get full model detail including all 6 modules from console detail page."""
    detail_url = f"https://bailian.console.aliyun.com/{region}/?tab=model#/model-market/detail/{model_name}?serviceSite=asia-pacific-china"
    browser, pw, page, is_daemon = await acquire_browser_session(detail_url)
    try:
        await page.goto(detail_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)

        title = await page.title()
        if "登录" in title:
            return {
                "model": model_name,
                "error": "需要登录百炼控制台查看模型详情",
                "console_url": detail_url,
                "suggestion": "请登录后重试，或使用 help.aliyun.com 查看公开模型文档"
            }

        result = await page.evaluate(JS_EXTRACT_BASIC)

        api_examples = {}
        skip_labels = ['中国内地', '全球', '国际', '美国', '新加坡']
        sdk_items = await page.query_selector_all('.efm_ant-segmented-group .efm_ant-segmented-item')
        for sdk_item in sdk_items:
            label = await sdk_item.query_selector('.efm_ant-segmented-item-label')
            if not label:
                continue
            sdk_title = (await label.inner_text()).strip()
            if sdk_title in skip_labels:
                continue
            try:
                await sdk_item.click()
                await asyncio.sleep(1.5)
                new_tabs = await page.evaluate(JS_DETECT_TABS)
                if new_tabs["apiTabs"]:
                    api_buttons = await page.query_selector_all('.apiStyleTabs__KcMI1 .apiStyleTab__LPxQn')
                    for btn in api_buttons:
                        btn_text = (await btn.inner_text()).strip()
                        try:
                            await btn.click()
                            api_examples[f"{sdk_title} - {btn_text}"] = await extract_code_block(page)
                        except:
                            pass
                else:
                    api_examples[sdk_title] = await extract_code_block(page)
            except:
                pass

        result["api_code_examples"] = api_examples
        result["available_tabs"] = await page.evaluate(JS_DETECT_TABS)
        result["model"] = model_name
        result["console_url"] = detail_url

        return result
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)


async def main():
    parser = argparse.ArgumentParser(description="Search Bailian Model Market")
    parser.add_argument("--keyword", "-k", default="", help="Filter by model name or keyword")
    parser.add_argument("--detail", "-d", default="", help="Get full model detail (all 6 modules)")
    parser.add_argument("--list", action="store_true", help="List all models")
    parser.add_argument("--filters", action="store_true", help="List all available filter options")
    parser.add_argument("--author", "-a", default="", help="Filter by author: 千问, 万相, 领域模型, DeepSeek, 月之暗面, 智谱AI, MiniMax, PixVerse, 可灵AI, Vidu")
    parser.add_argument("--provider", "-p", default="", help="Filter by provider: 阿里云百炼, 硅基流动, Kimi, MiniMax, PixVerse, 可灵AI, Vidu")
    parser.add_argument("--modality", "-m", default="", help="Filter by modality: 全模态, 文本生成, 深度思考, 视觉理解, 图片生成, 视频生成, 语音识别, 语音合成, 多模态向量, 文本向量, 实时全模态, 实时语音合成, 实时语音识别, 实时语音翻译")
    parser.add_argument("--region", default="cn-beijing", help="Bailian region")
    args = parser.parse_args()

    if args.filters:
        result = await get_filters(region=args.region)
    elif args.detail:
        result = await get_model_detail(args.detail, region=args.region)
    elif args.list or args.keyword or args.author or args.provider or args.modality:
        result = await list_models(
            keyword=args.keyword,
            author=args.author,
            provider=args.provider,
            modality=args.modality,
            region=args.region
        )
    else:
        parser.print_help()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
