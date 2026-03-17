import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import DashboardView from './views/DashboardView';
import BlastRadiusView from './views/BlastRadiusView';
import CyclesView from './views/CyclesView';
import CentralityView from './views/CentralityView';
import LicensesView from './views/LicensesView';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<DashboardView />} />
            <Route path="/blast-radius" element={<BlastRadiusView />} />
            <Route path="/cycles" element={<CyclesView />} />
            <Route path="/centrality" element={<CentralityView />} />
            <Route path="/licenses" element={<LicensesView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
