import React from 'react';
import { Button, Combo, Field, Panel, Text } from '../../../design/primitives';

const CreateManualRecordDialog = ({
  open,
  form,
  apps,
  environments = [],
  busy,
  error,
  onClose,
  onChange,
  onSubmit
}) => {
  const selectedApp = apps.find((app) => Number(app.id) === Number(form.application_id)) || null;
  const selectedEnv =
    environments.find((env) => Number(env.id) === Number(form.environment_id)) || null;

  return (
    <Panel
      open={open}
      onClose={busy ? undefined : onClose}
      title="Add Manual Domain"
      actions={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={onSubmit} variant="contained" disabled={busy}>
            Create
          </Button>
        </>
      }
    >
      <Text as="p" variant="meta" tone="secondary" style={{ margin: 0 }}>
        Manual domains stay in the main registry and can later be adopted into automated sync if a
        collector or cloud DNS source starts publishing the same name.
      </Text>
      <Field
        autoFocus
        label="Domain"
        value={form.name}
        onChange={(event) => onChange('name', event.target.value)}
        placeholder="api.example.com"
      />
      <Field
        label="IP address"
        value={form.ip_address}
        onChange={(event) => onChange('ip_address', event.target.value)}
        placeholder="10.10.10.10"
      />
      <Combo
        label="Application"
        options={apps}
        value={selectedApp}
        onChange={(app) => onChange('application_id', app?.id || '')}
        getOptionLabel={(app) => app?.name || ''}
        placeholder="Unassigned"
        disableClearable={false}
        mode="entity"
      />
      <Combo
        label="Environment"
        options={environments}
        value={selectedEnv}
        onChange={(env) => onChange('environment_id', env?.id || '')}
        getOptionLabel={(env) => env?.display_name || env?.name || ''}
        placeholder="Unassigned"
        disableClearable={false}
        disabled={!form.application_id}
        mode="entity"
      />
      <Field
        label="Application owner"
        value={form.application_owner}
        onChange={(event) => onChange('application_owner', event.target.value)}
      />
      <Field
        label="Maintainer"
        value={form.maintainer}
        onChange={(event) => onChange('maintainer', event.target.value)}
      />
      <Field
        label="Open ports"
        value={form.open_ports}
        onChange={(event) => onChange('open_ports', event.target.value)}
        placeholder="22, 80, 443"
      />
      <Field
        label="Description"
        value={form.description}
        onChange={(event) => onChange('description', event.target.value)}
        multiline
        minRows={3}
      />
      {error ? (
        <Text variant="meta" tone="critical">
          {error}
        </Text>
      ) : null}
    </Panel>
  );
};

export default CreateManualRecordDialog;
