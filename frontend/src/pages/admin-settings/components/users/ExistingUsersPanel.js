import React, { useMemo, useState } from 'react';
import { DeleteOutline, EditOutlined, People as PeopleIcon } from '@mui/icons-material';
import {
  Button,
  Combo,
  EmptyState,
  Field,
  Mono,
  Panel,
  Surface,
  Tag,
  Text
} from '../../../../design/primitives';
import { SPACE, alpha } from '../../../../design/tokens';
import { usePalette } from '../../../../design/usePalette';
import { ROLE_OPTIONS } from '../../constants';
import { getRoleMeta, normalizeOptionalPermissions } from '../../utils';
import AuthTypeChip from '../AuthTypeChip';
import OptionalPermissionControls from '../OptionalPermissionControls';
import SectionHeader from '../SectionHeader';

const PAGE_SIZE = 12;

const iconButtonVars = (palette, tone) => {
  const ink = tone === 'delete' ? palette.severity.critical : palette.accent;
  return {
    '--raptor-users-fill': alpha(ink, 0.12),
    '--raptor-users-fill-hover': alpha(ink, 0.2),
    '--raptor-users-fill-press': alpha(ink, 0.28),
    '--raptor-users-icon': ink,
    '--raptor-users-icon-hover': ink,
    '--raptor-users-icon-press': ink,
    '--raptor-users-line': alpha(ink, 0.35),
    '--raptor-users-line-hover': ink,
    '--raptor-users-line-press': ink,
    '--raptor-users-accent': palette.accent
  };
};

