import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { BugReport } from '@mui/icons-material';
import {
  Bar,
  DataList,
  DataRow,
  EmptyState,
  EnvTag,
  Mono,
  StatusGlyph,
  Surface,
  Tag,
  Text,
  severityKeyFromScore
} from '../../../design/primitives';
import { RADIUS, SPACE, TYPE } from '../../../design/tokens';
import { TRANSITION, panelVariants } from '../../../design/motion';
import { usePalette } from '../../../design/usePalette';

const SEVERITY_ORDER = [
  { key: 'critical', label: 'Critical', sample: 9 },
  { key: 'high', label: 'High', sample: 7 },
  { key: 'medium', label: 'Medium', sample: 4 },
  { key: 'low', label: 'Low', sample: 1 },
  { key: 'none', label: 'Unscored', sample: 0 }
];

const CLOSED = new Set(['fixed', 'accepted', 'not_affected']);

export const waveCoversEnv = (wave, envId) => {
  if (envId == null || envId === '') return true;
  const ids =
    Array.isArray(wave?.env_ids) && wave.env_ids.length
      ? wave.env_ids
      : wave?.environment_id != null && wave.environment_id !== ''
        ? [wave.environment_id]
        : [];
  return ids.some((id) => String(id) === String(envId));
};

const parseDate = (value) => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const mondayOf = (date) => {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  const day = copy.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  return copy;
};

const occurrencesInScope = (finding, envId) => {
  const all = finding.occurrences || [];
  if (envId == null || envId === '') return all;
  return all.filter((occ) => String(occ.environment_id) === String(envId));
};

const isClosedStatus = (status) => CLOSED.has(String(status || '').toLowerCase());

const scopedIsClosed = (finding, occurrences, envId) => {
  if (envId == null || envId === '') return isClosedStatus(finding.status);
  const live = occurrences.filter((occ) => String(occ.status || '').toLowerCase() !== 'draft');
  const rows = live.length ? live : occurrences;
  return rows.length > 0 && rows.every((occ) => isClosedStatus(occ.status));
};

const detectedAt = (finding, occurrences, fallback) => {
  const times = occurrences.map((occ) => parseDate(occ.created_at)).filter(Boolean);
  if (times.length) return new Date(Math.min(...times.map((item) => item.getTime())));
  return parseDate(finding.created_at) || fallback;
};

const closedAtFor = (finding, occurrences, envId) => {
  if (!scopedIsClosed(finding, occurrences, envId)) return null;
  const times = occurrences
    .map((occ) => parseDate(occ.status_changed_at) || parseDate(occ.updated_at))
    .filter(Boolean);
  if (times.length) return new Date(Math.max(...times.map((item) => item.getTime())));
  return parseDate(finding.updated_at) || parseDate(finding.created_at);
};

const weekLabel = (date) =>
  date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

const ChartCard = ({ title, hint, children }) => {
  const palette = usePalette();
  return (
    <Surface style={{ padding: SPACE.x16, minHeight: 180, height: '100%', width: '100%', boxSizing: 'border-box' }}>
      <div style={{ marginBottom: SPACE.x12 }}>
        <Text as="div" variant="h2">
          {title}
        </Text>
        {hint ? (
          <Text as="p" variant="meta" tone="secondary" style={{ margin: '4px 0 0' }}>
            {hint}
          </Text>
        ) : null}
      </div>
      {children}
      <style>{`
        .raptor-chart-empty { color: ${palette.textTertiary}; }
      `}</style>
    </Surface>
  );
};

