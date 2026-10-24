"""
Naukri Complete Profile Overhaul Script (GenAI Architect / 3+ Years Exp)
================================================================================
Targeted Sections:
  1. Resume Headline
  2. Profile Summary
  3. Key Skills Tags
  4. Employment Details (TCS - Job Description & Top 5 Skills)
  5. IT Skills (Generative AI, Azure AI Foundry, Bedrock - 3 Years)
  6. Career Profile (Role Category & Job Role away from DevOps)

Robust Features:
  - JS Click primary execution in safe_click to bypass elementNotInteractable exceptions
  - Event Dispatching (`input` & `change`) so React/Vue/Naukri state commits to backend API
  - Invisibility waits on `.drawer-backdrop` / `.modal-backdrop` to avoid element click interception
  - Generic drawer textarea & input fallbacks for Section 2 (Profile Summary) & Section 5 (IT Skills)
  - Save button & drawer invisibility checks + 3.5s network commit wait per section
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

# ------------------------------------------------------------
# Content Data (GenAI Focus - 3+ Years Experience)
# ------------------------------------------------------------
RESUME_HEADLINE = (
    "Generative AI Solution Architect / GenAI Engineer (3+ Yrs Exp) | Azure AI Foundry, "
    "Azure OpenAI, AWS Bedrock, GCP Vertex AI | RAG, Agentic AI, LangChain, LLMOps"
)

PROFILE_SUMMARY = (
    "Generative AI Solution Architect & GenAI Engineer with 3+ years of experience in architecting "
    "and deploying scalable, enterprise-grade GenAI and Agentic AI applications across Azure AI Foundry, "
    "AWS Bedrock, and GCP Vertex AI. Specialized in hybrid RAG architectures (Azure AI Search, Vector DBs), "
    "agentic workflows (LangGraph, Multi-Agent Systems), LLMOps, and cloud automation (Terraform, Docker, "
    "Kubernetes). Proven track record of implementing enterprise safety guardrails, Content Safety, PII redaction, "
    "and automated evaluation frameworks for service desk and conversational AI solutions."
)

EMPLOYMENT_DESCRIPTION = (
    "Architected and deployed enterprise GenAI solutions with 3+ years of specialized hands-on experience, "
    "including an AI-powered Service Desk Quality & Analytics Bot integrating multi-channel audits (voice transcripts, "
    "ServiceNow tickets, chat logs). Designed hybrid RAG pipelines using Azure AI Search, Azure OpenAI (GPT-4o), "
    "and AWS Bedrock with vector embeddings. Automated infrastructure-as-code deployments using Terraform, Docker, "
    "and Kubernetes with Entra ID Managed Identities and zero-trust private endpoints. Implemented automated evaluation "
    "frameworks measuring SOP groundedness, sentiment analysis, and token cost optimization."
)

KEY_SKILLS_TO_ADD = [
    "Generative AI", "Azure AI Foundry", "AWS Bedrock", "GCP Vertex AI",
    "LangChain", "LangGraph", "RAG", "Azure OpenAI", "Vector Database",
    "LLMOps", "Docker", "Terraform"
]

TOP_EMPLOYMENT_SKILLS = [
    "Azure AI Foundry", "AWS Bedrock", "Generative AI", "RAG", "LangChain"
]


def human_delay(min_s=1.5, max_s=3.0, reason=None):
    """Generate dynamic, human-like delays for visual DOM actions."""
    delay = random.uniform(min_s, max_s)
    msg = f"⏳ Sleeping for {delay:.2f}s"
    if reason:
        msg += f" ({reason})"
    logger.info(msg)
    time.sleep(delay)


def highlight(driver, element, color="yellow", border_size="3px"):
    """Visually highlight a DOM element on screen with a colored outline."""
    try:
        driver.execute_script(
            f"arguments[0].style.border='{border_size} solid {color}';"
            f"arguments[0].style.boxShadow='0 0 10px {color}';",
            element
        )
        time.sleep(0.3)
    except Exception:
        pass


def trigger_input_events(driver, element):
    """Dispatch 'input' and 'change' JavaScript events to ensure frontend frameworks update state."""
    try:
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true })); "
            "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
            element
        )
    except Exception:
        pass


def safe_click(driver, element):
    """Safely scroll to element and click using JS execution to prevent ElementNotInteractableException."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", element)
    except Exception:
        try:
            element.click()
        except Exception:
            pass


