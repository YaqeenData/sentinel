/**
 * Page copy, kept separate from layout. Everything here is distilled from the final
 * Sentinel Business + Engineering Case Study. Edit wording here, not in the components.
 */

export const snapshot = {
  what: 'Real-time data observability for streaming healthcare data.',
  monitors: ['Patient', 'Encounter', 'Observation'],
  detects: ['Contract violations', 'Missing values', 'Volume changes', 'Numeric drift', 'Categorical drift'],
  why: 'Spot unreliable data earlier, before it silently spreads downstream.',
  stack: ['Python', 'Kafka', 'FHIR', 'Google Cloud Storage', 'PostgreSQL', 'Streamlit', 'Docker'],
} as const;

export const aisha = {
  label: 'A fictional scenario',
  chain: [
    'A lab analyzer drifts out of calibration',
    'It produces a valid-looking result',
    'Every system keeps running',
    'The result looks unsafe, and treatment is delayed',
  ],
  text:
    'Aisha is a fictional patient. A lab analyzer has a calibration problem and records inaccurate pre-treatment values. The device stays online, and the records move through the hospital data flow without any alarm.',
  point:
    'Sentinel would not diagnose the device. The point is that data can stay structurally valid and keep moving while its behavior becomes unreliable, and that is a gap infrastructure monitoring cannot see.',
  takeaway: 'Nothing has to crash for bad data to create downstream consequences.',
};

export const resourcesPlain = [
  {name: 'Patient', question: 'Who is the person?', note: 'Identity and basic context.'},
  {name: 'Encounter', question: 'What healthcare interaction happened?', note: 'A visit, admission or appointment.'},
  {name: 'Observation', question: 'What was measured or recorded?', note: 'Vitals, lab values and statuses.'},
] as const;

export const fhirLine =
  'FHIR is a standard healthcare systems use to structure and exchange healthcare information.';

export const securityVsQuality = {
  security: {
    label: 'Security',
    asks: 'Who can access the data?',
    items: ['Access', 'Authorization', 'Encryption', 'Infrastructure'],
  },
  quality: {
    label: 'Data quality',
    asks: 'Can we trust the data itself?',
    items: ['Is it complete?', 'Is it valid?', 'Is expected data arriving?', 'Did its behavior change?'],
  },
  takeaway: ['Security protects access to the data.', 'Data quality protects trust in the data.'],
};

export const downstream = {
  lead: 'Cleaner, more trustworthy data supports better decisions.',
  note: 'It does not guarantee them. It gives every downstream use a more trustworthy input.',
  uses: [
    {name: 'Dashboards', text: 'Bad data can distort counts and trends.'},
    {name: 'Analytics', text: 'Incomplete data can distort reports and analysis.'},
    {name: 'Machine learning', text: 'Models inherit problems in their inputs.'},
    {name: 'Operations', text: 'Incomplete activity data can give an inaccurate picture of demand.'},
  ],
  closing: 'Data quality is upstream of decision quality.',
};

export const without = [
  'A problem begins',
  'The pipeline keeps running',
  'Unreliable data spreads',
  'A downstream symptom appears',
  'Investigation starts later',
] as const;

export const withSentinel = [
  'A problem begins',
  'Sentinel detects abnormal behavior',
  'Evidence and an incident appear',
  'Investigation starts earlier',
  'Downstream exposure can be reduced',
] as const;

export const values = [
  {name: 'Earlier detection', text: 'Reduce time-to-detection.'},
  {name: 'Faster investigation', text: 'See what changed, where and when.'},
  {name: 'Shared evidence', text: 'Give teams a common starting point.'},
  {name: 'Lower downstream risk', text: 'Limit how far unreliable data spreads unnoticed.'},
] as const;

export type JourneyStep = {
  id: string;
  label: string;
  title: string;
  caption: string;
  file: string;
  alt: string;
  tone: 'healthy' | 'attention' | 'info';
  state: string;
};

