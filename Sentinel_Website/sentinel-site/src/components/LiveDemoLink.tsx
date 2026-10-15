import {ExternalLink} from 'lucide-react';
import type {ReactNode} from 'react';
import {siteConfig} from '../data/site';

type Props = {
  variant?: 'primary' | 'secondary' | 'ghost';
  children?: ReactNode;
  className?: string;
};

/** The single component that renders the Live Demo link. URL lives in data/site.ts. */
export function LiveDemoLink({variant = 'primary', children = 'Live Demo', className = ''}: Props) {
  return (
    <a
      className={`button ${variant} ${className}`.trim()}
      href={siteConfig.liveDemoUrl}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children} <ExternalLink size={15} aria-hidden="true" />
    </a>
  );
}
