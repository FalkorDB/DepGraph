import { useState, useEffect, useCallback, useRef } from 'react';
import GraphCanvas from '../components/GraphCanvas';
import PackageSelector from '../components/PackageSelector';
import { api } from '../api';
import type { BlastRadiusResult } from '../types';
import type { CanvasData } from '../canvas-types';

export default function BlastRadiusView() {
  const [packages, setPackages] = useState<string[]>([]);
  const [selected, setSelected] = useState('');
  const [result, setResult] = useState<BlastRadiusResult | null>(null);
  const [graphData, setGraphData] = useState<CanvasData | null>(null);
  const [loading, setLoading] = useState(false);
  const analyzeReqId = useRef(0);

  useEffect(() => {
    api.packages(500).then((pkgs) => setPackages(pkgs.map((p) => p.name)));
  }, []);

  const analyze = useCallback(async (name: string) => {
    if (!name) return;
    const reqId = ++analyzeReqId.current;
    setSelected(name);
    setLoading(true);
    try {
      const [br, gd] = await Promise.all([
        api.blastRadius(name),
        api.graphBlastRadius(name),
      ]);
      if (reqId !== analyzeReqId.current) return;
      setResult(br);
      setGraphData(gd as CanvasData);
    } catch {
      if (reqId !== analyzeReqId.current) return;
      setResult(null);
      setGraphData(null);
    } finally {
      if (reqId === analyzeReqId.current) setLoading(false);
    }
  }, []);

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>💥 Blast Radius Analysis</h2>
          <p className="view-subtitle">What breaks if this package has a vulnerability?</p>
        </div>
      </div>

      <PackageSelector
        packages={packages}
        selected={selected}
        onSelect={analyze}
        label="Analyze package"
      />

      {loading && <div className="loading-placeholder">Analyzing...</div>}

      {result && !loading && (
        <>
          <div className="result-summary">
            <div className="result-stat">
              <span className="result-stat-value">{result.total_affected}</span>
              <span className="result-stat-label">Affected packages</span>
            </div>
            <div className="result-stat">
              <span className="result-stat-value">{result.max_depth}</span>
              <span className="result-stat-label">Max propagation depth</span>
            </div>
          </div>

          <div className="graph-section">
            <h3>Impact Subgraph</h3>
            <GraphCanvas
              data={graphData}
              selectedNode={selected}
              onNodeClick={(node) => analyze(node.data?.name as string)}
            />
          </div>

          {result.affected_packages.length > 0 && (
            <div className="table-section">
              <h3>Affected Packages</h3>
              <table className="data-table">
                <thead>
                  <tr><th>Package</th><th>Depth</th><th>Dependency Chain</th></tr>
                </thead>
                <tbody>
                  {result.affected_packages.map((ap) => (
                    <tr key={ap.name} onClick={() => analyze(ap.name)} className="clickable-row">
                      <td className="pkg-name">{ap.name}</td>
                      <td className="center">{ap.depth}</td>
                      <td className="chain">{ap.path.join(' → ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
