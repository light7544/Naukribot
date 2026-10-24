"""
Naukri Auto-Apply Bot - Recommended Jobs Edition (Fixed 2026)
"""

import os
import re
import sys
import time
import csv
import difflib
import logging
import random
import getpass
from datetime import datetime
from bot_config import (
    load_project_env,
    project_dir,
    is_keep_browser_open,
    is_job_title_allowed,
    smart_infer_text_answer,
    smart_infer_radio_option,
)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    WebDriverException,
)

PROJECT_DIR = project_dir(__file__)
load_project_env(__file__)

raw_max = os.getenv('MAX_APPLICATIONS', '25')
try:
    parsed_max = int(raw_max)
except ValueError:
    parsed_max = 25

MAX_APPLICATIONS = min(30, max(1, parsed_max))
MAX_SELECT = 5
ANSWERS_CSV = str(PROJECT_DIR / "application_answers.csv")
RESULTS_CSV = PROJECT_DIR / "naukriapplied.csv"
KEEP_BROWSER_OPEN = is_keep_browser_open()

TABS = [
    {"num": 1, "id": "preference",    "label": "Preferences"},
    {"num": 2, "id": "profile",       "label": "Profile"},
    {"num": 3, "id": "top_candidate", "label": "Top Candidate"},
    {"num": 4, "id": "apply",         "label": "Applies"},
    {"num": 5, "id": "similar_jobs",  "label": "You might like"},
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def human_delay(min_sec=1.2, max_sec=2.8, reason=None):
    delay = random.uniform(min_sec, max_sec)
    msg = f"Sleeping for {delay:.2f} seconds..."
    if reason:
        msg += f" ({reason})"
    logger.info(msg)
    time.sleep(delay)


def get_credentials():
    email = os.getenv('NAUKRI_EMAIL', '').strip()
    password = os.getenv('NAUKRI_PASSWORD', '').strip()
    if not email:
        email = input("Enter your Naukri Email: ").strip()
    if not password:
        password = getpass.getpass("Enter your Naukri Password: ").strip()
    return email, password


def load_answers():
    answers = {}
    if not os.path.exists(ANSWERS_CSV):
        return answers
    try:
        with open(ANSWERS_CSV, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return answers
            lines = content.split('\n')
            header_idx = next((i for i, l in enumerate(lines) if l.startswith('question_text,')), -1)
            if header_idx == -1:
                return answers
            reader = csv.DictReader(lines[header_idx:])
            for row in reader:
                q = (row.get('question_text') or '').strip()
                a = (row.get('answer') or '').strip()
                if q and a:
                    answers[q] = a
        logger.info(f"Loaded {len(answers)} known answers from {ANSWERS_CSV}")
    except Exception as e:
        logger.warning(f"Could not load {ANSWERS_CSV}: {e}")
    return answers


def _strip_question_boilerplate(q: str) -> str:
    """
    Removes common recruiter boilerplate so 'How many years of experience do you have in Deep Learning?'
    becomes 'deep learning', preventing false fuzzy matches with 'data engineering'!
    """
    s = q.strip().lower()
    s = re.sub(r"[^\w\s]", " ", s)
    boilerplates = (
        "how many years of experience do you have in",
        "how many years of experience you have in",
        "how many years of work experience do you have in",
        "what is your relevant years of experience using",
        "what is your experience in",
        "do you have experience in",
        "are you currently residing in",
        "are you willing to relocate to",
        "are you willing to relocate",
    )
    for bp in boilerplates:
        if s.startswith(bp):
            s = s[len(bp):].strip()
            break
    return " ".join(s.split())


def fuzzy_lookup(question_text, known_answers, threshold=0.92):
    """
    Lookup a stored answer ONLY if the core subject/skill of the question matches,
    and NEVER return 'no' or 'Less than 1' for an experience/years question.
    """
    if not question_text or not known_answers:
        return None

    q_clean = question_text.strip()
    q_lower = q_clean.lower()
    is_exp_question = any(k in q_lower for k in ("how many years", "years of experience", "relevant years", "experience do you have"))

    # 1. Exact match check
    if q_clean in known_answers:
        ans = known_answers[q_clean]
        if is_exp_question and ans.strip().lower() in ("no", "n", "less than 1", "0", "none"):
            return None  # Ignore bad historical answers for experience questions
        return ans

    # 2. Compare stripped core subject (so 'Deep Learning' never matches 'Data Engineering')
    core_q = _strip_question_boilerplate(q_clean)
    for stored_q, stored_ans in known_answers.items():
        if is_exp_question and stored_ans.strip().lower() in ("no", "n", "less than 1", "0", "none"):
            continue
        core_stored = _strip_question_boilerplate(stored_q)
        if core_q and core_q == core_stored:
            return stored_ans
        # Only allow high-threshold fuzzy match if the stripped core strings are >= 92% similar
        if core_q and core_stored and difflib.SequenceMatcher(None, core_q, core_stored).ratio() >= threshold:
            logger.info(f"   ~ Core match: '{stored_q}' → '{stored_ans}'")
            return stored_ans

    return None


def save_answer(question_text, answer, field_type="text"):
    if not question_text or not answer:
        return
    needs_header = not os.path.exists(ANSWERS_CSV) or os.path.getsize(ANSWERS_CSV) == 0
    try:
        with open(ANSWERS_CSV, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            if needs_header:
                writer.writerow(['question_text', 'answer', 'field_type', 'created_at'])
            writer.writerow([question_text, answer, field_type, datetime.now().isoformat()])
        logger.info(f"💾 Saved: '{question_text}' → '{answer}'")
    except Exception as e:
        logger.warning(f"Could not save to {ANSWERS_CSV}: {e}")


def load_previously_applied_urls() -> set[str]:
    existing = set()
    if RESULTS_CSV.exists() and RESULTS_CSV.stat().st_size:
        try:
            with RESULTS_CSV.open('r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    u = (row.get('passed') or '').strip()
                    if u:
                        existing.add(u.split('?')[0])
        except Exception:
            pass
    return existing


def save_confirmed_applications(job_urls):
    if not job_urls:
        return
    try:
        existing = load_previously_applied_urls()
        new_urls = [url for url in dict.fromkeys(job_urls) if url and url.split('?')[0] not in existing]
        if not new_urls:
            return
        needs_header = not RESULTS_CSV.exists() or RESULTS_CSV.stat().st_size == 0
        with RESULTS_CSV.open('a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['passed', 'failed'])
            if needs_header:
                writer.writeheader()
            for url in new_urls:
                writer.writerow({'passed': url, 'failed': ''})
        logger.info("Saved %d confirmed application URLs to %s", len(new_urls), RESULTS_CSV)
    except OSError as exc:
        logger.warning("Could not write application history: %s", exc)


def create_edge_driver():
    options = webdriver.EdgeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])

    edge_driver_path = os.getenv("EDGE_DRIVER_PATH", "").strip()
    service = EdgeService(executable_path=edge_driver_path) if (edge_driver_path and os.path.isfile(edge_driver_path)) else EdgeService()
    return webdriver.Edge(service=service, options=options)


def login_naukri(driver, email, password):
    logger.info("Logging in to Naukri.com...")
    driver.get('https://login.naukri.com/')
    wait = WebDriverWait(driver, 25)
    username = wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, "#usernameField, #emailTxt, input[type='email'], input[placeholder*='Email']")
    ))
    password_field = wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, "#passwordField, #pwd1, input[type='password']")
    ))
    username.clear()
    username.send_keys(email)
    password_field.clear()
    password_field.send_keys(password)
    try:
        submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button.blue-btn")
        submit.click()
    except NoSuchElementException:
        password_field.send_keys(Keys.ENTER)

    logger.info("Login submitted. Complete any OTP/CAPTCHA in Edge if Naukri asks.")

    def session_ready(d):
        try:
            url = (d.current_url or "").lower()
            if "login.naukri.com" not in url and "/nlogin" not in url:
                return True
            login_fields = d.find_elements(By.CSS_SELECTOR, "#usernameField, #passwordField, input[type='password']")
            return not any(field.is_displayed() for field in login_fields)
        except StaleElementReferenceException:
            return False

    WebDriverWait(driver, 120, poll_frequency=1).until(session_ready)
    logger.info("Login completed.")


