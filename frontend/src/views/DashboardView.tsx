import { useState, useEffect, useCallback } from 'react';
import GraphCanvas from '../components/GraphCanvas';
import StatCard from '../components/StatCard';
import { api } from '../api';
import type { GraphStats, PackageInfo } from '../types';
import type { CanvasData, CanvasNode } from '../canvas-types';

export default function DashboardView() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [graphData, setGraphData] = useState<CanvasData | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [nodeDetail, setNodeDetail] = useState<PackageInfo | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

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

  const handleNodeClick = useCallback(async (node: CanvasNode) => {
    const name = node.data?.name as string || null;
    setSelectedNode(name);
    if (name && node.labels?.includes('Package')) {
      try {
        const pkg = await api.getPackage(name);
        setNodeDetail(pkg);
      } catch {
        setNodeDetail(null);
      }
    } else {
      setNodeDetail(null);
    }
  }, []);

  // Filter graph data by search term (highlight matching nodes)
  const filteredData = graphData && searchTerm
    ? {
        ...graphData,
        nodes: graphData.nodes.map(n => ({
          ...n,
          color: (n.data?.name as string || '').toLowerCase().includes(searchTerm.toLowerCase())
            ? '#FFD93D'
            : n.color,
        })),
      }
    : graphData;

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

        <div className="graph-toolbar">
          <input
            type="text"
            placeholder="🔍 Search nodes..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <div className="graph-legend">
            <span className="legend-item"><span className="legend-dot" style={{ background: '#4ECDC4' }} /> Package</span>
            <span className="legend-item"><span className="legend-dot" style={{ background: '#FF6B6B' }} /> Vulnerability</span>
            <span className="legend-item"><span className="legend-dot" style={{ background: '#45B7D1' }} /> Maintainer</span>
            {searchTerm && <span className="legend-item"><span className="legend-dot" style={{ background: '#FFD93D' }} /> Match</span>}
          </div>
        </div>

        {loading ? (
          <div className="loading-placeholder">Loading graph...</div>
        ) : (
          <GraphCanvas
            data={filteredData}
            selectedNode={selectedNode}
            onNodeClick={handleNodeClick}
          />
        )}

        {nodeDetail && (
          <div className="node-detail-panel">
            <h4>📦 {nodeDetail.name}</h4>
            <div className="detail-row"><span className="detail-label">Version</span><span>{nodeDetail.version}</span></div>
            <div className="detail-row"><span className="detail-label">License</span><span>{nodeDetail.license}</span></div>
            <div className="detail-row"><span className="detail-label">Downloads</span><span>{nodeDetail.downloads.toLocaleString()}</span></div>
            <div className="detail-row"><span className="detail-label">Description</span><span>{nodeDetail.description}</span></div>
          </div>
        )}
      </div>
    </div>
  );
}
