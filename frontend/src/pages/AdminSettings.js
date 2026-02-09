import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Box,
  Collapse,
  IconButton,
  LinearProgress,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import {
  BugReport as BugReportIcon,
  Build as BuildIcon,
  FactCheck as FactCheckIcon,
  Menu as MenuIcon,
  People as PeopleIcon,
  Security as SecurityIcon,
  Storage as StorageIcon
} from '@mui/icons-material';
import {
  COMMON_PASSWORDS,
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH
} from './admin-settings/constants';
import {
  buildResetCsv,
  buildResetSummary,
  normalizeOptionalPermissions
} from './admin-settings/utils';
import AdminSettingsNavDrawer from './admin-settings/components/AdminSettingsNavDrawer';
import IpSourcesSection from './admin-settings/components/IpSourcesSection';
import MaintenanceSection from './admin-settings/components/MaintenanceSection';
import ResetPentestDialog from './admin-settings/components/ResetPentestDialog';
import SecuritySection from './admin-settings/components/SecuritySection';
import ChecklistTemplatesSection from './admin-settings/components/ChecklistTemplatesSection';
import VulnCategoriesSection from './admin-settings/components/VulnCategoriesSection';
import DomainUsersPanel from './admin-settings/components/users/DomainUsersPanel';
import ExistingUsersPanel from './admin-settings/components/users/ExistingUsersPanel';
import LocalUsersPanel from './admin-settings/components/users/LocalUsersPanel';
import UserManagementSection from './admin-settings/components/users/UserManagementSection';

const REQUIRED_RESET_PHRASE = 'RESET ALL BUT OPEN VULNERABILITIES';
const EMPTY_CHECKLIST_TEMPLATE_FORM = {
  key: '',
  name: '',
  service: '',
  source: '',
  autoPortsText: '',
  sectionsJson: '[]',
  enabled: true
};

