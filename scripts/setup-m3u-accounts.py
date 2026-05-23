"""Setup M3U accounts in Dispatcharr via Playwright browser automation"""

import os
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Load secrets
env_file = os.path.join(os.path.dirname(__file__), "..", ".env.secrets")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key] = val

DISPATCHARR_URL = "http://localhost:9191"
USERNAME = os.environ.get("DISPATCHARR_ADMIN_USERNAME")
PASSWORD = os.environ.get("DISPATCHARR_ADMIN_PASSWORD")
if not USERNAME or not PASSWORD:
    print("ERROR: DISPATCHARR_ADMIN_USERNAME and DISPATCHARR_ADMIN_PASSWORD must be set")
    sys.exit(1)

MEGA_SERVER = os.environ.get("MEGA_SERVER", "")
MEGA_USERNAME = os.environ.get("MEGA_USERNAME", "")
MEGA_PASSWORD = os.environ.get("MEGA_PASSWORD", "")

STRONG_SERVER = os.environ.get("STRONG_SERVER", "")
STRONG_USERNAME = os.environ.get("STRONG_USERNAME", "")
STRONG_PASSWORD = os.environ.get("STRONG_PASSWORD", "")


def add_m3u_account(page, name, server, username, password, account_type="XC"):
    """Add an M3U account via the Dispatcharr UI"""
    print(f"  Adding {name} account...")

    # Navigate to M3U accounts page
    page.goto(f"{DISPATCHARR_URL}/settings/m3u", wait_until="networkidle")
    time.sleep(2)

    # Click "Add Account" button
    add_button = page.get_by_role("button", name="Add Account")
    if not add_button.is_visible():
        # Try alternative selectors
        add_button = page.get_by_text("Add Account")
    add_button.click()
    time.sleep(1)

    # Fill in account details
    # Name field
    name_input = page.get_by_label("Name")
    if not name_input.is_visible():
        name_input = page.locator('input[name="name"]').first
    name_input.fill(name)

    # Account type - select XC (Xtream Codes)
    type_select = page.get_by_label("Account Type")
    if not type_select.is_visible():
        type_select = page.locator('select[name="account_type"]').first
    type_select.select_option("XC")

    # Server URL
    server_input = page.get_by_label("Server URL")
    if not server_input.is_visible():
        server_input = page.locator('input[name="server_url"]').first
    server_input.fill(server)

    # Username
    user_input = page.get_by_label("Username")
    if not user_input.is_visible():
        user_input = page.locator('input[name="username"]').first
    user_input.fill(username)

    # Password
    pass_input = page.get_by_label("Password")
    if not pass_input.is_visible():
        pass_input = page.locator('input[name="password"]').first
    pass_input.fill(password)

    # Click Save/Create
    save_button = page.get_by_role("button", name="Save")
    if not save_button.is_visible():
        save_button = page.get_by_role("button", name="Create")
    if not save_button.is_visible():
        save_button = page.get_by_text("Save")
    save_button.click()

    # Wait for success message or account to appear
    time.sleep(3)
    print(f"  ✓ {name} account added")


def login(page):
    """Login to Dispatcharr"""
    print(f"Logging in as {USERNAME}...")
    page.goto(f"{DISPATCHARR_URL}/login", wait_until="networkidle")
    time.sleep(2)

    # Fill login form
    username_input = page.get_by_label("Username")
    if not username_input.is_visible():
        username_input = page.locator('input[name="username"]').first
    username_input.fill(USERNAME)

    password_input = page.get_by_label("Password")
    if not password_input.is_visible():
        password_input = page.locator('input[name="password"]').first
    password_input.fill(PASSWORD)

    # Click login
    login_button = page.get_by_role("button", name="Login")
    if not login_button.is_visible():
        login_button = page.get_by_text("Login")
    login_button.click()

    # Wait for navigation
    time.sleep(3)
    print("✓ Logged in")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        try:
            login(page)

            # Add MEGA account
            if MEGA_SERVER and MEGA_USERNAME and MEGA_PASSWORD:
                add_m3u_account(page, "MEGA", MEGA_SERVER, MEGA_USERNAME, MEGA_PASSWORD)

            # Add STRONG account
            if STRONG_SERVER and STRONG_USERNAME and STRONG_PASSWORD:
                add_m3u_account(page, "STRONG", STRONG_SERVER, STRONG_USERNAME, STRONG_PASSWORD)

            print("\n✓ All M3U accounts added")

        except PlaywrightTimeout as e:
            print(f"\n✗ Timeout: {e}")
            page.screenshot(path="/tmp/dispatcharr_error.png")
            print("Screenshot saved to /tmp/dispatcharr_error.png")
            sys.exit(1)
        except Exception as e:
            print(f"\n✗ Error: {e}")
            page.screenshot(path="/tmp/dispatcharr_error.png")
            print("Screenshot saved to /tmp/dispatcharr_error.png")
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()