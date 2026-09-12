# DAS Internship — Project Context

Context pack for the **Development of Secure Applications (DAS)** PBL internship
(3rd-year Software Engineering, Technical University of Moldova).
Team project: 4-week company internship (1–26 September) building the foundation
of a secure-application MVP, continued as a PBL course from October to December.

This folder is meant to be dropped in wholesale as context for future prompts /
agent work on this project (report writing, presentation prep, planning, etc.).
Every subfolder pairs the **original file** (unedited) with a **plain-text /
Markdown extraction** of the same content, so agents that can't open `.docx`,
`.pdf`, or images can still read everything.

## Folder structure

```
DAS_Internship_Context/
├── README.md                                    ← you are here
├── 00_program_overview/
│   └── PBL_ELSE_Platform_Guidelines.md           ← verbatim text pasted by the user (ELSE platform pages):
│                                                    PBL/internship structure, ECTS, free-rider policy,
│                                                    required documentation, submission process,
│                                                    Midterm 1 / Midterm 2 / final evaluation rules
├── 01_official_requirements/
│   ├── DAS_internship_requirements.pdf           ← original faculty PDF (project brief)
│   └── DAS_internship_requirements.md            ← extracted text of the same PDF
│       (project objectives, technical security requirements, September work plan,
│        possible security measures, expected outcomes)
├── 02_report_writing/
│   ├── Internship_Report_writing_guidelines.docx ← original Word template/rules
│   ├── Internship_Report_writing_guidelines.md   ← extracted text (formatting rules,
│       required report sections: Abstract, Introduction, Domain Analysis, System Design,
│       Conclusions, Bibliography, figures/tables/formulas/appendices/references rules)
│   ├── report_evaluation_rubric.png              ← original grading rubric (image/table)
│   └── report_evaluation_rubric.md               ← transcribed rubric table (5 criteria × 2 pts)
├── 03_attendance/
│   ├── Weekly_Attendance_Sheet.docx               ← original weekly attendance template
│   └── Weekly_Attendance_Sheet.md                 ← extracted text
├── 04_curriculum/
│   ├── Curriculum_IS_5_PProd.docx                 ← official university curriculum/syllabus
│   │                                                 for "Practica în producție" (S.O.010), in Romanian
│   └── Curriculum_IS_5_PProd.md                   ← extracted text
├── 05_autumn_internship_instructions/
│   ├── DAS_Internship_instructions_students-f.pdf ← original faculty letter to students
│   └── DAS_Internship_instructions_students.md    ← extracted text
│       (role/responsibility table: contract, weekly reports, log book, company evaluation,
│        Midterm 1 / Midterm 2 / final exam, progress meetings, DAS-internship-vs-PBL
│        distinction, final checklist)
```

## What's in each source, at a glance

| File | Language | Covers |
|---|---|---|
| `00_program_overview/PBL_ELSE_Platform_Guidelines.md` | EN + some RO | Program logistics: schedule, credits, legal basis, free-rider policy, required documents, submission logistics, weekly attendance/activity sheet process, grading breakdown (Midterm 1, Midterm 2, Final) |
| `01_official_requirements/DAS_internship_requirements.*` | EN | The actual **technical project brief**: security objectives, technical requirements (encryption, secure APIs, frontend/backend/DB security), what to do in September, possible security measures, what a finished September deliverable looks like |
| `02_report_writing/Internship_Report_writing_guidelines.*` | EN | Mandatory **report template**: formatting (fonts, margins, spacing), required sections and what goes in each, rules for figures/tables/formulas/appendices/citations (IEEE via Zotero) |
| `02_report_writing/report_evaluation_rubric.*` | EN | The **grading rubric** for the report: 5 criteria (formatting, structure, citations, originality, language), each scored 4–10 |
| `03_attendance/Weekly_Attendance_Sheet.*` | EN | Blank weekly attendance table template (per-day hours online/offline, mentor sign-off) |
| `04_curriculum/Curriculum_IS_5_PProd.*` | RO | Official university syllabus for the internship module (S.O.010, 8 ECTS): objectives, internship logbook (caiet de practică) structure, internship report requirements, evaluation |
| `05_autumn_internship_instructions/DAS_Internship_instructions_students*` | EN | Faculty letter to students: role/responsibility table covering the Internship Contract, Weekly Activity Report, Weekly Attendance Sheet, Log Book, Company Evaluation, Internship Report, Midterm 1, Midterm 2, Final Exam, biweekly progress meetings, and an explicit **DAS Internship vs. PBL** distinction + final checklist |

## Notes for agents using this as context

- The **`.md` files are for reading/reasoning**; the **original `.docx`/`.pdf`/`.png` files are the source of truth** for exact formatting, and are what should actually be filled in/submitted.
- `00_program_overview` is pasted text, kept verbatim exactly as provided — do not treat wording differences from the other official documents as errors; where they overlap, the official PDF/DOCX documents (`01`–`05`) take precedence for formal requirements.
- Key deliverables implied across these files: Internship Contract (2 signed/stamped originals), Internship Log Book (Caiet de practică), Weekly Attendance Sheets, Weekly individual/activity reports, Internship Group Report (formatted per `02_report_writing`), Project presentation (PPT).
- **Known discrepancy, kept as-is (not corrected):** `00_program_overview` and `01_official_requirements` state the internship runs **1–26 September (4 weeks)**, while `05_autumn_internship_instructions` states **"September 01–6" and "7 weeks."** This looks like a typo in the source PDF rather than a real schedule change, but it has not been altered — confirm the actual dates on ELSE before relying on either figure.
- `05_autumn_internship_instructions` also makes explicit that the **DAS Internship Report** and the **later PBL Report** are separate deliverables with separate requirements, even though material can be reused between them.
- Two additional PDFs uploaded alongside `05` (`DAS_internship_project_requirements.pdf` and `..._1_.pdf`) were checked and are byte-identical duplicates of `01_official_requirements/DAS_internship_requirements.pdf` — not added again to avoid redundancy.
