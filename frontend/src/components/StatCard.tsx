interface StatCardProps {
  label: string;
  value: number | string;
  icon: string;
  color?: string;
}

export default function StatCard({ label, value, icon, color = '#4ECDC4' }: StatCardProps) {
  return (
    <div className="stat-card" style={{ borderTopColor: color }}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-content">
        <div className="stat-value">{typeof value === 'number' ? value.toLocaleString() : value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}
