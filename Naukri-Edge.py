"""
Naukri Auto-Apply Bot - Keyword Search Edition (Fixed 2026)
==========================================================
Automates job applications on Naukri.com using Selenium with Edge browser.
Scrapes keyword search result pages in small batches (4 tabs at a time).
Applies directly to Naukri jobs and solves chatbot questionnaires automatically.
"""

import os
import re
import csv
import sys
import time
import random
import getpass
import logging
import importlib.util
from pathlib import Path
from urllib.parse import quote_plus

from bot_config import (
    load_project_env,
    project_dir,
    is_keep_browser_open,
    is_job_title_allowed,
    TITLE_WHITELIST,
    TITLE_BLACKLIST,
)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# ------------------------------------------------------------
# Configuration & Project Environment
# ------------------------------------------------------------
PROJECT_DIR = project_dir(__file__)
load_project_env(__file__)

# Import shared helpers from Naukri-Recommended.py
rec_script = PROJECT_DIR / "Naukri-Recommended.py"
spec = importlib.util.spec_from_file_location("naukri_rec", rec_script)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {rec_script}")
naukri_rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(naukri_rec)

handle_chatbot_drawer = naukri_rec.handle_chatbot_drawer
load_answers = naukri_rec.load_answers
load_previously_applied_urls = naukri_rec.load_previously_applied_urls
login_naukri = naukri_rec.login_naukri
save_confirmed_applications = getattr(naukri_rec, 'save_confirmed_applications', None)
create_edge_driver = naukri_rec.create_edge_driver

# Personal Details
FIRSTNAME = os.getenv('FIRSTNAME', '').strip()
LASTNAME = os.getenv('LASTNAME', '').strip()

# Job Search
KEYWORDS = [kw.strip() for kw in os.getenv('KEYWORDS', '').split(',') if kw.strip()]
LOCATION = os.getenv('LOCATION', '').strip()

# Limits & Anti-Detection Safety Cap (Recommended: 20-30 max)
raw_max = os.getenv('MAX_APPLICATIONS', '25')
try:
    parsed_max = int(raw_max)
except ValueError:
    parsed_max = 25

MAX_APPLICATIONS = min(30, max(1, parsed_max))

try:
    PAGES_PER_KEYWORD = max(1, min(10, int(os.getenv('PAGES_PER_KEYWORD', '2'))))
except ValueError:
    PAGES_PER_KEYWORD = 2

KEEP_BROWSER_OPEN = is_keep_browser_open()
EDGE_DRIVER_PATH = os.getenv('EDGE_DRIVER_PATH', '').strip()

# ------------------------------------------------------------
# Logging Setup
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def human_delay(min_sec=1.2, max_sec=2.8, reason=None):
    """Generate dynamic delays to simulate human interactions."""
    delay = random.uniform(min_sec, max_sec)
    msg = f"Sleeping for {delay:.2f} seconds..."
    if reason:
        msg += f" ({reason})"
    logger.info(msg)
    time.sleep(delay)


def get_credentials():
    """Retrieve credentials from .env or CLI prompt."""
    email = os.getenv('NAUKRI_EMAIL', '').strip()
    password = os.getenv('NAUKRI_PASSWORD', '').strip()

    if not email:
        print("\n[Security] NAUKRI_EMAIL not found in environment.")
        email = input("Enter your Naukri Email: ").strip()

    if not password:
        print("[Security] NAUKRI_PASSWORD not found in environment.")
        password = getpass.getpass("Enter your Naukri Password: ").strip()

    return email, password


def validate_config(email, password):
    """Check that required configuration values are set."""
    errors = []
    if not email:
        errors.append("Naukri email is missing.")
    if not password:
        errors.append("Naukri password is missing.")
    if not KEYWORDS:
        errors.append("KEYWORDS is not set (comma-separated job roles).")
    if errors:
        for e in errors:
            logger.error(e)
        return False
    return True


