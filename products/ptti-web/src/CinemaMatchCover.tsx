import { useId } from 'react';
import type { CSSProperties } from 'react';
import type { Locale } from './i18n';

/** Original sport illustration. No player likeness, event photography or external image. */
export function CinemaMatchCover({ identity, title, locale }: { identity: string; title: string; locale: Locale }) {
  const id = useId().replaceAll(':', '');
  const seed = [...identity].reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 0);
  const colors = ['#b84935','#36777b','#9c703e','#645490','#315f96','#876049'];
  const color = colors[seed % colors.length];
  const angle = seed % 3 === 0 ? -12 : seed % 3 === 1 ? 9 : 0;
  return <figure className="cinema-match-cover" data-cover-origin="PTTI_ORIGINAL" style={{ '--cover-accent': color } as CSSProperties}>
    <svg viewBox="0 0 640 360" role="img" aria-label={`${title} · ${locale === 'zh-CN' ? 'PTTI 原创运动插画，非赛事照片' : 'Original PTTI sport illustration, not event photography'}`}>
      <defs><radialGradient id={`${id}-light`}><stop stopColor={color}/><stop offset="1" stopColor="#101724"/></radialGradient><linearGradient id={`${id}-rubber`} x2="1" y2="1"><stop stopColor="#f46c52"/><stop offset="1" stopColor="#671b28"/></linearGradient><radialGradient id={`${id}-ball`} cx=".3" cy=".2"><stop stopColor="#fffef4"/><stop offset=".7" stopColor="#dcd8c8"/><stop offset="1" stopColor="#8d9a9f"/></radialGradient></defs>
      <path fill={`url(#${id}-light)`} d="M0 0h640v360H0z"/>
      <path d="M0 360L640 0H460L0 258Z" fill={color} opacity=".24"/>
      <g fill="none" stroke="#f4e3c7" opacity=".18"><path d="M-40 300Q280 15 720 115M-40 320Q280 35 720 135M-40 340Q280 55 720 155"/><path d="M0 32h640M0 328h640"/></g>
      <g className="cinema-cover-equipment" transform={`translate(${seed % 2 ? 158 : 480} 204) rotate(${(seed % 2 ? -32 : 32) + angle})`}><rect x="-15" y="38" width="30" height="108" rx="10" fill="#d5a56b"/><ellipse rx="91" ry="108" fill="#b98958"/><ellipse cy="-4" rx="86" ry="102" fill={`url(#${id}-rubber)`}/><ellipse cy="-8" rx="75" ry="90" fill="none" stroke="#ffcfad" opacity=".25"/></g>
      <g stroke="#fff1d0" strokeLinecap="round" opacity=".6"><path d={seed % 2 ? 'M325 128l115-35M337 147l143-22M343 167l100-4' : 'M318 128L203 93M306 147l-143-22M300 167l-100-4'} strokeWidth="3"/></g>
      <circle className="cinema-cover-ball" cx={seed % 2 ? 294 : 347} cy="159" r="49" fill={`url(#${id}-ball)`}/>
      <text x="26" y="53" fill="#f3e2c6" fontSize="17" letterSpacing="5" fontFamily="sans-serif">PTTI</text>
    </svg>
    <figcaption>{locale === 'zh-CN' ? '原创封面' : 'Original artwork'}</figcaption>
  </figure>;
}