const HorizontalBars = ({ items, colorFor, empty }) => {
  const palette = usePalette();
  const max = Math.max(...items.map((item) => item.value), 0);
  if (!items.length || max === 0) {
    return (
      <Text variant="meta" tone="secondary">
        {empty}
      </Text>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {items.map((item) => (
        <div key={item.key || item.label}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
            <Text variant="meta" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {item.label}
            </Text>
            <Mono tone="secondary">{item.value}</Mono>
          </div>
          <Bar
            value={max > 0 ? (item.value / max) * 100 : 0}
            color={colorFor ? colorFor(item) : palette.accent}
          />
        </div>
      ))}
    </div>
  );
};

const StackedArea = ({ series, height = 180 }) => {
  const palette = usePalette();
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(0);
  const [hoverIndex, setHoverIndex] = useState(null);
  const clipId = useId().replace(/:/g, '');

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return undefined;
    const apply = () => {
      const next = Math.round(node.getBoundingClientRect().width);
      if (next > 0) setWidth(next);
    };
    apply();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(apply);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const n = series[0]?.points?.length || 0;
  const plotWidth = width > 0 ? width : 520;
  if (!n) {
    return (
      <Text variant="meta" tone="secondary">
        No findings yet to plot over time.
      </Text>
    );
  }
  const totals = series[0].points.map((_, index) =>
    series.reduce((sum, item) => sum + Number(item.points[index] || 0), 0)
  );
  const max = Math.max(...totals, 1);
  const pad = { top: 8, right: 8, bottom: 24, left: 28 };
  const innerW = plotWidth - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const xAt = (index) => pad.left + (n === 1 ? innerW / 2 : (index / (n - 1)) * innerW);
  const yAt = (value) => pad.top + innerH - (value / max) * innerH;

  const stacked = series.map((item) => item.points.map((point) => Number(point) || 0));
  const layers = [];
  for (let s = 0; s < series.length; s += 1) {
    const tops = stacked[s].map((_, index) => stacked.slice(0, s + 1).reduce((sum, row) => sum + row[index], 0));
    const bottoms = stacked[s].map((_, index) => stacked.slice(0, s).reduce((sum, row) => sum + row[index], 0));
    const path = [
      ...tops.map((value, index) => `${index === 0 ? 'M' : 'L'} ${xAt(index)} ${yAt(value)}`),
      ...bottoms
        .slice()
        .reverse()
        .map((value, reverseIndex) => `L ${xAt(n - 1 - reverseIndex)} ${yAt(value)}`),
      'Z'
    ].join(' ');
    layers.push({ key: series[s].key, path, color: series[s].color, tops });
  }

  const pickIndex = (event) => {
    const svg = event.currentTarget;
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const x = ((event.clientX - rect.left) / rect.width) * plotWidth;
    const t = n === 1 ? 0 : (x - pad.left) / innerW;
    const index = Math.round(t * Math.max(n - 1, 1));
    setHoverIndex(Math.max(0, Math.min(n - 1, index)));
  };

  const hover = hoverIndex == null
    ? null
    : {
        index: hoverIndex,
        label: series[0].labels[hoverIndex],
        x: xAt(hoverIndex),
        values: series.map((item, seriesIndex) => ({
          key: item.key,
          label: item.label,
          color: item.color,
          value: Number(item.points[hoverIndex] || 0),
          y: yAt(layers[seriesIndex].tops[hoverIndex])
        })),
        total: totals[hoverIndex]
      };

  const tipAlign = hover ? (hover.x < 140 ? 0 : hover.x > plotWidth - 140 ? -100 : -50) : -50;

  return (
    <div ref={wrapRef} style={{ width: '100%', position: 'relative' }}>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${plotWidth} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Active and fixed findings over time. Hover a week to read the counts."
        style={{ display: 'block', width: '100%', cursor: 'crosshair' }}
        onMouseMove={pickIndex}
        onMouseLeave={() => setHoverIndex(null)}
      >
        <defs>
          <clipPath id={clipId}>
            <motion.rect
              x={pad.left}
              y={0}
              height={height}
              initial={{ width: 0 }}
              animate={{ width: innerW }}
              transition={TRANSITION.draw}
            />
          </clipPath>
        </defs>
        {[0, 0.5, 1].map((frac) => {
          const y = yAt(max * frac);
          return (
            <g key={frac}>
              <line x1={pad.left} x2={plotWidth - pad.right} y1={y} y2={y} stroke={palette.line} strokeWidth="1" />
              <text x={pad.left - 6} y={y + 4} textAnchor="end" fill={palette.textTertiary} fontSize="10">
                {Math.round(max * frac)}
              </text>
            </g>
          );
        })}
        <g clipPath={`url(#${clipId})`}>
          {layers.map((layer) => (
            <path key={layer.key} d={layer.path} fill={layer.color} opacity="0.85" />
          ))}
        </g>
        {series[0].labels.map((label, index) =>
          index % 2 === 0 || n < 8 ? (
            <text
              key={label + index}
              x={xAt(index)}
              y={height - 6}
              textAnchor="middle"
              fill={hoverIndex === index ? palette.text : palette.textTertiary}
              fontSize="10"
              fontWeight={hoverIndex === index ? 600 : 400}
            >
              {label}
            </text>
          ) : null
        )}
        <AnimatePresence>
          {hover ? (
            <motion.g
              key="cursor"
              initial={{ opacity: 0, x: hover.x }}
              animate={{ opacity: 1, x: hover.x }}
              exit={{ opacity: 0 }}
              transition={TRANSITION.move}
              style={{ pointerEvents: 'none' }}
            >
              <line
                x1={0}
                x2={0}
                y1={pad.top}
                y2={pad.top + innerH}
                stroke={palette.accent}
                strokeWidth="1"
              />
              {hover.values.map((item) => (
                <circle
                  key={item.key}
                  cx={0}
                  cy={item.y}
                  r={3.5}
                  fill={item.color}
                  stroke={palette.surface}
                  strokeWidth="1.5"
                />
              ))}
            </motion.g>
          ) : null}
        </AnimatePresence>
        <rect
          x={pad.left}
          y={pad.top}
          width={innerW}
          height={innerH}
          fill="transparent"
        />
      </svg>
      <AnimatePresence>
        {hover ? (
          <motion.div
            key="tip"
            variants={panelVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            style={{
              position: 'absolute',
              left: hover.x,
              top: pad.top,
              transform: `translate(${tipAlign}%, 0)`,
              minWidth: 148,
              padding: '8px 10px',
              background: palette.raised,
              border: `1px solid ${palette.line}`,
              borderRadius: RADIUS.base,
              pointerEvents: 'none',
              zIndex: 2
            }}
            role="status"
          >
            <Text as="div" variant="meta" tone="secondary" style={{ marginBottom: 6 }}>
              Week of {hover.label}
            </Text>
            {hover.values
              .slice()
              .reverse()
              .map((item) => (
                <div
                  key={item.key}
                  style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center' }}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 8, height: 8, background: item.color, display: 'inline-block' }} />
                    <Text variant="meta">{item.label}</Text>
                  </span>
                  <Mono>{item.value}</Mono>
                </div>
              ))}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: 16,
                marginTop: 4,
                paddingTop: 4,
                borderTop: `1px solid ${palette.line}`
              }}
            >
              <Text variant="meta" tone="secondary">
                Total
              </Text>
              <Mono>{hover.total}</Mono>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
      <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
        {series.map((item) => (
          <span key={item.key} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, background: item.color, display: 'inline-block' }} />
            <Text variant="meta" tone="secondary">
              {item.label}
            </Text>
          </span>
        ))}
      </div>
    </div>
  );
};

