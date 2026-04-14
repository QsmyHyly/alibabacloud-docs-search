#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
interact_doc.py - Interact with help.aliyun.com documentation page components.

Uses a persistent browser daemon via connect_over_cdp.
Multiple commands share the same running browser instance.

Runtime state (daemon pid, cdp url, browser profile) is stored in the skill
directory under .alidoc_runtime/. Use --cleanup to remove stale runtime files.

Usage - Daemon management:
    python scripts/interact_doc.py --start
    python scripts/interact_doc.py --stop
    python scripts/interact_doc.py --daemon-status
    python scripts/interact_doc.py --cleanup            # Remove stale runtime files

Usage - Single-shot (no daemon needed):
    python scripts/interact_doc.py --url "URL" --list
    python scripts/interact_doc.py --url "URL" --expand "FAQ" --screenshot --output "path.png"

Usage - Daemon mode (persistent browser session):
    python scripts/interact_doc.py --new --url "URL"
    python scripts/interact_doc.py --list
    python scripts/interact_doc.py --expand "FAQ"
    python scripts/interact_doc.py --tab "手动安装@0"
    python scripts/interact_doc.py --screenshot -o "path.png"
    python scripts/interact_doc.py --download-md -o "path.md"

Options:
    --runtime-dir DIR   Override runtime dir (default: skill/.alidoc_runtime/)
    --config KEY=VALUE  Set a config value (e.g. --config viewport_width=1440)
"""

import asyncio
import argparse
import sys
import os
import json
import time
import subprocess
import signal
from pathlib import Path
from playwright.async_api import async_playwright

# ============================================================
# State file management (stateless skill principle)
# ============================================================

# Skill config file: stores persistent settings (runtime_dir, viewport, etc.)
# Located inside the skill directory, NOT in the project root.
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SKILL_CONFIG_FILE = SKILL_DIR / ".alidoc_config.json"

DEFAULT_CONFIG = {
    "viewport_width": 1920,
    "viewport_height": 1080
}

# Forbidden output directories (skill directory)


def load_skill_config():
    """Load persistent configuration from the skill directory."""
    if SKILL_CONFIG_FILE.exists():
        try:
            with open(SKILL_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_skill_config(config):
    """Save persistent configuration to the skill directory."""
    SKILL_CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_effective_config():
    """Merge defaults with persistent skill config."""
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(load_skill_config())
    return cfg


# Runtime directory: inside skill directory for easy cleanup
RUNTIME_DIR = SKILL_DIR / ".alidoc_runtime"


def get_runtime_dir(args):
    """Resolve runtime directory: CLI arg -> Env var -> Skill directory."""
    # 1. CLI arg (one-time override)
    if args.runtime_dir:
        return Path(args.runtime_dir)
    # 2. Environment variable
    env_dir = os.environ.get("ALIDOC_RUNTIME_DIR")
    if env_dir:
        return Path(env_dir)
    # 3. Skill directory runtime
    return RUNTIME_DIR


def ensure_runtime_dir(rdir):
    """Create runtime directory if it doesn't exist."""
    rdir.mkdir(parents=True, exist_ok=True)
    return rdir


def load_config():
    """Load effective config (defaults + skill config)."""
    return get_effective_config()


def save_config(config):
    """Save persistent config to skill directory."""
    save_skill_config(config)


def daemon_pid_file(rdir):
    return rdir / "daemon.pid"


def daemon_cdp_file(rdir):
    return rdir / "daemon_cdp.txt"


# ============================================================
# Daemon Management
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


def start_daemon(rdir, config):
    """Start a Chrome browser daemon with remote debugging."""
    if is_daemon_running(rdir):
        pid, cdp = get_daemon_info(rdir)
        print(f"Daemon already running: PID={pid}, CDP={cdp}")
        return True

    chrome = find_chrome()
    cdp_port = 9250
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
        for i in range(30):
            time.sleep(0.5)
            if is_port_open(cdp_port):
                with open(daemon_pid_file(rdir), "w") as f:
                    f.write(str(proc.pid))
                with open(daemon_cdp_file(rdir), "w") as f:
                    f.write(f"http://localhost:{cdp_port}")
                print(f"Daemon started: PID={proc.pid}")
                return True
        print("Timeout waiting for browser to start")
        proc.kill()
        return False
    except FileNotFoundError:
        print(f"Chrome not found at {chrome}. Please install Chrome or set PATH.")
        return False