JOB_CARD_SELECTORS = (
    "article.jobTuple",
    "div.srp-jobtuple-wrapper",
    "div.cust-job-tuple",
    "div[class*='jobTuple']",
    "[data-job-id]",
)


def find_job_cards(driver):
    for selector in JOB_CARD_SELECTORS:
        cards = [c for c in driver.find_elements(By.CSS_SELECTOR, selector) if c.is_displayed()]
        if cards:
            return cards
    return []


def find_multi_apply_button(driver):
    selectors = (
        "button.multi-apply-button",
        "button[class*='multi-apply']",
        "button[class*='multiApply']",
        "button[class*='apply-button']",
        ".multi-apply-button",
        "[class*='multi-apply']",
        "[class*='multiApply']",
    )
    for selector in selectors:
        for button in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                text = " ".join((button.text or "").lower().split())
                if button.is_displayed() and button.is_enabled() and "apply" in text and "company site" not in text:
                    return button
            except StaleElementReferenceException:
                continue

    try:
        xpath_buttons = driver.find_elements(By.XPATH, "//button[contains(translate(., 'APPLY', 'apply'), 'apply')]")
        for button in xpath_buttons:
            text = " ".join((button.text or "").lower().split())
            if button.is_displayed() and button.is_enabled() and "company site" not in text:
                return button
    except Exception:
        pass
    return None


