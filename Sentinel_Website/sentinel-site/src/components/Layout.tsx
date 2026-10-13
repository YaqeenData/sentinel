import {ExternalLink, Menu, X} from 'lucide-react';
import {useState} from 'react';
import {NavLink, Outlet} from 'react-router-dom';
import {siteConfig} from '../data/site';
import {ThemeToggle} from './ThemeToggle';

const nav = [
  ['/', 'Overview'],
  ['/case-study', 'Case Study'],
  ['/demo', 'Demo'],
  ['/team', 'Team'],
] as const;

export function Layout() {
  const [open, setOpen] = useState(false);

  return (
    <div className="site-shell">
      <header className="site-header">
        <NavLink className="brand" to="/" onClick={() => setOpen(false)}>
          <img src="./assets/brand/sentinel-logo.svg" alt="Sentinel logo" />
          <span>
            <strong>Sentinel</strong>
            <small>Data Health Monitoring</small>
          </span>
        </NavLink>

        <button className="mobile-menu" type="button" onClick={() => setOpen((v) => !v)} aria-label="Toggle navigation">
          {open ? <X /> : <Menu />}
        </button>

        <nav className={open ? 'nav-links open' : 'nav-links'}>
          {nav.map(([to, label]) => (
            <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({isActive}) => (isActive ? 'active' : '')}>
              {label}
            </NavLink>
          ))}
          {siteConfig.liveDashboardUrl ? (
            <a className="nav-cta" href={siteConfig.liveDashboardUrl} target="_blank" rel="noreferrer">
              Live Dashboard <ExternalLink size={15} />
            </a>
          ) : (
            <span className="nav-cta disabled">Live Dashboard · soon</span>
          )}
          <ThemeToggle />
        </nav>
      </header>

      <main>
        <Outlet />
      </main>

      <footer className="site-footer">
        <div className="footer-brand">
          <img src="./assets/brand/sentinel-logo.svg" alt="" />
          <div>
            <strong>Sentinel</strong>
            <span>Healthcare-aware data observability</span>
          </div>
        </div>
        <p>Data Engineering Capstone · {siteConfig.year} · Built by a four-person team.</p>
      </footer>
    </div>
  );
}
