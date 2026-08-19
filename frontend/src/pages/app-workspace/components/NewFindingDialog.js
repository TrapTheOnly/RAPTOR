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
        minRows={4}
        label="Description"
        placeholder="What you found, how you proved it, and the impact"
        value={form.description}
        onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
      />
    </Panel>
  );
};

export default NewFindingDialog;
