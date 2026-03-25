import apiClient from './axiosConfig';

const CHANNELS_BASE = '/channels';

export const channelApi = {
  /**
   * List all channels for the current organization.
   * @param {Object} params - Query parameters (channel_type, is_active, search, ordering)
   */
  list(params = {}) {
    return apiClient.get(`${CHANNELS_BASE}/`, { params });
  },

  /**
   * Get detailed configuration for a specific channel.
   * @param {string} id - Channel UUID
   */
  get(id) {
    return apiClient.get(`${CHANNELS_BASE}/${id}/`);
  },

  /**
   * Create a new channel with its type-specific configuration.
   * @param {Object} data - Channel data including type-specific config (email_config, sms_config, etc.)
   */
  create(data) {
    return apiClient.post(`${CHANNELS_BASE}/`, data);
  },

  /**
   * Update an existing channel.
   * @param {string} id - Channel UUID
   * @param {Object} data - Updated channel data
   */
  update(id, data) {
    return apiClient.put(`${CHANNELS_BASE}/${id}/`, data);
  },

  /**
   * Partially update a channel.
   * @param {string} id - Channel UUID
   * @param {Object} data - Partial update fields
   */
  patch(id, data) {
    return apiClient.patch(`${CHANNELS_BASE}/${id}/`, data);
  },

  /**
   * Delete a channel.
   * @param {string} id - Channel UUID
   */
  delete(id) {
    return apiClient.delete(`${CHANNELS_BASE}/${id}/`);
  },

  /**
   * Send a test notification through a channel.
   * @param {string} id - Channel UUID
   * @param {Object} data - Test parameters { test_recipient, test_message }
   */
  test(id, data) {
    return apiClient.post(`${CHANNELS_BASE}/${id}/test/`, data);
  },

  /**
   * Toggle a channel's active state.
   * @param {string} id - Channel UUID
   */
  toggle(id) {
    return apiClient.post(`${CHANNELS_BASE}/${id}/toggle/`);
  },

  /**
   * Set a channel as the default for its type.
   * @param {string} id - Channel UUID
   */
  setDefault(id) {
    return apiClient.post(`${CHANNELS_BASE}/${id}/set_default/`);
  },
};

export default channelApi;