def stop_daemon(rdir):
    """Stop the browser daemon."""
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


def is_daemon_running(rdir):
    pid_f = daemon_pid_file(rdir)
    cdp_f = daemon_cdp_file(rdir)
    if not pid_f.exists() or not cdp_f.exists():
        return False
    try:
        pid = int(pid_f.read_text().strip())
        if os.name == 'nt':
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True
            )
            return str(pid) in result.stdout
        else:
            os.kill(pid, 0)
            return True
    except (ValueError, FileNotFoundError, ProcessLookupError):
        _cleanup_daemon_files(rdir)
        return False


def get_daemon_info(rdir):
    pid = int(daemon_pid_file(rdir).read_text().strip())
    cdp = daemon_cdp_file(rdir).read_text().strip()
    return pid, cdp


def _cleanup_daemon_files(rdir):
    for f in [daemon_pid_file(rdir), daemon_cdp_file(rdir)]:
        if f.exists():
            f.unlink()


def cleanup_runtime(rdir):
    """Remove all stale runtime files and browser profile."""
    if not rdir.exists():
        print(f"Runtime dir does not exist: {rdir}")
        return

    stopped = False
    if is_daemon_running(rdir):
        print("Daemon is still running. Stopping first...")
        stop_daemon(rdir)
        stopped = True

    import shutil
    profile_dir = rdir / "browser_profile"
    removed = []

    if profile_dir.exists():
        shutil.rmtree(profile_dir)
        removed.append(str(profile_dir))

    for f in [daemon_pid_file(rdir), daemon_cdp_file(rdir)]:
        if f.exists():
            f.unlink()
            removed.append(str(f))

    if not stopped and not removed:
        print("Nothing to clean up.")
    else:
        for item in removed:
            print(f"  Removed: {item}")
        if stopped:
            print("  Stopped daemon")
        print("Cleanup complete.")


def is_port_open(port):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("localhost", port))
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


# ============================================================
# Path Validation (no output inside skill directory)
# ============================================================

def validate_output_path(output_path):
    out = Path(output_path).resolve()
    try:
        out.relative_to(SKILL_DIR)
        print(f"Error: Output path '{output_path}' is inside the skill directory ({SKILL_DIR}).")
        print(f"Please specify an output path outside the skill folder.")
        sys.exit(1)
    except ValueError:
        pass
    return out


# ============================================================
# JS Selectors
# ============================================================

JS_LIST_ELEMENTS = r"""() => {
    const result = { collapsible: [], tabs: [] };

    const collapseSections = document.querySelectorAll('section.collapse');
    for (const sec of collapseSections) {
        const titleEl = sec.querySelector('.expandable-title, .expandable-title-bold, .expandable-title-regular');
        const title = titleEl ? titleEl.textContent.trim() : 'untitled';
        const isExpanded = sec.classList.contains('open') || sec.classList.contains('expanded');
        result.collapsible.push({ title, expanded: isExpanded });
    }

    const tabGroups = document.querySelectorAll('[data-tag="tabbed-content-box"]');
    for (let i = 0; i < tabGroups.length; i++) {
        const group = tabGroups[i];
        const tabs = group.querySelectorAll('.tab-item');
        const tabList = [];
        for (const tab of tabs) {
            tabList.push({ text: tab.textContent.trim(), selected: tab.classList.contains('selected-tab-item') });
        }
        let context = '';
        let prev = group.previousElementSibling;
        for (let j = 0; j < 3 && prev; j++) {
            const txt = prev.textContent.trim().substring(0, 100);
            if (txt && txt.length > 5) { context = txt; break; }
            prev = prev.previousElementSibling;
        }
        result.tabs.push({ index: i, tabs: tabList, context });
    }

    return result;
}"""


# ============================================================
# Page Operations
# ============================================================

async def list_elements(page):
    return await page.evaluate(JS_LIST_ELEMENTS)


