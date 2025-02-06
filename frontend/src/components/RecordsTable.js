import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Box,
  CssBaseline,
  ThemeProvider,
  createTheme,
  Typography,
  Button,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import UpdateIcon from '@mui/icons-material/Update';
import WarningIcon from '@mui/icons-material/Warning';
import Papa from 'papaparse'; // For CSV export
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward'; // Import icons
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';


function sanitizeInput(str) {
  return str.replace(/[^a-zA-Z0-9.\-_ ]+/g, '');
}

const columnOrder = [
  'name',
  'ip_address',
  'source',
  'application_owner',
  'maintainer',
  'status',
  'creation_date',
  'last_modification_date',
];

const RecordsTable = ({ userRole, darkMode }) => {
  const [records, setRecords] = useState([]);
  const [editRowId, setEditRowId] = useState(null);
  const [formData, setFormData] = useState({});
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [sourceColors, setSourceColors] = useState(new Map());
  const isAdmin = userRole === 'admin';
  let navigate = useNavigate();

  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: darkMode ? '#90caf9' : '#1976d2',
      },
      secondary: {
        main: darkMode ? '#f48fb1' : '#d81b60',
      },
    },
  });

  const generateColor = (index, isDark) => {
    const hue = (index * 137.5) % 360;
    const saturation = isDark ? '60%' : '75%';
    const lightness = isDark ? '35%' : '85%';
    return `hsl(${hue}, ${saturation}, ${lightness})`;
  };

  useEffect(() => {
    fetchRecords();
  }, []);

  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await axios.get('/session-status');
        if (response.status !== 200) {
          navigate('/login');
        }
      } catch (error) {
        console.error("Session expired:", error);
        navigate('/login');
      }
    };

    checkSession();

    const interval = setInterval(checkSession, 1 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status, darkMode) => {
    const iconColor = darkMode ? '#90caf9' : '#1976d2';
    switch (status) {
      case 'unchanged':
        return <CheckCircleIcon style={{ color: iconColor }} />;
      case 'updated':
        return <UpdateIcon style={{ color: iconColor }} />;
      case 'missing':
        return <WarningIcon style={{ color: iconColor }} />;
      default:
        return null;
    }
  };

  const formatDateTime = (datetime) => {
    if (!datetime) return 'N/A';
    return new Intl.DateTimeFormat('en-UK', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(new Date(datetime));
  };

 const fetchRecords = async () => {
    try {
      const response = await axios.get(`/records`);
      let fetchedRecords = response.data; 

      if (sortConfig.key !== null) {
        fetchedRecords = [...fetchedRecords].sort((a, b) => {
          let aValue = a[sortConfig.key];
          let bValue = b[sortConfig.key];

          if (sortConfig.key === 'creation_date' || sortConfig.key === 'last_modification_date') {
            aValue = new Date(aValue);
            bValue = new Date(bValue);
          }

          if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
          if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
          return 0;
        });
      }

      setRecords(fetchedRecords);

    } catch (error) {
      console.error('Error fetching records:', error);
    }
  };

  const handleEdit = (record) => {
    setEditRowId(record.id);
    setFormData({
      name: record.name,
      ip_address: record.ip_address,
      source: record.source,
      application_owner: record.application_owner,
      maintainer: record.maintainer,
      description: record.description
    });
  };

  const handleCancel = () => {
    setEditRowId(null);
    setFormData({});
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: sanitizeInput(value),
    }));
  };

  const handleSave = async (id) => {
    try {
      await axios.post(`/records/${id}`, formData);
      await fetchRecords();
      setEditRowId(null);
      setFormData({});
    } catch (error) {
      console.error('Error updating record:', error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`/records/${id}`);
      await fetchRecords();
    } catch (error) {
      console.error('Error deleting record:', error);
    }
  };

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  
    const sortedRecords = [...records].sort((a, b) => {
      let aValue = a[key];
      let bValue = b[key];

      if (key === 'creation_date' || key === 'last_modification_date') {
        aValue = new Date(aValue);
        bValue = new Date(bValue);
      }
  
      if (aValue < bValue) return direction === 'asc' ? -1 : 1;
      if (aValue > bValue) return direction === 'asc' ? 1 : -1;
      return 0;
    });
    setRecords(sortedRecords);
  };

  const handleExportCSV = () => {
    const reorderedRecords = records.map(record => {
      const newRecord = {};
      columnOrder.forEach(key => {
        newRecord[key] = record[key] === undefined ? '' : record[key];
      });
      return newRecord;
    });
  
  
    const csv = Papa.unparse(reorderedRecords);
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

  const getRowColor = (source) => {
    if (source === 'Other') {
      return {}
    }

    if (!sourceColors.has(source)) {
      const newColors = new Map(sourceColors);
      newColors.set(source, generateColor(sourceColors.size, darkMode));
      setSourceColors(newColors);
    }

    return {
      backgroundColor: sourceColors.get(source),
    };
  };

  useEffect(() => {
    const newColors = new Map();
    records
      .map((record) => record.source)
      .sort()
      .forEach((source, index) => {
        if (!newColors.has(source)) {
          newColors.set(source, generateColor(index, darkMode));
        }
      });
    setSourceColors(newColors);
  }, [records, darkMode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box p={2}>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={2}
        >
          <Typography variant="h6" component="h1">
            DNS Records
          </Typography>
          <Box display="flex" alignItems="center">
            <Button
              variant="contained"
              color="primary"
              startIcon={<DownloadIcon />}
              onClick={handleExportCSV}
              sx={{ marginRight: 4 }}
            >
              Export CSV
            </Button>
          </Box>
        </Box>
        <TableContainer component={Paper}>
          <Table>
           <TableHead>
              <TableRow>
                <TableCell onClick={() => handleSort('name')} sx={{ cursor: 'pointer',  verticalAlign: 'middle' }} >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span>Name</span> {
                      sortConfig.key === 'name' ? 
                        sortConfig.direction === 'asc' ? 
                          <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> : 
                          <ArrowDownwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> :
                        <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#1C1C1C' : '#fff' }} />
                      }
                  </Box>
                </TableCell>
                <TableCell onClick={() => handleSort('ip_address')} sx={{ cursor: 'pointer',  verticalAlign: 'middle' }} >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span>IP Address</span> {
                      sortConfig.key === 'ip_address' ? 
                        sortConfig.direction === 'asc' ? 
                          <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> : 
                          <ArrowDownwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> :
                        <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#1C1C1C' : '#fff' }} />
                      }
                  </Box>
                </TableCell>
                <TableCell onClick={() => handleSort('source')} sx={{ cursor: 'pointer',  verticalAlign: 'middle' }} >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span>Source</span> {
                      sortConfig.key === 'source' ? 
                        sortConfig.direction === 'asc' ? 
                          <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> : 
                          <ArrowDownwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> :
                        <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#1C1C1C' : '#fff' }} />
                      }
                  </Box>
                </TableCell>
                <TableCell onClick={() => handleSort('application_owner')} sx={{ cursor: 'pointer',  verticalAlign: 'middle' }} >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span>Application Owner</span> {
                      sortConfig.key === 'application_owner' ? 
                        sortConfig.direction === 'asc' ? 
                          <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> : 
                          <ArrowDownwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> :
                        <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#1C1C1C' : '#fff' }} />
                      }
                  </Box>
                </TableCell>
                <TableCell onClick={() => handleSort('maintainer')} sx={{ cursor: 'pointer',  verticalAlign: 'middle' }} >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span>Maintainer</span> {
                      sortConfig.key === 'maintainer' ? 
                        sortConfig.direction === 'asc' ? 
                          <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> : 
                          <ArrowDownwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> :
                        <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#1C1C1C' : '#fff' }} />
                      }
                  </Box>
                </TableCell>
                <TableCell onClick={() => handleSort('status')} sx={{ cursor: 'pointer',  verticalAlign: 'middle' }} >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span>Status</span> {
                      sortConfig.key === 'status' ? 
                        sortConfig.direction === 'asc' ? 
                          <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> : 
                          <ArrowDownwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> :
                        <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#1C1C1C' : '#fff' }} />
                      }
                  </Box>
                </TableCell>
                <TableCell onClick={() => handleSort('creation_date')} sx={{ cursor: 'pointer',  verticalAlign: 'middle' }} >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span>Creation Date</span> {
                      sortConfig.key === 'creation_date' ? 
                        sortConfig.direction === 'asc' ? 
                          <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> : 
                          <ArrowDownwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> :
                        <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#1C1C1C' : '#fff' }} />
                      }
                  </Box>
                </TableCell>
                <TableCell onClick={() => handleSort('last_modification_date')} sx={{ cursor: 'pointer',  verticalAlign: 'middle' }} >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span>Last Modified Date</span> {
                      sortConfig.key === 'last_modification_date' ? 
                        sortConfig.direction === 'asc' ? 
                          <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> : 
                          <ArrowDownwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#fff' : '#000' }} /> :
                        <ArrowUpwardIcon sx={{ fontSize: '1rem', color: theme.palette.mode === 'dark' ? '#1C1C1C' : '#fff' }} />
                      }
                  </Box>
                </TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {records.map((record) => (
                <TableRow key={record.name} style={getRowColor(record.source)}>
                  {editRowId === record.id ? (
                    <>
                      <TableCell>{record.name}</TableCell>
                      <TableCell>{record.ip_address}</TableCell>
                      <TableCell>{record.source}</TableCell>
                      <TableCell>
                        <input
                          name="application_owner"
                          value={formData.application_owner || ''}
                          onChange={handleChange}
                        />
                      </TableCell>
                      <TableCell>
                        <input
                          name="maintainer"
                          value={formData.maintainer || ''}
                          onChange={handleChange}
                        />
                      </TableCell>
                      <TableCell>{getStatusIcon(record.status, darkMode)}</TableCell>
                      <TableCell>{formatDateTime(record.creation_date)}</TableCell>
                      <TableCell>
                        {record.last_modification_date
                          ? formatDateTime(record.last_modification_date)
                          : 'Never'}
                      </TableCell>
                      <TableCell>
                        <IconButton onClick={() => handleSave(record.id)}>
                          <SaveIcon color="primary" />
                        </IconButton>
                        <IconButton onClick={handleCancel}>
                          <CancelIcon color="secondary" />
                        </IconButton>
                      </TableCell>
                    </>
                  ) : (
                    <>
                      {/* Display Mode */}
                      <TableCell>
                        <Button
                            color="primary"
                            onClick={() => navigate(`/records/${record.name}`)}
                            style={{textTransform: 'none'}}
                        >
                            {record.name}
                        </Button>
                      </TableCell>
                      <TableCell>{record.ip_address}</TableCell>
                      <TableCell>{record.source}</TableCell>
                      <TableCell>{record.application_owner || 'N/A'}</TableCell>
                      <TableCell>{record.maintainer || 'N/A'}</TableCell>
                      <TableCell>{getStatusIcon(record.status, darkMode)}</TableCell>
                      <TableCell>{formatDateTime(record.creation_date)}</TableCell>
                      <TableCell>
                        {record.last_modification_date
                          ? formatDateTime(record.last_modification_date)
                          : 'Never'}
                      </TableCell>
                      <TableCell>
                        <IconButton onClick={() => handleEdit(record)}>
                          <EditIcon color="primary" />
                        </IconButton>
                        {isAdmin ? (
                          <IconButton onClick={() => handleDelete(record.id)}>
                            <DeleteIcon color="error" />
                          </IconButton>
                        ) : (
                          <></>
                        )}
                      </TableCell>
                    </>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </ThemeProvider>
  );
};

export default RecordsTable;