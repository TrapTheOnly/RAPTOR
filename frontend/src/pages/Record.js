import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Box, 
  Typography, 
  Paper, 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow, 
  TablePagination, 
  Button, 
  TextField,
  Card,
  CardContent,
  Grid,
  useTheme,
  alpha,
  Chip,
  Stack,
  Divider,
  Alert,
  LinearProgress
} from '@mui/material';
import {
  Computer as ComputerIcon,
  Storage as StorageIcon,
  Person as PersonIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  History as HistoryIcon,
  Domain as DomainIcon,
  Info as InfoIcon,
  CalendarToday as CalendarIcon,
  Update as UpdateIcon,
  ArrowBack as ArrowBackIcon,
  Check as CheckIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { MuiMarkdown } from 'mui-markdown';

const Record = ({ darkMode, userPermissions }) => {
  const [record, setRecord] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { domain, recordId } = useParams();
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [editingDescription, setEditingDescription] = useState(false);
  const [editedDescription, setEditedDescription] = useState('');
  const theme = useTheme();
  const hasPermission = (permission) => (userPermissions || []).includes(permission);
  const canModifyRecords = hasPermission('modify_records');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError('');
      try {
        const endpoint = recordId
          ? `/api/records/${recordId}`
          : `/api/records/${encodeURIComponent(domain)}`;
        const recordResponse = await axios.get(endpoint);
        setRecord(recordResponse.data);
        setEditedDescription(recordResponse.data.description || '');
        const historyResponse = await axios.get(`/api/records/${recordResponse.data.id}/history`);
        setHistory(historyResponse.data);
        if (!recordId && domain && recordResponse.data?.id) {
          navigate(`/records/record/${recordResponse.data.id}`, { replace: true });
        }
      } catch (err) {
        setError('Failed to load record details.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [domain, navigate, recordId]);

  const formatDateTime = (datetime) => 
    !datetime ? 'N/A' : new Intl.DateTimeFormat('en-UK', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    }).format(new Date(datetime));

  const getActionColor = (action) => {
    switch (action) {
      case 'created': return theme.palette.success.main;
      case 'updated': return theme.palette.warning.main;
      case 'deleted': return theme.palette.error.main;
      default: return theme.palette.text.primary;
    }
  };

  const getActionIcon = (action) => {
    switch (action) {
      case 'created': return <CheckIcon sx={{ fontSize: 16 }} />;
      case 'updated': return <UpdateIcon sx={{ fontSize: 16 }} />;
      case 'deleted': return <CloseIcon sx={{ fontSize: 16 }} />;
      default: return <InfoIcon sx={{ fontSize: 16 }} />;
    }
  };

  const getActionChip = (action) => {
    const color = getActionColor(action);
    return (
      <Chip
        icon={getActionIcon(action)}
        label={action}
        size="small"
        sx={{
          backgroundColor: alpha(color, 0.1),
          color: color,
          fontWeight: 500,
          textTransform: 'capitalize'
        }}
      />
    );
  };

  const handleEditDescription = () => { 
    if (!canModifyRecords) return;
    setEditingDescription(true); 
  };

  const handleSaveDescription = async () => {
    if (!canModifyRecords || !record) return;
    try {
      await axios.post(`/api/records/${record.id}`, { ...record, description: editedDescription });
      setRecord((await axios.get(`/api/records/${record.id}`)).data);
      setEditingDescription(false);
    } catch (error) {
      console.error('Error updating description:', error);
      setError('Failed to update description. Please try again.');
    }
  };

  const handleCancelEdit = () => { 
    setEditingDescription(false); 
    setEditedDescription(record?.description || ''); 
  };

  const handleChangePage = (event, newPage) => { 
    setPage(newPage); 
  };

  const handleChangeRowsPerPage = (event) => { 
    setRowsPerPage(parseInt(event.target.value, 10)); 
    setPage(0); 
  };

  const getSourceAvatar = (source) => {
    const colors = {
      'Production': '#f44336',
      'External': '#ff9800',
      'Development': '#4caf50',
      'Testing': '#9c27b0',
      'Other': '#666666'
    };
    
    return (
      <Chip
        label={source}
        sx={{
          backgroundColor: alpha(colors[source] || colors['Other'], 0.1),
          color: colors[source] || colors['Other'],
          fontWeight: 500
        }}
      />
    );
  };

  const getStatusChip = (status) => {
    const configs = {
      'Active': { color: '#4CAF50' },
      'Inactive': { color: '#f44336' },
      'Pending': { color: '#FF9800' }
    };
    
    const config = configs[status] || { color: '#666666' };

    return (
      <Chip
        label={status || 'Unknown'}
        sx={{
          backgroundColor: alpha(config.color, 0.1),
          color: config.color,
          fontWeight: 500
        }}
      />
    );
  };

  if (loading) {
    return (
      <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
        <LinearProgress />
        <Typography variant="h6" sx={{ mt: 2, textAlign: 'center' }}>
          Loading record details...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(-1)}
        >
          Go Back
        </Button>
      </Box>
    );
  }

  if (!record) {
    return (
      <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
        <Alert severity="warning" sx={{ mb: 2 }}>
          Record not found.
        </Alert>
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(-1)}
        >
          Go Back
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Record Details
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Detailed information and history for {record.name}
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(-1)}
          sx={{ 
            borderColor: theme.palette.divider,
            color: 'text.primary',
            '&:hover': {
              borderColor: theme.palette.primary.main,
              backgroundColor: alpha(theme.palette.primary.main, 0.04)
            }
          }}
        >
          Back to Records
        </Button>
      </Box>

      <Grid container spacing={3}>
        {/* Record Information Card */}
        <Grid item xs={12} lg={8}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={3}>
                <DomainIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Record Information
                </Typography>
              </Box>

              <Grid container spacing={3}>
                <Grid item xs={12} sm={6}>
                  <Box sx={{ mb: 2 }}>
                    <Typography 
                      variant="caption" 
                      color="text.secondary"
                      sx={{ 
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        fontWeight: 500,
                        display: 'block',
                        mb: 0.5
                      }}
                    >
                      Domain Name
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <DomainIcon sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                      <Typography variant="h6" sx={{ fontWeight: 500 }}>
                        {record.name}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Box sx={{ mb: 2 }}>
                    <Typography 
                      variant="caption" 
                      color="text.secondary"
                      sx={{ 
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        fontWeight: 500,
                        display: 'block',
                        mb: 0.5
                      }}
                    >
                      IP Address
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <ComputerIcon sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                      <Typography variant="body1" sx={{ fontFamily: 'monospace', fontWeight: 500 }}>
                        {record.ip_address}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Box sx={{ mb: 2 }}>
                    <Typography 
                      variant="caption" 
                      color="text.secondary"
                      sx={{ 
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        fontWeight: 500,
                        display: 'block',
                        mb: 0.5
                      }}
                    >
                      Source
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <StorageIcon sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                      {getSourceAvatar(record.source)}
                    </Box>
                  </Box>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Box sx={{ mb: 2 }}>
                    <Typography 
                      variant="caption" 
                      color="text.secondary"
                      sx={{ 
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        fontWeight: 500,
                        display: 'block',
                        mb: 0.5
                      }}
                    >
                      Status
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <InfoIcon sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                      {getStatusChip(record.status)}
                    </Box>
                  </Box>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Box sx={{ mb: 2 }}>
                    <Typography 
                      variant="caption" 
                      color="text.secondary"
                      sx={{ 
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        fontWeight: 500,
                        display: 'block',
                        mb: 0.5
                      }}
                    >
                      Application Owner
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <PersonIcon sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                      <Typography variant="body1" sx={{ fontWeight: 500 }}>
                        {record.application_owner || 'Not assigned'}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Box sx={{ mb: 2 }}>
                    <Typography 
                      variant="caption" 
                      color="text.secondary"
                      sx={{ 
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        fontWeight: 500,
                        display: 'block',
                        mb: 0.5
                      }}
                    >
                      Maintainer
                    </Typography>
                    <Box display="flex" alignItems="center">
                      <PersonIcon sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                      <Typography variant="body1" sx={{ fontWeight: 500 }}>
                        {record.maintainer || 'Not assigned'}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>

                {record.open_ports && (
                  <Grid item xs={12}>
                    <Box sx={{ mb: 2 }}>
                      <Typography 
                        variant="caption" 
                        color="text.secondary"
                        sx={{ 
                          textTransform: 'uppercase',
                          letterSpacing: 0.5,
                          fontWeight: 500,
                          display: 'block',
                          mb: 0.5
                        }}
                      >
                        Open Ports
                      </Typography>
                      <Box display="flex" alignItems="center" flexWrap="wrap" gap={1}>
                        <ComputerIcon sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                        {record.open_ports.split(',').map((port, index) => (
                          <Chip
                            key={index}
                            label={port.trim()}
                            size="small"
                            sx={{
                              fontFamily: 'monospace',
                              backgroundColor: alpha(theme.palette.info.main, 0.1),
                              color: theme.palette.info.main
                            }}
                          />
                        ))}
                      </Box>
                    </Box>
                  </Grid>
                )}
              </Grid>

              <Divider sx={{ my: 3 }} />

              {/* Description Section */}
              <Box>
                <Typography 
                  variant="caption" 
                  color="text.secondary"
                  sx={{ 
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    fontWeight: 500,
                    display: 'block',
                    mb: 1
                  }}
                >
                  Description
                </Typography>
                
                {editingDescription ? (
                  <Box>
                    <TextField 
                      multiline 
                      fullWidth 
                      value={editedDescription} 
                      onChange={(e) => setEditedDescription(e.target.value)} 
                      variant="outlined" 
                      minRows={4}
                      placeholder="Enter a description for this record..."
                      sx={{ mb: 2 }}
                      disabled={!canModifyRecords}
                    />
                    <Stack direction="row" spacing={1}>
                      <Button 
                        variant="contained" 
                        startIcon={<SaveIcon />}
                        onClick={handleSaveDescription}
                        size="small"
                        disabled={!canModifyRecords}
                      >
                        Save
                      </Button>
                      <Button 
                        variant="outlined" 
                        startIcon={<CancelIcon />}
                        onClick={handleCancelEdit}
                        size="small"
                      >
                        Cancel
                      </Button>
                    </Stack>
                  </Box>
                ) : (
                  <Box>
                    <Paper 
                      sx={{ 
                        p: 2, 
                        backgroundColor: 'background.default',
                        border: `1px solid ${theme.palette.divider}`,
                        mb: 2
                      }}
                    >
                      {record.description ? (
                        <MuiMarkdown>{record.description}</MuiMarkdown>
                      ) : (
                        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                          No description provided.
                        </Typography>
                      )}
                    </Paper>
                    <Button 
                      variant="outlined" 
                      startIcon={<EditIcon />}
                      onClick={handleEditDescription}
                      size="small"
                      disabled={!canModifyRecords}
                    >
                      Edit Description
                    </Button>
                  </Box>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Metadata Card */}
        <Grid item xs={12} lg={4}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={3}>
                <CalendarIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Metadata
                </Typography>
              </Box>

              <Stack spacing={2}>
                <Box>
                  <Typography 
                    variant="caption" 
                    color="text.secondary"
                    sx={{ 
                      textTransform: 'uppercase',
                      letterSpacing: 0.5,
                      fontWeight: 500,
                      display: 'block',
                      mb: 0.5
                    }}
                  >
                    Creation Date
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {formatDateTime(record.creation_date)}
                  </Typography>
                </Box>

                <Box>
                  <Typography 
                    variant="caption" 
                    color="text.secondary"
                    sx={{ 
                      textTransform: 'uppercase',
                      letterSpacing: 0.5,
                      fontWeight: 500,
                      display: 'block',
                      mb: 0.5
                    }}
                  >
                    Last Modified
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {record.last_modification_date ? formatDateTime(record.last_modification_date) : "Never"}
                  </Typography>
                </Box>

                <Box>
                  <Typography 
                    variant="caption" 
                    color="text.secondary"
                    sx={{ 
                      textTransform: 'uppercase',
                      letterSpacing: 0.5,
                      fontWeight: 500,
                      display: 'block',
                      mb: 0.5
                    }}
                  >
                    Record ID
                  </Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 500 }}>
                    {record.id}
                  </Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        {/* Change History */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={3}>
                <HistoryIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Change History
                </Typography>
                <Chip 
                  label={`${history.length} changes`}
                  size="small"
                  sx={{ 
                    ml: 2,
                    backgroundColor: alpha(theme.palette.info.main, 0.1),
                    color: theme.palette.info.main
                  }}
                />
              </Box>
              
              {history.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <HistoryIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    No history found
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    This record has no recorded changes
                  </Typography>
                </Box>
              ) : (
                <>
                  <TableContainer component={Paper} sx={{ backgroundColor: 'background.default' }}>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 600 }}>Timestamp</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>User</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Old IP</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>New IP</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Old Source</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>New Source</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Old Maintainer</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>New Maintainer</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {history.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage).map((historyItem) => (
                          <TableRow 
                            key={historyItem.id}
                            sx={{
                              '&:hover': { 
                                backgroundColor: alpha(getActionColor(historyItem.action), 0.05) 
                              }
                            }}
                          >
                            <TableCell>
                              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                {formatDateTime(historyItem.timestamp)}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                {historyItem.username}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              {getActionChip(historyItem.action)}
                            </TableCell>
                            <TableCell>
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  fontFamily: 'monospace',
                                  color: historyItem.old_ip_address ? 'text.primary' : 'text.secondary'
                                }}
                              >
                                {historyItem.old_ip_address || 'N/A'}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  fontFamily: 'monospace',
                                  color: historyItem.new_ip_address ? 'text.primary' : 'text.secondary'
                                }}
                              >
                                {historyItem.new_ip_address || 'N/A'}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  color: historyItem.old_source ? 'text.primary' : 'text.secondary'
                                }}
                              >
                                {historyItem.old_source || 'N/A'}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  color: historyItem.new_source ? 'text.primary' : 'text.secondary'
                                }}
                              >
                                {historyItem.new_source || 'N/A'}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  color: historyItem.old_maintainer ? 'text.primary' : 'text.secondary'
                                }}
                              >
                                {historyItem.old_maintainer || 'N/A'}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography 
                                variant="body2" 
                                sx={{ 
                                  color: historyItem.new_maintainer ? 'text.primary' : 'text.secondary'
                                }}
                              >
                                {historyItem.new_maintainer || 'N/A'}
                              </Typography>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                  <TablePagination 
                    rowsPerPageOptions={[5, 10, 25]} 
                    component="div" 
                    count={history.length} 
                    rowsPerPage={rowsPerPage} 
                    page={page} 
                    onPageChange={handleChangePage} 
                    onRowsPerPageChange={handleChangeRowsPerPage}
                    sx={{
                      borderTop: `1px solid ${theme.palette.divider}`,
                      backgroundColor: 'background.paper'
                    }}
                  />
                </>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Record;
