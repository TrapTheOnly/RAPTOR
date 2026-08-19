const previews = new Map();

export const rememberAppPreview = (app) => {
  if (app?.id == null) return;
  previews.set(String(app.id), app);
};

export const rememberAppPreviews = (apps = []) => {
  apps.forEach(rememberAppPreview);
};

export const peekAppPreview = (id) => previews.get(String(id)) || null;
