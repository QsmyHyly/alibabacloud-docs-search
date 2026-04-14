#!/usr/bin/env node

/**
 * check_env.js - Check environment and dependencies for Alibaba Cloud docs search
 *
 * Checks:
 * 1. Node.js version (>= 18 for fetch API)
 * 2. Required npm packages installed
 * 3. Alibaba Cloud credentials configured (optional for basic search)
 */

const fs = require('fs');
const path = require('path');

const REQUIRED_PACKAGES = {
  'node-fetch': '^3.3.0',
  'cheerio': '^1.0.0'
};

function check() {
  const results = {};
  let allPassed = true;

  // Check Node.js version
  const nodeVersion = process.version;
  const majorVersion = parseInt(nodeVersion.slice(1).split('.')[0]);
  results.nodeVersion = {
    passed: majorVersion >= 18,
    message: `Node.js ${nodeVersion} (required >= 18)`
  };
  if (!results.nodeVersion.passed) allPassed = false;

  // Check package.json exists
  const packageJsonPath = path.join(__dirname, '..', 'package.json');
  if (fs.existsSync(packageJsonPath)) {
    const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    const deps = { ...pkg.dependencies };

    for (const [pkgName] of Object.entries(REQUIRED_PACKAGES)) {
      results[pkgName] = {
        passed: !!deps[pkgName],
        message: deps[pkgName]
          ? `${pkgName}@${deps[pkgName]} (installed)`
          : `${pkgName} not found in package.json`
      };
      if (!results[pkgName].passed) allPassed = false;
    }
  } else {
    results.packageJson = {
      passed: false,
      message: 'package.json not found. Run: npm init -y && npm install node-fetch cheerio'
    };
    allPassed = false;
  }

  // Check credentials (optional, only warn)
  const hasAkId = !!process.env.ALIBABA_CLOUD_ACCESS_KEY_ID;
  const hasAkSecret = !!process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET;
  const hasCliConfig = fs.existsSync(path.join(
    process.env.HOME || process.env.USERPROFILE || '',
    '.aliyun', 'config.json'
  ));

  results.credentials = {
    passed: hasAkId && hasAkSecret || hasCliConfig,
    message: hasAkId && hasAkSecret
      ? 'Environment variables configured'
      : hasCliConfig
        ? 'Alibaba Cloud CLI config found (~/.aliyun/config.json)'
        : 'No credentials found (optional — basic search works without them)'
  };

  // Output results
  console.log(JSON.stringify({
    allPassed,
    checks: results,
    installCommand: 'npm install'
  }, null, 2));

  process.exit(allPassed ? 0 : 1);
}

check();
