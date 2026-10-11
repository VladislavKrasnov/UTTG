const PATHS = {
  orbit: (
    <>
      <circle cx="12" cy="12" r="3.2" />
      <ellipse cx="12" cy="12" rx="10" ry="4.2" transform="rotate(-25 12 12)" />
      <circle cx="20.2" cy="8.4" r="1.4" fill="currentColor" stroke="none" />
    </>
  ),
  rocket: (
    <>
      <path d="M12 2.5c3 2.4 4.5 5.7 4.5 9.5v4h-9v-4c0-3.8 1.5-7.1 4.5-9.5Z" />
      <circle cx="12" cy="9.5" r="1.6" />
      <path d="M7.5 13 5 16.5V19l2.5-1.5M16.5 13l2.5 3.5V19l-2.5-1.5M10 19.5c.6 1.2 1.3 2 2 2s1.4-.8 2-2" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
    </>
  ),
  asteroid: (
    <>
      <path d="M9 4.5 15.5 4l4.5 5-1 6.5-5.5 4.5-6.5-1.5L3.5 13 5 7Z" />
      <circle cx="10" cy="10" r="1.3" />
      <circle cx="14.5" cy="14" r="1.8" />
    </>
  ),
  server: (
    <>
      <rect x="3.5" y="4" width="17" height="6.5" rx="1.5" />
      <rect x="3.5" y="13.5" width="17" height="6.5" rx="1.5" />
      <path d="M7 7.25h.01M7 16.75h.01M11 7.25h6M11 16.75h6" />
    </>
  ),
  play: <path d="M8 5.5v13l10.5-6.5Z" fill="currentColor" />,
  pause: <path d="M7.5 5.5h3v13h-3zM13.5 5.5h3v13h-3z" fill="currentColor" />,
  expand: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
  help: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M9.4 9.3a2.7 2.7 0 0 1 5.2 1c0 1.8-2.6 2.3-2.6 3.9M12 17.4h.01" />
    </>
  ),
};

export function Icon({ name }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}
