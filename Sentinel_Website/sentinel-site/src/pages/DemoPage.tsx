import {ArrowRight} from 'lucide-react';
import {Link} from 'react-router-dom';
import {DemoVideo} from '../components/DemoVideo';
import {LiveDemoLink} from '../components/LiveDemoLink';
import {SectionHeading} from '../components/SectionHeading';
import {Shot} from '../components/Shot';

export function DemoPage() {
  return (
    <div className="page-wrap">
      <section className="page-hero section-wrap">
        <span className="eyebrow">Demo</span>
        <h1>See Sentinel in Action</h1>
        <p>From healthy data, to detection, investigation, and recovery.</p>
      </section>

      <section className="section-wrap demo-feature">
        <DemoVideo />
        <div className="demo-actions">
          <LiveDemoLink>Open Live Demo</LiveDemoLink>
          <Link className="button secondary" to="/">Read the story <ArrowRight size={16} aria-hidden="true" /></Link>
        </div>
        <p className="rd-quiet rd-left">Dark and light modes supported. The demo uses synthetic data; Sentinel monitors data health, not patient health.</p>
      </section>

      <section className="section-wrap section-block">
        <SectionHeading eyebrow="Evidence" title="A closer look at what Sentinel shows." />
        <div className="rd-shot-grid">
          <Shot
            className="span-3"
            file="sentinel-data-quality-volume"
            state="Investigate · volume"
            tone="info"
            alt="Sentinel Data Quality view showing the Observation volume drop and spike check"
            caption="Data Quality: the volume check that flagged the drop."
          />
          <Shot
            className="span-3"
            file="sentinel-incident-volume"
            state="Incident · volume"
            tone="info"
            alt="Sentinel Incidents page with one open volume-drop incident"
            caption="Incidents: severity, status and the record count at detection."
          />
          <Shot
            className="span-3"
            file="sentinel-data-quality-critical"
            state="Investigate · contract"
            tone="critical"
            alt="Sentinel Data Quality view showing a failed Observation contract validation"
            caption="Data Quality: the contract check that failed and the rows affected."
          />
          <Shot
            className="span-3"
            file="sentinel-incident-critical"
            state="Incidents · critical"
            tone="critical"
            alt="Sentinel Incidents page with three open incidents and an incidents-by-type chart"
            caption="Incidents: open, resolved and total incidents by type."
          />
        </div>
      </section>
    </div>
  );
}
