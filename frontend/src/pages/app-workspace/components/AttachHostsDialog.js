import React, { useEffect, useState } from 'react';
import { Alert } from '@mui/material';
import { Button, Panel, Text } from '../../../design/primitives';
import HostPicker from './HostPicker';

const AttachHostsDialog = ({ open, finding, appId, sharedHosts = [], onClose, onSave }) => {
  const [selected, setSelected] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const attachedIds = (finding?.occurrences || []).map((item) => item.record_id);

  useEffect(() => {
    if (open) {
      setSelected([]);
      setSubmitting(false);
    }
  }, [open, finding?.id]);

  const submit = async () => {
    const ids = selected.map((host) => host.id).filter((id) => !attachedIds.map(String).includes(String(id)));
    if (ids.length === 0) return;
    setSubmitting(true);
    try {
      await onSave(ids);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel
      open={open}
      onClose={onClose}
      title="Attach hosts"
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="contained" disabled={selected.length === 0 || submitting} onClick={submit}>
            Attach
          </Button>
        </>
      }
    >
      <Alert severity="info">
        Search the application. Each host becomes an occurrence of this finding. This does not attach an entire
        environment.
      </Alert>
      <Text as="div" variant="bodyStrong" style={{ marginBottom: 8 }}>
        {finding?.title || 'Finding'}
      </Text>
      <HostPicker
        appId={appId}
        sharedHosts={sharedHosts}
        label="Hosts"
        placeholder="Search hosts in this application"
        multiple
        value={selected}
        excludeIds={attachedIds}
        onChange={(value) => setSelected(value || [])}
      />
    </Panel>
  );
};

export default AttachHostsDialog;
