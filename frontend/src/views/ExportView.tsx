import { useState, useCallback } from 'react';
import { api } from '../api';

export default function ExportView() {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = useCallback(async (format: 'cyclonedx' | 'spdx') => {
    setExporting(true);
    setError(null);
    try {
      const data = format === 'cyclonedx'
        ? await api.exportCycloneDX()
        : await api.exportSPDX();

      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `depgraph-sbom-${format}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  }, []);

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>SBOM Export</h2>
          <p className="view-subtitle">Export the dependency graph as a Software Bill of Materials</p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="export-grid">
        <div className="card export-card">
          <div className="export-icon">📋</div>
          <h3>CycloneDX 1.5</h3>
          <p style={{ color: '#94a3b8', marginBottom: '1.5rem' }}>
            Industry-standard SBOM format. Includes all packages, versions, licenses,
            and the complete dependency tree.
          </p>
          <ul className="export-features">
            <li>✅ Component inventory with purls</li>
            <li>✅ Dependency graph (dependsOn)</li>
            <li>✅ License information</li>
            <li>✅ Tool metadata</li>
          </ul>
          <button
            className="btn btn-primary"
            onClick={() => handleExport('cyclonedx')}
            disabled={exporting}
            style={{ marginTop: '1rem', width: '100%' }}
          >
            {exporting ? 'Exporting...' : '⬇️ Download CycloneDX JSON'}
          </button>
        </div>

        <div className="card export-card">
          <div className="export-icon">📄</div>
          <h3>SPDX 2.3</h3>
          <p style={{ color: '#94a3b8', marginBottom: '1.5rem' }}>
            Linux Foundation SBOM standard. Recognized by NTIA and used for
            regulatory compliance.
          </p>
          <ul className="export-features">
            <li>✅ Package list with SPDX IDs</li>
            <li>✅ DEPENDS_ON relationships</li>
            <li>✅ License concluded/declared</li>
            <li>✅ Creation info & namespace</li>
          </ul>
          <button
            className="btn btn-primary"
            onClick={() => handleExport('spdx')}
            disabled={exporting}
            style={{ marginTop: '1rem', width: '100%' }}
          >
            {exporting ? 'Exporting...' : '⬇️ Download SPDX JSON'}
          </button>
        </div>
      </div>
    </div>
  );
}
