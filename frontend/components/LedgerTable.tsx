import { useEffect, useState } from "react";
import { Search, Filter, ArrowUpDown, TrendingUp, TrendingDown } from "lucide-react";
import { io } from "socket.io-client";


export type LedgerEntry = {
  text: string;
  date: string;
  amount: number;
  currency: string;
  vendor: string;
  ttype: string;
  referenceid: string;
  label: string;
  fingerprint: string;
};

export default function LedgerTable() {
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<string>("date");
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  useEffect(() => {
    const socket = io(process.env.NEXT_PUBLIC_SOCKET_URL || "http://localhost:3001");

    const handleUpdate = (entry: LedgerEntry) => {
      if (!entry.fingerprint) return;

      setLedger((prev) => {
        const fingerprint = entry.fingerprint.trim();
        const existsByFingerprint = prev.some(e => e.fingerprint?.trim() === fingerprint);
        
        if (existsByFingerprint) {
          console.log("Duplicate by fingerprint:", fingerprint);
          return prev;
        }
        
        const existsByContent = prev.some(e => 
          e.vendor === entry.vendor &&
          e.amount === entry.amount &&
          e.date === entry.date &&
          e.referenceid === entry.referenceid
        );
        
        if (existsByContent) {
          console.log("Duplicate by content for:", entry.vendor, entry.amount);
          return prev;
        }
        
        return [entry, ...prev];
      });
    };

    socket.on("ledger_update", handleUpdate);
    socket.on("connect", () => console.log("Connected to WebSocket server"));
    socket.on("disconnect", () => console.warn("Disconnected from WebSocket server"));

    return () => {
      socket.off("ledger_update", handleUpdate);
      socket.disconnect();
    };
  }, []);


  const filteredLedger = ledger
    .filter((entry) =>
      filter === "all" ? true : entry.label.toLowerCase() === filter
    )
    .filter((entry) =>
      entry.text.toLowerCase().includes(search.toLowerCase()) ||
      entry.vendor.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      if (sortKey === "amount") {
        return sortAsc ? a.amount - b.amount : b.amount - a.amount;
      }
      if (sortKey === "date") {
        return sortAsc
          ? new Date(a.date).getTime() - new Date(b.date).getTime()
          : new Date(b.date).getTime() - new Date(a.date).getTime();
      }
      return 0;
    });

  const formatAmount = (amount: number, currency: string) => {
    const safeAmount = typeof amount === "number" && !isNaN(amount) ? amount : 0;
    const safeCurrency = /^[A-Z]{3}$/.test(currency || "") ? currency : "SGD";

    const formattedNumber = new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(safeAmount);

    return `${safeCurrency} ${formattedNumber}`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const getCategoryColor = (label: string) => {
    const colors = {
      travel: 'bg-blue-50 text-blue-700 border-blue-200',
      meals_and_entertainment: 'bg-green-50 text-green-700 border-green-200',
      office: 'bg-purple-50 text-purple-700 border-purple-200',
      saas: 'bg-orange-50 text-orange-700 border-orange-200',
      transport: 'bg-green-50 text-green-700 border-green-200',
      other: 'bg-gray-50 text-gray-700 border-gray-200'
    };
    const normalized = label.trim().toLowerCase();
    return colors[normalized as keyof typeof colors] || colors.other;
  };

  const totalPerCurrency = filteredLedger.reduce((acc, entry) => {
    acc[entry.currency] = (acc[entry.currency] || 0) + entry.amount;
    return acc;
  }, {} as Record<string, number>);


  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Transaction Ledger</h1>
          <p className="text-gray-600">Monitor and analyze your financial transactions in real-time</p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex flex-wrap gap-4 items-center">
            {/* Search */}
            <div className="relative flex-1 min-w-64">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search transactions..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              />
            </div>

            {/* Filter */}
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="pl-10 pr-8 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none bg-white min-w-40"
              >
                <option value="all">All Categories</option>
                <option value="travel">Travel</option>
                <option value="meals_and_entertainment">Meals & Entertainment</option>
                <option value="office">Office</option>
                <option value="transport">Transport</option>
                <option value="saas">SaaS</option>
                <option value="other">Other</option>
              </select>
            </div>

            {/* Sort Controls */}
            <div className="flex gap-2">
              <button
                onClick={() => setSortKey("date")}
                className={`px-4 py-3 rounded-xl font-medium transition-all ${
                  sortKey === "date" 
                    ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/25' 
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Date
              </button>
              <button
                onClick={() => setSortKey("amount")}
                className={`px-4 py-3 rounded-xl font-medium transition-all ${
                  sortKey === "amount" 
                    ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/25' 
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Amount
              </button>
              <button
                onClick={() => setSortAsc((prev) => !prev)}
                className="px-4 py-3 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 transition-all flex items-center gap-2"
              >
                {sortAsc ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                {sortAsc ? "Asc" : "Desc"}
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
          {filteredLedger.length === 0 ? (
            <div className="text-center py-16">
              <div className="text-gray-400 mb-4">
                <ArrowUpDown className="w-12 h-12 mx-auto" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No transactions yet</h3>
              <p className="text-gray-600">Transactions will appear here as they're processed in real-time</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50/50">
                  <tr>
                    <th className="text-left py-4 px-6 font-semibold text-gray-900">Date</th>
                    <th className="text-left py-4 px-6 font-semibold text-gray-900">Vendor</th>
                    <th className="text-right py-4 px-6 font-semibold text-gray-900">Amount</th>
                    <th className="text-left py-4 px-6 font-semibold text-gray-900">Category</th>
                    <th className="text-left py-4 px-6 font-semibold text-gray-900">Type</th>
                    <th className="text-left py-4 px-6 font-semibold text-gray-900">Reference</th>
                    <th className="text-left py-4 px-6 font-semibold text-gray-900">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredLedger.map((entry, i) => (
                    <tr key={entry.referenceid} className="hover:bg-gray-50/50 transition-colors">
                      <td className="py-4 px-6 text-sm text-gray-900 font-medium">
                        {formatDate(entry.date)}
                      </td>
                      <td className="py-4 px-6">
                        <div className="font-medium text-gray-900">{entry.vendor}</div>
                      </td>
                      <td className="py-4 px-6 text-right">
                        <span className="font-semibold text-gray-900 text-lg">
                          {formatAmount(entry.amount, entry.currency)}
                        </span>
                      </td>
                      <td className="py-4 px-6">
                        <span className={`inline-flex px-3 py-1 rounded-full text-xs font-medium border capitalize ${getCategoryColor(entry.label)}`}>
                          {entry.label}
                        </span>
                      </td>
                      <td className="py-4 px-6">
                        <span className="text-sm text-gray-600 capitalize">{entry.ttype}</span>
                      </td>
                      <td className="py-4 px-6">
                        <span className="text-sm font-mono text-gray-500 bg-gray-50 px-2 py-1 rounded">
                          {entry.referenceid}
                        </span>
                      </td>
                      <td className="py-4 px-6 max-w-xs">
                        <div className="text-sm text-gray-600 truncate" title={entry.text}>
                          {entry.text.length > 60 ? entry.text.slice(0, 60) + '...' : entry.text}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Summary */}
        {filteredLedger.length > 0 && (
          <div className="mt-6 bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Summary</h3>
                <p className="text-gray-600">Showing {filteredLedger.length} transaction{filteredLedger.length !== 1 ? 's' : ''}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-600">Total Amount</p>
                <p className="text-2xl font-bold text-gray-900">
                  {Object.entries(totalPerCurrency).map(([currency, total]) => (
                    <p key={currency} className="text-sm text-gray-700">
                      Total in {currency}: <strong>{formatAmount(total as number, currency)}</strong>
                    </p>
                  ))}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}