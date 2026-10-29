# Pathwise — Resume & Career Insights

A browser-based resume analyzer and career-guidance demo for students and college placement teams. It uses local rules and a bundled role/skills dataset; it does not call an AI service or upload resume content.

## Requirements

- Node.js 18 or newer
- npm

## Run locally

```bash
npm install
npm run dev
```

Open the local URL printed by Vite. To create a production build, run `npm run build`; to preview it, run `npm run preview`.

## Using the app

- Upload a text-based PDF or DOCX resume or a PNG, JPG, or WebP image (maximum 5 MB), paste an image with **Ctrl+V** while on the student dashboard, paste resume text, or choose **Explore with sample data**.
- Review the resume evidence score, detected skills and their evidence, role matches, skill gaps, free learning resources, and resume improvement suggestions.
- Open **Placement insights** for illustrative sample-cohort metrics and anonymized summaries analyzed in the current browser.

Resume images are read with English OCR in the browser. The first image analysis downloads the OCR worker and English language model; after that they can be reused from the browser cache. Scanned/image-only PDFs are not OCR processed, so upload a page image or paste its text instead. The analyzer recognizes a small, editable vocabulary of skills and common section headings; it does not infer a qualification merely because a role recommends it.

## How scoring works

The score is an evidence checklist, not a hiring prediction:

| Category | Weight |
| --- | ---: |
| Skills evidence | 30 |
| Education | 15 |
| Projects | 25 |
| Experience | 15 |
| Certifications | 10 |
| Resume structure | 5 |

Section scores use detected headings and basic text patterns. A missing section receives zero in that category; this does not mean the student lacks the underlying qualification. Skill scores reflect whether a listed skill appears in a skills section, a project/experience context, or alongside a measurable result. Role matches are calculated from the overlap between these detected skills and each role's local requirements. These rules are intentionally transparent and are not a validation of actual proficiency.

## Privacy and limitations

PDF/DOCX extraction, image OCR, and analysis run in the browser. Image OCR needs an internet connection the first time to download its worker and English language model; the image itself is not uploaded. The app does not send resume content to an analysis server. The placement view stores only a limited set of anonymized score, role, and detected-skill summaries in this browser's `localStorage`; no name, contact detail, or source resume text is saved. The initial placement cohort is explicitly illustrative sample data. This prototype is not a student-information system and should not be used to make automated hiring or student-selection decisions.

The free resource links point to external learning sites and require an internet connection when opened. The interface uses system sans-serif fonts and does not request remote font files.
