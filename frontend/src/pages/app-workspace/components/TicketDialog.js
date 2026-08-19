import React, { useEffect, useState } from 'react';
import { Button, Field, Panel, Text } from '../../../design/primitives';
import { isHttpUrl } from './FindingCard';

const TicketDialog = ({ open, finding, onClose, onSave }) => {
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setValue(finding?.ticket_url || '');
      setError('');
    }
  }, [open, finding]);

  const handleSave = () => {
    const trimmed = value.trim();
    if (trimmed && !isHttpUrl(trimmed)) {
      setError('Enter a full URL starting with http:// or https://');
      return;
    }
    onSave(trimmed);
  };

  return (
    <Panel
      open={open}
      onClose={onClose}
      title="Link remediation ticket"
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="contained" onClick={handleSave}>
            Save
          </Button>
        </>
      }
    >
      <Text variant="meta" tone="secondary">
        One ticket tracks the whole finding across every host it affects.
      </Text>
      <Field
        autoFocus
        label="Ticket URL"
        placeholder="https://jira.example.com/browse/SEC-1234"
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          setError('');
        }}
        error={error}
        hint={error ? undefined : 'Leave empty to unlink the current ticket.'}
      />
    </Panel>
  );
};

export default TicketDialog;