export const buildStats = (findings, waves, environments, options = {}) => {
  const envId = options.envId;
  const now = options.now ? new Date(options.now) : new Date();
  const scopedWaves = (waves || []).filter((wave) => waveCoversEnv(wave, envId));
  const scopedFindings = (findings || [])
    .map((finding) => ({ finding, occurrences: occurrencesInScope(finding, envId) }))
    .filter((item) => !envId || item.occurrences.length > 0);

  const bySeverity = Object.fromEntries(SEVERITY_ORDER.map((item) => [item.key, 0]));
  const recentBySeverity = Object.fromEntries(SEVERITY_ORDER.map((item) => [item.key, 0]));
  const byStatus = {};
  const occStatus = {};
  const envMap = {};
  const waveMap = {};
  scopedWaves.forEach((wave) => {
    waveMap[String(wave.id)] = {
      key: String(wave.id),
      label: wave.name,
      findings: 0,
      testers: (wave.members || []).length
    };
  });

  const sorted = [...scopedFindings].sort((a, b) => {
    const aTime = parseDate(a.finding.created_at)?.getTime() || 0;
    const bTime = parseDate(b.finding.created_at)?.getTime() || 0;
    return bTime - aTime;
  });
  const recent = sorted.slice(0, 20);
  recent.forEach(({ finding }) => {
    recentBySeverity[severityKeyFromScore(finding.baseScore)] += 1;
  });

  scopedFindings.forEach(({ finding, occurrences }) => {
    bySeverity[severityKeyFromScore(finding.baseScore)] += 1;
    const status = envId
      ? scopedIsClosed(finding, occurrences, envId)
        ? 'fixed'
        : 'open'
      : String(finding.status || 'open').toLowerCase();
    byStatus[status] = (byStatus[status] || 0) + 1;
    const waveKey = finding.discovered_wave_id != null ? String(finding.discovered_wave_id) : '';
    if (waveKey && waveMap[waveKey]) waveMap[waveKey].findings += 1;
    if (envId) {
      occurrences.forEach((occ) => {
        const occState = String(occ.status || 'open').toLowerCase();
        occStatus[occState] = (occStatus[occState] || 0) + 1;
      });
      return;
    }
    const seenEnvs = new Set();
    occurrences.forEach((occ) => {
      const occState = String(occ.status || 'open').toLowerCase();
      occStatus[occState] = (occStatus[occState] || 0) + 1;
      const slug = occ.environment_slug || 'unassigned';
      if (seenEnvs.has(slug)) return;
      seenEnvs.add(slug);
      if (!envMap[slug]) {
        const env = (environments || []).find((item) => item.slug === slug);
        envMap[slug] = {
          key: slug,
          label: env?.display_name || occ.environment_name || slug,
          value: 0
        };
      }
      envMap[slug].value += 1;
    });
  });

  const thisMonday = mondayOf(now);
  const weeks = [];
  for (let i = 11; i >= 0; i -= 1) {
    const start = new Date(thisMonday);
    start.setDate(thisMonday.getDate() - i * 7);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    end.setHours(23, 59, 59, 999);
    weeks.push({ start, end, label: weekLabel(start), active: 0, fixed: 0 });
  }

  scopedFindings.forEach(({ finding, occurrences }) => {
    const created = detectedAt(finding, occurrences, now);
    const closedAt = closedAtFor(finding, occurrences, envId);
    weeks.forEach((week) => {
      if (created > week.end) return;
      if (closedAt && closedAt <= week.end) week.fixed += 1;
      else week.active += 1;
    });
  });

  const formatStatus = (key) => key.replace(/_/g, ' ');

  return {
    bySeverity: SEVERITY_ORDER.map((item) => ({
      key: item.key,
      label: item.label,
      value: bySeverity[item.key],
      sample: item.sample
    })),
    recentBySeverity: SEVERITY_ORDER.map((item) => ({
      key: item.key,
      label: item.label,
      value: recentBySeverity[item.key],
      sample: item.sample
    })),
    perWave: Object.values(waveMap)
      .map((item) => ({ ...item, value: item.findings }))
      .sort((a, b) => b.value - a.value),
    testersPerWave: Object.values(waveMap)
      .map((item) => ({ key: item.key, label: item.label, value: item.testers }))
      .sort((a, b) => b.value - a.value),
    perEnv: Object.values(envMap).sort((a, b) => b.value - a.value),
    byStatus: Object.entries(byStatus)
      .map(([key, value]) => ({ key, label: formatStatus(key), value }))
      .sort((a, b) => b.value - a.value),
    occStatus: Object.entries(occStatus)
      .map(([key, value]) => ({ key, label: formatStatus(key), value }))
      .sort((a, b) => b.value - a.value),
    overTime: weeks,
    total: scopedFindings.length,
    recentList: sorted.slice(0, 8).map(({ finding, occurrences }) => ({
      ...finding,
      occurrences
    }))
  };
};

