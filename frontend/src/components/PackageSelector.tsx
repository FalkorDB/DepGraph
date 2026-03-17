import { useState, useEffect } from 'react';

interface PackageSelectorProps {
  packages: string[];
  selected: string;
  onSelect: (name: string) => void;
  label?: string;
}

export default function PackageSelector({
  packages,
  selected,
  onSelect,
  label = 'Select Package',
}: PackageSelectorProps) {
  const [filter, setFilter] = useState('');
  const [open, setOpen] = useState(false);

  const filtered = packages.filter((p) =>
    p.toLowerCase().includes(filter.toLowerCase())
  );

  useEffect(() => {
    const handleClick = () => setOpen(false);
    if (open) document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [open]);

  return (
    <div className="package-selector" onClick={(e) => e.stopPropagation()}>
      <label className="selector-label">{label}</label>
      <div className="selector-input-wrapper">
        <input
          className="selector-input"
          type="text"
          value={open ? filter : selected}
          placeholder="Type to search..."
          onFocus={() => { setOpen(true); setFilter(''); }}
          onChange={(e) => setFilter(e.target.value)}
        />
        {open && filtered.length > 0 && (
          <ul className="selector-dropdown">
            {filtered.slice(0, 30).map((name) => (
              <li
                key={name}
                className={`selector-option ${name === selected ? 'selected' : ''}`}
                onClick={() => { onSelect(name); setOpen(false); setFilter(''); }}
              >
                {name}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
