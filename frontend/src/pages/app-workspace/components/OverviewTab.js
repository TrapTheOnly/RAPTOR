import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { LayoutGroup, motion } from 'motion/react';
import {
  Button,
  DataList,
  DataRow,
  EnvTag,
  Mono,
  SeverityDot,
  StatusGlyph,
  Surface,
  Tag,
  Text,
  severityKeyFromScore
} from '../../../design/primitives';
import { LAYOUT, ROW, SPACE } from '../../../design/tokens';
import { LAYOUT_ID, TRANSITION } from '../../../design/motion';
import { usePalette } from '../../../design/usePalette';

const SEVERITY_ORDER = [
  { label: 'Critical', key: 'critical', sample: 9 },
  { label: 'High', key: 'high', sample: 7 },
  { label: 'Medium', key: 'medium', sample: 4 },
  { label: 'Low', key: 'low', sample: 1 },
  { label: 'Unscored', key: 'none', sample: 0 }
];

const SectionHead = ({ title, hint, actions }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-end',
      gap: 16,
      marginBottom: 12
    }}
  >
    <div>
      <Text as="div" variant="h2">
        {title}
      </Text>
      {hint ? (
        <Text as="p" variant="meta" tone="secondary" style={{ margin: '4px 0 0', maxWidth: 560 }}>
          {hint}
        </Text>
      ) : null}
    </div>
    {actions}
  </div>
);

const EnvTile = ({ env, appId, selected }) => {
  const navigate = useNavigate();
  const palette = usePalette();
  const hostCount = Number(env.host_count || 0);

  return (
    <Surface
      as="button"
      type="button"
      selected={selected}
      interactive
      onClick={() => {
        if (selected) return;
        navigate(`/apps/${appId}/envs/${env.id}`);
      }}
      style={{
        padding: 12,
        paddingLeft: selected ? 12 + LAYOUT.railWidth : 12,
        textAlign: 'left',
        cursor: selected ? 'default' : 'pointer',
        width: '100%',
        color: palette.text,
        font: 'inherit',
        appearance: 'none'
      }}
    >
      {selected ? (
        <motion.span
          layoutId={LAYOUT_ID.envCoverageRail}
          transition={TRANSITION.layout}
          aria-hidden
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: LAYOUT.railWidth,
            background: palette.accent
          }}
        />
      ) : null}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <EnvTag slug={env.slug} label={env.slug} />
        <Text variant="meta" tone="secondary">
          {hostCount === 0 ? 'No hosts' : `${hostCount} host${hostCount === 1 ? '' : 's'}`}
        </Text>
      </div>
      <Text as="div" variant="bodyStrong">
        {env.display_name}
      </Text>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, margin: '6px 0 10px' }}>
        <Text variant="h2">{hostCount}</Text>
        <Text variant="meta" tone="secondary">
          hosts
        </Text>
      </div>
    </Surface>
  );
};

const formatDate = (value) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

const QuietRow = ({ children, onClick, palette }) => (
  <div
    role={onClick ? 'button' : undefined}
    tabIndex={onClick ? 0 : undefined}
    onClick={onClick}
    onKeyDown={
      onClick
        ? (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              onClick();
            }
          }
        : undefined
    }
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: SPACE.x12,
      minHeight: ROW.comfortable,
      borderTop: `1px solid ${palette.line}`,
      borderBottom: `1px solid ${palette.line}`,
      padding: `8px 0`,
      cursor: onClick ? 'pointer' : 'default'
    }}
  >
    {children}
  </div>
);

const SeverityTrack = ({ mix, total, palette }) => {
  const filled = mix.filter((tier) => tier.count > 0);
  return (
    <div>
      <div
        style={{
          display: 'flex',
          height: 6,
          background: palette.line,
          overflow: 'hidden',
          marginBottom: 10
        }}
      >
        {total === 0 ? (
          <div style={{ flex: 1, background: palette.line }} />
        ) : (
          filled.map((tier) => (
            <div
              key={tier.key}
              style={{
                flexGrow: tier.count,
                flexBasis: 0,
                background: palette.severity[tier.key]
              }}
            />
          ))
        )}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 14px' }}>
        {mix.map((tier) => (
          <span key={tier.key} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <SeverityDot severity={tier.key} />
            <Text variant="meta" tone="secondary">
              {tier.label} {tier.count}
            </Text>
          </span>
        ))}
      </div>
    </div>
  );
};

