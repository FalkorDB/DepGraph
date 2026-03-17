/** Type declarations for @falkordb/canvas web component. */

export interface FalkorDBCanvasElement extends HTMLElement {
  setData(data: CanvasData): void;
  getData(): CanvasData;
  setConfig(config: CanvasConfig): void;
  setWidth(width: number): void;
  setHeight(height: number): void;
  setBackgroundColor(color: string): void;
  setForegroundColor(color: string): void;
  setIsLoading(loading: boolean): void;
  zoomToFit(padding?: number): void;
  getGraph(): unknown;
}

export interface CanvasNode {
  id: number;
  labels: string[];
  color: string;
  visible: boolean;
  size?: number;
  caption?: string;
  data: Record<string, unknown>;
}

export interface CanvasLink {
  id: number;
  relationship: string;
  color: string;
  source: number;
  target: number;
  visible: boolean;
  data: Record<string, unknown>;
}

export interface CanvasData {
  nodes: CanvasNode[];
  links: CanvasLink[];
}

export interface CanvasConfig {
  width?: number;
  height?: number;
  backgroundColor?: string;
  foregroundColor?: string;
  cooldownTicks?: number;
  onNodeClick?: (node: CanvasNode, event: MouseEvent) => void;
  onNodeHover?: (node: CanvasNode | null) => void;
  onLinkClick?: (link: CanvasLink, event: MouseEvent) => void;
  onEngineStop?: () => void;
  isNodeSelected?: (node: CanvasNode) => boolean;
  isLinkSelected?: (link: CanvasLink) => boolean;
}
