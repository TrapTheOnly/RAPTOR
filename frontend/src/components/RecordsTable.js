import React, { useState, useEffect } from 'react';
import axios from 'axios';

// Basic sanitization for demonstration
function sanitizeInput(str) {
  return str.replace(/[^a-zA-Z0-9.\-_ ]+/g, '');
}

const RecordsTable = () => {
  const [records, setRecords] = useState([]);
  const [editRowId, setEditRowId] = useState(null);
  const [formData, setFormData] = useState({}); 

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
      data: record.data
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
      [name]: sanitizeInput(value)
    }));
  };

  const handleSave = async (id) => {
    try {
      // POST to /records/<id> with the new data
      await axios.post(`http://127.0.0.1:5000/records/${id}`, formData);
      // Refresh the table
      await fetchRecords();
      setEditRowId(null);
    } catch (error) {
      console.error('Error updating record:', error);
    }
  };

  return (
    <div>
      <h2>DNS Records</h2>
      <table border="1" cellPadding="5" cellSpacing="0">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>TTL</th>
            <th>Class</th>
            <th>Type</th>
            <th>Data</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => {
            if (editRowId === record.id) {
              // Editable row
              return (
                <tr key={record.id}>
                  <td>{record.id}</td>
                  <td>
                    <input
                      name="name"
                      value={formData.name}
                      onChange={handleChange}
                    />
                  </td>
                  <td>
                    <input
                      name="ttl"
                      type="number"
                      value={formData.ttl}
                      onChange={handleChange}
                    />
                  </td>
                  <td>
                    <input
                      name="record_class"
                      value={formData.record_class}
                      onChange={handleChange}
                    />
                  </td>
                  <td>
                    <input
                      name="record_type"
                      value={formData.record_type}
                      onChange={handleChange}
                    />
                  </td>
                  <td>
                    <input
                      name="data"
                      value={formData.data}
                      onChange={handleChange}
                    />
                  </td>
                  <td>
                    <button onClick={() => handleSave(record.id)}>Save</button>
                    <button onClick={handleCancel}>Cancel</button>
                  </td>
                </tr>
              );
            } else {
              // Read-only row
              return (
                <tr key={record.id}>
                  <td>{record.id}</td>
                  <td>{record.name}</td>
                  <td>{record.ttl}</td>
                  <td>{record.record_class}</td>
                  <td>{record.record_type}</td>
                  <td>{record.data}</td>
                  <td>
                    <button onClick={() => handleEdit(record)}>Edit</button>
                  </td>
                </tr>
              );
            }
          })}
        </tbody>
      </table>
    </div>
  );
};

export default RecordsTable;