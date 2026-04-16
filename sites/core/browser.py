from playwright.sync_api import sync_playwright
from .settings import DEFAULT_USER_AGENT, HEADLESS, LOCALE, TIMEOUT, TIMEZONE_ID


def create_browser_context(playwright):
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale=LOCALE,
        timezone_id=TIMEZONE_ID,
        user_agent=DEFAULT_USER_AGENT,
    )
    return browser, context


def open_page(context, url, wait_until="domcontentloaded", timeout=TIMEOUT, sleep_ms=1200):
    page = context.new_page()
    page.goto(url, wait_until=wait_until, timeout=timeout)
    page.wait_for_timeout(sleep_ms)
    return page