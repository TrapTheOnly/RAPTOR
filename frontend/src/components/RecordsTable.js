import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Switch,
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
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import UpdateIcon from '@mui/icons-material/Update';
import WarningIcon from '@mui/icons-material/Warning';
import Papa from 'papaparse'; // For CSV export

function sanitizeInput(str) {
  return str.replace(/[^a-zA-Z0-9.\-_ ]+/g, '');
}

const RecordsTable = () => {
  const storedTheme = localStorage.getItem('theme') || 'light';
  const [records, setRecords] = useState([]);
  const [editRowId, setEditRowId] = useState(null);
  const [formData, setFormData] = useState({});
  const [darkMode, setDarkMode] = useState(storedTheme === 'dark');
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

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

  useEffect(() => {
    fetchRecords();
  }, []);

  useEffect(() => {
    // Save theme preference to local storage whenever it changes
    localStorage.setItem('theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

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
    if (!datetime) return 'N/A'; // Handle cases where last_modification_date is null
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
      setRecords(response.data);
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
  
      // Convert to Date objects if sorting by creation_date or last_modification_date
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
    const csv = Papa.unparse(records);
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
    switch (source) {
      case 'WAF':
        return { backgroundColor: !darkMode ? '#ffcccb' : '#803232' }; // Light red
      case 'Nginx':
        return { backgroundColor: !darkMode ? '#ccffcc' : '#328032' }; // Light green
      case 'Cloud':
        return { backgroundColor: !darkMode ? '#ccccff' : '#323280'}; // Light blue
      default:
        return {};
    }
  };

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
          <Typography variant="h4" component="h1">
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
            <LightModeIcon />
            <Switch
              checked={darkMode}
              onChange={() => setDarkMode(!darkMode)}
            />
            <DarkModeIcon />
          </Box>
        </Box>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell onClick={() => handleSort('name')}>Name</TableCell>
                <TableCell onClick={() => handleSort('ip_address')}>IP Address</TableCell>
                <TableCell onClick={() => handleSort('source')}>Source</TableCell>
                <TableCell onClick={() => handleSort('status')}>Status</TableCell>
                <TableCell onClick={() => handleSort('creation_date')}>Creation Date</TableCell>
                <TableCell onClick={() => handleSort('last_modification_date')}>Last Modified Date</TableCell>                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
                {records.map((record) => (
                    <TableRow
                    key={record.name}
                    style={getRowColor(record.source)}
                    >
                    {editRowId === record.id ? (
                        <>
                        {/* Editable Fields */}
                        <TableCell>
                            <input
                            name="name"
                            value={formData.name}
                            onChange={handleChange}
                            />
                        </TableCell>
                        <TableCell>
                            <input
                            name="ip_address"
                            value={formData.ip_address}
                            onChange={handleChange}
                            />
                        </TableCell>
                        <TableCell>
                            <input
                            name="source"
                            value={formData.source}
                            onChange={handleChange}
                            />
                        </TableCell>

                        {/* Non-Editable Fields */}
                        <TableCell>{getStatusIcon(record.status, darkMode)}</TableCell>
                        <TableCell>{formatDateTime(record.creation_date)}</TableCell>
                        <TableCell>{record.last_modification_date ? formatDateTime(record.last_modification_date) : "Never"}</TableCell>

                        {/* Action Buttons */}
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
                        <TableCell>{record.name}</TableCell>
                        <TableCell>{record.ip_address}</TableCell>
                        <TableCell>{record.source}</TableCell>
                        <TableCell>{getStatusIcon(record.status, darkMode)}</TableCell>
                        <TableCell>{formatDateTime(record.creation_date)}</TableCell>
                        <TableCell>{record.last_modification_date ? formatDateTime(record.last_modification_date) : "Never"}</TableCell>
                        <TableCell>
                            <IconButton onClick={() => handleEdit(record)}>
                            <EditIcon color="primary" />
                            </IconButton>
                            <IconButton onClick={() => handleDelete(record.id)}>
                            <DeleteIcon color="error" />
                            </IconButton>
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