import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useMediaQuery, useTheme } from '@mui/material';
import {
  Article as ArticleIcon,
  BugReport as BugReportIcon,
  Build as BuildIcon,
  Dns as DnsIcon,
  Email as EmailIcon,
  FactCheck as FactCheckIcon,
  Hub as HubIcon,
  People as PeopleIcon,
  Security as SecurityIcon,
  SmartToy as SmartToyIcon
} from '@mui/icons-material';
import {
  Button,
  EmptyState,
  Page,
  PageHeader,
  Progress,
  Toast
} from '../design/primitives';
import {
  COMMON_PASSWORDS,
  DOMAIN_SUBSECTIONS,
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH
} from './admin-settings/constants';
import {
  buildResetCsv,
  buildResetSummary,
  normalizeOptionalPermissions
} from './admin-settings/utils';
import {
  createEmptyReportTemplateForm,
  createReportTemplateFormFromApi,
  toReportTemplateDefinition
} from './admin-settings/report-template-utils';
import { hasPermission as hasRolePermission } from '../utils/permissions';
import SettingsNav from './admin-settings/components/SettingsNav';
import SettingsShell from './admin-settings/components/SettingsShell';
import IpSourcesSection from './admin-settings/components/IpSourcesSection';
import MaintenanceSection from './admin-settings/components/MaintenanceSection';
import ResetPentestDialog from './admin-settings/components/ResetPentestDialog';
import SecuritySection from './admin-settings/components/SecuritySection';
import ChecklistTemplatesSection from './admin-settings/components/ChecklistTemplatesSection';
import CollectorsSection from './admin-settings/components/CollectorsSection';
import CloudDnsSection from './admin-settings/components/CloudDnsSection';
import DomainsManagementSection from './admin-settings/components/DomainsManagementSection';
import DomainsRefreshCard from './admin-settings/components/DomainsRefreshCard';
import ReportTemplatesSection from './admin-settings/components/ReportTemplatesSection';
import VulnCategoriesSection from './admin-settings/components/VulnCategoriesSection';
import DomainUsersPanel from './admin-settings/components/users/DomainUsersPanel';
import ExistingUsersPanel from './admin-settings/components/users/ExistingUsersPanel';
import LocalUsersPanel from './admin-settings/components/users/LocalUsersPanel';
import ServiceAccountsPanel from './admin-settings/components/users/ServiceAccountsPanel';
import SsoConnectionsPanel from './admin-settings/components/users/SsoConnectionsPanel';
import UserManagementSection from './admin-settings/components/users/UserManagementSection';
import EmailSettingsPanel from './admin-settings/components/EmailSettingsPanel';
import AiScannerSection from './admin-settings/components/AiScannerSection';
import IntegrationsSection from './admin-settings/components/IntegrationsSection';

const REQUIRED_RESET_PHRASE = 'RESET NOTEBOOKS KEEP FINDINGS';
const EMPTY_CHECKLIST_TEMPLATE_FORM = {
  key: '',
  name: '',
  service: '',
  source: '',
  autoPortsText: '',
  sectionsJson: '[]',
  enabled: true
};

