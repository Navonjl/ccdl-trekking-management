"""Screenshots of the live application for Chapter 3, one per role.

    ADMIN_PASSWORD=... uv run --no-project --with playwright python docs/report/measure/screenshots.py
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = "https://hitc602.centralindia.cloudapp.azure.com"
FIGS = Path(__file__).resolve().parent.parent / "figures"
VIEW = {"width": 1280, "height": 760}


def login(page, email, password):
    page.goto(SITE + "/login")
    page.fill("#email", email)
    page.fill("#password", password)
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("networkidle")


def shot(page, name):
    page.wait_for_timeout(600)
    page.screenshot(path=str(FIGS / name))
    print("wrote", name)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/chromium")

    def fresh():
        # A new context per role, so no session carries over between logins.
        return browser.new_context(viewport=VIEW, device_scale_factor=2).new_page()

    page = fresh()
    page.goto(SITE + "/login")
    page.wait_for_load_state("networkidle")
    shot(page, "app-login.png")

    login(page, "asha@example.com", "trekker123")
    shot(page, "app-browse.png")
    page.goto(SITE + "/bookings")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Export as CSV").click()
    page.get_by_text("Your export is ready.").wait_for(timeout=60000)
    shot(page, "app-export.png")

    page = fresh()
    login(page, "admin@example.com", os.environ["ADMIN_PASSWORD"])
    page.wait_for_selector("canvas")
    shot(page, "app-admin.png")

    page = fresh()
    login(page, "ramesh.staff@example.com", "staff123")
    shot(page, "app-staff.png")

    browser.close()
