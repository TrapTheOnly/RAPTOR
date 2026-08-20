import React from 'react';
import { LAYOUT, SPACE, Z } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';
import { SETTINGS_NAV_WIDTH } from '../constants';

const SettingsShell = ({ renderNav, children, isMobile, navOpen, onCloseNav }) => {
  const palette = usePalette();

  return (
    <>
      <style>{`
        .raptor-settings {
          display: grid;
          grid-template-columns: minmax(220px, ${SETTINGS_NAV_WIDTH}px) minmax(0, 1fr);
          gap: 0;
          align-items: start;
          border-top: 1px solid var(--raptor-line);
        }
        .raptor-settings-nav {
          border-right: 1px solid var(--raptor-line);
          padding: ${SPACE.x16}px ${SPACE.x12}px ${SPACE.x16}px 0;
          min-width: 0;
        }
        .raptor-settings-main {
          min-width: 0;
          padding: ${SPACE.x16}px 0 ${SPACE.x16}px ${SPACE.x24}px;
        }
        @media (max-width: 960px) {
          .raptor-settings { grid-template-columns: 1fr; }
          .raptor-settings-nav { display: none; }
          .raptor-settings-main { padding: ${SPACE.x16}px 0 0; }
        }
      `}</style>
      <div className="raptor-settings">
        <nav className="raptor-settings-nav" aria-label="Settings sections">
          {renderNav?.()}
        </nav>
        <div className="raptor-settings-main">{children}</div>
      </div>
      {isMobile && navOpen ? (
        <>
          <button
            type="button"
            aria-label="Close settings navigation"
            onClick={onCloseNav}
            style={{
              position: 'fixed',
              inset: 0,
              border: 0,
              background: palette.scrim,
              zIndex: Z.drawer
            }}
          />
          <div
            style={{
              position: 'fixed',
              top: LAYOUT.navHeight,
              left: 0,
              bottom: 0,
              width: SETTINGS_NAV_WIDTH,
              background: palette.surface,
              zIndex: Z.drawer + 1,
              padding: SPACE.x16,
              overflow: 'auto',
              borderRight: `1px solid ${palette.line}`
            }}
          >
            {renderNav?.()}
          </div>
        </>
      ) : null}
    </>
  );
};

export default SettingsShell;
