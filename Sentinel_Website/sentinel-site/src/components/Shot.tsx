import {asset} from '../data/site';
import {ZoomImage} from './ZoomImage';

export type Tone = 'healthy' | 'attention' | 'critical' | 'info';

type Props = {
  file: string;
  alt: string;
  caption?: string;
  state?: string;
  tone?: Tone;
  eager?: boolean;
  zoom?: boolean;
  className?: string;
};

/** A dashboard screenshot in a Sentinel window frame. 16:9, fixed size to avoid layout shift. */
export function Shot({file, alt, caption, state, tone = 'info', eager = false, zoom = true, className = ''}: Props) {
  const src = asset(`screenshots/${file}.webp`);
  const img = (
    <img
      src={src}
      alt={alt}
      width={1920}
      height={1080}
      loading={eager ? 'eager' : 'lazy'}
      decoding="async"
    />
  );
  return (
    <figure className={`rd-shot tone-${tone} ${className}`.trim()}>
      <div className="rd-shot-frame">
        {state ? <span className="rd-state">{state}</span> : null}
        {zoom ? (
          <ZoomImage label={alt} zoomed={<img src={src} alt={alt} width={1920} height={1080} />}>
            {img}
          </ZoomImage>
        ) : (
          img
        )}
      </div>
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  );
}
