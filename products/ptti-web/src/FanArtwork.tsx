import { useId } from 'react';
import type { CSSProperties } from 'react';
import { message } from './i18n';
import type { Locale } from './i18n';

const palettes = [
  ['#f23d50', '#f7b56b'], ['#db4d6d', '#8cbdb4'], ['#cf633b', '#d7b97b'],
  ['#757adb', '#e3a3c1'], ['#c5354f', '#7cabe0'], ['#42978f', '#e4c48c'],
  ['#b39a4b', '#b5c7e7'], ['#b34b79', '#efb6a0'],
];

/** Original graphic art. Identity affects art direction only, never source facts. */
export function FanArtwork({ locale, kind, identity = '', monogram, title, subtitle, decorative = false }: {
  locale: Locale; kind: 'match' | 'star' | 'clip'; identity?: string;
  monogram?: string; title?: string; subtitle?: string; decorative?: boolean;
}) {
  const uid = useId().replaceAll(':', '');
  let seed = 2166136261;
  for (const char of identity || title || kind) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619) >>> 0;
  seed = (seed ^ (seed >>> 16)) >>> 0;
  const variant = seed % palettes.length;
  const [accent, light] = palettes[variant];
  const glyph = monogram || (title || 'PTTI').split(/\s+/).map((part) => part[0]).join('').slice(0, 3);
  const arena = kind !== 'star';
  return <div className={`fan-artwork fan-artwork-${kind}${decorative ? ' fan-artwork-stage' : ''}`} data-art-variant={variant}
    style={{ '--art-accent': accent, '--art-light': light } as CSSProperties}
    role={decorative ? undefined : 'img'} aria-hidden={decorative || undefined}
    aria-label={decorative ? undefined : `${title ? `${title} · ` : ''}${message(locale, 'fan.artworkLabel')}`}>
    <svg viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id={`air-${uid}`} cx="72%" cy="42%" r="68%"><stop stopColor={accent} stopOpacity=".32"/><stop offset=".54" stopColor="#17151d"/><stop offset="1" stopColor="#07090d"/></radialGradient>
        <linearGradient id={`floor-${uid}`} x2="0" y2="1"><stop stopColor={accent} stopOpacity=".03"/><stop offset=".55" stopColor={accent} stopOpacity=".18"/><stop offset="1" stopColor="#07080b"/></linearGradient>
        <linearGradient id={`beam-${uid}`} x2=".45" y2="1"><stop stopColor={light} stopOpacity=".5"/><stop offset="1" stopColor={light} stopOpacity="0"/></linearGradient>
        <linearGradient id={`court-${uid}`} x1="0" y1="0" x2="1" y2="1"><stop stopColor={accent}/><stop offset=".5" stopColor="#391922"/><stop offset="1" stopColor="#111820"/></linearGradient>
        <linearGradient id={`trail-${uid}`}><stop stopColor={accent} stopOpacity="0"/><stop offset=".7" stopColor={accent}/><stop offset="1" stopColor="#fff1d9"/></linearGradient>
        <radialGradient id={`ball-${uid}`} cx="30%" cy="25%"><stop stopColor="#fffdf5"/><stop offset=".75" stopColor="#f7e4c9"/><stop offset="1" stopColor="#bf9471"/></radialGradient>
        <pattern id={`net-${uid}`} width="9" height="7" patternUnits="userSpaceOnUse"><path d="M0 0h9v7" fill="none" stroke="#f2ede1" strokeOpacity=".32" strokeWidth=".7"/></pattern>
      </defs>
      <path fill={`url(#air-${uid})`} d="M0 0h1200v800H0z"/>
      {arena ? <>
        <g fill="none" stroke="#d7d5dc" strokeOpacity=".09">
          <path d="M0 365Q600-250 1200 365M0 300Q600-300 1200 300M140 0l260 350M1080 0 865 350M650 0l-10 330"/>
          <path d="M0 401h1200M0 424h1200M0 448h1200M0 476h1200"/>
        </g>
        <g fill={`url(#beam-${uid})`}>
          <path d="m645 56-188 505 462 42Z" opacity=".32"/>
          <path d="m1002 97-417 478 503-28Z" opacity=".24"/>
          <path d="m357 112 140 446 265-10Z" opacity=".12"/>
        </g>
        <path d="M0 478h1200v322H0z" fill={`url(#floor-${uid})`}/>
        <g fill="none" stroke={light} strokeOpacity=".09"><path d="m730 440-610 360m610-360-260 360m260-360 170 360m-170-360 510 360M0 665h1200M0 747h1200"/></g>
        <ellipse cx="770" cy="635" rx="347" ry="90" fill="#000" opacity=".5"/>
        <path d="m427 519 389-144 294 114-393 169Z" fill={`url(#court-${uid})`} stroke={light} strokeWidth="2.5"/>
        <path d="m427 519 290 139 393-169v16L717 675 427 535Z" fill="#0c1018" stroke={accent} strokeOpacity=".5"/>
        <path d="m717 658 0 90m-235-199 0 93m560-128 0 108m-235-224 0 84" fill="none" stroke="#3b3e46" strokeWidth="11"/>
        <path d="m482 642 235 106 325-126M482 619l560-18" fill="none" stroke="#242933" strokeWidth="8"/>
        <path d="m447 519 370-135 272 105-373 157Z" fill="none" stroke="#f5e9db" strokeWidth="2" strokeOpacity=".8"/>
        <path d="m617 450 285 122" fill="none" stroke="#f5e9db" strokeWidth="1.5" strokeOpacity=".65"/>
        <path d="m614 448 294 117v-50L614 407Z" fill={`url(#net-${uid})`} stroke="#f3e9d7" strokeOpacity=".6"/>
        <path d="m614 407 294 108" fill="none" stroke="#fff0dc" strokeWidth="3"/>
        <path d="M614 397v67m294 39v78" stroke="#141c27" strokeWidth="5"/>
        <path className="fan-ball-trail" d="M432 370Q716 107 1030 345" fill="none" stroke={`url(#trail-${uid})`} strokeWidth="3"/>
        <path d="M385 356Q712 65 1040 323" fill="none" stroke={accent} strokeWidth="1" strokeOpacity=".22"/>
        <circle cx="1030" cy="345" r="41" fill={light} opacity=".06"/>
        <circle cx="1030" cy="345" r="22" fill={light} opacity=".1"/>
        <circle cx="1030" cy="345" r="12" fill={`url(#ball-${uid})`}/>
        <g fill={light}><circle cx="645" cy="56" r="3"/><circle cx="1002" cy="97" r="3"/><circle cx="357" cy="112" r="2"/></g>
        <path d="m1008 713 56-23m-40 39 56-23" stroke={accent} strokeWidth="6"/>
      </> : <>
        <circle cx="640" cy="350" r="300" fill="none" stroke={accent} strokeWidth="1" opacity=".35"/>
        <circle cx="640" cy="350" r="264" fill="none" stroke={light} strokeWidth="34" opacity=".06"/>
        <path d="m115 800 620-800h180L305 800Z" fill={accent} opacity=".19"/>
        <path d="m770 800 430-600v240L955 800Z" fill={accent} opacity=".38"/>
        <path d="M-50 520Q700 85 1190 350" fill="none" stroke={light} strokeWidth="2" opacity=".42"/>
        <circle cx="1055" cy="307" r="20" fill={`url(#ball-${uid})`}/>
        <g stroke={light} strokeWidth="1" opacity=".12"><path d="M135 0v800M1080 0v800M0 140h1200M0 660h1200"/></g>
      </>}
    </svg>
    {!arena && <strong className="fan-art-monogram" aria-hidden="true">{glyph}</strong>}
    {!decorative && (title || subtitle) && <span className="fan-art-poster-copy">{subtitle && <small>{subtitle}</small>}{title && <strong>{title}</strong>}</span>}
    <span className="fan-art-brand">PTTI <i>ORIGINALS</i></span>
    <span className="fan-art-credit">{message(locale, 'fan.artworkCredit')}</span>
  </div>;
}
