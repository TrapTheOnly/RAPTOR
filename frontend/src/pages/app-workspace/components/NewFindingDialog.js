import React, { useEffect, useState } from 'react';
import { Alert } from '@mui/material';
import { Button, Combo, Field, Panel } from '../../../design/primitives';
import HostPicker from './HostPicker';

const AUTH_OPTIONS = [
  { value: '', label: 'Not specified' },
  { value: 'unauth', label: 'unauth' },
  { value: 'user', label: 'user' },
  { value: 'admin', label: 'admin' },
  { value: 'sso', label: 'sso' }
];

const emptyForm = {
  title: '',
  record_id: '',
  record_ids: [],
  description: '',
  impact: '',
  evidence: '',
  remediation: '',
  auth_context: '',
  ticket_url: ''
};

const NewFindingDialog = ({ open, appId, sharedHosts = [], lockedHost = null, envId, waveId, onClose, onCreate }) => {
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [foundHere, setFoundHere] = useState(null);
  const [alsoAffects, setAlsoAffects] = useState([]);

  useEffect(() => {
    if (open) {
      setForm({
        ...emptyForm,
        record_id: lockedHost?.id || ''
      });
      setFoundHere(lockedHost || null);
      setAlsoAffects([]);
      setSubmitting(false);
    }
  }, [open, lockedHost]);

  const foundHereId = foundHere?.id || form.record_id;

  const submit = async () => {
    setSubmitting(true);
    try {
      await onCreate({ ...form, wave_id: waveId || undefined });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel
      open={open}
      onClose={onClose}
      title="New finding"
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="contained"
            onClick={submit}
            disabled={!form.title.trim() || !form.record_id || !waveId || submitting}
          >
            Create finding
          </Button>
        </>
      }
    >
      <Alert severity="info">
        {waveId
          ? 'Write the finding once. Search the application for the host you proved it on, then attach every other host it affects. It is stamped with this wave.'
          : 'Findings are filed from an engagement wave. Open a wave, then create the finding there.'}
      </Alert>
      <Field
        autoFocus
        label="Title"
        placeholder="Permissive CORS policy on API gateway"
        value={form.title}
        onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
      />
      <HostPicker
        appId={appId}
        sharedHosts={sharedHosts}
        envId={envId}
        label="Found-here host"
        placeholder="Search the host you proved it on"
        value={foundHere}
        locked={Boolean(lockedHost)}
        onChange={(value) => {
          const nextAlso = alsoAffects.filter((item) => String(item.id) !== String(value?.id));
          setFoundHere(value);
          setAlsoAffects(nextAlso);
          setForm((prev) => ({
            ...prev,
            record_id: value?.id || '',
            record_ids: nextAlso.map((item) => item.id)
          }));
        }}
      />
      <HostPicker
        appId={appId}
        sharedHosts={sharedHosts}
        envId={envId}
        label="Also affects"
        placeholder="Search more hosts in this application"
        multiple
        value={alsoAffects}
        excludeIds={foundHereId ? [foundHereId] : []}
        onChange={(value) => {
          const next = (value || []).filter((item) => String(item.id) !== String(foundHereId || ''));
          setAlsoAffects(next);
          setForm((prev) => ({ ...prev, record_ids: next.map((item) => item.id) }));
        }}
      />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Combo
          label="Auth context"
          options={AUTH_OPTIONS}
          value={form.auth_context}
          onChange={(value) => setForm((prev) => ({ ...prev, auth_context: value }))}
        />
        <Field
          label="Ticket URL"
          placeholder="https://…"
          value={form.ticket_url}
          onChange={(event) => setForm((prev) => ({ ...prev, ticket_url: event.target.value }))}
        />
      </div>
      <Field
        multiline
        minRows={3}
        label="Description"
        placeholder="What you found. Hosts stay on the occurrence table."
        value={form.description}
        onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
      />
      <Field
        multiline
        minRows={3}
        label="Impact"
        placeholder="What an attacker can do in this environment."
        value={form.impact}
        onChange={(event) => setForm((prev) => ({ ...prev, impact: event.target.value }))}
      />
      <Field
        multiline
        minRows={3}
        label="Evidence"
        placeholder="Proof, requests, and screenshots. Add images on the finding page."
        value={form.evidence}
        onChange={(event) => setForm((prev) => ({ ...prev, evidence: event.target.value }))}
      />
      <Field
        multiline
        minRows={3}
        label="Remediation"
        placeholder="How to fix it and what to retest."
        value={form.remediation}
        onChange={(event) => setForm((prev) => ({ ...prev, remediation: event.target.value }))}
      />
    </Panel>
  );
};

export default NewFindingDialog;
