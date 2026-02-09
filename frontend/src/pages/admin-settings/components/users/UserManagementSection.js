import React from 'react';
import {
  Card,
  CardContent
} from '@mui/material';

const UserManagementSection = ({
  userManagementPage,
  existingPanel,
  domainPanel,
  localPanel
}) => (
  <Card>
    <CardContent>
      {userManagementPage === 'existing' && existingPanel}
      {userManagementPage === 'add-domain' && domainPanel}
      {userManagementPage === 'local' && localPanel}
    </CardContent>
  </Card>
);

export default UserManagementSection;
