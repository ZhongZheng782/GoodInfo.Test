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
    async with async_playwright() as p:
        print("[1/5] Connecting to Chromium CDP at http://192.168.31.101:9222 ...")
        browser = await p.chromium.connect_over_cdp("http://192.168.31.101:9222")
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
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        title = await page.title()
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
            out_dir = os.path.join(os.getcwd(), "DividendDetail")
            os.makedirs(out_dir, exist_ok=True)
            out_file = os.path.join(out_dir, "DividendDetail_2330_台積電.xls")
            
            clean_html = "<html><head><meta charset='UTF-8'></head><body>" + table_html + "</body></html>"
            with open(out_file, "w", encoding="utf-8-sig") as f:
                f.write(clean_html)
            file_size = os.path.getsize(out_file)
            print(f"[5/5] SUCCESS! File saved to: {out_file} ({file_size} bytes)")
        else:
            print("[5/5] ERROR: Table tblDetail not found!")
            await page.screenshot(path="cdp_failure_screenshot.png", full_page=True)
            content = await page.content()
            with open("cdp_failure_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("   Saved cdp_failure_screenshot.png and cdp_failure_page.html for diagnosis.")

        await page.close()

if __name__ == "__main__":
    asyncio.run(test_download())
