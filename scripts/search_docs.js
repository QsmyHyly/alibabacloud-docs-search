#!/usr/bin/env node

/**
 * search_docs.js - Search Alibaba Cloud documentation
 *
 * Usage: node scripts/search_docs.js "<keyword>" [maxResults]
 *
 * Search methods (in order of preference):
 * 1. Web scrape help.aliyun.com search page (no credentials)
 * 2. IQS UnifiedSearch API (requires credentials)
 *
 * Output: JSON array of search results
 */

const https = require('https');
const http = require('http');

const MAX_RESULTS = process.argv[3] ? parseInt(process.argv[3]) : 10;
const KEYWORD = process.argv[2] || '';

if (!KEYWORD) {
  console.error('Usage: node scripts/search_docs.js "<keyword>" [maxResults]');
  process.exit(1);
}

/**
 * Search via help.aliyun.com web search page scraping
 * This method requires no credentials
 */
function searchViaWeb(keyword) {
  const encoded = encodeURIComponent(keyword);
  const url = `https://help.aliyun.com/zh/search.htm?keyword=${encoded}`;

  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const results = parseSearchResults(data, keyword);
          resolve(results);
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error('Search request timeout'));
    });
  });
}

/**
 * Parse search results from help.aliyun.com HTML
 */
function parseSearchResults(html, keyword) {
  const results = [];

  // Extract title links from search results
  // Pattern: <a href="..." class="...">title</a>
  const titleRegex = /<a[^>]*href="(\/zh\/[^"]+)"[^>]*>([^<]*(?:<[^>]+>[^<]*)*?)<\/a>/g;
  let match;

  const seen = new Set();
  while ((match = titleRegex.exec(html)) !== null) {
    const url = match[1];
    const title = match[2].replace(/<[^>]+>/g, '').trim();

    // Filter to only documentation pages
    if (url.includes('/zh/') &&
        !url.includes('.js') &&
        !url.includes('.css') &&
        !url.includes('.png') &&
        title.length > 3 &&
        title.length < 200 &&
        !seen.has(url)) {

      seen.add(url);

      // Calculate simple relevance score
      let relevance = 0;
      const titleLower = title.toLowerCase();
      const kwLower = keyword.toLowerCase();

      if (titleLower.includes(kwLower)) relevance += 3;
      if (titleLower.startsWith(kwLower)) relevance += 2;
      if (titleLower.split(kwLower).length > 1) relevance += 1;

      results.push({
        title,
        url: `https://help.aliyun.com${url}`,
        relevance: relevance > 0 ? (relevance >= 5 ? 'High' : relevance >= 3 ? 'Medium' : 'Low') : 'Low',
        relevanceScore: relevance
      });
    }
  }

  // Sort by relevance
  results.sort((a, b) => b.relevanceScore - a.relevanceScore);

  return results.slice(0, MAX_RESULTS);
}

/**
 * Search via IQS UnifiedSearch API (requires credentials)
 * Reference: https://help.aliyun.com/document_detail/2963346.html
 */
async function searchViaIQS(keyword) {
  try {
    // Try to use aliyun CLI if available
    const { execSync } = require('child_process');
    const encoded = encodeURIComponent(keyword);

    try {
      // Try using aliyun CLI for IQS UnifiedSearch
      const output = execSync(
        `aliyun iqs UnifiedSearch --Query "${keyword}" --MaxResults ${MAX_RESULTS}`,
        { encoding: 'utf8', timeout: 15000 }
      );
      const parsed = JSON.parse(output);
      return formatIQSResults(parsed);
    } catch {
      // Fallback to web search
      return searchViaWeb(keyword);
    }
  } catch (e) {
    console.error(`IQS search failed, falling back: ${e.message}`);
    return searchViaWeb(keyword);
  }
}

function formatIQSResults(data) {
  if (!data.Hits || !data.Hits.Hit) return [];

  return data.Hits.Hit.slice(0, MAX_RESULTS).map(hit => ({
    title: hit.Title || '',
    url: hit.Url || '',
    snippet: hit.Snippet || '',
    relevance: hit.Score > 0.7 ? 'High' : hit.Score > 0.4 ? 'Medium' : 'Low',
    relevanceScore: hit.Score || 0
  }));
}

// Main execution
async function main() {
  try {
    const hasCredentials = process.env.ALIBABA_CLOUD_ACCESS_KEY_ID &&
                           process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET;

    let results;
    if (hasCredentials) {
      results = await searchViaIQS(KEYWORD);
    } else {
      results = await searchViaWeb(KEYWORD);
    }

    console.log(JSON.stringify({
      keyword: KEYWORD,
      totalResults: results.length,
      results: results.map(r => ({
        title: r.title,
        url: r.url,
        relevance: r.relevance
      }))
    }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({
      error: true,
      message: error.message,
      suggestion: 'Try broader keywords or check network connectivity'
    }));
    process.exit(1);
  }
}

main();
