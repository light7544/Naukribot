# Naukri job application helper

This folder contains the Recommended Jobs browser helper and a keyword-search variant. The recommended workflow is:

```powershell
\.venv\Scripts\Activate.ps1
python -u Naukri-Recommended.py
```

The project-local virtual environment is already set up in this folder. If you open a new PowerShell terminal and have not activated it, use the direct command instead: 

```powershell
\.venv\Scripts\python.exe -u Naukri-Recommended.py
```

When the script asks which Naukri tabs to process, enter `1` for **Preferences**.

## Setup

1. Install Python 3.10 or newer and Microsoft Edge.
2. If `.venv` does not exist, create it and install dependencies with `python -m venv .venv` then `\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
3. Put your Naukri credentials and settings in `.env`. The program reads it from the project folder even if you launch the command from another folder. Keep `.env` private.
4. Start the command above. If Naukri presents a CAPTCHA or verification step, complete it in the visible browser.

Selenium 4 includes Selenium Manager, which locates/downloads a compatible EdgeDriver when needed. No separate webdriver-manager package or pandas/BeautifulSoup installs are required for these scripts.

## Recommended Jobs flow

- Select tabs in the terminal; blank input defaults to Preferences.
- The script selects up to five qualifying jobs per batch and respects the configured application cap.
- It tries current and older Naukri job-card selectors and waits for UI state changes instead of assuming the page loaded.
- It reuses only high-confidence saved questionnaire answers from `application_answers.csv`.
- If a question has no matching saved answer, answer it truthfully in the browser. The script no longer invents experience, relocation, salary, notice-period, or eligibility answers.
- If the application drawer cannot be confirmed, it stops the run as uncertain instead of reporting success or continuing into a possible duplicate submission.
- Confirmed job URLs are written to `naukriapplied.csv`; learned answers stay in `application_answers.csv`.

Naukri changes page markup over time. If the page does not expose a supported tab, job card, checkbox, or application drawer, the script logs the current page title and URL and stops that batch. Do not try to bypass CAPTCHA or other account protections.

## Other scripts

- `Naukri-Edge.py` searches jobs using `KEYWORDS`, `LOCATION`, and `PAGES_PER_KEYWORD`.
- `update_naukri_profile.py` and `update_naukri_full_genai_live.py` modify profile content. Review the values they will submit before running.
- `Naukri autoapply jobs.ipynb` is an archived legacy notebook; it used Selenium APIs removed in Selenium 4. Use the Python scripts instead.

## Configuration

See `.env.example` for the supported variables. The Recommended Jobs script uses:
- `NAUKRI_EMAIL`: Your Naukri account email (or prompted at CLI if omitted).
- `NAUKRI_PASSWORD`: Your Naukri account password (or prompted at CLI if omitted).
- `MAX_APPLICATIONS`: Daily application cap (default: `25`, clamped to safe maximum of 30).
- `RECOMMENDED_TABS`: Optional comma-separated tab numbers (e.g., `1` for Preferences). Leave commented to receive the interactive menu each run.
- `KEEP_BROWSER_OPEN`: Optional debug setting (`true` or `false`, default: `false`). When `true`, keeps the browser window open after run completion so you can inspect page cards, tabs, or modals. The console will prompt you to press `Enter` to close the browser and exit.

## Understanding "Zero Selected"

If the log displays `Cards rejected by filters: Found X job cards, but 0 eligible jobs selected` and `Completed run: 0 jobs were processed`:
- **Cards were found and analyzed**: The bot successfully loaded the page and located job cards (e.g., 61 cards on Preferences).
- **Filtering evaluation**: Each card's title is extracted and evaluated against the GenAI / AI Architect / LLM / RAG / Machine Learning whitelist and the DevOps/SRE blacklist.
- **Why it was rejected**: The diagnostic log prints the exact title and rejection filter for each card:
  - `⛔ [REJECTED: NON-GENAI] 'Job Title' | Does not match any GenAI/AI Architect whitelist keyword`
  - `⛔ [REJECTED: BLACKLIST] 'Job Title' | Matched blacklist keyword '...'`
  - `⚠️ [REJECTED: NO CHECKBOX] 'Job Title'`
- **Accurate outcome**: The bot accurately reports that 0 jobs were processed rather than claiming success. If you want to visually verify why cards were rejected or check what cards are on the screen, set `KEEP_BROWSER_OPEN=true` in your `.env`.

## Safety and privacy

- The bot may submit applications from your signed-in account. Review your selected tab and every answer before allowing submission.
- Unknown questionnaire answers require your input; stored answers are in plain CSV, so keep that file private.
- Never share `.env`, application history, or answer CSVs publicly.
- Use the site in accordance with its current terms and account rules. The automation can still break when Naukri changes its interface, login, or application flow.

