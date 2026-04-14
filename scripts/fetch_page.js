#!/usr/bin/env node

/**
 * fetch_page.js - Fetch and parse a single help.aliyun.com documentation page
 *
 * Usage: node scripts/fetch_page.js "<url>"
 *
 * Output: JSON object with page title, content, tables, and code examples
 *
 * Supported URL formats:
 * - https://help.aliyun.com/zh/model-studio/what-is-model-studio
 * - https://help.aliyun.com/zh/model-studio/models
 * - Any help.aliyun.com/zh/... page
 */

const https = require('https');
const http = require('http');

const URL = process.argv[2] || '';

if (!URL) {
  console.error('Usage: node scripts/fetch_page.js "<url>"');
  console.error('Example: node scripts/fetch_page.js "https://help.aliyun.com/zh/model-studio/what-is-model-studio"');
  process.exit(1);
}

// Validate URL is from help.aliyun.com
if (!URL.startsWith('https://help.aliyun.com') && !URL.startsWith('http://help.aliyun.com')) {
  console.error(JSON.stringify({
    error: true,
    message: 'Only help.aliyun.com URLs are supported'
  }));
  process.exit(1);
}

/**
 * Fetch page content via HTTPS
 */
function fetchPage(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
      }
    }, (res) => {
      // Follow redirects
      if (res.statusCode === 301 || res.statusCode === 302) {
        const location = res.headers.location;
        if (location) {
          resolve(fetchPage(location.startsWith('http') ? location : `https://help.aliyun.com${location}`));
          return;
        }
      }

      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    });

    req.on('error', reject);
    req.setTimeout(15000, () => {
      req.destroy();
      reject(new Error('Page fetch timeout (15s)'));
    });
  });
}

/**
 * Parse HTML content to extract structured information
 */
function parsePage(html) {
  const result = {
    title: '',
    content: '',
    sections: [],
    codeBlocks: [],
    tables: [],
    links: []
  };

  // Extract page title
  const titleMatch = html.match(/<title>(.*?)<\/title>/s);
  if (titleMatch) {
    result.title = titleMatch[1]
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .trim();
  }

  // Extract meta description
  const descMatch = html.match(/<meta[^>]*name="description"[^>]*content="([^"]*)"/);
  if (descMatch) {
    result.description = descMatch[1]
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .trim();
  }

  // Extract main content area
  // help.aliyun.com uses specific class patterns for content
  const contentPatterns = [
    /<article[^>]*>([\s\S]*?)<\/article>/,
    /<main[^>]*>([\s\S]*?)<\/main>/,
    /<div[^>]*class="[^"]*content[^"]*"[^>]*>([\s\S]*?)<\/div>/,
    /<div[^>]*id="app"[^>]*>([\s\S]*?)<\/div>/
  ];

  let mainContent = '';
  for (const pattern of contentPatterns) {
    const match = html.match(pattern);
    if (match) {
      mainContent = match[1];
      break;
    }
  }

  if (!mainContent) {
    mainContent = html;
  }

  // Extract code blocks
  const codeBlockRegex = /<pre[^>]*><code[^>]*>([\s\S]*?)<\/code><\/pre>/g;
  let codeMatch;
  let codeIndex = 0;
  while ((codeMatch = codeBlockRegex.exec(mainContent)) !== null) {
    const code = codeMatch[1]
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/<[^>]+>/g, '')
      .trim();

    if (code.length > 5) {
      result.codeBlocks.push({
        index: ++codeIndex,
        language: detectLanguage(codeMatch[0]),
        code: code
      });
    }
  }

  // Extract tables
  const tableRegex = /<table[^>]*>([\s\S]*?)<\/table>/g;
  let tableMatch;
  let tableIndex = 0;
  while ((tableMatch = tableRegex.exec(mainContent)) !== null) {
    const table = parseTable(tableMatch[1]);
    if (table.rows.length > 1) {
      result.tables.push({
        index: ++tableIndex,
        headers: table.headers,
        rows: table.rows
      });
    }
  }

  // Extract internal links
  const linkRegex = /<a[^>]*href="(\/zh\/[^"]+)"[^>]*>([^<]*)<\/a>/g;
  let linkMatch;
  const seenLinks = new Set();
  while ((linkMatch = linkRegex.exec(mainContent)) !== null) {
    const linkUrl = linkMatch[1];
    const linkText = linkMatch[2].trim();
    if (linkText && !seenLinks.has(linkUrl) && linkText.length < 100) {
      seenLinks.add(linkUrl);
      result.links.push({
        text: linkText,
        url: `https://help.aliyun.com${linkUrl}`
      });
    }
  }

  // Extract plain text content (strip HTML tags)
  result.content = mainContent
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, '\n')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, '\n\n')
    .trim()
    .slice(0, 10000); // Limit content size

  return result;
}

/**
 * Parse HTML table to structured data
 */
function parseTable(tableHtml) {
  const result = { headers: [], rows: [] };

  // Extract headers
  const thRegex = /<th[^>]*>([\s\S]*?)<\/th>/g;
  let thMatch;
  while ((thMatch = thRegex.exec(tableHtml)) !== null) {
    const header = thMatch[1]
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/g, ' ')
      .trim();
    if (header) result.headers.push(header);
  }

  // Extract rows
  const trRegex = /<tr[^>]*>([\s\S]*?)<\/tr>/g;
  let trMatch;
  while ((trMatch = trRegex.exec(tableHtml)) !== null) {
    const rowHtml = trMatch[1];
    const tdRegex = /<td[^>]*>([\s\S]*?)<\/td>/g;
    const cells = [];
    let tdMatch;
    while ((tdMatch = tdRegex.exec(rowHtml)) !== null) {
      const cell = tdMatch[1]
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .trim();
      cells.push(cell);
    }
    if (cells.length > 0) {
      result.rows.push(cells);
    }
  }

  return result;
}

/**
 * Detect code block language
 */
function detectLanguage(preHtml) {
  const langMatch = preHtml.match(/class="[^"]*language-([^"]+)"/);
  if (langMatch) return langMatch[1];
  if (preHtml.includes('bash') || preHtml.includes('shell')) return 'bash';
  if (preHtml.includes('python')) return 'python';
  if (preHtml.includes('javascript')) return 'javascript';
  if (preHtml.includes('json')) return 'json';
  return 'text';
}

// Main execution
async function main() {
  try {
    const html = await fetchPage(URL);
    const parsed = parsePage(html);

    console.log(JSON.stringify({
      url: URL,
      title: parsed.title,
      description: parsed.description || '',
      contentLength: parsed.content.length,
      codeBlocksCount: parsed.codeBlocks.length,
      tablesCount: parsed.tables.length,
      linksCount: parsed.links.length,
      content: parsed.content,
      codeBlocks: parsed.codeBlocks,
      tables: parsed.tables,
      links: parsed.links.slice(0, 30) // Limit links
    }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({
      error: true,
      message: error.message,
      url: URL,
      suggestion: 'Check URL is valid and accessible'
    }));
    process.exit(1);
  }
}

main();
