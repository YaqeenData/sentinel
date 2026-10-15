import {ArrowDown, ArrowRight, Check, ExternalLink} from 'lucide-react';
import {Link} from 'react-router-dom';
import {ArchitectureFigure} from '../components/ArchitectureFigure';
import {DemoVideo} from '../components/DemoVideo';
import {ProductJourney} from '../components/ProductJourney';
import {Reveal} from '../components/Reveal';
import {Shot} from '../components/Shot';
import {
  aisha,
  architectureNotes,
  checks,
  downstream,
  engineeringDetails,
  fhirLine,
  healthStatement,
  prototypeStatement,
  resourcesPlain,
  results,
  scopeNext,
  scopeToday,
  securityVsQuality,
  snapshot,
  values,
  withSentinel,
  without,
} from '../data/content';
import {siteConfig, team, teamNote} from '../data/site';

function GitHubLink({variant = 'ghost', children = 'View GitHub'}: {variant?: 'ghost' | 'secondary'; children?: string}) {
  return (
    <a className={`button ${variant}`} href={siteConfig.repositoryUrl} target="_blank" rel="noopener noreferrer">
      {children} <ExternalLink size={14} aria-hidden="true" />
    </a>
  );
}

export function HomePage() {
  return (
    <>
      {/* HERO */}
      <section className="story-hero rd-hero section-wrap" id="top">
        <Reveal className="story-hero-inner">
          <div className="story-logo-wrap" aria-hidden="true">
            <span className="story-logo-halo story-logo-halo-a" />
            <span className="story-logo-halo story-logo-halo-b" />
            <img src="./assets/brand/sentinel-logo.svg" alt="" />
          </div>
          <span className="eyebrow story-eyebrow">Sentinel</span>
          <h1>
            The pipeline can be green
            <br />
            <span className="rd-accent">while the data is wrong.</span>
          </h1>
          <p>
            Sentinel monitors streaming healthcare data for quality problems that can stay invisible while the
            pipeline, database and dashboards keep working.
          </p>
          <div className="story-actions">
            <a className="button primary" href="#demo">Watch Demo <ArrowDown size={16} aria-hidden="true" /></a>
            <GitHubLink>View GitHub</GitHubLink>
          </div>
        </Reveal>
        <Reveal className="rd-hero-shot" delay={120}>
          <Shot
            file="sentinel-healthy"
            alt="Sentinel overview dashboard showing healthy Patient, Observation, and Encounter resources."
            state="Healthy"
            tone="healthy"
            eager
          />
        </Reveal>
      </section>

      {/* EXECUTIVE SNAPSHOT */}
      <section className="rf-snapshot section-wrap" aria-label="Sentinel at a glance">
        <dl>
          <div>
            <dt>What is it</dt>
            <dd>{snapshot.what}</dd>
          </div>
          <div>
            <dt>What it monitors</dt>
            <dd>{snapshot.monitors.join(' · ')}</dd>
          </div>
          <div>
            <dt>What it detects</dt>
            <dd>{snapshot.detects.join(' · ')}</dd>
          </div>
          <div>
            <dt>Why it matters</dt>
            <dd>{snapshot.why}</dd>
          </div>
        </dl>
        <ul className="rf-stack" aria-label="Technology stack">
          {snapshot.stack.map((s) => <li key={s}>{s}</li>)}
        </ul>
      </section>

      {/* WHY DATA QUALITY MATTERS */}
      <section className="story-section rd-section" id="why">
        <div className="section-wrap rf-narrow">
          <Reveal>
            <div className="story-kicker">Why data quality matters</div>
            <h2>A system can stay up while the information inside it is wrong.</h2>
          </Reveal>
          <Reveal className="rf-aisha" delay={60}>
            <span className="rf-flag">{aisha.label}</span>
            <p>{aisha.text}</p>
            <ol className="rf-chain" aria-label="What happens in the scenario">
              {aisha.chain.map((step) => <li key={step}>{step}</li>)}
            </ol>
            <p className="rf-muted">{aisha.point}</p>
          </Reveal>
          <Reveal delay={80}>
            <p className="rf-pull">{aisha.takeaway}</p>
          </Reveal>
        </div>
      </section>

      {/* WHAT HEALTHCARE DATA */}
      <section className="story-section rd-section" id="data">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">The data</div>
            <h2>Three kinds of healthcare data.</h2>
          </Reveal>
          <div className="rf-trio-plain">
            {resourcesPlain.map((r, i) => (
              <Reveal key={r.name} delay={i * 60}>
                <div className="rf-plain">
                  <strong>{r.name}</strong>
                  <p className="rf-q">{r.question}</p>
                  <p className="rf-muted">{r.note}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal delay={80}>
            <p className="story-lead rf-fhir">{fhirLine}</p>
          </Reveal>
        </div>
      </section>

      {/* SECURITY IS NOT DATA QUALITY */}
      <section className="story-section rd-section">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">Two different jobs</div>
            <h2>Security is not data quality.</h2>
          </Reveal>
          <div className="rf-vs">
            <Reveal className="rf-vs-col">
              <span className="rd-col-label">{securityVsQuality.security.label}</span>
              <p className="rf-vs-ask">{securityVsQuality.security.asks}</p>
              <ul>{securityVsQuality.security.items.map((i) => <li key={i}>{i}</li>)}</ul>
            </Reveal>
            <Reveal className="rf-vs-col quality" delay={100}>
              <span className="rd-col-label">{securityVsQuality.quality.label}</span>
              <p className="rf-vs-ask">{securityVsQuality.quality.asks}</p>
              <ul>{securityVsQuality.quality.items.map((i) => <li key={i}>{i}</li>)}</ul>
            </Reveal>
          </div>
          <Reveal delay={80}>
            <p className="rf-pull">
              {securityVsQuality.takeaway[0]}
              <br />
              <span className="rd-accent">{securityVsQuality.takeaway[1]}</span>
            </p>
          </Reveal>
        </div>
      </section>

      {/* WHY THE BUSINESS CARES */}
      <section className="story-section rd-section" id="business">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">Why the business cares</div>
            <h2>{downstream.lead}</h2>
            <p className="story-lead">{downstream.note}</p>
          </Reveal>
          <ul className="rf-uses">
            {downstream.uses.map((u, i) => (
              <Reveal key={u.name} delay={i * 50}>
                <li>
                  <strong>{u.name}</strong>
                  <span>{u.text}</span>
                </li>
              </Reveal>
            ))}
          </ul>
          <Reveal delay={60}>
            <p className="rf-pull">{downstream.closing}</p>
          </Reveal>

          <div className="rd-compare rf-compare">
            <Reveal className="rd-flow without">
              <span className="rd-flow-label">Without Sentinel</span>
              <ol>{without.map((s) => <li key={s}>{s}</li>)}</ol>
            </Reveal>
            <Reveal className="rd-flow with" delay={100}>
              <span className="rd-flow-label">With Sentinel</span>
              <ol>{withSentinel.map((s) => <li key={s}>{s}</li>)}</ol>
            </Reveal>
          </div>

          <Reveal delay={60}>
            <dl className="rf-values">
              {values.map((v) => (
                <div key={v.name}>
                  <dt>{v.name}</dt>
                  <dd>{v.text}</dd>
                </div>
              ))}
            </dl>
          </Reveal>
        </div>
      </section>

      {/* SENTINEL IN ACTION */}
      <section className="story-section rd-section rd-demo" id="action">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">Sentinel in action</div>
            <h2>Monitor. Detect. Investigate. Track.</h2>
            <p className="story-lead">The real dashboard, following one volume drop from start to finish.</p>
          </Reveal>
          <Reveal delay={60}>
            <ProductJourney />
          </Reveal>
        </div>
      </section>

      <section className="story-section rd-section rd-demo rf-video" id="demo">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">Demo</div>
            <h2>See Sentinel in action</h2>
            <p className="story-lead">From healthy monitoring to detection, investigation and recovery.</p>
          </Reveal>
          <Reveal className="rd-demo-stage" delay={80}>
            <DemoVideo />
            <div className="story-actions rd-left">
              <Link className="button secondary" to="/demo">More from the demo <ArrowRight size={16} aria-hidden="true" /></Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* WHAT SENTINEL CHECKS */}
      <section className="story-section rd-section" id="checks">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">What Sentinel checks</div>
            <h2>Five questions about the data.</h2>
          </Reveal>
          <ol className="rf-checks">
            {checks.map((c, i) => (
              <Reveal key={c.name} delay={(i % 3) * 40}>
                <li>
                  <span className="rf-check-name">{c.name}</span>
                  <h3>{c.question}</h3>
                  <p>{c.examples}</p>
                  <details className="rf-tech">
                    <summary>Technical details</summary>
                    <p>{c.technical}</p>
                  </details>
                </li>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      {/* ENGINEERING */}
      <section className="story-section rd-section story-architecture" id="architecture">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">How it is engineered</div>
            <h2>Live data, judged against a historical reference.</h2>
          </Reveal>
          <Reveal delay={60}>
            <ArchitectureFigure />
          </Reveal>
          <div className="rf-notes">
            {architectureNotes.map((n, i) => (
              <Reveal key={i} delay={i * 50}><p>{n}</p></Reveal>
            ))}
          </div>
          <Reveal delay={60}>
            <details className="rf-eng">
              <summary>Engineering details</summary>
              <dl>
                {engineeringDetails.map(([t, d]) => (
                  <div key={t}>
                    <dt>{t}</dt>
                    <dd>{d}</dd>
                  </div>
                ))}
              </dl>
              <p className="rf-results"><strong>{results.line}</strong> {results.note}</p>
              <Link className="case-study-link" to="/case-study">Read the engineering deep dive <ArrowRight size={18} aria-hidden="true" /></Link>
            </details>
          </Reveal>
        </div>
      </section>

      {/* SCOPE */}
      <section className="story-section rd-section rd-scope" id="scope">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">Scope</div>
            <h2>What exists today, and what comes next.</h2>
          </Reveal>
          <Reveal className="rd-statement" delay={60}>
            <strong>{prototypeStatement}</strong>
            <span>{healthStatement}</span>
          </Reveal>
          <div className="rd-scope-grid">
            <Reveal className="rd-scope-col today">
              <span className="rd-col-label">Today</span>
              <ul>{scopeToday.map((s) => <li key={s}><Check size={15} aria-hidden="true" /> {s}</li>)}</ul>
            </Reveal>
            <Reveal className="rd-scope-col next" delay={100}>
              <span className="rd-col-label">Next</span>
              <ul>{scopeNext.map((s) => <li key={s}><ArrowRight size={15} aria-hidden="true" /> {s}</li>)}</ul>
            </Reveal>
          </div>
        </div>
      </section>

      {/* TEAM */}
      <section className="story-section rd-section story-team-preview" id="team">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">Team</div>
            <h2 className="rd-h2-small">Four data engineers, one capstone.</h2>
          </Reveal>
          <div className="rd-team" role="list">
            {team.map((m, i) => (
              <Reveal className="rd-member" delay={i * 60} key={m.name}>
                <div role="listitem">
                  <strong>{m.name}</strong>
                  <span>{m.role}</span>
                  <p className="rf-contrib">{m.contribution}</p>
                  <div className="rd-member-links">
                    {m.linkedin ? (
                      <a href={m.linkedin} target="_blank" rel="noopener noreferrer" aria-label={`${m.name} on LinkedIn`}>LinkedIn <ExternalLink size={12} aria-hidden="true" /></a>
                    ) : null}
                    {m.portfolio ? (
                      <a href={m.portfolio} target="_blank" rel="noopener noreferrer" aria-label={`${m.name} portfolio`}>Portfolio <ExternalLink size={12} aria-hidden="true" /></a>
                    ) : null}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
          <p className="rd-quiet rd-left">{teamNote}</p>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="story-section rd-section rd-final">
        <div className="section-wrap">
          <Reveal className="rd-final-inner">
            <h2>
              The pipeline can be green
              <br />
              <span className="rd-accent">while the data is wrong.</span>
            </h2>
            <div className="story-actions">
              <a className="button primary" href="#demo">Watch Demo</a>
              <GitHubLink variant="secondary">View GitHub</GitHubLink>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}
