import {asset, siteConfig} from '../data/site';
import {ZoomImage} from './ZoomImage';

const alt =
  'Sentinel system architecture showing a live path (Synthea, HAPI FHIR, Python producer, Kafka, 60-second windows, Sentinel detection engine, PostgreSQL, Streamlit dashboard) and a historical reference path (Synthea historical synthetic FHIR data, Google Cloud Storage Bronze and Silver, learning what healthy data looks like) that feeds the detection engine.';

/** The final architecture diagram from the case study. Click to enlarge; the dialog scrolls sideways on phones. */
export function ArchitectureFigure() {
  const {file, width, height} = siteConfig.architecture;
  const src = asset(file);
  return (
    <figure className="rf-arch">
      <ZoomImage label="Sentinel system architecture" className="rd-diagram-zoom" zoomed={<img src={src} alt={alt} />}>
        <img src={src} alt={alt} width={width} height={height} loading="lazy" decoding="async" />
      </ZoomImage>
      <figcaption>Select the diagram to enlarge it.</figcaption>
    </figure>
  );
}
