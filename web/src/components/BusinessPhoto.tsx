import { useState } from 'react';
import { BUSINESS_PHOTOS } from '../data/businessPhotos';

/** A business introduction photo, never an input to a neighborhood assessment. */
export function BusinessPhoto({ businessId, name }: { businessId: string; name: string }) {
  const photo = BUSINESS_PHOTOS[businessId];
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  if (!photo || failedUrl === photo.url) {
    return <div className="business-photo-fallback"><span aria-hidden="true">▧</span><span>Photo unavailable<small>{name}</small></span></div>;
  }
  return <figure className="business-photo">
    <img src={photo.url} alt={photo.alt} width={750} height={460} decoding="async" onError={() => setFailedUrl(photo.url)} />
    <figcaption><span>{photo.caption}</span><a href={photo.sourceUrl} target="_blank" rel="noopener noreferrer">Photo source ↗</a></figcaption>
  </figure>;
}
