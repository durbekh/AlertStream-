import apiClient from './axiosConfig';

const TEMPLATES_BASE = '/templates';

export const templateApi = {
  /**
   * List all notification templates.
   * @param {Object} params - Query parameters (template_type, category, is_active, search)
   */
  list(params = {}) {
    return apiClient.get(`${TEMPLATES_BASE}/`, { params });
  },

  /**
   * Get a template with its variables and version history.
   * @param {string} id - Template UUID
   */
  get(id) {
    return apiClient.get(`${TEMPLATES_BASE}/${id}/`);
  },

  /**
   * Create a new notification template.
   * @param {Object} data - Template data including variables
   */
  create(data) {
    return apiClient.post(`${TEMPLATES_BASE}/`, data);
  },

  /**
   * Update an existing template (creates a new version if content changed).
   * @param {string} id - Template UUID
   * @param {Object} data - Updated template data
   */
  update(id, data) {
    return apiClient.put(`${TEMPLATES_BASE}/${id}/`, data);
  },

  /**
   * Delete a template.
   * @param {string} id - Template UUID
   */
  delete(id) {
    return apiClient.delete(`${TEMPLATES_BASE}/${id}/`);
  },

  /**
   * Preview a template rendered with context variables.
   * @param {string} id - Template UUID
   * @param {Object} context - Template variable values
   */
  preview(id, context = {}) {
    return apiClient.post(`${TEMPLATES_BASE}/${id}/preview/`, { context });
  },

  /**
   * Get all versions of a template.
   * @param {string} id - Template UUID
   */
  getVersions(id) {
    return apiClient.get(`${TEMPLATES_BASE}/${id}/versions/`);
  },

  /**
   * Publish a specific version of a template.
   * @param {string} id - Template UUID
   * @param {number} versionNumber - Version number to publish
   */
  publishVersion(id, versionNumber) {
    return apiClient.post(`${TEMPLATES_BASE}/${id}/versions/${versionNumber}/publish/`);
  },

  /**
   * Duplicate an existing template.
   * @param {string} id - Template UUID
   * @param {Object} data - Optional new name and slug
   */
  duplicate(id, data = {}) {
    return apiClient.post(`${TEMPLATES_BASE}/${id}/duplicate/`, data);
  },
};

export default templateApi;
