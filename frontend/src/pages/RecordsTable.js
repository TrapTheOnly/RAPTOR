import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  TextField,
  Typography,
  Card,
  CardContent,
  Chip,
  IconButton,
  Button,
  Collapse,
  Grid,
  InputAdornment,
  Divider,
  Paper,
  LinearProgress,
  useTheme,
  alpha,
  Tooltip,
  Avatar,
  Menu,
  MenuItem,
  Autocomplete,
  Stack
} from '@mui/material';
import {
  Search,
  ExpandMore,
  ExpandLess,
  Edit,
  Save,
  Cancel,
  Delete,
  History,
  Security,
  Computer,
  Warning,
  CheckCircle,
  Update,
  FilterList,
  Download,
  Refresh,
  Add,
  Close,
  ArrowDropDown
} from '@mui/icons-material';
import Papa from 'papaparse';

const RecordsTable = ({ userRole, darkMode }) => {
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
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    updated: 0,
    missing: 0,
    sources: 0
  });

  const navigate = useNavigate();
  const theme = useTheme();
  const isAdmin = userRole === 'admin';

  // Search parameters configuration with aliases
  const searchParameters = [
    { 
      key: 'status', 
      label: 'Status', 
      icon: '📊',
      description: 'Record status (active, updated, missing)',
      aliases: ['state'],
      getValue: (record) => record.status
    },
    { 
      key: 'source', 
      label: 'Source', 
      icon: '🏷️',
      description: 'Data source (Production, External, etc.)',
      aliases: ['src'],
      getValue: (record) => record.source
    },
    { 
      key: 'ip', 
      label: 'IP Address', 
      icon: '🌐',
      description: 'IP address or subnet',
      aliases: ['ip_address', 'ipaddr'],
      getValue: (record) => record.ip_address
    },
    { 
      key: 'owner', 
      label: 'App Owner', 
      icon: '👤',
      description: 'Application owner',
      aliases: ['application_owner', 'app_owner', 'owner'],
      getValue: (record) => record.application_owner
    },
    { 
      key: 'maintainer', 
      label: 'Maintainer', 
      icon: '🔧',
      description: 'System maintainer',
      aliases: ['maint'],
      getValue: (record) => record.maintainer
    },
    { 
      key: 'domain', 
      label: 'Domain Name', 
      icon: '🌍',
      description: 'Domain name contains',
      aliases: ['name', 'hostname', 'dns_name'],
      getValue: (record) => record.name
    },
    { 
      key: 'created', 
      label: 'Created Date', 
      icon: '📅',
      description: 'Creation date (YYYY-MM-DD)',
      aliases: ['creation_date', 'date'],
      getValue: (record) => record.creation_date?.split('T')[0]
    },
    { 
      key: 'ports', 
      label: 'Open Ports', 
      icon: '🔌',
      description: 'Filter by individual port numbers (e.g., 22, 443, 8080)',
      aliases: ['open_ports', 'port'],
      getValue: (record) => record.open_ports
    }
  ];

  useEffect(() => {
    fetchRecords();
  }, []);

  useEffect(() => {
    extractParameterValues();
  }, [records]);

  useEffect(() => {
    applyFilters();
  }, [records, activeFilters, searchQuery]);

  const fetchRecords = async () => {
    setLoading(true);
      try {
        const sessionResponse = await axios.get('/session-status');
        if (sessionResponse.status !== 200) {
          navigate('/login');
          return;
        }
      
        const recordsResponse = await axios.get('/api/records');
      const fetchedRecords = recordsResponse.data.sort((a, b) => 
        new Date(b.last_modification_date || b.creation_date) - new Date(a.last_modification_date || a.creation_date)
      );
      
      setRecords(fetchedRecords);
      calculateStats(fetchedRecords);
      } catch (error) {
      console.error('Error fetching records:', error);
        navigate('/login');
    } finally {
      setLoading(false);
    }
  };

  const extractParameterValues = () => {
    const values = {};
    const counts = {};
    
    searchParameters.forEach(param => {
      if (param.key === 'ports') {
        // Special handling for ports - split comma-separated values into individual ports
        const allPorts = new Set();
        const portCounts = {};
        
        records.forEach(record => {
          const portsValue = param.getValue(record);
          if (portsValue && portsValue.toString().trim() !== '') {
            // Split by comma, trim whitespace, filter empty values, and add to set
            const recordPorts = portsValue.split(',')
              .map(port => port.trim())
              .filter(port => port !== '' && !isNaN(port));
            
            recordPorts.forEach(port => {
              allPorts.add(port);
              portCounts[port] = (portCounts[port] || 0) + 1;
            });
          }
        });
        
        // Convert set to sorted array of unique ports
        values[param.key] = Array.from(allPorts).sort((a, b) => parseInt(a) - parseInt(b));
        counts[param.key] = portCounts;
      } else {
        // Standard handling for other parameters
        const uniqueValues = [...new Set(
          records
            .map(record => param.getValue(record))
            .filter(value => value && value.toString().trim() !== '')
        )].sort();
        
        values[param.key] = uniqueValues;
        
        // Count occurrences for standard parameters
        const valueCounts = {};
        uniqueValues.forEach(value => {
          valueCounts[value] = records.filter(record => 
            param.getValue(record) === value
          ).length;
        });
        counts[param.key] = valueCounts;
      }
    });
    
    setParameterValues(values);
    setParameterCounts(counts);
  };

  // Simple pattern detection
  const analyzeInput = (input) => {
    const trimmed = input.trim();
    
    // Check for field=value pattern
    const completePattern = /^(\w+)\s*=\s*(.+)$/;
    const fieldOnlyPattern = /^(\w+)\s*=\s*$/;
    const partialFieldPattern = /^(\w+)$/;
    
    const completeMatch = trimmed.match(completePattern);
    const fieldOnlyMatch = trimmed.match(fieldOnlyPattern);
    const partialMatch = trimmed.match(partialFieldPattern);
    
    // Find matching parameter
    const findParam = (name) => searchParameters.find(p => 
      p.key === name.toLowerCase() || 
      (p.aliases && p.aliases.includes(name.toLowerCase()))
    );
    
    if (completeMatch) {
      const [, fieldName, value] = completeMatch;
      const param = findParam(fieldName);
      return { 
        type: 'complete', 
        field: param?.key, 
        value: value.trim(),
        hasWildcards: value.includes('*') || value.includes('?')
      };
    }
    
    if (fieldOnlyMatch) {
      const [, fieldName] = fieldOnlyMatch;
      const param = findParam(fieldName);
      return { type: 'field_ready', field: param?.key };
    }
    
    if (partialMatch && findParam(partialMatch[1])) {
      return { type: 'field_partial', field: findParam(partialMatch[1])?.key };
    }
    
    return { type: 'text' };
  };

  // Generate suggestions based on input
  const generateSuggestions = (input) => {
    const analysis = analyzeInput(input);
    
    if (analysis.type === 'field_ready' && analysis.field) {
      // Show values for completed field
      const values = parameterValues[analysis.field] || [];
      return values.map(value => ({
        type: 'value',
        field: analysis.field,
        value,
        display: value,
        count: parameterCounts[analysis.field]?.[value] || 0
      }));
    }
    
    if (analysis.type === 'field_partial' || analysis.type === 'text') {
      // Show field suggestions
      const inputLower = input.toLowerCase();
      const suggestions = [];
      
      searchParameters.forEach(param => {
        // Main field
        if (param.key.includes(inputLower) || param.label.toLowerCase().includes(inputLower)) {
          suggestions.push({
            type: 'field',
            field: param.key,
            display: `${param.key}=`,
            label: param.label,
            icon: param.icon,
            description: param.description
          });
        }
        
        // Aliases
        if (param.aliases) {
          param.aliases.forEach(alias => {
            if (alias.includes(inputLower)) {
              suggestions.push({
                type: 'field',
                field: param.key,
                display: `${alias}=`,
                label: `${param.label} (${alias})`,
                icon: param.icon,
                description: param.description
              });
            }
          });
        }
      });
      
      return suggestions;
    }
    
    return [];
  };

  // Handle input changes
  const handleInputChange = (value) => {
    setSearchInput(value);
    
    if (!value.trim()) {
      setDropdownOpen(false);
      setSuggestions([]);
      return;
    }
    
    const newSuggestions = generateSuggestions(value);
    setSuggestions(newSuggestions);
    setDropdownOpen(newSuggestions.length > 0);
  };

  // Handle suggestion selection
  const selectSuggestion = (suggestion) => {
    if (suggestion.type === 'field') {
      setSearchInput(suggestion.display);
      // Keep dropdown open to show values
      const valueSuggestions = generateSuggestions(suggestion.display);
      setSuggestions(valueSuggestions);
      setDropdownOpen(valueSuggestions.length > 0);
    } else if (suggestion.type === 'value') {
      const fullInput = `${suggestion.field}=${suggestion.value}`;
      submitSearch(fullInput);
    }
  };

  // Submit search
  const submitSearch = (input = searchInput) => {
    const analysis = analyzeInput(input);
    
    if (analysis.type === 'complete' && analysis.field && analysis.value) {
      // Create filter chip
      const param = searchParameters.find(p => p.key === analysis.field);
      if (param) {
        const filterLabel = analysis.hasWildcards ? 
          `${param.label}: ${analysis.value} (wildcard)` :
          `${param.label}: ${analysis.value}`;
        
        const newFilter = { 
          id: Date.now(), 
          parameter: analysis.field, 
          value: analysis.value,
          label: filterLabel,
          hasWildcards: analysis.hasWildcards
        };
        
        setActiveFilters(prev => [...prev, newFilter]);
        setSearchInput('');
        setDropdownOpen(false);
        return;
      }
    }
    
    // Fallback to text search
    setSearchQuery(input);
    if (analysis.type === 'text') {
      setSearchInput(input);
    } else {
      setSearchInput('');
    }
    setDropdownOpen(false);
  };

  const calculateStats = (recordsData) => {
    const uniqueSources = new Set(recordsData.map(r => r.source)).size;
    const stats = {
      total: recordsData.length,
      active: recordsData.filter(r => r.status === 'unchanged').length,
      updated: recordsData.filter(r => r.status === 'updated').length,
      missing: recordsData.filter(r => r.status === 'missing').length,
      sources: uniqueSources
    };
    setStats(stats);
  };

  // Wildcard matching helper function
  const matchesWildcard = (text, pattern) => {
    if (!pattern.includes('*') && !pattern.includes('?')) {
      return text.toLowerCase().includes(pattern.toLowerCase());
    }
    
    // Convert wildcard pattern to regex
    const regexPattern = pattern
      .replace(/[.*+?^${}()|[\]\\]/g, '\\$&') // Escape special regex chars
      .replace(/\\\*/g, '.*') // Convert * to .*
      .replace(/\\\?/g, '.'); // Convert ? to .
    
    const regex = new RegExp(`^${regexPattern}$`, 'i');
    return regex.test(text);
  };

  const applyFilters = () => {
    let filtered = [...records];

    // Apply parameter filters
    activeFilters.forEach(filter => {
      const param = searchParameters.find(p => p.key === filter.parameter);
      if (param) {
        filtered = filtered.filter(record => {
          const value = param.getValue(record);
          if (!value) return false;
          
          switch (filter.parameter) {
            case 'ip':
              return matchesWildcard(value, filter.value);
            case 'domain':
              return matchesWildcard(value, filter.value);
            case 'ports':
              // Match individual ports within comma-separated lists
              if (!value) return false;
              const portList = value.split(',').map(p => p.trim());
              return portList.some(port => matchesWildcard(port, filter.value));
            case 'created':
              return value === filter.value;
            default:
              return matchesWildcard(value, filter.value);
          }
        });
      }
    });

    // Apply free text search if any
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      const hasWildcards = query.includes('*') || query.includes('?');
      
      filtered = filtered.filter(r => {
        const searchFields = [
          r.name,
          r.ip_address,
          r.source,
          r.application_owner,
          r.maintainer,
          r.open_ports
        ];
        
        return searchFields.some(field => {
          if (!field) return false;
          return hasWildcards ? 
            matchesWildcard(field, query) : 
            field.toLowerCase().includes(query);
        });
      });
    }

    setFilteredRecords(filtered);
  };

  const addFilter = (parameter, value) => {
    const newFilter = { 
      id: Date.now(), 
      parameter, 
      value,
      label: `${searchParameters.find(p => p.key === parameter)?.label}: ${value}`
    };
    
    setActiveFilters(prev => [...prev, newFilter]);
    setSearchMenuAnchor(null);
    setSelectedParameter(null);
  };

  const removeFilter = (filterId) => {
    setActiveFilters(prev => prev.filter(f => f.id !== filterId));
  };

  const clearAllFilters = () => {
    setActiveFilters([]);
    setSearchQuery('');
    setSearchInput('');
    setDropdownOpen(false);
  };

  const handleParameterSelect = (parameter) => {
    setSelectedParameter(parameter);
  };

  const toggleExpanded = (recordId) => {
    const newExpanded = new Set(expandedRecords);
    if (newExpanded.has(recordId)) {
      newExpanded.delete(recordId);
    } else {
      newExpanded.add(recordId);
    }
    setExpandedRecords(newExpanded);
  };

  const startEditing = (record) => {
    setEditingRecord(record.id);
    setEditForm({
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
      await axios.post(`/api/records/${recordId}`, editForm);
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
        await axios.delete(`/api/records/${recordId}`);
        fetchRecords();
      } catch (error) {
        console.error('Error deleting record:', error);
      }
    }
  };

  const exportCSV = () => {
    const csv = Papa.unparse(filteredRecords);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'dns_records.csv');
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'unchanged':
        return <CheckCircle sx={{ color: '#4CAF50', fontSize: 16 }} />;
      case 'updated':
        return <Update sx={{ color: '#2196F3', fontSize: 16 }} />;
      case 'missing':
        return <Warning sx={{ color: '#FF9800', fontSize: 16 }} />;
      default:
        return <Computer sx={{ color: theme.palette.text.secondary, fontSize: 16 }} />;
    }
  };

  const getStatusChip = (status) => {
    const configs = {
      unchanged: { label: 'Active', color: '#4CAF50' },
      updated: { label: 'Updated', color: '#2196F3' },
      missing: { label: 'Missing', color: '#FF9800' }
    };
    
    const config = configs[status] || { label: 'Unknown', color: theme.palette.text.secondary };

  return (
      <Chip
        size="small"
        label={config.label}
        sx={{
          backgroundColor: alpha(config.color, 0.1),
          color: config.color,
          fontWeight: 500,
          fontSize: '0.75rem'
        }}
      />
    );
  };

  const formatDateTime = (datetime) => {
    if (!datetime) return 'Never';
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(datetime));
  };

  const getSourceAvatar = (source) => {
    const colors = {
      'Production': '#4CAF50',
      'External': '#2196F3',
      'Development': '#FF9800',
      'Testing': '#9C27B0',
      'Other': '#666666'
    };
    
    return (
      <Avatar
        sx={{
          width: 24,
          height: 24,
          fontSize: '0.75rem',
          backgroundColor: colors[source] || colors['Other'],
          mr: 1
        }}
      >
        {source?.charAt(0) || '?'}
      </Avatar>
    );
  };

  const PortsDisplay = ({ ports, maxVisible = 5 }) => {
    const [showAll, setShowAll] = useState(false);
    
    if (!ports || ports.trim() === '') {
      return (
        <Typography 
          variant="body2" 
          sx={{ 
            fontWeight: 500,
            color: 'text.secondary'
          }}
        >
          None specified
        </Typography>
      );
    }

    const portList = ports.split(',').map(p => p.trim()).filter(p => p !== '');
    const hasMany = portList.length > maxVisible;
    const displayPorts = showAll ? portList : portList.slice(0, maxVisible);

    return (
      <Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: hasMany ? 1 : 0 }}>
          {displayPorts.map((port, index) => (
            <Chip
              key={index}
              label={port}
              size="small"
              sx={{
                height: 20,
                fontSize: '0.7rem',
                fontFamily: 'monospace',
                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                color: theme.palette.primary.main,
                '& .MuiChip-label': {
                  px: 1
                }
              }}
            />
          ))}
          {hasMany && !showAll && (
            <Chip
              label={`+${portList.length - maxVisible} more`}
              size="small"
              variant="outlined"
              clickable
              onClick={() => setShowAll(true)}
              sx={{
                height: 20,
                fontSize: '0.7rem',
                borderColor: theme.palette.text.secondary,
                color: theme.palette.text.secondary,
                '& .MuiChip-label': {
                  px: 1
                }
              }}
            />
          )}
        </Box>
        {hasMany && showAll && (
          <Button
            size="small"
            onClick={() => setShowAll(false)}
            sx={{ 
              minHeight: 'auto',
              p: 0.5,
              fontSize: '0.7rem',
              textTransform: 'none'
            }}
          >
            Show less
          </Button>
        )}
                    </Box>
    );
  };

  if (loading) {
    return (
      <Box p={3}>
        <LinearProgress />
        <Typography variant="h6" sx={{ mt: 2 }}>Loading records...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Records
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Existing internet-facing DNS records
          </Typography>
        </Box>
      </Box>
      {/* Enhanced Search Interface */}
      <Box mb={3}>
        {/* Active Filters */}
        {(activeFilters.length > 0 || searchQuery) && (
          <Box mb={2}>
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <Typography variant="body2" color="text.secondary">
                Active Filters:
              </Typography>
              <Button 
                size="small" 
                onClick={clearAllFilters}
                sx={{ minWidth: 'auto', p: 0.5 }}
              >
                Clear All
              </Button>
            </Box>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {/* Filter Chips */}
              {activeFilters.map((filter) => (
                <Chip
                  key={filter.id}
                  label={filter.label}
                  onDelete={() => removeFilter(filter.id)}
                  size="small"
                  icon={filter.hasWildcards ? <Typography sx={{ fontSize: '0.8em' }}>*</Typography> : undefined}
                  sx={{
                    backgroundColor: filter.hasWildcards ? 
                      alpha(theme.palette.warning.main, 0.1) : 
                      alpha(theme.palette.primary.main, 0.1),
                    color: filter.hasWildcards ? 
                      theme.palette.warning.main : 
                      theme.palette.primary.main,
                    '& .MuiChip-deleteIcon': {
                      color: filter.hasWildcards ? 
                        theme.palette.warning.main : 
                        theme.palette.primary.main,
                    }
                  }}
                />
              ))}
              
              {/* Active Text Search */}
              {searchQuery && (
                <Chip
                  label={`Search: "${searchQuery}"`}
                  onDelete={() => {
                    setSearchQuery('');
                    setSearchInput('');
                  }}
                  size="small"
                  sx={{
                    backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                    color: theme.palette.secondary.main,
                    '& .MuiChip-deleteIcon': {
                      color: theme.palette.secondary.main,
                    }
                  }}
                />
              )}
            </Stack>
          </Box>
        )}

        {/* Search Bar with Custom Dropdown */}
        <Box display="flex" gap={1} position="relative">
          <Box position="relative" width="100%">
            <TextField
              fullWidth
              value={searchInput}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  if (dropdownOpen && suggestions.length > 0) {
                    selectSuggestion(suggestions[0]);
                  } else {
                    submitSearch();
                  }
                } else if (e.key === 'Tab' && dropdownOpen && suggestions.length > 0) {
                  e.preventDefault();
                  selectSuggestion(suggestions[0]);
                } else if (e.key === 'Escape') {
                  setDropdownOpen(false);
                } else if (e.key === 'ArrowDown' && dropdownOpen) {
                  e.preventDefault();
                  // Could add keyboard navigation here
                }
              }}
              placeholder="Type field=value (e.g., source=Prod*) or search text..."
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search color="action" />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <Tooltip title="Export Filtered Results">
                      <IconButton onClick={exportCSV} size="small">
                        <Download />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Refresh">
                      <IconButton onClick={fetchRecords} size="small">
                        <Refresh />
                      </IconButton>
                    </Tooltip>
                  </InputAdornment>
                )
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  backgroundColor: 'background.paper',
                  '& fieldset': {
                    border: `1px solid ${theme.palette.divider}`,
                  },
                }
              }}
            />
            
            {/* Custom Dropdown */}
            {dropdownOpen && suggestions.length > 0 && (
              <Paper
                sx={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  zIndex: 1300,
                  mt: 0.5,
                  maxHeight: 300,
                  overflow: 'auto',
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: 1,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
                }}
              >
                {suggestions.map((suggestion, index) => (
                  <Box
                    key={index}
                    onClick={() => selectSuggestion(suggestion)}
                    sx={{
                      p: 1.5,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      '&:hover': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.08)
                      },
                      borderBottom: index < suggestions.length - 1 ? 
                        `1px solid ${alpha(theme.palette.divider, 0.5)}` : 'none'
                    }}
                  >
                    <Box display="flex" alignItems="center" flex={1}>
                      {suggestion.icon && (
                        <Typography sx={{ fontSize: '1.1em', mr: 1.5 }}>
                          {suggestion.icon}
                        </Typography>
                      )}
                      <Box>
                        <Typography 
                          variant="body2" 
                          sx={{ 
                            fontWeight: 500,
                            fontFamily: suggestion.type === 'value' && 
                              (suggestion.field === 'ip' || suggestion.field === 'ports') ? 
                              'monospace' : 'inherit'
                          }}
                        >
                          {suggestion.display}
                        </Typography>
                        {suggestion.description && (
                          <Typography variant="caption" color="text.secondary">
                            {suggestion.description}
                          </Typography>
                        )}
                        {suggestion.type === 'value' && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            Use * for wildcards (e.g., {suggestion.value}*)
                          </Typography>
                        )}
                      </Box>
                    </Box>
                    {suggestion.count !== undefined && (
                      <Chip 
                        label={suggestion.count}
                        size="small"
                        sx={{ 
                          height: 18,
                          fontSize: '0.65rem',
                          backgroundColor: alpha(theme.palette.primary.main, 0.1),
                          color: theme.palette.primary.main
                        }}
                      />
                    )}
                  </Box>
                ))}
              </Paper>
            )}
          </Box>
          
          <Button
            variant="contained"
            startIcon={<Add />}
            endIcon={<ArrowDropDown />}
            onClick={(e) => setSearchMenuAnchor(e.currentTarget)}
            sx={{ 
              minWidth: 'auto',
              whiteSpace: 'nowrap',
              backgroundColor: 'background.paper',
              color: 'text.primary',
              border: `1px solid ${theme.palette.divider}`,
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.04),
                borderColor: theme.palette.primary.main,
                boxShadow: '0 4px 8px rgba(0,0,0,0.15)',
              },
              '&:active': {
                backgroundColor: alpha(theme.palette.primary.main, 0.08),
              },
              px: 2,
              py: 1,
              fontWeight: 500,
              textTransform: 'none'
            }}
          >
            Add Filter
          </Button>

          {/* Smart Search Help */}
          <Tooltip 
            title={
              <Box>
                <Typography variant="caption" display="block" sx={{ fontWeight: 500 }}>
                  Smart Search Examples:
                </Typography>
                <Typography variant="caption" display="block">
                  • source=Production (or src=Production)
                </Typography>
                <Typography variant="caption" display="block">
                  • open_ports=443 (or port=443)
                </Typography>
                <Typography variant="caption" display="block">
                  • status=updated (or state=updated)
                </Typography>
                <Typography variant="caption" display="block">
                  • owner=john (or app_owner=john)
                </Typography>
                <Typography variant="caption" display="block" sx={{ mt: 1, fontWeight: 500 }}>
                  Wildcards:
                </Typography>
                <Typography variant="caption" display="block">
                  • domain=*.example.com (ends with)
                </Typography>
                <Typography variant="caption" display="block">
                  • source=Prod* (starts with)
                </Typography>
                <Typography variant="caption" display="block">
                  • owner=*john* (contains)
                </Typography>
                <Typography variant="caption" display="block">
                  • port=80? (single character)
                </Typography>
                <Typography variant="caption" display="block" sx={{ mt: 1, fontStyle: 'italic' }}>
                  Or just type any text to search all fields
                </Typography>
                <Typography variant="caption" display="block" sx={{ mt: 1, opacity: 0.7 }}>
                  💡 Press Tab to accept suggestions, Enter to search
                </Typography>
              </Box>
            }
            arrow
            placement="bottom-start"
          >
            <IconButton size="small" sx={{ color: 'text.secondary' }}>
              <Typography variant="caption" sx={{ fontSize: '1.2em' }}>
                💡
              </Typography>
            </IconButton>
          </Tooltip>
        </Box>

        {/* Search Parameters Menu */}
        <Menu
          anchorEl={searchMenuAnchor}
          open={Boolean(searchMenuAnchor)}
          onClose={() => {
            setSearchMenuAnchor(null);
            setSelectedParameter(null);
          }}
          transformOrigin={{ horizontal: 'right', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          PaperProps={{
            elevation: 4,
            sx: {
              maxWidth: 320,
              mt: 0.5,
              backgroundColor: 'background.paper',
              border: `1px solid ${theme.palette.divider}`,
              borderRadius: 1.5,
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              '& .MuiMenuItem-root': {
                py: 1,
                px: 1.5,
                mx: 0.5,
                my: 0.25,
                borderRadius: 0.75,
                fontSize: '0.875rem',
                transition: 'all 0.15s ease-in-out',
                '&:hover': {
                  backgroundColor: alpha(theme.palette.primary.main, 0.06),
                  transform: 'translateX(1px)',
                },
                '&:first-of-type': {
                  mt: 0.5,
                },
                '&:last-of-type': {
                  mb: 0.5,
                }
              },
              '& .MuiList-root': {
                py: 0,
              }
            }
          }}
        >
          {!selectedParameter ? (
            // Show available parameters
            searchParameters.map((param) => (
              <MenuItem
                key={param.key}
                onClick={() => handleParameterSelect(param)}
                sx={{ 
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 1.5,
                  backgroundColor: 'background.default',
                  border: `1px solid ${alpha(theme.palette.divider, 0.3)}`,
                  mb: 0.5,
                  borderRadius: 1,
                  py: 1.25,
                  px: 1.5,
                  fontSize: '0.875rem',
                  '&:hover': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.04),
                    borderColor: alpha(theme.palette.primary.main, 0.2),
                    transform: 'translateX(2px)',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
                  },
                  '&:last-child': {
                    mb: 0
                  }
                }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 32,
                    height: 32,
                    borderRadius: 1,
                    backgroundColor: alpha(theme.palette.primary.main, 0.08),
                    flexShrink: 0
                  }}
                >
                  <Typography sx={{ fontSize: '1.1em' }}>
                    {param.icon}
                  </Typography>
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      fontWeight: 600,
                      color: 'text.primary',
                      mb: 0.25,
                      fontSize: '0.875rem'
                    }}
                  >
                    {param.label}
                  </Typography>
                  <Typography 
                    variant="caption" 
                    sx={{ 
                      color: 'text.secondary',
                      mb: 0.75,
                      lineHeight: 1.3,
                      fontSize: '0.75rem'
                    }}
                  >
                    {param.description}
                  </Typography>
                  <Chip
                    label={`${parameterValues[param.key]?.length || 0} ${param.key === 'ports' ? 'ports' : 'values'}`}
                    size="small"
                    sx={{ 
                      height: 18,
                      fontSize: '0.65rem',
                      backgroundColor: alpha(theme.palette.info.main, 0.08),
                      color: 'info.main',
                      fontWeight: 500,
                      '& .MuiChip-label': {
                        px: 0.75
                      }
                    }}
                  />
                </Box>
              </MenuItem>
            ))
          ) : (
            // Show values for selected parameter
            <>
              <MenuItem 
                onClick={() => setSelectedParameter(null)}
                sx={{ 
                  borderBottom: `1px solid ${theme.palette.divider}`,
                  mb: 0.5,
                  backgroundColor: alpha(theme.palette.secondary.main, 0.04),
                  '&:hover': {
                    backgroundColor: alpha(theme.palette.secondary.main, 0.08),
                    transform: 'translateX(0px)',
                  },
                  mx: 0,
                  px: 1.5,
                  py: 1,
                  borderRadius: '6px 6px 0 0',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      color: 'secondary.main',
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      fontSize: '0.875rem'
                    }}
                  >
                    ← Back to Parameters
                  </Typography>
                </Box>
              </MenuItem>
              <Box sx={{ px: 1.5, pb: 0.75, pt: 0.25 }}>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'text.primary',
                    fontWeight: 600,
                    mb: 0.25,
                    fontSize: '0.875rem'
                  }}
                >
                  {selectedParameter.label} Values ({parameterValues[selectedParameter.key]?.length || 0}):
                </Typography>
                {selectedParameter.key === 'ports' && (
                  <Typography 
                    variant="caption" 
                    sx={{ 
                      color: 'text.secondary',
                      fontStyle: 'italic',
                      fontSize: '0.7rem'
                    }}
                  >
                    Individual ports from all records
                  </Typography>
                )}
              </Box>
              {parameterValues[selectedParameter.key]?.map((value) => (
                <MenuItem
                  key={value}
                  onClick={() => addFilter(selectedParameter.key, value)}
                  sx={{ 
                    ml: 0.5,
                    mr: 0.5,
                    mb: 0.5,
                    borderRadius: 0.75,
                    fontFamily: selectedParameter.key === 'ip' || selectedParameter.key === 'ports' ? 'monospace' : 'inherit',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    backgroundColor: 'background.default',
                    border: `1px solid ${alpha(theme.palette.divider, 0.25)}`,
                    py: 1,
                    px: 1.5,
                    fontSize: '0.875rem',
                    transition: 'all 0.15s ease-in-out',
                    '&:hover': {
                      backgroundColor: alpha(theme.palette.success.main, 0.06),
                      borderColor: alpha(theme.palette.success.main, 0.25),
                      transform: 'translateX(1px)',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
                    },
                    '&:last-child': {
                      mb: 0
                    }
                  }}
                >
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      fontWeight: 500,
                      color: 'text.primary',
                      fontSize: '0.875rem'
                    }}
                  >
                    {value}
                  </Typography>
                  <Chip 
                    label={parameterCounts[selectedParameter.key]?.[value] || 0}
                    size="small"
                    sx={{ 
                      ml: 1,
                      height: 16,
                      fontSize: '0.6rem',
                      backgroundColor: alpha(theme.palette.success.main, 0.08),
                      color: 'success.main',
                      fontWeight: 600,
                      '& .MuiChip-label': {
                        px: 0.5
                      }
                    }}
                  />
                </MenuItem>
              ))}
            </>
          )}
        </Menu>
      </Box>

      {/* Stats Bar */}
      <Paper sx={{ p: 2, mb: 3, backgroundColor: 'background.paper' }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item>
            <Box display="flex" alignItems="center">
              <Computer sx={{ mr: 1, color: 'text.secondary' }} />
              <Typography variant="h6" sx={{ mr: 1 }}>{stats.total}</Typography>
              <Typography variant="body2" color="text.secondary">Total</Typography>
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex" alignItems="center">
              <CheckCircle sx={{ mr: 1, color: '#4CAF50' }} />
              <Typography variant="h6" sx={{ mr: 1 }}>{stats.active}</Typography>
              <Typography variant="body2" color="text.secondary">Active</Typography>
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex" alignItems="center">
              <Update sx={{ mr: 1, color: '#2196F3' }} />
              <Typography variant="h6" sx={{ mr: 1 }}>{stats.updated}</Typography>
              <Typography variant="body2" color="text.secondary">Updated</Typography>
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex" alignItems="center">
              <Warning sx={{ mr: 1, color: '#FF9800' }} />
              <Typography variant="h6" sx={{ mr: 1 }}>{stats.missing}</Typography>
              <Typography variant="body2" color="text.secondary">Issues</Typography>
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex" alignItems="center">
              <FilterList sx={{ mr: 1, color: 'text.secondary' }} />
              <Typography variant="h6" sx={{ mr: 1 }}>{stats.sources}</Typography>
              <Typography variant="body2" color="text.secondary">Sources</Typography>
            </Box>
          </Grid>
          <Grid item xs />
          <Grid item>
            <Typography variant="body2" color="text.secondary">
              Showing {filteredRecords.length} of {stats.total} records
              {activeFilters.length > 0 && (
                <Chip
                  label={`${activeFilters.length} filter${activeFilters.length !== 1 ? 's' : ''}`}
                  size="small"
                  sx={{ ml: 1, height: 20 }}
                />
              )}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Records List */}
      <Box>
        {filteredRecords.map((record) => (
          <Card
            key={record.id}
            sx={{
              mb: 1,
              backgroundColor: 'background.paper',
              border: `1px solid ${theme.palette.divider}`,
              '&:hover': {
                borderColor: theme.palette.primary.main,
                backgroundColor: alpha(theme.palette.primary.main, 0.02)
              },
              transition: 'all 0.2s ease-in-out'
            }}
          >
            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
              {/* Collapsed View */}
              <Box
                display="flex"
                alignItems="center"
                justifyContent="space-between"
                onClick={() => toggleExpanded(record.id)}
                sx={{ cursor: 'pointer' }}
              >
                <Box display="flex" alignItems="center" flex={1}>
                  <IconButton size="small" sx={{ mr: 1 }}>
                    {expandedRecords.has(record.id) ? <ExpandLess /> : <ExpandMore />}
                  </IconButton>
                  
                  <Typography variant="h6" sx={{ mr: 2, fontWeight: 500 }}>
                    {record.name}
                  </Typography>
                  
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mr: 2, fontFamily: 'monospace' }}
                  >
                    {record.ip_address}
                  </Typography>
                  
                  {getStatusChip(record.status)}
                </Box>

                <Box display="flex" alignItems="center">
                  {getSourceAvatar(record.source)}
                  <Typography variant="body2" color="text.secondary" sx={{ mr: 2 }}>
                    {record.source}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Modified {formatDateTime(record.last_modification_date)}
                  </Typography>
                </Box>
              </Box>

              {/* Expanded View */}
              <Collapse in={expandedRecords.has(record.id)}>
                <Box sx={{ mt: 2 }}>
                  <Divider sx={{ mb: 2 }} />
                  
                  <Grid container spacing={3}>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Details
                      </Typography>
                      
                      {editingRecord === record.id ? (
                        <Box>
                          <TextField
                            fullWidth
                            label="Application Owner"
                            value={editForm.application_owner}
                            onChange={(e) => setEditForm({ ...editForm, application_owner: e.target.value })}
                            sx={{ mb: 2 }}
                            size="small"
                          />
                          <TextField
                            fullWidth
                            label="Maintainer"
                            value={editForm.maintainer}
                            onChange={(e) => setEditForm({ ...editForm, maintainer: e.target.value })}
                            sx={{ mb: 2 }}
                            size="small"
                          />
                          <TextField
                            fullWidth
                            label="Open Ports"
                            value={editForm.open_ports}
                            onChange={(e) => setEditForm({ ...editForm, open_ports: e.target.value })}
                            placeholder="22, 80, 443, 8080"
                            size="small"
                            multiline
                            rows={2}
                            helperText="Comma-separated port numbers (e.g., 22, 80, 443)"
                            InputProps={{
                              sx: { fontFamily: 'monospace' }
                            }}
                          />
                        </Box>
                      ) : (
                        <Box>
                          <Box 
                            sx={{ 
                              display: 'grid', 
                              gap: 2, 
                              gridTemplateColumns: 'repeat(2, 1fr)',
                              alignItems: 'start'
                            }}
                          >
                            <Box sx={{ minWidth: 100 }}>
                              <Typography 
                                variant="caption" 
                                color="text.secondary"
                                sx={{ 
                                  textTransform: 'uppercase',
                                  letterSpacing: 0.5,
                                  fontWeight: 500
                                }}
                              >
                                Owner
                              </Typography>
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  fontWeight: 500,
                                  color: record.application_owner ? 'text.primary' : 'text.secondary'
                                }}
                              >
                                {record.application_owner || 'Not assigned'}
                              </Typography>
                            </Box>

                            <Box sx={{ minWidth: 100 }}>
                              <Typography 
                                variant="caption" 
                                color="text.secondary"
                                sx={{ 
                                  textTransform: 'uppercase',
                                  letterSpacing: 0.5,
                                  fontWeight: 500
                                }}
                              >
                                Maintainer
                              </Typography>
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  fontWeight: 500,
                                  color: record.maintainer ? 'text.primary' : 'text.secondary'
                                }}
                              >
                                {record.maintainer || 'Not assigned'}
                              </Typography>
                            </Box>

                            <Box sx={{ minWidth: 100 }}>
                              <Typography 
                                variant="caption" 
                                color="text.secondary"
                                sx={{ 
                                  textTransform: 'uppercase',
                                  letterSpacing: 0.5,
                                  fontWeight: 500
                                }}
                              >
                                Open Ports
                              </Typography>
                              <PortsDisplay ports={record.open_ports} />
                            </Box>

                            <Box sx={{ minWidth: 100 }}>
                              <Typography 
                                variant="caption" 
                                color="text.secondary"
                                sx={{ 
                                  textTransform: 'uppercase',
                                  letterSpacing: 0.5,
                                  fontWeight: 500
                                }}
                              >
                                Created
                              </Typography>
                              <Typography 
                                variant="body2" 
                                sx={{ fontWeight: 500 }}
                              >
                                {formatDateTime(record.creation_date)}
                              </Typography>
                            </Box>

                            <Box sx={{ minWidth: 100 }}>
                              <Typography 
                                variant="caption" 
                                color="text.secondary"
                                sx={{ 
                                  textTransform: 'uppercase',
                                  letterSpacing: 0.5,
                                  fontWeight: 500
                                }}
                              >
                                Status
                              </Typography>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                {getStatusIcon(record.status)}
                                <Typography 
                                  variant="body2" 
                                  sx={{ 
                                    fontWeight: 500,
                                    textTransform: 'capitalize'
                                  }}
                                >
                                  {record.status}
                                </Typography>
                              </Box>
                            </Box>
                          </Box>
                        </Box>
                      )}
                    </Grid>

                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Actions
                      </Typography>
                      
                      <Box display="flex" gap={1} flexWrap="wrap">
                        {editingRecord === record.id ? (
                          <>
                            <Button
                              size="small"
                              variant="contained"
                              startIcon={<Save />}
                              onClick={() => saveRecord(record.id)}
                            >
                              Save
                            </Button>
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<Cancel />}
                              onClick={cancelEditing}
                            >
                              Cancel
                            </Button>
                    </>
                  ) : (
                    <>
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<Edit />}
                              onClick={() => startEditing(record)}
                            >
                              Edit
                            </Button>
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<History />}
                              onClick={() => navigate(`/records/${record.name}`)}
                            >
                              View
                            </Button>
                            {(userRole === 'admin' || userRole === 'pentester') && (
                              <Button
                                size="small"
                                variant="outlined"
                                startIcon={<Security />}
                                onClick={() => navigate(`/pentest/record/${record.id}`)}
                              >
                                Security
                              </Button>
                            )}
                            {isAdmin && (
                              <Button
                                size="small"
                                variant="outlined"
                                color="error"
                                startIcon={<Delete />}
                                onClick={() => deleteRecord(record.id)}
                              >
                                Delete
                              </Button>
                            )}
                    </>
                  )}
                      </Box>
                    </Grid>
                  </Grid>
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        ))}

        {filteredRecords.length === 0 && (
          <Paper sx={{ p: 4, textAlign: 'center', backgroundColor: 'background.paper' }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No records found
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {activeFilters.length > 0 
                ? 'Try adjusting your filters or search query'
                : 'Try adding some filters or search for specific records'
              }
            </Typography>
          </Paper>
        )}
      </Box>
    </Box>
  );
};

export default RecordsTable;