const AdminSettings = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [selectedUserRoles, setSelectedUserRoles] = useState({});
  const [selectedUserPermissions, setSelectedUserPermissions] = useState({});
  const [existingUsers, setExistingUsers] = useState([]);
  const [editedUserRoles, setEditedUserRoles] = useState({});
  const [editedUserPermissions, setEditedUserPermissions] = useState({});
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  const [loading, setLoading] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [retypePassword, setRetypePassword] = useState('');

  const [sourceTypes, setSourceTypes] = useState([]);
  const [ipsBySource, setIpsBySource] = useState({});
  const [selectedSource, setSelectedSource] = useState('');
  const [newSourceName, setNewSourceName] = useState('');
  const [newIpAddress, setNewIpAddress] = useState('');
  const [ipsToAdd, setIpsToAdd] = useState([]);
  const [ipsToDelete, setIpsToDelete] = useState([]);

  const [localUsername, setLocalUsername] = useState('');
  const [localRole, setLocalRole] = useState('user');
  const [localTempPassword, setLocalTempPassword] = useState('');
  const [localPermissions, setLocalPermissions] = useState([]);

  const [vulnCategories, setVulnCategories] = useState([]);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [checklistTemplates, setChecklistTemplates] = useState([]);
  const [selectedChecklistTemplateId, setSelectedChecklistTemplateId] = useState(null);
  const [checklistTemplateForm, setChecklistTemplateForm] = useState(
    EMPTY_CHECKLIST_TEMPLATE_FORM
  );

  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetPhrase, setResetPhrase] = useState('');
  const [resetConfirmChecked, setResetConfirmChecked] = useState(false);
  const [resetStats, setResetStats] = useState(null);
  const [resetSummary, setResetSummary] = useState(null);
  const [resetCsv, setResetCsv] = useState('');

  const [selectedSection, setSelectedSection] = useState('users');
  const [userManagementPage, setUserManagementPage] = useState('existing');
  const [navOpen, setNavOpen] = useState(false);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const sections = useMemo(
    () => [
      {
        key: 'users',
        label: 'User Management',
        description: 'Manage existing users, roles, and access types.',
        icon: PeopleIcon
      },
      {
        key: 'security',
        label: 'Security',
        description: 'Update the admin password and security settings.',
        icon: SecurityIcon
      },
      {
        key: 'ip-sources',
        label: 'IP Sources',
        description: 'Map IP addresses to source groups used in asset tracking.',
        icon: StorageIcon
      },
      {
        key: 'vuln-categories',
        label: 'Vulnerability Categories',
        description: 'Manage the vulnerability taxonomy used in pentest reports.',
        icon: BugReportIcon
      },
      {
        key: 'checklist-templates',
        label: 'Checklist Templates',
        description: 'Manage service checklists used by pentest records.',
        icon: FactCheckIcon
      },
      {
        key: 'maintenance',
        label: 'Maintenance',
        description: 'Run manual updates and manage pentest resets.',
        icon: BuildIcon
      }
    ],
    []
  );

  const activeSection =
    sections.find((section) => section.key === selectedSection) || sections[0];
  const selectedChecklistTemplate = useMemo(
    () =>
      checklistTemplates.find(
        (template) => template.id === selectedChecklistTemplateId
      ) || null,
    [checklistTemplates, selectedChecklistTemplateId]
  );

  const showMessage = useCallback((type, text) => {
    setMessageType(type);
    setMessage(text);
  }, []);

  const validatePassword = (value) => {
    if (!value) return 'New password is required.';
    if (value.length < MIN_PASSWORD_LENGTH) {
      return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (value.length > MAX_PASSWORD_LENGTH) {
      return `Password must be at most ${MAX_PASSWORD_LENGTH} characters.`;
    }
    if (COMMON_PASSWORDS.has(value.trim().toLowerCase())) {
      return 'Password is too common.';
    }
    return '';
  };

  const fetchIpSources = useCallback(async () => {
    try {
      const response = await axios.get('/ip-sources');
      if (response.status === 200 && response.data.ip_sources) {
        const map = {};
        response.data.ip_sources.forEach((item) => {
          map[item.source_name] = map[item.source_name] || [];
          map[item.source_name].push(item.ip_address);
        });
        setSourceTypes(
          Array.from(new Set(response.data.ip_sources.map((item) => item.source_name)))
        );
        setIpsBySource(map);
      }
    } catch (error) {
      showMessage('error', 'Failed to fetch IP sources.');
      console.error(error);
    }
  }, [showMessage]);

  const fetchExistingUsers = useCallback(async () => {
    try {
      const response = await axios.get('/existing-users');
      if (response.status === 200) setExistingUsers(response.data.users);
    } catch (error) {
      showMessage('error', 'Failed to fetch existing users.');
    }
  }, [showMessage]);

  const fetchVulnCategories = useCallback(async () => {
    try {
      const response = await axios.get('/vuln-categories');
      if (response.status === 200) {
        setVulnCategories(response.data.categories || []);
      }
    } catch (error) {
      showMessage('error', 'Failed to fetch vulnerability categories.');
    }
  }, [showMessage]);

  const fetchChecklistTemplates = useCallback(async () => {
    try {
      const response = await axios.get('/checklist-templates?include_disabled=true');
      if (response.status === 200) {
        const templates = response.data.templates || [];
        setChecklistTemplates(templates);
        return templates;
      }
    } catch (error) {
      showMessage('error', 'Failed to fetch checklist templates.');
    }
    return [];
  }, [showMessage]);

  useEffect(() => {
    fetchIpSources();
    fetchExistingUsers();
    fetchVulnCategories();
    fetchChecklistTemplates();
  }, [
    fetchChecklistTemplates,
    fetchExistingUsers,
    fetchIpSources,
    fetchVulnCategories
  ]);

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(''), 5000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [message]);

  const handleAddSourceType = () => {
    const trimmedName = newSourceName.trim();
    if (!trimmedName || sourceTypes.includes(trimmedName)) {
      showMessage(
        'error',
        sourceTypes.includes(trimmedName)
          ? 'This source type already exists.'
          : 'Invalid source name.'
      );
      return;
    }
    setSourceTypes((prev) => [...prev, trimmedName]);
    setIpsBySource((prev) => ({ ...prev, [trimmedName]: [] }));
    setSelectedSource(trimmedName);
    setNewSourceName('');
  };

  const handleSelectSourceType = (sourceName) => {
    setSelectedSource(sourceName);
    setIpsToAdd([]);
    setIpsToDelete([]);
    setNewIpAddress('');
  };

  const handleAddIp = () => {
    const trimmedIp = newIpAddress.trim();
    if (!trimmedIp || !selectedSource) return;
    const currentIps = ipsBySource[selectedSource] || [];
    if (currentIps.includes(trimmedIp)) {
      showMessage('error', 'IP already exists in this source.');
      return;
    }
    setIpsBySource((prev) => ({
      ...prev,
      [selectedSource]: [...currentIps, trimmedIp]
    }));
    setIpsToAdd((prev) => [...prev, trimmedIp]);
    setNewIpAddress('');
  };

  const handleDeleteIpClick = (ip) => {
    setIpsToDelete((prev) => (prev.includes(ip) ? prev : [...prev, ip]));
    setIpsBySource((prev) => ({
      ...prev,
      [selectedSource]: (prev[selectedSource] || []).filter((currentIp) => currentIp !== ip)
    }));
  };

  const handleSubmitChanges = async () => {
    if (!selectedSource) return;
    setLoading(true);
    try {
      await Promise.all([
        ...ipsToAdd.map((ip) =>
          axios.post('/ip-sources', { source_name: selectedSource, ip_address: ip })
        ),
        ...ipsToDelete.map((ip) =>
          axios.delete('/ip-sources', { data: { ip_address: ip } })
        )
      ]);
      showMessage('success', 'Changes submitted successfully.');
      setIpsToAdd([]);
      setIpsToDelete([]);
      fetchIpSources();
    } catch (error) {
      console.error('Failed to submit changes', error);
      showMessage('error', 'Failed to submit changes.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectUser = (user) => {
    if (!selectedUsers.some((selected) => selected.username === user.username)) {
      setSelectedUsers((prev) => [...prev, user]);
      setSearchResults((prev) =>
        prev.filter((result) => result.username !== user.username)
      );
      setSelectedUserRoles((prev) => ({ ...prev, [user.username]: 'user' }));
      setSelectedUserPermissions((prev) => ({ ...prev, [user.username]: [] }));
    }
  };

  const handleRemoveUser = (user) => {
    setSearchResults((prev) => [...prev, user]);
    setSelectedUsers((prev) =>
      prev.filter((selected) => selected.username !== user.username)
    );
    setSelectedUserRoles((prev) => {
      const { [user.username]: removedRole, ...restRoles } = prev;
      return restRoles;
    });
    setSelectedUserPermissions((prev) => {
      const { [user.username]: removedPerms, ...restPerms } = prev;
      return restPerms;
    });
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const usersWithRoles = selectedUsers.map((user) => ({
        username: user.username,
        email: user.email,
        role: selectedUserRoles[user.username] || 'user',
        permissions: normalizeOptionalPermissions(
          selectedUserRoles[user.username] || 'user',
          selectedUserPermissions[user.username] || []
        )
      }));
      const responses = await Promise.all(
        usersWithRoles.map((user) => axios.post('/add-user', user))
      );
      if (responses.every((response) => response.status === 200)) {
        showMessage('success', 'Users added successfully.');
        setSelectedUsers([]);
        setSelectedUserRoles({});
        setSelectedUserPermissions({});
        fetchExistingUsers();
      }
    } catch (error) {
      showMessage('error', 'Failed to add users. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveRole = async (username, newRole) => {
    try {
      const response = await axios.post('/update-user-role', {
        username,
        role: newRole
      });
      if (response.status === 200) {
        setExistingUsers((prevUsers) =>
          prevUsers.map((user) =>
            user.username === username ? { ...user, role: newRole } : user
          )
        );
        setEditedUserPermissions((prev) => ({ ...prev, [username]: [] }));
        showMessage('success', response.data.message);
      } else {
        showMessage('error', 'Failed to update role. Please try again.');
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to update user role. Please try again.'
      );
    }
  };

  const handleSavePermissions = async (username, role, permissions) => {
    const normalized = normalizeOptionalPermissions(role, permissions);
    try {
      const response = await axios.post('/update-user-permissions', {
        username,
        permissions: normalized
      });
      if (response.status === 200) {
        setExistingUsers((prevUsers) =>
          prevUsers.map((user) =>
            user.username === username ? { ...user, permissions: normalized } : user
          )
        );
        setEditedUserPermissions((prev) => ({ ...prev, [username]: normalized }));
        showMessage('success', response.data.message);
      } else {
        showMessage('error', 'Failed to update permissions. Please try again.');
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error ||
          'Failed to update permissions. Please try again.'
      );
    }
  };

  const handleDeleteUser = async (username) => {
    if (!window.confirm(`Are you sure you want to delete user ${username}?`)) return;
    try {
      const response = await axios.delete('/delete-user', { data: { username } });
      if (response.status === 200) {
        showMessage('success', `User ${username} deleted successfully.`);
        setExistingUsers((prev) =>
          prev.filter((user) => user.username !== username)
        );
      }
    } catch (error) {
      showMessage('error', `Failed to delete user ${username}.`);
    }
  };

  const handleSearch = async () => {
    setLoading(true);
    try {
      setSearchResults([]);
      const response = await axios.get(`/ldap-search?query=${searchQuery}`);
      if (response.status === 200) {
        setSearchResults(
          response.data.results.filter(
            (user) =>
              user.username !== 'None' &&
              user.email !== 'None' &&
              user.full_name !== 'None'
          )
        );
      } else {
        showMessage('error', 'No results found.');
      }
    } catch (error) {
      showMessage('error', 'Error searching LDAP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleManualParse = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/manual-update');
      if (response.status === 200) {
        showMessage('success', 'Records updated successfully.');
      }
    } catch (error) {
      showMessage('error', 'Failed to parse records. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleAddVulnCategory = async () => {
    const name = newCategoryName.trim();
    if (!name) {
      showMessage('error', 'Category name is required.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/vuln-categories', { name });
      if (response.status === 200) {
        showMessage('success', 'Category added successfully.');
        setNewCategoryName('');
        fetchVulnCategories();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to add category.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteVulnCategory = async (categoryId) => {
    if (!window.confirm('Delete this category?')) return;
    setLoading(true);
    try {
      const response = await axios.delete(`/vuln-categories/${categoryId}`);
      if (response.status === 200) {
        showMessage('success', 'Category deleted successfully.');
        fetchVulnCategories();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to delete category.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNewChecklistTemplate = () => {
    setSelectedChecklistTemplateId(null);
    setChecklistTemplateForm({ ...EMPTY_CHECKLIST_TEMPLATE_FORM });
  };

  const handleSelectChecklistTemplate = (template) => {
    setSelectedChecklistTemplateId(template.id);
    setChecklistTemplateForm({
      key: template.key || '',
      name: template.name || '',
      service: template.service || '',
      source: template.source || '',
      autoPortsText: (template.auto_ports || []).join(', '),
      sectionsJson: JSON.stringify(template.sections || [], null, 2),
      enabled: Boolean(template.enabled)
    });
  };

  const handleChecklistTemplateFormChange = (field, value) => {
    setChecklistTemplateForm((prev) => ({ ...prev, [field]: value }));
  };

  const parseAutoPorts = (rawPortsText) => {
    const seen = new Set();
    return rawPortsText
      .split(',')
      .map((value) => Number.parseInt(value.trim(), 10))
      .filter((value) => Number.isInteger(value) && value >= 1 && value <= 65535)
      .filter((value) => {
        if (seen.has(value)) return false;
        seen.add(value);
        return true;
      });
  };

  const handleSaveChecklistTemplate = async () => {
    const key = selectedChecklistTemplate?.is_system
      ? (selectedChecklistTemplate.key || '').trim().toLowerCase()
      : checklistTemplateForm.key.trim().toLowerCase();
    const name = checklistTemplateForm.name.trim();
    const service = checklistTemplateForm.service.trim().toLowerCase();
    if (!key || !name || !service) {
      showMessage('error', 'Template key, name, and service are required.');
      return;
    }

    let sections = [];
    try {
      const parsed = JSON.parse(checklistTemplateForm.sectionsJson || '[]');
      if (!Array.isArray(parsed)) {
        showMessage('error', 'Sections JSON must be an array.');
        return;
      }
      sections = parsed;
    } catch (error) {
      showMessage('error', 'Sections JSON is invalid.');
      return;
    }

    const payload = {
      key,
      name,
      service,
      source: checklistTemplateForm.source.trim(),
      auto_ports: parseAutoPorts(checklistTemplateForm.autoPortsText || ''),
      sections,
      enabled: Boolean(checklistTemplateForm.enabled)
    };

    setLoading(true);
    try {
      if (selectedChecklistTemplateId) {
        const response = await axios.put(
          `/checklist-templates/${selectedChecklistTemplateId}`,
          payload
        );
        if (response.status === 200) {
          showMessage('success', 'Checklist template updated.');
        }
      } else {
        const response = await axios.post('/checklist-templates', payload);
        if (response.status === 200) {
          showMessage('success', 'Checklist template created.');
          setSelectedChecklistTemplateId(response.data.id || null);
        }
      }
      const refreshedTemplates = await fetchChecklistTemplates();
      const refreshedSelectionId = selectedChecklistTemplateId || payload.key;
      const refreshedTemplate = refreshedTemplates.find(
        (template) =>
          template.id === refreshedSelectionId || template.key === refreshedSelectionId
      );
      if (refreshedTemplate) {
        handleSelectChecklistTemplate(refreshedTemplate);
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to save checklist template.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteChecklistTemplate = async (templateId, templateName) => {
    const template = checklistTemplates.find((item) => item.id === templateId);
    if (template?.is_system) {
      showMessage(
        'error',
        'System templates cannot be deleted. Disable or reset them instead.'
      );
      return;
    }
    if (!window.confirm(`Delete checklist template "${templateName}"?`)) return;
    setLoading(true);
    try {
      const response = await axios.delete(`/checklist-templates/${templateId}`);
      if (response.status === 200) {
        showMessage('success', 'Checklist template deleted.');
        if (selectedChecklistTemplateId === templateId) {
          handleCreateNewChecklistTemplate();
        }
        fetchChecklistTemplates();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to delete checklist template.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleResetChecklistTemplate = async (template) => {
    if (!template?.id || !template?.is_system) {
      showMessage('error', 'Only system templates can be reset to canonical.');
      return;
    }
    if (
      !window.confirm(
        `Reset "${template.name}" to canonical defaults? This clears admin edits for this template.`
      )
    ) {
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`/checklist-templates/${template.id}/reset`);
      if (response.status === 200) {
        showMessage('success', 'Checklist template reset to canonical.');
      }
      const refreshedTemplates = await fetchChecklistTemplates();
      const refreshedTemplate = refreshedTemplates.find(
        (item) => item.id === template.id
      );
      if (refreshedTemplate) {
        handleSelectChecklistTemplate(refreshedTemplate);
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to reset checklist template.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async () => {
    const validationError = validatePassword(newPassword);
    if (validationError) {
      showMessage('error', validationError);
      return;
    }
    if (newPassword !== retypePassword) {
      showMessage('error', 'New password and retyped password do not match.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/change-password', {
        current_password: currentPassword,
        new_password: newPassword
      });
      if (response.status === 200) {
        showMessage('success', 'Password changed successfully.');
        setCurrentPassword('');
        setNewPassword('');
        setRetypePassword('');
      }
    } catch (error) {
      showMessage(
        'error',
        'Failed to change password. Please check your current password.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCreateLocalUser = async () => {
    const trimmedUsername = localUsername.trim().toLowerCase();
    if (!trimmedUsername) {
      showMessage('error', 'Local username is required.');
      return;
    }
    if (!['user', 'pentester', 'manager'].includes(localRole)) {
      showMessage('error', 'Invalid role specified.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/add-local-user', {
        username: trimmedUsername,
        role: localRole,
        permissions: normalizeOptionalPermissions(localRole, localPermissions)
      });
      if (response.status === 200) {
        showMessage('success', 'Local user created. Temporary password generated.');
        setLocalTempPassword(response.data.temp_password || '');
        setLocalUsername('');
        setLocalRole('user');
        setLocalPermissions([]);
        fetchExistingUsers();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to create local user.'
      );
    } finally {
      setLoading(false);
    }
  };

  const fetchResetSummary = useCallback(async () => {
    try {
      const response = await axios.get('/pentest/records');
      if (response.status === 200) {
        const data = response.data || [];
        setResetSummary(buildResetSummary(data));
        setResetCsv(buildResetCsv(data));
      }
    } catch (error) {
      showMessage('error', 'Failed to load pentest summary.');
    }
  }, [showMessage]);

  const handleOpenResetDialog = () => {
    setResetDialogOpen(true);
    setResetPhrase('');
    setResetConfirmChecked(false);
    fetchResetSummary();
  };

  const handleCloseResetDialog = () => {
    setResetDialogOpen(false);
  };

  const downloadResetCsv = () => {
    if (!resetCsv) return;
    const blob = new Blob([resetCsv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'pentest_yearly_summary.csv');
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleResetOpenVulnerabilities = async () => {
    if (!resetConfirmChecked || resetPhrase !== REQUIRED_RESET_PHRASE) {
      showMessage('error', 'Please confirm the reset phrase to proceed.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/pentest/reset-keep-open', {
        confirm: true,
        phrase: resetPhrase
      });
      if (response.status === 200) {
        setResetStats(response.data.stats || null);
        showMessage(
          'success',
          'Pentest progress reset successfully (open vulnerabilities preserved).'
        );
        handleCloseResetDialog();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to reset pentest progress.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleEditedRoleChange = async (username, newRole) => {
    setEditedUserRoles((prev) => ({ ...prev, [username]: newRole }));
    setEditedUserPermissions((prev) => ({
      ...prev,
      [username]: normalizeOptionalPermissions(newRole, prev[username] || [])
    }));
    await handleSaveRole(username, newRole);
  };

  const handleSelectedRoleChange = (username, newRole) => {
    setSelectedUserRoles((prev) => ({ ...prev, [username]: newRole }));
    setSelectedUserPermissions((prev) => ({
      ...prev,
      [username]: normalizeOptionalPermissions(newRole, prev[username] || [])
    }));
  };

  const handleSelectedPermissionToggle = (username, permission) => {
    const roleKey = selectedUserRoles[username] || 'user';
    const current = normalizeOptionalPermissions(
      roleKey,
      selectedUserPermissions[username] || []
    );
    const next = current.includes(permission)
      ? current.filter((perm) => perm !== permission)
      : [...current, permission];
    setSelectedUserPermissions((prev) => ({ ...prev, [username]: next }));
  };

  const handleLocalRoleChange = (nextRole) => {
    setLocalRole(nextRole);
    setLocalPermissions((prev) => normalizeOptionalPermissions(nextRole, prev));
  };

  const handleLocalPermissionToggle = (permission) => {
    const current = normalizeOptionalPermissions(localRole, localPermissions);
    const next = current.includes(permission)
      ? current.filter((perm) => perm !== permission)
      : [...current, permission];
    setLocalPermissions(next);
  };

  const handleSelectSection = (sectionKey) => {
    setSelectedSection(sectionKey);
    if (isMobile) setNavOpen(false);
  };

  const renderSection = () => {
    switch (selectedSection) {
      case 'users':
        return (
          <UserManagementSection
            userManagementPage={userManagementPage}
            existingPanel={
              <ExistingUsersPanel
                existingUsers={existingUsers}
                editedUserRoles={editedUserRoles}
                editedUserPermissions={editedUserPermissions}
                onRoleChange={handleEditedRoleChange}
                onSavePermissions={handleSavePermissions}
                onDeleteUser={handleDeleteUser}
              />
            }
            domainPanel={
              <DomainUsersPanel
                loading={loading}
                searchQuery={searchQuery}
                setSearchQuery={setSearchQuery}
                searchResults={searchResults}
                existingUsers={existingUsers}
                selectedUsers={selectedUsers}
                selectedUserRoles={selectedUserRoles}
                selectedUserPermissions={selectedUserPermissions}
                onSearch={handleSearch}
                onSelectUser={handleSelectUser}
                onRemoveUser={handleRemoveUser}
                onSelectedRoleChange={handleSelectedRoleChange}
                onSelectedPermissionToggle={handleSelectedPermissionToggle}
                onSubmit={handleSubmit}
              />
            }
            localPanel={
              <LocalUsersPanel
                loading={loading}
                localUsername={localUsername}
                setLocalUsername={setLocalUsername}
                localRole={localRole}
                localPermissions={localPermissions}
                localTempPassword={localTempPassword}
                onRoleChange={handleLocalRoleChange}
                onTogglePermission={handleLocalPermissionToggle}
                onCreateLocalUser={handleCreateLocalUser}
              />
            }
          />
        );
      case 'security':
        return (
          <SecuritySection
            loading={loading}
            currentPassword={currentPassword}
            setCurrentPassword={setCurrentPassword}
            newPassword={newPassword}
            setNewPassword={setNewPassword}
            retypePassword={retypePassword}
            setRetypePassword={setRetypePassword}
            onChangePassword={handleChangePassword}
          />
        );
      case 'ip-sources':
        return (
          <IpSourcesSection
            loading={loading}
            sourceTypes={sourceTypes}
            ipsBySource={ipsBySource}
            selectedSource={selectedSource}
            newSourceName={newSourceName}
            setNewSourceName={setNewSourceName}
            newIpAddress={newIpAddress}
            setNewIpAddress={setNewIpAddress}
            onAddSourceType={handleAddSourceType}
            onSelectSourceType={handleSelectSourceType}
            onAddIp={handleAddIp}
            onDeleteIp={handleDeleteIpClick}
            onSubmitChanges={handleSubmitChanges}
          />
        );
      case 'vuln-categories':
        return (
          <VulnCategoriesSection
            loading={loading}
            vulnCategories={vulnCategories}
            newCategoryName={newCategoryName}
            setNewCategoryName={setNewCategoryName}
            onAddVulnCategory={handleAddVulnCategory}
            onDeleteVulnCategory={handleDeleteVulnCategory}
          />
        );
      case 'checklist-templates':
        return (
          <ChecklistTemplatesSection
            loading={loading}
            templates={checklistTemplates}
            selectedTemplateId={selectedChecklistTemplateId}
            selectedTemplate={selectedChecklistTemplate}
            templateForm={checklistTemplateForm}
            onCreateNewTemplate={handleCreateNewChecklistTemplate}
            onSelectTemplate={handleSelectChecklistTemplate}
            onChangeTemplateForm={handleChecklistTemplateFormChange}
            onSaveTemplate={handleSaveChecklistTemplate}
            onDeleteTemplate={handleDeleteChecklistTemplate}
            onResetTemplate={handleResetChecklistTemplate}
          />
        );
      case 'maintenance':
        return (
          <MaintenanceSection
            loading={loading}
            resetCsv={resetCsv}
            resetStats={resetStats}
            onManualParse={handleManualParse}
            onDownloadResetCsv={downloadResetCsv}
            onOpenResetDialog={handleOpenResetDialog}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: 'background.default' }}>
      <AdminSettingsNavDrawer
        isMobile={isMobile}
        navOpen={navOpen}
        onClose={() => setNavOpen(false)}
        sections={sections}
        selectedSection={selectedSection}
        onSelectSection={handleSelectSection}
        userManagementPage={userManagementPage}
        onSelectUserManagementPage={setUserManagementPage}
      />

      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Box display="flex" alignItems="center" gap={2} mb={3}>
          {isMobile && (
            <IconButton onClick={() => setNavOpen(true)}>
              <MenuIcon />
            </IconButton>
          )}
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {activeSection.label}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {activeSection.description}
            </Typography>
          </Box>
        </Box>

        {loading && <LinearProgress sx={{ mb: 2 }} />}

        <Collapse in={Boolean(message)}>
          <Alert
            severity={messageType || 'info'}
            sx={{ mb: 2 }}
            onClose={() => setMessage('')}
          >
            {message}
          </Alert>
        </Collapse>

        {renderSection()}
      </Box>

      <ResetPentestDialog
        open={resetDialogOpen}
        loading={loading}
        onClose={handleCloseResetDialog}
        onConfirm={handleResetOpenVulnerabilities}
        requiredResetPhrase={REQUIRED_RESET_PHRASE}
        resetSummary={resetSummary}
        resetPhrase={resetPhrase}
        setResetPhrase={setResetPhrase}
        resetConfirmChecked={resetConfirmChecked}
        setResetConfirmChecked={setResetConfirmChecked}
      />
    </Box>
  );
};

export default AdminSettings;