# CRITICAL: Only match actual left-hand bulk-selection checkboxes (.tuple-check-box).
# NEVER match generic 'i.naukicon' or '[class*=check]' inside the card body, which causes
# Selenium to click the job card itself and navigate away on 'Apply on company site' cards!
CHECKBOX_CANDIDATE_SELECTORS = (
    ".tuple-check-box i.naukicon-ot-checkbox",
    ".tuple-check-box i.naukicon",
    ".tuple-check-box i",
    ".tuple-check-box label",
    ".tuple-check-box",
    "div[class*='tuple-check'] i",
    "div[class*='tuple-check']",
)

def find_card_checkbox(card):
    """Return the left-hand multi-apply checkbox ONLY if this card supports direct multi-apply."""
    for selector in CHECKBOX_CANDIDATE_SELECTORS:
        try:
            for el in card.find_elements(By.CSS_SELECTOR, selector):
                if el.is_displayed():
                    return el
        except StaleElementReferenceException:
            raise
        except Exception:
            continue
    return None


def is_card_checkbox_checked(card, checkbox_el=None):
    try:
        if checkbox_el:
            if checkbox_el.is_selected():
                return True
            if (checkbox_el.get_attribute("aria-checked") or "").lower() == "true":
                return True
            cls = (checkbox_el.get_attribute("class") or "").lower()
            if any(t in cls for t in ("checked", "selected", "ot-checked")):
                return True
        checked_elements = card.find_elements(
            By.CSS_SELECTOR,
            ".tuple-check-box i.naukicon-ot-Checked, "
            ".tuple-check-box i.naukicon-ot-checkbox-selected, "
            "[class*='tuple-check'] [class*='Checked'], "
            "[class*='tuple-check'] [class*='checked'], "
            "i.naukicon-ot-Checked, "
            "input[type='checkbox']:checked, "
            "[aria-checked='true']"
        )
        return bool(checked_elements)
    except StaleElementReferenceException:
        raise
    except Exception:
        return False


def extract_card_title(card):
    for selector in ("a.title", ".title", "[class*='title']", "h2", "a[href*='job-listings']"):
        try:
            el = card.find_element(By.CSS_SELECTOR, selector)
            for attr in ("title", "textContent", "innerText"):
                val = (el.get_attribute(attr) or "").strip()
                if val:
                    return " ".join(val.split())
            if el.text and el.text.strip():
                return " ".join(el.text.strip().split())
        except Exception:
            continue
    return "Unknown Title"


def extract_card_url(card) -> str:
    for selector in ("a.title", "a[href*='job-listings']", "a[href*='naukri.com']"):
        try:
            href = (card.find_element(By.CSS_SELECTOR, selector).get_attribute("href") or "").strip()
            if href:
                return href
        except Exception:
            continue
    return ""


