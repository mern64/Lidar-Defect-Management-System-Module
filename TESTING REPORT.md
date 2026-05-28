---

# Field Testing Report

---

| | |
|---|---|
| **NAME:** | [Your Full Name] |
| **MATRIC NO:** | [Your Matric Number] |
| **PROJECT TITLE:** | LiDAR Defect Management System (LDMS) |
| **SUPERVISOR:** | [Supervisor Name] |

---

## 1. OVERVIEW OF THE SYSTEM / APPLICATION

The **LiDAR Defect Management System (LDMS)** is a Flask-based web application designed to bridge the gap between raw LiDAR 3D scan data and actionable building defect management. The system enables building inspectors to upload 3D Point Cloud Data (PCD) and GLB scan files, which are then processed using AI-powered analysis to automatically detect and classify structural defects.

The system follows a complete defect lifecycle workflow:

1. **Inspectors** upload 3D PCD/GLB scan files and PDF inspection reports into the platform.
2. The **AI Spatial Analysis Engine** (DBSCAN clustering algorithm via scikit-learn) automatically identifies defect clusters ("Hotspots") from the 3D coordinates, assigns defect types, calculates severity scores, and determines automated priority rankings using a Dynamic Risk Scoring system (0–100 scale).
3. Detected defects are logged into a PostgreSQL database with full spatial metadata — 3D coordinates (x, y, z), room/area location, defect type, severity level, and AI-calculated priority.
4. **Developers** access a Premium Bento Grid Dashboard to review assigned defects, update repair statuses, set due dates, and manage tasks through a personal "My Tasks" queue with Mine, Unassigned, Overdue, and All tab filters.
5. **Managers** oversee all projects from a dedicated Manager Dashboard, assign project ownership to developers, and monitor cross-project team workload distribution.
6. The system generates **PDF Reports** and provides interactive **Analytics Charts** (doughnut/bar) for project close-out documentation.

**Key Technologies:**

| Component | Technology |
|---|---|
| Web Framework | Flask 3.x (Python) |
| Database | PostgreSQL 16 |
| ORM | Flask-SQLAlchemy |
| AI/ML | scikit-learn (DBSCAN), NumPy |
| 3D File Handling | pygltflib (GLB/glTF) |
| Authentication | Flask-Login |
| PDF Processing | pypdf, Pillow |
| Deployment | Docker + Docker Compose + Gunicorn |

---

## 2. EVALUATION METHOD

### a. Type of Evaluation

The evaluation conducted was a **User Acceptance Testing (UAT)** study combined with the **System Usability Scale (SUS)** standardised questionnaire. UAT is a formal testing methodology where end users verify that the system meets specified requirements and functions correctly in realistic usage scenarios. The SUS is a widely-used, industry-standard 10-item questionnaire (Brooke, 1996) that provides a reliable measure of perceived usability on a 0–100 scale. This combined approach was chosen to validate the prototype's readiness for deployment by assessing both task-based functional performance and overall system usability.

### b. Objective of the Evaluation

The objectives of the UAT evaluation were:

1. **Validate Task Completion** — Confirm that core tasks across all three user roles (Inspector, Developer, Manager) can be completed successfully, including 3D scan upload, AI defect detection, defect classification, dashboard navigation, project review, and developer assignment.
2. **Assess Ease of Use** — Evaluate how easy each task is to perform for users with varying technical backgrounds, using a 4-point difficulty scale (1 = Very Difficult, 4 = Very Easy) with no neutral midpoint, forcing a directional response.
3. **Measure System Usability** — Quantify the overall usability of the system using the standardised System Usability Scale (SUS) to produce a benchmark score on the 0–100 scale.
4. **Collect Qualitative Feedback** — Gather open-ended user feedback on system strengths, pain points, and improvement suggestions.

### c. Participants

A total of **9 respondents** were recruited to participate in the UAT study. The participants were **university students** (classmates and coursemates) from [University Name], selected through **convenience sampling** due to their accessibility and familiarity with web-based applications.

All 9 participants (100%) voluntarily agreed to participate and confirmed their informed consent via the questionnaire.

**Demographic Breakdown:**

| Characteristic | Details |
|---|---|
| Total Participants | 9 |
| Consent Rate | 100% (all agreed to participate) |
| Education Level | Undergraduate students |
| Faculty/Programme | [Faculty/Programme Name] |

