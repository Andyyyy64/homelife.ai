import { useState, useEffect, useCallback } from 'react';

// Connect directly to the Python MJPEG server — no proxy overhead
const LIVE_URL = `${window.location.protocol}//${window.location.hostname}:3002/stream`;

export function LiveFeed() {
  const [live, setLive] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleClose = useCallback(() => setExpanded(false), []);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded, handleClose]);

  return (
    <>
      <div className="live-feed" onClick={() => live && setExpanded(true)} style={{ cursor: live ? 'pointer' : 'default' }}>
        <div className={`live-indicator ${live ? 'active' : ''}`}>
          <span className={`live-dot ${live ? '' : 'offline'}`} />
          {live ? 'LIVE' : 'OFFLINE'}
        </div>
        <img
          src={LIVE_URL}
          alt="Live feed"
          className="live-image"
          style={{ display: live ? 'block' : 'none' }}
          onLoad={() => setLive(true)}
          onError={() => setLive(false)}
        />
      </div>
      {expanded && (
        <div className="live-modal-overlay" onClick={handleClose}>
          <div className="live-modal" onClick={(e) => e.stopPropagation()}>
            <div className="live-modal-header">
              <div className={`live-indicator ${live ? 'active' : ''}`}>
                <span className={`live-dot ${live ? '' : 'offline'}`} />
                LIVE
              </div>
              <button className="live-modal-close" onClick={handleClose}>
                &times;
              </button>
            </div>
            <img
              src={LIVE_URL}
              alt="Live feed"
              className="live-modal-image"
            />
          </div>
        </div>
      )}
    </>
  );
}