async def expand_section(page, title_text):
    collapse_titles = await page.query_selector_all(
        '.expandable-title, .expandable-title-bold, .expandable-title-regular'
    )
    for title_el in collapse_titles:
        text = (await title_el.inner_text()).strip()
        if title_text in text:
            is_expanded = await title_el.evaluate("""el => {
                let p = el.parentElement;
                while (p) {
                    if (p.tagName === 'SECTION') return p.classList.contains('open') || p.classList.contains('expanded');
                    p = p.parentElement;
                }
                return false;
            }""")
            if is_expanded:
                return False, f"Already expanded: {text}"
            await title_el.evaluate("el => el.click()")
            await asyncio.sleep(0.5)
            return True, f"Expanded: {text}"
    return False, f"Section not found: {title_text}"


async def switch_tab(page, tab_text, group_index=None):
    tab_groups = await page.query_selector_all('[data-tag="tabbed-content-box"]')
    groups_to_check = [tab_groups[group_index]] if group_index is not None else tab_groups

    for gi, group in enumerate(groups_to_check):
        tabs = await group.query_selector_all('.tab-item')
        for tab in tabs:
            text = (await tab.inner_text()).strip()
            if tab_text in text:
                is_selected = await tab.evaluate("el => el.classList.contains('selected-tab-item')")
                if is_selected:
                    return False, f"Already selected: {text} (group {gi})"
                await tab.click()
                await asyncio.sleep(1)
                return True, f"Switched to: {text} (group {gi})"
    return False, f"Tab not found: {tab_text}"


async def expand_all_sections(page):
    collapse_titles = await page.query_selector_all(
        '.expandable-title, .expandable-title-bold, .expandable-title-regular'
    )
    count = 0
    for title_el in collapse_titles:
        try:
            await title_el.evaluate("el => el.click()")
            await asyncio.sleep(0.3)
            count += 1
        except Exception:
            pass
    return count


async def switch_all_first_tabs(page):
    tab_groups = await page.query_selector_all('[data-tag="tabbed-content-box"]')
    switched = []
    for gi, group in enumerate(tab_groups):
        tabs = await group.query_selector_all('.tab-item')
        for tab in tabs:
            cls = await tab.get_attribute("class") or ""
            if "selected" not in cls:
                await tab.click()
                await asyncio.sleep(0.5)
                switched.append(f"group {gi}: {(await tab.inner_text()).strip()}")
                break
    return switched


async def take_screenshot(page, output, highlight=False, padding=30):
    output_path = validate_output_path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if highlight:
        crop_box = None
        content = await page.query_selector('article, .article, .content, #content, main')
        if content:
            box = await content.bounding_box()
            if box:
                crop_box = {
                    'x': max(0, box['x'] - padding),
                    'y': max(0, box['y'] - padding),
                    'width': box['width'] + padding * 2,
                    'height': box['height'] + padding * 2
                }

        if crop_box:
            tmp_path = output_path.with_suffix('.tmp.png')
            await page.screenshot(path=str(tmp_path), full_page=True)
            from PIL import Image, ImageDraw
            img = Image.open(str(tmp_path))
            left = int(crop_box['x'])
            top = int(crop_box['y'])
            right = min(img.width, int(crop_box['x'] + crop_box['width']))
            bottom = min(img.height, int(crop_box['y'] + crop_box['height']))
            img_crop = img.crop((left, top, right, bottom))
            draw = ImageDraw.Draw(img_crop)
            draw.rectangle([2, 2, img_crop.width - 3, img_crop.height - 3], outline='red', width=4)
            img_crop.save(str(output_path))
            tmp_path.unlink()
            return {"path": str(output_path), "size_kb": f"{output_path.stat().st_size / 1024:.1f}",
                    "dimensions": f"{img_crop.width}x{img_crop.height}"}
        else:
            await page.screenshot(path=str(output_path), full_page=True)
            return {"path": str(output_path), "size_kb": f"{output_path.stat().st_size / 1024:.1f}",
                    "note": "full page (no content area for crop)"}
    else:
        await page.screenshot(path=str(output_path), full_page=True)
        return {"path": str(output_path), "size_kb": f"{output_path.stat().st_size / 1024:.1f}"}