def type_human_like(driver, element, text, min_delay=0.015, max_delay=0.045):
    """Simulate keypresses with JS focus and event dispatching."""
    try:
        driver.execute_script("arguments[0].focus();", element)
    except Exception:
        pass

    for ch in text:
        try:
            element.send_keys(ch)
        except Exception:
            driver.execute_script("arguments[0].value += arguments[1];", element, ch)
        time.sleep(random.uniform(min_delay, max_delay))
    trigger_input_events(driver, element)


def wait_for_backdrop_invisibility(driver, timeout=8):
    """Wait for any drawer or modal backdrop overlay to disappear before next action."""
    backdrop_xpaths = [
        "//div[contains(@class,'drawer-backdrop') or contains(@class,'modal-backdrop') or contains(@class,'backdrop') or contains(@class,'overlay')]"
    ]
    for xpath in backdrop_xpaths:
        try:
            elems = driver.find_elements(By.XPATH, xpath)
            for elem in elems:
                if elem.is_displayed():
                    logger.info("Waiting for backdrop overlay to become invisible...")
                    WebDriverWait(driver, timeout).until(EC.invisibility_of_element(elem))
        except Exception:
            pass


def scroll_to_text(driver, text_query):
    """Find element containing text_query and scroll it smoothly into center view."""
    try:
        elements = driver.find_elements(
            By.XPATH,
            f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text_query.lower()}')]"
        )
        for elem in elements:
            if elem.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                time.sleep(1.0)
                return elem
    except Exception:
        pass
    return None


def save_and_wait(driver, save_button, extra_wait=3.5):
    """Click save button, trigger change events, wait for invisibility, and allow network commit."""
    highlight(driver, save_button, color="#00E676")
    trigger_input_events(driver, save_button)
    safe_click(driver, save_button)
    logger.info("Clicked Save. Waiting for drawer/modal to close and network commit...")

    try:
        WebDriverWait(driver, 8).until(EC.invisibility_of_element(save_button))
    except Exception:
        pass

    wait_for_backdrop_invisibility(driver, timeout=6)
    human_delay(extra_wait, extra_wait + 1.0, reason="network save commit window")


def get_credentials():
    """Retrieve credentials from env or prompt interactively without persisting."""
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
    """Create and return a visible Edge WebDriver instance using built-in Selenium Manager or custom path."""
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

    driver = webdriver.Edge(service=service, options=options)
    return driver



def login(driver, email, password):
    """Log in to Naukri.com."""
    logger.info("=" * 60)
    logger.info("STEP 0: Logging in to Naukri.com...")
    logger.info("=" * 60)

    driver.get("https://www.naukri.com/nlogin/login")
    wait = WebDriverWait(driver, 20)

    username_elem = wait.until(
        EC.presence_of_element_located((By.XPATH, "//input[@id='usernameField'] | //input[@id='emailTxt']"))
    )
    highlight(driver, username_elem, color="#00E5FF")
    username_elem.clear()
    type_human_like(driver, username_elem, email)

    human_delay(0.5, 1.2, reason="password field focus")

    pwd_elem = driver.find_element(By.XPATH, "//input[@id='passwordField'] | //input[@id='pwd1']")
    highlight(driver, pwd_elem, color="#00E5FF")
    pwd_elem.clear()
    type_human_like(driver, pwd_elem, password)

    login_btn = driver.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Login')]")
    highlight(driver, login_btn, color="#76FF03")
    safe_click(driver, login_btn)
    logger.info("[✔] Login clicked. Waiting for profile dashboard...")
    human_delay(4.0, 6.0, reason="dashboard navigation")


