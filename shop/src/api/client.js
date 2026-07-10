const BASE = '/api/v1'

async function http(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail
    try {
      const body = await res.json()
      detail = body.detail?.message || body.detail || `Request failed (${res.status})`
    } catch {
      detail = `Request failed (${res.status})`
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Shop
  getProducts: (category) =>
    http(`/shop/products${category ? `?category=${category}` : ''}`),
  getCategories: () => http('/shop/categories'),
  checkout: (payload) =>
    http('/shop/checkout', { method: 'POST', body: JSON.stringify(payload) }),
  getCustomerOrders: (customerId) =>
    http(`/shop/customers/${customerId}/orders`),

  // Orders + returns (existing ReturnShieldAI logic)
  getOrder: (orderId) => http(`/orders/${orderId}`),
  getOrderReturns: (orderId) => http(`/orders/${orderId}/returns`),
  getEligibility: (orderId) => http(`/orders/${orderId}/return-eligibility`),
  getReturnableItems: (orderId) => http(`/orders/${orderId}/returnable-items`),
  createReturn: (orderId, payload, headers = {}) =>
    http(`/orders/${orderId}/returns`, { method: 'POST', body: JSON.stringify(payload), headers }),
  getReturnDetail: (returnId) => http(`/returns/${returnId}`),
  compareImage: (orderId, image_data_url, filename, mime_type) =>
    http(`/orders/${orderId}/return-image-compare`, {
      method: 'POST',
      body: JSON.stringify({ image_data_url, filename, mime_type }),
    }),
}
