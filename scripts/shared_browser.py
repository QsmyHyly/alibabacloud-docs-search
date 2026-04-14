#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared_browser.py - Shared browser session management for alibabacloud-docs-search.

Provides:
  - Daemon lifecycle: start_daemon, stop_daemon, is_daemon_running
  - Session acquisition: acquire_browser_session, cleanup_browser_session
  - Page matching: find_matching_page

All search_*.py scripts should use acquire_browser_session() instead of
directly calling playwright's launch(). This enables automatic reuse of
a running browser daemon started by interact_doc.py --start.

Usage in search scripts:
    browser, pw, page, is_daemon = await acquire_browser_session(target_url)
    try:
        await page.goto(target_url, ...)
        # ... do work ...
    finally:
        await cleanup_browser_session(browser, pw, is_daemon)
"""

import asyncio
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from playwright.async_api import async_playwright

# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
RUNTIME_DIR = SKILL_DIR / ".alidoc_runtime"

DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DEFAULT_CDP_PORT = 9250


def _get_runtime_dir():
    """Resolve runtime directory: env var or default."""
    env_dir = os.environ.get("ALIDOC_RUNTIME_DIR")
    if env_dir:
        return Path(env_dir)
    return RUNTIME_DIR


def ensure_runtime_dir():
    """Create runtime directory if it doesn't exist."""
    rdir = _get_runtime_dir()
    rdir.mkdir(parents=True, exist_ok=True)
    return rdir


# ============================================================
# Daemon state files
# ============================================================

def _daemon_pid_file(rdir):
    return rdir / "daemon.pid"


def _daemon_cdp_file(rdir):
    return rdir / "daemon_cdp.txt"


# ============================================================
# Daemon lifecycle
# ============================================================

def find_chrome():
    """Find Chrome/Chromium executable."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return "chrome"


def is_port_open(port):
    """Check if a TCP port is accepting connections."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("localhost", port))
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def _cleanup_daemon_files(rdir):
    """Remove stale PID and CDP files."""
    for f in [_daemon_pid_file(rdir), _daemon_cdp_file(rdir)]:
        if f.exists():
            f.unlink()


def is_daemon_running(rdir=None):
    """Check if the browser daemon is running (PID alive + CDP port open)."""
    if rdir is None:
        rdir = _get_runtime_dir()
    pid_f = _daemon_pid_file(rdir)
    cdp_f = _daemon_cdp_file(rdir)
    if not pid_f.exists() or not cdp_f.exists():
        return False
    try:
        pid = int(pid_f.read_text().strip())
    except (ValueError, FileNotFoundError):
        _cleanup_daemon_files(rdir)
        return False

    # Check process alive
    try:
        if os.name == 'nt':
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True
            )
            if str(pid) not in result.stdout:
                _cleanup_daemon_files(rdir)
                return False
        else:
            os.kill(pid, 0)
    except (ProcessLookupError, FileNotFoundError):
        _cleanup_daemon_files(rdir)
        return False

    # Verify CDP port is actually responding
    try:
        cdp_content = cdp_f.read_text().strip()
        port = int(cdp_content.rsplit(":", 1)[-1])
        if not is_port_open(port):
            _cleanup_daemon_files(rdir)
            return False
    except (ValueError, FileNotFoundError):
        _cleanup_daemon_files(rdir)
        return False

    return True


def get_daemon_info(rdir=None):
    """Read PID and CDP URL from daemon state files."""
    if rdir is None:
        rdir = _get_runtime_dir()
    pid = int(_daemon_pid_file(rdir).read_text().strip())
    cdp = _daemon_cdp_file(rdir).read_text().strip()
    return pid, cdp


