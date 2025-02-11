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
  ThemeProvider,
  createTheme,
  CssBaseline,
  TablePagination,
  Button,
  TextField
} from '@mui/material';
import { MuiMarkdown } from 'mui-markdown';


const Record = ({ darkMode }) => {
  const [record, setRecord] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { domain } = useParams();
  const navigate = useNavigate();
  const [page, setPage] = useState(0); 
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [editingDescription, setEditingDescription] = useState(false);
  const [editedDescription, setEditedDescription] = useState('');

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
    const fetchRecordDetails = async () => {
      setLoading(true);
      setError('');
      try {
        const recordResponse = await axios.get(`/records/${domain}`);
        setRecord(recordResponse.data);
        setEditedDescription(recordResponse.data.description || '');

        const historyResponse = await axios.get(`/records/${recordResponse.data.id}/history`);
        setHistory(historyResponse.data);
      } catch (err) {
        setError('Failed to load record details.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchRecordDetails();

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
  }, [domain, navigate]);

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
    
    const getActionColor = (action) => {
        switch (action) {
            case 'created':
                return 'success.main';
            case 'updated':
                return 'warning.main';
            case 'deleted':
                return 'error.main';
            default:
                return 'text.primary';
        }
    };

  const handleEditDescription = () => {
    setEditingDescription(true);
  };

  const handleSaveDescription = async () => {
    try {
      await axios.post(`/records/${record.id}`, {
        ...record,
        description: editedDescription,
      });
      const recordResponse = await axios.get(`/records/${domain}`);
        setRecord(recordResponse.data);
        setEditingDescription(false);
    } catch (error) {
      console.error('Error updating description:', error);
      setError('Failed to update description.  Please try again.');
    }
  };

  const handleCancelEdit = () => {
    setEditingDescription(false);
    setEditedDescription(record.description || '');
  };

    const handleChangePage = (event, newPage) => {
      setPage(newPage);
    };

    const handleChangeRowsPerPage = (event) => {
      setRowsPerPage(parseInt(event.target.value, 10));
      setPage(0);
    };


  if (loading) {
    return <Box p={2}>Loading...</Box>;
  }

  if (error) {
    return <Box p={2}><Typography color="error">{error}</Typography></Box>;
  }

  if (!record) {
    return <Box p={2}><Typography>Record not found.</Typography></Box>;
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
        padding="2rem"
        bgcolor={theme.palette.background.default}
      >
        <Paper elevation={3} style={{ padding: '2rem', width: '900px', maxWidth: '95%' }}>
          <Typography variant="h4" align="center" gutterBottom>
            Record Details: {record.name}
          </Typography>

          <Box mb={3}>
            <Typography variant="h6">Record Information</Typography>
            <Box>
                <Typography><strong>Name:</strong> {record.name}</Typography>
                <Typography><strong>IP Address:</strong> {record.ip_address}</Typography>
                <Typography><strong>Source:</strong> {record.source}</Typography>
                <Typography><strong>Application Owner:</strong> {record.application_owner || 'N/A'}</Typography>
                <Typography><strong>Maintainer:</strong> {record.maintainer || 'N/A'}</Typography>
                
                <Typography gutterBottom><strong>Description:</strong></Typography>
                {editingDescription ? (
                <Box>
                    <TextField
                    multiline
                    fullWidth
                    value={editedDescription}
                    onChange={(e) => setEditedDescription(e.target.value)}
                    variant="outlined"
                    minRows={4}
                    />
                    <Box mt={1}>
                        <Button variant="contained" color="primary" onClick={handleSaveDescription} style={{ marginRight: '8px' }}>
                        Save
                        </Button>
                        <Button variant="outlined" color="secondary" onClick={handleCancelEdit}>
                        Cancel
                        </Button>
                    </Box>
                </Box>
                ) : (
                <Box>
                    <MuiMarkdown>{record.description || '_No description provided._'}</MuiMarkdown><br></br>
                    <Button variant="outlined" color="primary" onClick={handleEditDescription} sx={{ marginTop: 2 }}>
                    Edit Description
                    </Button>
                </Box>
                )}
              <br></br>
                <Typography><strong>Status:</strong> {record.status}</Typography>
                <Typography><strong>Creation Date:</strong> {formatDateTime(record.creation_date)}</Typography>
                <Typography><strong>Last Modification Date:</strong> {record.last_modification_date ? formatDateTime(record.last_modification_date) : "Never"}</Typography>
            </Box>
          </Box>

          <Box>
            <Typography variant="h6" gutterBottom>
              Change History
            </Typography>
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Timestamp</TableCell>
                    <TableCell>User</TableCell>
                    <TableCell>Action</TableCell>
                    <TableCell>Old IP Address</TableCell>
                    <TableCell>New IP Address</TableCell>
                    <TableCell>Old Source</TableCell>
                    <TableCell>New Source</TableCell>
                    <TableCell>Old Maintainer</TableCell>
                    <TableCell>New Maintainer</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {history
                    .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                    .map((historyItem) => (
                    <TableRow key={historyItem.history_id}>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{formatDateTime(historyItem.timestamp)}</TableCell>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{historyItem.username}</TableCell>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{historyItem.action}</TableCell>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{historyItem.old_ip_address || 'N/M'}</TableCell>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{historyItem.new_ip_address || 'N/M'}</TableCell>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{historyItem.old_source || 'N/M'}</TableCell>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{historyItem.new_source || 'N/M'}</TableCell>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{historyItem.old_maintainer || 'N/M'}</TableCell>
                      <TableCell sx={{ color: getActionColor(historyItem.action) }}>{historyItem.new_maintainer || 'N/M'}</TableCell>
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
            />
          </Box>
        </Paper>
      </Box>
    </ThemeProvider>
  );
};

export default Record;