import { useState } from 'react';
import type { ReactNode } from 'react';
import mediaIndex from './approved-public-media.json';
import { createPublicMediaIndex } from './fan-media.mjs';
import type { FanPublicMediaAsset } from './fan-media.mjs';

const publicMedia = createPublicMediaIndex(mediaIndex);

export function MediaAsset({ asset, fallback, title, subtitle, priority = false, decorative = false }: {
  asset: FanPublicMediaAsset | undefined;
  fallback: ReactNode;
  title?: string;
  subtitle?: string;
  priority?: boolean;
  decorative?: boolean;
}) {
  const [failedAssetId, setFailedAssetId] = useState<string | null>(null);
  const [loadedAssetId, setLoadedAssetId] = useState<string | null>(null);
  if (!asset || failedAssetId === asset.asset_id) return <>{fallback}</>;
  const loaded = loadedAssetId === asset.asset_id;
  const renditionsByMime = new Map<string, typeof asset.renditions[number][]>();
  for (const rendition of asset.renditions) {
    const entries = renditionsByMime.get(rendition.mime_type) ?? [];
    entries.push(rendition);
    renditionsByMime.set(rendition.mime_type, entries);
  }
  const fallbackRendition = asset.renditions.find((entry) => entry.mime_type === 'image/webp')
    ?? asset.renditions.find((entry) => entry.mime_type === 'image/jpeg' || entry.mime_type === 'image/png')
    ?? asset.renditions[0];
  const fallbackMime = fallbackRendition.mime_type;
  const fallbackSrcSet = asset.renditions.filter((entry) => entry.mime_type === fallbackMime)
    .sort((a, b) => a.width - b.width).map((entry) => `${entry.src} ${entry.width}w`).join(', ');
  const isWide = fallbackRendition.width > fallbackRendition.height;
  return <figure className={`fan-artwork fan-artwork-${asset.kind === 'ATHLETE_PORTRAIT' ? 'star' : 'match'} fan-media-asset${isWide ? ' fan-media-wide' : ''}${decorative ? ' fan-artwork-stage' : ''}`}
    data-media-asset-id={asset.asset_id} data-media-sha256={fallbackRendition.sha256}>
    <picture className={`fan-media-picture${loaded ? ' is-loaded' : ' is-loading'}`} style={{ aspectRatio: `${fallbackRendition.width} / ${fallbackRendition.height}` }}>
      {[...renditionsByMime.entries()].sort(([left], [right]) => left === 'image/avif' ? -1 : right === 'image/avif' ? 1 : 0).map(([mime, entries]) => <source key={mime} type={mime}
        srcSet={entries.sort((a, b) => a.width - b.width).map((entry) => `${entry.src} ${entry.width}w`).join(', ')} sizes={asset.sizes} />)}
      <img src={fallbackRendition.src} srcSet={fallbackSrcSet} sizes={asset.sizes}
        width={fallbackRendition.width} height={fallbackRendition.height} alt={decorative ? '' : asset.alt} loading={priority ? 'eager' : 'lazy'}
        fetchPriority={priority ? 'high' : 'auto'} decoding="async" style={{ objectPosition: asset.object_position }}
        onLoad={() => setLoadedAssetId(asset.asset_id)} onError={() => setFailedAssetId(asset.asset_id)} />
    </picture>
    {(title || subtitle) && <span className="fan-art-poster-copy">{subtitle && <small>{subtitle}</small>}{title && <strong>{title}</strong>}</span>}
    <figcaption className="fan-media-attribution">
      <span>{asset.attribution} {asset.derivative_notice} {asset.context_notice} {asset.license.includes('BY-SA') ? `ShareAlike: derivatives retain the same ${asset.license} license.` : ''}</span>
      <a href={asset.license_url} target="_blank" rel="noopener noreferrer" aria-label={`${asset.license} license details`}>{asset.license}</a>
      <a href={asset.source_page_url} target="_blank" rel="noopener noreferrer" aria-label={`Original image by ${asset.photographer}`}>Original / 原图</a>
    </figcaption>
  </figure>;
}

export function AthletePortrait({ athleteId, fallback, title, subtitle, priority = false, decorative = false }: {
  athleteId: string; fallback: ReactNode; title?: string; subtitle?: string; priority?: boolean; decorative?: boolean;
}) {
  return <MediaAsset asset={publicMedia.athletes.get(athleteId)} fallback={fallback} title={title} subtitle={subtitle} priority={priority} decorative={decorative} />;
}

export function MatchPoster({ matchId, fallback, title, subtitle, priority = false, decorative = false }: {
  matchId: string; fallback: ReactNode; title?: string; subtitle?: string; priority?: boolean; decorative?: boolean;
}) {
  return <MediaAsset asset={publicMedia.matches.get(matchId)} fallback={fallback} title={title} subtitle={subtitle} priority={priority} decorative={decorative} />;
}