def build_search_urls():
    """
    Build valid Naukri search URLs even when LOCATION has multiple comma-separated cities.
    Avoids invalid comma-separated path slugs like bangalore,-bengaluru.
    """
    urls = []
    raw_locs = [loc.strip() for loc in LOCATION.split(',') if loc.strip()]
    # Remove duplicate 'bengaluru' if 'bangalore' is already present
    cleaned_locs = []
    for l in raw_locs:
        if l.lower() == "bengaluru" and any(x.lower() == "bangalore" for x in raw_locs):
            continue
        cleaned_locs.append(l)

    loc_slug = "-".join(re.sub(r"[^a-z0-9]+", "-", l.lower()).strip("-") for l in cleaned_locs)
    loc_query = ", ".join(cleaned_locs)

    for keyword in KEYWORDS:
        keyword_slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")
        for page_num in range(1, PAGES_PER_KEYWORD + 1):
            page_suffix = f"-{page_num}" if page_num > 1 else ""
            if not cleaned_locs:
                url = f"https://www.naukri.com/{keyword_slug}-jobs{page_suffix}?k={quote_plus(keyword)}"
            else:
                url = (
                    f"https://www.naukri.com/{keyword_slug}-jobs-in-{loc_slug}{page_suffix}"
                    f"?k={quote_plus(keyword)}&l={quote_plus(loc_query)}"
                )
            urls.append((keyword, url))
    return urls


def extract_title_from_url_slug(url: str) -> str:
    """
    Fallback extractor that parses the job title from a Naukri URL slug:
    e.g. 'https://www.naukri.com/job-listings-generative-ai-developer-infosys-pune-3-to-8-years-131026043475'
    -> 'generative ai developer infosys'
    """
    try:
        slug = url.split("job-listings-")[-1].split("?")[0]
        # Strip trailing '-X-to-Y-years-<job_id>'
        slug = re.sub(r"-\d+-to-\d+-years-\d+$", "", slug)
        slug = re.sub(r"-\d+$", "", slug)
        return slug.replace("-", " ").strip()
    except Exception:
        return ""


def extract_job_title_reliably(driver, link: str) -> str:
    """
    Waits for Naukri's React SPA to render the job title <h1> on the JD page.
    Falls back to DOM textContent, document.title, and finally the URL slug so it NEVER returns empty.
    """
    title_selectors = (
        "h1.jd-header-title",
        "h1[class*='jd-header-title']",
        "div[class*='jd-header-title']",
        "header h1",
        "h1",
    )

    # 1. Wait up to 6 seconds for the <h1> element to mount in the React DOM
    try:
        WebDriverWait(driver, 6, poll_frequency=0.3).until(
            lambda d: any(
                (el.text or el.get_attribute("textContent") or "").strip()
                for el in d.find_elements(By.CSS_SELECTOR, ", ".join(title_selectors))
            )
        )
    except Exception:
        pass

    # 2. Try reading visible text or textContent from title selectors
    for sel in title_selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                txt = (el.text or el.get_attribute("textContent") or el.get_attribute("title") or "").strip()
                if txt:
                    return " ".join(txt.split())
        except Exception:
            continue

    # 3. Fallback to document.title (e.g., "Generative AI Developer - Job Openings in ...")
    try:
        doc_title = (driver.title or "").strip()
        if doc_title and "naukri.com" not in doc_title.lower()[:12]:
            return doc_title.split(" - ")[0].strip()
    except Exception:
        pass

    # 4. Ultimate fallback: parse directly from the Naukri URL slug
    return extract_title_from_url_slug(link)


def collect_job_links_from_tab(driver, window_handle):
    """Switch to a specific tab and scrape job links from the page, pre-filtering GenAI titles."""
    links = []
    try:
        driver.switch_to.window(window_handle)
        human_delay(2.0, 3.5, reason="wait for search results render")

        selectors = [
            "div.srp-jobtuple-wrapper a.title",
            "div.cust-job-tuple a.title",
            "article.jobTuple a.title",
            "a.title",
        ]
        anchors = []
        for selector in selectors:
            anchors = [el for el in driver.find_elements(By.CSS_SELECTOR, selector) if el.is_displayed()]
            if anchors:
                break
        logger.info(f"[Tab: {driver.title[:45]}] Found {len(anchors)} job links")
        for anchor in anchors:
            href = (anchor.get_attribute('href') or '').strip()
            card_title = (
                anchor.get_attribute('title')
                or anchor.text
                or anchor.get_attribute('textContent')
                or extract_title_from_url_slug(href)
            ).strip()
            if href and href.startswith('https://www.naukri.com/'):
                allowed, _ = is_job_title_allowed(card_title)
                if allowed:
                    links.append(href)

    except WebDriverException as e:
        logger.warning(f"[Tab] Error reading tab: {e}")

    return links