async def download_markdown(page, output):
    """Click 'Copy as MD' and save the markdown content."""
    btn = await page.query_selector('.CopyAsMarkdown--copyButton--SVGoWIG')
    if not btn:
        btns = await page.query_selector_all('button')
        for b in btns:
            t = (await b.inner_text()).strip()
            if "复制为 MD" in t:
                btn = b
                break
    if not btn:
        return None, "'Copy as MD' button not found"

    await btn.click()
    await asyncio.sleep(2)

    md = await page.evaluate("() => window._capturedMD")
    if md and len(md) > 100:
        output_path = validate_output_path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md.strip(), encoding="utf-8")
        return output_path, f"Saved ({output_path.stat().st_size / 1024:.1f} KB)"
    return None, "Failed to capture markdown content"


# ============================================================
# Daemon Connection
# ============================================================

async def get_daemon_page(rdir, config):
    """Connect to the running browser daemon and return the active page."""
    _, cdp_url = get_daemon_info(rdir)

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(cdp_url)

    contexts = browser.contexts
    if not contexts:
        context = await browser.new_context(
            viewport={"width": config["viewport_width"], "height": config["viewport_height"]}
        )
    else:
        context = contexts[0]

    pages = context.pages
    if pages:
        page = pages[-1]
    else:
        page = await context.new_page()

    # Ensure capture script is injected
    try:
        await page.evaluate("""
            if (!window._capturedMD_setup) {
                window._capturedMD = null;
                const origExec = Document.prototype.execCommand;
                Document.prototype.execCommand = function(cmd, ...args) {
                    if (cmd === 'copy') {
                        const sel = window.getSelection();
                        if (sel && sel.rangeCount > 0) {
                            window._capturedMD = sel.toString();
                        }
                    }
                    return origExec.call(this, cmd, ...args);
                };
                window._capturedMD_setup = true;
            }
        """)
    except Exception:
        pass

    return browser, pw, page


# ============================================================
# Single-shot Mode (no daemon)
# ============================================================

async def run_single_shot(url, actions=None, expand_all=False, switch_tabs=False,
                          screenshot=False, highlight=False, padding=30, output="output.png",
                          list_only=False, download_md=False):
    config = load_config()
    result = {"url": url, "actions_performed": []}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": config["viewport_width"], "height": config["viewport_height"]}
        )
        page = await ctx.new_page()

        await page.add_init_script("""
            window._capturedMD = null;
            const origExec = Document.prototype.execCommand;
            Document.prototype.execCommand = function(cmd, ...args) {
                if (cmd === 'copy') {
                    const sel = window.getSelection();
                    if (sel && sel.rangeCount > 0) {
                        window._capturedMD = sel.toString();
                    }
                }
                return origExec.call(this, cmd, ...args);
            };
        """)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            if list_only:
                result["elements"] = await list_elements(page)
                return result

            if expand_all:
                count = await expand_all_sections(page)
                result["actions_performed"].append(f"Expanded {count} sections")

            if switch_tabs:
                switched = await switch_all_first_tabs(page)
                result["actions_performed"].append(f"Switched {len(switched)} tab groups")

            if actions:
                for action in actions:
                    if action.startswith("expand:"):
                        success, msg = await expand_section(page, action[7:])
                        result["actions_performed"].append(msg)
                    elif action.startswith("tab:"):
                        parts = action[4:].split("@")
                        tab_text = parts[0]
                        group_idx = int(parts[1]) if len(parts) > 1 else None
                        success, msg = await switch_tab(page, tab_text, group_idx)
                        result["actions_performed"].append(msg)

            if screenshot and output:
                result["screenshot"] = await take_screenshot(page, output, highlight, padding)

            if download_md and output:
                md_path = output.replace(".png", ".md") if output.endswith(".png") else output + ".md"
                saved, msg = await download_markdown(page, md_path)
                if saved:
                    result["markdown"] = {"path": str(saved), "size_kb": f"{saved.stat().st_size / 1024:.1f}"}
                else:
                    result["markdown_error"] = msg

            result["title"] = await page.title()

        except Exception as e:
            result["error"] = str(e)
        finally:
            await browser.close()

    return result


# ============================================================
# Daemon Mode
# ============================================================

