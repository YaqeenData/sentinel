import {useRef, useState} from 'react';
import type {KeyboardEvent} from 'react';
import {journey} from '../data/content';
import {Shot} from './Shot';

/**
 * Monitor → Detect → Investigate → Track as one tabbed product story.
 * One large real screenshot at a time (fixed 16:9 frame, so no layout shift), keyboard-operable tabs.
 */
export function ProductJourney() {
  const [active, setActive] = useState(0);
  const tabs = useRef<Array<HTMLButtonElement | null>>([]);
  const step = journey[active];

  const move = (next: number) => {
    const i = (next + journey.length) % journey.length;
    setActive(i);
    tabs.current[i]?.focus();
  };

  const onKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); move(active + 1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); move(active - 1); }
    if (e.key === 'Home') { e.preventDefault(); move(0); }
    if (e.key === 'End') { e.preventDefault(); move(journey.length - 1); }
  };

  return (
    <div className="rf-journey">
      <div className="rf-tabs" role="tablist" aria-label="Sentinel product journey">
        {journey.map((s, i) => (
          <button
            key={s.id}
            ref={(el) => { tabs.current[i] = el; }}
            id={`journey-tab-${s.id}`}
            role="tab"
            type="button"
            aria-selected={i === active}
            aria-controls="journey-panel"
            tabIndex={i === active ? 0 : -1}
            className={i === active ? 'rf-tab is-active' : 'rf-tab'}
            onClick={() => setActive(i)}
            onKeyDown={onKey}
          >
            <span className="rf-tab-n">{String(i + 1).padStart(2, '0')}</span>
            {s.label}
          </button>
        ))}
      </div>
      <div id="journey-panel" role="tabpanel" aria-labelledby={`journey-tab-${step.id}`} className="rf-journey-panel">
        <Shot
          key={step.id}
          file={step.file}
          alt={step.alt}
          state={step.state}
          tone={step.tone}
          eager={active === 0}
        />
        <p className="rf-journey-caption"><strong>{step.title.slice(5)}.</strong> {step.caption}</p>
      </div>
    </div>
  );
}
