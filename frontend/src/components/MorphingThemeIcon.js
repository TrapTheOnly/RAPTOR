import React, { useState, useEffect } from 'react';

const MorphingThemeIcon = ({ isDark, isAnimating, onAnimationComplete }) => {
  // SVG paths for sun and moon
  const sunPath = "M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10z";
  const moonPath = "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z";
  
  const [currentPath, setCurrentPath] = useState(isDark ? moonPath : sunPath);

  useEffect(() => {
    if (isAnimating) {
      // Smooth morphing transition
      const newPath = isDark ? moonPath : sunPath;
      setCurrentPath(newPath);
      
      if (onAnimationComplete) {
        setTimeout(onAnimationComplete, 1200); // Match animation duration
      }
    } else {
      // Set path without animation when not animating
      setCurrentPath(isDark ? moonPath : sunPath);
    }
  }, [isDark, isAnimating, sunPath, moonPath, onAnimationComplete]);

  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`morphing-theme-icon ${isAnimating ? 'morphing' : ''}`}
      style={{
        transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
        transformOrigin: 'center',
      }}
    >
      {/* Main morphing shape */}
      <path
        d={currentPath}
        style={{
          transition: 'd 1.2s cubic-bezier(0.4, 0, 0.2, 1)',
          fill: isDark ? 'currentColor' : 'none',
        }}
      />
      
      {/* Sun rays that appear for light mode */}
      {!isDark && (
        <g style={{
          opacity: isAnimating ? 0 : 1,
          transition: 'opacity 0.6s ease-in-out',
        }}>
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </g>
      )}
      
      {/* Morphing particles effect during animation */}
      {isAnimating && (
        <g>
          <circle cx="8" cy="8" r="1" 
            style={{
              opacity: 0.6,
              animation: 'morphParticle1 1.2s ease-out',
            }}
          />
          <circle cx="16" cy="8" r="1"
            style={{
              opacity: 0.6,
              animation: 'morphParticle2 1.2s ease-out',
            }}
          />
          <circle cx="8" cy="16" r="1"
            style={{
              opacity: 0.6,
              animation: 'morphParticle3 1.2s ease-out',
            }}
          />
          <circle cx="16" cy="16" r="1"
            style={{
              opacity: 0.6,
              animation: 'morphParticle4 1.2s ease-out',
            }}
          />
        </g>
      )}
      
      {/* CSS animations for particles */}
      <defs>
        <style>
          {`
            @keyframes morphParticle1 {
              0% { opacity: 0; transform: translate(0, 0) scale(0); }
              50% { opacity: 0.8; transform: translate(-4px, -4px) scale(1.2); }
              100% { opacity: 0; transform: translate(-8px, -8px) scale(0); }
            }
            @keyframes morphParticle2 {
              0% { opacity: 0; transform: translate(0, 0) scale(0); }
              50% { opacity: 0.8; transform: translate(4px, -4px) scale(1.2); }
              100% { opacity: 0; transform: translate(8px, -8px) scale(0); }
            }
            @keyframes morphParticle3 {
              0% { opacity: 0; transform: translate(0, 0) scale(0); }
              50% { opacity: 0.8; transform: translate(-4px, 4px) scale(1.2); }
              100% { opacity: 0; transform: translate(-8px, 8px) scale(0); }
            }
            @keyframes morphParticle4 {
              0% { opacity: 0; transform: translate(0, 0) scale(0); }
              50% { opacity: 0.8; transform: translate(4px, 4px) scale(1.2); }
              100% { opacity: 0; transform: translate(8px, 8px) scale(0); }
            }
          `}
        </style>
      </defs>
    </svg>
  );
};

export default MorphingThemeIcon; 