import React, { useState, useEffect, useRef } from 'react';
import { 
  ShieldAlert, 
  Activity, 
  MessageSquare, 
  Database, 
  Truck, 
  Users, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle2, 
  Search, 
  ArrowRight, 
  Warehouse as WhIcon, 
  TrendingDown, 
  Terminal, 
  Play, 
  ChevronDown, 
  ChevronUp, 
  ExternalLink 
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Legend 
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const queries = [
  "Which suppliers are most likely to miss deliveries next week?",
  "Which products are at risk of going out of stock?",
  "What is causing today's biggest supply chain disruption?",
  "Which warehouse should fulfill an order of 1500 units for MCU-32-Core?"
];

export default function App() {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState('monitor'); // monitor, inventory, suppliers, shipments, chat

  // Dashboard Stats
  const [stats, setStats] = useState({
    total_skus: 0,
    total_suppliers: 0,
    at_risk_skus: 0,
    delayed_shipments: 0,
    latest_run_status: 'N/A',
    latest_run_time: null,
    decisions_count: 0
  });

  // Data states
  const [inventory, setInventory] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [shipments, setShipments] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [runs, setRuns] = useState([]);
  const [execSummary, setExecSummary] = useState('');
  
  // Loading & Error States
  const [loadingStats, setLoadingStats] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [triggeringMonitor, setTriggeringMonitor] = useState(false);

  // Search Filters
  const [skuSearch, setSkuSearch] = useState('');
  const [supplierSearch, setSupplierSearch] = useState('');

  // Expandable decision cards
  const [expandedDecisions, setExpandedDecisions] = useState({});

  // Suggest Alternate Supplier Drawer/Modal state
  const [alternateSupplierData, setAlternateSupplierData] = useState(null);
  const [loadingAlternates, setLoadingAlternates] = useState(false);

  // Chat Agent state
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    {
      role: 'assistant',
      text: "Hello! I am the Reactive Ops Agent. I can search live inventory, check supplier risks, analyze delayed shipments, recommend warehouse routing, and find alternate suppliers. How can I help you resolve a supply chain disruption today?",
      steps: []
    }
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // Fetch initial dashboard metrics
  const fetchDashboardStats = async () => {
    setLoadingStats(true);
    try {
      const res = await fetch(`${API_BASE}/dashboard-summary`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error("Error fetching stats:", err);
    } finally {
      setLoadingStats(false);
    }
  };

  // Fetch executive summary
  const fetchExecutiveSummary = async () => {
    setLoadingSummary(true);
    try {
      const res = await fetch(`${API_BASE}/exec-summary`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setExecSummary(data.summary);
      }
    } catch (err) {
      console.error("Error fetching summary:", err);
      setExecSummary("Could not load executive summary. Ensure backend is running.");
    } finally {
      setLoadingSummary(false);
    }
  };

  // Fetch Core Tables (decisions, runs, inventory, suppliers, shipments)
  const fetchTabData = async () => {
    setLoadingData(true);
    try {
      const [invRes, supRes, shipRes, decRes, runsRes] = await Promise.all([
        fetch(`${API_BASE}/inventory-risk`),
        fetch(`${API_BASE}/suppliers`),
        fetch(`${API_BASE}/shipments/delays`),
        fetch(`${API_BASE}/agent/monitor/decisions`),
        fetch(`${API_BASE}/agent/monitor/runs`)
      ]);

      if (invRes.ok) setInventory(await invRes.json());
      if (supRes.ok) setSuppliers(await supRes.json());
      if (shipRes.ok) setShipments(await shipRes.json());
      if (decRes.ok) setDecisions(await decRes.json());
      if (runsRes.ok) setRuns(await runsRes.json());
    } catch (err) {
      console.error("Error fetching tab data:", err);
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    fetchDashboardStats();
    fetchExecutiveSummary();
    fetchTabData();
  }, []);

  useEffect(() => {
    // Scroll to bottom of chat
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, chatLoading]);

  // Handle Manual Trigger of Autonomous Monitor Agent
  const triggerMonitorScan = async () => {
    setTriggeringMonitor(true);
    try {
      const res = await fetch(`${API_BASE}/agent/monitor/run`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        // Refresh everything
        await Promise.all([
          fetchDashboardStats(),
          fetchExecutiveSummary(),
          fetchTabData()
        ]);
        alert(`Autonomous Monitor Run triggered successfully! Run ID: ${data.run_id}`);
      } else {
        alert("Failed to run monitor agent. Check server logs.");
      }
    } catch (err) {
      console.error("Error running monitor:", err);
      alert("Error contacting server to run monitor.");
    } finally {
      setTriggeringMonitor(false);
    }
  };

  // Handle Alternate Supplier Suggestion click
  const handleSuggestAlternates = async (skuName) => {
    setLoadingAlternates(true);
    try {
      const res = await fetch(`${API_BASE}/suppliers/suggest-alternate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sku_id_or_name: skuName })
      });
      if (res.ok) {
        const data = await res.json();
        setAlternateSupplierData(data);
      } else {
        alert("Failed to fetch alternates.");
      }
    } catch (err) {
      console.error(err);
      alert("Error connecting to server.");
    } finally {
      setLoadingAlternates(false);
    }
  };

  // Handle Reactive Agent message submission
  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userText = chatInput;
    setChatInput('');
    setChatHistory(prev => [...prev, { role: 'user', text: userText, steps: [] }]);
    setChatLoading(true);
 
    try {
      const res = await fetch(`${API_BASE}/agent/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userText })
      });

      if (res.ok) {
        const data = await res.json();
        setChatHistory(prev => [...prev, {
          role: 'assistant',
          text: data.answer,
          steps: data.steps || []
        }]);
        // Refresh dashboard summary metrics dynamically as actions might have updated states
        fetchDashboardStats();
      } else {
        setChatHistory(prev => [...prev, {
          role: 'assistant',
          text: "I encountered an error querying the server. Please verify the API connection.",
          steps: []
        }]);
      }
    } catch (err) {
      setChatHistory(prev => [...prev, {
        role: 'assistant',
        text: "Error: Failed to connect to Reactive Agent. Make sure the backend is active.",
        steps: []
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  // Toggle expanding a decision card
  const toggleDecision = (id) => {
    setExpandedDecisions(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  // Map severity styles
  const getSeverityBadge = (sev) => {
    const s = sev.toLowerCase();
    if (s === 'critical') return 'bg-rose-500/20 text-rose-400 border border-rose-500/30';
    if (s === 'high') return 'bg-amber-500/20 text-amber-400 border border-amber-500/30';
    if (s === 'medium') return 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
    return 'bg-gray-500/20 text-gray-400 border border-gray-500/30';
  };

  // Filter lists
  const filteredInventory = inventory.filter(k => 
    k.name.toLowerCase().includes(skuSearch.toLowerCase()) || 
    k.category.toLowerCase().includes(skuSearch.toLowerCase())
  );

  const filteredSuppliers = suppliers.filter(s => 
    s.name.toLowerCase().includes(supplierSearch.toLowerCase()) || 
    s.category.toLowerCase().includes(supplierSearch.toLowerCase())
  );

  // Prepare data for Chart (Top At-Risk Stock vs Safety levels)
  const chartData = inventory
    .filter(k => k.risk_level !== 'none')
    .slice(0, 7)
    .map(k => ({
      name: k.name,
      Stock: k.current_stock,
      Safety: k.safety_stock,
      Reorder: k.reorder_point
    }));

  return (
    <div className="min-h-screen bg-darkBg text-gray-100 flex flex-col font-sans">
      
      {/* ── HEADER ── */}
      <header className="border-b border-borderDark bg-cardBg/30 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-accentOrange/10 text-accentOrange rounded-xl border border-accentOrange/20 shadow-[0_0_15px_rgba(255,90,31,0.1)]">
            <Truck className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center space-x-2">
              <span>SupplySense</span>
            </h1>
            <p className="text-xs text-gray-400">AI Supply Chain Risk & Inventory Intelligence</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button 
            onClick={triggerMonitorScan} 
            disabled={triggeringMonitor}
            className="flex items-center space-x-2 bg-accentOrange/10 hover:bg-accentOrange/20 border border-accentOrange/30 hover:border-accentOrange/50 text-accentOrange hover:text-white px-4 py-2 rounded-xl text-sm font-medium transition duration-200 disabled:opacity-50"
          >
            <Play className={`w-4 h-4 ${triggeringMonitor ? 'animate-spin' : ''}`} />
            <span>{triggeringMonitor ? 'Analyzing Snapshot...' : 'Manual Agent Scan'}</span>
          </button>
          
          <button 
            onClick={() => { fetchDashboardStats(); fetchExecutiveSummary(); fetchTabData(); }}
            className="p-2 bg-gray-800/40 hover:bg-gray-800 border border-borderDark rounded-xl text-gray-400 hover:text-white transition"
            title="Refresh All Data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="flex-1 max-w-[1600px] w-full mx-auto p-6 flex flex-col space-y-6">
        
        {/* ── KPI STATS CARDS ── */}
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-cardBg border border-borderDark rounded-2xl p-5 hover:border-gray-700/60 transition shadow-none">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] uppercase font-bold tracking-wider text-gray-500 block">At-Risk Products</span>
              <div className="p-2 bg-accentOrange/10 text-accentOrange rounded-lg border border-accentOrange/20">
                <ShieldAlert className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-accentOrange">{stats.at_risk_skus}</span>
              <span className="text-xs text-gray-400">/ {stats.total_skus} total SKUs</span>
            </div>
          </div>

          <div className="bg-cardBg border border-borderDark rounded-2xl p-5 hover:border-gray-700/60 transition shadow-none">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] uppercase font-bold tracking-wider text-gray-500 block">Delayed Shipments</span>
              <div className="p-2 bg-accentOrange/10 text-accentOrange rounded-lg border border-accentOrange/20">
                <Truck className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-accentOrange">{stats.delayed_shipments}</span>
              <span className="text-xs text-gray-400 font-medium">Active Delay Risk</span>
            </div>
          </div>

          <div className="bg-cardBg border border-borderDark rounded-2xl p-5 hover:border-gray-700/60 transition shadow-none">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] uppercase font-bold tracking-wider text-gray-500 block">Supply Partners</span>
              <div className="p-2 bg-gray-800 text-gray-400 rounded-lg border border-gray-700">
                <Users className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-white">{stats.total_suppliers}</span>
              <span className="text-xs text-gray-400">Persisted Profiles</span>
            </div>
          </div>

          <div className="bg-cardBg border border-borderDark rounded-2xl p-5 hover:border-gray-700/60 transition shadow-none">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] uppercase font-bold tracking-wider text-gray-500 block">Monitor Agent Run Status</span>
              <div className={`p-2 rounded-lg border ${
                stats.latest_run_status === 'success' 
                  ? 'bg-neonEmerald/10 text-neonEmerald border-neonEmerald/20' 
                  : stats.latest_run_status === 'failed' 
                    ? 'bg-neonRose/10 text-neonRose border-neonRose/20' 
                    : 'bg-accentOrange/10 text-accentOrange border-accentOrange/20'
              }`}>
                <Activity className="w-5 h-5" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <span className="text-base font-extrabold text-white uppercase tracking-wider">{stats.latest_run_status}</span>
                {stats.latest_run_status === 'running' && (
                  <span className="w-2.5 h-2.5 rounded-full bg-accentOrange animate-ping"></span>
                )}
              </div>
              <span className="text-xs text-gray-400 block">
                Last checked: {stats.latest_run_time ? new Date(stats.latest_run_time).toLocaleTimeString() : 'N/A'}
              </span>
            </div>
          </div>
        </section>

        {/* ── NAVIGATION TABS ── */}
        <nav className="flex space-x-1 border border-borderDark p-1 bg-cardBg/50 rounded-xl max-w-max">
          <button 
            onClick={() => setActiveTab('monitor')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition duration-150 ${activeTab === 'monitor' ? 'bg-accentOrange text-white shadow-md' : 'text-gray-400 hover:text-white hover:bg-gray-800/40'}`}
          >
            <Activity className="w-4 h-4" />
            <span>Risk Monitor Log</span>
          </button>
          <button 
            onClick={() => setActiveTab('inventory')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition duration-150 ${activeTab === 'inventory' ? 'bg-accentOrange text-white shadow-md' : 'text-gray-400 hover:text-white hover:bg-gray-800/40'}`}
          >
            <Database className="w-4 h-4" />
            <span>Stock Analysis</span>
          </button>
          <button 
            onClick={() => setActiveTab('suppliers')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition duration-150 ${activeTab === 'suppliers' ? 'bg-accentOrange text-white shadow-md' : 'text-gray-400 hover:text-white hover:bg-gray-800/40'}`}
          >
            <Users className="w-4 h-4" />
            <span>Supply Partners</span>
          </button>
          <button 
            onClick={() => setActiveTab('shipments')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition duration-150 ${activeTab === 'shipments' ? 'bg-accentOrange text-white shadow-md' : 'text-gray-400 hover:text-white hover:bg-gray-800/40'}`}
          >
            <Truck className="w-4 h-4" />
            <span>Logistics delays</span>
          </button>
          <button 
            onClick={() => setActiveTab('chat')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition duration-150 ${activeTab === 'chat' ? 'bg-accentOrange text-white shadow-md' : 'text-gray-400 hover:text-white hover:bg-gray-800/40'}`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>Reactive Chat Agent</span>
          </button>
        </nav>

        {/* ── TAB PANEL CONTENT ── */}
        <main className="flex-1 bg-cardBg/40 border border-borderDark rounded-2xl p-6 backdrop-blur">
          
          {/* TAB 1: RISK MONITOR CENTER */}
          {activeTab === 'monitor' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* LEFT: AGENT ACTIVITY LOG PANEL (PRIORITY HACKATHON ELEMENT) */}
              <div className="lg:col-span-2 flex flex-col space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                      <Terminal className="w-5 h-5 text-neonEmerald" />
                      <span>Autonomous Agent Decision Log</span>
                    </h2>
                    <p className="text-xs text-gray-400">Structured audit decisions generated by the scheduling agent citing live metrics.</p>
                  </div>
                </div>

                <div className="space-y-3 overflow-y-auto max-h-[600px] pr-2">
                  {decisions.length === 0 ? (
                    <div className="bg-cardBg border border-borderDark rounded-2xl p-8 text-center text-gray-500">
                      No decisions generated yet. Trigger a "Manual Agent Scan" to generate decisions.
                    </div>
                  ) : (
                    decisions.map((d) => {
                      const isExpanded = expandedDecisions[d.id];
                      return (
                        <div 
                          key={d.id} 
                          className="bg-cardBg border border-borderDark rounded-xl overflow-hidden hover:border-gray-700 transition"
                        >
                          {/* Header Summary */}
                          <div 
                            onClick={() => toggleDecision(d.id)}
                            className="p-4 flex items-center justify-between cursor-pointer select-none"
                          >
                            <div className="flex items-center space-x-3">
                              <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase tracking-wider ${getSeverityBadge(d.severity)}`}>
                                {d.severity}
                              </span>
                              <div>
                                <h3 className="text-sm font-semibold text-white">{d.decision_type.replace('_', ' ').toUpperCase()}</h3>
                                <p className="text-xs text-gray-400">Subject: <span className="font-medium text-gray-300">{d.subject_name}</span></p>
                              </div>
                            </div>
                            <div className="flex items-center space-x-3">
                              <span className="text-xs text-gray-500">{new Date(d.created_at).toLocaleTimeString()}</span>
                              {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                            </div>
                          </div>

                          {/* Expanded Content (Reasoning & Action Plan) */}
                          {isExpanded && (
                            <div className="border-t border-borderDark bg-gray-950/40 p-4 space-y-3 text-sm">
                              <div>
                                <h4 className="text-xs font-semibold text-neonEmerald mb-1 uppercase tracking-wider">CITED TELEMETRY METRIC</h4>
                                <div className="bg-gray-900/60 p-2.5 rounded-lg border border-borderDark text-neonEmerald font-mono text-xs">
                                  {d.reasoning.metric_cited}
                                </div>
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                                <div>
                                  <h4 className="font-semibold text-white mb-0.5">Vulnerability Summary</h4>
                                  <p className="text-gray-400">{d.reasoning.context}</p>
                                </div>
                                <div>
                                  <h4 className="font-semibold text-white mb-0.5">Downstream Impact</h4>
                                  <p className="text-gray-400">{d.reasoning.impact}</p>
                                </div>
                              </div>

                              <div className="bg-neonBlue/5 border border-neonBlue/10 p-3 rounded-lg">
                                <h4 className="text-xs font-semibold text-neonBlue mb-1 uppercase tracking-wider flex items-center space-x-1">
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                  <span>Agent Prescribed Action Plan</span>
                                </h4>
                                <p className="text-xs text-gray-300 leading-relaxed font-sans">{d.recommended_action}</p>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* RIGHT: EXECUTIVE STATE SUMMARY */}
              <div className="flex flex-col space-y-4">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                    <ShieldAlert className="w-5 h-5 text-neonRose" />
                    <span>Executive Synthesis</span>
                  </h2>
                  <p className="text-xs text-gray-400">AI-synthesized high-level report on critical focus areas.</p>
                </div>

                <div className="bg-cardBg border border-borderDark rounded-2xl p-5 space-y-4 h-full flex flex-col justify-between">
                  <div className="flex-1">
                    {loadingSummary ? (
                      <div className="flex flex-col items-center justify-center h-48 space-y-2 text-gray-500">
                        <RefreshCw className="w-6 h-6 animate-spin text-neonBlue" />
                        <span className="text-xs font-mono">Synthesizing state...</span>
                      </div>
                    ) : (
                      <p className="text-gray-300 leading-relaxed text-sm whitespace-pre-line font-sans">
                        {execSummary || "No executive summary generated yet."}
                      </p>
                    )}
                  </div>

                  <button 
                    onClick={fetchExecutiveSummary}
                    disabled={loadingSummary}
                    className="w-full flex items-center justify-center space-x-2 bg-gray-800 hover:bg-gray-700 border border-borderDark hover:border-gray-600 text-gray-300 hover:text-white px-4 py-2.5 rounded-xl text-xs font-medium transition"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingSummary ? 'animate-spin' : ''}`} />
                    <span>Regenerate Executive Summary</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: INVENTORY STOCK ANALYSIS */}
          {activeTab === 'inventory' && (
            <div className="space-y-6">
              
              {/* Chart Section */}
              {chartData.length > 0 && (
                <div className="bg-cardBg border border-borderDark rounded-2xl p-5">
                  <h3 className="text-sm font-semibold text-white mb-4">Stock Levels vs Safety Thresholds for At-Risk Items</h3>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorStock" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#FF5A1F" stopOpacity={0.2}/>
                            <stop offset="95%" stopColor="#FF5A1F" stopOpacity={0}/>
                          </linearGradient>
                          <linearGradient id="colorSafety" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.1}/>
                            <stop offset="95%" stopColor="#F43F5E" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2E" />
                        <XAxis dataKey="name" stroke="#9CA3AF" fontSize={11} />
                        <YAxis stroke="#9CA3AF" fontSize={11} />
                        <Tooltip contentStyle={{ backgroundColor: '#1A1A1D', borderColor: '#2A2A2E' }} />
                        <Legend fontSize={12} />
                        <Area type="monotone" dataKey="Stock" stroke="#FF5A1F" fillOpacity={1} fill="url(#colorStock)" />
                        <Area type="monotone" dataKey="Safety" stroke="#F43F5E" strokeDasharray="5 5" fillOpacity={1} fill="url(#colorSafety)" />
                        <Area type="monotone" dataKey="Reorder" stroke="#F59E0B" fillOpacity={0} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Table Section */}
              <div className="flex flex-col space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                    <Database className="w-5 h-5 text-neonBlue" />
                    <span>Real-time Inventory Risk Analysis</span>
                  </h2>
                  <div className="relative max-w-xs w-full">
                    <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                      <Search className="w-4 h-4" />
                    </span>
                    <input 
                      type="text" 
                      placeholder="Filter by SKU or category..."
                      value={skuSearch}
                      onChange={(e) => setSkuSearch(e.target.value)}
                      className="bg-cardBg border border-borderDark focus:border-neonBlue focus:ring-1 focus:ring-neonBlue rounded-xl pl-9 pr-4 py-2 w-full text-xs text-gray-100 placeholder-gray-500 focus:outline-none transition duration-200"
                    />
                  </div>
                </div>

                <div className="overflow-x-auto border border-borderDark rounded-xl">
                  <table className="min-w-full divide-y divide-borderDark bg-cardBg/30 text-left text-sm text-gray-300">
                    <thead className="bg-cardBg text-xs text-gray-400 uppercase tracking-wider">
                      <tr>
                        <th className="px-6 py-3.5 font-semibold">SKU Name</th>
                        <th className="px-6 py-3.5 font-semibold">Category</th>
                        <th className="px-6 py-3.5 font-semibold">Current Stock</th>
                        <th className="px-6 py-3.5 font-semibold">Safety / Reorder Point</th>
                        <th className="px-6 py-3.5 font-semibold">Daily Demand</th>
                        <th className="px-6 py-3.5 font-semibold">Days to stockout</th>
                        <th className="px-6 py-3.5 font-semibold text-center">Stockout Risk</th>
                        <th className="px-6 py-3.5 font-semibold text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-borderDark">
                      {filteredInventory.map((k) => (
                        <tr key={k.sku_id} className="hover:bg-gray-800/30 transition">
                          <td className="px-6 py-4 font-semibold text-white">{k.name}</td>
                          <td className="px-6 py-4 text-gray-400">{k.category}</td>
                          <td className="px-6 py-4 font-mono font-medium">{k.current_stock} units</td>
                          <td className="px-6 py-4 text-xs font-mono text-gray-400">
                            {k.safety_stock} / {k.reorder_point}
                          </td>
                          <td className="px-6 py-4 font-mono text-gray-400">{k.average_daily_demand} /day</td>
                          <td className="px-6 py-4 font-mono font-medium">
                            {k.days_to_stockout === null || k.days_to_stockout === floatValue("inf") ? '∞' : `${k.days_to_stockout} days`}
                          </td>
                          <td className="px-6 py-4 text-center">
                            <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase ${
                              k.risk_level === 'critical' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                              k.risk_level === 'high' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                              k.risk_level === 'medium' ? 'bg-yellow-500/10 text-yellow-500/80 border border-yellow-500/20' :
                              k.risk_level === 'low' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                              'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            }`}>
                              {k.risk_level}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <button 
                              onClick={() => handleSuggestAlternates(k.name)}
                              className="text-xs bg-neonBlue/10 hover:bg-neonBlue/20 text-neonBlue px-3 py-1.5 rounded-lg border border-neonBlue/20 hover:border-neonBlue/40 transition duration-150"
                            >
                              Suggest Alternate
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Suggest alternate drawer */}
              {alternateSupplierData && (
                <div className="bg-cardBg border border-neonBlue/20 rounded-2xl p-5 space-y-4 shadow-[0_0_20px_rgba(59,130,246,0.05)]">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                        <Users className="w-4 h-4 text-neonBlue" />
                        <span>Alternative Suppliers for {alternateSupplierData.sku_name}</span>
                      </h3>
                      <p className="text-xs text-gray-400">Category: <span className="font-semibold text-gray-300">{alternateSupplierData.sku_category}</span> | Current Stock: <span className="font-mono text-gray-300">{alternateSupplierData.current_stock} units</span></p>
                    </div>
                    <button 
                      onClick={() => setAlternateSupplierData(null)}
                      className="text-xs text-gray-400 hover:text-white"
                    >
                      Dismiss
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {alternateSupplierData.suggested_suppliers.length === 0 ? (
                      <p className="text-sm text-gray-500">No alternate suppliers found for this category.</p>
                    ) : (
                      alternateSupplierData.suggested_suppliers.map((s, index) => (
                        <div key={s.supplier_id} className="bg-darkBg border border-borderDark rounded-xl p-4 space-y-2 relative overflow-hidden">
                          {index === 0 && (
                            <span className="absolute top-2 right-2 text-[10px] bg-neonEmerald/10 text-neonEmerald border border-neonEmerald/20 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
                              Safest Option
                            </span>
                          )}
                          <h4 className="text-sm font-bold text-white">{s.name}</h4>
                          <div className="text-xs space-y-1 text-gray-400 font-mono">
                            <p>Composite Risk: <span className="text-white font-bold">{s.composite_risk_score}</span></p>
                            <p>Financial Risk: {s.financial_risk}</p>
                            <p>Geopolitical Risk: {s.geopolitical_risk}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

            </div>
          )}

          {/* TAB 3: SUPPLY PARTNERS */}
          {activeTab === 'suppliers' && (
            <div className="flex flex-col space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                    <Users className="w-5 h-5 text-neonEmerald" />
                    <span>Active Supply Partners</span>
                  </h2>
                  <p className="text-xs text-gray-400">15 suppliers mapped to material categories and tracked by geopolitical, financial, and delay risks.</p>
                </div>

                <div className="relative max-w-xs w-full">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                    <Search className="w-4 h-4" />
                  </span>
                  <input 
                    type="text" 
                    placeholder="Search suppliers..."
                    value={supplierSearch}
                    onChange={(e) => setSupplierSearch(e.target.value)}
                    className="bg-cardBg border border-borderDark focus:border-neonEmerald focus:ring-1 focus:ring-neonEmerald rounded-xl pl-9 pr-4 py-2 w-full text-xs text-gray-100 placeholder-gray-500 focus:outline-none transition duration-200"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredSuppliers.map((s) => {
                  const isHighRisk = s.composite_risk_score >= 0.45;
                  return (
                    <div 
                      key={s.supplier_id} 
                      className={`bg-cardBg border rounded-2xl p-5 space-y-3 transition duration-200 ${
                        isHighRisk 
                          ? 'border-neonRose/20 hover:border-neonRose/40 shadow-[0_0_15px_rgba(244,63,94,0.02)]' 
                          : 'border-borderDark hover:border-gray-700'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                            <span>{s.name}</span>
                          </h3>
                          <span className="text-[10px] bg-gray-800 text-gray-300 border border-gray-700 px-2 py-0.5 rounded-full font-medium">
                            {s.category}
                          </span>
                        </div>
                        
                        <div className="text-right">
                          <span className="text-[10px] text-gray-500 font-mono block">COMPOSITE RISK</span>
                          <span className={`text-lg font-bold font-mono ${isHighRisk ? 'text-neonRose' : 'text-neonEmerald'}`}>
                            {s.composite_risk_score.toFixed(2)}
                          </span>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs font-mono border-t border-b border-borderDark/40 py-2.5 text-gray-400">
                        <div className="flex justify-between px-1">
                          <span>Financial Risk:</span>
                          <span className="text-white font-bold">{s.financial_risk.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between px-1 border-l border-borderDark/40">
                          <span>Geopolitical:</span>
                          <span className="text-white font-bold">{s.geopolitical_risk.toFixed(2)}</span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-xs text-gray-400 pt-0.5">
                        <span className="truncate">{s.contact_email}</span>
                        <a 
                          href={`mailto:${s.contact_email}`}
                          className="text-neonBlue hover:underline flex items-center space-x-0.5 font-medium"
                        >
                          <span>Email Ops</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 4: SHIPPING LOGISTICS DELAYS */}
          {activeTab === 'shipments' && (
            <div className="flex flex-col space-y-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                  <Truck className="w-5 h-5 text-neonRose" />
                  <span>Logistics Shipment Delays</span>
                </h2>
                <p className="text-xs text-gray-400">Shipments flagged as delayed or pending past delivery targets, evaluated for stockout risk impact.</p>
              </div>

              <div className="overflow-x-auto border border-borderDark rounded-xl">
                <table className="min-w-full divide-y divide-borderDark bg-cardBg/30 text-left text-sm text-gray-300">
                  <thead className="bg-cardBg text-xs text-gray-400 uppercase tracking-wider">
                    <tr>
                      <th className="px-6 py-3.5 font-semibold">SKU Component</th>
                      <th className="px-6 py-3.5 font-semibold">Quantity</th>
                      <th className="px-6 py-3.5 font-semibold">Origin Supplier</th>
                      <th className="px-6 py-3.5 font-semibold">Destination Warehouse</th>
                      <th className="px-6 py-3.5 font-semibold">Est. Delivery</th>
                      <th className="px-6 py-3.5 font-semibold">Status</th>
                      <th className="px-6 py-3.5 font-semibold text-center">Delay Stockout Impact</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-borderDark">
                    {shipments.map((sh) => (
                      <tr key={sh.shipment_id} className="hover:bg-gray-800/30 transition">
                        <td className="px-6 py-4 font-semibold text-white">{sh.sku_name}</td>
                        <td className="px-6 py-4 font-mono font-medium">{sh.quantity} units</td>
                        <td className="px-6 py-4 text-gray-300">{sh.supplier_name}</td>
                        <td className="px-6 py-4 text-gray-400">{sh.warehouse_name}</td>
                        <td className="px-6 py-4 font-mono text-gray-400">{sh.estimated_delivery_date}</td>
                        <td className="px-6 py-4">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                            sh.status === 'delayed' ? 'bg-neonRose/10 text-neonRose border border-neonRose/20' : 'bg-neonAmber/10 text-neonAmber border border-neonAmber/20'
                          }`}>
                            {sh.status} ({sh.days_overdue}d late)
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase ${
                            sh.delay_impact_level === 'critical' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                            sh.delay_impact_level === 'high' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                            sh.delay_impact_level === 'medium' ? 'bg-yellow-500/10 text-yellow-500/80 border border-yellow-500/20' :
                            'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          }`}>
                            {sh.delay_impact_level}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 5: REACTIVE OPERATIONS CHAT */}
          {activeTab === 'chat' && (
            <div className="flex flex-col h-[650px] bg-darkBg border border-borderDark rounded-2xl overflow-hidden">
              
              {/* Header */}
              <div className="bg-cardBg px-5 py-3 border-b border-borderDark flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-neonEmerald animate-ping"></div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Reactive Operations Agent</h3>
                    <p className="text-[10px] text-gray-400">Hand-rolled tool-use loop (Capped at 5 turns)</p>
                  </div>
                </div>
                
                <button 
                  onClick={() => setChatHistory([{
                    role: 'assistant',
                    text: "Hello! I am the Reactive Ops Agent. I can search live inventory, check supplier risks, analyze delayed shipments, recommend warehouse routing, and find alternate suppliers. How can I help you resolve a supply chain disruption today?",
                    steps: []
                  }])}
                  className="text-xs text-gray-400 hover:text-white hover:underline transition"
                >
                  Clear History
                </button>
              </div>

              {/* Message History */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {chatHistory.map((msg, index) => {
                  const isUser = msg.role === 'user';
                  return (
                    <div key={index} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1`}>
                      
                      {/* LLM Thought Trace (collapsible console) */}
                      {!isUser && msg.steps && msg.steps.length > 0 && (
                        <details className="w-full max-w-xl bg-gray-950/80 border border-borderDark rounded-xl overflow-hidden mb-2 text-xs font-mono text-gray-400">
                          <summary className="px-4 py-2 hover:bg-gray-900 cursor-pointer flex items-center justify-between text-[11px] text-gray-500 font-bold uppercase select-none">
                            <span className="flex items-center space-x-1.5">
                              <Terminal className="w-3.5 h-3.5 text-neonBlue" />
                              <span>Agent Loop Execution Trace ({msg.steps.length} turns)</span>
                            </span>
                            <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
                          </summary>
                          
                          <div className="p-4 border-t border-borderDark space-y-3 max-h-[300px] overflow-y-auto">
                            {msg.steps.map((step, sIdx) => (
                              <div key={sIdx} className="space-y-1">
                                <div className="text-[10px] text-gray-500 font-bold uppercase">
                                  {step.role.replace('_', ' ')}
                                </div>
                                <div className={`p-2 rounded font-mono text-[11px] leading-relaxed whitespace-pre-wrap ${
                                  step.role === 'thought' ? 'text-gray-300 bg-gray-900/40' :
                                  step.role === 'tool_call' ? 'text-neonBlue bg-neonBlue/5 border border-neonBlue/10' :
                                  'text-neonEmerald bg-neonEmerald/5 border border-neonEmerald/10'
                                }`}>
                                  {step.content}
                                </div>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}

                      {/* Bubble content */}
                      <div className={`max-w-xl rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                        isUser 
                          ? 'bg-neonBlue text-white font-medium rounded-tr-none shadow-[0_4px_12px_rgba(59,130,246,0.1)]' 
                          : 'bg-cardBg text-gray-200 border border-borderDark rounded-tl-none'
                      }`}>
                        <p className="whitespace-pre-wrap">{msg.text}</p>
                      </div>
                    </div>
                  );
                })}

                {chatLoading && (
                  <div className="flex flex-col items-start space-y-2">
                    <div className="bg-cardBg text-gray-400 border border-borderDark rounded-2xl rounded-tl-none px-4 py-3 text-sm flex items-center space-x-3">
                      <RefreshCw className="w-4 h-4 animate-spin text-neonBlue" />
                      <span>Agent is executing query loop...</span>
                    </div>
                  </div>
                )}
                
                <div ref={chatEndRef} />
              </div>

              {/* Sample queries tags */}
              <div className="px-5 py-2.5 bg-cardBg/20 border-t border-borderDark/40 flex flex-wrap gap-2">
                <span className="text-[10px] text-gray-500 font-semibold uppercase flex items-center pr-1">Try Sample:</span>
                {queries.map((q, qIdx) => (
                  <button 
                    key={qIdx}
                    onClick={() => { setChatInput(q); }}
                    className="text-[11px] bg-gray-800/60 hover:bg-gray-800 border border-borderDark text-gray-300 px-3 py-1 rounded-full transition duration-150"
                  >
                    {q}
                  </button>
                ))}
              </div>

              {/* Input Form */}
              <form onSubmit={handleChatSubmit} className="bg-cardBg border-t border-borderDark p-4 flex space-x-3">
                <input 
                  type="text" 
                  placeholder="Ask a supply chain, risk, or warehouse routing question..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={chatLoading}
                  className="bg-darkBg border border-borderDark focus:border-neonBlue focus:ring-1 focus:ring-neonBlue rounded-xl px-4 py-3 flex-1 text-sm text-gray-100 placeholder-gray-500 focus:outline-none transition disabled:opacity-50"
                />
                
                <button 
                  type="submit" 
                  disabled={chatLoading || !chatInput.trim()}
                  className="bg-neonBlue hover:bg-blue-600 disabled:bg-gray-800 disabled:text-gray-500 border border-neonBlue hover:border-blue-500 disabled:border-borderDark text-white px-5 rounded-xl flex items-center justify-center transition"
                >
                  <ArrowRight className="w-5 h-5" />
                </button>
              </form>
            </div>
          )}

        </main>
      </div>
      
      {/* ── FOOTER ── */}
      <footer className="border-t border-borderDark/60 py-4 px-6 mt-12 bg-cardBg/10 text-center text-xs text-gray-500">
        SupplySense Ops Center — Build v1.0.0. PostgreSQL Persistent Store. Real-time Multi-Turn Agent Loop.
      </footer>
    </div>
  );
}

// Helper to represent python infinity locally in js
function floatValue(val) {
  return val;
}
