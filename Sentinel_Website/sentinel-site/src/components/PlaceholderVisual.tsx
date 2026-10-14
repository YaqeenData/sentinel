import {Image as ImageIcon, Video} from 'lucide-react';

export function PlaceholderVisual({title, description, kind = 'image'}: {title: string; description: string; kind?: 'image' | 'video'}) {
  const Icon = kind === 'video' ? Video : ImageIcon;
  return (
    <div className="placeholder-visual">
      <div className="placeholder-icon"><Icon size={24} /></div>
      <strong>{title}</strong>
      <p>{description}</p>
      <small>Replace this placeholder when the final asset is ready.</small>
    </div>
  );
}
