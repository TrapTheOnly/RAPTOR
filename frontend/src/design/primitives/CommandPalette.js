import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { FONTS, RADIUS, SPACE, TYPE, Z } from '../tokens';
import { panelVariants, scrimVariants } from '../motion';
import { usePalette } from '../usePalette';
import { hasPermission } from '../../utils/permissions';
import { Mono, Text } from './type';

const NAV_COMMANDS = [
  { id: 'nav-dashboard', group: 'Go to', label: 'Dashboard', hint: '/dashboard', to: '/dashboard', permission: 'view_dashboard' },
  { id: 'nav-records', group: 'Go to', label: 'Assets', hint: '/records', to: '/records', permission: 'view_records' },
  { id: 'nav-security', group: 'Go to', label: 'Security', hint: '/pentest', to: '/pentest', permission: 'view_security_dashboard' },
  { id: 'nav-settings', group: 'Go to', label: 'Settings', hint: '/settings', to: '/settings', permission: 'view_settings' },
  { id: 'nav-docs', group: 'Go to', label: 'Documentation', hint: '/docs', to: '/docs' }
];

const EMPTY_LIMITS = { apps: 5, waves: 5, findings: 0 };
const SEARCH_LIMITS = { apps: 8, waves: 8, findings: 8 };

const match = (haystack, query) => String(haystack || '').toLowerCase().includes(query);

const groupItems = (items) => {
  const groups = [];
  items.forEach((item, index) => {
    const last = groups[groups.length - 1];
    const entry = { item, index };
    if (!last || last.name !== item.group) groups.push({ name: item.group, entries: [entry] });
    else last.entries.push(entry);
  });
  return groups;
};

export const CommandPalette = ({ open, onClose, userRole, userPermissions }) => {
  const palette = usePalette();
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [apps, setApps] = useState([]);
  const [waves, setWaves] = useState([]);
  const [findings, setFindings] = useState([]);
  const canViewPentestPage = hasPermission(userRole, userPermissions, 'view_pentest_page');

  useEffect(() => {
    if (!open) return undefined;
    setQuery('');
    setActive(0);
    const handle = window.setTimeout(() => inputRef.current?.focus(), 20);

    if (!canViewPentestPage) {
      setApps([]);
      setWaves([]);
      setFindings([]);
      return () => window.clearTimeout(handle);
    }

    const load = async () => {
      try {
        const appsResponse = await axios.get('/api/apps');
        const nextApps = appsResponse.data.apps || appsResponse.data || [];
        const list = Array.isArray(nextApps) ? nextApps : [];
        setApps(list);
        const [waveSets, findingSets] = await Promise.all([
          Promise.all(
            list.slice(0, 12).map((app) =>
              axios
                .get(`/api/apps/${app.id}/waves`)
                .then((response) =>
                  (response.data.waves || []).map((wave) => ({
                    ...wave,
                    appId: app.id,
                    appName: app.name
                  }))
                )
                .catch(() => [])
            )
          ),
          Promise.all(
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
          )
        ]);
        setWaves(waveSets.flat());
        setFindings(findingSets.flat());
      } catch (error) {
        setApps([]);
        setWaves([]);
        setFindings([]);
      }
    };

    load();
    return () => window.clearTimeout(handle);
  }, [canViewPentestPage, open]);

  const items = useMemo(() => {
    const term = query.trim().toLowerCase();
    const limits = term ? SEARCH_LIMITS : EMPTY_LIMITS;
    const navItems = NAV_COMMANDS.filter((item) => {
      if (item.permission && !hasPermission(userRole, userPermissions, item.permission)) return false;
      return !term || match(item.label, term);
    });
    if (!canViewPentestPage) return navItems;
    const appItems = apps
      .filter((app) => !term || match(app.name, term))
      .slice(0, limits.apps)
      .map((app) => ({
        id: `app-${app.id}`,
        group: 'Applications',
        label: app.name,
        hint: 'workspace',
        to: `/apps/${app.id}`
      }));
    const waveItems = waves
      .filter((wave) => !term || match(wave.name, term) || match(wave.appName, term) || match(wave.status, term))
      .slice(0, limits.waves)
      .map((wave) => ({
        id: `wave-${wave.appId}-${wave.id}`,
        group: 'Waves',
        label: wave.name || 'Untitled wave',
        hint: wave.appName,
        to: `/apps/${wave.appId}/waves/${wave.id}`
      }));
    const findingItems = findings
      .filter((finding) => !term || match(finding.title, term) || match(finding.appName, term) || match(finding.categoryName, term))
      .slice(0, limits.findings)
      .map((finding) => ({
        id: `finding-${finding.id}`,
        group: 'Findings',
        label: finding.title || 'Untitled finding',
        hint: finding.appName,
        to: `/apps/${finding.appId}/findings/${finding.id}`
      }));
    if (term) return [...findingItems, ...waveItems, ...appItems, ...navItems];
    return [...navItems, ...appItems, ...waveItems, ...findingItems];
  }, [apps, canViewPentestPage, findings, query, userPermissions, userRole, waves]);

  const groups = useMemo(() => groupItems(items), [items]);

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
            alignItems: 'flex-start',
            paddingTop: '12vh'
          }}
        >
          <motion.div
            variants={panelVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            onClick={(event) => event.stopPropagation()}
            style={{
              width: 520,
              maxWidth: 'calc(100vw - 32px)',
              maxHeight: 'min(400px, 56vh)',
              display: 'flex',
              flexDirection: 'column',
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
              placeholder="Jump to an app, wave, or finding"
              style={{
                width: '100%',
                border: 0,
                outline: 'none',
                background: 'transparent',
                color: palette.text,
                fontFamily: FONTS.sans,
                fontSize: 14,
                lineHeight: '20px',
                padding: `${SPACE.x12}px ${SPACE.x16}px`,
                borderBottom: `1px solid ${palette.line}`,
                flexShrink: 0
              }}
            />
            <div style={{ overflowY: 'auto', padding: '6px 4px 8px', minHeight: 0 }}>
              {items.length === 0 ? (
                <Text as="div" variant="meta" tone="tertiary" style={{ padding: 16 }}>
                  No matches.
                </Text>
              ) : (
                groups.map((group) => (
                  <div key={group.name} style={{ marginBottom: 4 }}>
                    <Text
                      as="div"
                      variant="micro"
                      tone="tertiary"
                      style={{
                        ...TYPE.micro,
                        padding: '6px 10px 4px',
                        color: palette.textTertiary
                      }}
                    >
                      {group.name}
                    </Text>
                    {group.entries.map(({ item, index }) => (
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
                          padding: '6px 10px',
                          cursor: 'pointer',
                          fontFamily: FONTS.sans,
                          fontSize: 13,
                          lineHeight: '20px'
                        }}
                      >
                        <span>{item.label}</span>
                        <Mono tone="tertiary" style={{ fontSize: 11 }}>
                          {item.hint}
                        </Mono>
                      </button>
                    ))}
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
};
