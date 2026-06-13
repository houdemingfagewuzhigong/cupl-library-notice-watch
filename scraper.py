#!/usr/bin/env python3
"""Fetch CUPL Library public notices and keep a daily history."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


BASE_URL = "https://lib.cupl.edu.cn"
HOME_URL = BASE_URL + "/"
NOTICE_URL = BASE_URL + "/"
DATA_DIR = Path("data")


@dataclass
class Notice:
    id: str
    title: str
    date: str
    url: str
    summary: str
    section: str
    source_url: str
    first_seen_at: str
    last_seen_at: str


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def clean(text: str) -> str:
    text = re.sub(r"<script.*?</script>", "", text or "", flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<.*?>", "", text, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def notice_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def node_executable() -> str:
    bundled = Path("/Users/songshiji/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
    return str(bundled) if bundled.exists() else "node"


def browser_fetch(max_items: int) -> tuple[list[dict], dict[str, str]]:
    script = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const maxItems = Number(process.argv[2] || 20);
  const launchOptions = { headless: true };
  const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  if (fs.existsSync(macChrome)) launchOptions.executablePath = macChrome;
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
  });
  const diagnostics = {};
  const items = [];
  try {
    await page.goto('https://lib.cupl.edu.cn/', { waitUntil: 'networkidle', timeout: 45000 });
    await page.waitForTimeout(2500);
    const bodyText = await page.locator('body').innerText({ timeout: 10000 }).catch(() => '');
    if (bodyText.includes('访问被限制')) diagnostics.home = 'site returned access restriction page';
    const links = await page.$$eval('a', (as, limit) => as.map(a => ({
      text: (a.innerText || a.textContent || '').trim(),
      href: a.href
    })).filter(x => x.href && x.text && /通知|公告|新闻|资源|服务|讲座|培训/i.test(x.text) && !/更多|首页|登录/.test(x.text)).slice(0, limit), maxItems);
    if (!links.length) diagnostics.links = 'no public notice-like links matched; body starts with: ' + bodyText.slice(0, 120);
    for (const link of links) {
      let date = '';
      const dateMatch = link.text.match(/20\d{2}[-年.\/]\d{1,2}[-月.\/]\d{1,2}/);
      if (dateMatch) date = dateMatch[0].replace(/[年月.\/]/g, '-').replace(/日/g, '').replace(/-(\d)(?=-|$)/g, '-0$1');
      items.push({ title: link.text, url: link.href, date, summary: '' });
    }
  } catch (error) {
    diagnostics.browser = error.message;
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify({ items, diagnostics }));
})();
"""
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False) as fh:
        fh.write(script)
        path = fh.name
    try:
        env = os.environ.copy()
        node_path = "/Users/songshiji/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
        if Path(node_path).exists():
            env["NODE_PATH"] = node_path
        result = subprocess.run([node_executable(), path, str(max_items)], text=True, capture_output=True, timeout=90, env=env)
        if result.returncode != 0:
            return [], {"browser": result.stderr.strip() or f"node exited {result.returncode}"}
        payload = json.loads(result.stdout or "{}")
        return payload.get("items", []), payload.get("diagnostics", {})
    finally:
        Path(path).unlink(missing_ok=True)


def fetch(max_items: int = 20) -> tuple[list[Notice], dict[str, str]]:
    seen_at = now_iso()
    raw_items, diagnostics = browser_fetch(max_items)
    notices = [
        Notice(
            id=notice_id(item["url"]),
            title=clean(item.get("title", "")),
            date=item.get("date", ""),
            url=item["url"],
            summary=clean(item.get("summary", "")),
            section="图书馆公开信息",
            source_url=HOME_URL,
            first_seen_at=seen_at,
            last_seen_at=seen_at,
        )
        for item in raw_items
        if item.get("url") and item.get("title")
    ]
    unique = {notice.id: notice for notice in notices}
    return sorted(unique.values(), key=lambda item: (item.date, item.title), reverse=True), diagnostics


def load_existing() -> dict[str, Notice]:
    path = DATA_DIR / "notices.json"
    if not path.exists():
        return {}
    return {item["id"]: Notice(**item) for item in json.loads(path.read_text(encoding="utf-8"))}


def save(notices: list[Notice], diagnostics: dict[str, str]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "history").mkdir(exist_ok=True)
    existing = load_existing()
    merged = existing.copy()
    seen_at = now_iso()
    for notice in notices:
        if notice.id in merged:
            notice.first_seen_at = merged[notice.id].first_seen_at
        notice.last_seen_at = seen_at
        merged[notice.id] = notice
    rows = sorted(merged.values(), key=lambda item: (item.date, item.title), reverse=True)
    payload = [asdict(item) for item in rows]
    (DATA_DIR / "notices.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DATA_DIR / "history" / f"{dt.date.today().isoformat()}.json").write_text(json.dumps([asdict(item) for item in notices], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (DATA_DIR / "notices.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(Notice.__dataclass_fields__.keys()))
        writer.writeheader()
        writer.writerows(payload)
    meta = {
        "site": "中国政法大学图书馆",
        "home_url": HOME_URL,
        "notice_url": NOTICE_URL,
        "updated_at": seen_at,
        "total_notices": len(rows),
        "sections": ["图书馆公开信息"],
        "latest_date": rows[0].date if rows else None,
        "diagnostics": diagnostics,
        "disclaimer": "非官方项目，仅归档公开网页信息，不代表中国政法大学官方。",
    }
    (DATA_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    max_items = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    notices, diagnostics = fetch(max_items)
    save(notices, diagnostics)
    print(f"fetched {len(notices)} notices from CUPL Library public pages")
    if notices:
        print(f"latest: {notices[0].date or 'unknown-date'} {notices[0].title}")
    if diagnostics:
        print("diagnostics:", json.dumps(diagnostics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
