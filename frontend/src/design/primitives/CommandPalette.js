import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { FONTS, RADIUS, SPACE, Z } from '../tokens';
import { panelVariants, scrimVariants } from '../motion';
import { usePalette } from '../usePalette';
import { Mono, Text } from './type';

const NAV_COMMANDS = [
  { id: 'nav-dashboard', group: 'Go to', label: 'Dashboard', hint: '/dashboard', to: '/dashboard' },
  { id: 'nav-records', group: 'Go to', label: 'Assets', hint: '/records', to: '/records' },
  { id: 'nav-security', group: 'Go to', label: 'Security', hint: '/pentest', to: '/pentest' },
  { id: 'nav-settings', group: 'Go to', label: 'Settings', hint: '/settings', to: '/settings' },
  { id: 'nav-docs', group: 'Go to', label: 'Documentation', hint: '/docs', to: '/docs' }
];

const match = (haystack, query) => String(haystack || '').toLowerCase().includes(query);

export const CommandPalette = ({ open, onClose }) => {
  const palette = usePalette();
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [apps, setApps] = useState([]);
  const [hosts, setHosts] = useState([]);
  const [findings, setFindings] = useState([]);

  useEffect(() => {
    if (!open) return undefined;
    setQuery('');
    setActive(0);
    const handle = window.setTimeout(() => inputRef.current?.focus(), 20);

    const load = async () => {
      try {
        const appsResponse = await axios.get('/api/apps');
        const nextApps = appsResponse.data.apps || appsResponse.data || [];
        const list = Array.isArray(nextApps) ? nextApps : [];
        setApps(list);
        const findingSets = await Promise.all(
          list.slice(0, 12).map((app) =>
            axios
              .get(`/api/apps/${app.id}/findings`, { params: { limit: 25, include_drafts: 1 } })
              .then((response) =>
                (response.data.findings || []).map((finding) => ({
                  ...finding,
                  appId: app.id,
                  appName: app.name
                }))
              )
              .catch(() => [])
          )
        );
        setFindings(findingSets.flat());
      } catch (error) {
        setApps([]);
      }
    };

    load();
    return () => window.clearTimeout(handle);
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const term = query.trim();
    if (term.length < 2) {
      setHosts([]);
      return undefined;
    }
    const handle = window.setTimeout(async () => {
      try {
        const response = await axios.get('/api/hosts/search', { params: { q: term, limit: 8 } });
        setHosts(response.data.hosts || []);
      } catch (error) {
        setHosts([]);
      }
    }, 140);
    return () => window.clearTimeout(handle);
  }, [open, query]);

  const items = useMemo(() => {
    const term = query.trim().toLowerCase();
    const appItems = apps
      .filter((app) => !term || match(app.name, term))
      .slice(0, 8)
      .map((app) => ({
        id: `app-${app.id}`,
        group: 'Applications',
        label: app.name,
        hint: 'workspace',
        to: `/apps/${app.id}`
      }));
    const hostItems = hosts.slice(0, 8).map((host) => ({
      id: `host-${host.id}`,
      group: 'Hosts',
      label: host.name,
      hint: host.application_name || host.ip_address || 'notebook',
      to: `/pentest/record/${host.id}`
    }));
    const findingItems = findings
      .filter((finding) => !term || match(finding.title, term) || match(finding.appName, term))
      .slice(0, 8)
      .map((finding) => ({
        id: `finding-${finding.id}`,
        group: 'Findings',
        label: finding.title || 'Untitled finding',
        hint: finding.appName,
        to: `/apps/${finding.appId}`
      }));
    const navItems = NAV_COMMANDS.filter((item) => !term || match(item.label, term));
    return [...navItems, ...appItems, ...hostItems, ...findingItems];
  }, [apps, findings, hosts, query]);

  useEffect(() => {
    setActive(0);
  }, [query, items.length]);

  const go = useCallback(
    (item) => {
      if (!item) return;
      onClose();
      navigate(item.to);
    },
    [navigate, onClose]
  );

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        setActive((prev) => Math.min(prev + 1, Math.max(items.length - 1, 0)));
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        setActive((prev) => Math.max(prev - 1, 0));
      } else if (event.key === 'Enter') {
        event.preventDefault();
        go(items[active]);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [active, go, items, onClose, open]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="palette-scrim"
          variants={scrimVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          onClick={onClose}
          style={{
            position: 'fixed',
            inset: 0,
            background: palette.scrim,
            zIndex: Z.palette,
            display: 'flex',
            justifyContent: 'center',
            paddingTop: 120
          }}
        >
          <motion.div
            variants={panelVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            onClick={(event) => event.stopPropagation()}
            style={{
              width: 560,
              maxWidth: 'calc(100vw - 32px)',
              background: palette.raised,
              border: `1px solid ${palette.line}`,
              borderRadius: RADIUS.panel,
              boxShadow: palette.shadow,
              overflow: 'hidden'
            }}
          >
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Jump to an app, host, or finding"
              style={{
                width: '100%',
                border: 0,
                outline: 'none',
                background: 'transparent',
                color: palette.text,
                fontFamily: FONTS.sans,
                fontSize: 14,
                lineHeight: '20px',
                padding: `${SPACE.x16}px ${SPACE.x16}px`,
                borderBottom: `1px solid ${palette.line}`
              }}
            />
            <div style={{ maxHeight: 360, overflowY: 'auto', padding: 4 }}>
              {items.length === 0 ? (
                <Text as="div" variant="meta" tone="tertiary" style={{ padding: 16 }}>
                  No matches.
                </Text>
              ) : (
                items.map((item, index) => (
                  <button
                    key={item.id}
                    type="button"
                    onMouseEnter={() => setActive(index)}
                    onClick={() => go(item)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      width: '100%',
                      textAlign: 'left',
                      border: 0,
                      borderRadius: RADIUS.base,
                      background: index === active ? palette.accentFill : 'transparent',
                      color: palette.text,
                      padding: '8px 10px',
                      cursor: 'pointer',
                      fontFamily: FONTS.sans,
                      fontSize: 13
                    }}
                  >
                    <span>
                      <Text as="span" variant="micro" tone="tertiary" style={{ display: 'block', marginBottom: 2 }}>
                        {item.group}
                      </Text>
                      {item.label}
                    </span>
                    <Mono tone="tertiary" style={{ fontSize: 11 }}>
                      {item.hint}
                    </Mono>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
};