export const journey: JourneyStep[] = [
  {
    id: 'monitor',
    label: 'Monitor',
    title: '01 · Monitor',
    caption:
      'Start with a clear view of overall data health and the status of Patient, Observation and Encounter.',
    file: 'sentinel-healthy',
    alt: 'Sentinel overview dashboard showing healthy Patient, Observation, and Encounter resources.',
    tone: 'healthy',
    state: 'Healthy',
  },
  {
    id: 'detect',
    label: 'Detect',
    title: '02 · Detect',
    caption: 'Sentinel surfaces a change even though the pipeline itself is still running.',
    file: 'sentinel-attention-volume',
    alt: 'Sentinel dashboard showing an Observation volume-drop incident: 5,909 records observed against a baseline of 10,148.5.',
    tone: 'attention',
    state: 'Attention',
  },
  {
    id: 'investigate',
    label: 'Investigate',
    title: '03 · Investigate',
    caption:
      'See which quality check failed, what changed, and how the observed value compares with expected behavior.',
    file: 'sentinel-data-quality-volume',
    alt: 'Sentinel Data Quality view showing the active volume detector.',
    tone: 'info',
    state: 'Data Quality',
  },
  {
    id: 'track',
    label: 'Track',
    title: '04 · Track',
    caption: 'Track severity, status, timing and recovery through the incident lifecycle.',
    file: 'sentinel-incident-volume',
    alt: 'Sentinel Incidents page showing an open volume-drop incident with its severity, status and record-count chart.',
    tone: 'info',
    state: 'Incidents',
  },
];

export const checks = [
  {
    name: 'Contract',
    question: 'Does the record still follow the expected rules?',
    examples: 'Missing required fields, an unexpected status, a wrong type.',
    technical: 'Rule-based validation. Expectations are explicit, so no statistics are needed.',
  },
  {
    name: 'Missingness',
    question: 'Did information that is normally present suddenly disappear?',
    examples: 'A usually-filled value starts arriving empty.',
    technical: 'Null-rate comparison against healthy historical behavior. Null rate is a simple proportion.',
  },
  {
    name: 'Volume',
    question: 'Are we receiving much less or more data than expected?',
    examples: 'Observation records drop well below the usual count.',
    technical: 'Historical median and MAD, which stay robust against extreme historical windows.',
  },
  {
    name: 'Numeric drift',
    question: 'Did numeric values shift away from their normal pattern?',
    examples: 'Measured values start behaving differently from normal.',
    technical: 'Two-sample Kolmogorov–Smirnov test. Compares full distributions without assuming normality.',
  },
  {
    name: 'Categorical drift',
    question: 'Did the mix of categories unexpectedly change?',
    examples: 'One status or code suddenly dominates.',
    technical: 'Jensen–Shannon distance between category proportions. Handles zero shares.',
  },
] as const;

export const architectureNotes = [
  'Live data flows from Synthea through HAPI FHIR and a Python producer into Kafka. Events are grouped into 60-second windows, and each closed window is evaluated by the Sentinel detection engine.',
  'Historical synthetic data from Synthea is kept in Google Cloud Storage as Bronze (raw FHIR) and Silver (cleaned). It provides the reference for what healthy behavior looks like. Google Cloud stores the data; Synthea is where it comes from.',
  'Detection results, metrics and incidents are stored in PostgreSQL and shown in the Streamlit dashboard. The dashboard reads monitoring state; it contains no detection logic.',
];

export const engineeringDetails = [
  ['Processing-time windows', 'Simple, live monitoring of what reached Sentinel in each interval. The trade-off: late arrival cannot be identified from event time.'],
  ['Fixed baselines', 'Repeatable and explainable for a controlled prototype, but they do not adapt automatically. Production would need governed, versioned, rolling or seasonal baselines.'],
  ['Bronze / Silver history', 'Bronze preserves raw FHIR. Silver is normalized, which makes profiling and detection easier.'],
  ['Incident lifecycle', 'An abnormal window opens an incident. Repeated abnormal windows keep the same incident open. Healthy behavior resolves it.'],
  ['Different checks, different methods', 'One interpretable method per failure mode, instead of a single universal detector.'],
] as const;

export const results = {
  line: 'In the controlled capstone test, the prototype detected every injected failure class, and resolved the incident when healthy data returned.',
  note: 'This is evidence of behavior in a repeatable synthetic test, not a claim of hospital production readiness.',
};

export const scopeToday = [
  'Synthetic FHIR data',
  'Patient, Encounter and Observation',
  'Five data-quality checks',
  'Fixed baselines and thresholds',
  'Incident lifecycle with recovery',
  'Live dashboard',
] as const;

/** Only directions named in the final case study's production path. */
export const scopeNext = [
  'Governed, versioned baselines',
  'More FHIR resources',
  'Event-time monitoring',
  'Scalable streaming',
  'Alert routing',
  'Authentication, IAM and auditability',
  'CI/CD',
] as const;

export const prototypeStatement = 'Sentinel is a controlled data-observability prototype, not a production clinical system.';
export const healthStatement = 'Sentinel monitors data health, not patient health.';