def collect_all_jobs_parallel(driver, search_urls, batch_size=4):
    """
    Open search pages in small batches (4 tabs at a time) to prevent Edge freezing
    and avoid Cloudflare / Naukri bot rate-limiting.
    Returns a deduplicated list of job URLs.
    """
    logger.info("=" * 50)
    logger.info(f"Opening {len(search_urls)} search pages in batches of {batch_size}...")
    logger.info("=" * 50)

    original_window = driver.current_window_handle
    all_links = []

    for batch_idx in range(0, len(search_urls), batch_size):
        batch = search_urls[batch_idx:batch_idx + batch_size]
        logger.info(f"--- Batch {batch_idx // batch_size + 1}: Opening {len(batch)} search tab(s) ---")

        opened_handles = []
        for idx, (kw, url) in enumerate(batch):
            if idx == 0 and len(driver.window_handles) == 1:
                driver.get(url)
                opened_handles.append(original_window)
            else:
                driver.switch_to.new_window('tab')
                driver.get(url)
                opened_handles.append(driver.current_window_handle)
            human_delay(1.5, 2.5, reason="staggered tab load")

        for handle in opened_handles:
            tab_links = collect_job_links_from_tab(driver, handle)
            all_links.extend(tab_links)

        # Close extra tabs from this batch and return to original window
        for handle in opened_handles:
            if handle != original_window:
                try:
                    driver.switch_to.window(handle)
                    driver.close()
                except WebDriverException:
                    pass
        driver.switch_to.window(original_window)
        human_delay(1.0, 2.0, reason="batch pause")

    # Deduplicate while preserving order
    seen = set()
    unique_links = []
    for link in all_links:
        clean = link.split('?')[0]
        if clean not in seen:
            seen.add(clean)
            unique_links.append(link)

    logger.info(f"Total unique job links collected: {len(unique_links)}")
    return unique_links


def click_apply_button(driver):
    """
    Click ONLY direct Naukri 'Apply' buttons (skipping 'Apply on company site' external redirects
    and 'Already Applied' badges).
    """
    human_delay(1.8, 3.0, reason="pre-apply check")

    # Check if already applied
    already = driver.find_elements(By.XPATH, "//*[contains(@id,'already-applied') or contains(text(),'Already Applied')]")
    if any(el.is_displayed() for el in already):
        logger.info("  ℹ️ Already applied to this job. Skipping.")
        return False

    # Direct Apply selectors (strictly excluding 'company site')
    direct_selectors = [
        (By.ID, "apply-button"),
        (By.CSS_SELECTOR, "button.apply-button"),
        (By.XPATH, "//button[normalize-space()='Apply']"),
        (By.XPATH, "//button[contains(@class,'apply-button') and not(contains(translate(., 'COMPANY', 'company'), 'company'))]"),
        (By.XPATH, "//button[contains(translate(., 'APPLY', 'apply'), 'apply') and not(contains(translate(., 'COMPANY', 'company'), 'company'))]"),
    ]

    for by, selector in direct_selectors:
        try:
            btns = driver.find_elements(by, selector)
            for btn in btns:
                txt = (btn.text or "").strip().lower()
                if btn.is_displayed() and btn.is_enabled() and "company" not in txt and "apply" in txt:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    return True
        except Exception:
            continue

    return False