const OverviewTab = ({
  appId,
  envId,
  environments,
  findings,
  waves,
  onGoToTab,
  onOpenWave
}) => {
  const palette = usePalette();
  const navigate = useNavigate();

  const topFindings = useMemo(
    () =>
      [...findings]
        .filter((finding) => ['open', 'retest'].includes(String(finding.status || '').toLowerCase()))
        .sort((a, b) => Number(b.baseScore || 0) - Number(a.baseScore || 0))
        .slice(0, 5),
    [findings]
  );

  const severityMix = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0, none: 0 };
    findings.forEach((finding) => {
      counts[severityKeyFromScore(finding.baseScore)] += 1;
    });
    return SEVERITY_ORDER.map((tier) => ({ ...tier, count: counts[tier.key] }));
  }, [findings]);

  const openWave = waves.find((wave) => wave.status === 'open');
  const visibleEnvs = environments.filter((env) => Number(env.host_count || 0) > 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x32 }}>
      <section>
        <SectionHead
          title="Environment coverage"
          hint={
            envId
              ? 'The highlighted environment is the one you are in. Click another to switch, or App overview to leave.'
              : 'Each environment is a drill-down, not a separate application. Open one to scope findings and set its rules of engagement.'
          }
          actions={
            <Button size="small" onClick={() => onGoToTab(envId ? 'env-settings' : 'environments')}>
              {envId ? 'Manage environment' : 'Manage environments'}
            </Button>
          }
        />
        {visibleEnvs.length === 0 ? (
          <QuietRow palette={palette}>
            <Text variant="meta" tone="secondary">
              No hosts filed yet
            </Text>
            <Text variant="meta" tone="tertiary">
              Environments appear here once they have hosts
            </Text>
          </QuietRow>
        ) : (
          <LayoutGroup>
            <div
              style={{
                display: 'grid',
                gap: 12,
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))'
              }}
            >
              {visibleEnvs.map((env) => (
                <EnvTile
                  key={env.id}
                  env={env}
                  appId={appId}
                  selected={String(env.id) === String(envId)}
                />
              ))}
            </div>
          </LayoutGroup>
        )}
      </section>

      <div
        style={{
          display: 'grid',
          gap: 32,
          alignItems: 'start',
          gridTemplateColumns: 'minmax(0, 1.5fr) minmax(0, 1fr)'
        }}
      >
        <section>
          <SectionHead
            title="Open risk"
            actions={
              <Button size="small" onClick={() => onGoToTab('findings')}>
                Findings
              </Button>
            }
          />
          {topFindings.length === 0 ? (
            <QuietRow onClick={() => onGoToTab('findings')} palette={palette}>
              <Text variant="meta" tone="secondary">
                No open or retest findings
              </Text>
              <Text variant="meta" tone="tertiary">
                {findings.length === 0 ? 'None recorded' : `${findings.length} closed or draft`}
              </Text>
            </QuietRow>
          ) : (
            <DataList>
              {topFindings.map((finding) => {
                const score = Number(finding.baseScore || 0);
                const hostNames = (finding.occurrences || [])
                  .map((item) => item.dns_name)
                  .filter(Boolean);
                const hostCount = (finding.occurrences || []).length;
                return (
                  <DataRow
                    key={finding.id}
                    id={finding.id}
                    severity={severityKeyFromScore(finding.baseScore)}
                    onToggle={() =>
                      navigate(`/apps/${appId}/findings/${finding.id}`)
                    }
                    title={
                      <Text variant="bodyStrong">
                        {finding.title || finding.categoryName || 'Untitled finding'}
                      </Text>
                    }
                    meta={
                      <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 4 }}>
                        {hostCount} host{hostCount === 1 ? '' : 's'}
                        {hostNames.length ? ` · ${hostNames.slice(0, 2).join(', ')}` : ''}
                        {hostNames.length > 2 ? ` +${hostNames.length - 2}` : ''}
                      </Text>
                    }
                    trailing={
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
                        {score > 0 ? <Mono tone="secondary">{score.toFixed(1)}</Mono> : null}
                        <StatusGlyph status={finding.status} />
                      </span>
                    }
                  />
                );
              })}
            </DataList>
          )}
        </section>

        <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x24 }}>
          <section>
            <SectionHead
              title="Wave"
              actions={
                <Button
                  size="small"
                  onClick={() => (onOpenWave ? onOpenWave(openWave) : onGoToTab('waves'))}
                >
                  Open wave
                </Button>
              }
            />
            {openWave ? (
              <QuietRow onClick={() => (onOpenWave ? onOpenWave(openWave) : onGoToTab('waves'))} palette={palette}>
                <div style={{ minWidth: 0 }}>
                  <Text as="div" variant="bodyStrong">
                    {openWave.name}
                  </Text>
                  <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 2 }}>
                    {formatDate(openWave.opened_at)
                      ? `Opened ${formatDate(openWave.opened_at)} · `
                      : ''}
                    {openWave.host_count || 0} live hosts
                  </Text>
                </div>
                <Tag>open</Tag>
              </QuietRow>
            ) : (
              <QuietRow onClick={() => onGoToTab('waves')} palette={palette}>
                <Text variant="meta" tone="secondary">
                  No wave open
                </Text>
                <Text variant="meta" tone="tertiary">
                  Open a wave to start testing
                </Text>
              </QuietRow>
            )}
          </section>

          <section>
            <SectionHead
              title="Severity"
              actions={
                findings.length > 0 ? (
                  <Text variant="meta" tone="secondary">
                    {findings.length} finding{findings.length === 1 ? '' : 's'}
                  </Text>
                ) : null
              }
            />
            <SeverityTrack mix={severityMix} total={findings.length} palette={palette} />
          </section>
        </div>
      </div>
    </div>
  );
};

export default OverviewTab;
