/** API types matching the FastAPI backend. */

export interface PackageInfo {
  name: string;
  version: string;
  license: string;
  description: string;
  downloads: number;
}

export interface AffectedPackage {
  name: string;
  depth: number;
  path: string[];
}

export interface BlastRadiusResult {
  source_package: string;
  affected_packages: AffectedPackage[];
  total_affected: number;
  max_depth: number;
}

export interface CycleResult {
  cycles: string[][];
  total_cycles: number;
}

export interface PackageCentrality {
  name: string;
  direct_dependents: number;
  transitive_dependents: number;
}

export interface CentralityResult {
  packages: PackageCentrality[];
}

export interface LicenseIssue {
  package: string;
  license: string;
  risk: string;
  dependency_chain: string[];
}

export interface LicenseReport {
  root_package: string;
  issues: LicenseIssue[];
  total_dependencies_checked: number;
}

export interface DepthResult {
  package: string;
  max_depth: number;
  dependency_count: number;
  tree: Record<string, unknown>;
}

export interface GraphStats {
  packages: number;
  dependencies: number;
  vulnerabilities: number;
  maintainers: number;
}

export interface HealthResponse {
  status: string;
  falkordb_connected: boolean;
  graph_name: string;
  node_count: number;
  relationship_count: number;
}

import type { CanvasNode, CanvasLink } from './canvas-types';

export interface GraphData {
  nodes: CanvasNode[];
  links: CanvasLink[];
}
