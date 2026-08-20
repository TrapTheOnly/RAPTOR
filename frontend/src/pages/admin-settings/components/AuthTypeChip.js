import React from 'react';
import { Tag } from '../../../design/primitives';

const LABELS = {
  local: 'Local',
  ldap: 'LDAP',
  service: 'Service',
  oidc: 'OIDC',
  saml: 'SAML',
  federated: 'Directory'
};

const AuthTypeChip = ({ authType }) => {
  const normalized = String(authType || 'ldap').toLowerCase();
  return <Tag>{LABELS[normalized] || 'Directory'}</Tag>;
};

export default AuthTypeChip;