def apply_to_jobs(driver, job_links, known_answers):
    """
    Visit each job link, check title whitelist, click Direct Apply,
    and handle any chatbot questionnaires automatically.
    """
    applied = 0
    failed = 0
    applied_list = {'passed': [], 'failed': []}
    previously_applied = load_previously_applied_urls()

    logger.info("=" * 50)
    logger.info(f"Starting job applications (safe cap: {MAX_APPLICATIONS})...")
    logger.info("=" * 50)

    for i, link in enumerate(job_links, 1):
        if applied >= MAX_APPLICATIONS:
            logger.info(f"Reached max application limit ({MAX_APPLICATIONS}). Stopping run.")
            break

        clean_url = link.split('?')[0]
        if clean_url in previously_applied:
            logger.info(f"[{i}/{len(job_links)}] ⏭️ Already applied previously: {clean_url}")
            continue

        logger.info(f"[{i}/{len(job_links)}] Visiting: {link}")
        try:
            driver.get(link)
        except WebDriverException as e:
            logger.warning(f"  ✗ Failed to load page: {e}")
            failed += 1
            applied_list['failed'].append(link)
            continue

        # Wait for React JD page to render and extract title reliably (with URL slug fallback)
        page_title = extract_job_title_reliably(driver, link)
        allowed, reason = is_job_title_allowed(page_title)
        if not allowed:
            # Double-check URL slug in case DOM h1 had a generic company header
            slug_title = extract_title_from_url_slug(link)
            slug_allowed, slug_reason = is_job_title_allowed(slug_title)
            if slug_allowed:
                allowed, reason = slug_allowed, f"{slug_reason} (from URL)"
                page_title = slug_title

        if not allowed:
            logger.warning(f"  ⛔ [SKIP] '{page_title}' | Reason: {reason}")
            failed += 1
            applied_list['failed'].append(link)
            continue

        # Click Direct "Apply" button
        if click_apply_button(driver):
            # If questionnaire drawer opens, answer it automatically
            handle_chatbot_drawer(driver, known_answers)
            applied += 1
            applied_list['passed'].append(link)
            previously_applied.add(clean_url)
            if save_confirmed_applications:
                save_confirmed_applications([link])
            logger.info(f"  ✓ Applied! Total: {applied}")
            human_delay(1.5, 3.0)
        else:
            failed += 1
            applied_list['failed'].append(link)
            logger.warning(f"  ✗ No Direct Apply button found (or external company redirect).")
            continue

        # Custom name inputs if required by standard form
        if FIRSTNAME:
            try:
                fn_el = driver.find_element(By.ID, 'CUSTOM-FIRSTNAME')
                fn_el.clear()
                fn_el.send_keys(FIRSTNAME)
            except NoSuchElementException:
                pass

        if LASTNAME:
            try:
                ln_el = driver.find_element(By.ID, 'CUSTOM-LASTNAME')
                ln_el.clear()
                ln_el.send_keys(LASTNAME)
            except NoSuchElementException:
                pass

        try:
            submit_btn = driver.find_element(By.XPATH, "//*[text()='Submit and Apply']")
            submit_btn.click()
            human_delay(1.5, 2.5)
        except NoSuchElementException:
            pass

        # Human delay between applications
        human_delay(3.5, 6.5, reason="inter-application delay")

    return applied, failed, applied_list


def save_results(applied_list):
    """Save applied and failed links to CSV."""
    csv_file = PROJECT_DIR / "naukriapplied.csv"
    try:
        row_count = max((len(values) for values in applied_list.values()), default=0)
        with csv_file.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['passed', 'failed'])
            writer.writeheader()
            for index in range(row_count):
                writer.writerow({key: values[index] if index < len(values) else ''
                                 for key, values in applied_list.items()})
        logger.info(f"Results saved to {csv_file}")
    except Exception as e:
        logger.warning(f"Could not save results to {csv_file}: {e}")


def main():
    """Main entry point for Edge Keyword Search bot."""
    logger.info("=" * 50)
    logger.info("Naukri Auto-Apply Bot (Edge Edition - 2026 Update)")
    logger.info("=" * 50)

    email, password = get_credentials()
    if not validate_config(email, password):
        return

    logger.info(f"Keywords: {KEYWORDS}")
    logger.info(f"Location: {LOCATION or 'Anywhere'}")
    logger.info(f"Max applications: {MAX_APPLICATIONS}")
    logger.info(f"Pages per keyword: {PAGES_PER_KEYWORD}")

    known_answers = load_answers()
    driver = None
    try:
        driver = create_edge_driver()
        login_naukri(driver, email, password)

        search_urls = build_search_urls()
        logger.info(f"Total search pages to open: {len(search_urls)}")

        job_links = collect_all_jobs_parallel(driver, search_urls, batch_size=4)
        if not job_links:
            logger.warning("No job links found. Check your keywords and location.")
            return

        applied, failed, applied_list = apply_to_jobs(driver, job_links, known_answers)
        save_results(applied_list)

        logger.info("=" * 50)
        logger.info("APPLICATION SUMMARY")
        logger.info(f"  Successfully applied: {applied}")
        logger.info(f"  Failed/Skipped:       {failed}")
        logger.info(f"  Total processed:      {applied + failed}")
        logger.info(f"  Results saved to:     naukriapplied.csv")
        logger.info("=" * 50)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        if driver:
            if KEEP_BROWSER_OPEN:
                logger.info("=" * 50)
                logger.info("🔍 KEEP_BROWSER_OPEN is enabled: Leaving browser open for inspection.")
                logger.info("Press Enter in terminal to close browser...")
                logger.info("=" * 50)
                try:
                    input()
                except (KeyboardInterrupt, EOFError):
                    pass
            try:
                driver.quit()
                logger.info("Browser closed.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
