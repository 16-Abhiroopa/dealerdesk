import React, { useState, useEffect } from 'react';
import { 
  Layers, 
  Package, 
  Users, 
  ShoppingCart, 
  Bot, 
  TrendingUp, 
  Search, 
  AlertTriangle, 
  ArrowUpRight, 
  Send, 
  RefreshCw, 
  ChevronRight, 
  ShieldCheck, 
  Calendar, 
  Sparkles 
} from 'lucide-react';
import { api, type Product, type Dealer, type Order, type ReorderSuggestion, type AssistantResponse } from './api';

type Tab = 'overview' | 'catalogue' | 'dealers' | 'orders' | 'assistant' | 'forecast';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [systemHealth, setSystemHealth] = useState<'checking' | 'healthy' | 'offline'>('checking');
  
  // Products state
  const [products, setProducts] = useState<Product[]>([]);
  const [productCount, setProductCount] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [vehicleFilter, setVehicleFilter] = useState('');
  const [productsLoading, setProductsLoading] = useState(false);
  const [page, setPage] = useState(1);
  
  // Dealers state
  const [dealers, setDealers] = useState<Dealer[]>([]);
  const [selectedDealerId, setSelectedDealerId] = useState<number>(1);
  
  // Orders state
  const [orders, setOrders] = useState<Order[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  
  // Forecast & Reorder state
  const [reorders, setReorders] = useState<ReorderSuggestion[]>([]);
  const [forecastSku, setForecastSku] = useState<string>('FIL-1016');
  const [skuForecast, setSkuForecast] = useState<Array<{ week_start: string; forecast_units: number }>>([]);
  
  // Inventory Edit State
  const [editingSku, setEditingSku] = useState<string | null>(null);
  const [editQty, setEditQty] = useState<number>(0);
  
  // Assistant Chat State
  const [sessionId] = useState<string>(() => `sess-${Math.random().toString(36).substring(2, 9)}`);
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string; toolCalls?: any[]; citedSkus?: string[]; actions?: any[] }>>([
    {
      role: 'assistant',
      text: 'Hello! I am your AI DealerDesk assistant. You can ask me for parts, check real-time stock, or draft orders for your dealership.',
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Initial Data Load
  useEffect(() => {
    checkHealth();
    loadDealers();
    loadProducts();
    loadReorders();
    loadOrders();
  }, []);

  useEffect(() => {
    loadProducts();
  }, [searchQuery, categoryFilter, vehicleFilter, page]);

  useEffect(() => {
    if (forecastSku) {
      loadSkuForecast(forecastSku);
    }
  }, [forecastSku]);

  const checkHealth = async () => {
    try {
      const res = await api.getHealth();
      if (res?.status === 'ok') setSystemHealth('healthy');
      else setSystemHealth('offline');
    } catch {
      setSystemHealth('offline');
    }
  };

  const loadDealers = async () => {
    try {
      const res = await api.getDealers();
      setDealers(res.results || []);
      if (res.results?.length) setSelectedDealerId(res.results[0].id);
    } catch (err) {
      console.error(err);
    }
  };

  const loadProducts = async () => {
    setProductsLoading(true);
    try {
      const res = await api.getProducts({
        search: searchQuery,
        category: categoryFilter,
        vehicle: vehicleFilter,
        page,
        page_size: 15,
      });
      setProducts(res.results || []);
      setProductCount(res.count || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setProductsLoading(false);
    }
  };

  const loadOrders = async () => {
    setOrdersLoading(true);
    try {
      const res = await api.getOrders();
      setOrders(res.results || []);
    } catch (err) {
      console.error(err);
    } finally {
      setOrdersLoading(false);
    }
  };

  const loadReorders = async () => {
    try {
      const res = await api.getReorderSuggestions();
      setReorders(res.results || []);
    } catch (err) {
      console.error(err);
    }
  };

  const loadSkuForecast = async (sku: string) => {
    try {
      const res = await api.getForecast(sku);
      setSkuForecast(res.forecast || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdateStock = async () => {
    if (!editingSku) return;
    try {
      await api.updateInventory(editingSku, editQty, 'Manual dashboard update');
      setEditingSku(null);
      loadProducts();
      loadReorders();
    } catch (err: any) {
      alert(err.message || 'Failed to update stock');
    }
  };

  const handleSendChat = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setChatLoading(true);

    try {
      const resp: AssistantResponse = await api.chatAssistant(sessionId, selectedDealerId, userMsg);
      setChatMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: resp.reply,
          toolCalls: resp.tool_calls,
          citedSkus: resp.cited_skus,
          actions: resp.actions,
        }
      ]);
      // If order was created, reload orders
      if (resp.actions?.some(a => a.type === 'draft_order_created')) {
        loadOrders();
      }
    } catch (err: any) {
      setChatMessages(prev => [
        ...prev,
        { role: 'assistant', text: `Error: ${err.message || 'Assistant request failed'}` }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const categories = [
    'Brakes', 'Engine & Oils', 'Filters', 'Drivetrain', 
    'Lighting & Electrical', 'Controls & Grips', 'Body & Styling', 'Tyres & Tubes'
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-dark)' }}>
      {/* SIDEBAR NAVIGATION */}
      <aside style={{
        width: 260,
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-color)',
        display: 'flex',
        flexDirection: 'column',
        padding: '24px 16px',
        position: 'sticky',
        top: 0,
        height: '100vh',
        zIndex: 50
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingBottom: 24, borderBottom: '1px solid var(--border-color)' }}>
          <div style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(99, 102, 241, 0.4)'
          }}>
            <Package size={22} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.1rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#fff' }}>VIKMO</h1>
            <p style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 600, letterSpacing: '0.05em' }}>DEALERDESK AI</p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 24, flex: 1 }}>
          {[
            { id: 'overview', label: 'Overview', icon: Layers },
            { id: 'catalogue', label: 'Parts Catalogue', icon: Package, badge: productCount ? `${productCount}` : undefined },
            { id: 'dealers', label: 'Dealers & Stock', icon: Users },
            { id: 'orders', label: 'Draft Orders', icon: ShoppingCart },
            { id: 'assistant', label: 'AI Assistant', icon: Bot, highlight: true },
            { id: 'forecast', label: 'Demand Forecast', icon: TrendingUp },
          ].map(item => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id as Tab)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '12px 14px',
                  borderRadius: 10,
                  border: 'none',
                  background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                  color: isActive ? '#fff' : 'var(--text-muted)',
                  cursor: 'pointer',
                  fontWeight: isActive ? 600 : 500,
                  fontSize: '0.9rem',
                  transition: 'all 0.15s ease',
                  textAlign: 'left',
                  borderLeft: isActive ? '3px solid var(--primary)' : '3px solid transparent'
                }}
              >
                <Icon size={18} color={isActive ? 'var(--primary)' : 'currentColor'} />
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.highlight && (
                  <span className="badge badge-indigo" style={{ fontSize: '0.65rem' }}>AI</span>
                )}
                {item.badge && (
                  <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: 12 }}>{item.badge}</span>
                )}
              </button>
            );
          })}
        </nav>

        {/* System Health Status */}
        <div className="glass-panel" style={{ padding: 12, borderRadius: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: systemHealth === 'healthy' ? '#10b981' : '#f43f5e',
              boxShadow: systemHealth === 'healthy' ? '0 0 8px #10b981' : '0 0 8px #f43f5e'
            }} />
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>PostgreSQL API: {systemHealth.toUpperCase()}</span>
          </div>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: 4 }}>REST endpoints operational</p>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main style={{ flex: 1, padding: '32px 40px', overflowY: 'auto' }}>
        {/* Top Header Bar */}
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
          <div>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff' }}>
              {activeTab === 'overview' && 'Executive Commerce Overview'}
              {activeTab === 'catalogue' && 'Vehicle Parts Catalogue & Live Inventory'}
              {activeTab === 'dealers' && 'Verified Dealer Network & Stock Control'}
              {activeTab === 'orders' && 'B2B Draft Orders & Line-by-Line Tax'}
              {activeTab === 'assistant' && 'Grounded AI Assistant & Tool Execution'}
              {activeTab === 'forecast' && 'ML Demand Forecasting & Safety Stock'}
            </h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: 4 }}>
              Distributor Platform for South India Motorcycle & Automotive Spares
            </p>
          </div>

          {/* Active Dealer Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>Active Session Dealer:</span>
            <select
              value={selectedDealerId}
              onChange={e => setSelectedDealerId(Number(e.target.value))}
              className="input-field"
              style={{ padding: '8px 12px', fontSize: '0.85rem', minWidth: 200 }}
            >
              {dealers.map(d => (
                <option key={d.id} value={d.id}>
                  {d.dealer_code} - {d.name} ({d.city || 'BLR'})
                </option>
              ))}
            </select>
          </div>
        </header>

        {/* 1. OVERVIEW DASHBOARD */}
        {activeTab === 'overview' && (
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* KPI Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 18 }}>
              {[
                { title: 'Catalogue Products', value: productCount || '600', note: 'Seeded in catalogue.csv', icon: Package, color: 'var(--primary)' },
                { title: 'Dealer Network', value: dealers.length || '25', note: 'Verified South India partners', icon: Users, color: 'var(--accent-cyan)' },
                { title: 'Total Draft Orders', value: orders.length || '0', note: 'Zero-deduction drafts', icon: ShoppingCart, color: 'var(--accent-emerald)' },
                { title: 'ML Forecast Items', value: reorders.length || '40', note: 'Lead time & sigma safety stock', icon: TrendingUp, color: 'var(--accent-amber)' },
              ].map((kpi, idx) => {
                const Icon = kpi.icon;
                return (
                  <div key={idx} className="glass-panel" style={{ padding: 20 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>{kpi.title}</span>
                      <Icon size={18} color={kpi.color} />
                    </div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff', margin: '12px 0 4px' }}>
                      {kpi.value}
                    </div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{kpi.note}</span>
                  </div>
                );
              })}
            </div>

            {/* Critical Stock Alerts & Quick AI Order */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 24 }}>
              {/* Critical Stock Shortages */}
              <div className="glass-panel" style={{ padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <AlertTriangle size={20} color="var(--accent-amber)" />
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Priority Reorder Recommendations</h3>
                  </div>
                  <button onClick={() => setActiveTab('forecast')} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                    View All 40 SKUs <ArrowUpRight size={14} />
                  </button>
                </div>

                <table className="modern-table">
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Current Stock</th>
                      <th>Reorder Point</th>
                      <th>Suggested Qty</th>
                      <th>Lead Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reorders.slice(0, 5).map(r => (
                      <tr key={r.sku}>
                        <td className="font-mono" style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{r.sku}</td>
                        <td>
                          <span className={`badge ${r.current_stock < r.reorder_point ? 'badge-rose' : 'badge-emerald'}`}>
                            {r.current_stock} units
                          </span>
                        </td>
                        <td>{r.reorder_point}</td>
                        <td style={{ fontWeight: 700, color: r.reorder_qty > 0 ? 'var(--accent-amber)' : 'var(--text-muted)' }}>
                          {r.reorder_qty}
                        </td>
                        <td>{r.lead_time_weeks} wks</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* AI Quick Query Card */}
              <div className="glass-panel" style={{ padding: 24, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <Sparkles size={20} color="var(--primary)" />
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>AI Catalogue Assistant</h3>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    Search parts, check verified live pricing, and draft orders with grounded database tool-calling.
                  </p>

                  <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[
                      'Do you have brake pads for a Pulsar 150?',
                      'Check stock for OIL-1001',
                      'Put 5 units of BRK-1044 aside for me',
                    ].map((prompt, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setActiveTab('assistant');
                          setChatInput(prompt);
                        }}
                        style={{
                          textAlign: 'left',
                          background: 'rgba(255,255,255,0.03)',
                          border: '1px solid var(--border-color)',
                          padding: '10px 14px',
                          borderRadius: 8,
                          color: 'var(--text-main)',
                          fontSize: '0.85rem',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <span>"{prompt}"</span>
                        <ChevronRight size={14} color="var(--text-dim)" />
                      </button>
                    ))}
                  </div>
                </div>

                <button onClick={() => setActiveTab('assistant')} className="btn-primary" style={{ marginTop: 24, width: '100%', justifyContent: 'center' }}>
                  Open AI Ordering Console
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 2. CATALOGUE & STOCK TAB */}
        {activeTab === 'catalogue' && (
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Filters Bar */}
            <div className="glass-panel" style={{ padding: 18, display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ position: 'relative', flex: 1, minWidth: 240 }}>
                <Search size={16} color="var(--text-dim)" style={{ position: 'absolute', left: 14, top: 14 }} />
                <input
                  type="text"
                  placeholder="Search SKU, part name, or brand (e.g. Brake, Mahle, BRK-1044)..."
                  value={searchQuery}
                  onChange={e => { setSearchQuery(e.target.value); setPage(1); }}
                  className="input-field"
                  style={{ width: '100%', paddingLeft: 38 }}
                />
              </div>

              <select
                value={categoryFilter}
                onChange={e => { setCategoryFilter(e.target.value); setPage(1); }}
                className="input-field"
                style={{ minWidth: 160 }}
              >
                <option value="">All Categories</option>
                {categories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>

              <input
                type="text"
                placeholder="Filter Vehicle (e.g. Pulsar, Duke, Thar)..."
                value={vehicleFilter}
                onChange={e => { setVehicleFilter(e.target.value); setPage(1); }}
                className="input-field"
                style={{ minWidth: 180 }}
              />

              <button onClick={() => { setSearchQuery(''); setCategoryFilter(''); setVehicleFilter(''); setPage(1); }} className="btn-secondary">
                Reset
              </button>
            </div>

            {/* Products Table */}
            <div className="glass-panel" style={{ overflow: 'hidden' }}>
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Product Name</th>
                    <th>Category</th>
                    <th>Brand</th>
                    <th>Vehicle Fitment</th>
                    <th>Price (INR)</th>
                    <th>Available Stock</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {productsLoading ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                        <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px' }} />
                        Loading catalogue from PostgreSQL...
                      </td>
                    </tr>
                  ) : products.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                        No products match your search criteria.
                      </td>
                    </tr>
                  ) : (
                    products.map(p => (
                      <tr key={p.sku}>
                        <td className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{p.sku}</td>
                        <td style={{ fontWeight: 600, maxWidth: 220 }}>{p.name}</td>
                        <td><span className="badge badge-indigo">{p.category}</span></td>
                        <td>{p.brand}</td>
                        <td><span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{p.vehicle_fitment}</span></td>
                        <td className="font-mono" style={{ fontWeight: 700 }}>₹{p.price}</td>
                        <td>
                          <span className={`badge ${p.stock > 10 ? 'badge-emerald' : p.stock > 0 ? 'badge-amber' : 'badge-rose'}`}>
                            {p.stock} in stock
                          </span>
                        </td>
                        <td>
                          <button
                            onClick={() => {
                              setEditingSku(p.sku);
                              setEditQty(p.stock);
                            }}
                            className="btn-secondary"
                            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                          >
                            Adjust Stock
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>

              {/* Pagination Bar */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderTop: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
                  Showing {products.length} of {productCount} products
                </span>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    className="btn-secondary"
                    style={{ padding: '6px 14px', opacity: page <= 1 ? 0.4 : 1 }}
                  >
                    Previous
                  </button>
                  <span style={{ display: 'flex', alignItems: 'center', padding: '0 12px', fontSize: '0.85rem', fontWeight: 600 }}>
                    Page {page}
                  </span>
                  <button
                    disabled={products.length < 15}
                    onClick={() => setPage(p => p + 1)}
                    className="btn-secondary"
                    style={{ padding: '6px 14px', opacity: products.length < 15 ? 0.4 : 1 }}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 3. DEALERS & INVENTORY TAB */}
        {activeTab === 'dealers' && (
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div className="glass-panel" style={{ padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Registered Dealer Network (25 South India Partners)</h3>
                <span className="badge badge-emerald">25 Active Verified Dealers</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                {dealers.map(d => (
                  <div
                    key={d.id}
                    onClick={() => setSelectedDealerId(d.id)}
                    style={{
                      background: selectedDealerId === d.id ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255,255,255,0.02)',
                      border: selectedDealerId === d.id ? '1px solid var(--primary)' : '1px solid var(--border-color)',
                      borderRadius: 12,
                      padding: 18,
                      cursor: 'pointer',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{d.dealer_code}</span>
                      <span className="badge badge-indigo">ID: {d.id}</span>
                    </div>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#fff', marginBottom: 6 }}>{d.name}</h4>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>City: {d.city || 'Bengaluru'}</p>
                    <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Credit Limit:</span>
                      <span className="font-mono" style={{ fontWeight: 600, color: 'var(--accent-emerald)' }}>₹{d.credit_limit || '1,00,000'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 4. ORDERS TAB */}
        {activeTab === 'orders' && (
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div className="glass-panel" style={{ padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>B2B Orders with Exact Paisa GST</h3>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>18% GST line-by-line ROUND_HALF_UP exact accounting</p>
                </div>
                <button onClick={() => setActiveTab('assistant')} className="btn-primary">
                  Draft New Order via AI
                </button>
              </div>

              <table className="modern-table">
                <thead>
                  <tr>
                    <th>Order Number</th>
                    <th>Dealer ID</th>
                    <th>Status</th>
                    <th>Items Count</th>
                    <th>Subtotal</th>
                    <th>18% GST</th>
                    <th>Grand Total</th>
                    <th>Created At</th>
                  </tr>
                </thead>
                <tbody>
                  {ordersLoading ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: 30 }}>Loading orders...</td>
                    </tr>
                  ) : orders.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                        No orders recorded yet. Ask the AI Assistant to create a draft order!
                      </td>
                    </tr>
                  ) : (
                    orders.map(o => (
                      <tr key={o.order_number}>
                        <td className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{o.order_number}</td>
                        <td>Dealer #{o.dealer_id}</td>
                        <td>
                          <span className={`badge ${
                            o.status === 'CONFIRMED' ? 'badge-emerald' : 
                            o.status === 'DRAFT' ? 'badge-amber' : 
                            o.status === 'CANCELLED' ? 'badge-rose' : 'badge-indigo'
                          }`}>
                            {o.status}
                          </span>
                        </td>
                        <td>{o.items?.length || 0} line items</td>
                        <td className="font-mono">₹{o.subtotal}</td>
                        <td className="font-mono">₹{o.tax_total}</td>
                        <td className="font-mono" style={{ fontWeight: 700, color: '#fff' }}>₹{o.grand_total}</td>
                        <td style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                          {new Date(o.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 5. AI ASSISTANT CHAT TAB */}
        {activeTab === 'assistant' && (
          <div className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24, height: 'calc(100vh - 160px)' }}>
            {/* Chat Box */}
            <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
              {/* Header */}
              <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Bot size={22} color="var(--primary)" />
                  <div>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 700 }}>DealerDesk Autonomous Ordering Agent</h3>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Session: {sessionId} · Grounded in Live PostgreSQL</p>
                  </div>
                </div>
                <span className="badge badge-emerald">Strict DB Grounding</span>
              </div>

              {/* Message History */}
              <div style={{ flex: 1, padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
                {chatMessages.map((msg, idx) => (
                  <div
                    key={idx}
                    style={{
                      alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      maxWidth: '80%',
                      background: msg.role === 'user' ? 'linear-gradient(135deg, #6366f1, #4f46e5)' : 'rgba(30, 41, 59, 0.7)',
                      border: msg.role === 'user' ? 'none' : '1px solid var(--border-color)',
                      padding: '14px 18px',
                      borderRadius: 16,
                      color: '#fff',
                      fontSize: '0.9rem',
                      lineHeight: 1.5,
                      boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
                    }}
                  >
                    <div>{msg.text}</div>

                    {/* Tool Call & Action Badges */}
                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <span style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>Tools Executed:</span>
                        {msg.toolCalls.map((tc, tidx) => (
                          <div key={tidx} className="font-mono" style={{ fontSize: '0.75rem', background: 'rgba(0,0,0,0.3)', padding: '4px 8px', borderRadius: 6 }}>
                            ⚙️ {tc.name}({JSON.stringify(tc.arguments)})
                          </div>
                        ))}
                      </div>
                    )}

                    {msg.actions && msg.actions.length > 0 && (
                      <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                        {msg.actions.map((act, aidx) => (
                          <span key={aidx} className="badge badge-emerald">
                            ✅ Created {act.order_number}
                          </span>
                        ))}
                      </div>
                    )}

                    {msg.citedSkus && msg.citedSkus.length > 0 && (
                      <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>Cited SKUs:</span>
                        {msg.citedSkus.map(s => (
                          <span key={s} className="badge badge-indigo font-mono">{s}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {chatLoading && (
                  <div style={{ alignSelf: 'flex-start', background: 'rgba(30, 41, 59, 0.7)', padding: '12px 18px', borderRadius: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <RefreshCw size={16} className="animate-spin" color="var(--primary)" />
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Executing catalogue tools & grounding check...</span>
                  </div>
                )}
              </div>

              {/* Chat Input Bar */}
              <form onSubmit={handleSendChat} style={{ padding: 16, borderTop: '1px solid var(--border-color)', display: 'flex', gap: 12 }}>
                <input
                  type="text"
                  placeholder="Ask for parts (e.g. 'Do you have brake pads for a Pulsar 150?', 'Put 5 units aside')..."
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  className="input-field"
                  style={{ flex: 1 }}
                  disabled={chatLoading}
                />
                <button type="submit" disabled={chatLoading} className="btn-primary" style={{ padding: '0 20px' }}>
                  <Send size={16} /> Send
                </button>
              </form>
            </div>

            {/* AI Assistant Safety & Grounding Guardrails Card */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              <div className="glass-panel" style={{ padding: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <ShieldCheck size={20} color="var(--accent-emerald)" />
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Active Safety Defenses</h4>
                </div>
                <ul style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.6, paddingLeft: 18 }}>
                  <li><strong>Zero Hallucination:</strong> Price & stock regex-verified against live DB tool results.</li>
                  <li><strong>Prompt Injection Shield:</strong> Malicious description codes (CHN-1037) neutralized.</li>
                  <li><strong>Order Safety:</strong> Creates DRAFT orders only; confirmation requires explicit manual call.</li>
                  <li><strong>Session Isolation:</strong> Dealer #{selectedDealerId} state isolated by session ID.</li>
                </ul>
              </div>

              <div className="glass-panel" style={{ padding: 20 }}>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: 10 }}>Quick Prompts</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {[
                    'Do you have brake pads for Pulsar 150?',
                    'Check stock for OIL-1001',
                    'Put 10 units aside for me',
                    'What is the price of FIL-1016?',
                  ].map((p, idx) => (
                    <button
                      key={idx}
                      onClick={() => setChatInput(p)}
                      className="btn-secondary"
                      style={{ fontSize: '0.75rem', textAlign: 'left', padding: '8px 10px' }}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 6. DEMAND FORECAST & REORDER TAB */}
        {activeTab === 'forecast' && (
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* 4-Week Demand Curve Chart Inspector */}
            <div className="glass-panel" style={{ padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>4-Week Demand Forecast Visualizer</h3>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Exported into ml/forecast.csv (160 rows). Accounting for Diwali festival proximity and promotions.
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>Select Forecast SKU:</span>
                  <select
                    value={forecastSku}
                    onChange={e => setForecastSku(e.target.value)}
                    className="input-field"
                    style={{ padding: '8px 12px', fontSize: '0.85rem' }}
                  >
                    {reorders.map(r => <option key={r.sku} value={r.sku}>{r.sku}</option>)}
                  </select>
                </div>
              </div>

              {/* Forecast 4 Weeks Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
                {skuForecast.map((wk, idx) => (
                  <div key={idx} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-dim)', fontSize: '0.8rem', marginBottom: 8 }}>
                      <Calendar size={14} />
                      <span>Week Starting {wk.week_start}</span>
                    </div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>
                      {wk.forecast_units} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>units</span>
                    </div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: 4, display: 'inline-block' }}>
                      Week {idx + 1} Horizon
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Reorder Suggestions Table */}
            <div className="glass-panel" style={{ padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Automated Reorder Suggestions (All 40 SKUs)</h3>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Formula: Safety Stock = ceil(1.65 × σ × √L) · Reorder Point = LTD + SS · Reorder Qty = max(0, ceil(RP − Live Stock))
                  </p>
                </div>
                <span className="badge badge-emerald">40 Forecast SKUs Evaluated</span>
              </div>

              <table className="modern-table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Live Available Stock</th>
                    <th>Lead Time (L)</th>
                    <th>Lead Time Demand</th>
                    <th>Safety Stock (SS)</th>
                    <th>Reorder Point (RP)</th>
                    <th>Suggested Reorder Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {reorders.map(r => (
                    <tr key={r.sku}>
                      <td className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{r.sku}</td>
                      <td>
                        <span className={`badge ${r.current_stock < r.reorder_point ? 'badge-rose' : 'badge-emerald'}`}>
                          {r.current_stock}
                        </span>
                      </td>
                      <td>{r.lead_time_weeks} weeks</td>
                      <td className="font-mono">{r.lead_time_demand}</td>
                      <td className="font-mono">{r.safety_stock}</td>
                      <td className="font-mono" style={{ fontWeight: 700 }}>{r.reorder_point}</td>
                      <td>
                        <span style={{
                          fontWeight: 800,
                          color: r.reorder_qty > 0 ? 'var(--accent-amber)' : 'var(--text-dim)',
                          fontSize: '0.95rem'
                        }}>
                          {r.reorder_qty > 0 ? `+${r.reorder_qty} units` : 'Adequate'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* ADJUST INVENTORY MODAL */}
      {editingSku && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100
        }}>
          <div className="glass-panel" style={{ width: 420, padding: 24, borderRadius: 16 }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: 8 }}>Manual Stock Adjustment</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 20 }}>
              Set available physical stock for <strong style={{ color: 'var(--accent-cyan)' }}>{editingSku}</strong>.
            </p>

            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)', display: 'block', marginBottom: 6 }}>
                New Stock Quantity (Must be integer &ge; 0):
              </label>
              <input
                type="number"
                min="0"
                value={editQty}
                onChange={e => setEditQty(Math.max(0, parseInt(e.target.value) || 0))}
                className="input-field"
                style={{ width: '100%', fontSize: '1.2rem', fontWeight: 700 }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button onClick={() => setEditingSku(null)} className="btn-secondary">
                Cancel
              </button>
              <button onClick={handleUpdateStock} className="btn-primary">
                Save & Update Live Stock
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