def update_resume_headline(driver):
    """SECTION 1: Update Resume Headline."""
    logger.info("=" * 60)
    logger.info("[SECTION 1/6] Updating Resume Headline...")
    logger.info("=" * 60)

    wait_for_backdrop_invisibility(driver)
    driver.get("https://www.naukri.com/mnjuser/profile")
    human_delay(2.5, 3.5, reason="loading profile page")

    wait = WebDriverWait(driver, 15)
    scroll_to_text(driver, "Resume headline")

    try:
        edit_selectors = [
            "//div[contains(@class,'resumeHeadline') or contains(@id,'lazyResumeHeadline')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Resume headline') or contains(text(),'Resume Headline')]/ancestor::div[contains(@class,'card') or contains(@class,'widget') or contains(@class,'section') or contains(@class,'box')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Resume headline') or contains(text(),'Resume Headline')]/following::span[contains(@class,'edit')][1]"
        ]
        edit_btn = None
        for sel in edit_selectors:
            found = driver.find_elements(By.XPATH, sel)
            if found:
                edit_btn = found[0]
                break

        if not edit_btn:
            logger.warning("[!] Resume Headline edit button not found.")
            return

        highlight(driver, edit_btn, color="yellow")
        safe_click(driver, edit_btn)
        human_delay(1.5, 2.5, reason="headline edit modal open")

        textarea = wait.until(
            EC.presence_of_element_located((
                By.XPATH,
                "//textarea[@id='resumeHeadlineTxt'] | "
                "//div[contains(@class,'resumeHeadline') or contains(@class,'drawer') or contains(@class,'modal')]//textarea"
            ))
        )
        highlight(driver, textarea, color="#FFD600")
        textarea.click()
        textarea.send_keys(Keys.CONTROL + "a")
        textarea.send_keys(Keys.BACKSPACE)
        trigger_input_events(driver, textarea)
        human_delay(0.5, 1.0, reason="cleared headline text")

        logger.info("Typing new Resume Headline (GenAI 3+ Years)...")
        type_human_like(driver, textarea, RESUME_HEADLINE)
        trigger_input_events(driver, textarea)
        human_delay(1.0, 1.5, reason="headline typing complete")

        save_btn = driver.find_element(
            By.XPATH,
            "//div[contains(@class,'resumeHeadline') or contains(@class,'drawer') or contains(@class,'modal')]//button[contains(text(),'Save')] | //button[contains(text(),'Save')]"
        )
        save_and_wait(driver, save_btn)
        logger.info("[✔] Resume Headline updated and committed successfully!")
    except Exception as e:
        logger.warning(f"[!] Resume Headline update error: {e}")


def update_profile_summary(driver):
    """SECTION 2: Update Profile Summary."""
    logger.info("=" * 60)
    logger.info("[SECTION 2/6] Updating Profile Summary...")
    logger.info("=" * 60)

    wait_for_backdrop_invisibility(driver)
    scroll_to_text(driver, "Profile summary")

    try:
        edit_selectors = [
            "//div[contains(@class,'profileSummary') or contains(@id,'lazyProfileSummary') or contains(@class,'summary')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Profile summary') or contains(text(),'Profile Summary')]/ancestor::div[contains(@class,'card') or contains(@class,'widget') or contains(@class,'section') or contains(@class,'box')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Profile summary') or contains(text(),'Profile Summary')]/following::span[contains(@class,'edit')][1]",
            "//*[contains(text(),'Profile summary') or contains(text(),'Profile Summary')]/..//*[contains(@class,'edit') or contains(@class,'icon')]"
        ]

        edit_btn = None
        for sel in edit_selectors:
            found = driver.find_elements(By.XPATH, sel)
            for f in found:
                if f.is_displayed():
                    edit_btn = f
                    break
            if edit_btn:
                break

        if edit_btn:
            highlight(driver, edit_btn, color="yellow")
            safe_click(driver, edit_btn)
            human_delay(2.0, 3.5, reason="profile summary edit modal open")

            wait = WebDriverWait(driver, 10)
            textarea = wait.until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//div[contains(@class,'drawer') or contains(@class,'modal') or contains(@class,'layer')]//textarea | "
                    "//textarea[contains(@id,'profileSummary') or contains(@name,'profileSummary') or contains(@placeholder,'summary') or contains(@class,'summary')] | "
                    "//textarea"
                ))
            )
            highlight(driver, textarea, color="#FFD600")
            textarea.click()
            textarea.send_keys(Keys.CONTROL + "a")
            textarea.send_keys(Keys.BACKSPACE)
            trigger_input_events(driver, textarea)
            human_delay(0.5, 1.0, reason="cleared profile summary text")

            logger.info("Inserting GenAI Profile Summary (3+ Yrs Exp)...")
            textarea.send_keys(PROFILE_SUMMARY)
            trigger_input_events(driver, textarea)
            human_delay(1.0, 2.0, reason="summary insertion complete")

            save_btns = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'profileSummary') or contains(@class,'drawer') or contains(@class,'modal')]//button[contains(text(),'Save')] | "
                "//button[contains(text(),'Save')]"
            )
            for sb in save_btns:
                if sb.is_displayed():
                    save_and_wait(driver, sb)
                    logger.info("[✔] Profile Summary updated and committed successfully!")
                    break
        else:
            logger.warning("[!] Profile Summary edit button not found on page.")

    except Exception as e:
        logger.warning(f"[!] Profile Summary section error: {e}")


