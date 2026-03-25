import apiClient from './axiosConfig';

const CAMPAIGNS_BASE = '/campaigns';

export const campaignApi = {
  /**
   * List all campaigns with filtering and pagination.
   * @param {Object} params - Query parameters (status, campaign_type, search, ordering)
   */
  list(params = {}) {
    return apiClient.get(`${CAMPAIGNS_BASE}/`, { params });
  },

  /**
   * Get detailed campaign information including segments and schedule.
   * @param {string} id - Campaign UUID
   */
  get(id) {
    return apiClient.get(`${CAMPAIGNS_BASE}/${id}/`);
  },

  /**
   * Create a new campaign with segments and optional schedule.
   * @param {Object} data - Campaign configuration
   */
  create(data) {
    return apiClient.post(`${CAMPAIGNS_BASE}/`, data);
  },

  /**
   * Update an existing campaign (only allowed in draft/scheduled state).
   * @param {string} id - Campaign UUID
   * @param {Object} data - Updated campaign data
   */
  update(id, data) {
    return apiClient.put(`${CAMPAIGNS_BASE}/${id}/`, data);
  },

  /**
   * Delete a campaign.
   * @param {string} id - Campaign UUID
   */
  delete(id) {
    return apiClient.delete(`${CAMPAIGNS_BASE}/${id}/`);
  },

  /**
   * Start sending a campaign.
   * @param {string} id - Campaign UUID
   */
  start(id) {
    return apiClient.post(`${CAMPAIGNS_BASE}/${id}/start/`);
  },

  /**
   * Pause a sending campaign.
   * @param {string} id - Campaign UUID
   */
  pause(id) {
    return apiClient.post(`${CAMPAIGNS_BASE}/${id}/pause/`);
  },

  /**
   * Resume a paused campaign.
   * @param {string} id - Campaign UUID
   */
  resume(id) {
    return apiClient.post(`${CAMPAIGNS_BASE}/${id}/resume/`);
  },

  /**
   * Cancel a campaign.
   * @param {string} id - Campaign UUID
   */
  cancel(id) {
    return apiClient.post(`${CAMPAIGNS_BASE}/${id}/cancel/`);
  },

  /**
   * Get delivery results for a campaign with optional status filtering.
   * @param {string} id - Campaign UUID
   * @param {Object} params - Query parameters (status, page)
   */
  getResults(id, params = {}) {
    return apiClient.get(`${CAMPAIGNS_BASE}/${id}/results/`, { params });
  },

  /**
   * Get aggregated statistics for a campaign.
   * @param {string} id - Campaign UUID
   */
  getStats(id) {
    return apiClient.get(`${CAMPAIGNS_BASE}/${id}/stats/`);
  },

  /**
   * Duplicate a campaign.
   * @param {string} id - Campaign UUID
   * @param {Object} data - Optional new name
   */
  duplicate(id, data = {}) {
    return apiClient.post(`${CAMPAIGNS_BASE}/${id}/duplicate/`, data);
  },
};

export default campaignApi;