async def run_daemon_action(rdir, url=None, actions=None, expand_all=False,
                            switch_tabs=False, screenshot=False, highlight=False,
                            padding=30, output="output.png", download_md=False,
                            list_only=False):
    config = load_config()
    result = {"mode": "daemon", "actions_performed": []}

    browser = None
    pw = None
    try:
        browser, pw, page = await get_daemon_page(rdir, config)

        if url:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            result["url"] = url
        else:
            result["url"] = page.url

        if list_only:
            result["elements"] = await list_elements(page)
            return result

        if expand_all:
            count = await expand_all_sections(page)
            result["actions_performed"].append(f"Expanded {count} sections")

        if switch_tabs:
            switched = await switch_all_first_tabs(page)
            result["actions_performed"].append(f"Switched {len(switched)} tab groups")

        if actions:
            for action in actions:
                if action.startswith("expand:"):
                    success, msg = await expand_section(page, action[7:])
                    result["actions_performed"].append(msg)
                elif action.startswith("tab:"):
                    parts = action[4:].split("@")
                    tab_text = parts[0]
                    group_idx = int(parts[1]) if len(parts) > 1 else None
                    success, msg = await switch_tab(page, tab_text, group_idx)
                    result["actions_performed"].append(msg)

        if screenshot and output:
            result["screenshot"] = await take_screenshot(page, output, highlight, padding)

        if download_md and output:
            md_path = output.replace(".png", ".md") if output.endswith(".png") else output + ".md"
            saved, msg = await download_markdown(page, md_path)
            if saved:
                result["markdown"] = {"path": str(saved), "size_kb": f"{saved.stat().st_size / 1024:.1f}"}
            else:
                result["markdown_error"] = msg

        result["title"] = await page.title()

    except Exception as e:
        result["error"] = str(e)
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

    return result


# ============================================================
# CLI
# ============================================================

def _print_elements(elements):
    if not elements:
        return
    if "collapsible" in elements:
        print(f"\n=== Collapsible Sections ({len(elements['collapsible'])}) ===")
        for i, item in enumerate(elements["collapsible"]):
            status = "expanded" if item["expanded"] else "collapsed"
            print(f"  [{i}] \"{item['title']}\" ({status})")
    if "tabs" in elements:
        print(f"\n=== Tab Groups ({len(elements['tabs'])}) ===")
        for g in elements["tabs"]:
            tab_names = []
            for t in g["tabs"]:
                marker = "*" if t["selected"] else " "
                tab_names.append(f"{marker}{t['text']}")
            ctx = f" | Context: {g['context'][:60]}" if g["context"] else ""
            print(f"  Group {g['index']}: {' | '.join(tab_names)}{ctx}")