def update_key_skills(driver):
    """SECTION 3: Update Key Skills Tags."""
    logger.info("=" * 60)
    logger.info("[SECTION 3/6] Updating Key Skills Tags...")
    logger.info("=" * 60)

    wait_for_backdrop_invisibility(driver)
    scroll_to_text(driver, "Key skills")

    try:
        edit_selectors = [
            "//div[contains(@class,'keySkills') or contains(@id,'lazyKeySkills')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Key skills') or contains(text(),'Key Skills')]/ancestor::div[contains(@class,'card') or contains(@class,'widget') or contains(@class,'section') or contains(@class,'box')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Key skills') or contains(text(),'Key Skills')]/following::span[contains(@class,'edit')][1]",
            "//*[contains(text(),'Key skills') or contains(text(),'Key Skills')]/..//*[contains(@class,'edit') or contains(@class,'icon')]"
        ]

        edit_btn = None
        for sel in edit_selectors:
            found = driver.find_elements(By.XPATH, sel)
            for f in found:
                if f.is_displayed():
                    edit_btn = f
                    break
            if edit_btn:
                break

        if edit_btn:
            highlight(driver, edit_btn, color="yellow")
            safe_click(driver, edit_btn)
            human_delay(2.0, 3.5, reason="key skills modal open")

            input_boxes = driver.find_elements(
                By.XPATH,
                "//input[contains(@placeholder,'skill') or contains(@placeholder,'Skill') or contains(@id,'keySkillSugg') or contains(@class,'input')] | "
                "//div[contains(@class,'keySkills') or contains(@class,'drawer') or contains(@class,'modal')]//input"
            )
            if input_boxes:
                skill_input = input_boxes[0]
                highlight(driver, skill_input, color="#00E5FF")

                for skill in KEY_SKILLS_TO_ADD:
                    try:
                        logger.info(f"  + Adding skill tag: '{skill}'")
                        safe_click(driver, skill_input)
                        type_human_like(driver, skill_input, skill, min_delay=0.015, max_delay=0.04)
                        human_delay(0.6, 1.2, reason=f"suggestion lookup for {skill}")

                        suggestions = driver.find_elements(
                            By.XPATH,
                            "//div[contains(@class,'suggester') or contains(@class,'dropdown') or contains(@class,'autoComplete') or contains(@class,'Sugg') or contains(@class,'layer')]//li"
                        )
                        if suggestions and suggestions[0].is_displayed():
                            safe_click(driver, suggestions[0])
                        else:
                            skill_input.send_keys(Keys.ENTER)
                        trigger_input_events(driver, skill_input)
                        human_delay(0.4, 0.8, reason=f"added {skill}")
                    except Exception as se:
                        logger.debug(f"Could not add skill tag '{skill}': {se}")

            save_btns = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'keySkills') or contains(@class,'drawer') or contains(@class,'modal')]//button[contains(text(),'Save')] | //button[contains(text(),'Save')]"
            )
            for sb in save_btns:
                if sb.is_displayed():
                    save_and_wait(driver, sb)
                    logger.info("[✔] Key Skills updated and committed successfully!")
                    break
        else:
            logger.warning("[!] Key Skills edit button not found on page.")

    except Exception as e:
        logger.warning(f"[!] Key Skills update error: {e}")


