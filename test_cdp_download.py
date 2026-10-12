import sys
import os
import platform
import asyncio
from playwright.async_api import async_playwright

if platform.system() == "Windows":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

async def test_download():
    # Detect candidate CDP URLs: explicit env var, Docker bridge gateway, LAN IP, Tailscale IP, localhost
    default_candidates = [
        os.environ.get("GOODINFO_CDP_URL"),
        "http://172.21.0.1:9222",
        "http://192.168.31.101:9222",
        "http://100.110.72.104:9222",
        "http://127.0.0.1:9222"
    ]
    candidates = [c for c in default_candidates if c]

    async with async_playwright() as p:
        browser = None
        for candidate_url in candidates:
            try:
                print(f"[1/5] Testing Chromium CDP connection at {candidate_url} ...")
                browser = await p.chromium.connect_over_cdp(candidate_url, timeout=5000)
                print(f"   Connected successfully to CDP at {candidate_url}")
                break
            except Exception as e:
                print(f"   CDP connection to {candidate_url} failed: {e}")

        if not browser:
            raise ConnectionError(f"Could not connect to any Chromium CDP endpoint in {candidates}")

        context = browser.contexts[0]
        page = await context.new_page()

        # Apply stealth evasions
        try:
            from playwright_stealth import Stealth
            stealth_config = Stealth(
                navigator_webdriver=True,
                chrome_app=True,
                chrome_csi=True,
                chrome_load_times=True,
                navigator_languages_override=('zh-TW', 'zh', 'en-US', 'en'),
                navigator_platform_override='Win32'
            )
            await stealth_config.apply_stealth_async(page)
            print("   [Stealth] Applied playwright-stealth evasions.")
        except Exception as stealth_err:
            print(f"   [Stealth] Warning: {stealth_err}")

        url = "https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID=2330"
        print(f"[2/5] Navigating to {url} ...")
        
        for attempt in range(1, 4):
            print(f"   Navigating attempt {attempt}/3 ...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            title = await page.title()
            print(f"   Attempt {attempt} Title: {title}")
            if "522" not in title and "523" not in title and "520" not in title and "524" not in title:
                break
            print(f"   Origin server transient error ({title}). Waiting 5s before retry...")
            await asyncio.sleep(5)
        print(f"[3/5] Page title: {title}")

        # Handle Cloudflare Challenge (Automatic wait first, fallback to click)
        for wait_sec in range(12):
            title = await page.title()
            if "Just a moment" not in title and "Cloudflare" not in title and title.strip() != "":
                print(f"   [Turnstile] Verified automatically or bypassed! Page title: {title}")
                break
            print(f"   [Turnstile] Waiting for verification... ({wait_sec + 1}/12, title={title})")
            
            # If after 5 seconds still not verified, try locating and clicking Turnstile checkbox iframe
            if wait_sec >= 4:
                try:
                    for frame in page.frames:
                        if "challenges.cloudflare.com" in frame.url:
                            print("   [Turnstile] Found challenges.cloudflare.com frame, attempting click...")
                            # Click checkbox or stage inside frame
                            await frame.click("body", timeout=2000)
                            break
                    else:
                        iframes = await page.query_selector_all("iframe[src*='cloudflare']")
                        if iframes:
                            box = await iframes[0].bounding_box()
                            if box:
                                click_x = box['x'] + 28
                                click_y = box['y'] + (box['height'] / 2)
                                print(f"   [Turnstile] Clicking iframe bounding box ({click_x:.1f}, {click_y:.1f})...")
                                await page.mouse.click(click_x, click_y)
                except Exception as click_err:
                    print(f"   [Turnstile] Fallback click notice: {click_err}")

            await page.wait_for_timeout(1500)

        title = await page.title()
        print(f"[3/5] Active page title: {title}")
        await page.wait_for_timeout(2000)

        print("[4/5] Extracting table tblDetail ...")
        table_html = await page.evaluate("""() => {
            const tbl = document.getElementById('tblDetail') || window['tblDetail'];
            if (tbl) return tbl.outerHTML;
            const tables = Array.from(document.querySelectorAll('table')).filter(
                t => t.rows && t.rows.length >= 2 && t.innerText.length > 80
            );
            if (tables.length > 0) return tables[0].outerHTML;
            return null;
        }""")

        if table_html:
            import io
            import pandas as pd
            clean_html = "<html><head><meta charset='UTF-8'></head><body>" + table_html + "</body></html>"
            
            # Pure in-memory parsing via io.StringIO (0 Disk I/O)
            dfs = pd.read_html(io.StringIO(clean_html))
            if dfs:
                df = dfs[0]
                mem_bytes = df.memory_usage(deep=True).sum()
                print(f"[5/5] SUCCESS (In-Memory)! Extracted DataFrame: shape={df.shape}, memory={mem_bytes} bytes (Zero Disk I/O)")
                print("   [In-Memory Preview Top 3 Rows]:")
                for idx, row in df.iloc[:3, :4].iterrows():
                    print(f"      Row {idx}: {dict(row)}")

                # Export raw payload if requested (for GitHub Actions artifact transfer)
                for arg in sys.argv:
                    if arg.startswith("--export-payload="):
                        payload_path = arg.split("=", 1)[1]
                        with open(payload_path, "w", encoding="utf-8") as pf:
                            pf.write(clean_html)
                        print(f"   [Payload] Exported {len(clean_html)} chars to {payload_path}")

                # Optional disk persistence only if explicitly requested via --save
                if "--save" in sys.argv:
                    out_dir = os.path.join(os.getcwd(), "DividendDetail")
                    os.makedirs(out_dir, exist_ok=True)
                    out_file = os.path.join(out_dir, "DividendDetail_2330_台積電.xls")
                    with open(out_file, "w", encoding="utf-8-sig") as f:
                        f.write(clean_html)
                    print(f"   [--save] Saved to disk: {out_file} ({os.path.getsize(out_file)} bytes)")
                return df
            else:
                print("[5/5] ERROR: No tables parsed from HTML in memory!")
                return None
        else:
            print("[5/5] ERROR: Table tblDetail not found!")
            await page.screenshot(path="cdp_failure_screenshot.png", full_page=True)
            content = await page.content()
            with open("cdp_failure_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("   Saved cdp_failure_screenshot.png and cdp_failure_page.html for diagnosis.")
            await page.close()
            sys.exit(1)

        await page.close()

if __name__ == "__main__":
    res = asyncio.run(test_download())
    if res is None:
        sys.exit(1)
