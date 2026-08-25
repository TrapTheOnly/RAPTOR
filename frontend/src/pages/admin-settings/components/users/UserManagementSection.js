import React from 'react';
import { Tabs } from '../../../../design/primitives';
import { USER_SUBSECTIONS } from '../../constants';

const UserManagementSection = ({
  userManagementPage,
  onSelectUserManagementPage,
  existingPanel,
  domainPanel,
  localPanel,
  serviceAccountsPanel,
  ssoPanel
}) => (
  <>
    <style>{`
      .raptor-users-split {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        gap: 24px;
        align-items: stretch;
      }
      .raptor-users-pane {
        height: 100%;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        min-height: 0;
      }
      .raptor-users-pane-foot {
        margin-top: auto;
        padding-top: 16px;
      }
      .raptor-users-pane-fill {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: column;
      }
      .raptor-users-cards {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
      }
      .raptor-users-card {
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 0;
      }
      .raptor-users-card-row {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }
      .raptor-users-card-name,
      .raptor-users-card-handle {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-width: 0;
      }
      .raptor-users-card-name { flex: 1; }
      .raptor-users-card-handle { flex-shrink: 0; max-width: 40%; }
      .raptor-users-card-meta {
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
        overflow: hidden;
      }
      .raptor-users-card-actions {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
        margin-left: auto;
      }
      .raptor-users-icon-btn {
        appearance: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
        width: 28px;
        height: 28px;
        padding: 0;
        line-height: 0;
        border-radius: 4px;
        border: 1px solid var(--raptor-users-line);
        cursor: pointer;
        color: var(--raptor-users-icon);
        background: var(--raptor-users-fill);
        transition: background-color 90ms cubic-bezier(0, 0, 0.58, 1),
          color 90ms cubic-bezier(0, 0, 0.58, 1),
          border-color 90ms cubic-bezier(0, 0, 0.58, 1);
      }
      .raptor-users-icon-btn:hover:not(:disabled) {
        background: var(--raptor-users-fill-hover);
        color: var(--raptor-users-icon-hover);
        border-color: var(--raptor-users-line-hover);
      }
      .raptor-users-icon-btn:active:not(:disabled) {
        background: var(--raptor-users-fill-press);
        color: var(--raptor-users-icon-press);
        border-color: var(--raptor-users-line-press);
      }
      .raptor-users-icon-btn:focus-visible {
        outline: 1px solid var(--raptor-users-accent);
        outline-offset: 1px;
      }
      .raptor-users-icon-btn:disabled {
        opacity: 0.38;
        cursor: default;
      }
      @media (max-width: 1100px) {
        .raptor-users-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 960px) {
        .raptor-users-split { grid-template-columns: 1fr; }
      }
      @media (max-width: 720px) {
        .raptor-users-cards { grid-template-columns: 1fr; }
      }
    `}</style>
    <Tabs
      value={userManagementPage}
      onChange={onSelectUserManagementPage}
      items={USER_SUBSECTIONS.map((sub) => ({ value: sub.key, label: sub.tabLabel }))}
    />
    {userManagementPage === 'existing' && existingPanel}
    {userManagementPage === 'add-domain' && domainPanel}
    {userManagementPage === 'local' && localPanel}
    {userManagementPage === 'service-accounts' && serviceAccountsPanel}
    {userManagementPage === 'sso' && ssoPanel}
  </>
);

export default UserManagementSection;
