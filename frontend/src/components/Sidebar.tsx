import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/blast-radius', label: 'Blast Radius', icon: '💥' },
  { to: '/cycles', label: 'Cycles', icon: '🔄' },
  { to: '/centrality', label: 'Centrality', icon: '🎯' },
  { to: '/licenses', label: 'Licenses', icon: '📜' },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">📦 DepGraph</h1>
        <p className="sidebar-subtitle">Dependency Impact Analyzer</p>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'nav-item-active' : ''}`
            }
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <p>Powered by FalkorDB</p>
      </div>
    </aside>
  );
}
