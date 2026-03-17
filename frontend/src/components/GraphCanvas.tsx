import { useEffect, useRef, useCallback } from 'react';
import '@falkordb/canvas';
import type { FalkorDBCanvasElement, CanvasData, CanvasNode } from '../canvas-types';

declare module 'react' {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      'falkordb-canvas': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>;
    }
  }
}

interface GraphCanvasProps {
  data: CanvasData | null;
  onNodeClick?: (node: CanvasNode) => void;
  selectedNode?: string | null;
  width?: number;
  height?: number;
  className?: string;
}

export default function GraphCanvas({
  data,
  onNodeClick,
  selectedNode,
  width,
  height,
  className = '',
}: GraphCanvasProps) {
  const canvasRef = useRef<FalkorDBCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleResize = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const rect = container.getBoundingClientRect();
    canvas.setWidth(width ?? rect.width);
    canvas.setHeight(height ?? rect.height);
  }, [width, height]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.setConfig({
      backgroundColor: '#0f172a',
      foregroundColor: '#e2e8f0',
      cooldownTicks: 200,
      onNodeClick: (node: CanvasNode) => {
        onNodeClick?.(node);
      },
      isNodeSelected: (node: CanvasNode) => {
        if (!selectedNode) return false;
        return node.data?.name === selectedNode;
      },
    });

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [onNodeClick, selectedNode, handleResize]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data) return;
    canvas.setData(data);
    const timer = window.setTimeout(() => canvas.zoomToFit(1.2), 800);
    return () => window.clearTimeout(timer);
  }, [data]);

  return (
    <div ref={containerRef} className={`graph-canvas-container ${className}`}>
      {!data ? (
        <div className="graph-placeholder">
          <p>No graph data loaded. Seed the database first.</p>
        </div>
      ) : (
        <falkordb-canvas
          ref={canvasRef}
          style={{ width: '100%', height: '100%', display: 'block' }}
        />
      )}
    </div>
  );
}