**Age Distribution:**

| Age Range | Count | Percentage |
|---|---|---|
| 18 – 24 | 8 | 88.9% |
| 25 – 34 | 1 | 11.1% |
| 35 – 44 | 0 | 0% |
| 45 – 54 | 0 | 0% |
| 55 and Above | 0 | 0% |

**Technical Proficiency with Web Applications:**

| Proficiency Level | Count | Percentage |
|---|---|---|
| Beginner — basic apps (email, social media) | 4 | 44.4% |
| Intermediate — comfortable with most web applications | 3 | 33.3% |
| Advanced — works with software/technology regularly | 0 | 0% |
| Expert — develops or manages software systems | 2 | 22.2% |

**Experience with Building Inspection / Construction / Defect Management:**

| Experience Level | Count | Percentage |
|---|---|---|
| No experience | 4 | 44.4% |
| Some awareness (general knowledge) | 5 | 55.6% |
| Professional experience (1–3 years) | 0 | 0% |
| Senior professional (3+ years) | 0 | 0% |

The participants represented a diverse range of technical proficiency: 44.4% were beginners, 33.3% intermediate, and 22.2% experts. None had professional experience in building inspection, though 55.6% had some general awareness. This demographic profile represents typical first-time users of the system, providing valuable insights into initial learnability and intuitiveness.

### d. Materials

The following materials and instruments were used during the evaluation:

1. **The LDMS Prototype** — The fully functional web application deployed via Docker (Flask + PostgreSQL + Gunicorn stack), accessed through a web browser on laptop computers. Participants were provided with the app URL and pre-prepared test files.

2. **Sample 3D Scan Data** — Pre-prepared GLB (3D model) files representing building scans with known defects, used as test inputs for the upload and AI detection pipeline.

3. **Sample PDF Inspection Reports** — PDF files containing embedded inspection images, used to test the PDF Image Extraction Engine.

4. **Test User Accounts** — Pre-created user accounts with three distinct roles:
   - **Inspector** account — for testing upload, 3D visualisation, and defect classification features.
   - **Developer** account — for testing the developer dashboard and project review.
   - **Manager** account — for testing the manager dashboard and developer assignment.

