import { useState, useEffect, useCallback } from 'react';
import GraphCanvas from '../components/GraphCanvas';
import StatCard from '../components/StatCard';
import { api } from '../api';
import type { GraphStats } from '../types';
import type { CanvasData } from '../canvas-types';

export default function DashboardView() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [graphData, setGraphData] = useState<CanvasData | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, g] = await Promise.all([api.stats(), api.graphData()]);
      setStats(s);
      setGraphData(g as CanvasData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await api.seed(80);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to seed');
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>Dashboard</h2>
          <p className="view-subtitle">Overview of the package dependency graph</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleSeed}
          disabled={seeding}
        >
          {seeding ? 'Seeding...' : '🌱 Seed Graph'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {stats && (
        <div className="stat-grid">
          <StatCard label="Packages" value={stats.packages} icon="📦" color="#4ECDC4" />
          <StatCard label="Dependencies" value={stats.dependencies} icon="🔗" color="#45B7D1" />
          <StatCard label="Vulnerabilities" value={stats.vulnerabilities} icon="🛡️" color="#FF6B6B" />
          <StatCard label="Maintainers" value={stats.maintainers} icon="👤" color="#FFD93D" />
        </div>
      )}

      <div className="graph-section">
        <h3>
          Full Dependency Graph
          {selectedNode && <span className="selected-badge">Selected: {selectedNode}</span>}
        </h3>
        {loading ? (
          <div className="loading-placeholder">Loading graph...</div>
        ) : (
          <GraphCanvas
            data={graphData}
            selectedNode={selectedNode}
            onNodeClick={(node) => setSelectedNode(node.data?.name as string || null)}
          />
        )}
      </div>
    </div>
  );
}
