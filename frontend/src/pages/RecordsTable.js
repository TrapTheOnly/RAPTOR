import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, LinearProgress, Paper, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import AppGroupsList from './records-table/components/AppGroupsList';
import ManageAppsDialog from './records-table/components/ManageAppsDialog';
import RecordCard from './records-table/components/RecordCard';
import RecordsStatsBar from './records-table/components/RecordsStatsBar';
import RecordsToolbar from './records-table/components/RecordsToolbar';
import SearchFiltersSection from './records-table/components/SearchFiltersSection';
import { SEARCH_PARAMETERS } from './records-table/constants';
import {
  createApp,
  deleteAppById,
  deleteRecordById,
  getApps,
  getRecords,
  getSessionStatus,
  renameApp,
  updateRecordById
} from './records-table/services';
import {
  analyzeSearchInput,
  buildAppGroups,
  buildRecordsCsv,
  calculateRecordStats,
  createFilterFromAnalysis,
  createFilterFromSelection,
  downloadCsvFile,
  extractParameterValues,
  filterRecords,
  generateSearchSuggestions
} from './records-table/utils';

const RecordsTable = ({ userRole, userPermissions, darkMode }) => {
  const [records, setRecords] = useState([]);
  const [filteredRecords, setFilteredRecords] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilters, setActiveFilters] = useState([]);
  const [expandedRecords, setExpandedRecords] = useState(new Set());
  const [editingRecord, setEditingRecord] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchMenuAnchor, setSearchMenuAnchor] = useState(null);
  const [selectedParameter, setSelectedParameter] = useState(null);
  const [parameterValues, setParameterValues] = useState({});
  const [parameterCounts, setParameterCounts] = useState({});
  const [searchInput, setSearchInput] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [apps, setApps] = useState([]);
  const [groupByApp, setGroupByApp] = useState(true);
  const [expandedApps, setExpandedApps] = useState(new Set());
  const [appsDialogOpen, setAppsDialogOpen] = useState(false);
  const [newAppName, setNewAppName] = useState('');
  const [appEdits, setAppEdits] = useState({});
  const [appsBusy, setAppsBusy] = useState(false);
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    updated: 0,
    missing: 0,
    sources: 0
  });

  const navigate = useNavigate();
  const theme = useTheme();
  const hasPermission = (permission) =>
    userRole === 'admin' || userPermissions?.includes(permission);
  const canDeleteRecords = hasPermission('delete_records');
  const canManageApps = hasPermission('manage_apps');
  const canModifyRecords = hasPermission('modify_records');
  const canViewRecordDetails = hasPermission('view_record_details');
  const canExportRecords = hasPermission('export_records');
  const canViewPentestPage = hasPermission('view_pentest_page');

  const fetchRecords = useCallback(async () => {
    setLoading(true);
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
      setStats(calculateRecordStats(fetchedRecords));
    } catch (error) {
      console.error('Error fetching records:', error);
      navigate('/login');
    } finally {
      setLoading(false);
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

  useEffect(() => {
    fetchRecords();
    fetchApps();
  }, [fetchApps, fetchRecords]);

  useEffect(() => {
    const { valuesByKey, countsByKey } = extractParameterValues(records, SEARCH_PARAMETERS);
    setParameterValues(valuesByKey);
    setParameterCounts(countsByKey);
  }, [records]);

  useEffect(() => {
    setFilteredRecords(filterRecords(records, activeFilters, searchQuery, SEARCH_PARAMETERS));
  }, [records, activeFilters, searchQuery]);

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
    } finally {
      setAppsBusy(false);
    }
  };

  const handleRenameApp = async (appId) => {
    const name = (appEdits[appId] || '').trim();
    if (!name) return;
    setAppsBusy(true);
    try {
      await renameApp(appId, name);

      // Instant UI propagation for all records assigned to this application.
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
    } finally {
      setAppsBusy(false);
    }
  };

  const handleDeleteApp = async (appId) => {
    if (!window.confirm('Delete this application? Domains will be unassigned.')) return;
    setAppsBusy(true);
    try {
      await deleteAppById(appId);
      fetchApps();
      fetchRecords();
    } catch (error) {
      console.error('Error deleting application:', error);
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

    const newSuggestions = generateSearchSuggestions(
      value,
      SEARCH_PARAMETERS,
      parameterValues,
      parameterCounts
    );
    setSuggestions(newSuggestions);
    setDropdownOpen(newSuggestions.length > 0);
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

  const addFilter = (parameter, value) => {
    setActiveFilters((prev) => [
      ...prev,
      createFilterFromSelection(parameter, value, SEARCH_PARAMETERS)
    ]);
    setSearchMenuAnchor(null);
    setSelectedParameter(null);
  };

  const removeFilter = (filterId) => {
    setActiveFilters((prev) => prev.filter((entry) => entry.id !== filterId));
  };

  const clearAllFilters = () => {
    setActiveFilters([]);
    setSearchQuery('');
    setSearchInput('');
    setDropdownOpen(false);
  };

  const toggleExpanded = (recordId) => {
    const nextExpanded = new Set(expandedRecords);
    if (nextExpanded.has(recordId)) {
      nextExpanded.delete(recordId);
    } else {
      nextExpanded.add(recordId);
    }
    setExpandedRecords(nextExpanded);
  };

  const toggleAppGroup = (groupKey) => {
    const nextExpanded = new Set(expandedApps);
    if (nextExpanded.has(groupKey)) {
      nextExpanded.delete(groupKey);
    } else {
      nextExpanded.add(groupKey);
    }
    setExpandedApps(nextExpanded);
  };

  const startEditing = (record) => {
    if (!canModifyRecords) return;
    setEditingRecord(record.id);
    setEditForm({
      application_id: record.application_id || '',
      application_owner: record.application_owner || '',
      maintainer: record.maintainer || '',
      open_ports: record.open_ports || ''
    });
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
    }
  };

  const deleteRecord = async (recordId) => {
    if (window.confirm('Are you sure you want to delete this record?')) {
      try {
        await deleteRecordById(recordId);
        fetchRecords();
      } catch (error) {
        console.error('Error deleting record:', error);
      }
    }
  };

  const exportCSV = () => {
    const csv = buildRecordsCsv(filteredRecords);
    downloadCsvFile(csv, 'dns_records.csv');
  };

  const groupedRecords = useMemo(() => buildAppGroups(filteredRecords), [filteredRecords]);

  const renderRecordCard = (record) => (
    <RecordCard
      key={record.id}
      record={record}
      isExpanded={expandedRecords.has(record.id)}
      isEditing={editingRecord === record.id}
      editForm={editForm}
      apps={apps}
      canModifyRecords={canModifyRecords}
      canDeleteRecords={canDeleteRecords}
      canViewRecordDetails={canViewRecordDetails}
      canViewPentestPage={canViewPentestPage}
      onToggleExpanded={toggleExpanded}
      onUpdateEditForm={setEditForm}
      onStartEditing={startEditing}
      onSave={saveRecord}
      onCancelEditing={cancelEditing}
      onDelete={deleteRecord}
      onOpenHistory={(targetRecord) => navigate(`/records/record/${targetRecord.id}`)}
      onOpenPentest={(targetRecord) => navigate(`/pentest/record/${targetRecord.id}`)}
      theme={theme}
    />
  );

  if (loading) {
    return (
      <Box p={3}>
        <LinearProgress />
        <Typography variant="h6" sx={{ mt: 2 }}>
          Loading records...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Records
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Existing internet-facing DNS records
          </Typography>
        </Box>
      </Box>

      <SearchFiltersSection
        activeFilters={activeFilters}
        searchQuery={searchQuery}
        searchInput={searchInput}
        dropdownOpen={dropdownOpen}
        suggestions={suggestions}
        canExportRecords={canExportRecords}
        onClearAllFilters={clearAllFilters}
        onRemoveFilter={removeFilter}
        onSetSearchQuery={setSearchQuery}
        onSetSearchInput={setSearchInput}
        onInputChange={handleInputChange}
        onSubmitSearch={submitSearch}
        onSelectSuggestion={selectSuggestion}
        onSetDropdownOpen={setDropdownOpen}
        onExportCsv={exportCSV}
        onRefresh={fetchRecords}
        onOpenSearchMenu={(event) => setSearchMenuAnchor(event.currentTarget)}
        searchMenuAnchor={searchMenuAnchor}
        selectedParameter={selectedParameter}
        onCloseSearchMenu={() => {
          setSearchMenuAnchor(null);
          setSelectedParameter(null);
        }}
        searchParameters={SEARCH_PARAMETERS}
        parameterValues={parameterValues}
        parameterCounts={parameterCounts}
        onSelectParameter={setSelectedParameter}
        onAddFilter={addFilter}
        onBackToParameters={() => setSelectedParameter(null)}
        theme={theme}
      />

      <RecordsToolbar
        groupByApp={groupByApp}
        onToggleGroupByApp={setGroupByApp}
        canManageApps={canManageApps}
        onOpenAppsDialog={() => setAppsDialogOpen(true)}
        theme={theme}
      />

      <RecordsStatsBar
        stats={stats}
        filteredCount={filteredRecords.length}
        activeFilterCount={activeFilters.length}
      />

      <Box>
        {groupByApp ? (
          <AppGroupsList
            groups={groupedRecords}
            expandedApps={expandedApps}
            onToggleAppGroup={toggleAppGroup}
            renderRecordCard={renderRecordCard}
            theme={theme}
          />
        ) : (
          filteredRecords.map(renderRecordCard)
        )}

        {filteredRecords.length === 0 && (
          <Paper sx={{ p: 4, textAlign: 'center', backgroundColor: 'background.paper' }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No records found
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {activeFilters.length > 0
                ? 'Try adjusting your filters or search query'
                : 'Try adding some filters or search for specific records'}
            </Typography>
          </Paper>
        )}
      </Box>

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
        theme={theme}
      />
    </Box>
  );
};

export default RecordsTable;
