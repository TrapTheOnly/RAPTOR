import React, { useState, useEffect, useCallback } from 'react';
import {
  Badge,
  Box,
  Button,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Popover,
  Tooltip,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';
import {
  NotificationsOutlined,
  PersonAdd,
  PersonRemove,
  BugReport,
  SyncProblem,
  CloudDone,
  CloudOff,
  Close,
  ClearAll,
} from '@mui/icons-material';
import {
  fetchNotifications,
  fetchNotificationCount,
  dismissNotification,
  dismissAllNotifications,
} from '../services/notifications';

const NOTIFICATION_ICONS = {
  collaborator_added: PersonAdd,
  collaborator_removed: PersonRemove,
  finding_added: BugReport,
  sync_conflict: SyncProblem,
  zone_sync_success: CloudDone,
  zone_sync_failure: CloudOff,
};

const NOTIFICATION_COLORS = {
  collaborator_added: '#4CAF50',
  collaborator_removed: '#FF9800',
  finding_added: '#F44336',
  sync_conflict: '#FF9800',
  zone_sync_success: '#4CAF50',
  zone_sync_failure: '#F44336',
};

function timeAgo(dateString) {
  const now = new Date();
  const date = new Date(dateString);
  const seconds = Math.floor((now - date) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const NotificationBell = ({ username }) => {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [count, setCount] = useState(0);

  const pollCount = useCallback(async () => {
    if (!username) return;
    try {
      const res = await fetchNotificationCount();
      setCount(res.data.count || 0);
    } catch {
      // silent
    }
  }, [username]);

  useEffect(() => {
    pollCount();
    const interval = setInterval(pollCount, 30000);
    return () => clearInterval(interval);
  }, [pollCount]);

  const handleOpen = async (event) => {
    setAnchorEl(event.currentTarget);
    try {
      const res = await fetchNotifications();
      setNotifications(res.data.notifications || []);
      setCount(res.data.count || 0);
    } catch {
      // silent
    }
  };

  const handleClose = () => setAnchorEl(null);

  const handleDismiss = async (id) => {
    try {
      await dismissNotification(id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      setCount((prev) => Math.max(0, prev - 1));
    } catch {
      // silent
    }
  };

  const handleDismissAll = async () => {
    try {
      await dismissAllNotifications();
      setNotifications([]);
      setCount(0);
    } catch {
      // silent
    }
  };

  const open = Boolean(anchorEl);

  return (
    <>
      <Tooltip title="Notifications">
        <IconButton
          onClick={handleOpen}
          sx={{
            color: theme.palette.text.secondary,
            '&:hover': {
              color: theme.palette.text.primary,
              backgroundColor: alpha(theme.palette.text.primary, 0.05),
            },
          }}
        >
          <Badge
            badgeContent={count}
            color="error"
            max={99}
            sx={{
              '& .MuiBadge-badge': {
                fontSize: '0.7rem',
                minWidth: 18,
                height: 18,
              },
            }}
          >
            <NotificationsOutlined />
          </Badge>
        </IconButton>
      </Tooltip>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        PaperProps={{
          sx: {
            width: 380,
            maxHeight: 480,
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 2,
          },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            px: 2,
            py: 1.5,
          }}
        >
          <Typography variant="subtitle1" fontWeight={600}>
            Notifications
          </Typography>
          {notifications.length > 0 && (
            <Button
              size="small"
              startIcon={<ClearAll />}
              onClick={handleDismissAll}
              sx={{ textTransform: 'none', fontSize: '0.8rem' }}
            >
              Clear all
            </Button>
          )}
        </Box>
        <Divider />

        {notifications.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <NotificationsOutlined
              sx={{ fontSize: 40, color: theme.palette.text.disabled, mb: 1 }}
            />
            <Typography variant="body2" color="text.secondary">
              No notifications
            </Typography>
          </Box>
        ) : (
          <List disablePadding sx={{ overflow: 'auto', maxHeight: 380 }}>
            {notifications.map((notification, index) => {
              const IconComp = NOTIFICATION_ICONS[notification.type] || NotificationsOutlined;
              const iconColor = NOTIFICATION_COLORS[notification.type] || theme.palette.text.secondary;

              return (
                <React.Fragment key={notification.id}>
                  {index > 0 && <Divider />}
                  <ListItem
                    sx={{
                      py: 1.5,
                      px: 2,
                      alignItems: 'flex-start',
                      '&:hover': {
                        backgroundColor: alpha(theme.palette.text.primary, 0.03),
                      },
                    }}
                    secondaryAction={
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => handleDismiss(notification.id)}
                        sx={{ color: theme.palette.text.disabled }}
                      >
                        <Close fontSize="small" />
                      </IconButton>
                    }
                  >
                    <ListItemIcon sx={{ minWidth: 36, mt: 0.5 }}>
                      <IconComp sx={{ color: iconColor, fontSize: 22 }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Typography variant="body2" fontWeight={500} sx={{ pr: 3 }}>
                          {notification.title}
                        </Typography>
                      }
                      secondary={
                        <Box>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ display: 'block', lineHeight: 1.4, mt: 0.25 }}
                          >
                            {notification.message}
                          </Typography>
                          <Typography
                            variant="caption"
                            color="text.disabled"
                            sx={{ display: 'block', mt: 0.5, fontSize: '0.7rem' }}
                          >
                            {timeAgo(notification.created_at)}
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                </React.Fragment>
              );
            })}
          </List>
        )}
      </Popover>
    </>
  );
};

export default NotificationBell;
