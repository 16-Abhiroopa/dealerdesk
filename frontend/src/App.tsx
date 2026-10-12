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
  Sparkles,
  Plus,
  Minus,
  Trash2,
  CheckCircle2,
  XCircle,
  Eye,
  Truck,
  Check,
  X,
  UserCheck
} from 'lucide-react';
import { 
  api, 
  type Product, 
  type Dealer, 
  type Order, 
  type ReorderSuggestion, 
  type AssistantResponse 
} from './api';

type Tab = 'overview' | 'catalogue' | 'dealers' | 'orders' | 'assistant' | 'forecast';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [systemHealth, setSystemHealth] = useState<'checking' | 'healthy' | 'offline'>('checking');
  const [staffMode, setStaffMode] = useState<boolean>(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  
  // Products state
  const [products, setProducts] = useState<Product[]>([]);
  const [productCount, setProductCount] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [vehicleFilter, setVehicleFilter] = useState('');
  const [productsLoading, setProductsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [addQuantities, setAddQuantities] = useState<Record<string, number>>({});
  
  // Interactive Cart / Draft Order Creator
  const [cart, setCart] = useState<Array<{ product: Product; quantity: number }>>([]);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  
  // Dealers state
  const [dealers, setDealers] = useState<Dealer[]>([]);
  const [selectedDealerId, setSelectedDealerId] = useState<number>(1);
  
  // Orders state
  const [orders, setOrders] = useState<Order[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [orderFilterStatus, setOrderFilterStatus] = useState<string>('ALL');
  const [expandedOrderNumber, setExpandedOrderNumber] = useState<string | null>(null);
  const [orderActionLoading, setOrderActionLoading] = useState<Record<string, boolean>>({});
  
  // Forecast & Reorder state
  const [reorders, setReorders] = useState<ReorderSuggestion[]>([]);
  const [forecastSku, setForecastSku] = useState<string>('FIL-1016');
  const [skuForecast, setSkuForecast] = useState<Array<{ week_start: string; forecast_units: number }>>([]);
  
  // Inventory Edit State (Staff Mode)
  const [editingSku, setEditingSku] = useState<string | null>(null);
  const [editQty, setEditQty] = useState<number>(0);
  
  // Assistant Chat State
  const [sessionId] = useState<string>(() => `sess-${Math.random().toString(36).substring(2, 9)}`);
  const [assistantMode, setAssistantMode] = useState<string>('rule_based');
  const [chatMessages, setChatMessages] = useState<Array<{ 
    role: 'user' | 'assistant'; 
    text: string; 
    toolCalls?: any[]; 
    citedSkus?: string[]; 
    actions?: any[];
    mode?: string;
  }>>([
    {
      role: 'assistant',
      text: 'Hello! I am your DealerDesk Assistant (operating in tokenless local rule-based mode). I can search parts, check real-time stock and prices, verify order status, and prepare draft orders from live PostgreSQL data.',
      mode: 'rule_based'
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

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => {
      setNotification(prev => (prev?.message === message ? null : prev));
    }, 5000);
  };

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
      if (res.results?.length && !selectedDealerId) {
        setSelectedDealerId(res.results[0].id);
      }
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
      const res = await api.getOrders(1, 50);
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

  // Cart Management
  const getSelectedQty = (sku: string) => addQuantities[sku] || 1;
  const setSelectedQty = (sku: string, qty: number) => {
    const val = Math.max(1, qty);
    setAddQuantities(prev => ({ ...prev, [sku]: val }));
  };

  const handleAddToCart = (product: Product) => {
    if (product.stock <= 0) {
      showNotification('error', `Cannot order ${product.name}: Out of stock.`);
      return;
    }
    const desiredQty = getSelectedQty(product.sku);
    if (desiredQty > product.stock) {
      showNotification('error', `Requested ${desiredQty} units exceeds available stock of ${product.stock}.`);
      return;
    }

    setCart(prev => {
      const existing = prev.find(item => item.product.sku === product.sku);
      if (existing) {
        const newQty = Math.min(product.stock, existing.quantity + desiredQty);
        return prev.map(item => item.product.sku === product.sku ? { ...item, quantity: newQty } : item);
      }
      return [...prev, { product, quantity: desiredQty }];
    });

    showNotification('success', `Added ${desiredQty}x ${product.name} to draft order.`);
  };

  const handleUpdateCartQty = (sku: string, delta: number) => {
    setCart(prev => prev.map(item => {
      if (item.product.sku === sku) {
        const newQty = Math.max(1, Math.min(item.product.stock, item.quantity + delta));
        return { ...item, quantity: newQty };
      }
      return item;
    }));
  };

  const handleRemoveFromCart = (sku: string) => {
    setCart(prev => prev.filter(item => item.product.sku !== sku));
  };

  const cartSubtotal = cart.reduce((sum, item) => sum + (parseFloat(item.product.price) * item.quantity), 0);
  const cartTax = cartSubtotal * 0.18;
  const cartGrandTotal = cartSubtotal + cartTax;

  const handleCreateDraftOrder = async () => {
    if (cart.length === 0) return;
    setIsSubmittingOrder(true);
    try {
      const itemsPayload = cart.map(item => ({ sku: item.product.sku, quantity: item.quantity }));
      const order = await api.createOrder(selectedDealerId, itemsPayload);
      showNotification('success', `Draft order ${order.order_number} created successfully! Grand Total: ₹${order.grand_total}`);
      setCart([]);
      await loadOrders();
      setActiveTab('orders');
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to create draft order');
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  // Order Lifecycle Actions
  const handleConfirmOrder = async (orderNumber: string) => {
    setOrderActionLoading(prev => ({ ...prev, [orderNumber]: true }));
    try {
      const confirmed = await api.confirmOrder(orderNumber);
      showNotification('success', `Order ${confirmed.order_number} CONFIRMED! Stock deducted atomically in PostgreSQL.`);
      await Promise.all([loadOrders(), loadProducts(), loadReorders()]);
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to confirm order: Insufficient stock');
    } finally {
      setOrderActionLoading(prev => ({ ...prev, [orderNumber]: false }));
    }
  };

  const handleCancelOrder = async (orderNumber: string) => {
    if (!confirm(`Are you sure you want to cancel order ${orderNumber}? If confirmed, stock will be restored automatically.`)) return;
    setOrderActionLoading(prev => ({ ...prev, [orderNumber]: true }));
    try {
      const cancelled = await api.cancelOrder(orderNumber);
      showNotification('success', `Order ${cancelled.order_number} CANCELLED. Inventory stock restored.`);
      await Promise.all([loadOrders(), loadProducts(), loadReorders()]);
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to cancel order');
    } finally {
      setOrderActionLoading(prev => ({ ...prev, [orderNumber]: false }));
    }
  };

  const handleDispatchOrder = async (orderNumber: string) => {
    setOrderActionLoading(prev => ({ ...prev, [orderNumber]: true }));
    try {
      const dispatched = await api.dispatchOrder(orderNumber);
      showNotification('success', `Order ${dispatched.order_number} marked as DISPATCHED.`);
      await loadOrders();
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to dispatch order');
    } finally {
      setOrderActionLoading(prev => ({ ...prev, [orderNumber]: false }));
    }
  };

  const handleDeliverOrder = async (orderNumber: string) => {
    setOrderActionLoading(prev => ({ ...prev, [orderNumber]: true }));
    try {
      const delivered = await api.deliverOrder(orderNumber);
      showNotification('success', `Order ${delivered.order_number} marked as DELIVERED.`);
      await loadOrders();
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to deliver order');
    } finally {
      setOrderActionLoading(prev => ({ ...prev, [orderNumber]: false }));
    }
  };

  const handleUpdateStock = async () => {
    if (!editingSku) return;
    try {
      await api.updateInventory(editingSku, editQty, 'Staff warehouse inventory adjustment');
      showNotification('success', `Updated inventory for SKU ${editingSku} to ${editQty} units.`);
      setEditingSku(null);
      await Promise.all([loadProducts(), loadReorders()]);
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to update stock');
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
      if (resp.mode) setAssistantMode(resp.mode);
      setChatMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: resp.reply,
          toolCalls: resp.tool_calls,
          citedSkus: resp.cited_skus,
          actions: resp.actions,
          mode: resp.mode,
        }
      ]);
      if (resp.actions?.some(a => a.type === 'draft_order_created')) {
        showNotification('success', 'AI Assistant created a new draft order!');
        await loadOrders();
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
    'Lighting & Electrical', 'Controls & Grips', 'Body & Styling', 
    'Universal Accessories', 'Tyres & Tubes'
  ];

  const currentDealer = dealers.find(d => d.id === selectedDealerId) || dealers[0];

  const filteredOrders = orders.filter(o => {
    if (orderFilterStatus !== 'ALL' && o.status !== orderFilterStatus) return false;
    return true;
  });

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-dark)' }}>
      {/* Floating Notification Banner */}
      {notification && (
        <div 
          style={{
            position: 'fixed',
            top: 24,
            right: 24,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '14px 20px',
            borderRadius: 12,
            background: notification.type === 'success' ? 'rgba(6, 78, 59, 0.95)' : 'rgba(159, 18, 57, 0.95)',
            border: `1px solid ${notification.type === 'success' ? '#10b981' : '#f43f5e'}`,
            color: '#ffffff',
            boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
            backdropFilter: 'blur(8px)',
            maxWidth: 480,
            animation: 'fadeIn 0.25s ease'
          }}
        >
          {notification.type === 'success' ? <CheckCircle2 size={20} color="#34d399" /> : <XCircle size={20} color="#fb7185" />}
          <span style={{ fontSize: '0.9rem', fontWeight: 500, flex: 1 }}>{notification.message}</span>
          <button 
            onClick={() => setNotification(null)}
            style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: 4 }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Sidebar */}
      <aside style={{ width: 260, background: 'var(--bg-sidebar)', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '24px 20px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: '1px solid var(--border-color)' }}>
          <div style={{ width: 38, height: 38, borderRadius: 10, background: 'linear-gradient(135deg, #6366f1, #06b6d4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Layers size={22} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.05rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#fff' }}>VIKMO DealerDesk</h1>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Automotive Parts B2B</p>
          </div>
        </div>

        {/* Dealer Identity Switcher */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', background: 'rgba(255,255,255,0.015)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 700 }}>
              Active Dealership
            </span>
            <span className="badge badge-emerald font-mono" style={{ fontSize: '0.68rem' }}>
              {currentDealer ? currentDealer.dealer_code : '...'}
            </span>
          </div>
          <select 
            value={selectedDealerId} 
            onChange={e => setSelectedDealerId(Number(e.target.value))}
            className="input-field"
            style={{ width: '100%', fontSize: '0.82rem', padding: '8px 10px' }}
          >
            {dealers.map(d => (
              <option key={d.id} value={d.id}>
                {d.dealer_code} - {d.name} ({d.city || 'BLR'})
              </option>
            ))}
          </select>
        </div>

        {/* Navigation */}
        <nav style={{ padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
          {[
            { id: 'overview', label: 'Overview Dashboard', icon: Layers },
            { id: 'catalogue', label: 'Parts Catalogue', icon: Package, badge: productCount ? `${productCount}` : undefined },
            { id: 'orders', label: 'Draft & Confirmed Orders', icon: ShoppingCart, badge: orders.length ? `${orders.length}` : undefined },
            { id: 'dealers', label: 'Dealers & Network', icon: Users },
            { id: 'assistant', label: 'AI Order Assistant', icon: Bot, isAIExtra: true },
            { id: 'forecast', label: 'Demand Forecasting', icon: TrendingUp },
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
                  width: '100%',
                  padding: '11px 14px',
                  borderRadius: 10,
                  border: 'none',
                  background: isActive ? 'linear-gradient(90deg, rgba(99, 102, 241, 0.18), rgba(99, 102, 241, 0.05))' : 'transparent',
                  color: isActive ? '#fff' : 'var(--text-muted)',
                  fontWeight: isActive ? 600 : 500,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease',
                  borderLeft: isActive ? '3px solid var(--primary)' : '3px solid transparent'
                }}
              >
                <Icon size={18} color={isActive ? 'var(--primary)' : 'currentColor'} />
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.badge && (
                  <span className="badge badge-indigo" style={{ fontSize: '0.68rem', padding: '2px 7px' }}>
                    {item.badge}
                  </span>
                )}
                {item.isAIExtra && (
                  <span className="badge badge-emerald" style={{ fontSize: '0.65rem', padding: '2px 6px' }}>
                    Local
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Quick Cart Indicator in Sidebar */}
        {cart.length > 0 && (
          <div style={{ padding: 16, margin: 12, borderRadius: 12, background: 'rgba(99, 102, 241, 0.12)', border: '1px solid var(--border-glow)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#fff' }}>Draft in Progress</span>
              <span className="badge badge-indigo">{cart.length} items</span>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 10 }}>Total: ₹{cartGrandTotal.toFixed(2)}</p>
            <button 
              onClick={() => setActiveTab('catalogue')} 
              className="btn-primary" 
              style={{ width: '100%', padding: '6px 10px', fontSize: '0.78rem', justifyContent: 'center' }}
            >
              Review Draft Items
            </button>
          </div>
        )}

        {/* System Health Status */}
        <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: systemHealth === 'healthy' ? '#10b981' : systemHealth === 'checking' ? '#f59e0b' : '#f43f5e' }} />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>PostgreSQL Backend</span>
          </div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: systemHealth === 'healthy' ? '#10b981' : '#f43f5e' }}>
            {systemHealth.toUpperCase()}
          </span>
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflowY: 'auto' }}>
        {/* Top Header Bar */}
        <header style={{ padding: '16px 32px', background: 'rgba(15, 23, 42, 0.65)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'sticky', top: 0, zIndex: 100 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff' }}>
              {activeTab === 'overview' && 'Dealership Command Centre'}
              {activeTab === 'catalogue' && 'Real-Time Parts Catalogue'}
              {activeTab === 'orders' && 'B2B Draft & Confirmed Orders'}
              {activeTab === 'dealers' && 'South India Dealer Network'}
              {activeTab === 'assistant' && 'AI Dealer Assistant (Tokenless Local Mode)'}
              {activeTab === 'forecast' && 'ML Demand Forecast & Reorders'}
            </h2>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* Mode Switcher: Dealer vs Staff Mode */}
            <div 
              onClick={() => setStaffMode(!staffMode)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 14px',
                borderRadius: 20,
                background: staffMode ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${staffMode ? '#f59e0b' : 'var(--border-color)'}`,
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              title="Click to toggle distributor warehouse staff mode for stock adjustments"
            >
              <UserCheck size={15} color={staffMode ? '#fbbf24' : 'var(--text-muted)'} />
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: staffMode ? '#fbbf24' : 'var(--text-muted)' }}>
                {staffMode ? 'Distributor Staff Mode' : 'Dealer Portal Mode'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 20, border: '1px solid var(--border-color)' }}>
              <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700 }}>
                {currentDealer ? currentDealer.dealer_code.substring(0, 2) : 'VK'}
              </div>
              <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>{currentDealer?.name || 'Verified Dealer'}</span>
            </div>
          </div>
        </header>

        {/* Content Body */}
        <div style={{ padding: 32, flex: 1 }}>

          {/* 1. OVERVIEW TAB */}
          {activeTab === 'overview' && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
              {/* KPI Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20 }}>
                <div className="glass-panel" style={{ padding: 22 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)', marginBottom: 10 }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>Catalogue Items</span>
                    <Package size={20} color="var(--primary)" />
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff' }}>{productCount || 600}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--accent-emerald)', marginTop: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <ArrowUpRight size={14} /> PostgreSQL Live Master
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: 22 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)', marginBottom: 10 }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>Total Orders</span>
                    <ShoppingCart size={20} color="var(--accent-cyan)" />
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff' }}>{orders.length}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 6 }}>
                    {orders.filter(o => o.status === 'CONFIRMED').length} Confirmed · {orders.filter(o => o.status === 'DRAFT').length} Draft
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: 22 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)', marginBottom: 10 }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>Verified Network</span>
                    <Users size={20} color="var(--accent-emerald)" />
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff' }}>{dealers.length || 25}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--accent-emerald)', marginTop: 6 }}>
                    25 Verified South India Dealers
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: 22 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)', marginBottom: 10 }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>Reorder Alerts</span>
                    <AlertTriangle size={20} color="var(--accent-amber)" />
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff' }}>
                    {reorders.filter(r => r.reorder_qty > 0).length || 40}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--accent-amber)', marginTop: 6 }}>
                    Calculated via 4-Wk Lead Time ML
                  </div>
                </div>
              </div>

              {/* Quick Actions & Stock Alerts */}
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24 }}>
                <div className="glass-panel" style={{ padding: 24 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <div>
                      <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Critical Reorder Suggestions (Part D ML Engine)</h3>
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Safety Stock formula: SS = z × σ × √L</p>
                    </div>
                    <button onClick={() => setActiveTab('forecast')} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                      View All Forecasts
                    </button>
                  </div>

                  <table className="modern-table">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>Current Stock</th>
                        <th>Safety Stock</th>
                        <th>Reorder Point</th>
                        <th>Recommended Qty</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reorders.slice(0, 5).map(r => (
                        <tr key={r.sku}>
                          <td className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{r.sku}</td>
                          <td>
                            <span className={`badge ${r.current_stock > 10 ? 'badge-emerald' : r.current_stock > 0 ? 'badge-amber' : 'badge-rose'}`}>
                              {r.current_stock} units
                            </span>
                          </td>
                          <td>{r.safety_stock}</td>
                          <td>{r.reorder_point}</td>
                          <td className="font-mono" style={{ fontWeight: 700, color: r.reorder_qty > 0 ? 'var(--accent-amber)' : 'var(--text-dim)' }}>
                            {r.reorder_qty > 0 ? `+${r.reorder_qty} units` : 'Optimal'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* AI Assistant Quick Panel */}
                <div className="glass-panel" style={{ padding: 24, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                      <Sparkles size={20} color="var(--primary)" />
                      <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Tokenless AI Assistant</h3>
                    </div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                      Deterministic rule-based agent with real-time PostgreSQL grounding. Zero external API keys or tokens required.
                    </p>

                    <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {[
                        'Check stock for BRK-1044',
                        'Do you have brake pads for a Pulsar 150?',
                        'Order 5 units of OIL-1001',
                        'What is the status of my recent orders?'
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
                            padding: '9px 12px',
                            borderRadius: 8,
                            color: 'var(--text-main)',
                            fontSize: '0.82rem',
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

                  <button onClick={() => setActiveTab('assistant')} className="btn-primary" style={{ marginTop: 20, width: '100%', justifyContent: 'center' }}>
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

              {/* Products Table with Direct Order Action */}
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
                      <th>Stock Availability</th>
                      <th>Add to Draft Order</th>
                      {staffMode && <th>Staff Warehouse Adjust</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {productsLoading ? (
                      <tr>
                        <td colSpan={staffMode ? 9 : 8} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                          <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px' }} />
                          Loading catalogue from PostgreSQL...
                        </td>
                      </tr>
                    ) : products.length === 0 ? (
                      <tr>
                        <td colSpan={staffMode ? 9 : 8} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                          No products match your search criteria.
                        </td>
                      </tr>
                    ) : (
                      products.map(p => {
                        const isOutOfStock = p.stock <= 0;
                        const qty = getSelectedQty(p.sku);
                        return (
                          <tr key={p.sku}>
                            <td className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{p.sku}</td>
                            <td style={{ fontWeight: 600, maxWidth: 220 }}>{p.name}</td>
                            <td><span className="badge badge-indigo">{p.category}</span></td>
                            <td>{p.brand}</td>
                            <td><span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{p.vehicle_fitment}</span></td>
                            <td className="font-mono" style={{ fontWeight: 700 }}>₹{p.price}</td>
                            <td>
                              <span className={`badge ${p.stock > 10 ? 'badge-emerald' : p.stock > 0 ? 'badge-amber' : 'badge-rose'}`}>
                                {isOutOfStock ? 'Out of Stock (0)' : `${p.stock} Available`}
                              </span>
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <input
                                  type="number"
                                  min={1}
                                  max={Math.max(1, p.stock)}
                                  disabled={isOutOfStock}
                                  value={qty}
                                  onChange={e => setSelectedQty(p.sku, parseInt(e.target.value) || 1)}
                                  className="input-field"
                                  style={{ width: 60, padding: '4px 8px', fontSize: '0.85rem', textAlign: 'center' }}
                                />
                                <button
                                  disabled={isOutOfStock}
                                  onClick={() => handleAddToCart(p)}
                                  className="btn-primary"
                                  style={{ padding: '6px 12px', fontSize: '0.8rem', opacity: isOutOfStock ? 0.4 : 1 }}
                                >
                                  <Plus size={14} /> Add
                                </button>
                              </div>
                            </td>
                            {staffMode && (
                              <td>
                                <button
                                  onClick={() => {
                                    setEditingSku(p.sku);
                                    setEditQty(p.stock);
                                  }}
                                  className="btn-secondary"
                                  style={{ padding: '6px 10px', fontSize: '0.78rem' }}
                                >
                                  Adjust
                                </button>
                              </td>
                            )}
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>

                {/* Pagination Bar */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderTop: '1px solid var(--border-color)' }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
                    Showing {products.length} of {productCount} products in catalogue
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

              {/* Floating Draft Order Cart Bar */}
              {cart.length > 0 && (
                <div 
                  className="glass-panel" 
                  style={{
                    position: 'sticky',
                    bottom: 24,
                    padding: '16px 24px',
                    background: 'rgba(15, 23, 42, 0.95)',
                    border: '1px solid var(--primary)',
                    boxShadow: '0 12px 35px rgba(0,0,0,0.6)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 16,
                    zIndex: 90
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <ShoppingCart size={20} color="#fff" />
                    </div>
                    <div>
                      <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff' }}>
                        Draft Order ({cart.length} item{cart.length > 1 ? 's' : ''})
                      </h4>
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        Dealer: <strong>{currentDealer?.dealer_code} - {currentDealer?.name}</strong>
                      </p>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Subtotal: ₹{cartSubtotal.toFixed(2)} + 18% GST: ₹{cartTax.toFixed(2)}</div>
                      <div className="font-mono" style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
                        Total: ₹{cartGrandTotal.toFixed(2)}
                      </div>
                    </div>

                    <button 
                      onClick={() => setCart([])}
                      className="btn-secondary"
                      style={{ padding: '8px 12px', fontSize: '0.85rem' }}
                    >
                      Clear
                    </button>

                    <button
                      disabled={isSubmittingOrder}
                      onClick={handleCreateDraftOrder}
                      className="btn-primary"
                      style={{ padding: '10px 20px', fontSize: '0.9rem' }}
                    >
                      {isSubmittingOrder ? (
                        <>
                          <RefreshCw size={16} className="animate-spin" /> Saving Draft...
                        </>
                      ) : (
                        <>
                          <Check size={16} /> Save Draft Order
                        </>
                      )}
                    </button>
                  </div>

                  {/* Cart Items List */}
                  <div style={{ width: '100%', display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 10, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                    {cart.map(item => (
                      <div 
                        key={item.product.sku}
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid var(--border-color)',
                          borderRadius: 8,
                          padding: '6px 12px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          fontSize: '0.82rem'
                        }}
                      >
                        <span className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{item.product.sku}</span>
                        <span>{item.product.name}</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <button 
                            onClick={() => handleUpdateCartQty(item.product.sku, -1)}
                            className="btn-secondary"
                            style={{ padding: '2px 6px', fontSize: '0.75rem' }}
                            title="Decrease quantity"
                          >
                            <Minus size={12} />
                          </button>
                          <span className="font-mono" style={{ fontWeight: 700, padding: '0 4px' }}>{item.quantity}</span>
                          <button 
                            onClick={() => handleUpdateCartQty(item.product.sku, 1)}
                            className="btn-secondary"
                            style={{ padding: '2px 6px', fontSize: '0.75rem' }}
                            title="Increase quantity"
                          >
                            <Plus size={12} />
                          </button>
                        </div>
                        <span className="font-mono" style={{ fontWeight: 600 }}>₹{(parseFloat(item.product.price) * item.quantity).toFixed(2)}</span>
                        <button 
                          onClick={() => handleRemoveFromCart(item.product.sku)}
                          style={{ background: 'transparent', border: 'none', color: '#f43f5e', cursor: 'pointer', padding: 2 }}
                          title="Remove item"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 3. ORDERS TAB */}
          {activeTab === 'orders' && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <div className="glass-panel" style={{ padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
                  <div>
                    <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Orders Lifecycle Management</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      Strict atomic confirmation with row-level PostgreSQL stock locks & exact paisa GST
                    </p>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <button onClick={loadOrders} className="btn-secondary" style={{ padding: '8px 12px' }}>
                      <RefreshCw size={14} className={ordersLoading ? 'animate-spin' : ''} /> Refresh
                    </button>
                    <button onClick={() => setActiveTab('catalogue')} className="btn-primary">
                      + Create New Order
                    </button>
                  </div>
                </div>

                {/* Filter Status Tabs */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 18, borderBottom: '1px solid var(--border-color)', paddingBottom: 12, overflowX: 'auto' }}>
                  {['ALL', 'DRAFT', 'CONFIRMED', 'DISPATCHED', 'DELIVERED', 'CANCELLED'].map(st => (
                    <button
                      key={st}
                      onClick={() => setOrderFilterStatus(st)}
                      style={{
                        padding: '6px 14px',
                        borderRadius: 20,
                        border: 'none',
                        background: orderFilterStatus === st ? 'var(--primary)' : 'rgba(255,255,255,0.04)',
                        color: orderFilterStatus === st ? '#fff' : 'var(--text-muted)',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {st} {st !== 'ALL' && `(${orders.filter(o => o.status === st).length})`}
                    </button>
                  ))}
                </div>

                {/* Orders Table */}
                <table className="modern-table">
                  <thead>
                    <tr>
                      <th>Order Number</th>
                      <th>Dealer</th>
                      <th>Status</th>
                      <th>Items</th>
                      <th>Subtotal</th>
                      <th>18% GST</th>
                      <th>Grand Total</th>
                      <th>Created At</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ordersLoading ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>Loading orders...</td>
                      </tr>
                    ) : filteredOrders.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                          No {orderFilterStatus !== 'ALL' ? orderFilterStatus : ''} orders found. Create a draft order from the catalogue or AI assistant!
                        </td>
                      </tr>
                    ) : (
                      filteredOrders.map(o => {
                        const isLoading = orderActionLoading[o.order_number];
                        const isExpanded = expandedOrderNumber === o.order_number;
                        const dealerInfo = dealers.find(d => d.id === o.dealer_id);

                        return (
                          <React.Fragment key={o.order_number}>
                            <tr>
                              <td className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>
                                {o.order_number}
                              </td>
                              <td>
                                <span style={{ fontWeight: 600 }}>{dealerInfo?.name || `Dealer #${o.dealer_id}`}</span>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{dealerInfo?.dealer_code}</div>
                              </td>
                              <td>
                                <span className={`badge ${
                                  o.status === 'CONFIRMED' ? 'badge-emerald' : 
                                  o.status === 'DRAFT' ? 'badge-amber' : 
                                  o.status === 'CANCELLED' ? 'badge-rose' : 'badge-indigo'
                                }`}>
                                  {o.status}
                                </span>
                              </td>
                              <td>
                                <button
                                  onClick={() => setExpandedOrderNumber(isExpanded ? null : o.order_number)}
                                  className="btn-secondary"
                                  style={{ padding: '4px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 4 }}
                                >
                                  <Eye size={12} /> {o.items?.length || 0} lines
                                </button>
                              </td>
                              <td className="font-mono">₹{o.subtotal}</td>
                              <td className="font-mono">₹{o.tax_total}</td>
                              <td className="font-mono" style={{ fontWeight: 700, color: '#fff' }}>₹{o.grand_total}</td>
                              <td style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                                {new Date(o.created_at).toLocaleString()}
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: 6 }}>
                                  {o.status === 'DRAFT' && (
                                    <>
                                      <button
                                        disabled={isLoading}
                                        onClick={() => handleConfirmOrder(o.order_number)}
                                        className="btn-success"
                                        style={{ padding: '5px 10px', fontSize: '0.75rem' }}
                                        title="Confirm order and deduct inventory atomically"
                                      >
                                        <Check size={12} /> Confirm
                                      </button>
                                      <button
                                        disabled={isLoading}
                                        onClick={() => handleCancelOrder(o.order_number)}
                                        className="btn-danger"
                                        style={{ padding: '5px 10px', fontSize: '0.75rem' }}
                                        title="Cancel draft order"
                                      >
                                        <X size={12} /> Cancel
                                      </button>
                                    </>
                                  )}

                                  {o.status === 'CONFIRMED' && (
                                    <>
                                      {staffMode && (
                                        <button
                                          disabled={isLoading}
                                          onClick={() => handleDispatchOrder(o.order_number)}
                                          className="btn-secondary"
                                          style={{ padding: '5px 10px', fontSize: '0.75rem' }}
                                        >
                                          <Truck size={12} /> Dispatch
                                        </button>
                                      )}
                                      <button
                                        disabled={isLoading}
                                        onClick={() => handleCancelOrder(o.order_number)}
                                        className="btn-danger"
                                        style={{ padding: '5px 10px', fontSize: '0.75rem' }}
                                        title="Cancel confirmed order and restore stock"
                                      >
                                        Cancel & Restore
                                      </button>
                                    </>
                                  )}

                                  {o.status === 'DISPATCHED' && staffMode && (
                                    <button
                                      disabled={isLoading}
                                      onClick={() => handleDeliverOrder(o.order_number)}
                                      className="btn-success"
                                      style={{ padding: '5px 10px', fontSize: '0.75rem' }}
                                    >
                                      Mark Delivered
                                    </button>
                                  )}

                                  {o.status === 'CANCELLED' && (
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Closed</span>
                                  )}

                                  {o.status === 'DELIVERED' && (
                                    <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)' }}>Completed</span>
                                  )}
                                </div>
                              </td>
                            </tr>

                            {/* Expanded Order Items Row */}
                            {isExpanded && (
                              <tr>
                                <td colSpan={9} style={{ background: 'rgba(0,0,0,0.25)', padding: '16px 24px' }}>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                                      Order {o.order_number} Line Items Breakdown (18% GST line-by-line):
                                    </div>
                                    <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
                                      <thead>
                                        <tr style={{ color: 'var(--text-dim)', textAlign: 'left', borderBottom: '1px solid var(--border-color)' }}>
                                          <th style={{ padding: '6px 8px' }}>SKU</th>
                                          <th style={{ padding: '6px 8px' }}>Product Name</th>
                                          <th style={{ padding: '6px 8px' }}>Quantity</th>
                                          <th style={{ padding: '6px 8px' }}>Unit Price</th>
                                          <th style={{ padding: '6px 8px' }}>Subtotal</th>
                                          <th style={{ padding: '6px 8px' }}>18% Tax</th>
                                          <th style={{ padding: '6px 8px' }}>Line Total</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {o.items?.map((item, idx) => (
                                          <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                                            <td className="font-mono" style={{ padding: '6px 8px', color: 'var(--accent-cyan)' }}>{item.sku}</td>
                                            <td style={{ padding: '6px 8px' }}>{item.name || item.sku}</td>
                                            <td style={{ padding: '6px 8px', fontWeight: 700 }}>{item.quantity}</td>
                                            <td className="font-mono" style={{ padding: '6px 8px' }}>₹{item.unit_price}</td>
                                            <td className="font-mono" style={{ padding: '6px 8px' }}>₹{item.line_subtotal}</td>
                                            <td className="font-mono" style={{ padding: '6px 8px' }}>₹{item.line_tax}</td>
                                            <td className="font-mono" style={{ padding: '6px 8px', fontWeight: 700, color: '#fff' }}>₹{item.line_total}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 4. DEALERS & INVENTORY TAB */}
          {activeTab === 'dealers' && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <div className="glass-panel" style={{ padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
                  <div>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Registered Dealer Network (25 South India Partners)</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Verified B2B dealers across Bengaluru, Chennai, Hyderabad, and Kochi</p>
                  </div>
                  <span className="badge badge-emerald">25 Active Verified Partners</span>
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
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        Session: {sessionId} · Dealer: {currentDealer?.dealer_code}
                      </p>
                    </div>
                  </div>
                  <span className={`badge ${assistantMode === 'rule_based' ? 'badge-indigo' : 'badge-emerald'}`}>
                    {assistantMode === 'rule_based' ? 'Tokenless Local Rule-Based' : 'Gemini AI Live'}
                  </span>
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
                        <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center' }}>
                          {msg.actions.map((act, aidx) => (
                            <div key={aidx} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                              <span className="badge badge-emerald">
                                ✅ Created {act.order_number}
                              </span>
                              <button
                                onClick={() => {
                                  setActiveTab('orders');
                                  setExpandedOrderNumber(act.order_number);
                                }}
                                className="btn-secondary"
                                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                              >
                                View Order
                              </button>
                            </div>
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
                    placeholder="Ask for parts, check stock, check orders, or draft orders..."
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

              {/* Safety & Grounding Card */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                <div className="glass-panel" style={{ padding: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <ShieldCheck size={20} color="var(--accent-emerald)" />
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Tokenless Architecture</h4>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: 14 }}>
                    Operating 100% locally with deterministic intent matching and live PostgreSQL queries. No paid API keys or external services required.
                  </p>
                  <ul style={{ fontSize: '0.78rem', color: 'var(--text-dim)', paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <li>Exact live database tool grounding</li>
                    <li>Stock verification before draft creation</li>
                    <li>Multi-turn memory persistence in PostgreSQL</li>
                    <li>Refuses unconfirmed stock deductions</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* 6. FORECAST TAB */}
          {activeTab === 'forecast' && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <div className="glass-panel" style={{ padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                  <div>
                    <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Part D — Demand Forecasting & Reorder Suggestions</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      Multiplicative decomposition model with Diwali festive lift (beats Naive, MA-4, and YoY baselines)
                    </p>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Select SKU:</span>
                    <select
                      value={forecastSku}
                      onChange={e => setForecastSku(e.target.value)}
                      className="input-field"
                      style={{ minWidth: 160 }}
                    >
                      {reorders.map(r => (
                        <option key={r.sku} value={r.sku}>{r.sku}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* SKU 4-Week Forecast Chart / Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
                  {skuForecast.map((wf, idx) => (
                    <div key={wf.week_start} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-dim)', fontSize: '0.78rem', marginBottom: 8 }}>
                        <Calendar size={14} /> Week {idx + 1} ({wf.week_start})
                      </div>
                      <div className="font-mono" style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>
                        {wf.forecast_units} <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-muted)' }}>units</span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: idx === 1 ? 'var(--accent-amber)' : 'var(--text-dim)', marginTop: 6 }}>
                        {idx === 1 ? 'Festive Diwali Lift' : 'Baseline Demand'}
                      </div>
                    </div>
                  ))}
                </div>

                {/* 40 SKUs Reorder Table */}
                <div style={{ marginTop: 12 }}>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 12 }}>All 40 Evaluated SKUs Reorder Recommendations</h4>
                  <table className="modern-table">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>Current Stock</th>
                        <th>Lead Time</th>
                        <th>Lead Time Demand</th>
                        <th>Safety Stock (SS)</th>
                        <th>Reorder Point (ROP)</th>
                        <th>Recommended Reorder Qty</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reorders.map(r => (
                        <tr key={r.sku}>
                          <td className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>{r.sku}</td>
                          <td>
                            <span className={`badge ${r.current_stock > 10 ? 'badge-emerald' : r.current_stock > 0 ? 'badge-amber' : 'badge-rose'}`}>
                              {r.current_stock}
                            </span>
                          </td>
                          <td>{r.lead_time_weeks} wks</td>
                          <td>{r.lead_time_demand}</td>
                          <td>{r.safety_stock}</td>
                          <td>{r.reorder_point}</td>
                          <td className="font-mono" style={{ fontWeight: 700, color: r.reorder_qty > 0 ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>
                            {r.reorder_qty > 0 ? `+${r.reorder_qty} units` : 'Sufficient'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

        </div>
      </main>

      {/* Staff Warehouse Inventory Adjustment Modal */}
      {editingSku && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="glass-panel" style={{ padding: 28, width: 420, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>Adjust Warehouse Inventory</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Staff manual stock adjustment for SKU <span className="font-mono" style={{ color: 'var(--accent-cyan)' }}>{editingSku}</span>.
            </p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>New Stock Quantity (Units)</label>
              <input
                type="number"
                min={0}
                value={editQty}
                onChange={e => setEditQty(Math.max(0, parseInt(e.target.value) || 0))}
                className="input-field"
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
              <button onClick={() => setEditingSku(null)} className="btn-secondary">
                Cancel
              </button>
              <button onClick={handleUpdateStock} className="btn-primary">
                Save Stock
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