def update_employment_description(driver):
    """SECTION 4: Update Employment Description (TCS - Systems Engineer & Top 5 Key Skills)."""
    logger.info("=" * 60)
    logger.info("[SECTION 4/6] Updating Employment Description & Top 5 Key Skills...")
    logger.info("=" * 60)

    wait_for_backdrop_invisibility(driver)
    scroll_to_text(driver, "Employment")

    try:
        edit_selectors = [
            "//div[contains(@class,'employment') or contains(@id,'lazyEmployment')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Employment') or contains(text(),'Systems Engineer') or contains(text(),'Tata Consultancy Services')]/ancestor::div[contains(@class,'card') or contains(@class,'widget') or contains(@class,'section') or contains(@class,'box') or contains(@class,'employment')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Employment')]/following::span[contains(@class,'edit')][1]"
        ]

        edit_btn = None
        for sel in edit_selectors:
            found = driver.find_elements(By.XPATH, sel)
            for f in found:
                if f.is_displayed():
                    edit_btn = f
                    break
            if edit_btn:
                break

        if edit_btn:
            highlight(driver, edit_btn, color="yellow")
            safe_click(driver, edit_btn)
            human_delay(2.0, 3.5, reason="employment edit drawer open")

            desc_textareas = driver.find_elements(
                By.XPATH,
                "//textarea[contains(@id,'jobDescription') or contains(@name,'jobDescription') or contains(@placeholder,'description') or contains(@class,'jobDescription')] | "
                "//div[contains(@class,'drawer') or contains(@class,'modal') or contains(@class,'employment')]//textarea"
            )

            if desc_textareas:
                desc_elem = desc_textareas[0]
                highlight(driver, desc_elem, color="#FFD600")
                desc_elem.click()
                desc_elem.send_keys(Keys.CONTROL + "a")
                desc_elem.send_keys(Keys.BACKSPACE)
                trigger_input_events(driver, desc_elem)
                human_delay(0.5, 1.0, reason="cleared employment description")

                logger.info("Inserting GenAI Employment Description (3+ Yrs Exp)...")
                desc_elem.send_keys(EMPLOYMENT_DESCRIPTION)
                trigger_input_events(driver, desc_elem)
                human_delay(1.0, 2.0, reason="description entered")

            # Check for top key skills inside employment form
            emp_skills_inputs = driver.find_elements(
                By.XPATH,
                "//input[contains(@placeholder,'Top key skills') or contains(@placeholder,'key skills') or contains(@id,'topKeySkills') or contains(@name,'topKeySkills') or contains(@placeholder,'Skills')]"
            )
            if emp_skills_inputs:
                skills_in = emp_skills_inputs[0]
                highlight(driver, skills_in, color="#00E5FF")
                for s in TOP_EMPLOYMENT_SKILLS:
                    try:
                        logger.info(f"  + Adding Top Employment Skill: '{s}'")
                        safe_click(driver, skills_in)
                        type_human_like(driver, skills_in, s)
                        human_delay(0.5, 1.0)
                        sugg = driver.find_elements(
                            By.XPATH,
                            "//div[contains(@class,'suggester') or contains(@class,'dropdown') or contains(@class,'autoComplete') or contains(@class,'layer')]//li"
                        )
                        if sugg and sugg[0].is_displayed():
                            safe_click(driver, sugg[0])
                        else:
                            skills_in.send_keys(Keys.ENTER)
                        trigger_input_events(driver, skills_in)
                    except Exception:
                        pass

            save_btns = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'drawer') or contains(@class,'modal') or contains(@class,'employment')]//button[contains(text(),'Save')] | //button[contains(text(),'Save') or contains(@id,'submit')]"
            )
            for sb in save_btns:
                if sb.is_displayed():
                    save_and_wait(driver, sb)
                    logger.info("[✔] Employment Details updated and committed successfully!")
                    break
        else:
            logger.warning("[!] Employment edit button not found on page.")

    except Exception as e:
        logger.warning(f"[!] Employment Section update error: {e}")