def select_jobs_and_apply(driver, seen_keys: set[str], max_to_select=None):
    if max_to_select is None:
        max_to_select = MAX_SELECT
    if max_to_select <= 0:
        return 0, []

    logger.info("=" * 50)
    logger.info(f"STEP 1: Selecting up to {max_to_select} jobs...")
    logger.info("=" * 50)

    try:
        WebDriverWait(driver, 15).until(lambda d: find_job_cards(d))
    except TimeoutException:
        logger.warning("No job cards appeared after 15 seconds.")
        return 0, []

    # Scroll down to load fresh cards if needed
    for _ in range(2):
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(0.4)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.4)

    job_cards = find_job_cards(driver)
    logger.info(f"Found {len(job_cards)} job cards on page.")
    if not job_cards:
        return 0, []

    selected = 0
    selected_urls = []

    for card_idx, card in enumerate(job_cards, start=1):
        if selected >= max_to_select:
            break
        try:
            title = extract_card_title(card)

            # Guard: If browser accidentally left the recommendedjobs URL, navigate back immediately
            if "recommendedjobs" not in (driver.current_url or "").lower():
                logger.warning("Browser navigated away from recommendedjobs! Returning...")
                driver.back()
                time.sleep(2.0)
                break

            job_url = extract_card_url(card)
            card_key = (job_url.split('?')[0] if job_url else f"{title}_{card_idx}")

            if card_key in seen_keys:
                continue

            allowed, reason = is_job_title_allowed(title)
            if not allowed:
                seen_keys.add(card_key)
                logger.info(f"  [{card_idx}/{len(job_cards)}] ⛔ [SKIP] '{title}' | {reason}")
                continue

            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", card)
            time.sleep(0.25)

            checkbox = find_card_checkbox(card)
            if checkbox is None:
                seen_keys.add(card_key)
                logger.info(f"  [{card_idx}/{len(job_cards)}] ⚠️ [NO CHECKBOX / EXTERNAL] '{title}'")
                continue

            if is_card_checkbox_checked(card, checkbox):
                seen_keys.add(card_key)
                continue

            clicked = False
            try:
                if checkbox.is_displayed():
                    checkbox.click()
                    clicked = True
            except Exception:
                pass
            if not clicked:
                driver.execute_script("arguments[0].click();", checkbox)

            time.sleep(0.3)
            if not is_card_checkbox_checked(card, checkbox):
                for alt_sel in (".tuple-check-box i", ".tuple-check-box label", ".tuple-check-box"):
                    for alt_el in card.find_elements(By.CSS_SELECTOR, alt_sel):
                        try:
                            driver.execute_script("arguments[0].click();", alt_el)
                            if is_card_checkbox_checked(card, alt_el):
                                break
                        except Exception:
                            pass

            seen_keys.add(card_key)
            selected += 1
            if job_url:
                selected_urls.append(job_url)
            logger.info(f"  [{selected}/{max_to_select}] 📌 Selected: '{title}' ({reason})")
            human_delay(0.5, 1.0, reason="card selection pause")

        except StaleElementReferenceException:
            continue
        except Exception as e:
            logger.warning(f"  Select error on card {card_idx}: {e}")

    if selected == 0:
        return 0, []

    try:
        human_delay(1.0, 2.0, reason="pre-apply pause")
        apply_btn = WebDriverWait(driver, 8).until(find_multi_apply_button)
        if not apply_btn:
            logger.error("Could not find multi-apply button.")
            return 0, []
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", apply_btn)
        try:
            apply_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", apply_btn)
        logger.info(f"🚀 Clicked 'Apply' for {selected} job(s)!")
        human_delay(2.5, 3.8, reason="waiting for response / chatbot drawer")
        return selected, selected_urls
    except Exception as e:
        logger.error(f"Could not click bulk Apply button: {e}")
        return 0, []


# ============================================================
# Step 2: Handle Direct Apply OR Chatbot Drawer Questions
# ============================================================

def is_direct_apply_confirmed(driver) -> bool:
    """Detect if Naukri applied directly without needing a chatbot questionnaire."""
    try:
        url = (driver.current_url or "").lower()
        if any(tok in url for tok in ("saveapply", "apply-confirmation", "myapply")):
            return True
        page_text = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
        success_phrases = (
            "applied successfully",
            "you have successfully applied",
            "application sent",
            "successfully applied to",
        )
        if any(phrase in page_text for phrase in success_phrases):
            return True
    except Exception:
        pass
    return False


def find_visible_chatbot_drawer(driver):
    try:
        for selector in (
            "[id*='ChatbotContainer']",
            ".chatbot_Drawer",
            "[class*='chatbot_Drawer']",
            "[class*='chatbot-drawer']",
            "div[class*='drawer-wrapper']",
        ):
            for container in driver.find_elements(By.CSS_SELECTOR, selector):
                if container.is_displayed():
                    return container
    except Exception:
        return None
    return None


def is_drawer_open(driver):
    return find_visible_chatbot_drawer(driver) is not None


