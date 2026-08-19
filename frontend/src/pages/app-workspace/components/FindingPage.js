import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Alert } from '@mui/material';
import { ArrowBack, CallMerge, ConfirmationNumber, PlaylistAdd, Save, TrendingUp } from '@mui/icons-material';
import {
  Button,
  Combo,
  Field,
  Mono,
  Page,
  PageHeader,
  Progress,
  StatusGlyph,
  Tag,
  Text
} from '../../../design/primitives';
import { SPACE, TYPE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';
import { DEFAULT_CVSS_METRICS } from '../../pentest-record/constants';
import { calculateCvssBase } from '../../pentest-record/cvss';
import { fetchVulnerabilityCategories, uploadPentestImage } from '../../pentest-record/services';
import MarkdownEditorCard from '../../pentest-record/components/MarkdownEditorCard';
import { getFinding, patchFinding } from '../services';
import CvssCalculator from './CvssCalculator';
import FindingCard from './FindingCard';

const AUTH_OPTIONS = [
  { value: '', label: 'Not specified' },
  { value: 'unauth', label: 'unauth' },
  { value: 'user', label: 'user' },
  { value: 'admin', label: 'admin' },
  { value: 'sso', label: 'sso' }
];

const FactChip = ({ kicker, to, weight = 'plain', children }) => {
  const palette = usePalette();
  const backgrounds = {
    host: palette.raised,
    wave: palette.hover,
    env: palette.surface,
    plain: palette.canvas
  };
  const inner = (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        height: 32,
        padding: '0 10px',
        borderRadius: 4,
        border: `1px solid ${palette.line}`,
        background: backgrounds[weight] || backgrounds.plain,
        color: palette.text,
        boxSizing: 'border-box'
      }}
    >
      <span style={{ ...TYPE.micro, color: palette.textTertiary, letterSpacing: '0.04em' }}>{kicker}</span>
      <span style={{ fontSize: 13, lineHeight: '16px', fontWeight: 500 }}>{children}</span>
    </span>
  );
  if (!to) return inner;
  return (
    <RouterLink to={to} style={{ color: 'inherit', textDecoration: 'none' }}>
      {inner}
    </RouterLink>
  );
};

