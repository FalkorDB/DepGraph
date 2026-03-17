import { useState, useCallback } from 'react';
import { api } from '../api';
import type { VulnScanResult, VulnEntry } from '../types';

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
};

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className="badge"
      style={{
        backgroundColor: SEVERITY_COLORS[severity] ?? '#64748b',
        color: '#fff',
        padding: '2px 8px',
        borderRadius: '4px',
        fontSize: '0.75rem',
        fontWeight: 600,
        textTransform: 'uppercase',
      }}
    >
      {severity}
    </span>
  );
}

export default function VulnerabilitiesView() {
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<VulnScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScanAll = useCallback(async () => {
    setScanning(true);
    setError(null);
    try {
      const r = await api.scanAll();
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan failed');
    } finally {
      setScanning(false);
    }
  }, []);

  const groupBySeverity = (vulns: VulnEntry[]) => {
    const groups: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    vulns.forEach((v) => {
      const s = v.severity.toLowerCase();
      groups[s] = (groups[s] || 0) + 1;
    });
    return groups;
  };

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>Vulnerability Scanner</h2>
          <p className="view-subtitle">Scan packages against the OSV.dev vulnerability database</p>
        </div>
        <button className="btn btn-primary" onClick={handleScanAll} disabled={scanning}>
          {scanning ? '🔍 Scanning...' : '🛡️ Scan All Packages'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {result && (
        <>
          <div className="stat-grid">
            <div className="stat-card" style={{ borderLeftColor: '#4ECDC4' }}>
              <div className="stat-value">{result.packages_scanned}</div>
              <div className="stat-label">Packages Scanned</div>
            </div>
            <div className="stat-card" style={{ borderLeftColor: result.vulnerabilities_found > 0 ? '#ef4444' : '#22c55e' }}>
              <div className="stat-value">{result.vulnerabilities_found}</div>
              <div className="stat-label">Vulnerabilities Found</div>
            </div>
            {(() => {
              const groups = groupBySeverity(result.vulnerabilities);
              return (
                <>
                  <div className="stat-card" style={{ borderLeftColor: '#ef4444' }}>
                    <div className="stat-value">{groups.critical}</div>
                    <div className="stat-label">Critical</div>
                  </div>
                  <div className="stat-card" style={{ borderLeftColor: '#f97316' }}>
                    <div className="stat-value">{groups.high}</div>
                    <div className="stat-label">High</div>
                  </div>
                </>
              );
            })()}
          </div>

          {result.vulnerabilities.length > 0 ? (
            <div className="card" style={{ marginTop: '1.5rem' }}>
              <h3>Vulnerability Details</h3>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Severity</th>
                      <th>Package</th>
                      <th>Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.vulnerabilities.map((v, i) => (
                      <tr key={`${v.id}-${i}`}>
                        <td><code>{v.id}</code></td>
                        <td><SeverityBadge severity={v.severity} /></td>
                        <td>{v.package}</td>
                        <td style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {v.summary}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="result-banner success-banner" style={{ marginTop: '1.5rem' }}>
              ✅ No vulnerabilities found! Your dependency graph is clean.
            </div>
          )}
        </>
      )}

      {!result && !scanning && (
        <div className="card" style={{ marginTop: '1.5rem', textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.2rem', color: '#94a3b8' }}>
            Click "Scan All Packages" to check every package in the graph against the
            <a href="https://osv.dev" target="_blank" rel="noopener" style={{ color: '#4ECDC4', marginLeft: '4px' }}>
              OSV.dev
            </a> vulnerability database.
          </p>
        </div>
      )}
    </div>
  );
}
