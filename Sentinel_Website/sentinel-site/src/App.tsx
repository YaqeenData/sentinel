import {Navigate, Route, Routes} from 'react-router-dom';
import {Layout} from './components/Layout';
import {CaseStudyPage} from './pages/CaseStudyPage';
import {DemoPage} from './pages/DemoPage';
import {HomePage} from './pages/HomePage';
import {TeamPage} from './pages/TeamPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/case-study" element={<CaseStudyPage />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/team" element={<TeamPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
