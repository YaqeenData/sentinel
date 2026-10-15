import {Moon, Sun} from 'lucide-react';
import {useEffect, useState} from 'react';

type Theme = 'light' | 'dark';

const initialTheme = (): Theme => {
  const stored = localStorage.getItem('sentinel-theme') as Theme | null;
  if (stored === 'light' || stored === 'dark') return stored;
  return 'dark'; // dark is the primary experience; light is opt-in via the toggle
};

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('sentinel-theme', theme);
  }, [theme]);

  const next = theme === 'dark' ? 'light' : 'dark';

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
    </button>
  );
}
