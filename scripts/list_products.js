#!/usr/bin/env node

/**
 * list_products.js - List Alibaba Cloud documentation categories and products
 *
 * Usage: node scripts/list_products.js [productCode]
 *
 * If no productCode provided, lists all major documentation categories.
 * If productCode provided, lists sub-categories for that product.
 *
 * Output: JSON array of categories/products
 */

// Known documentation categories and their URL patterns on help.aliyun.com
const CATEGORIES = {
  "aiml": {
    name: "人工智能与机器学习",
    url: "https://help.aliyun.com/zh/aiml/",
    products: {
      "model-studio": { name: "大模型服务平台百炼", url: "https://help.aliyun.com/zh/model-studio/what-is-model-studio" },
      "pai": { name: "人工智能平台 PAI", url: "https://help.aliyun.com/zh/pai/" },
      "nlp": { name: "自然语言处理", url: "https://help.aliyun.com/zh/nlp/" },
      "ocr": { name: "文字识别", url: "https://help.aliyun.com/zh/ocr/" },
      "nls": { name: "智能语音交互", url: "https://help.aliyun.com/zh/nls/" },
      "viapi": { name: "视觉智能开放平台", url: "https://help.aliyun.com/zh/viapi/" },
      "docmind": { name: "文档智能", url: "https://help.aliyun.com/zh/document-mind/" },
      "tingwu": { name: "通义听悟", url: "https://help.aliyun.com/zh/tingwu/" },
      "dashvector": { name: "向量检索服务 DashVector", url: "https://help.aliyun.com/zh/dashvector/" }
    }
  },
  "computing": {
    name: "计算",
    url: "https://help.aliyun.com/zh/ecs/",
    products: {
      "ecs": { name: "云服务器 ECS", url: "https://help.aliyun.com/zh/ecs/" },
      "fc": { name: "函数计算", url: "https://help.aliyun.com/zh/function-comput/" },
      "eci": { name: "弹性容器实例", url: "https://help.aliyun.com/zh/eci/" }
    }
  },
  "database": {
    name: "数据库",
    url: "https://help.aliyun.com/zh/rds/",
    products: {
      "rds": { name: "云数据库 RDS", url: "https://help.aliyun.com/zh/rds/" },
      "polardb": { name: "云原生数据库 PolarDB", url: "https://help.aliyun.com/zh/polardb/" },
      "mongodb": { name: "云数据库 MongoDB", url: "https://help.aliyun.com/zh/mongodb/" },
      "redis": { name: "云数据库 Tair (Redis)", url: "https://help.aliyun.com/zh/tair/" }
    }
  },
  "storage": {
    name: "存储",
    url: "https://help.aliyun.com/zh/oss/",
    products: {
      "oss": { name: "对象存储 OSS", url: "https://help.aliyun.com/zh/oss/" },
      "nas": { name: "文件存储 NAS", url: "https://help.aliyun.com/zh/nas/" },
      "ots": { name: "表格存储", url: "https://help.aliyun.com/zh/tablestore/" }
    }
  },
  "networking": {
    name: "网络与CDN",
    url: "https://help.aliyun.com/zh/vpc/",
    products: {
      "vpc": { name: "专有网络 VPC", url: "https://help.aliyun.com/zh/vpc/" },
      "slb": { name: "负载均衡", url: "https://help.aliyun.com/zh/slb/" },
      "cdn": { name: "CDN", url: "https://help.aliyun.com/zh/cdn/" }
    }
  },
  "security": {
    name: "安全",
    url: "https://help.aliyun.com/zh/sas/",
    products: {
      "sas": { name: "云安全中心", url: "https://help.aliyun.com/zh/sas/" },
      "waf": { name: "Web应用防火墙", url: "https://help.aliyun.com/zh/waf/" },
      "kms": { name: "密钥管理服务", url: "https://help.aliyun.com/zh/kms/" }
    }
  }
};

const productCode = process.argv[2];

if (productCode) {
  // Search for product across all categories
  const found = [];
  for (const [catCode, cat] of Object.entries(CATEGORIES)) {
    if (catCode === productCode || cat.name.includes(productCode)) {
      found.push({
        categoryCode: catCode,
        categoryName: cat.name,
        categoryUrl: cat.url,
        products: Object.entries(cat.products).map(([code, prod]) => ({
          productCode: code,
          productName: prod.name,
          productUrl: prod.url
        }))
      });
    }
    for (const [prodCode, prod] of Object.entries(cat.products)) {
      if (prodCode === productCode || prod.name.includes(productCode)) {
        found.push({
          categoryCode: catCode,
          categoryName: cat.name,
          productCode: prodCode,
          productName: prod.name,
          productUrl: prod.url,
          matchType: 'product'
        });
      }
    }
  }

  if (found.length > 0) {
    console.log(JSON.stringify({
      search: productCode,
      found: found
    }, null, 2));
  } else {
    console.log(JSON.stringify({
      search: productCode,
      message: `No products found for "${productCode}". Try broader terms or list all categories.`,
      suggestion: 'Run without arguments to see all categories'
    }));
  }
} else {
  // List all categories
  const output = Object.entries(CATEGORIES).map(([code, cat]) => ({
    categoryCode: code,
    categoryName: cat.name,
    url: cat.url,
    products: Object.entries(cat.products).map(([prodCode, prod]) => ({
      productCode: prodCode,
      productName: prod.name
    }))
  }));

  console.log(JSON.stringify({
    totalCategories: output.length,
    categories: output
  }, null, 2));
}
