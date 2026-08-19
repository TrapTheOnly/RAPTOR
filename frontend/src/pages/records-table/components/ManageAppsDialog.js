import React, { useState } from 'react';
import { Button, DataList, DataRow, EmptyState, Field, Panel, Text } from '../../../design/primitives';

const ManageAppsDialog = ({
  open,
  onClose,
  apps,
  newAppName,
  onSetNewAppName,
  appEdits,
  onSetAppEdits,
  appsBusy,
  onCreateApp,
  onRenameApp,
  onDeleteApp
}) => {
  const [confirmId, setConfirmId] = useState(null);

  return (
    <Panel
      open={open}
      onClose={onClose}
      title="Manage applications"
      maxWidth="sm"
      actions={
        <Button onClick={onClose} variant="outlined">
          Close
        </Button>
      }
    >
      <Text as="p" variant="meta" tone="secondary" style={{ margin: 0 }}>
        Group domains into applications. Assign a domain by editing the record.
      </Text>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
        <Field
          label="New application"
          value={newAppName}
          onChange={(event) => onSetNewAppName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onCreateApp();
          }}
        />
        <Button
          variant="contained"
          onClick={onCreateApp}
          disabled={!newAppName.trim() || appsBusy}
          style={{ marginBottom: 0 }}
        >
          Create
        </Button>
      </div>

      {apps.length === 0 ? (
        <EmptyState title="No applications yet" hint="Create one to start grouping domains." />
      ) : (
        <DataList>
          {apps.map((app) => {
            const confirming = confirmId === app.id;
            return (
              <DataRow
                key={app.id}
                id={app.id}
                title={
                  confirming ? (
                    <Text variant="bodyStrong">Delete {app.name}?</Text>
                  ) : (
                    <Field
                      aria-label={`Rename ${app.name}`}
                      value={appEdits[app.id] ?? app.name}
                      onChange={(event) =>
                        onSetAppEdits((prev) => ({ ...prev, [app.id]: event.target.value }))
                      }
                      onClick={(event) => event.stopPropagation()}
                    />
                  )
                }
                meta={
                  confirming ? (
                    <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 4 }}>
                      Domains will be unassigned.
                    </Text>
                  ) : null
                }
                trailing={
                  <div style={{ display: 'flex', gap: 8 }} onClick={(event) => event.stopPropagation()}>
                    {confirming ? (
                      <>
                        <Button size="small" onClick={() => setConfirmId(null)}>
                          Cancel
                        </Button>
                        <Button
                          size="small"
                          variant="contained"
                          disabled={appsBusy}
                          onClick={() => {
                            onDeleteApp(app.id);
                            setConfirmId(null);
                          }}
                        >
                          Delete
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button size="small" variant="outlined" disabled={appsBusy} onClick={() => onRenameApp(app.id)}>
                          Save
                        </Button>
                        <Button size="small" disabled={appsBusy} onClick={() => setConfirmId(app.id)}>
                          Delete
                        </Button>
                      </>
                    )}
                  </div>
                }
              />
            );
          })}
        </DataList>
      )}
    </Panel>
  );
};

export default ManageAppsDialog;
