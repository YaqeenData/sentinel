import type { ReactNode } from 'react';
import { SectionHeading } from '../components/SectionHeading';
import { PlaceholderVisual } from '../components/PlaceholderVisual';
const base = import.meta.env.BASE_URL;

function DeepDive({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <details className="deep-dive">
      <summary>{title}</summary>
      <div>{children}</div>
    </details>
  );
}

export function CaseStudyPage() {
  return (
    <div className="page-wrap">
      {/* ─────────────────────────────────────────────
          HERO
      ───────────────────────────────────────────── */}
      <section className="page-hero section-wrap">
        <span className="eyebrow">Engineering Case Study</span>

        <h1>
          Moving data successfully and trusting the data that arrived are two
          different engineering problems.
        </h1>

        <p>
          This case study documents how Sentinel was scoped, built, tested, and
          evaluated as a healthcare-aware streaming data observability
          prototype.
        </p>
      </section>

      {/* ─────────────────────────────────────────────
          01 — PROBLEM
      ───────────────────────────────────────────── */}
      <section className="section-wrap case-section">
        <SectionHeading eyebrow="01" title="Problem & constraints" />

        <div className="prose-grid">
          <div>
            <h3>What we wanted to understand</h3>

            <p>
              A pipeline can keep running while the data becomes incomplete,
              structurally invalid, statistically different, or abnormal in
              volume. We wanted to make that gap observable without treating
              infrastructure health as a proxy for data health.
            </p>

            <h3>Constraints that shaped the design</h3>

            <p>
              Sentinel was built as a one-week, four-person capstone. We did
              not use real hospital data, so Synthea provided synthetic FHIR
              resources that could be replayed, profiled, and deliberately
              broken in a safe environment.
            </p>
          </div>

          <PlaceholderVisual
            title="Pipeline health vs. data health"
            description="Add a simple visual showing green infrastructure beside changing data behavior."
          />
        </div>
      </section>

      {/* ─────────────────────────────────────────────
          02 — ARCHITECTURE
      ───────────────────────────────────────────── */}
      <section className="section-wrap case-section">
        <SectionHeading eyebrow="02" title="Architecture" />

        <p className="lead-prose">
          Sentinel has two complementary paths: historical data establishes
          healthy reference behavior, while live data is replayed through Kafka
          and evaluated in 60-second processing windows.
        </p>

        <div className="case-two-col">
          <article className="case-card">
            <span>Historical</span>
            <h3>Build the reference</h3>
            <p>
              Synthea → FHIR → Bronze → Silver → GCS → profiling → healthy
              baselines.
            </p>
          </article>

          <article className="case-card">
            <span>Live</span>
            <h3>Evaluate what is arriving now</h3>
            <p>
              FHIR replay → Kafka → consumer → 60-second windows → detectors →
              PostgreSQL → Streamlit.
            </p>
          </article>
        </div>

        <figure className="case-diagram">
          <picture>
            <source
              media="(max-width: 720px)"
              srcSet={`${base}assets/diagrams/sentinel-system-architecture-mobile.svg`}
            />

            <img
              src={`${base}assets/diagrams/sentinel-system-architecture.svg`}
              alt="Sentinel system architecture showing the historical reference path used to establish healthy baselines and the live streaming path through Kafka, the detection engine, PostgreSQL, and the monitoring dashboard."
              loading="lazy"
            />
          </picture>

          <figcaption>
            Sentinel separates baseline generation from live stream evaluation so
            controlled failures do not redefine healthy behavior.
          </figcaption>
        </figure>

        <DeepDive title="Why processing time instead of event time?">
          <p>
            Processing-time windows answer the operational question: “What
            reached Sentinel during this monitoring interval?” FHIR event time
            is retained for clinical context. A production extension could
            compare processing time with event time to detect late-arriving
            data.
          </p>
        </DeepDive>
      </section>

      {/* ─────────────────────────────────────────────
          03 — DETECTORS
      ───────────────────────────────────────────── */}
      <section className="section-wrap case-section">
        <SectionHeading eyebrow="03" title="Detector design" />

        <p className="lead-prose">
          Each monitoring window is evaluated by multiple detectors. Rather
          than forcing every anomaly into one model, Sentinel uses a detector
          suited to the structure of each failure mode.
        </p>

        <div className="case-two-col">
          <article className="case-card">
            <span>Rule-based</span>
            <h3>Contract validation</h3>
            <p>
              Checks required fields, allowed values, expected types, and
              consistency between value types and populated fields.
            </p>
          </article>

          <article className="case-card">
            <span>Rate-based</span>
            <h3>Missingness</h3>
            <p>
              Checks whether important values disappear relative to healthy
              historical behavior.
            </p>
          </article>

          <article className="case-card">
            <span>Distribution-based</span>
            <h3>Numeric drift</h3>
            <p>
              Uses the two-sample Kolmogorov–Smirnov statistic with sample and
              effect-size requirements.
            </p>
          </article>

          <article className="case-card">
            <span>Distribution-based</span>
            <h3>Categorical drift</h3>
            <p>
              Uses Jensen–Shannon distance to compare baseline and current
              category proportions.
            </p>
          </article>

          <article className="case-card">
            <span>Robust count anomaly</span>
            <h3>Volume</h3>
            <p>
              Uses the historical median, MAD, and percentage guardrails to
              detect drops and spikes.
            </p>
          </article>
        </div>

        <figure className="case-diagram detector-diagram">
          <img
            className="diagram-dark"
            src={`${base}assets/diagrams/sentinel-detection-engine-dark.webp`}
            alt="Sentinel detection engine showing contract validation, missingness, numeric drift, categorical drift, and volume monitoring."
            loading="lazy"
          />

          <img
            className="diagram-light"
            src={`${base}assets/diagrams/sentinel-detection-engine-light.webp`}
            alt=""
            aria-hidden="true"
            loading="lazy"
          />

          <figcaption>
            Different failure modes are evaluated independently before Sentinel decides
            whether the window remains healthy or should open an incident.
          </figcaption>
        </figure>

        <DeepDive title="Why not use one universal anomaly detector?">
          <p>
            These failure modes have different statistical structures.
            Structural validity is rule-based, missingness is a rate, numeric
            values need a numeric-distribution comparison, categories need
            probability-distribution comparison, and volume is a robust count
            problem. Using different methods keeps each detector interpretable.
          </p>
        </DeepDive>
      </section>

      {/* ─────────────────────────────────────────────
          04 — EXPERIMENT
      ───────────────────────────────────────────── */}
      <section className="section-wrap case-section">
        <SectionHeading eyebrow="04" title="Controlled experiment" />

        <div className="prose-grid">
          <div>
            <h3>Why inject failures?</h3>

            <p>
              We needed a repeatable way to verify that each detector reacted
              to the failure mode it was designed to observe. Failures were
              injected only into the live path, while the healthy historical
              baseline remained unchanged.
            </p>

            <h3>Volume experiment</h3>

            <p>
              Normal windows were centered around approximately 10,580
              Observation records. A controlled volume failure retained roughly
              a quarter of the incoming rows, producing approximately 2,600
              records. Kafka and the consumer remained operational, but Sentinel
              opened a volume-drop incident and later resolved it after
              recovery.
            </p>
          </div>

          <PlaceholderVisual
            title="Healthy → incident → recovery"
            description="Add three screenshots from the dashboard showing the complete incident lifecycle."
          />
        </div>
      </section>

      {/* ─────────────────────────────────────────────
          05 — ENGINEERING DECISIONS
      ───────────────────────────────────────────── */}
      <section className="section-wrap case-section">
        <SectionHeading
          eyebrow="05"
          title="Engineering decisions & trade-offs"
        />

        <div
          className="decision-table"
          role="table"
          aria-label="Engineering decisions"
        >
          <div className="decision-row heading">
            <span>Decision</span>
            <span>Why</span>
            <span>Trade-off</span>
          </div>

          <div className="decision-row">
            <strong>Fixed baseline</strong>
            <span>
              Keeps controlled experiments repeatable and prevents injected
              failures from becoming “normal.”
            </span>
            <span>
              Production would need baseline versioning or governed
              recalibration.
            </span>
          </div>

          <div className="decision-row">
            <strong>60-second windows</strong>
            <span>
              Simple, observable operational cadence for a short capstone.
            </span>
            <span>
              Different resources may need different windows in production.
            </span>
          </div>

          <div className="decision-row">
            <strong>Kafka replay</strong>
            <span>
              Separates producer and monitoring logic while providing a
              controllable live stream.
            </span>
            <span>
              Capstone infrastructure is not a production-scale Kafka
              deployment.
            </span>
          </div>

          <div className="decision-row">
            <strong>PostgreSQL state</strong>
            <span>
              Persists metrics and incident lifecycle independently from
              dashboard rendering.
            </span>
            <span>
              Long-term scale and retention would require stronger operational
              design.
            </span>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────
          06 — SCOPE
      ───────────────────────────────────────────── */}
      <section className="section-wrap case-section">
        <SectionHeading
          eyebrow="06"
          title="What the project demonstrated — and what it did not"
        />

        <div className="case-two-col">
          <article className="case-card success">
            <h3>Demonstrated</h3>
            <p>
              Streaming synthetic FHIR data, monitoring
              Patient/Encounter/Observation resources, multiple detector types,
              incident persistence, recovery, and dashboard visualization in a
              controlled environment.
            </p>
          </article>

          <article className="case-card caution">
            <h3>Not claimed</h3>
            <p>
              Hospital production deployment, clinical decision support,
              regulatory compliance, national-scale throughput, universally
              correct thresholds, or replacement of mature commercial
              observability platforms.
            </p>
          </article>
        </div>

        <div className="statement-band">
          <span>Sentinel monitors</span>
          <strong>DATA HEALTH — not patient health.</strong>
        </div>
      </section>

      {/* ─────────────────────────────────────────────
          07 — NEXT
      ───────────────────────────────────────────── */}
      <section className="section-wrap case-section">
        <SectionHeading eyebrow="07" title="What we would build next" />

        <div className="future-grid">
          {[
            'Versioned / rolling baselines',
            'Event-time lateness monitoring',
            'Hysteresis & cooldowns',
            'Alert routing & ownership',
            'Authentication & authorization',
            'More FHIR resources',
            'Long-term trends',
            'Distributed production deployment',
          ].map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </section>

      {/* ─────────────────────────────────────────────
          08 — REFLECTION
      ───────────────────────────────────────────── */}
      <section className="section-wrap case-section reflection">
        <SectionHeading
          eyebrow="08 · Reflection"
          title="The harder question was never just whether the pipeline ran."
        />

        <p>
          Sentinel reinforced that moving data successfully and trusting the
          data that arrived are separate engineering problems. The deeper work
          was defining what healthy behavior meant, choosing interpretable ways
          to measure deviations, and making those deviations understandable to
          the people operating the system.
        </p>
      </section>
    </div>
  );
}