const IconAction = ({ tone, label, disabled, onClick, children }) => {
  const palette = usePalette();
  return (
    <button
      type="button"
      className={`raptor-users-icon-btn raptor-users-icon-btn--${tone}`}
      style={iconButtonVars(palette, tone)}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
};

const UserCard = ({ user, roleKey, permissionCount, onEdit, onDelete }) => {
  const roleMeta = getRoleMeta(roleKey);
  const name = user.full_name || user.username;
  const handle = user.full_name ? user.username : user.email || user.username;
  const editLabel = `Edit ${name}`;
  const deleteLabel = `Delete ${name}`;

  return (
    <Surface className="raptor-users-card">
      <div className="raptor-users-card-row">
        <Text as="div" variant="bodyStrong" className="raptor-users-card-name" title={name}>
          {name}
        </Text>
        <div className="raptor-users-card-actions">
          <IconAction
            tone="edit"
            label={editLabel}
            disabled={Boolean(user.is_service_account)}
            onClick={() => onEdit(user)}
          >
            <EditOutlined sx={{ fontSize: 16 }} />
          </IconAction>
          <IconAction tone="delete" label={deleteLabel} onClick={() => onDelete(user)}>
            <DeleteOutline sx={{ fontSize: 16 }} />
          </IconAction>
        </div>
      </div>
      <div className="raptor-users-card-row">
        <Mono tone="secondary" className="raptor-users-card-handle" title={handle}>
          {handle}
        </Mono>
        <div className="raptor-users-card-meta">
          {user.is_service_account ? <Tag>Service</Tag> : <Tag>{roleMeta.label}</Tag>}
          <Tag>{permissionCount} opt</Tag>
          <AuthTypeChip authType={user.auth_type} />
        </div>
      </div>
    </Surface>
  );
};

const ExistingUsersPanel = ({
  existingUsers,
  editedUserRoles,
  editedUserPermissions,
  onRoleChange,
  onSavePermissions,
  onDeleteUser
}) => {
  const [editingUser, setEditingUser] = useState(null);
  const [dialogRole, setDialogRole] = useState('user');
  const [dialogPermissions, setDialogPermissions] = useState([]);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);

  const selectedUser = useMemo(
    () => existingUsers.find((user) => user.username === editingUser) || null,
    [editingUser, existingUsers]
  );

  const filteredUsers = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return existingUsers;
    return existingUsers.filter((user) => {
      const roleKey = editedUserRoles[user.username] || user.role || '';
      const haystack = [user.full_name, user.username, user.email, user.auth_type, roleKey]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [editedUserRoles, existingUsers, query]);

  const pageCount = Math.max(1, Math.ceil(filteredUsers.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pagedUsers = filteredUsers.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const openAccessDialog = (user) => {
    if (user.is_service_account) return;
    const roleKey = editedUserRoles[user.username] || user.role;
    const permissions = normalizeOptionalPermissions(
      roleKey,
      editedUserPermissions[user.username] ?? user.permissions ?? []
    );
    setEditingUser(user.username);
    setDialogRole(roleKey);
    setDialogPermissions(permissions);
  };

  const closeAccessDialog = () => {
    setEditingUser(null);
    setDialogRole('user');
    setDialogPermissions([]);
  };

  const handleDialogRoleChange = (nextRole) => {
    if (!nextRole) return;
    setDialogRole(nextRole);
    setDialogPermissions((prev) => normalizeOptionalPermissions(nextRole, prev));
  };

  const handleDialogPermissionToggle = (permission) => {
    const current = normalizeOptionalPermissions(dialogRole, dialogPermissions);
    const next = current.includes(permission)
      ? current.filter((perm) => perm !== permission)
      : [...current, permission];
    setDialogPermissions(next);
  };

  const saveAccessChanges = async () => {
    if (!selectedUser) return;
    const nextRole = dialogRole;
    const nextPermissions = normalizeOptionalPermissions(dialogRole, dialogPermissions);
    const previousRole = editedUserRoles[selectedUser.username] || selectedUser.role;
    if (nextRole !== previousRole) {
      await onRoleChange(selectedUser.username, nextRole);
    }
    await onSavePermissions(selectedUser.username, nextRole, nextPermissions);
    closeAccessDialog();
  };

  return (
    <>
      <SectionHeader title="Existing Users">
        <Tag>{`${filteredUsers.length} users`}</Tag>
      </SectionHeader>

      <div style={{ maxWidth: 320, marginBottom: SPACE.x16 }}>
        <Field
          label="Search"
          placeholder="Name, username, role"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(1);
          }}
        />
      </div>

      {existingUsers.length === 0 ? (
        <EmptyState icon={PeopleIcon} title="No users found" hint="Add users to get started" />
      ) : filteredUsers.length === 0 ? (
        <EmptyState title="No matches" hint="Try a different name, username, or role." />
      ) : (
        <div className="raptor-users-cards">
          {pagedUsers.map((user) => {
            const roleKey = editedUserRoles[user.username] || user.role;
            const permissions = normalizeOptionalPermissions(
              roleKey,
              editedUserPermissions[user.username] ?? user.permissions ?? []
            );
            return (
              <UserCard
                key={user.username}
                user={user}
                roleKey={roleKey}
                permissionCount={permissions.length}
                onEdit={openAccessDialog}
                onDelete={setPendingDelete}
              />
            );
          })}
        </div>
      )}

      {filteredUsers.length > PAGE_SIZE ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8, marginTop: SPACE.x16 }}>
          <Button size="small" variant="outlined" disabled={safePage <= 1} onClick={() => setPage((value) => value - 1)}>
            Previous
          </Button>
          <Mono>
            {safePage} / {pageCount}
          </Mono>
          <Button
            size="small"
            variant="outlined"
            disabled={safePage >= pageCount}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}

      <Panel
        open={Boolean(selectedUser)}
        onClose={closeAccessDialog}
        title={selectedUser ? `Edit access: ${selectedUser.full_name || selectedUser.username}` : 'Edit access'}
        actions={
          <>
            <Button onClick={closeAccessDialog} variant="outlined">
              Cancel
            </Button>
            <Button variant="contained" onClick={saveAccessChanges}>
              Save
            </Button>
          </>
        }
      >
        <Combo
          label="Role"
          options={ROLE_OPTIONS}
          value={dialogRole}
          onChange={handleDialogRoleChange}
          disableClearable
        />
        <OptionalPermissionControls
          roleKey={dialogRole}
          permissions={normalizeOptionalPermissions(dialogRole, dialogPermissions)}
          onToggle={handleDialogPermissionToggle}
          compact
        />
      </Panel>

      <Panel
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title="Delete user"
        actions={
          <>
            <Button onClick={() => setPendingDelete(null)} variant="outlined">
              Cancel
            </Button>
            <Button
              variant="contained"
              color="error"
              onClick={() => {
                if (!pendingDelete) return;
                onDeleteUser(pendingDelete.username);
                setPendingDelete(null);
              }}
            >
              Delete
            </Button>
          </>
        }
      >
        <Text variant="body">
          Delete {pendingDelete?.full_name || pendingDelete?.username}? This cannot be undone.
        </Text>
      </Panel>
    </>
  );
};

export default ExistingUsersPanel;
