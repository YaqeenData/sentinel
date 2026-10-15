/**
 * Central project links and site-wide config.
 * Change a URL here and the whole site follows. Never paste these URLs into components.
 */
export const REPOSITORY_URL = 'https://github.com/yaqeendata/sentinel';

/** Resolve a file under public/assets/ so it works with the Vite base path (GitHub Pages). */
export const asset = (path: string) => `${import.meta.env.BASE_URL}assets/${path}`;

export const siteConfig = {
  projectName: 'Sentinel',
  tagline: 'The pipeline is green… but is the data healthy?',
  description:
    'Sentinel monitors streaming healthcare data for quality problems that can stay invisible while the pipeline, database and dashboards keep working. A controlled prototype on synthetic data.',
  year: '2026',
  repositoryUrl: REPOSITORY_URL,
  demoVideo: {
    src: 'demo/sentinel-product-demo.mp4',
    poster: 'demo/sentinel-demo-poster.webp',
  },
  /** Final system architecture, taken from the final case study. */
  architecture: {
    file: 'architecture/sentinel-architecture-final.webp',
    width: 1933,
    height: 705,
  },
};

export type TeamMember = {
  name: string;
  role: string;
  /** One line, taken from the final case study's project-level contribution summary. */
  contribution: string;
  linkedin?: string;
  portfolio?: string;
};

/** Single source for team data. Portfolio links exist only where one was provided. */
export const team: TeamMember[] = [
  {
    name: 'Yaqeen Alhalal',
    role: 'Team Lead & Data Engineer',
    contribution: 'Project leadership, data engineering, system integration, and observability/product design.',
    linkedin: 'https://www.linkedin.com/in/yaqeen-alhalal-8388541a3/',
    portfolio: 'https://www.yaqeenalhalal.dev',
  },
  {
    name: 'Sama Alharbi',
    role: 'Data Engineer',
    contribution: 'Data engineering implementation, integration, testing, and project delivery.',
    linkedin: 'https://www.linkedin.com/in/sama-a-831753201/',
    portfolio: 'https://samaalharbi2.github.io/',
  },
  {
    name: 'Sarah Masshi',
    role: 'Data Engineer',
    contribution: 'Data engineering implementation, testing, validation, and project delivery.',
    linkedin:
      'https://www.linkedin.com/in/sarah-maashi-5baa26282?utm_source=share_via&utm_content=profile&utm_medium=member_ios',
  },
  {
    name: 'Rutanah Maghrabi',
    role: 'Data Engineer',
    contribution: 'Data engineering implementation, testing, integration, and project delivery.',
    linkedin: 'https://www.linkedin.com/in/rutanah-maghrabi-22b3201b2',
  },
];

export const teamNote =
  'Contributions are summarized at project level; responsibilities overlapped across the shared capstone delivery.';
