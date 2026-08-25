import React, { useMemo } from 'react';
import { STATUS_VOCABULARY, getPalette } from '../../../../design/tokens';
import { RAPTOR_BRAND } from '../../../../design/RaptorMark';
import { flattenContext, resolvePreviewText, sampleReportContext } from '../../report-preview-sample';

const PAPER = {
  page: '#F8FAFC',
  ink: '#111827',
  muted: '#64748B',
  line: '#CBD5E1',
  rail: {
    critical: '#C6262E',
    high: '#9A4A08',
    medium: '#7A5B12',
    low: '#5A6472'
  }
};

const severityFromScore = (score) => {
  const numeric = Number(score || 0);
  if (numeric >= 9) return 'critical';
  if (numeric >= 7) return 'high';
  if (numeric >= 4) return 'medium';
  if (numeric > 0) return 'low';
  return 'informational';
};

const SEVERITY_CELL = {
  critical: { bg: '#DC2626', fg: '#FFFFFF', label: 'Critical' },
  high: { bg: '#EA580C', fg: '#FFFFFF', label: 'High' },
  medium: { bg: '#EAB308', fg: '#111827', label: 'Medium' },
  low: { bg: '#16A34A', fg: '#FFFFFF', label: 'Low' },
  informational: { bg: '#2563EB', fg: '#FFFFFF', label: 'Informational' }
};

const lightPalette = getPalette('light');

const PaperStatus = ({ status }) => {
  const vocab = STATUS_VOCABULARY[String(status || '').toLowerCase()] || {
    label: String(status || 'Unknown'),
    glyph: 'dot',
    tone: 'muted'
  };
  const color = lightPalette.tone[vocab.tone] || PAPER.muted;
  const size = 8;
  let mark = (
    <span style={{ width: size, height: size, borderRadius: 999, background: color, display: 'inline-block' }} />
  );
  if (vocab.glyph === 'ring') {
    mark = (
      <span
        style={{
          width: size,
          height: size,
          borderRadius: 999,
          border: `1.5px solid ${color}`,
          display: 'inline-block',
          boxSizing: 'border-box'
        }}
      />
    );
  } else if (vocab.glyph === 'half') {
    mark = (
      <span
        style={{
          width: size,
          height: size,
          borderRadius: 999,
          background: `linear-gradient(90deg, ${color} 50%, transparent 50%)`,
          border: `1.5px solid ${color}`,
          display: 'inline-block',
          boxSizing: 'border-box'
        }}
      />
    );
  } else if (vocab.glyph === 'check') {
    mark = (
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
        <path d="M1.5 5.2 L3.8 7.5 L8.5 2.4" fill="none" stroke={color} strokeWidth="1.6" />
      </svg>
    );
  } else if (vocab.glyph === 'slash') {
    mark = (
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
        <circle cx="5" cy="5" r="3.5" fill="none" stroke={color} strokeWidth="1.4" />
        <path d="M2.4 7.6 L7.6 2.4" stroke={color} strokeWidth="1.4" />
      </svg>
    );
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color, fontSize: 10 }}>
      {mark}
      {vocab.label}
    </span>
  );
};

const wantsField = (block, key) => {
  const fields = Array.isArray(block?.fields) ? block.fields : [];
  if (!fields.length) return true;
  return fields.includes(key);
};

const Hairline = () => <div style={{ height: 1, background: PAPER.line, margin: '10px 0' }} />;