def update_it_skills(driver):
    """SECTION 5: Add / Update IT Skills (Generative AI - 3 Years)."""
    logger.info("=" * 60)
    logger.info("[SECTION 5/6] Updating IT Skills Table (Generative AI - 3 Years)...")
    logger.info("=" * 60)

    wait_for_backdrop_invisibility(driver)
    scroll_to_text(driver, "IT skills")

    try:
        add_selectors = [
            "//div[contains(@class,'itSkills') or contains(@id,'lazyITSkills')]//*[contains(text(),'Add details') or contains(text(),'Add IT skill') or contains(text(),'Add') or contains(@class,'add') or contains(@class,'edit')]",
            "//*[contains(text(),'IT skills') or contains(text(),'IT Skills')]/ancestor::div[contains(@class,'card') or contains(@class,'widget') or contains(@class,'section') or contains(@class,'box')]//*[contains(text(),'Add details') or contains(text(),'Add IT skill') or contains(text(),'Add') or contains(text(),'Edit') or contains(@class,'add') or contains(@class,'edit')]",
            "//*[contains(text(),'IT skills') or contains(text(),'IT Skills')]/following::*[contains(text(),'Add') or contains(@class,'add') or contains(@class,'edit')][1]"
        ]

        add_btn = None
        for sel in add_selectors:
            found = driver.find_elements(By.XPATH, sel)
            for f in found:
                if f.is_displayed():
                    add_btn = f
                    break
            if add_btn:
                break

        if add_btn:
            highlight(driver, add_btn, color="yellow")
            safe_click(driver, add_btn)
            human_delay(2.0, 3.5, reason="IT skills modal open")

            skill_inputs = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'drawer') or contains(@class,'modal')]//input | "
                "//input[contains(@id,'skillName') or contains(@placeholder,'Skill') or contains(@name,'skillName')]"
            )
            if skill_inputs:
                s_input = skill_inputs[0]
                highlight(driver, s_input, color="#00E5FF")
                safe_click(driver, s_input)
                type_human_like(driver, s_input, "Generative AI")
                human_delay(0.8, 1.5, reason="IT skill suggestion lookup")

                # Strictly click the first suggestion item from the dropdown container via JS safe_click
                sugg_items = driver.find_elements(
                    By.XPATH,
                    "//div[contains(@class,'suggester') or contains(@class,'dropdown') or contains(@class,'autoComplete') or contains(@class,'layer')]//li | "
                    "//ul[contains(@class,'suggester') or contains(@class,'dropdown')]//li"
                )
                clicked_sugg = False
                for item in sugg_items:
                    if item.is_displayed():
                        logger.info(f"  + Clicking IT Skill suggestion item: '{item.text.strip()}'")
                        safe_click(driver, item)
                        clicked_sugg = True
                        break

                if not clicked_sugg:
                    s_input.send_keys(Keys.ENTER)

                trigger_input_events(driver, s_input)

            # Experience Years input/dropdown (usually the 2nd input in drawer or input with exp/year in id)
            exp_inputs = driver.find_elements(
                By.XPATH,
                "//input[contains(@id,'expYears') or contains(@placeholder,'Years') or contains(@id,'experience') or contains(@name,'expYears')]"
            )
            if not exp_inputs and len(skill_inputs) > 1:
                exp_inputs = [skill_inputs[1]]

            if exp_inputs:
                y_input = exp_inputs[0]
                highlight(driver, y_input, color="#00E5FF")
                safe_click(driver, y_input)
                type_human_like(driver, y_input, "3")
                human_delay(0.6, 1.2, reason="IT skill experience lookup")

                y_sugg = driver.find_elements(
                    By.XPATH,
                    "//div[contains(@class,'dropdown') or contains(@class,'suggester') or contains(@class,'layer')]//li[contains(text(),'3')]"
                )
                for ys in y_sugg:
                    if ys.is_displayed():
                        safe_click(driver, ys)
                        break
                trigger_input_events(driver, y_input)

            save_btns = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'drawer') or contains(@class,'modal')]//button[contains(text(),'Save')] | //button[contains(text(),'Save')]"
            )
            for sb in save_btns:
                if sb.is_displayed():
                    save_and_wait(driver, sb)
                    logger.info("[✔] IT Skill (Generative AI - 3 Years) saved and committed successfully!")
                    break
        else:
            logger.warning("[!] IT Skills add/edit button not found on page.")

    except Exception as e:
        logger.warning(f"[!] IT Skills update error: {e}")


