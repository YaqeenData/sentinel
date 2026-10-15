import {asset, siteConfig} from '../data/site';

/** Product-demo player. No autoplay, no sound until the viewer chooses. */
export function DemoVideo({id}: {id?: string}) {
  const {src, poster} = siteConfig.demoVideo;
  return (
    <figure className="rd-video" id={id}>
      <div className="rd-video-frame">
        <video
          controls
          playsInline
          preload="metadata"
          poster={asset(poster)}
          width={1920}
          height={1080}
          aria-label="Sentinel product demo: healthy monitoring, detection, investigation and recovery"
        >
          <source src={asset(src)} type="video/mp4" />
          Your browser cannot play this video.{' '}
          <a href={asset(src)}>Download the Sentinel product demo (MP4)</a>.
        </video>
      </div>
      <figcaption>
        1 min 37 s · Healthy → volume drop → recovery → critical contract failure → recovery, with short on-screen notes. Synthetic data only.
      </figcaption>
    </figure>
  );
}
