import type {CSSProperties} from 'react';
import {
  ArrowDown,
  ArrowRight,
  Check,
  CircleAlert,
  Database,
  GitBranch,
  HeartPulse,
  ShieldCheck,
  Waves,
} from 'lucide-react';
import {Link} from 'react-router-dom';
import {CountUp} from '../components/CountUp';
import {Reveal} from '../components/Reveal';
import {detectors, resources, siteConfig, team} from '../data/site';

const detectorIcons = [ShieldCheck, HeartPulse, Waves, GitBranch, Database];

const ownership = [
  ['BI', 'The dashboard is working.'],
  ['Analytics', 'The query did not change.'],
  ['Data Engineering', 'The pipeline succeeded.'],
  ['Source System', 'The API returned 200.'],
] as const;

export function HomePage() {
  return (
    <>
      <section className="story-hero section-wrap">
        <Reveal className="story-hero-inner">
          <div className="story-logo-wrap" aria-hidden="true">
            <span className="story-logo-halo story-logo-halo-a" />
            <span className="story-logo-halo story-logo-halo-b" />
            <img src="./assets/brand/sentinel-logo.svg" alt="" />
          </div>
          <span className="eyebrow story-eyebrow">Healthcare-aware data observability</span>
          <h1>{siteConfig.tagline}</h1>
          <p>{siteConfig.description}</p>
          <div className="story-actions">
            <Link className="button primary" to="/demo">See the demo <ArrowRight size={16} /></Link>
            <Link className="button ghost" to="/case-study">Read the case study</Link>
          </div>
          <a className="scroll-cue" href="#gap" aria-label="Scroll to the problem">
            <span>Scroll to explore</span>
            <ArrowDown size={15} />
          </a>
        </Reveal>
      </section>

      <section className="story-section story-gap" id="gap">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">01 · The gap</div>
            <h2>Everything can be working.</h2>
            <p className="story-lead">A successful pipeline proves that data moved. It does not prove that the data arriving downstream is still healthy.</p>
          </Reveal>

          <Reveal className="pipeline-stage" delay={80}>
            <div className="pipeline-track" aria-label="Healthy pipeline animation">
              <span className="pipeline-beam" />
              {['Source', 'Kafka', 'Pipeline', 'Database'].map((item, index) => (
                <div className="pipeline-node" key={item} style={{'--node-delay': `${index * 160}ms`} as CSSProperties}>
                  <span>{item}</span>
                  <Check size={14} />
                </div>
              ))}
              <span className="pipeline-pulse" />
            </div>
            <div className="pipeline-caption"><span className="live-dot" /> Infrastructure healthy</div>
          </Reveal>

          <div className="signal-shifts">
            <Reveal className="signal-shift" delay={0}>
              <span>Missing values</span>
              <strong>0% <b>→</b> 30%</strong>
              <div className="mini-track"><i style={{width: '30%'}} /></div>
            </Reveal>
            <Reveal className="signal-shift" delay={100}>
              <span>Volume</span>
              <strong>10,580 <b>→</b> 2,600</strong>
              <div className="mini-track danger"><i style={{width: '25%'}} /></div>
            </Reveal>
            <Reveal className="signal-shift" delay={200}>
              <span>Heart Rate</span>
              <strong>Distribution shifted</strong>
              <div className="sparkline" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /></div>
            </Reveal>
          </div>

          <Reveal className="story-impact" delay={120}>
            <span>The systems are green.</span>
            <strong>The data is not.</strong>
          </Reveal>
        </div>
      </section>

      <section className="story-section story-ownership">
        <div className="section-wrap ownership-layout">
          <Reveal className="ownership-heading">
            <div className="story-kicker">02 · Ownership</div>
            <h2>So who notices when the data itself changes?</h2>
            <p className="story-lead">A data-quality issue can sit between areas of responsibility even when every team is correct about its own component.</p>
          </Reveal>

          <div className="ownership-lines">
            {ownership.map(([team, quote], index) => (
              <Reveal className="ownership-line" delay={index * 80} key={team}>
                <span>{team}</span>
                <p>“{quote}”</p>
                <Check size={16} />
              </Reveal>
            ))}
          </div>

          <Reveal className="ownership-answer">
            <span>That gap is where</span>
            <strong>Sentinel watches.</strong>
          </Reveal>
        </div>
      </section>

      <section className="story-section story-detectors">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">03 · What Sentinel watches</div>
            <h2>Five questions. One view of data health.</h2>
            <p className="story-lead">The technical method changes with the failure mode. The question stays human-readable.</p>
          </Reveal>

          <div className="detector-story-list">
            {detectors.map((detector, index) => {
              const Icon = detectorIcons[index];
              return (
                <Reveal className="detector-story" key={detector.name} delay={index * 40}>
                  <div className="detector-story-index">{String(index + 1).padStart(2, '0')}</div>
                  <div className="detector-story-copy">
                    <div className="detector-story-name"><Icon size={20} /> {detector.name}</div>
                    <h3>{detector.question}</h3>
                    <p>{detector.detail}</p>
                  </div>
                  <div className={`detector-viz detector-viz-${index + 1}`} aria-hidden="true">
                    {index === 4 ? (
                      <div className="volume-viz-content">
                        <div className="volume-viz-group">
                          <div className="volume-viz-bars expected">
                            <span /><span /><span />
                          </div>
                          <small>~10,580 expected</small>
                        </div>
                        <div className="volume-viz-drop">
                          <strong>↓ 75%</strong>
                          <span>drop</span>
                        </div>
                        <div className="volume-viz-group">
                          <div className="volume-viz-bars observed">
                            <span /><span /><span />
                          </div>
                          <small>~2,600 observed</small>
                        </div>
                      </div>
                    ) : (
                      <><span /><span /><span /><span /><span /></>
                    )}
                  </div>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      <section className="story-section story-resources">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">04 · FHIR-aware</div>
            <h2>Not anonymous JSON. Resources with meaning.</h2>
            <p className="story-lead">Patient, Encounter, and Observation have different notions of healthy behavior. Sentinel keeps the detector logic reusable while the monitoring policy stays resource-aware.</p>
          </Reveal>

          <Reveal className="resource-orbit" delay={90}>
            <div className="resource-center">
              <span>FHIR</span>
              <strong>Data Health</strong>
            </div>
            <svg className="resource-lines" viewBox="0 0 900 260" role="presentation" aria-hidden="true">
              <path d="M450 130 C330 130 315 62 205 62" />
              <path d="M450 130 C450 130 450 62 450 62" />
              <path d="M450 130 C570 130 585 62 695 62" />
            </svg>
            <div className="resource-row">
              {resources.map((resource, index) => (
                <article className="resource-story-card" key={resource.name} style={{'--resource-delay': `${index * 140}ms`} as CSSProperties}>
                  <span>0{index + 1}</span>
                  <h3>{resource.name}</h3>
                  <p>{resource.description}</p>
                </article>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      <section className="story-section story-architecture">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">05 · How it works</div>
            <h2>Historical behavior defines healthy. Live windows test whether it still holds.</h2>
          </Reveal>

          <Reveal className="architecture-story" delay={90}>
            <div className="architecture-story-lane">
              <span className="architecture-story-label">Historical</span>
              <div className="architecture-story-track">
                {['Synthea / FHIR', 'Bronze', 'Silver', 'GCS', 'Healthy reference'].map((node, index) => (
                  <div className="architecture-story-node" key={node}>
                    <span>{node}</span>{index < 4 ? <b>→</b> : null}
                  </div>
                ))}
                <i className="architecture-particle historical" />
              </div>
            </div>
            <div className="architecture-story-join">↓</div>
            <div className="architecture-story-lane live">
              <span className="architecture-story-label">Live</span>
              <div className="architecture-story-track">
                {['FHIR replay', 'Kafka', '60-sec windows', 'Detectors', 'PostgreSQL', 'Dashboard'].map((node, index) => (
                  <div className="architecture-story-node" key={node}>
                    <span>{node}</span>{index < 5 ? <b>→</b> : null}
                  </div>
                ))}
                <i className="architecture-particle live" />
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="story-section story-proof">
        <div className="section-wrap">
          <Reveal>
            <div className="story-kicker">06 · Controlled proof</div>
            <h2>We did not wait for the data to fail. We broke it ourselves.</h2>
            <p className="story-lead">The infrastructure stayed alive while a controlled volume injection pushed the incoming stream far outside its healthy reference.</p>
          </Reveal>

          <div className="proof-story-grid">
            <Reveal className="proof-number healthy" delay={50}>
              <span>Expected</span>
              <strong><CountUp to={10580} /></strong>
              <small>records / window</small>
            </Reveal>
            <Reveal className="proof-collapse" delay={150}>
              <div className="collapse-line"><i /></div>
              <span>controlled injection</span>
              <b>▼ ~75%</b>
            </Reveal>
            <Reveal className="proof-number incident" delay={250}>
              <span>Observed</span>
              <strong><CountUp from={10580} to={2600} /></strong>
              <small>records / window</small>
            </Reveal>
          </div>

          <Reveal className="incident-story" delay={180}>
            <div>
              <CircleAlert size={19} />
              <span>VOLUME DROP</span>
            </div>
            <strong>Incident opened</strong>
            <p>Kafka kept running. The consumer stayed alive. Sentinel still detected the problem.</p>
          </Reveal>

          <Reveal className="recovery-story" delay={220}>
            <span>Healthy</span><b>→</b><span>Failure injected</span><b>→</b><span>Detected</span><b>→</b><span>Incident</span><b>→</b><span className="recovered">Recovered</span>
          </Reveal>
        </div>
      </section>

      <section className="story-section story-demo">
        <div className="section-wrap demo-story-layout">
          <Reveal className="demo-story-copy">
            <div className="story-kicker">07 · See it in action</div>
            <h2>The dashboard is evidence, not the whole project.</h2>
            <p className="story-lead">Use the final recording to show healthy data, controlled failure, detection, incident context, and recovery in one short sequence.</p>
            <div className="story-actions">
              <Link className="button primary" to="/demo">Open demo page <ArrowRight size={16} /></Link>
              <Link className="button ghost" to="/case-study">Engineering case study</Link>
            </div>
          </Reveal>

          <Reveal className="demo-window" delay={100}>
            <div className="demo-window-bar"><i /><i /><i /><span>Sentinel · Live Dashboard</span></div>
            <div className="demo-window-content">
              <img src="./assets/brand/sentinel-logo.svg" alt="" />
              <span>DEMO PLACEHOLDER</span>
              <strong>Healthy → Inject → Detect → Recover</strong>
              <small>Replace with the final Sentinel dashboard recording.</small>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="story-section story-case-study">
        <div className="section-wrap case-study-tease">
          <Reveal>
            <div className="story-kicker">08 · The engineering behind it</div>
            <h2>Architecture, baselines, detectors, failures, trade-offs.</h2>
            <p className="story-lead">The case study documents what we built, why we chose it, what went wrong, how we tested it, and what we would change in production.</p>
          </Reveal>
          <Reveal delay={100}>
            <Link className="case-study-link" to="/case-study">Read the full case study <ArrowRight size={19} /></Link>
          </Reveal>
        </div>
      </section>

      <section className="story-section story-team-preview">
        <div className="section-wrap team-preview-layout">
          <Reveal>
            <div className="story-kicker">09 · Built together</div>
            <h2>Four data engineers. One question worth investigating.</h2>
            <p className="story-lead">Exploring what it takes to make streaming data trustworthy.</p>
            <Link className="case-study-link" to="/team">Meet the team <ArrowRight size={19} /></Link>
          </Reveal>
          <Reveal className="team-preview-grid" delay={120}>
            {team.map((member) => (
              <span key={member.name} >
                {member.name}
              </span>
            ))}
          </Reveal>
        </div>
      </section>
    </>
  );
}
