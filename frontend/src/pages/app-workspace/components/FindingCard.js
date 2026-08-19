import React, { useState } from 'react';
import { IconButton, Tooltip } from '@mui/material';
import {
  CallMerge,
  ConfirmationNumber,
  Launch,
  PlaylistAdd,
  TrendingUp
} from '@mui/icons-material';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Button,
  Combo,
  DataRow,
  EnvTag,
  Mono,
  StatusGlyph,
  Tag,
  Text,
  severityKeyFromScore
} from '../../../design/primitives';
import { OCCURRENCE_STATUS_OPTIONS, statusMeta } from '../../../theme/tokens';

export const isHttpUrl = (value) => /^https?:\/\//i.test(String(value || '').trim());

const OccurrenceRow = ({ occurrence, canModify, busy, onStatusChange }) => {
  const isMissing = occurrence.host_status === 'missing';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        flexWrap: 'wrap',
        padding: '6px 0',
        opacity: isMissing ? 0.6 : 1
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <EnvTag slug={occurrence.environment_slug} label={occurrence.environment_slug || 'unassigned'} />
        <Mono style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {occurrence.dns_name || `record ${occurrence.record_id}`}
        </Mono>
        {isMissing ? <Tag>missing</Tag> : null}
        {occurrence.primary_url ? (
          <Tooltip title={occurrence.primary_url}>
            <IconButton size="small" component="a" href={occurrence.primary_url} target="_blank" rel="noreferrer">
              <Launch sx={{ fontSize: 15 }} />
            </IconButton>
          </Tooltip>
        ) : null}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {occurrence.evidence_note ? (
          <Text variant="meta" tone="secondary" style={{ maxWidth: 260 }}>
            {occurrence.evidence_note}
          </Text>
        ) : null}
        {canModify ? (
          <Combo
            aria-label="Occurrence status"
            options={OCCURRENCE_STATUS_OPTIONS.map((option) => ({
              value: option,
              label: statusMeta(option).label
            }))}
            value={OCCURRENCE_STATUS_OPTIONS.includes(occurrence.status) ? occurrence.status : 'open'}
            disabled={busy}
            onChange={(value) => onStatusChange(occurrence.record_id, value)}
            fullWidth={false}
            style={{ width: 148 }}
          />
        ) : (
          <StatusGlyph status={occurrence.status} />
        )}
        <Tooltip title="Open host notebook">
          <IconButton size="small" component={RouterLink} to={`/pentest/record/${occurrence.record_id}`}>
            <Launch sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </div>
    </div>
  );
};

const FindingCard = ({
  finding,
  appId,
  canModify,
  busy,
  onOccurrenceStatusChange,
  onOpenTicket,
  onOpenMerge,
  onPromote,
  onAttachHosts,
  defaultExpanded = false,
  hideNarrative = false,
  showActions = true
}) => {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const score = Number(finding.baseScore || 0);
  const findingPath = appId ? `/apps/${appId}/findings/${finding.id}` : null;
  const severity = severityKeyFromScore(score);
  const occurrences = finding.occurrences || [];
  const openCount = occurrences.filter((item) =>
    ['open', 'draft', 'retest'].includes(String(item.status || '').toLowerCase())
  ).length;
  const envSlugs = [...new Set(occurrences.map((item) => item.environment_slug).filter(Boolean))];
  const isScannerDraft = finding.source === 'scanner' && finding.status === 'draft';
  const ticketUrl = String(finding.ticket_url || '').trim();
  const ticketIsLink = isHttpUrl(ticketUrl);
  const severityLabel = score > 0
    ? `${severity === 'none' ? 'Unscored' : severity.charAt(0).toUpperCase() + severity.slice(1)} ${score.toFixed(1)}`
    : 'Unscored';

  return (
    <DataRow
      id={finding.id}
      severity={severity}
      expanded={hideNarrative ? true : expanded}
      onToggle={() => {
        if (findingPath && !hideNarrative) {
          navigate(findingPath);
          return;
        }
        setExpanded((prev) => !prev);
      }}
      title={
        findingPath ? (
          <Text
            as={RouterLink}
            variant="bodyStrong"
            to={findingPath}
            onClick={(event) => event.stopPropagation()}
            style={{ color: 'inherit', textDecoration: 'none' }}
          >
            {finding.title || finding.categoryName || 'Untitled finding'}
          </Text>
        ) : (
          <Text as="div" variant="bodyStrong">
            {finding.title || finding.categoryName || 'Untitled finding'}
          </Text>
        )
      }
      meta={
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 4 }}>
          <Tag>{severityLabel}</Tag>
          <StatusGlyph status={finding.status} />
          {isScannerDraft ? <Tag>scanner</Tag> : null}
          {finding.auth_context ? <Tag>{finding.auth_context}</Tag> : null}
          <Text variant="meta" tone="secondary">
            {occurrences.length} host{occurrences.length === 1 ? '' : 's'}
            {openCount > 0 && occurrences.length !== openCount ? ` · ${openCount} still open` : ''}
          </Text>
          {envSlugs.map((slug) => (
            <EnvTag key={slug} slug={slug} label={slug} />
          ))}
        </div>
      }
      trailing={
        ticketUrl ? (
          <Tooltip title={ticketIsLink ? ticketUrl : 'Ticket is not a URL. Click to fix.'}>
            <IconButton
              size="small"
              {...(ticketIsLink
                ? { component: 'a', href: ticketUrl, target: '_blank', rel: 'noreferrer' }
                : {})}
              onClick={(event) => {
                event.stopPropagation();
                if (!ticketIsLink && onOpenTicket) onOpenTicket(finding);
              }}
            >
              <ConfirmationNumber sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        ) : null
      }
    >
      <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
        Occurrences
      </Text>
      {occurrences.length === 0 ? (
        <Text variant="meta" tone="secondary">
          No occurrences attached yet.
        </Text>
      ) : (
        occurrences.map((occurrence) => (
          <OccurrenceRow
            key={`${occurrence.finding_id}-${occurrence.record_id}`}
            occurrence={occurrence}
            canModify={canModify}
            busy={busy}
            onStatusChange={(recordId, status) => onOccurrenceStatusChange(finding.id, recordId, status)}
          />
        ))
      )}
      {canModify && showActions ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          {finding.status === 'draft' && onPromote ? (
            <Button size="small" variant="contained" startIcon={<TrendingUp />} onClick={() => onPromote(finding)}>
              Promote to open
            </Button>
          ) : null}
          {onAttachHosts ? (
            <Button size="small" variant="outlined" startIcon={<PlaylistAdd />} onClick={() => onAttachHosts(finding)}>
              Attach hosts
            </Button>
          ) : null}
          {onOpenTicket ? (
            <Button size="small" variant="outlined" startIcon={<ConfirmationNumber />} onClick={() => onOpenTicket(finding)}>
              {finding.ticket_url ? 'Edit ticket' : 'Link ticket'}
            </Button>
          ) : null}
          {onOpenMerge ? (
            <Button size="small" variant="outlined" startIcon={<CallMerge />} onClick={() => onOpenMerge(finding)}>
              Merge into this
            </Button>
          ) : null}
        </div>
      ) : null}
    </DataRow>
  );
};

export default FindingCard;