const FindingPage = ({
  appId,
  app,
  findingId,
  canModify,
  pentestUsers = [],
  onAttachHosts,
  onOpenTicket,
  onOpenMerge,
  onPromote,
  onOccurrenceStatusChange,
  busyFinding,
  failWith,
  notify
}) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [payload, setPayload] = useState(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [authContext, setAuthContext] = useState('');
  const [ticketUrl, setTicketUrl] = useState('');
  const [category, setCategory] = useState(null);
  const [categories, setCategories] = useState([]);
  const [metrics, setMetrics] = useState(DEFAULT_CVSS_METRICS);
  const [collaborators, setCollaborators] = useState([]);
  const [editingMarkdown, setEditingMarkdown] = useState(false);
  const [imageUploading, setImageUploading] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    const [findingRes, categoriesRes] = await Promise.all([
      getFinding(findingId),
      fetchVulnerabilityCategories().catch(() => ({ data: [] }))
    ]);
    const data = findingRes.data;
    const finding = data.finding || {};
    setPayload(data);
    setTitle(finding.title || '');
    setDescription(finding.description || '');
    setAuthContext(finding.auth_context || '');
    setTicketUrl(finding.ticket_url || '');
    setMetrics({ ...DEFAULT_CVSS_METRICS, ...(finding.metrics || {}) });
    setCollaborators(finding.collaborators || []);
    const cats = Array.isArray(categoriesRes.data)
      ? categoriesRes.data
      : categoriesRes.data?.categories || [];
    setCategories(cats);
    const match =
      cats.find((item) => String(item.id) === String(finding.categoryId)) ||
      (finding.categoryName ? { id: finding.categoryId || finding.categoryName, name: finding.categoryName } : null);
    setCategory(match);
    setDirty(false);
  }, [findingId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    load()
      .catch((error) => failWith(error, 'Failed to load finding.'))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load, failWith]);

  const finding = payload?.finding;
  const wave = payload?.wave;
  const environment = payload?.environment;
  const foundHere = payload?.found_here;
  const score = useMemo(() => calculateCvssBase(metrics), [metrics]);

  const markDirty = (updater) => {
    setDirty(true);
    updater();
  };

  const handleSave = async () => {
    if (!finding) return;
    setSaving(true);
    try {
      await patchFinding(finding.id, {
        title,
        description,
        auth_context: authContext,
        ticket_url: ticketUrl,
        categoryId: category?.id || '',
        categoryName: category?.name || '',
        metrics,
        baseScore: score,
        collaborators
      });
      await load();
      notify('success', 'Finding saved.');
    } catch (error) {
      failWith(error, 'Failed to save finding.');
    } finally {
      setSaving(false);
    }
  };

  const insertImage = (url) => {
    setDescription((prev) => `${prev || ''}\n\n![uploaded-image](${url})\n`);
    setDirty(true);
    setEditingMarkdown(true);
  };

  const handleImageUpload = async (file) => {
    if (!file || !foundHere?.id) return;
    setImageUploading(true);
    try {
      const response = await uploadPentestImage(foundHere.id, file);
      insertImage(response.data.url);
    } catch (error) {
      failWith(error, 'Image upload failed.');
    } finally {
      setImageUploading(false);
    }
  };

  const handlePasteImage = async (event) => {
    const items = event.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        event.preventDefault();
        await handleImageUpload(item.getAsFile());
        break;
      }
    }
  };

  const backTo = `/apps/${appId}`;

  if (loading && !finding) {
    return (
      <Page>
        <PageHeader
          crumbs={[{ label: 'Applications', to: '/pentest' }, { label: app?.name || 'Application', to: backTo }]}
          title="Finding"
          subtitle="Loading…"
        />
        <Progress deferred />
      </Page>
    );
  }

  if (!finding) {
    return (
      <Page>
        <Alert severity="error">Finding not found.</Alert>
      </Page>
    );
  }

  const userOptions = [...new Set([...(pentestUsers || []), ...(collaborators || []), finding.created_by].filter(Boolean))];

  return (
    <Page>
      <PageHeader
        crumbs={[
          { label: 'Applications', to: '/pentest' },
          { label: app?.name || 'Application', to: backTo },
          { label: 'Findings', to: backTo },
          { label: title || finding.categoryName || 'Finding' }
        ]}
        leading={
          <Button
            size="small"
            startIcon={<ArrowBack sx={{ fontSize: 16 }} />}
            onClick={() => navigate(backTo, { state: { tab: 'findings' } })}
          >
            Findings
          </Button>
        }
        title={title || finding.categoryName || 'Untitled finding'}
        subtitle="Write the narrative once. Score it. Attach evidence. Occurrences stay on the hosts it touches."
        meta={
          <>
            {score > 0 ? <Tag emphasized>{score.toFixed(1)}</Tag> : <Tag>unscored</Tag>}
            <StatusGlyph status={finding.status} />
          </>
        }
        actions={
          canModify ? (
            <>
              <Button
                variant="contained"
                startIcon={<Save sx={{ fontSize: 16 }} />}
                onClick={handleSave}
                disabled={!dirty || saving}
              >
                {saving ? 'Saving…' : 'Save'}
              </Button>
              {finding.status === 'draft' && onPromote ? (
                <Button variant="outlined" startIcon={<TrendingUp />} onClick={() => onPromote(finding)}>
                  Promote to open
                </Button>
              ) : null}
              {onAttachHosts ? (
                <Button variant="outlined" startIcon={<PlaylistAdd />} onClick={() => onAttachHosts(finding)}>
                  Attach hosts
                </Button>
              ) : null}
              {onOpenTicket ? (
                <Button variant="outlined" startIcon={<ConfirmationNumber />} onClick={() => onOpenTicket(finding)}>
                  {ticketUrl ? 'Edit ticket' : 'Link ticket'}
                </Button>
              ) : null}
              {onOpenMerge ? (
                <Button variant="outlined" startIcon={<CallMerge />} onClick={() => onOpenMerge(finding)}>
                  Merge into this
                </Button>
              ) : null}
            </>
          ) : null
        }
      />

      <div
        style={{
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap',
          alignItems: 'center',
          minHeight: 32,
          marginBottom: SPACE.x24
        }}
      >
        {foundHere ? (
          <FactChip kicker="Found here" to={`/pentest/record/${foundHere.id}`} weight="host">
            <Mono>{foundHere.name}</Mono>
          </FactChip>
        ) : null}
        {wave ? (
          <FactChip kicker="Wave" to={`/apps/${appId}/waves/${wave.id}`} weight="wave">
            {wave.name}
          </FactChip>
        ) : (
          <FactChip kicker="Wave">Unassigned</FactChip>
        )}
        {environment ? (
          <FactChip kicker="Environment" to={`/apps/${appId}/envs/${environment.id}`} weight="env">
            {environment.display_name || environment.slug}
          </FactChip>
        ) : null}
        <FactChip kicker="Reported by" weight="plain">
          {finding.created_by || 'unknown'}
        </FactChip>
      </div>

      <div
        style={{
          display: 'grid',
          gap: SPACE.x32,
          gridTemplateColumns: 'minmax(280px, 360px) minmax(0, 1fr)',
          alignItems: 'start'
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x24 }}>
          <Field
            label="Title"
            value={title}
            onChange={(event) => markDirty(() => setTitle(event.target.value))}
            disabled={!canModify}
          />
          <Combo
            label="Category"
            placeholder="Select a vulnerability category"
            mode="entity"
            options={categories}
            value={category}
            getOptionLabel={(option) => option?.name || ''}
            isOptionEqualToValue={(a, b) => String(a?.id) === String(b?.id)}
            onChange={(value) => markDirty(() => setCategory(value))}
            disabled={!canModify}
          />
          <Combo
            label="Auth context"
            options={AUTH_OPTIONS}
            value={authContext}
            onChange={(value) => markDirty(() => setAuthContext(value))}
            disabled={!canModify}
          />
          <Field
            label="Ticket URL"
            value={ticketUrl}
            onChange={(event) => markDirty(() => setTicketUrl(event.target.value))}
            disabled={!canModify}
            placeholder="https://…"
          />
          <Combo
            label="Collaborators"
            placeholder="People on this finding"
            multiple
            freeSolo
            mode="enum"
            options={userOptions.map((name) => ({ value: name, label: name }))}
            value={collaborators}
            onChange={(value) => markDirty(() => setCollaborators(value || []))}
            disabled={!canModify}
          />
          <CvssCalculator
            metrics={metrics}
            score={score}
            disabled={!canModify}
            onChange={(next) => markDirty(() => setMetrics(next))}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x24 }}>
          <MarkdownEditorCard
            title="Description"
            value={description}
            isEditing={editingMarkdown}
            onToggleEditing={() => setEditingMarkdown((prev) => !prev)}
            onChange={(value) => markDirty(() => setDescription(value))}
            onUploadImage={handleImageUpload}
            onPasteImage={handlePasteImage}
            placeholder="What you found, how you proved it, and the impact. Paste or upload images."
            emptyText="No write-up yet. Edit to add markdown and evidence."
            minRows={16}
            canEdit={canModify}
            canUploadImages={Boolean(foundHere?.id)}
            imageUploading={imageUploading}
          />
        </div>
      </div>

      <section style={{ marginTop: SPACE.x32 }}>
        <Text as="div" variant="h2" style={{ marginBottom: 12 }}>
          Hosts this finding touches
        </Text>
        <FindingCard
          finding={{ ...finding, title, collaborators, occurrences: finding.occurrences || [] }}
          appId={appId}
          canModify={canModify}
          busy={busyFinding === finding.id}
          defaultExpanded
          hideNarrative
          showActions={false}
          onOccurrenceStatusChange={onOccurrenceStatusChange}
        />
        {foundHere ? (
          <Text as="p" variant="meta" tone="secondary" style={{ marginTop: 12 }}>
            Found-here host is <Mono>{foundHere.name}</Mono>. Open its notebook for recon and checklists.
          </Text>
        ) : null}
      </section>
    </Page>
  );
};

export default FindingPage;