const FindingsDashboardTab = ({
  findings = [],
  waves = [],
  environments = [],
  appId,
  envId
}) => {
  const navigate = useNavigate();
  const palette = usePalette();
  const stats = useMemo(
    () => buildStats(findings, waves, environments, { envId }),
    [findings, waves, environments, envId]
  );

  const severityColor = (item) => palette.severity?.[item.key] || palette.accent;
  const lifecycleColor = (item) => {
    if (CLOSED.has(item.key)) return palette.lifecycle?.positive || palette.accent;
    if (item.key === 'draft' || item.key === 'retest') return palette.lifecycle?.deferred || palette.textTertiary;
    return palette.accent;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16 }}>
        <div>
          <Text as="div" variant="h2">
            Findings
          </Text>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: '4px 0 0', maxWidth: 560 }}>
            {envId
              ? 'Open risk in this environment and its hosts. File findings from a wave that includes this environment.'
              : 'Open risk across this application. File findings from a wave — that is the engagement.'}
          </Text>
        </div>
      </div>

      {stats.total === 0 ? (
        <EmptyState
          icon={BugReport}
          title="No findings yet"
          hint={
            envId
              ? 'File findings from a wave that includes this environment. Only this environment’s hosts appear here.'
              : 'File findings from a wave. The wave is the engagement between the customer and the testers.'
          }
        />
      ) : (
        <>
          <style>{`
            .raptor-findings-charts {
              display: grid;
              gap: ${SPACE.x16}px;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              align-items: stretch;
            }
            @media (min-width: 1100px) {
              .raptor-findings-charts { grid-template-columns: repeat(4, minmax(0, 1fr)); }
            }
          `}</style>
          <div className="raptor-findings-charts">
          <div
            style={{
              gridColumn: envId ? 'span 3' : 'span 2',
              minWidth: 0,
              width: '100%',
              height: '100%'
            }}
          >
            <ChartCard
              title="Active and fixed over time"
              hint="Each column is the stock as of that week's last moment. When a week ends, those statuses stay frozen. Fixed includes accepted and not-affected."
            >
              <StackedArea
                series={[
                  {
                    key: 'fixed',
                    label: 'Fixed / closed',
                    color: palette.lifecycle?.positive || '#3FB950',
                    points: stats.overTime.map((week) => week.fixed),
                    labels: stats.overTime.map((week) => week.label)
                  },
                  {
                    key: 'active',
                    label: 'Active',
                    color: palette.severity?.high || palette.accent,
                    points: stats.overTime.map((week) => week.active),
                    labels: stats.overTime.map((week) => week.label)
                  }
                ]}
              />
            </ChartCard>
          </div>
          <ChartCard title="Occurrence status">
            <HorizontalBars items={stats.occStatus} colorFor={lifecycleColor} empty="No host occurrences yet." />
          </ChartCard>
          <ChartCard title="Recent by severity" hint="Last 20 findings, scored as filed.">
            <HorizontalBars items={stats.recentBySeverity} colorFor={severityColor} empty="Nothing recent." />
          </ChartCard>
          <ChartCard title="All findings by severity">
            <HorizontalBars items={stats.bySeverity} colorFor={severityColor} empty="No scores yet." />
          </ChartCard>
          <ChartCard title="Findings per wave">
            <HorizontalBars items={stats.perWave} empty="No wave stamps yet." />
          </ChartCard>
          {envId ? null : (
            <ChartCard title="Findings per environment" hint="A finding counts once per environment it touches.">
              <HorizontalBars items={stats.perEnv} empty="No environment tags yet." />
            </ChartCard>
          )}
          <ChartCard title="Testers per wave">
            <HorizontalBars items={stats.testersPerWave} empty="No testers listed on waves." />
          </ChartCard>
          </div>
        </>
      )}

      <section>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 12 }}>
          <Text as="div" variant="h2" style={{ ...TYPE.h2 }}>
            Recent findings
          </Text>
          <Text variant="meta" tone="secondary">
            {stats.total} total
          </Text>
        </div>
        {stats.recentList.length === 0 ? (
          <Text variant="meta" tone="secondary">
            Nothing to open yet.
          </Text>
        ) : (
          <DataList>
            {stats.recentList.map((finding) => {
              const envs = [
                ...new Set(
                  (finding.occurrences || []).map((item) => item.environment_slug).filter(Boolean)
                )
              ];
              return (
                <DataRow
                  key={finding.id}
                  id={finding.id}
                  severity={severityKeyFromScore(finding.baseScore)}
                  onToggle={() => navigate(`/apps/${appId}/findings/${finding.id}`)}
                  title={<Text variant="bodyStrong">{finding.title || finding.categoryName || 'Untitled finding'}</Text>}
                  meta={
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                      <Tag>{finding.status || 'open'}</Tag>
                      {envs.slice(0, 3).map((slug) => (
                        <EnvTag key={slug} slug={slug} label={slug} />
                      ))}
                      <Text variant="meta" tone="secondary">
                        {(finding.occurrences || []).length} host
                        {(finding.occurrences || []).length === 1 ? '' : 's'}
                      </Text>
                    </div>
                  }
                  trailing={
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
                      {Number(finding.baseScore) > 0 ? (
                        <Mono tone="secondary">{Number(finding.baseScore).toFixed(1)}</Mono>
                      ) : null}
                      <StatusGlyph status={finding.status} />
                    </span>
                  }
                />
              );
            })}
          </DataList>
        )}
      </section>
    </div>
  );
};

export default FindingsDashboardTab;
