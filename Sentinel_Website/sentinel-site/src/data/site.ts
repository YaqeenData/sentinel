export type TeamMember = {
  name: string;
  role: string;
  linkedin?: string;
  portfolio?: string;
};

export const siteConfig = {
  projectName: 'Sentinel',
  tagline: 'The pipeline is green — but is the data healthy?',
  description:
    'A healthcare-aware data observability project that monitors streaming FHIR data for structural issues, missingness, distribution drift, and abnormal volume while the pipeline continues to run.',
  year: '2026',
  teamSize: 4,
  liveDashboardUrl: '', // Add ngrok / permanent dashboard URL later.
  demoVideoUrl: '', // Add hosted demo video URL later.
  repositoryUrl: '', // Add the public GitHub repository URL if/when you want to expose it.
};

export const detectors = [
  {
    name: 'Contract',
    question: 'Does the data follow the structure and rules we expect?',
    detail: 'Required fields, allowed values, expected types, and value/type consistency.',
  },
  {
    name: 'Missingness',
    question: 'Are important values disappearing?',
    detail: 'Tracks changes in null rates against healthy historical behavior.',
  },
  {
    name: 'Numeric Drift',
    question: 'Are numeric values behaving differently?',
    detail: 'Compares current and historical numeric distributions using the KS statistic.',
  },
  {
    name: 'Categorical Drift',
    question: 'Are category proportions changing?',
    detail: 'Uses Jensen–Shannon distance to compare categorical distributions.',
  },
  {
    name: 'Volume',
    question: 'Are we receiving the amount of data we normally expect?',
    detail: 'Uses robust expected volume with median, MAD, and percentage guardrails.',
  },
];

export const resources = [
  {
    name: 'Patient',
    description: 'Patient-level FHIR data with resource-specific quality expectations.',
  },
  {
    name: 'Encounter',
    description: 'Healthcare interactions, timing, class, references, and volume behavior.',
  },
  {
    name: 'Observation',
    description: 'Clinical measurements and coded observations monitored for quality and drift.',
  },
];

export const team: TeamMember[] = [
  {name: 'Yaqeen Alhalal', role: 'Team Lead & Data Engineer', linkedin: 'https://www.linkedin.com/in/yaqeen-alhalal-8388541a3/', portfolio: 'https://www.yaqeenalhalal.dev'},
  {name: 'Sama Alharbi', role: 'Data Engineer', linkedin: 'https://www.linkedin.com/in/sama-a-831753201/', portfolio: 'https://samaalharbi2.github.io/'},
  {name: 'Sarah Masshi', role: 'Data Engineer', linkedin: 'https://www.linkedin.com/in/sarah-maashi-5baa26282?utm_source=share_via&utm_content=profile&utm_medium=member_ios',},
  {name: 'Rutanah Maghrabi', role: 'Data Engineer', linkedin: 'https://www.linkedin.com/in/rutanah-maghrabi-22b3201b2'},
];
