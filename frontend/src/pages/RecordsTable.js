import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dns, Download, Refresh } from '@mui/icons-material';
import AppGroupsList, { InventoryHead } from './records-table/components/AppGroupsList';
import CreateManualRecordDialog from './records-table/components/CreateManualRecordDialog';
import ManageAppsDialog from './records-table/components/ManageAppsDialog';
import RecordCard from './records-table/components/RecordCard';
import RecordsStatsBar from './records-table/components/RecordsStatsBar';
import SearchFiltersSection from './records-table/components/SearchFiltersSection';
import { INVENTORY_MIN_WIDTH_FLAT, INVENTORY_MIN_WIDTH_GROUPED, INVENTORY_TABLE, SEARCH_PARAMETERS } from './records-table/constants';
import {
  createManualRecord,
  createApp,
  deleteAppById,
  deleteRecordById,
  getApps,
  getEnvironments,
  getRecords,
  resolveSyncConflictById,
  getSessionStatus,
  renameApp,
  updateRecordById
} from './records-table/services';
import {
  analyzeSearchInput,
  buildAppGroups,
  buildRecordsCsv,
  calculateRecordStats,
  collectUnseenGroupKeys,
  createFilterFromAnalysis,
  downloadCsvFile,
  extractParameterValues,
  filterRecords,
  generateSearchSuggestions
} from './records-table/utils';
import {
  Button,
  EmptyState,
  Page,
  PageHeader,
  Panel,
  Progress,
  Surface,
  Text,
  Toast
} from '../design/primitives';
import { RADIUS } from '../design/tokens';

const emptyCreateForm = {
  name: '',
  ip_address: '',
  application_id: '',
  environment_id: '',
  application_owner: '',
  maintainer: '',
  open_ports: '',
  description: ''
};

