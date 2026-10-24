"""
Naukri Profile Optimizer (GenAI Developer / Engineer / Architect)
=================================================================
Automates updating Naukri.com Resume Headline and Profile Summary
to optimize recruiter discovery and ATS match rates for GenAI roles.

Usage:
    python update_naukri_profile.py
"""

import os
import time
import random
import getpass
import logging
from bot_config import load_project_env
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ------------------------------------------------------------
# Logging Setup
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

load_project_env(__file__)

PROFILE_HEADLINE = (
    "Generative AI Solution Architect / GenAI Engineer | Azure AI Foundry, "
    "Azure OpenAI, AWS Bedrock, GCP Vertex AI | RAG, Agentic AI, LangChain, LLMOps"
)

PROFILE_SUMMARY = (
    "Generative AI Solution Architect & GenAI Engineer specializing in designing "
    "and deploying scalable, enterprise-grade GenAI and Agentic AI applications across "
    "Azure AI Foundry, AWS Bedrock, and GCP Vertex AI. Strong expertise in hybrid RAG architectures, "
    "vector databases, LLMOps, infrastructure-as-code (Terraform), Docker, and enterprise compliance/security."
)


def human_delay(min_s=2.0, max_s=4.0, reason=None):
    """Generate dynamic, human-like delays to avoid triggering bot detection."""
    delay = random.uniform(min_s, max_s)
    msg = f"Sleeping for {delay:.2f} seconds..."
    if reason:
        msg += f" ({reason})"
    logger.info(msg)
    time.sleep(delay)


def get_credentials():
    """
    Retrieve credentials securely:
    1. Check environment variables (NAUKRI_EMAIL, NAUKRI_PASSWORD)
    2. If missing, prompt user via interactive CLI: input() for email, getpass.getpass() for password.
    Credentials remain strictly in memory and are never persisted to disk or logged.
    """
    email = os.getenv('NAUKRI_EMAIL', '').strip()
    password = os.getenv('NAUKRI_PASSWORD', '').strip()

    if not email:
        print("\n[Security] NAUKRI_EMAIL not found in environment.")
        try:
            email = input("Enter your Naukri Email: ").strip()
        except (EOFError, KeyboardInterrupt):
            email = ""

    if not password:
        print("[Security] NAUKRI_PASSWORD not found in environment.")
        try:
            password = getpass.getpass("Enter your Naukri Password: ").strip()
        except (EOFError, KeyboardInterrupt):
            password = ""

    return email, password


def setup_driver():
    """Create and return a visible Edge WebDriver instance with anti-detection options."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    edge_driver_path = os.getenv("EDGE_DRIVER_PATH", "").strip()
    if edge_driver_path and os.path.isfile(edge_driver_path):
        service = Service(executable_path=edge_driver_path)
    else:
        # Selenium 4 built-in Selenium Manager automatically locates or downloads EdgeDriver
        service = Service()

    return webdriver.Edge(service=service, options=options)



def login(driver, email, password):
    """Log in to Naukri.com using in-memory credentials and human-like typing delays."""
    logger.info("[*] Navigating to Naukri Login...")
    driver.get("https://www.naukri.com/nlogin/login")
    wait = WebDriverWait(driver, 20)

    # Fill username
    username_elem = wait.until(
        EC.presence_of_element_located((By.XPATH, "//input[@id='usernameField'] | //input[@id='emailTxt']"))
    )
    username_elem.clear()
    for ch in email:
        username_elem.send_keys(ch)
        time.sleep(random.uniform(0.04, 0.09))

    human_delay(0.5, 1.2, reason="typing password pause")

    # Fill password
    pwd_elem = driver.find_element(By.XPATH, "//input[@id='passwordField'] | //input[@id='pwd1']")
    pwd_elem.clear()
    for ch in password:
        pwd_elem.send_keys(ch)
        time.sleep(random.uniform(0.04, 0.09))

    human_delay(0.5, 1.0, reason="pre-submit login pause")

    login_btn = driver.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Login')]")
    login_btn.click()
    logger.info("[*] Login clicked. Waiting for dashboard...")
    human_delay(4.0, 6.0, reason="waiting for dashboard load")


def update_resume_headline(driver):
    """Navigate to profile page and update the Resume Headline."""
    wait = WebDriverWait(driver, 15)
    logger.info("[*] Navigating to Profile Page...")
    driver.get("https://www.naukri.com/mnjuser/profile")
    human_delay(3.0, 5.0, reason="profile page rendering")

    logger.info("[*] Updating Resume Headline...")
    # Click edit button on resume headline card
    edit_headline_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'resumeHeadline')]//span[contains(@class,'edit')]"))
    )
    edit_headline_btn.click()
    human_delay(1.5, 3.0, reason="headline edit modal delay")

    headline_textarea = wait.until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'resumeHeadline')]//textarea"))
    )
    headline_textarea.click()
    headline_textarea.send_keys(Keys.CONTROL + "a")
    headline_textarea.send_keys(Keys.BACKSPACE)
    human_delay(0.5, 1.0, reason="clearing text area")

    for ch in PROFILE_HEADLINE:
        headline_textarea.send_keys(ch)
        time.sleep(0.01)

    human_delay(1.0, 2.0, reason="pre-save headline pause")
    save_btn = driver.find_element(By.XPATH, "//div[contains(@class,'resumeHeadline')]//button[contains(text(),'Save')]")
    save_btn.click()
    logger.info("[✔] Resume Headline updated successfully.")
    human_delay(2.0, 3.5, reason="post-save headline pause")


def update_profile_summary(driver):
    """Update the Profile Summary section if present on profile page."""
    wait = WebDriverWait(driver, 15)
    logger.info("[*] Updating Profile Summary...")

    try:
        edit_summary_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'profileSummary')]//span[contains(@class,'edit')]"))
        )
        edit_summary_btn.click()
        human_delay(1.5, 3.0, reason="profile summary edit modal delay")

        summary_textarea = wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'profileSummary')]//textarea"))
        )
        summary_textarea.click()
        summary_textarea.send_keys(Keys.CONTROL + "a")
        summary_textarea.send_keys(Keys.BACKSPACE)
        human_delay(0.5, 1.0, reason="clearing summary text area")

        summary_textarea.send_keys(PROFILE_SUMMARY)
        human_delay(1.0, 2.0, reason="pre-save summary pause")

        save_btn = driver.find_element(By.XPATH, "//div[contains(@class,'profileSummary')]//button[contains(text(),'Save')]")
        save_btn.click()
        logger.info("[✔] Profile Summary updated successfully.")
        human_delay(2.0, 3.5, reason="post-save summary pause")
    except Exception as e:
        logger.warning(f"[!] Profile Summary section not updated or skipped: {e}")


def main():
    """Main execution entry point."""
    logger.info("=" * 50)
    logger.info("Naukri Profile Optimizer (GenAI Roles)")
    logger.info("=" * 50)

    email, password = get_credentials()
    if not email or not password:
        logger.error("Naukri email and password are required.")
        return

    driver = setup_driver()
    try:
        login(driver, email, password)
        update_resume_headline(driver)
        update_profile_summary(driver)
        logger.info("[✔] All profile modifications finished successfully.")
    except Exception as err:
        logger.exception(f"[!] Error updating profile: {err}")
    finally:
        human_delay(3.0, 5.0, reason="final closing pause")
        if driver:
            try:
                driver.quit()
                logger.info("Browser closed.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
