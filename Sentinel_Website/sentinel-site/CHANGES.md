# Website update summary

## New information architecture (home page, one continuous story)
1. Hero: "The pipeline can be green while the data is wrong." with Watch Demo / View GitHub
2. Executive snapshot: what it is, what it monitors, what it detects, why it matters, stack
3. Why data quality matters: one short fictional (Aisha) block
4. The data: Patient / Encounter / Observation in plain language, one FHIR sentence
5. Security is not data quality
6. Why the business cares: downstream uses, without vs with Sentinel, four values
7. Sentinel in action: tabbed Monitor / Detect / Investigate / Track with real screenshots
8. Demo video
9. What Sentinel checks: five human questions, technical method behind "Technical details"
10. How it is engineered: final architecture diagram, three short paragraphs, optional "Engineering details"
11. Scope: today / next, prototype statement
12. Team with one contribution line each
13. Final CTA

## Removed from the home page
Ownership-gap section, "How we prove it" counters (114,303 rows / 229 windows / 0 violations), the 9-screenshot episode grid, state rail, four icon cards for the journey, decorative detector visualisations, separate engineering-details list, multiple CTAs.

## Rewritten
Hero, problem framing, business value, product journey, detector descriptions, architecture section, scope, team, final CTA, Case Study page (architecture, detector and experiment text, next steps), Team page (contribution line, link rel).

## Files modified
src/data/site.ts, src/pages/HomePage.tsx, src/pages/CaseStudyPage.tsx, src/pages/TeamPage.tsx, src/components/DemoVideo.tsx, src/main.tsx, README.md, public/assets/demo/*

## Files created
src/data/content.ts, src/refine.css, src/components/ProductJourney.tsx, src/components/ArchitectureFigure.tsx, public/assets/architecture/sentinel-architecture-final.webp, CHANGES.md

## Files deleted
src/components/ThemedImage.tsx, src/components/CountUp.tsx (no longer used)

## Left out on purpose
KS / Jensen-Shannon / MAD detail beyond the expandable "Technical details"; the use-case ecosystem diagram, system-context diagram, incident-lifecycle diagram and the report's tables; the full Aisha sequence diagram; the five-row results table (summarised in one sentence).

## Unsupported or conflicting items found
- Removed counters 114,303 rows / 229 windows / 0 violations and the 10,580 -> ~2,600 volume-experiment figures: not in the final case study.
- Removed "one-week capstone", "hysteresis & cooldowns", "long-term trends", "wider field coverage", "additional failure types" and any diagnoses/medications roadmap: not in the final case study.
- Docker: the case-study diagram draws "Runs in Docker" around Source through Serve. The repository's compose file, as seen earlier, runs only Kafka and PostgreSQL. The site lists Docker in the stack and does not state which components run in it; please confirm against the repo.
- GitHub URL (`REPOSITORY_URL`) is carried over from the earlier site; confirm it is the right repository.
- Contribution lines are the case study's own project-level wording; the case study notes responsibilities overlapped.
