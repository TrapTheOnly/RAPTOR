import React from 'react';
import {
  Card,
  CardContent
} from '@mui/material';

const UserManagementSection = ({
  userManagementPage,
  existingPanel,
  domainPanel,
  localPanel,
  serviceAccountsPanel
}) => (
  <Card>
    <CardContent>
      {userManagementPage === 'existing' && existingPanel}
      {userManagementPage === 'add-domain' && domainPanel}
      {userManagementPage === 'local' && localPanel}
      {userManagementPage === 'service-accounts' && serviceAccountsPanel}
    </CardContent>
  </Card>
);

export default UserManagementSection;
