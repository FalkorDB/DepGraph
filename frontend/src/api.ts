/** API client for the DepGraph backend. */

const BASE = '/api';

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

async function postJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' });
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
  LicenseReport,
  PackageInfo,
} from './types';

export const api = {
  health: () => fetchJSON<HealthResponse>('/health'),
  stats: () => fetchJSON<GraphStats>('/stats'),
  packages: (limit = 200) => fetchJSON<PackageInfo[]>(`/packages?limit=${limit}`),
  searchPackages: (q: string) => fetchJSON<PackageInfo[]>(`/packages/search?q=${q}`),
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
};