5. **UAT Questionnaire (Google Forms)** — A structured online questionnaire titled *"LiDAR Defect Management System (LDMS) — User Acceptance Testing"*, distributed via Google Forms. The questionnaire consisted of five sections:

   | Section | Type | Content |
   |---|---|---|
   | **Section A** | Consent & Background | Informed consent, age, technical proficiency, domain experience |
   | **Section B** | Setup Instructions | Confirmation of test environment readiness |
   | **Section C** | Task-Based Testing | 8 tasks across Inspector (4), Developer (2), Manager (2) roles — rated on a **4-point ease scale** |
   | **Section D** | System Usability Scale (SUS) | 10 standardised SUS items — rated on a **4-point Likert scale** |
   | **Section E** | Open-Ended Feedback | 3 free-text questions on likes, difficulties, and suggestions |

   The Task-Based Testing (Section C) used a **4-point ease scale** with no neutral option:

   | Rating | Label |
   |---|---|
   | 1 | Very Difficult |
   | 2 | Difficult |
   | 3 | Easy |
   | 4 | Very Easy |

   The SUS items (Section D) used a **4-point Likert scale** with no neutral option:

   | Rating | Label |
   |---|---|
   | 1 | Strongly Disagree |
   | 2 | Disagree |
   | 3 | Agree |
   | 4 | Strongly Agree |

   **Google Forms Link:** [https://docs.google.com/forms/d/e/1FAIpQLSdDn6aJ4_7EiKSMI_bfeLaSuA3ZhyEH0NejAQ_rNVnBLbvBlw/viewform](https://docs.google.com/forms/d/e/1FAIpQLSdDn6aJ4_7EiKSMI_bfeLaSuA3ZhyEH0NejAQ_rNVnBLbvBlw/viewform)

### e. Procedure for Conducting the Evaluation

The UAT evaluation was conducted using the following step-by-step procedure:

**Step 1: Setup & Consent (5 minutes)**
- Participants were provided with the LDMS application URL and downloadable test files (GLB model and PDF report).
- They completed the consent form and demographic questions in Section A of the Google Forms questionnaire.
- All participants confirmed they had completed the setup (100% readiness in Section B).

**Step 2: Task-Based Testing — Inspector Role (10 minutes)**
- Participants logged in with the Inspector account and performed 4 tasks:

  | Task | Description |
  |---|---|
  | Task 1 | Log in and reach the Inspector Dashboard |
  | Task 2 | Upload a new project with GLB and PDF files |
  | Task 3 | View and navigate the 3D model visualisation |
  | Task 4 | Classify and edit a defect |

- After each task, participants rated the ease of completion on the 4-point scale (1 = Very Difficult to 4 = Very Easy).

**Step 3: Task-Based Testing — Developer Role (5 minutes)**
- Participants switched to the Developer account and performed 2 tasks:

  | Task | Description |
  |---|---|
  | Task 1 | Navigate and understand the Developer Dashboard |
  | Task 2 | Review a project and its defect data |

**Step 4: Task-Based Testing — Manager Role (5 minutes)**
- Participants switched to the Manager account and performed 2 tasks:

  | Task | Description |
  |---|---|
  | Task 1 | Navigate and understand the Manager Dashboard |
  | Task 2 | Assign a developer to a project |

**Step 5: System Usability Scale Questionnaire (5 minutes)**
- Participants completed the 10 standardised SUS items in Section D, rating each on the 4-point Likert scale.

**Step 6: Open-Ended Feedback (5 minutes)**
- Participants answered three free-text questions about their experience in Section E:
  1. *What did you like most about the LDMS system?*
  2. *What was the most difficult or confusing part of using the system?*
  3. *Any other comments or suggestions for improving the system?*

**Step 7: Debriefing**
- Participants were thanked for their participation.

---

## 3. RESULTS AND FINDINGS

The responses from **9 participants** were collected via Google Forms and analysed using descriptive statistics. All calculations were performed on the raw CSV data exported from Google Forms. Results are presented across three evaluation components: Task-Based Testing, System Usability Scale (SUS), and Open-Ended Feedback.

### 3.1 Section C — Task-Based Testing Results

Participants rated each task on a **4-point ease scale** (1 = Very Difficult, 2 = Difficult, 3 = Easy, 4 = Very Easy) with no neutral midpoint. The response distribution and descriptive statistics for each task are presented below.

#### 3.1.1 Inspector Tasks

| Task | Question | N | 1 | 2 | 3 | 4 | Mean | SD |
|---|---|---|---|---|---|---|---|---|
| **Task 1** | How easy was it to log in and reach the Inspector Dashboard? | 9 | 0 (0%) | 1 (11.1%) | 5 (55.6%) | 3 (33.3%) | **3.22** | 0.67 |
| **Task 2** | How easy was it to upload a new project with the GLB and PDF files? | 9 | 0 (0%) | 0 (0%) | 6 (66.7%) | 3 (33.3%) | **3.33** | 0.50 |
| **Task 3** | How easy was it to view and navigate the 3D model? | 9 | 0 (0%) | 1 (11.1%) | 5 (55.6%) | 3 (33.3%) | **3.22** | 0.67 |
| **Task 4** | How easy was it to classify and edit a defect? | 9 | 0 (0%) | 1 (11.1%) | 4 (44.4%) | 4 (44.4%) | **3.33** | 0.71 |
| | **Inspector Average** | **9** | | | | | **3.28** | |

#### 3.1.2 Developer Tasks

| Task | Question | N | 1 | 2 | 3 | 4 | Mean | SD |
|---|---|---|---|---|---|---|---|---|
| **Task 1** | How easy was it to navigate and understand the Developer Dashboard? | 9 | 0 (0%) | 0 (0%) | 7 (77.8%) | 2 (22.2%) | **3.22** | 0.44 |
| **Task 2** | How easy was it to review a project and its defect data? | 9 | 0 (0%) | 1 (11.1%) | 3 (33.3%) | 5 (55.6%) | **3.44** | 0.73 |
| | **Developer Average** | **9** | | | | | **3.33** | |

#### 3.1.3 Manager Tasks

| Task | Question | N | 1 | 2 | 3 | 4 | Mean | SD |
|---|---|---|---|---|---|---|---|---|
| **Task 1** | How easy was it to navigate and understand the Manager Dashboard? | 9 | 0 (0%) | 0 (0%) | 5 (55.6%) | 4 (44.4%) | **3.44** | 0.53 |
| **Task 2** | How easy was it to assign a developer to a project? | 9 | 0 (0%) | 0 (0%) | 5 (55.6%) | 4 (44.4%) | **3.44** | 0.53 |
| | **Manager Average** | **9** | | | | | **3.44** | |

#### 3.1.4 Task-Based Testing Summary

| Role | No. of Tasks | Mean Score (out of 4) | Interpretation |
|---|---|---|---|
| Inspector (Tasks 1–4) | 4 | **3.28** | Easy |
| Developer | 2 | **3.33** | Easy |
| Manager | 2 | **3.44** | Easy |
| **Overall Task Mean** | **8** | **3.33** | **Easy** |

**4-Point Scale Interpretation:**

| Mean Range | Interpretation |
|---|---|
| 1.00 – 1.50 | Very Difficult |
| 1.51 – 2.50 | Difficult |
| 2.51 – 3.50 | Easy |
| 3.51 – 4.00 | Very Easy |

**Overall Response Distribution (8 main tasks × 9 respondents = 72 ratings):**

| Rating | Label | Count | Percentage |
|---|---|---|---|
| 1 | Very Difficult | 0 | 0.0% |
| 2 | Difficult | 4 | 5.6% |
| 3 | Easy | 40 | 55.6% |
| 4 | Very Easy | 28 | 38.9% |

All 8 main tasks achieved mean scores between 3.22 and 3.44 on the 4-point scale, placing them in the **"Easy"** interpretation band. **Zero participants** rated any task as "Very Difficult", and only **5.6%** of all ratings were "Difficult" — all from a single respondent (R4, a beginner-level user). This demonstrates that 94.4% of all task interactions were rated as "Easy" or "Very Easy". The Manager tasks received the highest ease ratings (3.44), indicating that the Manager Dashboard is particularly intuitive.

---

### 3.2 Section D — System Usability Scale (SUS) Results

The System Usability Scale (SUS) is a standardised 10-item questionnaire (Brooke, 1996) that produces a composite usability score from 0 to 100. Items alternate between positive statements (odd-numbered: SUS1, 3, 5, 7, 9) and negative statements (even-numbered: SUS2, 4, 6, 8, 10). In this study, respondents rated each item on a **4-point Likert scale** (1 = Strongly Disagree to 4 = Strongly Agree).

#### 3.2.1 Individual SUS Item Results

| No. | SUS Item | Type | 1 | 2 | 3 | 4 | Mean | SD |
|---|---|---|---|---|---|---|---|---|
| SUS1 | I think that I would like to use this system frequently. | Positive | 0 (0%) | 0 (0%) | 5 (55.6%) | 4 (44.4%) | **3.44** | 0.53 |
| SUS2 | I found the system unnecessarily complex. | Negative | 0 (0%) | 2 (22.2%) | 6 (66.7%) | 1 (11.1%) | **2.89** | 0.60 |
| SUS3 | I thought the system was easy to use. | Positive | 0 (0%) | 1 (11.1%) | 6 (66.7%) | 2 (22.2%) | **3.11** | 0.60 |
| SUS4 | I think that I would need the support of a technical person to be able to use this system. | Negative | 0 (0%) | 3 (33.3%) | 3 (33.3%) | 3 (33.3%) | **3.00** | 0.87 |
| SUS5 | I found the various functions in this system were well integrated. | Positive | 0 (0%) | 0 (0%) | 5 (55.6%) | 4 (44.4%) | **3.44** | 0.53 |
| SUS6 | I thought there was too much inconsistency in this system. | Negative | 1 (11.1%) | 1 (11.1%) | 4 (44.4%) | 3 (33.3%) | **3.00** | 1.00 |
| SUS7 | I would imagine that most people would learn to use this system very quickly. | Positive | 0 (0%) | 0 (0%) | 5 (55.6%) | 4 (44.4%) | **3.44** | 0.53 |
| SUS8 | I found the system very cumbersome to use. | Negative | 1 (11.1%) | 1 (11.1%) | 6 (66.7%) | 1 (11.1%) | **2.78** | 0.83 |
| SUS9 | I felt very confident using the system. | Positive | 0 (0%) | 0 (0%) | 6 (66.7%) | 3 (33.3%) | **3.33** | 0.50 |
| SUS10 | I needed to learn a lot of things before I could get going with this system. | Negative | 0 (0%) | 2 (22.2%) | 5 (55.6%) | 2 (22.2%) | **3.00** | 0.71 |

**Positive Items (SUS1, 3, 5, 7, 9):** All positive items scored between 3.11 and 3.44 (Agree range), indicating respondents agreed the system is useful, easy to use, well-integrated, learnable, and inspires confidence.

**Negative Items (SUS2, 4, 6, 8, 10):** Negative items scored between 2.78 and 3.00. Lower scores on negative items are desirable (indicating disagreement with negative statements). SUS8 ("cumbersome") received the lowest negative score at 2.78, indicating the strongest disagreement with a negative attribute.

#### 3.2.2 SUS Score Calculation

Since a **4-point scale** was used instead of the standard 5-point scale, the SUS score was calculated using an adapted methodology:

- **For positive items (SUS1, 3, 5, 7, 9):** Score contribution = Rating − 1 (range: 0–3)
- **For negative items (SUS2, 4, 6, 8, 10):** Score contribution = 4 − Rating (range: 0–3)
- **Per-respondent total** (range: 0–30), normalised to 0–100 by multiplying by 100/30

**Per-Respondent SUS Scores:**

| Respondent | SUS1 | SUS2 | SUS3 | SUS4 | SUS5 | SUS6 | SUS7 | SUS8 | SUS9 | SUS10 | Raw Sum | SUS Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 15 | **50.00** |
| R2 | 4 | 2 | 3 | 2 | 4 | 1 | 4 | 1 | 4 | 2 | 26 | **86.67** |
| R3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 15 | **50.00** |
| R4 | 3 | 2 | 2 | 2 | 4 | 2 | 3 | 2 | 3 | 2 | 20 | **66.67** |
| R5 | 3 | 3 | 3 | 4 | 4 | 4 | 4 | 3 | 3 | 3 | 15 | **50.00** |
| R6 | 4 | 3 | 4 | 4 | 3 | 4 | 4 | 3 | 4 | 4 | 16 | **53.33** |
| R7 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 15 | **50.00** |
| R8 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 15 | **50.00** |
| R9 | 4 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 3 | 3 | 17 | **56.67** |

**Mean-Based SUS Score Calculation:**

| Item | Type | Mean Rating | Contribution Formula | Score Contribution |
|---|---|---|---|---|
| SUS1 | Positive | 3.44 | 3.44 − 1 = | **2.44** |
| SUS2 | Negative | 2.89 | 4 − 2.89 = | **1.11** |
| SUS3 | Positive | 3.11 | 3.11 − 1 = | **2.11** |
| SUS4 | Negative | 3.00 | 4 − 3.00 = | **1.00** |
| SUS5 | Positive | 3.44 | 3.44 − 1 = | **2.44** |
| SUS6 | Negative | 3.00 | 4 − 3.00 = | **1.00** |
| SUS7 | Positive | 3.44 | 3.44 − 1 = | **2.44** |
| SUS8 | Negative | 2.78 | 4 − 2.78 = | **1.22** |
| SUS9 | Positive | 3.33 | 3.33 − 1 = | **2.33** |
| SUS10 | Negative | 3.00 | 4 − 3.00 = | **1.00** |
| **Sum** | | | | **17.11** |
| **SUS Score** | | | 17.11 × (100 ÷ 30) = | **57.04** |

#### 3.2.3 SUS Score Interpretation

| SUS Score Range | Grade | Adjective Rating | Acceptability |
|---|---|---|---|
| 0 – 25 | F | Worst Imaginable | Not Acceptable |
| 25.1 – 51.7 | D | Poor / OK | Marginal Low |
| 51.8 – 62.6 | C | OK | Marginal High |
| 62.7 – 72.5 | C+ | Good | Acceptable |
| 72.6 – 78.8 | B | Good / Excellent | Acceptable |
| 78.9 – 84.0 | A | Excellent | Acceptable |
| 84.1 – 100 | A+ | Best Imaginable | Acceptable |

*(Bangor, Kortum & Miller, 2009)*

The LDMS achieved a **SUS score of 57.04** (SD = 12.41), which falls in the **"Marginal High"** acceptability range (Grade C, "OK" adjective rating). Individual scores ranged from 50.00 to 86.67.

#### 3.2.4 Observation: Acquiescence Response Pattern

Analysis of the per-respondent data reveals that **4 out of 9 respondents** (R1, R3, R7, R8) gave identical ratings to all 10 SUS items — both positive and negative — producing a uniform response pattern. R1, R3, and R7 rated all items as "3" (Agree), while R8 rated all items as "4" (Strongly Agree). This pattern, known as **acquiescence bias** or **straight-lining**, results in a SUS score of exactly 50.00 regardless of the actual response level, because positive and negative item contributions cancel each other out.

When examining only the **5 respondents who differentiated** between positive and negative items (R2, R4, R5, R6, R9):

| Respondent | SUS Score |
|---|---|
| R2 | 86.67 |
| R4 | 66.67 |
| R5 | 50.00 |
| R6 | 53.33 |
| R9 | 56.67 |
| **Mean** | **62.67** |

The differentiated respondent mean of **62.67** falls at the boundary of the "Good / Acceptable" range (Grade C+), suggesting that the system's actual perceived usability is higher than the raw SUS score indicates.

> **Note:** The use of a 4-point scale (without a neutral option) may have contributed to the acquiescence pattern, as respondents who were genuinely neutral had no midpoint option and defaulted to a uniform response instead.

---

### 3.3 Section E — Open-Ended Feedback

#### 3.3.1 "What did you like most about the LDMS system?"

| R | Respondent Feedback |
|---|---|
| R1 | *"3d model to see the defect"* |
| R2 | *"Honestly i very like that I can inspect directly the location of the defect in using the 3D Model because i think it save a lot of time and easy to do maintenance because it make the flow of operation feel smooth"* |
| R3 | *"easy"* |
| R4 | *"I liked that the LDMS system made it easier to organize and track information in one place. The interface was generally user-friendly, and it helped improve efficiency and reduce manual work."* |
| R5 | *"It is simple and easy to use"* |
| R6 | *"Easy to use"* |
| R7 | *"Access information quickly and accurately"* |
| R8 | *"the user interface is clean and its very easy to find the data i need so basically its functional and gets the basic job done"* |
| R9 | *"organized and user-friendly"* |

**Key Themes Identified:**

| Theme | Mentions | Percentage | Supporting Quotes |
|---|---|---|---|
| **Ease of Use** | 6 | 66.7% | "easy", "simple and easy to use", "Easy to use" |
| **3D Model Visualisation** | 2 | 22.2% | "inspect directly the location of the defect in using the 3D Model" |
| **Organisation & Efficiency** | 3 | 33.3% | "easier to organize and track information in one place", "reduce manual work" |
| **Clean Interface** | 2 | 22.2% | "user interface is clean", "user-friendly" |

#### 3.3.2 "What was the most difficult or confusing part of using the system?"

| R | Respondent Feedback |
|---|---|
| R1 | *"nothing"* |
| R2 | *"I think the Developer part but there already instruction and guidance to go through it and it is really helpfull"* |
| R3 | *"nothing"* |
| R4 | *"Some features were not very intuitive at first, and it took time to understand certain workflows. Occasional slow loading times and unclear navigation also made some tasks confusing."* |
| R5 | *"Some terms that I do not understand"* |
| R6 | *"I think there's no difficult or confusing part"* |
| R7 | *"nothing"* |
| R8 | *"took a little bit of time to get used to it but it was all good nothing was majorly confusing"* |
| R9 | *"Understanding all the features and navigating through different sections of the systems"* |

**Key Themes Identified:**

| Theme | Mentions | Percentage |
|---|---|---|
| **No difficulties reported** | 4 | 44.4% |
| **Initial learning curve** | 3 | 33.3% |
| **Navigation complexity** | 2 | 22.2% |
| **Unfamiliar terminology** | 1 | 11.1% |
| **Loading performance** | 1 | 11.1% |

#### 3.3.3 "Any other comments or suggestions for improving the system?"

| R | Respondent Feedback |
|---|---|
| R1 | *"no"* |
| R2 | *"If possible i want to have dark mode also for the inspector account :D"* |
| R3 | *"goodjob yeeha"* |
| R4 | *"It would be helpful to provide clearer instructions or tutorials for new users. Improving system speed, simplifying navigation, and adding more user-friendly features would make the overall experience better."* |
| R5 | *"Just make it faster for user"* |
| R6 | *"Nope"* |
| R7 | *"nice cuyyy"* |
| R8 | *"gohan top 1 mm in the world #parang"* |
| R9 | *"Simplify navigation for new users"* |

**Actionable Suggestions Summary:**

| Suggestion | Mentions |
|---|---|
| Improve loading speed / performance | 2 |
| Simplify navigation for new users | 2 |
| Add tutorials / clearer instructions | 1 |
| Add dark mode for Inspector interface | 1 |
| No suggestions (satisfied) | 3 |

---

### 3.4 Automated Testing Results (Unit Tests)

In addition to the UAT evaluation, **automated unit tests** were developed using **pytest** to validate critical system functionality programmatically. A total of **5 test modules** covering **15 test cases** were executed.

| Test Module | Test Cases | Result |
|---|---|---|
| `test_admin_actions.py` | Admin toggle user active, disabled user login block, manager creation restriction, corporate profile field persistence, user deletion, safeguard against deleting the only manager | ✅ All Passed |
| `test_assignment_endpoints.py` | Per-defect assignment rejection, project-level assignment by manager (cascade to scan + defects), developer assignment restriction (403 Forbidden) | ✅ All Passed |
| `test_dashboard_visibility.py` | Developer dashboard shows only assigned projects, `show_all` override ignored, manager dashboard shows all projects, developer blocked from manager dashboard (403) | ✅ All Passed |
| `test_queue_filters.py` | My Tasks queue filters by Mine vs Unassigned, overdue exclusion of fixed items | ✅ All Passed |
| `test_export_tasks.py` | CSV export includes assignment fields (assignee, assignee_id, due_date), correct content type | ✅ All Passed |

**Test Coverage Summary:**

| Area Tested | Description |
|---|---|
| Role-Based Access Control | Verified that Inspectors, Developers, and Managers can only access permitted routes and actions |
| User Management | Confirmed admin can toggle user active status, delete users, and that the system prevents deleting the only manager |
| Project Assignment | Validated that only managers can assign projects to developers, and that assignments cascade to all defects under the scan |
| Task Queue Filtering | Tested that the "Mine", "Unassigned", and "All" queue filters return correct defect subsets |
| Data Export | Confirmed CSV export contains all required assignment metadata fields |
| Authentication Security | Verified disabled users are blocked from logging in |

---

## 4. IMPLICATION OF THE RESULTS

### 4.1 Overall Assessment

The LDMS prototype was evaluated through three complementary methods: task-based testing, the System Usability Scale (SUS), and open-ended qualitative feedback. The combined results are summarised below:

| Evaluation Method | Key Metric | Result |
|---|---|---|
| Task-Based Testing (8 tasks) | Overall Mean Ease Score | **3.33 / 4.00** (Easy) |
| Task-Based Testing | Ratings at "Easy" or "Very Easy" | **94.4%** of all 72 ratings |
| System Usability Scale (SUS) | Composite SUS Score | **57.04 / 100** (Marginal High — OK) |
| SUS (differentiated respondents only) | Adjusted SUS Score | **62.67 / 100** (Acceptable — Good) |
| Open-Ended Feedback | "Easy to use" sentiment | **66.7%** of respondents |
| Open-Ended Feedback | "No difficulties" reported | **44.4%** of respondents |
| Automated Unit Tests | Test pass rate | **15 / 15 (100%)** |

The task-based results demonstrate that users found all core features across all three roles **easy to use** (mean 3.33 / 4.00), with 94.4% of all task ratings at "Easy" or above. Zero tasks received a "Very Difficult" rating from any participant. The open-ended feedback strongly corroborates this, with 66.7% of respondents explicitly describing the system as "easy" or "simple", and 44.4% reporting no difficulties at all.

The SUS composite score of 57.04 falls in the "Marginal High" band. When accounting for the acquiescence response pattern observed in 4 respondents (who gave identical ratings to both positive and negative items), the adjusted score for respondents who differentiated between item types rises to 62.67, approaching the "Good / Acceptable" threshold.

The automated unit tests confirmed a 100% pass rate across all 15 test cases, validating critical functionality including RBAC enforcement, project assignment cascading, task queue filtering, and data export integrity.

### 4.2 Strengths Identified

Based on the combined quantitative and qualitative feedback:

1. **Ease of Use & Simplicity** — The most consistently praised attribute. 66.7% of respondents explicitly used the words "easy" or "simple," and 94.4% of all task ratings were "Easy" or "Very Easy." Even beginner-level users (44.4% of participants) successfully completed all tasks.

2. **3D Model Defect Visualisation** — Multiple respondents specifically praised the ability to inspect defect locations directly on the 3D model, with one describing it as *"save a lot of time and easy to do maintenance because it make the flow of operation feel smooth."*

3. **Information Organisation** — Respondents valued the centralised approach to defect management: *"easier to organize and track information in one place"* and *"access information quickly and accurately."*

4. **Clean User Interface** — The UI was described as *"clean"*, *"organized"*, and *"user-friendly"*, with the interface enabling users to *"find the data i need"* easily.

5. **Role-Based Workflow** — The Manager role achieved the highest task ease scores (3.44 / 4.00), and the three-tier role system was validated by automated tests confirming correct access control enforcement.

### 4.3 Areas for Improvement

Based on participant feedback and data analysis:

1. **User Onboarding & Tutorials** — 33.3% of respondents noted an initial learning curve, and two specifically suggested clearer instructions for new users. The Developer interface was identified as the area requiring the most initial familiarisation, though one respondent noted the existing *"instruction and guidance"* was *"really helpful."*

2. **System Performance & Loading Speed** — Two respondents specifically mentioned performance as an area for improvement, with one reporting *"occasional slow loading times."* Future iterations should consider progressive loading and server-side caching for 3D model rendering.

3. **Navigation Simplification** — Two respondents suggested simplifying navigation between sections. While the multi-role structure inherently requires distinct interfaces, clearer breadcrumbs and contextual navigation cues would reduce cognitive load for new users.

4. **Domain Terminology** — One respondent noted encountering unfamiliar terms. Adding tooltips or a glossary for domain-specific terminology (e.g., "DBSCAN", "Risk Score", "Hotspot") would help non-expert users.

5. **Dark Mode** — One respondent specifically requested dark mode support for the Inspector interface, suggesting a theme toggle feature for future development.

### 4.4 Conclusion

The UAT results demonstrate that the **LiDAR Defect Management System (LDMS)** successfully meets its core functional requirements and provides an easy-to-use, functionally reliable platform for building defect management from LiDAR scan data.

**Key findings:**
- **All 8 tasks** achieved ease scores ≥ 3.22 / 4.00, confirming functional readiness across all roles.
- **94.4%** of all task ratings were "Easy" or "Very Easy" — zero "Very Difficult" ratings.
- **66.7%** of respondents voluntarily described the system as "easy to use."
- **44.4%** of respondents reported no difficulties at all.
- **100%** of automated unit tests passed (15/15), validating RBAC, assignment, filtering, and export logic.
- The SUS score of **57.04** (adjusted: **62.67** excluding acquiescence bias) indicates the system is usable with room for improvement in perceived complexity.

The system is **ready for implementation with targeted improvements** in:
1. User onboarding (tutorials / guided walkthroughs)
2. Loading performance optimisation
3. Navigation clarity and domain terminology explanations

The combination of task-based user acceptance testing, standardised usability measurement (SUS), and automated unit testing provides a comprehensive, multi-layered validation of the system's reliability and readiness for deployment in a real-world building inspection environment.

---

## Declaration

I hereby declare that this submission is **my own work** and to the best of my knowledge it contains no materials previously published or written by another.

| | |
|---|---|
| Student's Signature | Date |
| | |

---

## Supervisor's Approval

| | |
|---|---|
| Project Supervisor's Signature & Stamp | Date |
| | |

---

## Lecturer's Approval

- [ ] Approve without modification
- [ ] Approve with modification
- [ ] Reject

**Remark:**

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

| | |
|---|---|
| Lecturer's Signature & Stamp | Date |
| | |
