import { useState, useCallback } from 'react';
import { api } from '../api';
import type { IngestResult } from '../types';

export default function ImportView() {
  const [registry, setRegistry] = useState<'npm' | 'pypi'>('npm');
  const [packageName, setPackageName] = useState('');
  const [depth, setDepth] = useState(3);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleIngest = useCallback(async () => {
    if (!packageName.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = registry === 'npm'
        ? await api.ingestNpm(packageName.trim(), depth)
        : await api.ingestPypi(packageName.trim(), depth);
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ingestion failed');
    } finally {
      setLoading(false);
    }
  }, [registry, packageName, depth]);

  // SBOM Import
  const [sbomFile, setSbomFile] = useState<File | null>(null);
  const [sbomResult, setSbomResult] = useState<IngestResult | null>(null);
  const [sbomLoading, setSbomLoading] = useState(false);

  const handleSBOMImport = useCallback(async () => {
    if (!sbomFile) return;
    setSbomLoading(true);
    setError(null);
    try {
      const text = await sbomFile.text();
      const data = JSON.parse(text);
      const r = await api.importSBOM(data);
      setSbomResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'SBOM import failed');
    } finally {
      setSbomLoading(false);
    }
  }, [sbomFile]);

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>Import Packages</h2>
          <p className="view-subtitle">Ingest real packages from npm/PyPI or import an SBOM</p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* Registry Import */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h3>📦 Registry Import</h3>
        <p style={{ color: '#94a3b8', marginBottom: '1rem' }}>
          Fetch a real package and its transitive dependencies from npm or PyPI.
        </p>

        <div className="form-row">
          <div className="form-group">
            <label>Registry</label>
            <select value={registry} onChange={(e) => setRegistry(e.target.value as 'npm' | 'pypi')}>
              <option value="npm">npm</option>
              <option value="pypi">PyPI</option>
            </select>
          </div>
          <div className="form-group" style={{ flex: 2 }}>
            <label>Package Name</label>
            <input
              type="text"
              value={packageName}
              onChange={(e) => setPackageName(e.target.value)}
              placeholder={registry === 'npm' ? 'e.g. express' : 'e.g. requests'}
              onKeyDown={(e) => e.key === 'Enter' && handleIngest()}
            />
          </div>
          <div className="form-group">
            <label>Max Depth</label>
            <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ alignSelf: 'flex-end' }}>
            <button className="btn btn-primary" onClick={handleIngest} disabled={loading || !packageName.trim()}>
              {loading ? 'Fetching...' : '🔍 Ingest'}
            </button>
          </div>
        </div>

        {result && (
          <div className="result-banner success-banner-green">
            ✅ Ingested <strong>{result.packages}</strong> packages and <strong>{result.dependencies}</strong> dependencies
            {result.errors ? <span> ({result.errors} errors)</span> : null}
          </div>
        )}
      </div>

      {/* SBOM Import */}
      <div className="card">
        <h3>📋 SBOM Import</h3>
        <p style={{ color: '#94a3b8', marginBottom: '1rem' }}>
          Import a CycloneDX or SPDX JSON file to populate the graph.
        </p>

        <div className="form-row">
          <div className="form-group" style={{ flex: 2 }}>
            <label>SBOM File (JSON)</label>
            <input
              type="file"
              accept=".json"
              onChange={(e) => setSbomFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="form-group" style={{ alignSelf: 'flex-end' }}>
            <button className="btn btn-primary" onClick={handleSBOMImport} disabled={sbomLoading || !sbomFile}>
              {sbomLoading ? 'Importing...' : '📥 Import'}
            </button>
          </div>
        </div>

        {sbomResult && (
          <div className="result-banner success-banner-green">
            ✅ Imported <strong>{sbomResult.packages}</strong> packages and <strong>{sbomResult.dependencies}</strong> dependencies
          </div>
        )}
      </div>
    </div>
  );
}
