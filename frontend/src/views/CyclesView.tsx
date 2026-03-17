import { useState, useEffect } from 'react';
import GraphCanvas from '../components/GraphCanvas';
import { api } from '../api';
import type { CycleResult } from '../types';
import type { CanvasData } from '../canvas-types';

export default function CyclesView() {
  const [result, setResult] = useState<CycleResult | null>(null);
  const [graphData, setGraphData] = useState<CanvasData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.cycles(), api.graphCycles()])
      .then(([cr, gd]) => {
        setResult(cr);
        setGraphData(gd as CanvasData);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>🔄 Circular Dependencies</h2>
          <p className="view-subtitle">Dependency cycles that may cause build or resolution issues</p>
        </div>
      </div>

      {loading && <div className="loading-placeholder">Detecting cycles...</div>}

      {result && !loading && (
        <>
          <div className="result-summary">
            <div className="result-stat">
              <span className="result-stat-value">{result.total_cycles}</span>
              <span className="result-stat-label">Cycles found</span>
            </div>
          </div>

          {result.total_cycles > 0 ? (
            <>
              <div className="graph-section">
                <h3>Cycle Subgraph</h3>
                <GraphCanvas data={graphData} />
              </div>

              <div className="table-section">
                <h3>Detected Cycles</h3>
                <div className="cycle-list">
                  {result.cycles.map((cycle, i) => (
                    <div key={i} className="cycle-card">
                      <span className="cycle-number">Cycle {i + 1}</span>
                      <span className="cycle-chain">
                        {cycle.join(' → ')} → {cycle[0]}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="success-banner">🎉 No circular dependencies found!</div>
          )}
        </>
      )}
    </div>
  );
}