def update_career_profile(driver):
    """SECTION 6: Update Career Profile (Role Category & Job Role away from DevOps)."""
    logger.info("=" * 60)
    logger.info("[SECTION 6/6] Updating Career Profile (Role & Category away from DevOps)...")
    logger.info("=" * 60)

    wait_for_backdrop_invisibility(driver)
    scroll_to_text(driver, "Career profile")

    try:
        edit_selectors = [
            "//div[contains(@class,'careerProfile') or contains(@id,'lazyCareerProfile')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Career profile') or contains(text(),'Career Profile')]/ancestor::div[contains(@class,'card') or contains(@class,'widget') or contains(@class,'section') or contains(@class,'box')]//span[contains(@class,'edit') or contains(@class,'icon')]",
            "//*[contains(text(),'Career profile') or contains(text(),'Career Profile')]/following::span[contains(@class,'edit')][1]"
        ]

        edit_btn = None
        for sel in edit_selectors:
            found = driver.find_elements(By.XPATH, sel)
            for f in found:
                if f.is_displayed():
                    edit_btn = f
                    break
            if edit_btn:
                break

        if edit_btn:
            highlight(driver, edit_btn, color="yellow")
            safe_click(driver, edit_btn)
            human_delay(2.0, 3.5, reason="career profile edit modal open")

            role_inputs = driver.find_elements(
                By.XPATH,
                "//input[contains(@id,'jobRole') or contains(@placeholder,'Job role') or contains(@placeholder,'job role') or contains(@name,'jobRole') or contains(@id,'roleCategory')]"
            )
            for r_input in role_inputs:
                try:
                    highlight(driver, r_input, color="#00E5FF")
                    safe_click(driver, r_input)
                    r_input.send_keys(Keys.CONTROL + "a")
                    r_input.send_keys(Keys.BACKSPACE)
                    type_human_like(driver, r_input, "Artificial Intelligence Architect")
                    human_delay(0.6, 1.2, reason="role suggestion lookup")

                    suggestions = driver.find_elements(
                        By.XPATH,
                        "//div[contains(@class,'suggester') or contains(@class,'dropdown') or contains(@class,'autoComplete') or contains(@class,'layer')]//li"
                    )
                    if suggestions and suggestions[0].is_displayed():
                        safe_click(driver, suggestions[0])
                    else:
                        r_input.send_keys(Keys.ENTER)
                    trigger_input_events(driver, r_input)
                except Exception as re:
                    logger.debug(f"Career role input error: {re}")

            save_btns = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'careerProfile') or contains(@class,'drawer') or contains(@class,'modal')]//button[contains(text(),'Save')] | //button[contains(text(),'Save')]"
            )
            for sb in save_btns:
                if sb.is_displayed():
                    save_and_wait(driver, sb)
                    logger.info("[✔] Career Profile updated and committed successfully!")
                    break
        else:
            logger.warning("[!] Career Profile edit button not found on page.")

    except Exception as e:
        logger.warning(f"[!] Career Profile section error/skip: {e}")


def main():
    """Main profile overhaul entry point."""
    logger.info("=" * 60)
    logger.info("Naukri Complete Profile Overhaul (GenAI Architect / 3+ Yrs Exp)")
    logger.info("==========================================================")

    email, password = get_credentials()
    if not email or not password:
        logger.error("Naukri email and password are required.")
        return

    driver = setup_driver()
    try:
        login(driver, email, password)
        update_resume_headline(driver)
        update_profile_summary(driver)
        update_key_skills(driver)
        update_employment_description(driver)
        update_it_skills(driver)
        update_career_profile(driver)

        logger.info("=" * 60)
        logger.info("✅ ALL TARGETED PROFILE SECTIONS PROCESSED AND COMMITTED!")
        logger.info("==========================================================")
        logger.info("Keeping browser open for 20 seconds so you can inspect your live profile on screen...")
        human_delay(19.5, 20.5, reason="final live inspection delay")

    except Exception as err:
        logger.exception(f"[!] Unexpected error during profile overhaul: {err}")
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Browser session closed cleanly.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
