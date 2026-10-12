export interface Product {
  sku: string;
  name: string;
  category: string;
  brand: string;
  vehicle_fitment: string;
  price: string;
  stock: number;
  description: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Dealer {
  id: number;
  dealer_code: string;
  name: string;
  city?: string;
  phone?: string;
  email?: string;
  gstin?: string;
  credit_limit?: string;
}

export interface OrderItem {
  sku: string;
  name: string;
  quantity: number;
  unit_price: string;
  line_subtotal: string;
  line_tax: string;
  line_total: string;
}

export interface Order {
  order_number: string;
  dealer_id: number;
  status: string;
  items: OrderItem[];
  subtotal: string;
  tax_total: string;
  grand_total: string;
  created_at: string;
  updated_at: string;
}

export interface ForecastWeek {
  week_start: string;
  forecast_units: number;
}

export interface ReorderSuggestion {
  sku: string;
  current_stock: number;
  lead_time_weeks: number;
  lead_time_demand: number;
  safety_stock: number;
  reorder_point: number;
  reorder_qty: number;
}

export interface AssistantResponse {
  reply: string;
  cited_skus: string[];
  tool_calls: Array<{
    name: string;
    arguments: Record<string, any>;
  }>;
  actions: Array<{
    type: string;
    order_number?: string;
  }>;
  mode?: string;
}

const API_BASE = '/api';

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('dealerdesk_token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Token ${token}`;
  }
  return headers;
}

export interface AuthResponse {
  token: string;
  dealer: Dealer;
  credit_limit?: string;
  outstanding_orders?: string;
  available_credit?: string;
}

export const api = {
  getHealth: async () => {
    const res = await fetch(`${API_BASE}/health/`);
    return res.json();
  },

  loginDealer: async (usernameOrCode: string, password: string): Promise<AuthResponse> => {
    const res = await fetch(`${API_BASE}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: usernameOrCode, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Login failed');
    if (data.token) localStorage.setItem('dealerdesk_token', data.token);
    return data;
  },

  provisionDealer: async (dealerCode: string, verification: { email?: string; gstin?: string }, password: string): Promise<AuthResponse> => {
    const res = await fetch(`${API_BASE}/auth/provision/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dealer_code: dealerCode, ...verification, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Provisioning failed');
    if (data.token) localStorage.setItem('dealerdesk_token', data.token);
    return data;
  },

  resetPassword: async (dealerCode: string, email: string, newPassword: string) => {
    const res = await fetch(`${API_BASE}/auth/reset-password/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dealer_code: dealerCode, email, new_password: newPassword }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Password reset failed');
    if (data.token) localStorage.setItem('dealerdesk_token', data.token);
    return data;
  },

  getMe: async (): Promise<{ authenticated: boolean; dealer: Dealer | null; credit_limit?: string; outstanding_orders?: string; available_credit?: string }> => {
    const token = localStorage.getItem('dealerdesk_token');
    if (!token) return { authenticated: false, dealer: null };
    try {
      const res = await fetch(`${API_BASE}/auth/me/`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        localStorage.removeItem('dealerdesk_token');
        return { authenticated: false, dealer: null };
      }
      return res.json();
    } catch {
      return { authenticated: false, dealer: null };
    }
  },

  logout: async () => {
    try {
      await fetch(`${API_BASE}/auth/logout/`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
    } finally {
      localStorage.removeItem('dealerdesk_token');
    }
  },

  getProducts: async (params?: { search?: string; category?: string; vehicle?: string; page?: number; page_size?: number }): Promise<PaginatedResponse<Product>> => {
    const q = new URLSearchParams();
    if (params?.search) q.set('search', params.search);
    if (params?.category) q.set('category', params.category);
    if (params?.vehicle) q.set('vehicle', params.vehicle);
    if (params?.page) q.set('page', String(params.page));
    if (params?.page_size) q.set('page_size', String(params.page_size));
    const res = await fetch(`${API_BASE}/products/?${q.toString()}`, {
      headers: getAuthHeaders(),
    });
    return res.json();
  },

  updateInventory: async (sku: string, quantity: number, reason: string = 'manual adjustment') => {
    const res = await fetch(`${API_BASE}/inventory/${sku}/`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify({ quantity, reason }),
    });
    if (!res.ok) throw new Error((await res.json())?.error?.message || 'Inventory update failed');
    return res.json();
  },

  getDealers: async (page = 1, pageSize = 50): Promise<PaginatedResponse<Dealer>> => {
    const res = await fetch(`${API_BASE}/dealers/?page=${page}&page_size=${pageSize}`, {
      headers: getAuthHeaders(),
    });
    return res.json();
  },

  getDealerDetail: async (id: number): Promise<Dealer & { available_credit?: string; outstanding_orders?: string }> => {
    const res = await fetch(`${API_BASE}/dealers/${id}/`, {
      headers: getAuthHeaders(),
    });
    return res.json();
  },

  getOrders: async (page = 1, pageSize = 20, dealerId?: number): Promise<PaginatedResponse<Order>> => {
    const q = new URLSearchParams();
    q.set('page', String(page));
    q.set('page_size', String(pageSize));
    if (dealerId) q.set('dealer_id', String(dealerId));
    const res = await fetch(`${API_BASE}/orders/?${q.toString()}`, {
      headers: getAuthHeaders(),
    });
    return res.json();
  },

  createOrder: async (dealerId: number, items: Array<{ sku: string; quantity: number }>) => {
    const res = await fetch(`${API_BASE}/orders/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ dealer_id: dealerId, items }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Failed to create order');
    return data;
  },

  getOrder: async (orderNumber: string): Promise<Order> => {
    const res = await fetch(`${API_BASE}/orders/${orderNumber}/`, {
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Failed to fetch order');
    return data;
  },

  confirmOrder: async (orderNumber: string): Promise<Order> => {
    const res = await fetch(`${API_BASE}/orders/${orderNumber}/confirm/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Failed to confirm order');
    return data;
  },

  cancelOrder: async (orderNumber: string): Promise<Order> => {
    const res = await fetch(`${API_BASE}/orders/${orderNumber}/cancel/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Failed to cancel order');
    return data;
  },

  dispatchOrder: async (orderNumber: string): Promise<Order> => {
    const res = await fetch(`${API_BASE}/orders/${orderNumber}/dispatch/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Failed to dispatch order');
    return data;
  },

  deliverOrder: async (orderNumber: string): Promise<Order> => {
    const res = await fetch(`${API_BASE}/orders/${orderNumber}/deliver/`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Failed to deliver order');
    return data;
  },

  getReorderSuggestions: async (): Promise<{ results: ReorderSuggestion[] }> => {
    const res = await fetch(`${API_BASE}/reorder-suggestions/`, {
      headers: getAuthHeaders(),
    });
    return res.json();
  },

  getForecast: async (sku: string): Promise<{ sku: string; forecast: ForecastWeek[] }> => {
    const res = await fetch(`${API_BASE}/forecast/${sku}/`, {
      headers: getAuthHeaders(),
    });
    return res.json();
  },

  chatAssistant: async (sessionId: string, dealerId: number, message: string): Promise<AssistantResponse> => {
    const res = await fetch(`${API_BASE}/assistant/chat/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ session_id: sessionId, dealer_id: dealerId, message }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error?.message || 'Assistant request failed');
    return data;
  },
};


