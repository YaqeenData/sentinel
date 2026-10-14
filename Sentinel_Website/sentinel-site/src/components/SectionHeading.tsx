import type {ReactNode} from 'react';

export function SectionHeading({eyebrow, title, children}: {eyebrow: string; title: string; children?: ReactNode}) {
  return (
    <div className="section-heading">
      <span className="eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {children ? <div className="section-intro">{children}</div> : null}
    </div>
  );
}