const RecordsTable = ({ userRole, userPermissions }) => {
  const [records, setRecords] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilters, setActiveFilters] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [originFilter, setOriginFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [appFilter, setAppFilter] = useState('');
  const [conflictFilter, setConflictFilter] = useState(false);
  const [expandedRecords, setExpandedRecords] = useState(new Set());
  const [editingRecord, setEditingRecord] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [apps, setApps] = useState([]);
  const [envByApp, setEnvByApp] = useState({});
  const [groupByApp, setGroupByApp] = useState(true);
  const [expandedApps, setExpandedApps] = useState(new Set());
  const [appsDialogOpen, setAppsDialogOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createDialogBusy, setCreateDialogBusy] = useState(false);
  const [createDialogError, setCreateDialogError] = useState('');
  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [newAppName, setNewAppName] = useState('');
  const [appEdits, setAppEdits] = useState({});
  const [appsBusy, setAppsBusy] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [pendingConflictId, setPendingConflictId] = useState(null);
  const [toast, setToast] = useState(null);
  const coldStart = useRef(true);
  const seededAppKeys = useRef(new Set());

  const navigate = useNavigate();
  const hasPermission = (permission) =>
    userRole === 'admin' || userPermissions?.includes(permission);
  const canDeleteRecords = hasPermission('delete_records');
  const canManageApps = hasPermission('manage_apps');
  const canCreateManualRecords = hasPermission('create_manual_records');
  const canModifyRecords = hasPermission('modify_records');
  const canViewRecordDetails = hasPermission('view_record_details');
  const canExportRecords = hasPermission('export_records');
  const canViewPentestPage = hasPermission('view_pentest_page');
  const canViewSecurityDashboard = hasPermission('view_security_dashboard');
  const canResolveSyncConflicts = userRole === 'admin';

  const fetchRecords = useCallback(async () => {
    if (coldStart.current) setLoading(true);
    else setRefreshing(true);
    try {
      const sessionResponse = await getSessionStatus();
      if (sessionResponse.status !== 200) {
        navigate('/login');
        return;
      }

      const recordsResponse = await getRecords();
      const fetchedRecords = recordsResponse.data.sort(
        (left, right) =>
          new Date(right.last_modification_date || right.creation_date) -
          new Date(left.last_modification_date || left.creation_date)
      );

      setRecords(fetchedRecords);
      coldStart.current = false;
    } catch (error) {
      console.error('Error fetching records:', error);
      navigate('/login');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [navigate]);

  const fetchApps = useCallback(async () => {
    try {
      const response = await getApps();
      if (response.status === 200) {
        setApps(response.data || []);
      }
    } catch (error) {
      console.error('Error fetching applications:', error);
    }
  }, []);

  const loadEnvironments = useCallback(async (applicationId) => {
    if (!applicationId) return [];
    if (envByApp[applicationId]) return envByApp[applicationId];
    try {
      const response = await getEnvironments(applicationId);
      const environments = response.data.environments || [];
      setEnvByApp((prev) => ({ ...prev, [applicationId]: environments }));
      return environments;
    } catch (error) {
      return [];
    }
  }, [envByApp]);

  useEffect(() => {
    fetchRecords();
    fetchApps();
  }, [fetchApps, fetchRecords]);

  const { valuesByKey: parameterValues, countsByKey: parameterCounts } = useMemo(
    () => extractParameterValues(records, SEARCH_PARAMETERS),
    [records]
  );

  const searchFiltered = useMemo(() => {
    let next = filterRecords(records, activeFilters, searchQuery, SEARCH_PARAMETERS);
    if (originFilter) {
      next = next.filter((record) => (record.origin || 'automated') === originFilter);
    }
    if (sourceFilter) next = next.filter((record) => record.source === sourceFilter);
    if (appFilter === 'unassigned') {
      next = next.filter((record) => !record.application_id);
    } else if (appFilter) {
      next = next.filter((record) => String(record.application_id) === String(appFilter));
    }
    return next;
  }, [records, activeFilters, searchQuery, originFilter, sourceFilter, appFilter]);

  const filteredRecords = useMemo(() => {
    let next = searchFiltered;
    if (statusFilter) next = next.filter((record) => record.status === statusFilter);
    if (conflictFilter) next = next.filter((record) => Boolean(record.sync_conflict));
    return next;
  }, [searchFiltered, statusFilter, conflictFilter]);

  const stats = useMemo(() => calculateRecordStats(searchFiltered), [searchFiltered]);
  const groupedRecords = useMemo(() => buildAppGroups(filteredRecords), [filteredRecords]);
  const filtersOn = Boolean(
    activeFilters.length ||
      searchQuery ||
      statusFilter ||
      originFilter ||
      sourceFilter ||
      appFilter ||
      conflictFilter
  );

  useEffect(() => {
    const keys = groupedRecords.map((group) => group.key);
    const unseen = collectUnseenGroupKeys(seededAppKeys.current, keys);
    if (!unseen.length) return;
    unseen.forEach((key) => seededAppKeys.current.add(key));
    setExpandedApps((prev) => {
      const next = new Set(prev);
      unseen.forEach((key) => next.add(key));
      return next;
    });
  }, [groupedRecords]);

  const sourceOptions = useMemo(
    () => [
      { value: '', label: 'All sources' },
      ...(parameterValues.source || []).map((value) => ({ value, label: value }))
    ],
    [parameterValues]
  );

  const appOptions = useMemo(
    () => [
      { value: '', label: 'All apps' },
      { value: 'unassigned', label: 'Unassigned' },
      ...apps.map((app) => ({ value: String(app.id), label: app.name }))
    ],
    [apps]
  );

  const handleCreateApp = async () => {
    const name = newAppName.trim();
    if (!name) return;
    setAppsBusy(true);
    try {
      await createApp(name);
      setNewAppName('');
      fetchApps();
      fetchRecords();
    } catch (error) {
      console.error('Error creating application:', error);
      setToast({ message: 'Failed to create application.', severity: 'error' });
    } finally {
      setAppsBusy(false);
    }
  };

  const resetCreateDialog = () => {
    setCreateDialogOpen(false);
    setCreateDialogBusy(false);
    setCreateDialogError('');
    setCreateForm(emptyCreateForm);
  };

  const handleCreateManualRecord = async () => {
    if (!createForm.name.trim() || !createForm.ip_address.trim()) {
      setCreateDialogError('Domain and IP address are required.');
      return;
    }
    setCreateDialogBusy(true);
    setCreateDialogError('');
    try {
      await createManualRecord({
        ...createForm,
        name: createForm.name.trim(),
        ip_address: createForm.ip_address.trim()
      });
      resetCreateDialog();
      await fetchRecords();
    } catch (error) {
      setCreateDialogBusy(false);
      setCreateDialogError(error.response?.data?.error || 'Failed to create manual domain.');
    }
  };

  const handleRenameApp = async (appId) => {
    const name = (appEdits[appId] || '').trim();
    if (!name) return;
    setAppsBusy(true);
    try {
      await renameApp(appId, name);
      setApps((prev) => prev.map((app) => (app.id === appId ? { ...app, name } : app)));
      setRecords((prev) =>
        prev.map((record) =>
          Number(record.application_id) === Number(appId)
            ? { ...record, application_name: name }
            : record
        )
      );
      setAppEdits((prev) => ({ ...prev, [appId]: name }));
      await Promise.all([fetchApps(), fetchRecords()]);
    } catch (error) {
      console.error('Error renaming application:', error);
      setToast({ message: 'Failed to rename application.', severity: 'error' });
    } finally {
      setAppsBusy(false);
    }
  };

  const handleDeleteApp = async (appId) => {
    setAppsBusy(true);
    try {
      await deleteAppById(appId);
      fetchApps();
      fetchRecords();
    } catch (error) {
      console.error('Error deleting application:', error);
      setToast({ message: 'Failed to delete application.', severity: 'error' });
    } finally {
      setAppsBusy(false);
    }
  };

  const handleInputChange = (value) => {
    setSearchInput(value);

    if (!value.trim()) {
      setDropdownOpen(false);
      setSuggestions([]);
      return;
    }

    const nextSuggestions = generateSearchSuggestions(
      value,
      SEARCH_PARAMETERS,
      parameterValues,
      parameterCounts
    );
    setSuggestions(nextSuggestions);
    setDropdownOpen(nextSuggestions.length > 0);
  };

  const submitSearch = (input = searchInput) => {
    const analysis = analyzeSearchInput(input, SEARCH_PARAMETERS);
    const filter = createFilterFromAnalysis(analysis, SEARCH_PARAMETERS);

    if (filter) {
      setActiveFilters((prev) => [...prev, filter]);
      setSearchInput('');
      setDropdownOpen(false);
      return;
    }

    setSearchQuery(input);
    if (analysis.type === 'text') {
      setSearchInput(input);
    } else {
      setSearchInput('');
    }
    setDropdownOpen(false);
  };

  const selectSuggestion = (suggestion) => {
    if (suggestion.type === 'field') {
      setSearchInput(suggestion.display);
      const valueSuggestions = generateSearchSuggestions(
        suggestion.display,
        SEARCH_PARAMETERS,
        parameterValues,
        parameterCounts
      );
      setSuggestions(valueSuggestions);
      setDropdownOpen(valueSuggestions.length > 0);
      return;
    }

    if (suggestion.type === 'value') {
      submitSearch(`${suggestion.field}=${suggestion.value}`);
    }
  };

  const removeFilter = (filterId) => {
    setActiveFilters((prev) => prev.filter((entry) => entry.id !== filterId));
  };

  const clearAllFilters = () => {
    setActiveFilters([]);
    setSearchQuery('');
    setSearchInput('');
    setStatusFilter('');
    setOriginFilter('');
    setSourceFilter('');
    setAppFilter('');
    setConflictFilter(false);
    setDropdownOpen(false);
  };

  const toggleExpanded = (recordId) => {
    const nextExpanded = new Set(expandedRecords);
    if (nextExpanded.has(recordId)) nextExpanded.delete(recordId);
    else nextExpanded.add(recordId);
    setExpandedRecords(nextExpanded);
  };

  const toggleAppGroup = (groupKey) => {
    const nextExpanded = new Set(expandedApps);
    if (nextExpanded.has(groupKey)) nextExpanded.delete(groupKey);
    else nextExpanded.add(groupKey);
    setExpandedApps(nextExpanded);
  };

  const expandAllGroups = () => {
    setExpandedApps(new Set(groupedRecords.map((group) => group.key)));
  };

  const collapseAllGroups = () => {
    setExpandedApps(new Set());
  };

  const startEditing = (record) => {
    if (!canModifyRecords) return;
    setEditingRecord(record.id);
    setEditForm({
      application_id: record.application_id || '',
      environment_id: record.environment_id || '',
      application_owner: record.application_owner || '',
      maintainer: record.maintainer || '',
      open_ports: record.open_ports || '',
      description: record.description || ''
    });
    if (record.application_id) {
      loadEnvironments(record.application_id);
    }
  };

  const cancelEditing = () => {
    setEditingRecord(null);
    setEditForm({});
  };

  const saveRecord = async (recordId) => {
    try {
      await updateRecordById(recordId, editForm);
      setEditingRecord(null);
      setEditForm({});
      fetchRecords();
    } catch (error) {
      console.error('Error updating record:', error);
      setToast({ message: 'Failed to update record.', severity: 'error' });
    }
  };

  const confirmDeleteRecord = async () => {
    if (!pendingDeleteId) return;
    try {
      await deleteRecordById(pendingDeleteId);
      setPendingDeleteId(null);
      fetchRecords();
    } catch (error) {
      console.error('Error deleting record:', error);
      setToast({ message: 'Failed to delete record.', severity: 'error' });
    }
  };

  const confirmResolveConflict = async () => {
    if (!pendingConflictId) return;
    try {
      await resolveSyncConflictById(pendingConflictId);
      setPendingConflictId(null);
      fetchRecords();
    } catch (error) {
      setToast({
        message: error.response?.data?.error || 'Failed to resolve sync conflict.',
        severity: 'error'
      });
    }
  };

  const exportCSV = () => {
    const csv = buildRecordsCsv(filteredRecords);
    downloadCsvFile(csv, 'dns_records.csv');
  };

  const renderRecordCard = (record) => (
    <RecordCard
      key={record.id}
      record={record}
      grouped={groupByApp}
      isExpanded={expandedRecords.has(record.id)}
      isEditing={editingRecord === record.id}
      editForm={editForm}
      apps={apps}
      environments={envByApp[editForm.application_id] || []}
      canModifyRecords={canModifyRecords}
      canDeleteRecords={canDeleteRecords}
      canResolveSyncConflicts={canResolveSyncConflicts}
      canViewRecordDetails={canViewRecordDetails}
      onToggleExpanded={toggleExpanded}
      onUpdateEditForm={(next) => {
        setEditForm(next);
        if (next.application_id) loadEnvironments(next.application_id);
      }}
      onStartEditing={startEditing}
      onSave={saveRecord}
      onCancelEditing={cancelEditing}
      onDelete={setPendingDeleteId}
      onResolveSyncConflict={setPendingConflictId}
      onOpenHistory={(targetRecord) => navigate(`/records/record/${targetRecord.id}`)}
    />
  );

  const pendingDelete = records.find((record) => record.id === pendingDeleteId);
  const pendingConflict = records.find((record) => record.id === pendingConflictId);

  return (
    <Page>
      <PageHeader
        title="Asset Inventory"
        actions={
          <>
            <Button size="small" startIcon={<Refresh sx={{ fontSize: 16 }} />} onClick={fetchRecords}>
              Refresh
            </Button>
            {canExportRecords ? (
              <Button
                size="small"
                variant="outlined"
                startIcon={<Download sx={{ fontSize: 16 }} />}
                onClick={exportCSV}
              >
                Export
              </Button>
            ) : null}
          </>
        }
      />

      {refreshing || (loading && records.length === 0) ? <Progress deferred /> : null}

      <SearchFiltersSection
        activeFilters={activeFilters}
        searchQuery={searchQuery}
        searchInput={searchInput}
        dropdownOpen={dropdownOpen}
        suggestions={suggestions}
        onClearAllFilters={clearAllFilters}
        onRemoveFilter={removeFilter}
        onSetSearchQuery={setSearchQuery}
        onSetSearchInput={setSearchInput}
        onInputChange={handleInputChange}
        onSubmitSearch={submitSearch}
        onSelectSuggestion={selectSuggestion}
        onSetDropdownOpen={setDropdownOpen}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        originFilter={originFilter}
        onOriginFilterChange={setOriginFilter}
        sourceFilter={sourceFilter}
        onSourceFilterChange={setSourceFilter}
        appFilter={appFilter}
        onAppFilterChange={setAppFilter}
        conflictFilter={conflictFilter}
        sourceOptions={sourceOptions}
        appOptions={appOptions}
        groupByApp={groupByApp}
        onToggleGroupByApp={setGroupByApp}
        canManageApps={canManageApps}
        canCreateManualRecords={canCreateManualRecords}
        onOpenCreateDialog={() => setCreateDialogOpen(true)}
        onOpenAppsDialog={() => setAppsDialogOpen(true)}
        onExpandAll={expandAllGroups}
        onCollapseAll={collapseAllGroups}
      />

      <RecordsStatsBar
        stats={stats}
        inventoryCount={searchFiltered.length}
        totalCount={records.length}
        statusFilter={statusFilter}
        conflictFilter={conflictFilter}
        onStatusFilterChange={setStatusFilter}
        onConflictFilterChange={setConflictFilter}
      />

      {filteredRecords.length === 0 ? (
        <EmptyState
          icon={Dns}
          title={loading ? 'Loading hosts' : records.length === 0 ? 'No hosts yet' : 'No hosts match'}
          hint={
            loading
              ? 'Inventory will appear here once the first fetch lands.'
              : filtersOn
                ? 'Widen the filters or clear the search.'
                : 'Add a manual domain, or wait for DNS sync to land names here.'
          }
          actions={
            !loading && filtersOn ? (
              <Button variant="outlined" onClick={clearAllFilters}>
                Clear filters
              </Button>
            ) : canCreateManualRecords && !loading ? (
              <Button variant="contained" onClick={() => setCreateDialogOpen(true)}>
                Add Manual Domain
              </Button>
            ) : null
          }
        />
      ) : (
        <Surface
          style={{
            borderRadius: RADIUS.panel,
            overflow: 'auto'
          }}
        >
          <table
            style={{
              ...INVENTORY_TABLE,
              minWidth: groupByApp ? INVENTORY_MIN_WIDTH_GROUPED : INVENTORY_MIN_WIDTH_FLAT
            }}
          >
            <InventoryHead grouped={groupByApp} />
            {groupByApp ? (
              <AppGroupsList
                groups={groupedRecords}
                expandedApps={expandedApps}
                onToggleAppGroup={toggleAppGroup}
                renderRecordCard={renderRecordCard}
                canViewSecurityDashboard={canViewSecurityDashboard}
                canViewPentestPage={canViewPentestPage}
                canManageApps={canManageApps}
                canExportRecords={canExportRecords}
                onOpenApp={(appId) => navigate(`/apps/${appId}`)}
                onOpenPentest={(appId) => navigate(`/apps/${appId}`, { state: { tab: 'waves' } })}
                onManageApps={() => setAppsDialogOpen(true)}
                onExportGroup={(group) => {
                  const csv = buildRecordsCsv(group.records);
                  downloadCsvFile(csv, `${group.name.replace(/\s+/g, '_').toLowerCase()}_hosts.csv`);
                }}
              />
            ) : (
              <tbody>{filteredRecords.map(renderRecordCard)}</tbody>
            )}
          </table>
        </Surface>
      )}

      <ManageAppsDialog
        open={appsDialogOpen}
        onClose={() => setAppsDialogOpen(false)}
        apps={apps}
        newAppName={newAppName}
        onSetNewAppName={setNewAppName}
        appEdits={appEdits}
        onSetAppEdits={setAppEdits}
        appsBusy={appsBusy}
        onCreateApp={handleCreateApp}
        onRenameApp={handleRenameApp}
        onDeleteApp={handleDeleteApp}
      />

      <CreateManualRecordDialog
        open={createDialogOpen}
        form={createForm}
        apps={apps}
        environments={envByApp[createForm.application_id] || []}
        busy={createDialogBusy}
        error={createDialogError}
        onClose={resetCreateDialog}
        onChange={(field, value) => {
          setCreateForm((prev) => ({
            ...prev,
            [field]: value,
            ...(field === 'application_id' ? { environment_id: '' } : {})
          }));
          if (field === 'application_id' && value) {
            loadEnvironments(value);
          }
        }}
        onSubmit={handleCreateManualRecord}
      />

      <Panel
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDeleteId(null)}
        title="Remove host"
        actions={
          <>
            <Button onClick={() => setPendingDeleteId(null)}>Cancel</Button>
            <Button variant="contained" onClick={confirmDeleteRecord}>
              Delete
            </Button>
          </>
        }
      >
        <Text as="p" variant="body" style={{ margin: 0 }}>
          Remove {pendingDelete?.name || 'this domain'} from inventory? This does not delete findings
          that already exist on the host.
        </Text>
      </Panel>

      <Panel
        open={Boolean(pendingConflict)}
        onClose={() => setPendingConflictId(null)}
        title="Resolve sync conflict"
        actions={
          <>
            <Button onClick={() => setPendingConflictId(null)}>Cancel</Button>
            <Button variant="contained" onClick={confirmResolveConflict}>
              Adopt imported data
            </Button>
          </>
        }
      >
        <Text as="p" variant="body" style={{ margin: 0 }}>
          Convert {pendingConflict?.name || 'this manual host'} into an automated asset using the
          current live import.
        </Text>
      </Panel>

      <Toast
        open={Boolean(toast)}
        message={toast?.message}
        severity={toast?.severity}
        onClose={() => setToast(null)}
      />
    </Page>
  );
};

export default RecordsTable;
