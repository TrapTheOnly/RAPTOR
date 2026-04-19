import axios from 'axios';

export const fetchNotifications = () => axios.get('/notifications');

export const fetchNotificationCount = () => axios.get('/notifications/count');

export const dismissNotification = (id) => axios.delete(`/notifications/${id}`);

export const dismissAllNotifications = () => axios.delete('/notifications');
