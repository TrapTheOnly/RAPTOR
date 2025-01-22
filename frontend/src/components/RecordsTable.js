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
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';

// Basic sanitization for demonstration
function sanitizeInput(str) {
  return str.replace(/[^a-zA-Z0-9.\-_ ]+/g, '');
}

const RecordsTable = () => {
  const [records, setRecords] = useState([]);
  const [editRowId, setEditRowId] = useState(null);
  const [formData, setFormData] = useState({});
  const [darkMode, setDarkMode] = useState(false);

  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: darkMode ? '#90caf9' : '#1976d2', // Light blue in dark mode, blue in light mode
      },
      secondary: {
        main: darkMode ? '#f48fb1' : '#d81b60', // Pink in dark mode, dark pink in light mode
      },
    },
  });

  useEffect(() => {
    fetchRecords();
  }, []);

  const fetchRecords = async () => {
    try {
      const response = await axios.get('http://127.0.0.1:5000/records');
      setRecords(response.data);
    } catch (error) {
      console.error('Error fetching records:', error);
    }
  };

  const handleEdit = (record) => {
    setEditRowId(record.id);
    setFormData({
      name: record.name,
      ttl: record.ttl,
      record_class: record.record_class,
      record_type: record.record_type,
      data: record.data,
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
      await axios.post(`http://127.0.0.1:5000/records/${id}`, formData);
      await fetchRecords();
      setEditRowId(null);
    } catch (error) {
      console.error('Error updating record:', error);
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
                <TableCell>ID</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>TTL</TableCell>
                <TableCell>Class</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Data</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {records.map((record) => (
                <TableRow key={record.id}>
                  {editRowId === record.id ? (
                    <>
                      <TableCell>{record.id}</TableCell>
                      <TableCell>
                        <input
                          name="name"
                          value={formData.name}
                          onChange={handleChange}
                        />
                      </TableCell>
                      <TableCell>
                        <input
                          name="ttl"
                          type="number"
                          value={formData.ttl}
                          onChange={handleChange}
                        />
                      </TableCell>
                      <TableCell>
                        <input
                          name="record_class"
                          value={formData.record_class}
                          onChange={handleChange}
                        />
                      </TableCell>
                      <TableCell>
                        <input
                          name="record_type"
                          value={formData.record_type}
                          onChange={handleChange}
                        />
                      </TableCell>
                      <TableCell>
                        <input
                          name="data"
                          value={formData.data}
                          onChange={handleChange}
                        />
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
                      <TableCell>{record.id}</TableCell>
                      <TableCell>{record.name}</TableCell>
                      <TableCell>{record.ttl}</TableCell>
                      <TableCell>{record.record_class}</TableCell>
                      <TableCell>{record.record_type}</TableCell>
                      <TableCell>{record.data}</TableCell>
                      <TableCell>
                        <IconButton onClick={() => handleEdit(record)}>
                          <EditIcon color="primary" />
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