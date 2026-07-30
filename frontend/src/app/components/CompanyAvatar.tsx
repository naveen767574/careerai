import { useState } from 'react';

/**
 * CompanyAvatar
 *
 * Renders a source/company logo, with a proper avatar fallback:
 *  - a filled circle (deterministic background color from the name) + the
 *    company initial — never a bare letter floating on transparent bg.
 *
 * Fallback triggers ONLY when the logo is truly unavailable:
 *  - `logo` is null/empty, OR
 *  - the <img> fails to load (onError) — tracked via local state, not DOM hacks.
 *
 * To use a single generic placeholder logo instead of the colored initial,
 * drop the asset in /public and set FALLBACK_LOGO below.
 */

// Set to a public path (e.g. '/generic-company.png') to use one placeholder
// image for all missing logos. Leave null to use the colored-initial avatar.
const FALLBACK_LOGO: string | null = null;

// Small, readable palette — index chosen deterministically from the name so the
// same company always gets the same color.
const AVATAR_COLORS = [
  '#3b82f6', // blue
  '#8b5cf6', // purple
  '#06b6d4', // cyan
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ef4444', // red
  '#ec4899', // pink
  '#6366f1', // indigo
];

function colorFor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

function initialFor(name: string): string {
  const trimmed = (name || '').trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() : '?';
}

interface CompanyAvatarProps {
  logo?: string | null;
  name: string;      // company name — drives initial + fallback color
  alt?: string;
  className?: string; // sizing/shape of the outer box (defaults to w-12 h-12)
}

export function CompanyAvatar({ logo, name, alt, className = 'w-12 h-12' }: CompanyAvatarProps) {
  const [imgFailed, setImgFailed] = useState(false);

  const hasLogo = Boolean(logo) && !imgFailed;

  if (hasLogo) {
    return (
      <div className={`${className} rounded-xl glass-card flex items-center justify-center overflow-hidden p-1`}>
        <img
          src={logo as string}
          alt={alt || name}
          className="w-full h-full object-contain"
          onError={() => setImgFailed(true)}
        />
      </div>
    );
  }

  // Optional single generic placeholder image
  if (FALLBACK_LOGO) {
    return (
      <div className={`${className} rounded-xl glass-card flex items-center justify-center overflow-hidden p-1`}>
        <img src={FALLBACK_LOGO} alt={alt || name} className="w-full h-full object-contain" />
      </div>
    );
  }

  // Colored-circle avatar with the company initial
  return (
    <div
      className={`${className} rounded-full flex items-center justify-center text-white font-semibold text-lg select-none`}
      style={{ backgroundColor: colorFor(name || '?') }}
      aria-label={name || 'Company'}
      title={name || 'Company'}
    >
      {initialFor(name)}
    </div>
  );
}
