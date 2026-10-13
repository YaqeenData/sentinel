import {ExternalLink, Play, Radio} from 'lucide-react';
import {PlaceholderVisual} from '../components/PlaceholderVisual';
import {SectionHeading} from '../components/SectionHeading';
import {siteConfig} from '../data/site';

export function DemoPage() {
  return (
    <div className="page-wrap">
      <section className="page-hero section-wrap">
        <span className="eyebrow">Demo</span>
        <h1>Watch Sentinel move from healthy → abnormal → recovered.</h1>
        <p>The final demo will combine the live Streamlit dashboard with controlled injections so the full incident lifecycle is visible without relying on a pipeline crash.</p>
      </section>

      <section className="section-wrap demo-feature">
        <PlaceholderVisual kind="video" title="Sentinel product video" description="Drop the final rendered Sentinel video here or replace this section with an embedded hosted video." />
        <div className="demo-actions">
          {siteConfig.liveDashboardUrl ? (
            <a className="button primary" href={siteConfig.liveDashboardUrl} target="_blank" rel="noreferrer"><Radio size={17} /> Open live dashboard <ExternalLink size={15} /></a>
          ) : (
            <span className="button primary disabled"><Radio size={17} /> Live dashboard URL not set</span>
          )}
          {siteConfig.demoVideoUrl ? (
            <a className="button secondary" href={siteConfig.demoVideoUrl} target="_blank" rel="noreferrer"><Play size={17} /> Watch hosted demo</a>
          ) : null}
        </div>
      </section>

      <section className="section-wrap section-block">
        <SectionHeading eyebrow="Demo sequence" title="Four clips tell the full story." />
        <div className="demo-grid">
          <PlaceholderVisual kind="video" title="01 · Healthy overview" description="Overall data health and all active detectors in a healthy state." />
          <PlaceholderVisual kind="video" title="02 · Injection enabled" description="Controlled failure turned on without stopping the streaming pipeline." />
          <PlaceholderVisual kind="video" title="03 · Incident detected" description="Show the detector card, incident details, observed value, and healthy reference." />
          <PlaceholderVisual kind="video" title="04 · Recovery" description="Turn the failure off and capture incident resolution / healthy state returning." />
        </div>
      </section>

      <section className="section-wrap section-block">
        <SectionHeading eyebrow="Evidence" title="Screenshots for readers who do not watch the full demo." />
        <div className="demo-grid">
          <PlaceholderVisual title="Dashboard overview" description="Final polished Sentinel Overview page." />
          <PlaceholderVisual title="Incident details" description="One clear incident with resource, detector, observed value, baseline, severity, and status." />
          <PlaceholderVisual title="Resource monitoring" description="Patient / Encounter / Observation health view." />
          <PlaceholderVisual title="Detector evidence" description="A human-readable drift or volume visualization from the dashboard." />
        </div>
      </section>
    </div>
  );
}