def start_daemon(rdir=None):
    """Start a Chrome browser daemon with remote debugging."""
    if rdir is None:
        rdir = _get_runtime_dir()
    if is_daemon_running(rdir):
        pid, cdp = get_daemon_info(rdir)
        print(f"Daemon already running: PID={pid}, CDP={cdp}")
        return True

    ensure_runtime_dir()
    chrome = find_chrome()
    cdp_port = DEFAULT_CDP_PORT
    user_data_dir = str(rdir / "browser_profile")

    cmd = [
        chrome,
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--headless=new",
    ]

    print(f"Starting browser daemon: {chrome}")
    print(f"CDP port: {cdp_port}")
    print(f"Runtime dir: {rdir}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        for _ in range(30):
            time.sleep(0.5)
            if is_port_open(cdp_port):
                with open(_daemon_pid_file(rdir), "w") as f:
                    f.write(str(proc.pid))
                with open(_daemon_cdp_file(rdir), "w") as f:
                    f.write(f"http://localhost:{cdp_port}")
                print(f"Daemon started: PID={proc.pid}")
                return True
        print("Timeout waiting for browser to start")
        proc.kill()
        return False
    except FileNotFoundError:
        print(f"Chrome not found at {chrome}. Please install Chrome or set PATH.")
        return False


def stop_daemon(rdir=None):
    """Stop the browser daemon."""
    if rdir is None:
        rdir = _get_runtime_dir()
    if not is_daemon_running(rdir):
        print("No daemon running")
        return

    pid, _ = get_daemon_info(rdir)
    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True)
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"Daemon stopped: PID={pid}")
    except Exception as e:
        print(f"Failed to stop daemon: {e}")
    finally:
        _cleanup_daemon_files(rdir)


# ============================================================
# Session acquisition (unified entry point)
# ============================================================

async def acquire_browser_session(target_url=None):
    """
    Unified browser session acquisition.

    Checks if a browser daemon is running. If yes, connects via CDP and
    finds or creates a suitable page. If not, launches a fresh browser.

    Args:
        target_url: Optional target URL for page matching.

    Returns:
        (browser, pw, page, is_daemon) tuple.
        - is_daemon=True: connected to existing daemon, do NOT kill browser on cleanup
        - is_daemon=False: launched new browser, MUST call browser.close() on cleanup
    """
    # Try daemon first
    if is_daemon_running():
        try:
            _, cdp_url = get_daemon_info()
            pw = await async_playwright().start()
            browser = await pw.chromium.connect_over_cdp(cdp_url)

            # Get or create context
            contexts = browser.contexts
            if not contexts:
                context = await browser.new_context(
                    viewport=DEFAULT_VIEWPORT,
                    user_agent=DEFAULT_USER_AGENT
                )
            else:
                context = contexts[0]

            # Find matching page or create/use one
            page = find_matching_page(context, target_url)
            if not page:
                pages = context.pages
                if pages:
                    page = pages[-1]
                else:
                    page = await context.new_page()

            return browser, pw, page, True

        except Exception:
            # Daemon connection failed, fall through to launch
            pass

    # Fallback: launch new browser
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport=DEFAULT_VIEWPORT,
        user_agent=DEFAULT_USER_AGENT
    )
    page = await context.new_page()
    return browser, pw, page, False


async def cleanup_browser_session(browser, pw, is_daemon):
    """
    Clean up a browser session.

    - is_daemon=True: only close the CDP connection, daemon process stays alive
    - is_daemon=False: fully close browser and stop playwright
    """
    try:
        await browser.close()
    except Exception:
        pass
    try:
        await pw.stop()
    except Exception:
        pass


# ============================================================
# Page matching
# ============================================================

def find_matching_page(context, target_url):
    """
    Find an existing page in the browser context whose URL matches target_url.

    Matching rules (in priority order):
    1. Exact match (ignoring query string)
    2. Same host + page path is a prefix of target path
    3. For SPA apps (bailian console): same host match

    Returns the matching page, or None if no match.
    """
    if not target_url:
        return None

    try:
        from urllib.parse import urlparse
        target = urlparse(target_url)
        target_host = target.hostname or ""
        target_path = (target.path or "").rstrip("/")
    except Exception:
        return None

    for page in context.pages:
        try:
            page_url = page.url
            if not page_url:
                continue
            parsed = urlparse(page_url)
            page_host = parsed.hostname or ""
            page_path = (parsed.path or "").rstrip("/")

            # Tier 1: exact match (ignore query string)
            if page_host == target_host and page_path == target_path:
                return page

            # Tier 2: same host + page path is prefix of target path
            if (page_host == target_host
                    and page_path
                    and target_path.startswith(page_path)):
                return page

            # Tier 3: SPA match (bailian console uses hash routing)
            if ("bailian.console.aliyun.com" in page_host
                    and "bailian.console.aliyun.com" in target_host):
                return page

        except Exception:
            continue

    return None
