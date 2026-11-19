# Smart CO PO AttainX — Outcome-Based Education (OBE) Attainment Dashboard

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![Pandas](https://img.shields.io/badge/Pandas-2.1.4-150458.svg)](https://pandas.pydata.org/)
[![NumPy](https://img.shields.io/badge/NumPy-1.26.2-013243.svg)](https://numpy.org/)
[![Deployment](https://img.shields.io/badge/Deploy-Vercel-black.svg)](https://vercel.com/)

**Smart CO PO AttainX** is a web-based academic analytics and Outcome-Based Education (OBE) attainment platform engineered for engineering institutions. It automates Course Outcome (CO), Program Outcome (PO), and Program Specific Outcome (PSO) direct and indirect attainment calculations, generates subject-specific survey templates, validates CSV marks data, and renders accreditation-compliant dashboards conforming to National Board of Accreditation (NBA) criteria.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Project Architecture](#project-architecture)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Local Installation and Setup](#local-installation-and-setup)
- [Environment Variables and Configuration](#environment-variables-and-configuration)
- [How to Use AttainX](#how-to-use-attainx)
- [Academic Calculation Methodology](#academic-calculation-methodology)
  - [Course Evaluation Types and Weighting Schemes](#course-evaluation-types-and-weighting-schemes)
  - [Zero and Null CO-PO Mapping Value Exclusion](#zero-and-null-co-po-mapping-value-exclusion)
  - [Direct Assessment Attainment](#direct-assessment-attainment)
  - [Indirect Survey Attainment](#indirect-survey-attainment)
  - [PO and PSO Aggregation and Target Percentage](#po-and-pso-aggregation-and-target-percentage)
  - [Summary Display Conventions](#summary-display-conventions)
- [CSV Upload Formats and Templates](#csv-upload-formats-and-templates)
  - [1. CO-PO Mapping Sheets](#1-co-po-mapping-sheets)
  - [2. Direct Attainment Marks Sheets](#2-direct-attainment-marks-sheets)
  - [3. Survey Sheets (Indirect Ratings)](#3-survey-sheets-indirect-ratings)
  - [Dynamic Survey Template Generator](#dynamic-survey-template-generator)
- [Deployment on Vercel](#deployment-on-vercel)
- [Troubleshooting](#troubleshooting)
- [Limitations and Important Notes](#limitations-and-important-notes)

---

## Project Overview

Outcome-Based Education (OBE) requires academic departments to quantitatively measure student performance against stated Course Outcomes (COs) and assess how each course contributes to broader Program Outcomes (POs) and Program Specific Outcomes (PSOs). Performing these calculations manually across hundreds of students, continuous internal assessments, semester exams, and exit surveys is error-prone, labor-intensive, and difficult to audit.

**AttainX** automates this entire pipeline:
1. Faculty upload raw assessment and survey data via standardized CSV templates.
2. The calculation engine processes direct examinations and indirect surveys using NBA-standard 3-level rubrics.
3. Attainment scores are mapped to POs and PSOs according to academic department correlation matrices.
4. An interactive, print-ready dashboard is generated with visual target matrices, calculation summaries, and PDF export capabilities.

The application is architected to run as a high-performance serverless function on **Vercel** as well as in standard on-premise or local Python environments.

---

## Key Features

- **Multi-Algorithm Support:**
  - **Old POs (Till 2024-25):** 12 Program Outcomes (PO1–PO12) + 3 PSOs, 6 Course Outcomes, utilizing In-Semester Exam (ISE), End-Semester Exam (ESE), Unit Tests (UT1, UT2), Prelims, and Practical (PR) components.
  - **Old POs (11), CO(6):** Dedicated 11-PO curriculum format excluding PO12 with strict 6-CO validation.
  - **New POs (From 2025-26):** Modern assessment scheme integrating ESE with Continuous Comprehensive Evaluation (CCE1–CCE5).
- **Flexible Course Evaluation Types:**
  - **Standard Theory / Practical:** Evaluates classroom theory and optional laboratory work using an **80% Direct : 20% Indirect** weighting ratio.
  - **Only Practical:** Dedicated standalone laboratory/practical assessment using **100% Direct Attainment** (no exit survey required).
  - **Project / Termwork / Seminar:** Specialized project evaluation weighting ESE/Oral (75%) and continuous Review/Termwork (25%) using **100% Direct Attainment**.
- **Accurate Mathematical Aggregation:**
  - Strict exclusion of `0`, blank, `NaN`, and null mapping values from both mapping targets and weighted attainment denominators.
  - Mathematically sound weighted averaging preventing artificial score deflation.
  - Uncapped percentage calculation allowing genuine over-target performance tracking.
- **Dynamic Subject-Specific Survey Template Generator:**
  - Automatically parses the uploaded CO-PO mapping sheet in real time.
  - Generates custom survey CSVs matching the exact CO identifiers and count of the subject (5 COs, 6 COs, or arbitrary counts).
  - Outputs files with UTF-8 BOM (`\ufeff`) for native compatibility with Microsoft Excel.
- **Encoding-Safe CSV Ingestion:**
  - Multi-stage encoding fallback (`utf-8-sig` $\rightarrow$ `utf-8` $\rightarrow$ `cp1252`).
  - Transparently decodes Windows-1252 characters (such as en-dashes `0x96` and curly quotes) without data corruption or loss.
- **Option B Strict Survey Alignment:**
  - Robust CO matching using exact normalized string match, numeric CO index resolution, and positional mapping.
  - Enforces strict validation: rejects surveys missing required CO columns with precise, actionable error messages.
- **Accreditation-Ready Visual Dashboard:**
  - Color-coded attainment tables and tooltips displaying step-by-step formulas.
  - Dedicated `@media print` CSS styling optimized for one-click browser-to-PDF export.
  - Session-safe workflow enabling consecutive subject calculations without server restarts.
- **Authentication & Security:**
  - Role-based login system for Administrators and Department Faculty.
  - 30-minute rolling session timeout and strict HTTP-only cookie policies.
  - Request body limits to protect against denial-of-service and buffer exhaustion.

---

## Technology Stack

| Layer | Component | Version | Description |
|---|---|---|---|
| **Runtime** | Python | 3.12 | Core programming language runtime |
| **Framework** | Flask | 3.0.0 | Lightweight WSGI web framework and routing |
| **Data Engine** | Pandas | 2.1.4 | High-performance tabular data parsing, cleaning, and aggregation |
| **Numerical Engine** | NumPy | 1.26.2 | Vectorized numerical operations and NaN/null handling |
| **Frontend UI** | HTML5 / CSS3 / Vanilla JS | ES6+ | Responsive user interface, dynamic DOM state management, print stylesheet |
| **Serverless Host** | Vercel Serverless Functions | — | Cloud execution environment with 60s max duration |

---

## Project Architecture

AttainX utilizes a dual-tier execution architecture optimized for serverless platforms like Vercel while preserving modular local development:

```
+------------------------------------------------------------------------+
|                          Web Browser Client                            |
|          (Upload Form, JavaScript Dynamic State, Dashboard UI)         |
+------------------------------------+-----------------------------------+
                                     |
                                     | HTTP Requests (Form Data, CSVs)
                                     v
+------------------------------------------------------------------------+
|                      app.py (Root Serverless Gateway)                  |
|  - Manages bundle lifecycle & unpacking into ephemeral /tmp directory  |
|  - Dynamically loads core application via importlib                    |
|  - Injects encoding-safe CSV readers & survey generation logic        |
|  - Enforces 11-PO / New-PO calculation and rendering guards            |
+------------------------------------+-----------------------------------+
                                     |
                                     | Extracts on startup / mtime update
                                     v
+------------------------------------------------------------------------+
|                  obe-source.zip (Application Core)                     |
|  /obe-po-attainment-dashboard-github/                                  |
|    |-- app.py                    (Core Flask routes & calculation math)|
|    |-- templates/                                                      |
|    |     |-- login.html          (Authentication view)                 |
|    |     |-- upload_form.html    (Dynamic upload interface & JS logic) |
|    |     |-- dashboard.html      (OBE calculation results & print view)|
|    |-- public/static/            (Static assets, logo, CSV templates)  |
+------------------------------------------------------------------------+
```

1. **Root Gateway (`app.py`):** Serves as the WSGI entry point configured in `vercel.json`. It monitors the modification timestamp of `obe-source.zip`. On cold start or when the bundle updates, it unpacks the archive into the function's ephemeral `/tmp/attainx-source` filesystem, dynamically loads the application module, and applies production patches.
2. **Bundled Core (`obe-source.zip`):** Contains the complete Flask application, templates, mathematical algorithms, and static assets. This encapsulation keeps the repository root clean and allows instant deployment as a single serverless package.

---

## Repository Structure

```
AttainX/
├── .gitignore               # Git exclusion rules (pycache, env files, temporary directories)
├── .python-version          # Pinned Python version (3.12)
├── README.md                # Comprehensive technical documentation
├── app.py                   # Root WSGI gateway, bundle extractor, and patch layer
├── obe-source.zip           # Encapsulated application core archive
│   └── obe-po-attainment-dashboard-github/
│       ├── app.py           # Core Flask application, security, and algorithms
│       ├── requirements.txt # Dependency declarations for the bundled application
│       ├── vercel.json      # Deployment configuration for the bundled application
│       ├── public/
│       │   └── static/      # Downloadable CSV templates and department assets
│       │       ├── logo.png
│       │       ├── mapping_template.csv
│       │       ├── mapping_11po_template.csv
│       │       ├── mapping_new_pos_template.csv
│       │       ├── direct_template.csv
│       │       ├── direct_practical_template.csv
│       │       ├── direct_newpos_template.csv
│       │       ├── direct_only_practical_template.csv
│       │       ├── indirect_template.csv
│       │       ├── indirect_newpos_template.csv
│       │       └── PROJECT_ATTAINMENT.csv
│       └── templates/       # Jinja2 presentation templates
│           ├── index.html
│           ├── login.html
│           ├── upload_form.html
│           └── dashboard.html
├── requirements.txt         # Root Python dependencies (Flask, pandas, numpy)
└── vercel.json              # Vercel deployment and serverless function configuration
```

---

## Prerequisites

Before setting up AttainX locally, ensure you have:

- **Python:** Version 3.10 to 3.12 installed (`python3 --version`).
- **pip:** Python package installer (`pip --version`).
- **Git:** Version control system (`git --version`).
- **Web Browser:** Google Chrome, Mozilla Firefox, Microsoft Edge, or Apple Safari (modern browser with JavaScript enabled).

---

## Local Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/nafisdevtale/AttainX.git
cd AttainX
```

### 2. Create and Activate a Virtual Environment

It is recommended to run the project in an isolated Python virtual environment:

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
python -m venv venv
.\venv\Scripts\activate.bat
```

### 3. Install Dependencies

Install the pinned production dependencies:

```bash
pip install -r requirements.txt
```

Verify that all three packages installed successfully:
```bash
python -c "import flask, pandas, numpy; print('Environment ready!')"
```

### 4. Run the Application

Start the local development server:

```bash
python app.py
```

The application will extract `obe-source.zip` into `/tmp/attainx-source` (if not already extracted) and launch the Flask development server at:

```
http://127.0.0.1:5000/
```

Open your browser and navigate to the URL above to access the login page.

---

## Environment Variables and Configuration

AttainX relies on environment variables for session encryption and authentication credentials. For local development, safe default values are provided automatically. For production or staging deployments, configure the following variables:

| Variable | Required in Production | Default (Local Dev) | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | Fallback test key | Cryptographic secret for signing Flask session cookies. Must be a high-entropy string. |
| `TEACHER_PASSWORD` | **Yes** | `Instru` | Shared authentication password for pre-configured institutional faculty accounts. |
| `ADMIN_EMAILS` | Optional | `admin_email@example.com` | Comma-separated list of administrator email addresses. |
| `ADMIN_PASSWORD` | When Admin set | `ENTER_ADMIN_PASSWORD_HERE` | Password required for administrator access. |
| `VERCEL` | Auto-set | `None` | Automatically defined by Vercel; enables HTTPS-only secure session cookies. |

### Generating a Production Secret Key

Generate a cryptographically secure 64-character token using Python's `secrets` module:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Security & Session Policies

- **Session Inactivity Window:** 30 minutes of rolling inactivity (`PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)`).
- **Cookie Security:** `HttpOnly=True` (mitigates XSS cookie theft), `SameSite=Lax` (mitigates CSRF), `Secure=True` (enforced under Vercel HTTPS).
- **Upload Payload Cap:** Maximum request size is capped at **4 MB** (`MAX_CONTENT_LENGTH = 4 * 1024 * 1024`) to stay within serverless limits and prevent memory exhaustion.

---

## How to Use AttainX

Follow this workflow to calculate attainment for any course:

```
+-----------------------------------------------------------------------------------+
| 1. Log In                                                                         |
|    Sign in using an institutional faculty account or administrator credentials.   |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 2. Course & Class Selection                                                        |
|    Select Teacher Name, Academic Year, Class (FY B Tech through BE),               |
|    Course Evaluation Type, and Subject.                                           |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 3. Set Academic Algorithm & Attainment Threshold                                  |
|    Choose Old POs, Old POs (11), or New POs. Define baseline target % (default: 80%).|
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 4. Download / Generate Templates                                                  |
|    - Download official CO-PO Mapping & Direct Marks CSV templates.                |
|    - Select Mapping file and click 'Generate Survey Template' for matched COs.    |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 5. Upload Completed CSVs                                                          |
|    Upload Mapping Sheet, Direct Attainment Sheet, and Survey Sheet (as required). |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 6. Generate & Export Dashboard                                                    |
|    Click 'Generate Dashboard' to inspect calculation matrices. Use 'Save as PDF'  |
|    or click 'Calculate Another Subject' to continue.                              |
+-----------------------------------------------------------------------------------+
```

### Step 1: Authentication
Navigate to `/login`. Sign in using a pre-configured department email address or administrator credentials.

### Step 2: Course Information
1. **Teacher Name:** Select faculty member from the dropdown.
2. **Academic Year:** Select the evaluation academic year (e.g., `2024-25`, `2025-26`).
3. **Class Name:** Choose from the strictly ordered class offerings:
   - `FY B Tech`
   - `SE (Second Year)`
   - `SY B Tech`
   - `TY B Tech`
   - `TE (Third Year)`
   - `BE (Final Year)`
4. **Course Evaluation Type:**
   - *Standard Theory / Practical*
   - *Only Practical* (Automatically sets algorithm to New POs)
   - *Project / Termwork / Seminar*
5. **Subject Selection:** Select the subject. When switching between Theory and Practical under FY B Tech, the subject code automatically toggles between `ET124ES103` (Theory) and `ET124ES105` (Practical) while maintaining identical course titles.

### Step 3: Algorithm & Thresholds
- **Algorithm:** Select `Old POs (Till 2024-25)`, `OLD POs (11), CO(6)`, or `New POs (From 2025-26)`.
- **Target Threshold:** Enter the target student percentage (typically 80%, meaning 80% marks represents high attainment).

### Step 4: CSV Upload & Generation
- Attach the **CO-PO Mapping Sheet**.
- Click **📥 Generate Survey Template** to dynamically generate a survey CSV with headers matching the mapped COs.
- Fill in student exit survey responses (ratings 1–3).
- Attach the **Direct Attainment Sheet** and **Survey Sheet**.

### Step 5: Dashboard Review & Print
- Click **Generate Dashboard**.
- Review the Theory CO Attainment Summary, PO/PSO target tables, and attainment percentages.
- Click **Save as PDF / Print** to export an official accreditation record.
- Click **Calculate Another Subject** to process additional courses without losing session state.

---

## Academic Calculation Methodology

### Course Evaluation Types and Weighting Schemes

AttainX implements three dedicated evaluation paradigms based on institutional and NBA guidelines:

| Course Evaluation Type | Direct Weight | Indirect Survey Weight | Assessment Components Used |
|---|---|---|---|
| **Standard Theory / Practical** | **80%** (0.80) | **20%** (0.20) | ISE, ESE, UT1, UT2, Prelims (Old POs) or 75% ESE + 25% CCE (New POs) + optional PR lab |
| **Only Practical** | **100%** (1.00) | **0%** (None) | 75% ESE (Practical Exam) + 25% CCE (or 100% CCE for CCE-only practicals) |
| **Project / Termwork / Seminar** | **100%** (1.00) | **0%** (None) | 75% ESE / Oral Exam + 25% Termwork / Continuous Reviews |

---

### Zero and Null CO-PO Mapping Value Exclusion

To prevent artificial dilution of mapping targets and weighted attainment, AttainX strictly excludes non-mapped correlations:

1. **Eligible Values:** Only numeric values in $\{1, 2, 3\}$ are recognized as valid mapping weights.
2. **Excluded Values:** `0`, empty strings `""`, `NaN`, `-`, and null entries are completely ignored.
3. **Mapping Target Formula:**
   $$\text{Mapping Target} = \frac{\sum_{i \in \text{valid}} w_i}{N_{\text{valid}}}$$
   Where $w_i \in \{1, 2, 3\}$ and $N_{\text{valid}}$ is the count of non-zero, non-null mapping values for that PO/PSO.
4. **Weighted Attainment Formula:**
   $$\text{Weighted Attainment} = \frac{\sum_{i \in \text{valid}} (\text{CO Attainment}_i \times w_i)}{\sum_{i \in \text{valid}} w_i}$$
5. **Zero Division Guard:** If all mapping values for a PO or PSO column are zero, blank, or null, both the Target Mapping and Attainment default safely to `0.00`.

#### Numerical Verification Examples

| Mapping Weights Row | Valid Values | Valid Count | Total Weight | Mapping Target |
|---|---|---|---|---|
| `[3, 2, 0, 1, 0, 0]` | `[3, 2, 1]` | 3 | 6 | $\mathbf{2.00}$ |
| `[3, 2, 1, 2, 1, 1]` | `[3, 2, 1, 2, 1, 1]` | 6 | 10 | $\mathbf{1.67}$ |
| `[0, 0, 0, 0, 0, 0]` | `[]` | 0 | 0 | $\mathbf{0.00}$ |
| `[null, null, 2, null, 0, 1]` | `[2, 1]` | 2 | 3 | $\mathbf{1.50}$ |

---

### Direct Assessment Attainment

Student raw scores are evaluated against a 3-level criterion determined by the baseline threshold $T$ (default $80\%$):

- **Level 3 (High):** Percentage of students scoring $\ge T$ of maximum marks.
- **Level 2 (Moderate):** Percentage of students scoring $\ge (T - 15\%)$ of maximum marks.
- **Level 1 (Low):** Percentage of students scoring $\ge (T - 30\%)$ of maximum marks.

#### Component Blending
- **Old POs:**
  $$\text{Direct Exam Score} = 0.50 \times \text{ISE} + 0.50 \times \text{ESE}$$
  Internal class tests (UT1, UT2, Prelims) are factored into continuous internal evaluation.
- **New POs (Theory):**
  $$\text{Direct CO Score} = (0.75 \times \text{ESE}) + (0.25 \times \text{CCE}_i)$$
  Where $\text{CCE}_i$ corresponds to the specific Continuous Comprehensive Evaluation aligned with $\text{CO}_i$.
- **New POs (Theory with Practical):**
  $$\text{Direct CO Score} = \left(0.75 \times \frac{\text{ESE} + \text{PR}}{2}\right) + (0.25 \times \text{CCE}_i)$$

---

### Indirect Survey Attainment

Course Exit Surveys collect student ratings on a 1 to 3 Likert scale for each Course Outcome. The survey thresholds are offset by $10\%$ from direct thresholds:
- **High Threshold:** $T - 10\%$
- **Mid Threshold:** $(T - 15\%) - 10\%$
- **Low Threshold:** $(T - 30\%) - 10\%$

The computed indirect score per CO is blended into the final PO attainment.

---

### PO and PSO Aggregation and Target Percentage

For standard courses, direct and indirect components are blended at the PO level:

$$\text{Final PO Attainment} = (0.80 \times \text{Direct PO Contribution}) + (0.20 \times \text{Indirect PO Contribution})$$

For Project and Only Practical courses:

$$\text{Final PO Attainment} = 1.00 \times \text{Direct PO Contribution}$$

#### Target Attainment Percentage

$$\text{Attainment Percentage} = \left(\frac{\text{Final PO Attainment}}{\text{PO Mapping Target}}\right) \times 100$$

> **Important Note:** In accordance with institutional guidelines, this display is **not capped at 100%**. Values exceeding 100% are mathematically valid and indicate that student cohort attainment exceeded the mapped department target.

---

### Summary Display Conventions

- **Theory CO Attainment Summary:** Displays a single consolidated row titled **Final CO Attainment**.
- **Visual Styling:** Direct exam scores in this row are highlighted in bold **blue** (`#0056b3`).
- **No Secondary Reductions:** Values are displayed directly without redundant secondary percentage scaling.

---

## CSV Upload Formats and Templates

AttainX expects CSV files with specific column conventions. Sample templates for all formats are located in `public/static/` inside `obe-source.zip`.

### 1. CO-PO Mapping Sheets

- Must contain a row with the cell header `CO Codes` or `CO Code`.
- Subsequent rows list each Course Outcome identifier in the first column (`C301.1`, `C301.2`, etc.).
- Column headers must include `PO1` through `PO12` (or `PO1` through `PO11` for Old POs 11) and `PSO1`, `PSO2`, `PSO3`.
- Correlation values must be integers `1`, `2`, `3`, or `0` / empty for no correlation.

```csv
,DY Patil College of Engineering Akurdi Pune,,,,,,,,,,,,,,
,Department of Instrumentation Engineering,,,,,,,,,,,,,,
,CO-PO & PSO Mapping Matrix,,,,,,,,,,,,,,
CO Codes,Course Outcomes,PO1,PO2,PO3,PO4,PO5,PO6,PO7,PO8,PO9,PO10,PO11,PO12,PSO1,PSO2,PSO3
C410A.1,Understand sensor principles,3,2,1,0,0,1,0,0,1,0,0,2,2,1,0
C410A.2,Design signal conditioning,2,3,2,1,0,0,0,0,0,1,0,1,3,2,1
```

---

### 2. Direct Attainment Marks Sheets

#### Old POs Direct Marks (`direct_template.csv`)
Headers must include `ISE`, `ESE`, `UT1`, `UT2`, and `Prelims`. For courses with practicals, include a `PR` column.

```csv
Sr. No.,Name ,ISE,ESE,UT1,UT2,Prelims
1,Student Name A,24,56,18,19,42
2,Student Name B,22,61,16,17,38
```

#### New POs Direct Marks (`direct_newpos_template.csv`)
Headers must include `ESE` alongside individual CCE columns `CCE1`, `CCE2`, `CCE3`, `CCE4`, `CCE5`.

```csv
,CO ATTAINMENT,,,,,,
,,Extrenal Assessment,Internal Assessment,,,,
Sr. No.,Name ,ESE,CCE1,CCE2,CCE3,CCE4,CCE5
1,Student Name A,78,24,23,25,22,24
2,Student Name B,82,21,22,23,24,25
```

#### Only Practical Marks (`direct_only_practical_template.csv`)
Requires `CCE1` through `CCE5`. `ESE` is optional for continuous-only assessments.

---

### 3. Survey Sheets (Indirect Ratings)

Survey sheets record student ratings on a scale of 1 to 3 for each Course Outcome.

```csv
,Survey for Indirect Attainment Only,,,,,,,
Sr. No.,Name ,C410A.1,C410A.2,C410A.3,C410A.4,C410A.5,C410A.6
1,Student Name A,3,3,2,3,2,3
2,Student Name B,2,3,3,2,3,2
```

---

### Dynamic Survey Template Generator

AttainX includes a dynamic survey template generation engine:

1. **Extraction:** When a faculty member uploads or selects their CO-PO Mapping Sheet, the server extracts the exact list of CO identifiers (e.g. `C301.1`–`C301.6` or custom codes like `ET124ES103.1`–`ET124ES103.4`).
2. **Template Synthesis:** Generates a CSV containing:
   - Line 1: Title header `,Survey for Indirect Attainment Only,...`
   - Line 2: Column headers `Sr. No.,Name ,<CO1>,<CO2>,...`
   - Prepended with a UTF-8 Byte Order Mark (`\ufeff`) to ensure Microsoft Excel correctly preserves column formatting.
3. **Strict Validation:** During calculation, the system verifies that the uploaded survey contains a matching column for every mapped CO. If any mapped CO is missing from the survey, calculation halts with a specific error message (e.g., `Missing survey column for mapped CO: C410A.6`).

---

## Deployment on Vercel

AttainX is configured for deployment on Vercel using the official Python Serverless Runtime.

### Step 1: Connect Repository to Vercel
1. Log in to your [Vercel Dashboard](https://vercel.com/).
2. Click **Add New** $\rightarrow$ **Project**.
3. Import the `AttainX` repository.

### Step 2: Configure Build Settings
- **Framework Preset:** Other
- **Root Directory:** `./` (leave default repository root)
- **Runtime:** Configured automatically by `vercel.json`

### Step 3: Configure Environment Variables
Under **Project Settings** $\rightarrow$ **Environment Variables**, add:

```env
SECRET_KEY = <your-randomly-generated-48-char-secret>
TEACHER_PASSWORD = <institutional-faculty-password>
ADMIN_EMAILS = hod_instrumentation@dypcoeakurdi.ac.in,admin@attainx.com
ADMIN_PASSWORD = <secure-admin-password>
```

### Step 4: Deploy
Click **Deploy**. Vercel will execute the build, bundle `obe-source.zip` alongside `app.py`, and expose the serverless URL.

### Platform Configuration (`vercel.json`)
The repository includes an optimized serverless configuration:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "app.py": {
      "maxDuration": 60,
      "includeFiles": "obe-source.zip"
    }
  }
}
```

- `maxDuration: 60`: Extends execution timeout to 60 seconds for heavy matrix aggregations.
- `includeFiles: "obe-source.zip"`: Guarantees that the bundled core application is packaged with the serverless function.

---

## Troubleshooting

### 1. CSV Encoding Errors (`UnicodeDecodeError: 'utf-8' codec can't decode byte 0x96`)
- **Cause:** Microsoft Excel on Windows saves CSV files using Windows-1252 (CP1252), converting hyphens to en-dashes (`0x96`).
- **Solution:** AttainX features a built-in multi-pass reader trying `utf-8-sig`, `utf-8`, and `cp1252` sequentially. If a custom encoding is used, open the CSV in Excel or VS Code and re-save as **CSV UTF-8 (Comma delimited) (*.csv)**.

### 2. Survey Sheet CO Column Count Mismatch
- **Error:** `The Survey Sheet contains 5 CO columns, but the mapping sheet has 6 COs. Missing survey column for mapped CO: C410A.6.`
- **Cause:** Using a generic 5-CO survey template for a subject mapped to 6 COs.
- **Solution:** Select your CO-PO Mapping Sheet in Step 1, click **📥 Generate Survey Template**, and use the downloaded template to enter student responses.

### 3. Request Entity Too Large (`413 Payload Too Large`)
- **Cause:** Uploaded files exceed the 4 MB total request body ceiling.
- **Solution:** Remove unnecessary graphics or non-student rows from CSV files. Ensure only required marks columns are present.

### 4. Subject Dropdown Not Populating
- **Cause:** JavaScript disabled, or class not selected.
- **Solution:** Ensure a class is selected from the dropdown first. The subject list dynamically updates based on the selected Class and Course Evaluation Type.

### 5. Division by Zero or Blank Target Warnings
- **Cause:** PO columns containing all zeros or non-numeric characters.
- **Solution:** AttainX automatically isolates zero mapping columns and assigns `0.00` target and attainment without crashing. Verify that your CO-PO Mapping Sheet contains intended integer ratings ($1, 2, 3$).

---

## Limitations and Important Notes

- **Ephemeral Storage Architecture:**
  AttainX processes all uploaded CSVs in memory during the HTTP request lifecycle. Uploaded student scores are **not** persisted to an external database. Vercel serverless execution environments are ephemeral; if longitudinal tracking across multiple academic semesters is required, retain the exported PDF reports or raw CSV archives.
- **File Upload Limits:**
  Total request body size is capped at **4 MB**. This provides sufficient headroom for student cohorts up to 500 students while remaining comfortably below Vercel's 4.5 MB platform limit.
- **Excel Compatibility (UTF-8 BOM):**
  All dynamically generated templates include a Byte Order Mark (`\ufeff`). This ensures that Microsoft Excel opens column names with accents or hyphens without character scrambling.
- **Accreditation Disclaimer:**
  AttainX calculation algorithms adhere to standard NBA tier-II engineering criteria. Verification against your institution's specific internal academic audit guidelines is recommended prior to formal SAR (Self Assessment Report) submissions.

---

## License

This project is developed for academic OBE computation and accreditation documentation. Distributed under the institutional terms of the Department of Instrumentation Engineering, DYPCOE Akurdi.