def handle_chatbot_drawer(driver, known_answers):
    logger.info("=" * 50)
    logger.info("STEP 2: Checking for Direct Apply or Chatbot Questionnaire...")
    logger.info("=" * 50)

    # Wait up to 8 seconds for either a chatbot drawer OR direct apply confirmation
    drawer_appeared = False
    for _ in range(16):
        if find_visible_chatbot_drawer(driver) is not None:
            drawer_appeared = True
            break
        if is_direct_apply_confirmed(driver):
            logger.info("✅ Direct 1-Click Apply succeeded (no questionnaire required)!")
            return True
        time.sleep(0.5)

    if not drawer_appeared:
        # If no drawer appeared and no error modal blocked us, Naukri processed the 1-click apply directly
        logger.info("✅ No chatbot questionnaire popped up — treated as Direct Apply completed.")
        return True

    logger.info("💬 Chatbot drawer appeared. Answering questions...")
    human_delay(1.5, 2.5)
    last_bot_msg_count = 0

    for iteration in range(60):
        human_delay(1.2, 2.0)
        try:
            if not is_drawer_open(driver) or is_direct_apply_confirmed(driver):
                logger.info("✅ Chatbot drawer completed and closed!")
                return True

            # 1. Single-select Radio buttons
            if handle_radio_buttons(driver, known_answers):
                continue

            # 2. Multi-select Checkboxes inside Chatbot
            if handle_checkbox_questions(driver, known_answers):
                continue

            # 3. Chip / Option buttons inside Chatbot
            if handle_chip_options(driver, known_answers):
                continue

            # 4. Free-text / Contenteditable / Input field
            if handle_contenteditable(driver, known_answers):
                continue

            # 5. Standalone Save / Submit button ready
            save_btn = find_save_button(driver)
            if save_btn and click_save_button(driver, save_btn):
                logger.info("Clicked Save/Next button in drawer...")
                human_delay(1.5, 2.5)
                continue

            # 6. Log new bot prompts if waiting
            bot_msgs = driver.find_elements(By.CSS_SELECTOR, ".chatbot_ListItem.botItem .msg, .chatbot_ListItem .botMsg .msg, [class*='botItem'] [class*='msg']")
            if len(bot_msgs) > last_bot_msg_count:
                for msg in bot_msgs[last_bot_msg_count:]:
                    text = msg.text.strip()
                    if text:
                        logger.info(f"🤖 Bot asks: '{text}'")
                last_bot_msg_count = len(bot_msgs)

        except StaleElementReferenceException:
            continue
        except Exception as e:
            logger.warning(f"  Chatbot loop warning: {e}")
            continue

    logger.warning("Timed out waiting for chatbot drawer. Closing drawer and moving to next batch...")
    try:
        close_btns = driver.find_elements(By.CSS_SELECTOR, ".chatbot_Drawer .crossIcon, [class*='closeBtn'], [class*='crossIcon']")
        for cb in close_btns:
            if cb.is_displayed():
                driver.execute_script("arguments[0].click();", cb)
                break
    except Exception:
        pass
    return True


def get_latest_bot_question(driver):
    try:
        drawer = find_visible_chatbot_drawer(driver)
        if drawer is None:
            return None
        msgs = drawer.find_elements(By.CSS_SELECTOR, ".chatbot_ListItem.botItem .msg, .chatbot_ListItem .botMsg .msg, [class*='botMsg']")
        for m in reversed(msgs):
            t = m.text.strip()
            if t:
                return t
    except Exception:
        pass
    return None


def get_latest_user_answer(driver):
    try:
        drawer = find_visible_chatbot_drawer(driver)
        if drawer is None:
            return None
        msgs = drawer.find_elements(By.CSS_SELECTOR, ".chatbot_ListItem.userItem .msg, .userMsg .msg")
        if msgs:
            return msgs[-1].text.strip()
    except Exception:
        pass
    return None


def get_user_message_count(driver):
    try:
        drawer = find_visible_chatbot_drawer(driver)
        if drawer is None:
            return 0
        return len(drawer.find_elements(By.CSS_SELECTOR, ".chatbot_ListItem.userItem .msg, .userMsg .msg"))
    except Exception:
        return 0


def _click_save_after_selection(driver):
    time.sleep(0.4)
    save_btn = find_save_button(driver)
    if save_btn and click_save_button(driver, save_btn):
        logger.info("   Clicked Save after selection.")
        human_delay(1.2, 2.2)


