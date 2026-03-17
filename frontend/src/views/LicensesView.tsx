import { useState, useEffect, useCallback } from 'react';
import PackageSelector from '../components/PackageSelector';
import { api } from '../api';
import type { LicenseReport } from '../types';

const RISK_COLORS: Record<string, string> = {
  strong_copyleft: '#FF6B6B',
  weak_copyleft: '#FFD93D',
  permissive: '#4ECDC4',
  unknown: '#888888',
};

export default function LicensesView() {
  const [packages, setPackages] = useState<string[]>([]);
  const [selected, setSelected] = useState('');
  const [result, setResult] = useState<LicenseReport | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.packages(500).then((pkgs) => setPackages(pkgs.map((p) => p.name)));
  }, []);

  const analyze = useCallback(async (name: string) => {
    if (!name) return;
    setSelected(name);
    setLoading(true);
    try {
      setResult(await api.licenses(name));
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>📜 License Compatibility</h2>
          <p className="view-subtitle">Check transitive license propagation through dependencies</p>
        </div>
      </div>

      <PackageSelector
        packages={packages}
        selected={selected}
        onSelect={analyze}
        label="Check package"
      />

      {loading && <div className="loading-placeholder">Checking licenses...</div>}

      {result && !loading && (
        <>
          <div className="result-summary">
            <div className="result-stat">
              <span className="result-stat-value">{result.total_dependencies_checked}</span>
              <span className="result-stat-label">Dependencies checked</span>
            </div>
            <div className="result-stat">
              <span className="result-stat-value" style={{ color: result.issues.length > 0 ? '#FF6B6B' : '#4ECDC4' }}>
                {result.issues.length}
              </span>
              <span className="result-stat-label">Issues found</span>
            </div>
          </div>

          {result.issues.length > 0 ? (
            <div className="table-section">
              <h3>⚠️ License Issues</h3>
              <table className="data-table">
                <thead>
                  <tr><th>Package</th><th>License</th><th>Risk</th><th>Via</th></tr>
                </thead>
                <tbody>
                  {result.issues.map((issue) => (
                    <tr key={issue.package}>
                      <td className="pkg-name">{issue.package}</td>
                      <td><code>{issue.license}</code></td>
                      <td>
                        <span className="risk-badge" style={{ backgroundColor: RISK_COLORS[issue.risk] || '#888' }}>
                          {issue.risk.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="chain">{issue.dependency_chain.join(' → ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="success-banner">✅ No copyleft license issues found!</div>
          )}
        </>
      )}
    </div>
  );
}
