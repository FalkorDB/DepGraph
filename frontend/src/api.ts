/** API client for the DepGraph backend. */

const BASE = '';

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

async function postJSON<T>(path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = { method: 'POST' };
  if (body !== undefined) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

import type {
  BlastRadiusResult,
  CentralityResult,
  CycleResult,
  DepthResult,
  GraphData,
  GraphStats,
  HealthResponse,
  IngestResult,
  LicenseReport,
  PackageInfo,
  VulnScanResult,
} from './types';

export const api = {
  // Existing
  health: () => fetchJSON<HealthResponse>('/health'),
  stats: () => fetchJSON<GraphStats>('/stats'),
  packages: (limit = 200) => fetchJSON<PackageInfo[]>(`/packages?limit=${limit}`),
  searchPackages: (q: string) => fetchJSON<PackageInfo[]>(`/packages/search?q=${encodeURIComponent(q)}`),
  getPackage: (name: string) => fetchJSON<PackageInfo>(`/packages/${encodeURIComponent(name)}`),
  blastRadius: (name: string) => fetchJSON<BlastRadiusResult>(`/analysis/blast-radius/${encodeURIComponent(name)}`),
  cycles: (limit = 20) => fetchJSON<CycleResult>(`/analysis/cycles?limit=${limit}`),
  centrality: (limit = 20) => fetchJSON<CentralityResult>(`/analysis/centrality?limit=${limit}`),
  licenses: (name: string) => fetchJSON<LicenseReport>(`/analysis/licenses/${encodeURIComponent(name)}`),
  depth: (name: string) => fetchJSON<DepthResult>(`/analysis/depth/${encodeURIComponent(name)}`),
  graphData: () => fetchJSON<GraphData>('/graph/data'),
  graphBlastRadius: (name: string) => fetchJSON<GraphData>(`/graph/blast-radius/${encodeURIComponent(name)}`),
  graphCycles: () => fetchJSON<GraphData>('/graph/cycles'),
  seed: (n = 80) => postJSON<Record<string, number>>(`/seed?num_packages=${n}&clear=true`),

  // Registry ingestion
  ingestNpm: (name: string, depth = 3, includeDev = false) =>
    postJSON<IngestResult>(`/ingest/npm/${encodeURIComponent(name)}?max_depth=${depth}&include_dev=${includeDev}`),
  ingestPypi: (name: string, depth = 3, includeExtras = false) =>
    postJSON<IngestResult>(`/ingest/pypi/${encodeURIComponent(name)}?max_depth=${depth}&include_extras=${includeExtras}`),

  // SBOM
  exportCycloneDX: () => fetchJSON<Record<string, unknown>>('/sbom/cyclonedx'),
  exportSPDX: () => fetchJSON<Record<string, unknown>>('/sbom/spdx'),
  importSBOM: (data: Record<string, unknown>) => postJSON<IngestResult>('/sbom/import', data),

  // Vulnerability scanning
  scanAll: () => postJSON<VulnScanResult>('/vulnerabilities/scan'),
  scanPackage: (name: string, ecosystem = 'npm') =>
    fetchJSON<VulnScanResult>(`/vulnerabilities/scan/${encodeURIComponent(name)}?ecosystem=${ecosystem}`),
};