def handle_radio_buttons(driver, known_answers):
    """Automatically selects the saved OR smart-inferred radio option and clicks Save."""
    container = None
    for selector in (
        ".singleselect-radiobutton-container",
        ".ssrc__container",
        "[role='radiogroup']",
        "[class*='radiobutton-container']",
        "[class*='radio-container']",
    ):
        try:
            container = next((el for el in driver.find_elements(By.CSS_SELECTOR, selector) if el.is_displayed()), None)
        except StaleElementReferenceException:
            container = None
        if container:
            break
    if container is None:
        return False

    question_text = get_latest_bot_question(driver) or "RadioQuestion"
    radios = container.find_elements(By.CSS_SELECTOR, ".ssrc__radio, input[type='radio'], [role='radio']")
    labels = container.find_elements(By.CSS_SELECTOR, ".ssrc__label, label")

    option_texts = []
    for i in range(max(len(labels), len(radios))):
        txt = ""
        if i < len(labels):
            txt = (labels[i].text or "").strip()
        if not txt and i < len(radios):
            txt = (radios[i].get_attribute("value") or "").strip()
        option_texts.append(txt)

    known = fuzzy_lookup(question_text, known_answers)
    target_idx = None

    if known:
        for idx, opt in enumerate(option_texts):
            if opt.casefold() == known.casefold():
                target_idx = idx
                break

    if target_idx is None:
        # Use Smart Auto-Responder so we NEVER wait for manual user click
        target_idx = smart_infer_radio_option(question_text, option_texts)
        inferred_val = option_texts[target_idx] if target_idx < len(option_texts) else "Yes"
        logger.info("🤖 Smart Auto-Selected radio option '%s' for: '%s'", inferred_val, question_text)
        save_answer(question_text, inferred_val, "radio")
        known_answers[question_text] = inferred_val
    else:
        logger.info("✓ Using saved radio answer '%s' for: '%s'", option_texts[target_idx], question_text)

    # Click both the label and input/radio if needed
    clicked = False
    for candidate_list in (labels, radios):
        if target_idx < len(candidate_list):
            target_el = candidate_list[target_idx]
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target_el)
                target_el.click()
                clicked = True
                break
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", target_el)
                    clicked = True
                    break
                except Exception:
                    continue

    time.sleep(0.4)
    _click_save_after_selection(driver)
    return clicked


def handle_checkbox_questions(driver, known_answers):
    """Automatically selects the first valid checkbox option and clicks Save."""
    container = None
    for selector in (".multiselectcheckboxes-container", "[class*='multiselectcheckbox']", "[class*='checkbox-container']"):
        try:
            container = next((el for el in driver.find_elements(By.CSS_SELECTOR, selector) if el.is_displayed()), None)
        except StaleElementReferenceException:
            container = None
        if container:
            break
    if container is None:
        return False

    question_text = get_latest_bot_question(driver) or "CheckboxQuestion"
    labels = container.find_elements(By.CSS_SELECTOR, "label, .msc__label")
    if not labels:
        return False

    known = fuzzy_lookup(question_text, known_answers)
    clicked_any = False

    if known:
        wanted = {part.strip().casefold() for part in known.split(",") if part.strip()}
        for lbl in labels:
            if (lbl.text or "").strip().casefold() in wanted:
                try:
                    lbl.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", lbl)
                clicked_any = True

    if not clicked_any:
        # Auto-select first option
        first_lbl = labels[0]
        chosen_txt = (first_lbl.text or "Selected").strip()
        try:
            first_lbl.click()
        except Exception:
            driver.execute_script("arguments[0].click();", first_lbl)
        save_answer(question_text, chosen_txt, "checkbox")
        known_answers[question_text] = chosen_txt
        logger.info("🤖 Smart Auto-Selected checkbox '%s' for: '%s'", chosen_txt, question_text)

    time.sleep(0.4)
    _click_save_after_selection(driver)
    return True


def handle_chip_options(driver, known_answers):
    """Handle chip/pill style option buttons inside the Naukri chatbot drawer without blocking."""
    container = None
    for selector in (".chips-container", "[class*='chips-container']", "[class*='chip-container']", ".single-select-chip"):
        try:
            container = next((el for el in driver.find_elements(By.CSS_SELECTOR, selector) if el.is_displayed()), None)
        except StaleElementReferenceException:
            container = None
        if container:
            break
    if container is None:
        return False

    question_text = get_latest_bot_question(driver) or "ChipQuestion"
    chips = container.find_elements(By.CSS_SELECTOR, ".chip, [class*='chip'], button")
    if not chips:
        return False

    known = fuzzy_lookup(question_text, known_answers)
    if known:
        for chip in chips:
            txt = (chip.text or "").strip()
            if txt.casefold() == known.casefold():
                try:
                    chip.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", chip)
                logger.info("   ✓ Auto-selected chip answer '%s' for: %s", known, question_text)
                _click_save_after_selection(driver)
                return True

    # Smart infer chip option
    chip_texts = [(c.text or "").strip() for c in chips]
    best_idx = smart_infer_radio_option(question_text, chip_texts)
    target_chip = chips[best_idx] if best_idx < len(chips) else chips[0]
    chosen_txt = (target_chip.text or "").strip()
    try:
        target_chip.click()
    except Exception:
        driver.execute_script("arguments[0].click();", target_chip)
    logger.info("🤖 Smart Auto-Selected chip '%s' for: '%s'", chosen_txt, question_text)
    save_answer(question_text, chosen_txt, "chip")
    known_answers[question_text] = chosen_txt
    _click_save_after_selection(driver)
    return True


