import { useState, useEffect } from 'react';
import { api } from '../api';
import type { CentralityResult } from '../types';

export default function CentralityView() {
  const [result, setResult] = useState<CentralityResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.centrality(30)
      .then(setResult)
      .finally(() => setLoading(false));
  }, []);

  const maxTransitive = result
    ? Math.max(...result.packages.map((p) => p.transitive_dependents), 1)
    : 1;

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>🎯 Centrality Analysis</h2>
          <p className="view-subtitle">Most depended-upon packages — single points of failure</p>
        </div>
      </div>

      {loading && <div className="loading-placeholder">Computing centrality...</div>}

      {result && !loading && (
        <div className="centrality-grid">
          {result.packages.map((pkg, i) => (
            <div key={pkg.name} className="centrality-card">
              <div className="centrality-rank">#{i + 1}</div>
              <div className="centrality-info">
                <div className="centrality-name">{pkg.name}</div>
                <div className="centrality-stats">
                  <span>{pkg.direct_dependents} direct</span>
                  <span className="divider">·</span>
                  <span className="transitive">{pkg.transitive_dependents} transitive</span>
                </div>
                <div className="centrality-bar-wrapper">
                  <div
                    className="centrality-bar"
                    style={{ width: `${(pkg.transitive_dependents / maxTransitive) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