const TempBar = ({ label, value, color, max }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '72px 1fr 28px', gap: 8, alignItems: 'center', marginBottom: 4 }}>
    <span style={{ fontSize: 10, color: PAPER.muted }}>{label}</span>
    <div style={{ height: 6, background: '#E2E8F0', overflow: 'hidden' }}>
      <div style={{ width: `${Math.round((Number(value || 0) / Math.max(max, 1)) * 100)}%`, height: '100%', background: color }} />
    </div>
    <span style={{ fontSize: 10, color: PAPER.ink, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>
      {value}
    </span>
  </div>
);

const PaperBlock = ({ block, context, resolve, company, ink, logoUrl }) => {
  const type = block?.type;
  const title = resolve(block?.title || '');
  const hostOnly = ['open_ports', 'markdown', 'checklists'].includes(type);
  if (hostOnly && (context.scope !== 'host' || (type === 'open_ports' && !(context.open_ports || []).length))) {
    return null;
  }
  if (type === 'chart' && block.chart === 'wave_coverage' && !context.wave?.name) {
    return null;
  }

  if (type === 'cover') {
    const preparedFor = context.scope === 'host' ? context.record?.name : context.application?.name;
    return (
      <div style={{ padding: '20px 8px 16px', textAlign: 'center' }}>
        {block.show_logo ? (
          logoUrl ? (
            <img
              src={logoUrl}
              alt=""
              style={{
                width: '50%',
                maxHeight: 48,
                objectFit: 'contain',
                margin: '0 auto 12px',
                display: 'block'
              }}
            />
          ) : (
            <div
              style={{
                width: '50%',
                margin: '0 auto 12px',
                height: 28,
                background: ink || PAPER.line
              }}
            />
          )
        ) : null}
        <div style={{ fontSize: 16, fontWeight: 700, color: ink || PAPER.ink }}>{company}</div>
        <div style={{ fontSize: 22, fontWeight: 600, color: ink || PAPER.ink, marginTop: 8 }}>{title || 'Pentest Report'}</div>
        <div style={{ fontSize: 12, color: PAPER.muted, marginTop: 6 }}>{resolve(block.subtitle)}</div>
        <div style={{ marginTop: 16, display: 'grid', gap: 4, textAlign: 'left', maxWidth: 280, marginLeft: 'auto', marginRight: 'auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '96px 1fr', fontSize: 11 }}>
            <span style={{ color: PAPER.muted }}>Prepared For</span>
            <span style={{ color: PAPER.ink }}>{preparedFor || '—'}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '96px 1fr', fontSize: 11 }}>
            <span style={{ color: PAPER.muted }}>Prepared By</span>
            <span style={{ color: PAPER.ink }}>{context.pentest?.tested_by || '—'}</span>
          </div>
          {context.export?.watermark ? (
            <div style={{ display: 'grid', gridTemplateColumns: '96px 1fr', fontSize: 11 }}>
              <span style={{ color: PAPER.muted }}>Classification</span>
              <span style={{ color: PAPER.ink }}>{context.export.watermark}</span>
            </div>
          ) : null}
          <div style={{ display: 'grid', gridTemplateColumns: '96px 1fr', fontSize: 11 }}>
            <span style={{ color: PAPER.muted }}>Generated</span>
            <span style={{ color: PAPER.ink }}>{context.generated_date || context.generated_at || '—'}</span>
          </div>
        </div>
      </div>
    );
  }

  if (type === 'page_break') {
    return <Hairline />;
  }

  if (type === 'engagement_overview') {
    const rows =
      context.scope === 'host'
        ? [
            wantsField(block, 'target') ? ['Host', context.record?.name] : null,
            wantsField(block, 'ip') ? ['IP', context.record?.ip_address] : null,
            wantsField(block, 'tester') ? ['Tester', context.pentest?.tested_by] : null,
            wantsField(block, 'dates')
              ? ['Window', `${context.pentest?.test_start_date} – ${context.pentest?.test_end_date}`]
              : null
          ]
        : [
            wantsField(block, 'application') ? ['Application', context.application?.name] : null,
            wantsField(block, 'tester') ? ['Prepared By', context.pentest?.tested_by] : null,
            wantsField(block, 'hosts') ? ['Hosts', String(context.hosts?.length || 0)] : null,
            wantsField(block, 'wave') && context.wave?.name ? ['Wave', context.wave.name] : null
          ].filter(Boolean);
    const visible = rows.filter(Boolean);
    return (
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: PAPER.ink, borderLeft: `3px solid ${PAPER.rail.high}`, paddingLeft: 8 }}>
          {title || 'Engagement Overview'}
        </div>
        <div style={{ marginTop: 8, display: 'grid', gap: 4 }}>
          {visible.map(([label, value]) => (
            <div key={label} style={{ display: 'grid', gridTemplateColumns: '88px minmax(0, 1fr)', fontSize: 11 }}>
              <span style={{ color: PAPER.muted }}>{label}</span>
              <span style={{ color: PAPER.ink, overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{value || '—'}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === 'key_metrics') {
    const items = [
      wantsField(block, 'findings') ? ['Findings', context.metrics?.vulnerability_count] : null,
      wantsField(block, 'open_like') ? ['Open-like', context.metrics?.open_like_count] : null,
      wantsField(block, 'fixed') ? ['Fixed', context.metrics?.occurrence_fixed] : null,
      wantsField(block, 'hosts') ? ['Hosts', context.metrics?.host_count] : null
    ].filter(Boolean);
    return (
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: PAPER.ink, marginBottom: 8 }}>{title || 'Risk Snapshot'}</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          {items.map(([label, value]) => (
            <div key={label} style={{ borderTop: `1px solid ${PAPER.line}`, paddingTop: 6 }}>
              <div style={{ fontSize: 9, color: PAPER.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {label}
              </div>
              <div style={{ fontSize: 18, fontVariantNumeric: 'tabular-nums', color: PAPER.ink }}>{value ?? 0}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === 'table_of_contents') {
    const findings = context.findings || [];
    return (
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: PAPER.ink, marginBottom: 8 }}>
          {title || 'Table of Contents'}
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead>
            <tr>
              {['#', 'Finding', 'Severity'].map((label) => (
                <th
                  key={label}
                  style={{
                    background: ink || PAPER.ink,
                    color: '#fff',
                    fontSize: 9,
                    textAlign: label === 'Finding' ? 'left' : 'center',
                    padding: '4px 6px',
                    width: label === '#' ? '12%' : label === 'Severity' ? '24%' : '64%'
                  }}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {findings.map((finding, index) => {
              const key = severityFromScore(finding.baseScore);
              const cell = SEVERITY_CELL[key] || SEVERITY_CELL.informational;
              return (
                <tr key={finding.id || index}>
                  <td style={{ fontSize: 10, padding: '4px 6px', textAlign: 'center', borderBottom: `1px solid ${PAPER.line}` }}>
                    {index + 1}
                  </td>
                  <td
                    style={{
                      fontSize: 10,
                      padding: '4px 6px',
                      color: PAPER.ink,
                      overflowWrap: 'anywhere',
                      wordBreak: 'break-word',
                      borderBottom: `1px solid ${PAPER.line}`
                    }}
                  >
                    {finding.title}
                  </td>
                  <td
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      textAlign: 'center',
                      padding: '4px 6px',
                      background: cell.bg,
                      color: cell.fg,
                      borderBottom: `1px solid ${PAPER.line}`
                    }}
                  >
                    {cell.label}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  if (type === 'chart') {
    const chart = block.chart;
    const max = Math.max(
      context.metrics?.critical_count || 0,
      context.metrics?.high_count || 0,
      context.metrics?.medium_count || 0,
      context.metrics?.low_count || 0,
      context.metrics?.occurrence_open || 0,
      context.metrics?.occurrence_retest || 0,
      context.metrics?.occurrence_fixed || 0,
      1
    );
    return (
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: PAPER.ink, marginBottom: 8 }}>{title || 'Chart'}</div>
        {chart === 'occurrence_status' ? (
          <>
            <TempBar label="Open" value={context.metrics?.occurrence_open || 0} color={PAPER.rail.critical} max={max} />
            <TempBar label="Retest" value={context.metrics?.occurrence_retest || 0} color={PAPER.rail.medium} max={max} />
            <TempBar label="Fixed" value={context.metrics?.occurrence_fixed || 0} color={PAPER.rail.low} max={max} />
          </>
        ) : (
          <>
            <TempBar label="Critical" value={context.metrics?.critical_count || 0} color={PAPER.rail.critical} max={max} />
            <TempBar label="High" value={context.metrics?.high_count || 0} color={PAPER.rail.high} max={max} />
            <TempBar label="Medium" value={context.metrics?.medium_count || 0} color={PAPER.rail.medium} max={max} />
            <TempBar label="Low" value={context.metrics?.low_count || 0} color={PAPER.rail.low} max={max} />
          </>
        )}
      </div>
    );
  }

  if (type === 'open_ports') {
    return (
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: PAPER.ink }}>{title || 'Open Ports'}</div>
        <div style={{ fontSize: 11, color: PAPER.ink, marginTop: 6 }}>{(context.open_ports || []).join(', ')}</div>
      </div>
    );
  }

  if (type === 'markdown' || type === 'text') {
    const body = type === 'text' ? resolve(block.content) : context.record?.description || '';
    return (
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: PAPER.ink }}>{title || 'Section'}</div>
        <div style={{ fontSize: 11, color: PAPER.ink, marginTop: 6, whiteSpace: 'pre-wrap' }}>{body}</div>
      </div>
    );
  }

  if (type === 'vulnerabilities') {
    return (
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: PAPER.ink, marginBottom: 8 }}>
          {title || 'Detailed Findings'}
        </div>
        {(context.findings || []).map((finding) => {
          const severity = severityFromScore(finding.baseScore);
          return (
            <div
              key={finding.id}
              style={{
                position: 'relative',
                padding: '8px 8px 8px 12px',
                marginBottom: 8,
                borderBottom: `1px solid ${PAPER.line}`
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 8,
                  bottom: 8,
                  width: 3,
                  background: PAPER.rail[severity] || PAPER.rail.low
                }}
              />
              <div style={{ fontSize: 12, fontWeight: 600, color: PAPER.ink }}>{finding.title}</div>
              <div style={{ fontSize: 10, color: PAPER.muted, marginTop: 2 }}>
                {finding.category} · {severity}
              </div>
              {finding.impact ? (
                <div style={{ fontSize: 10, color: PAPER.ink, marginTop: 4 }}>{finding.impact}</div>
              ) : null}
              <div style={{ marginTop: 6, display: 'grid', gap: 3 }}>
                {(finding.occurrences || []).map((occ) => (
                  <div
                    key={`${finding.id}-${occ.dns_name}-${occ.status}`}
                    style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 10, color: PAPER.ink }}
                  >
                    <PaperStatus status={occ.status} />
                    <span>{occ.dns_name}</span>
                    <span style={{ color: PAPER.muted }}>{occ.environment_slug}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return null;
};

const ReportTemplatePaperPreview = ({ templateForm, previewKind, brandKit }) => {
  const context = useMemo(() => sampleReportContext(previewKind), [previewKind]);
  const flat = useMemo(() => {
    const merged = {
      ...flattenContext(context),
      report_title: templateForm?.placeholders?.report_title || '',
      report_subtitle: templateForm?.placeholders?.report_subtitle || '',
      prepared_by: templateForm?.placeholders?.prepared_by || '',
      prepared_for: templateForm?.placeholders?.prepared_for || ''
    };
    return merged;
  }, [context, templateForm?.placeholders]);
  const resolve = (text) => resolvePreviewText(text, flat);
  const branding = templateForm?.branding || {};
  const company = brandKit?.company_name || branding.company_name || 'Security Operations';
  const header = branding.header_text || company;
  const classification = branding.classification || context.export?.watermark || '';
  const footer = [branding.footer_text || company, context.generated_date || context.generated_at]
    .filter(Boolean)
    .join(' · ');
  const ink = brandKit?.print_ink || PAPER.rail.high;
  const logoUrl = brandKit?.logo_url || '';

  return (
    <div
      style={{
        position: 'relative',
        background: PAPER.page,
        color: PAPER.ink,
        border: `1px solid ${PAPER.line}`,
        aspectRatio: '1 / 1.414',
        width: '100%',
        overflow: 'auto',
        padding: '16px 16px 64px',
        boxSizing: 'border-box'
      }}
    >
      <div style={{ height: 3, background: ink, margin: '-16px -16px 12px' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: PAPER.muted, marginBottom: 12 }}>
        <span>{header}</span>
        <span>{classification || context.application?.name}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {(templateForm?.blocks || []).map((block, index) => (
          <PaperBlock
            key={block._uiId || index}
            block={block}
            context={context}
            resolve={resolve}
            company={company}
            ink={ink}
            logoUrl={logoUrl}
          />
        ))}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 12,
          bottom: 10,
          display: 'flex',
          alignItems: 'flex-end'
        }}
      >
        <img src={RAPTOR_BRAND.lockupPrint} alt="RAPTOR" style={{ height: 40, display: 'block' }} />
      </div>
      <div
        style={{
          position: 'absolute',
          right: 16,
          bottom: 16,
          fontSize: 8,
          color: PAPER.muted,
          maxWidth: '55%',
          textAlign: 'right'
        }}
      >
        {footer}
      </div>
    </div>
  );
};

export default ReportTemplatePaperPreview;