def _react_safe_fill_text(driver, element, text: str):
    """Fill a React contenteditable div or input/textarea and trigger React state listeners."""
    element.click()
    time.sleep(0.15)
    tag = (element.tag_name or "").lower()
    is_ce = (element.get_attribute("contenteditable") or "").lower() == "true"

    if is_ce or tag == "div":
        driver.execute_script(
            """
            const el = arguments[0];
            const val = arguments[1];
            el.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, val);
            if ((el.innerText || '').trim() !== val.trim()) {
                el.innerText = val;
            }
            el.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, data: val }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
            """,
            element,
            text,
        )
    else:
        driver.execute_script(
            """
            const el = arguments[0];
            const val = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
                        || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
            if (setter) {
                setter.call(el, val);
            } else {
                el.value = val;
            }
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            element,
            text,
        )


def handle_contenteditable(driver, known_answers):
    """
    Automatically fills ANY free-text chatbot question using either CSV memory
    or `smart_infer_text_answer()`, then clicks Save/Enter immediately without human intervention.
    """
    text_area = find_chat_text_area(driver)
    if not text_area:
        return False

    question_text = get_latest_bot_question(driver) or "ChatbotTextQuestion"
    answer_to_use = fuzzy_lookup(question_text, known_answers)

    if not answer_to_use:
        answer_to_use = smart_infer_text_answer(question_text)
        logger.info("🤖 Smart Auto-Answering '%s' → '%s'", question_text, answer_to_use)
        save_answer(question_text, answer_to_use, "text")
        known_answers[question_text] = answer_to_use
    else:
        logger.info("✓ Using saved text answer '%s' → '%s'", question_text, answer_to_use)

    try:
        fresh_text_area = find_chat_text_area(driver)
        if not fresh_text_area:
            return False

        # Fill via both native send_keys and React synthetic events
        fresh_text_area.click()
        time.sleep(0.15)
        try:
            fresh_text_area.send_keys(Keys.CONTROL, "a")
            fresh_text_area.send_keys(Keys.BACKSPACE)
            fresh_text_area.send_keys(str(answer_to_use))
        except Exception:
            _react_safe_fill_text(driver, fresh_text_area, str(answer_to_use))

        time.sleep(0.3)
        # Ensure text actually populated; if empty, force via JS _react_safe_fill_text
        curr_val = (fresh_text_area.text or fresh_text_area.get_attribute("value") or "").strip()
        if not curr_val:
            _react_safe_fill_text(driver, fresh_text_area, str(answer_to_use))
            time.sleep(0.3)

        # Click Save button or press Enter
        save_btn = find_save_button(driver)
        if save_btn and click_save_button(driver, save_btn):
            logger.info("   ✓ Clicked Save for answer '%s'", answer_to_use)
        else:
            fresh_text_area.send_keys(Keys.RETURN)
            logger.info("   ✓ Pressed Enter for answer '%s'", answer_to_use)

        human_delay(1.0, 1.8, reason="post-answer transition")
        return True
    except Exception as e:
        logger.warning(f"   Error auto-filling text for '{question_text}': {e}")
        return False


def click_save_button(driver, save_btn):
    try:
        cls = (save_btn.get_attribute("class") or "").lower()
        if "disabled" in cls:
            return False
        parent = save_btn.find_elements(By.XPATH, "./ancestor::*[contains(@class,'send')]")
        if parent and "disabled" in (parent[0].get_attribute("class") or "").lower():
            return False
    except Exception:
        pass
    try:
        save_btn.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", save_btn)
            return True
        except Exception:
            return False


def find_chat_text_area(driver):
    drawer = find_visible_chatbot_drawer(driver)
    if drawer is None:
        return None
    selectors = [
        ".chatbot_SendMessageContainer .textArea[contenteditable='true']",
        ".chatbot_InputContainer .textArea[contenteditable='true']",
        "div.textArea[contenteditable='true']",
        "div[contenteditable='true']",
        "input[placeholder*='Type']",
        "textarea[placeholder*='Type']",
        "input[placeholder*='Enter']",
        ".chatbot_Drawer input[type='text']",
        ".chatbot_Drawer input[type='number']",
        ".chatbot_Drawer textarea",
        "[id*='InputBox']",
    ]
    for sel in selectors:
        try:
            for el in drawer.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return el
        except Exception:
            continue
    return None


def find_save_button(driver):
    drawer = find_visible_chatbot_drawer(driver)
    if drawer is None:
        return None
    selectors = [
        ".sendMsg",
        ".sendMsgbtn_container .sendMsg",
        "[class*='sendMsg']",
        "button[type='submit']",
    ]
    for sel in selectors:
        try:
            for el in drawer.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    return el
        except Exception:
            continue
    return None


def select_tabs():
    env_tabs = os.getenv('RECOMMENDED_TABS', '').strip()
    if env_tabs:
        if env_tabs.lower() in ('all', '1,2,3,4,5'):
            return list(TABS)
        selected = [TABS[int(p.strip()) - 1] for p in env_tabs.split(',') if p.strip().isdigit() and 1 <= int(p.strip()) <= len(TABS)]
        if selected:
            return selected

    if not sys.stdin.isatty():
        return [TABS[0]]

    print("\n" + "=" * 50)
    print("Select job tabs to apply to:")
    for t in TABS:
        print(f"  {t['num']}. {t['label']}")
    print("=" * 50)
    try:
        raw = input("Enter numbers (e.g. 1,2,3,5) or press Enter for ALL tabs: ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""

    if not raw:
        return list(TABS)

    selected = [TABS[int(p.strip()) - 1] for p in raw.split(',') if p.strip().isdigit() and 1 <= int(p.strip()) <= len(TABS)]
    return selected or list(TABS)


def navigate_to_tab(driver, tab_id):
    driver.get('https://www.naukri.com/mnjuser/recommendedjobs')
    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, ".tab-list, [role='tablist'], [role='tab'], article.jobTuple, div.srp-jobtuple-wrapper")
        )
        human_delay(1.5, 2.5)
        tab_items = driver.find_elements(
            By.CSS_SELECTOR,
            f"#{tab_id}.tab-list-item, #{tab_id}, #{tab_id} .tab-list-item, [data-tab='{tab_id}']",
        )
        tab_el = next((el for el in tab_items if el.is_displayed()), None)
        if tab_el is None:
            label = next((item['label'] for item in TABS if item['id'] == tab_id), tab_id)
            xpath = f"//*[self::button or self::a or self::div or self::span or @role='tab'][contains(normalize-space(), '{label}')]"
            tab_items = driver.find_elements(By.XPATH, xpath)
            tab_el = next((el for el in tab_items if el.is_displayed() and el.rect.get('y', 999) < 400), None)
        if tab_el is None:
            logger.warning("Tab '%s' element not found; using default active view.", tab_id)
            return True
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab_el)
        try:
            tab_el.click()
        except Exception:
            driver.execute_script("arguments[0].click();", tab_el)
        logger.info(f"Switched to tab: {tab_id}")
        human_delay(2.0, 3.2)
        return True
    except Exception as e:
        logger.warning("Could not activate tab '%s': %s", tab_id, e)
        return False


def main():
    logger.info("=" * 50)
    logger.info(f"Naukri Recommended Jobs Bot (Daily Max Cap: {MAX_APPLICATIONS})")
    logger.info("=" * 50)

    email, password = get_credentials()
    if not email or not password:
        logger.error("Email and password are required to run the bot.")
        return

    selected_tabs = select_tabs()
    logger.info(f"Applying to tabs: {', '.join(str(t['label']) for t in selected_tabs)}")

    known_answers = load_answers()
    seen_keys = load_previously_applied_urls()
    total_applied = 0

    driver = None
    try:
        driver = create_edge_driver()
        login_naukri(driver, email, password)

        for tab in selected_tabs:
            if total_applied >= MAX_APPLICATIONS:
                break

            logger.info("=" * 50)
            logger.info(f"Tab: {tab['label']}")
            logger.info("=" * 50)

            while total_applied < MAX_APPLICATIONS:
                if not navigate_to_tab(driver, tab['id']):
                    break

                remaining = MAX_APPLICATIONS - total_applied
                batch_limit = min(MAX_SELECT, remaining)

                applied_count, batch_urls = select_jobs_and_apply(driver, seen_keys=seen_keys, max_to_select=batch_limit)
                if applied_count == 0:
                    logger.info(f"Finished tab '{tab['label']}': no more unseen qualifying jobs on this tab.")
                    break

                handle_chatbot_drawer(driver, known_answers)
                save_confirmed_applications(batch_urls)
                total_applied += applied_count
                known_answers = load_answers()

                logger.info(f"🎯 Total applied so far: {total_applied} / {MAX_APPLICATIONS}")
                human_delay(3.0, 5.5)

        logger.info("=" * 50)
        logger.info(f"✅ Run Complete! Total jobs applied in this session: {total_applied}")
        logger.info("=" * 50)

    except Exception as e:
        logger.exception(f"Error encountered during run: {e}")
    finally:
        if driver:
            if KEEP_BROWSER_OPEN:
                logger.info("🔍 KEEP_BROWSER_OPEN is enabled: Press Enter in terminal to close browser...")
                try:
                    input()
                except (KeyboardInterrupt, EOFError):
                    pass
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