const AdminSettings = ({ userRole, userPermissions = [] }) => {
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
  const [localFullName, setLocalFullName] = useState('');
  const [localIsServiceAccount, setLocalIsServiceAccount] = useState(false);
  const [localRole, setLocalRole] = useState('user');
  const [localTempPassword, setLocalTempPassword] = useState('');
  const [localPermissions, setLocalPermissions] = useState([]);
  const [serviceAccounts, setServiceAccounts] = useState([]);
  const [selectedServiceAccountUsername, setSelectedServiceAccountUsername] = useState('');
  const [createServiceAccountUsername, setCreateServiceAccountUsername] = useState('');
  const [createServiceAccountScopes, setCreateServiceAccountScopes] = useState(['records.read']);
  const [createServiceAccountEndDate, setCreateServiceAccountEndDate] = useState('');
  const [selectedServiceAccountScopes, setSelectedServiceAccountScopes] = useState([]);
  const [selectedServiceAccountEndDate, setSelectedServiceAccountEndDate] = useState('');
  const [visibleServiceApiKey, setVisibleServiceApiKey] = useState('');

  const [vulnCategories, setVulnCategories] = useState([]);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [checklistTemplates, setChecklistTemplates] = useState([]);
  const [selectedChecklistTemplateId, setSelectedChecklistTemplateId] = useState(null);
  const [checklistTemplateForm, setChecklistTemplateForm] = useState(
    EMPTY_CHECKLIST_TEMPLATE_FORM
  );
  const [reportTemplates, setReportTemplates] = useState([]);
  const [selectedReportTemplateId, setSelectedReportTemplateId] = useState(null);
  const [reportTemplateForm, setReportTemplateForm] = useState(() =>
    createEmptyReportTemplateForm()
  );

  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetPhrase, setResetPhrase] = useState('');
  const [resetConfirmChecked, setResetConfirmChecked] = useState(false);
  const [resetStats, setResetStats] = useState(null);
  const [resetSummary, setResetSummary] = useState(null);
  const [resetCsv, setResetCsv] = useState('');

  const [selectedSection, setSelectedSection] = useState('');
  const [userManagementPage, setUserManagementPage] = useState('existing');
  const [domainManagementPage, setDomainManagementPage] = useState('collectors');
  const [aiScannerPage, setAiScannerPage] = useState('connections');
  const [navOpen, setNavOpen] = useState(false);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const hasPermission = useCallback(
    (permission) => hasRolePermission(userRole, userPermissions, permission),
    [userPermissions, userRole]
  );

  const canManageUsers = userRole === 'admin';
  const canManageSecurity = userRole === 'admin';
  const canManageChecklistTemplates = userRole === 'admin';
  const canRunMaintenance = userRole === 'admin';
  const canManageIpSources = hasPermission('manage_ip_sources');
  const canManageVulnCategories = hasPermission('manage_vuln_categories');
  const canManageReportTemplates = hasPermission('manage_report_templates');
  const canManageIntegrations = userRole === 'admin' || userRole === 'manager';

  const sections = useMemo(
    () => [
      {
        key: 'users',
        label: 'User Management',
        description: 'Manage existing users, roles, and access types.',
        icon: PeopleIcon,
        visible: canManageUsers
      },
      {
        key: 'security',
        label: 'Security',
        description: 'Update privileged account password and security settings.',
        icon: SecurityIcon,
        visible: canManageSecurity
      },
      {
        key: 'domains',
        label: 'Domains Management',
        description: 'Collectors, cloud DNS connectors, zone refresh, and IP source groups.',
        icon: DnsIcon,
        visible: canManageSecurity || canManageIpSources || canRunMaintenance
      },
      {
        key: 'vuln-categories',
        label: 'Vulnerability Categories',
        description: 'Manage the vulnerability taxonomy used in pentest reports.',
        icon: BugReportIcon,
        visible: canManageVulnCategories
      },
      {
        key: 'checklist-templates',
        label: 'Checklist Templates',
        description: 'Manage service checklists used by pentest records.',
        icon: FactCheckIcon,
        visible: canManageChecklistTemplates
      },
      {
        key: 'report-templates',
        label: 'Report Templates',
        description: 'Design and maintain PDF report templates used by pentest records.',
        icon: ArticleIcon,
        visible: canManageReportTemplates
      },
      {
        key: 'integrations',
        label: 'Integrations',
        description: 'Connect Jira and DefectDojo, then map RAPTOR fields onto their ticket templates.',
        icon: HubIcon,
        visible: canManageIntegrations
      },
      {
        key: 'maintenance',
        label: 'Maintenance',
        description: 'Manage pentest resets.',
        icon: BuildIcon,
        visible: canRunMaintenance
      },
      {
        key: 'notifications',
        label: 'Notifications',
        description: 'Configure email notifications and SMTP settings.',
        icon: EmailIcon,
        visible: canManageSecurity
      },
      {
        key: 'ai-scanner',
        label: 'AI Scanner',
        description: 'Providers, RAPTOR Local, and scan policy for the agentic scanner.',
        icon: SmartToyIcon,
        visible: canManageSecurity
      }
    ],
    [
      canManageUsers,
      canManageSecurity,
      canManageIpSources,
      canManageVulnCategories,
      canManageChecklistTemplates,
      canManageReportTemplates,
      canManageIntegrations,
      canRunMaintenance
    ]
  );

  const visibleSections = useMemo(
    () => sections.filter((section) => section.visible),
    [sections]
  );

  const domainTabs = useMemo(
    () =>
      DOMAIN_SUBSECTIONS.filter((item) => {
        if (item.key === 'collectors') return canManageSecurity || canRunMaintenance;
        if (item.key === 'cloud') return canManageSecurity;
        if (item.key === 'ip-sources') return canManageIpSources;
        return false;
      }).map((item) => ({ key: item.key, label: item.label })),
    [canManageIpSources, canManageSecurity, canRunMaintenance]
  );

  const activeSection =
    visibleSections.find((section) => section.key === selectedSection) || visibleSections[0] || null;
  const selectedChecklistTemplate = useMemo(
    () =>
      checklistTemplates.find(
        (template) => template.id === selectedChecklistTemplateId
      ) || null,
    [checklistTemplates, selectedChecklistTemplateId]
  );
  const selectedReportTemplate = useMemo(
    () =>
      reportTemplates.find((template) => template.id === selectedReportTemplateId) || null,
    [reportTemplates, selectedReportTemplateId]
  );
  const selectedServiceAccount = useMemo(
    () =>
      serviceAccounts.find((account) => account.username === selectedServiceAccountUsername) || null,
    [serviceAccounts, selectedServiceAccountUsername]
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

  const fetchServiceAccounts = useCallback(async () => {
    try {
      const response = await axios.get('/service-accounts');
      if (response.status === 200) {
        const accounts = response.data.service_accounts || [];
        setServiceAccounts(accounts);
        if (accounts.length === 0) {
          setSelectedServiceAccountUsername('');
        } else if (
          !selectedServiceAccountUsername ||
          !accounts.some((account) => account.username === selectedServiceAccountUsername)
        ) {
          setSelectedServiceAccountUsername(accounts[0].username);
        }
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to fetch service accounts.'
      );
    }
  }, [selectedServiceAccountUsername, showMessage]);

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

  const fetchReportTemplates = useCallback(async () => {
    try {
      const response = await axios.get('/report-templates?include_disabled=true');
      if (response.status === 200) {
        const templates = response.data.templates || [];
        setReportTemplates(templates);
        return templates;
      }
    } catch (error) {
      showMessage('error', 'Failed to fetch report templates.');
    }
    return [];
  }, [showMessage]);

  useEffect(() => {
    if (canManageIpSources) fetchIpSources();
    if (canManageUsers) {
      fetchExistingUsers();
      fetchServiceAccounts();
    }
    if (canManageVulnCategories) fetchVulnCategories();
    if (canManageChecklistTemplates) fetchChecklistTemplates();
    if (canManageReportTemplates) fetchReportTemplates();
  }, [
    canManageChecklistTemplates,
    canManageIpSources,
    canManageReportTemplates,
    canManageUsers,
    canManageVulnCategories,
    fetchReportTemplates,
    fetchChecklistTemplates,
    fetchExistingUsers,
    fetchServiceAccounts,
    fetchIpSources,
    fetchVulnCategories
  ]);

  useEffect(() => {
    if (!visibleSections.length) return;
    if (selectedSection === 'collectors' || selectedSection === 'ip-sources') {
      setSelectedSection('domains');
      return;
    }
    if (!selectedSection || !visibleSections.some((section) => section.key === selectedSection)) {
      setSelectedSection(visibleSections[0].key);
    }
  }, [selectedSection, visibleSections]);

  useEffect(() => {
    if (!domainTabs.length) return;
    if (!domainTabs.some((item) => item.key === domainManagementPage)) {
      setDomainManagementPage(domainTabs[0].key);
    }
  }, [domainManagementPage, domainTabs]);

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(''), 5000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [message]);

  useEffect(() => {
    if (!selectedServiceAccount) {
      setSelectedServiceAccountScopes([]);
      setSelectedServiceAccountEndDate('');
      return;
    }
    setSelectedServiceAccountScopes(selectedServiceAccount.scopes || []);
    setSelectedServiceAccountEndDate('');
  }, [selectedServiceAccount]);

  const handleSelectServiceAccount = (username) => {
    if (username !== selectedServiceAccountUsername) {
      setVisibleServiceApiKey('');
    }
    setSelectedServiceAccountUsername(username);
  };

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
        full_name: user.full_name,
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
    try {
      const response = await axios.delete('/delete-user', { data: { username } });
      if (response.status === 200) {
        showMessage('success', `User ${username} deleted successfully.`);
        setExistingUsers((prev) =>
          prev.filter((user) => user.username !== username)
        );
        fetchServiceAccounts();
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

  const handleDomainsRefresh = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/admin/domains/refresh');
      const queued = response.data.agents?.queued ?? 0;
      const immediate = response.data.agents?.immediate ?? 0;
      if (response.data.ok) {
        showMessage(
          'success',
          `Asked ${queued} agent${queued === 1 ? '' : 's'} to collect (${immediate} immediate).`
        );
      } else {
        showMessage('error', 'Refresh completed with errors.');
      }
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to refresh domains.');
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

  const handleCreateNewReportTemplate = () => {
    setSelectedReportTemplateId(null);
    setReportTemplateForm(createEmptyReportTemplateForm());
  };

  const handleSelectReportTemplate = (template) => {
    setSelectedReportTemplateId(template.id);
    setReportTemplateForm(createReportTemplateFormFromApi(template));
  };

  const handleReportTemplateFormChange = (field, value) => {
    setReportTemplateForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSaveReportTemplate = async () => {
    const key = selectedReportTemplate?.is_system
      ? (selectedReportTemplate.key || '').trim().toLowerCase()
      : reportTemplateForm.key.trim().toLowerCase();
    const name = reportTemplateForm.name.trim();
    if (!key || !name) {
      showMessage('error', 'Template key and name are required.');
      return;
    }

    if (!Array.isArray(reportTemplateForm.blocks) || reportTemplateForm.blocks.length === 0) {
      showMessage('error', 'At least one report block is required.');
      return;
    }

    const payload = {
      key,
      name,
      description: reportTemplateForm.description.trim(),
      template: toReportTemplateDefinition(reportTemplateForm),
      enabled: Boolean(reportTemplateForm.enabled)
    };

    setLoading(true);
    try {
      if (selectedReportTemplateId) {
        const response = await axios.put(`/report-templates/${selectedReportTemplateId}`, payload);
        if (response.status === 200) {
          showMessage('success', 'Report template updated.');
        }
      } else {
        const response = await axios.post('/report-templates', payload);
        if (response.status === 200) {
          showMessage('success', 'Report template created.');
          setSelectedReportTemplateId(response.data.id || null);
        }
      }

      const refreshedTemplates = await fetchReportTemplates();
      const refreshedSelectionId = selectedReportTemplateId || payload.key;
      const refreshedTemplate = refreshedTemplates.find(
        (template) =>
          template.id === refreshedSelectionId || template.key === refreshedSelectionId
      );
      if (refreshedTemplate) {
        handleSelectReportTemplate(refreshedTemplate);
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to save report template.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteReportTemplate = async (templateId, templateName) => {
    const template = reportTemplates.find((item) => item.id === templateId);
    if (template?.is_system) {
      showMessage(
        'error',
        'System templates cannot be deleted. Disable or reset them instead.'
      );
      return;
    }
    if (!window.confirm(`Delete report template "${templateName}"?`)) return;
    setLoading(true);
    try {
      const response = await axios.delete(`/report-templates/${templateId}`);
      if (response.status === 200) {
        showMessage('success', 'Report template deleted.');
        if (selectedReportTemplateId === templateId) {
          handleCreateNewReportTemplate();
        }
        fetchReportTemplates();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to delete report template.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleResetReportTemplate = async (template) => {
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
      const response = await axios.post(`/report-templates/${template.id}/reset`);
      if (response.status === 200) {
        showMessage('success', 'Report template reset to canonical.');
      }
      const refreshedTemplates = await fetchReportTemplates();
      const refreshedTemplate = refreshedTemplates.find((item) => item.id === template.id);
      if (refreshedTemplate) {
        handleSelectReportTemplate(refreshedTemplate);
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to reset report template.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDuplicateReportTemplate = async () => {
    const sourceKey = String(reportTemplateForm.key || selectedReportTemplate?.key || 'template')
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, '-')
      .replace(/^-+/, '');
    const base = sourceKey.slice(0, 50) || 'template';
    const existing = new Set((reportTemplates || []).map((item) => item.key));
    let key = `${base}-copy`.slice(0, 63);
    if (!/^[a-z0-9]/.test(key)) key = `t${key}`.slice(0, 63);
    let n = 2;
    while (existing.has(key) || key.length < 2) {
      const suffix = `-copy-${n}`;
      key = `${base.slice(0, Math.max(1, 63 - suffix.length))}${suffix}`;
      n += 1;
    }
    const name = `${(reportTemplateForm.name || selectedReportTemplate?.name || 'Template').trim()} (copy)`;
    const payload = {
      key,
      name,
      description: (reportTemplateForm.description || '').trim(),
      template: toReportTemplateDefinition(reportTemplateForm),
      enabled: Boolean(reportTemplateForm.enabled)
    };
    setLoading(true);
    try {
      const response = await axios.post('/report-templates', payload);
      if (response.status === 200) {
        showMessage('success', 'Template duplicated.');
        const refreshedTemplates = await fetchReportTemplates();
        const created =
          refreshedTemplates.find((item) => item.id === response.data.id) ||
          refreshedTemplates.find((item) => item.key === key);
        if (created) {
          handleSelectReportTemplate(created);
        }
      }
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to duplicate report template.');
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
    if (!localIsServiceAccount && !['user', 'pentester', 'manager'].includes(localRole)) {
      showMessage('error', 'Invalid role specified.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/add-local-user', {
        username: trimmedUsername,
        full_name: localFullName.trim() || undefined,
        role: localIsServiceAccount ? 'user' : localRole,
        permissions: localIsServiceAccount
          ? []
          : normalizeOptionalPermissions(localRole, localPermissions),
        is_service_account: localIsServiceAccount
      });
      if (response.status === 200) {
        showMessage(
          'success',
          localIsServiceAccount
            ? 'Service account created successfully.'
            : 'Local user created. Temporary password generated.'
        );
        setLocalTempPassword(localIsServiceAccount ? '' : response.data.temp_password || '');
        setLocalUsername('');
        setLocalFullName('');
        setLocalIsServiceAccount(false);
        setLocalRole('user');
        setLocalPermissions([]);
        fetchExistingUsers();
        fetchServiceAccounts();
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
          'Notebooks reset. Findings and frozen reports were kept.'
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

  const toggleScope = (scopes, scope) =>
    scopes.includes(scope)
      ? scopes.filter((current) => current !== scope)
      : [...scopes, scope];

  const handleToggleCreateServiceScope = (scope) => {
    setCreateServiceAccountScopes((prev) => toggleScope(prev, scope));
  };

  const handleToggleSelectedServiceScope = (scope) => {
    setSelectedServiceAccountScopes((prev) => toggleScope(prev, scope));
  };

  const handleCreateServiceAccountWithKey = async () => {
    const username = createServiceAccountUsername.trim().toLowerCase();
    if (!username) {
      showMessage('error', 'Service account username is required.');
      return;
    }
    if (createServiceAccountScopes.length === 0) {
      showMessage('error', 'Select at least one privilege.');
      return;
    }

    setLoading(true);
    try {
      const createResponse = await axios.post('/service-accounts', { username });
      if (createResponse.status === 201 || createResponse.status === 200) {
        const keyResponse = await axios.post(`/service-accounts/${username}/api-key`, {
          scopes: createServiceAccountScopes,
          end_date: createServiceAccountEndDate || undefined
        });
        if (keyResponse.status === 201 || keyResponse.status === 200) {
          const issuedKey = keyResponse.data?.service_account?.api_key || '';
          setCreateServiceAccountUsername('');
          setCreateServiceAccountEndDate('');
          setCreateServiceAccountScopes(['records.read']);
          setSelectedServiceAccountUsername(username);
          setVisibleServiceApiKey(issuedKey);
          if (issuedKey) {
            showMessage('success', 'Service account created. Copy the API key now — it will not be shown again.');
          } else {
            showMessage('error', 'Service account created, but the API key was not returned.');
          }
          fetchExistingUsers();
          fetchServiceAccounts();
        }
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to create service account.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKeyForSelectedServiceAccount = async () => {
    if (!selectedServiceAccountUsername) {
      showMessage('error', 'Select a service account first.');
      return;
    }
    if (selectedServiceAccountScopes.length === 0) {
      showMessage('error', 'Select at least one privilege.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post(
        `/service-accounts/${selectedServiceAccountUsername}/api-key`,
        {
          scopes: selectedServiceAccountScopes,
          end_date: selectedServiceAccountEndDate || undefined
        }
      );
      if (response.status === 201 || response.status === 200) {
        const issuedKey = response.data?.service_account?.api_key || '';
        setSelectedServiceAccountEndDate('');
        setVisibleServiceApiKey(issuedKey);
        if (issuedKey) {
          showMessage('success', 'API key created. Copy it now — it will not be shown again.');
        } else {
          showMessage('error', 'API key created, but it was not returned.');
        }
        fetchServiceAccounts();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to create API key.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRotateSelectedApiKey = async () => {
    if (!selectedServiceAccountUsername) return;
    if (!window.confirm('Rotate this API key now? The previous key will stop working immediately.')) {
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post(
        `/service-accounts/${selectedServiceAccountUsername}/api-key/rotate`
      );
      if (response.status === 200) {
        const issuedKey = response.data?.service_account?.api_key || '';
        setVisibleServiceApiKey(issuedKey);
        if (issuedKey) {
          showMessage('success', 'API key rotated. Copy the new key now — it will not be shown again.');
        } else {
          showMessage('error', 'API key rotated, but the new key was not returned.');
        }
        fetchServiceAccounts();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to rotate API key.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSelectedServiceScopes = async () => {
    if (!selectedServiceAccountUsername) return;
    if (selectedServiceAccountScopes.length === 0) {
      showMessage('error', 'Select at least one privilege.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.put(
        `/service-accounts/${selectedServiceAccountUsername}/privileges`,
        {
          scopes: selectedServiceAccountScopes
        }
      );
      if (response.status === 200) {
        showMessage('success', 'Service account privileges updated.');
        fetchServiceAccounts();
      }
    } catch (error) {
      showMessage(
        'error',
        error.response?.data?.error || 'Failed to update privileges.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCopyVisibleApiKey = async () => {
    if (!visibleServiceApiKey) return;
    try {
      await navigator.clipboard.writeText(visibleServiceApiKey);
      showMessage('success', 'API key copied to clipboard.');
    } catch (error) {
      showMessage('error', 'Failed to copy API key.');
    }
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
            onSelectUserManagementPage={setUserManagementPage}
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
                localFullName={localFullName}
                setLocalFullName={setLocalFullName}
                localIsServiceAccount={localIsServiceAccount}
                setLocalIsServiceAccount={setLocalIsServiceAccount}
                localRole={localRole}
                localPermissions={localPermissions}
                localTempPassword={localTempPassword}
                onRoleChange={handleLocalRoleChange}
                onTogglePermission={handleLocalPermissionToggle}
                onCreateLocalUser={handleCreateLocalUser}
              />
            }
            serviceAccountsPanel={
              <ServiceAccountsPanel
                loading={loading}
                serviceAccounts={serviceAccounts}
                selectedServiceAccountUsername={selectedServiceAccountUsername}
                onSelectServiceAccount={handleSelectServiceAccount}
                createUsername={createServiceAccountUsername}
                setCreateUsername={setCreateServiceAccountUsername}
                createScopes={createServiceAccountScopes}
                onToggleCreateScope={handleToggleCreateServiceScope}
                createEndDate={createServiceAccountEndDate}
                setCreateEndDate={setCreateServiceAccountEndDate}
                onCreateServiceAccountWithKey={handleCreateServiceAccountWithKey}
                selectedScopes={selectedServiceAccountScopes}
                onToggleSelectedScope={handleToggleSelectedServiceScope}
                selectedEndDate={selectedServiceAccountEndDate}
                setSelectedEndDate={setSelectedServiceAccountEndDate}
                onCreateKeyForSelectedServiceAccount={handleCreateKeyForSelectedServiceAccount}
                onSaveSelectedScopes={handleSaveSelectedServiceScopes}
                onRotateSelectedKey={handleRotateSelectedApiKey}
                visibleApiKey={visibleServiceApiKey}
                onCopyVisibleApiKey={handleCopyVisibleApiKey}
                onDismissVisibleApiKey={() => setVisibleServiceApiKey('')}
              />
            }
            ssoPanel={<SsoConnectionsPanel showMessage={showMessage} />}
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
      case 'domains':
        return (
          <DomainsManagementSection
            canManageCollectors={canManageSecurity}
            canRunMaintenance={canRunMaintenance}
            canManageIpSources={canManageIpSources}
            tab={domainManagementPage}
            onSelectTab={setDomainManagementPage}
            collectors={<CollectorsSection showMessage={showMessage} />}
            refresh={<DomainsRefreshCard loading={loading} onRunUpdate={handleDomainsRefresh} />}
            cloudDns={canManageSecurity ? <CloudDnsSection showMessage={showMessage} /> : null}
            ipSources={
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
            }
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
      case 'report-templates':
        return (
          <ReportTemplatesSection
            loading={loading}
            selectedTemplate={selectedReportTemplate}
            templateForm={reportTemplateForm}
            showMessage={showMessage}
            onChangeTemplateForm={handleReportTemplateFormChange}
            onSaveTemplate={handleSaveReportTemplate}
            onDeleteTemplate={handleDeleteReportTemplate}
            onResetTemplate={handleResetReportTemplate}
            onDuplicateTemplate={handleDuplicateReportTemplate}
          />
        );
      case 'maintenance':
        return (
          <MaintenanceSection
            loading={loading}
            resetCsv={resetCsv}
            resetStats={resetStats}
            onDownloadResetCsv={downloadResetCsv}
            onOpenResetDialog={handleOpenResetDialog}
          />
        );
      case 'integrations':
        return <IntegrationsSection showMessage={showMessage} />;
      case 'notifications':
        return <EmailSettingsPanel showMessage={showMessage} />;
      case 'ai-scanner':
        return (
          <AiScannerSection
            tab={aiScannerPage}
            onSelectTab={setAiScannerPage}
            showMessage={showMessage}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Page>
      <PageHeader
        title="Settings"
        subtitle={
          activeSection?.description || 'Manage platform settings available for your role.'
        }
        leading={
          isMobile ? (
            <Button size="small" onClick={() => setNavOpen(true)}>
              Menu
            </Button>
          ) : null
        }
      />
      {loading ? <Progress deferred /> : null}
      <SettingsShell
        renderNav={() => (
          <SettingsNav
            sections={visibleSections}
            selectedSection={selectedSection}
            onSelectSection={handleSelectSection}
            userManagementPage={userManagementPage}
            onSelectUserManagementPage={setUserManagementPage}
            domainManagementPage={domainManagementPage}
            onSelectDomainManagementPage={setDomainManagementPage}
            domainTabs={domainTabs}
            aiScannerPage={aiScannerPage}
            onSelectAiScannerPage={setAiScannerPage}
            reportTemplates={reportTemplates}
            selectedReportTemplateId={selectedReportTemplateId}
            onCreateReportTemplate={handleCreateNewReportTemplate}
            onSelectReportTemplate={handleSelectReportTemplate}
          />
        )}
        isMobile={isMobile}
        navOpen={navOpen}
        onCloseNav={() => setNavOpen(false)}
      >
        {activeSection ? (
          renderSection()
        ) : (
          <EmptyState title="No settings" hint="No settings sections are available for your account." />
        )}
      </SettingsShell>
      <Toast
        open={Boolean(message)}
        message={message}
        severity={messageType || 'info'}
        onClose={() => setMessage('')}
      />
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
    </Page>
  );
};

export default AdminSettings;