async def main():
    parser = argparse.ArgumentParser(
        description="Interact with help.aliyun.com doc components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Runtime state (daemon pid, cdp, config, browser profile) is stored in a
user-specified directory, NOT inside the skill or project directory.

  --runtime-dir DIR     Set runtime directory
                        (default: $TEMP/alidoc-runtime/)
  ALIDOC_RUNTIME_DIR    Environment variable override for --runtime-dir
"""
    )

    # Runtime directory
    parser.add_argument("--runtime-dir", default="",
                        help="Directory for daemon state files (default: system temp)")

    # Daemon management
    daemon_group = parser.add_argument_group("Daemon")
    daemon_group.add_argument("--start", action="store_true", help="Start persistent browser daemon")
    daemon_group.add_argument("--stop", action="store_true", help="Stop browser daemon")
    daemon_group.add_argument("--daemon-status", action="store_true", help="Check daemon status")
    daemon_group.add_argument("--cleanup", action="store_true", help="Remove stale runtime files and browser profile")

    # Actions
    parser.add_argument("--new", action="store_true", help="Open URL in persistent browser")
    parser.add_argument("--url", "-u", default="", help="Documentation page URL")
    parser.add_argument("--list", "-l", action="store_true", help="List collapsible sections and tab groups")
    parser.add_argument("--expand", "-e", action="append", default=[], help="Expand section by title")
    parser.add_argument("--tab", "-t", action="append", default=[], help="Switch tab (text@groupIndex)")
    parser.add_argument("--expand-all", action="store_true", help="Expand all collapsible sections")
    parser.add_argument("--switch-tabs", action="store_true", help="Switch all tab groups to first tab")

    # Output
    parser.add_argument("--screenshot", "-s", action="store_true", help="Take screenshot")
    parser.add_argument("--download-md", action="store_true", help="Download page as Markdown")
    parser.add_argument("--highlight", action="store_true", help="Add red border to screenshot")
    parser.add_argument("--padding", type=int, default=30, help="Padding around highlighted area")
    parser.add_argument("--output", "-o", default="", help="Output file path")

    # Config
    parser.add_argument("--config", action="store_true", help="Show runtime config")
    parser.add_argument("--set", default="", help="Set runtime config value (key=value)")
    parser.add_argument("--set-runtime-dir", default="", help="Permanently set runtime dir in skill config (empty to clear)")

    args = parser.parse_args()

    # Permanent runtime dir setting
    if args.set_runtime_dir is not None and "--set-runtime-dir" in " ".join(sys.argv):
        val = args.set_runtime_dir
        cfg_file = SCRIPT_DIR.parent / ".alidoc_runtime_config.json"
        if not val:
            # Clear: write empty config
            cfg_file.write_text("{}", encoding="utf-8")
            print("Runtime dir cleared. Using system temp dir.")
        else:
            rd = Path(val)
            rd.mkdir(parents=True, exist_ok=True)
            cfg_file.write_text(json.dumps({"runtime_dir": str(rd)}, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Runtime dir permanently set to: {rd}")
            print(f"  Config file: {cfg_file}")
        return

    rdir = get_runtime_dir(args)

    # Config management
    if args.config:
        config = load_config()
        if args.set:
            key, val = args.set.split("=", 1)
            config[key] = int(val) if val.isdigit() else val
            save_config(config)
            print(f"Config updated: {key} = {config[key]}")
        print(f"Runtime dir: {rdir}")
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return

    # Daemon management
    if args.start:
        ensure_runtime_dir(rdir)
        config = load_config()
        if start_daemon(rdir, config):
            print("Daemon ready. Use --new --url to open pages.")
        return

    if args.stop:
        stop_daemon(rdir)
        return

    if args.daemon_status:
        if is_daemon_running(rdir):
            pid, cdp = get_daemon_info(rdir)
            print(f"Daemon running: PID={pid}, CDP={cdp}")
            print(f"Runtime dir: {rdir}")
        else:
            print("Daemon not running. Use --start to launch.")
        return

    if args.cleanup:
        cleanup_runtime(rdir)
        return

    # Daemon mode or single-shot
    use_daemon = args.new or (is_daemon_running(rdir) and not args.url and not args.list)
    if is_daemon_running(rdir) and not args.url:
        use_daemon = True

    actions = []
    for e in args.expand:
        actions.append(f"expand:{e}")
    for t in args.tab:
        actions.append(f"tab:{t}")

    if not args.output and (args.screenshot or args.download_md):
        if args.url:
            import re
            match = re.search(r'/zh/([^?]+)', args.url)
            slug = match.group(1).rstrip("/").replace("/", "_") if match else "doc"
            args.output = f"{slug}_interact.png"
        else:
            args.output = "doc_interact.png"

    if use_daemon and is_daemon_running(rdir):
        # Daemon mode
        result = await run_daemon_action(
            rdir=rdir,
            url=args.url if args.new else None,
            actions=actions if actions else None,
            expand_all=args.expand_all,
            switch_tabs=args.switch_tabs,
            screenshot=args.screenshot,
            highlight=args.highlight,
            padding=args.padding,
            output=args.output,
            download_md=args.download_md,
            list_only=args.list
        )
        if args.list and "elements" in result:
            _print_elements(result["elements"])
    else:
        # Single-shot mode
        if not args.url:
            parser.print_help()
            return

        result = await run_single_shot(
            url=args.url,
            actions=actions if actions else None,
            expand_all=args.expand_all,
            switch_tabs=args.switch_tabs,
            screenshot=args.screenshot,
            highlight=args.highlight,
            padding=args.padding,
            output=args.output,
            list_only=args.list,
            download_md=args.download_md
        )

        if args.list and "elements" in result:
            _print_elements(result["elements"])

    output_result = dict(result)
    if "elements" in output_result:
        del output_result["elements"]
    print(json.dumps(output_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
