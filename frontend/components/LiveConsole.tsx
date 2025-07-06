import { useEffect, useState, useRef } from "react";
import { Activity, Circle, Zap, ChevronDown, ChevronUp, Terminal } from "lucide-react";
import io from "socket.io-client";

export default function LiveConsole() {
  const [logs, setLogs] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const socket = io(process.env.NEXT_PUBLIC_SOCKET_URL || "http://localhost:3001");
    console.log("Setting up socket connection...");

    socket.on("connect", () => {
      console.log("Socket connected");
      setIsConnected(true);
    });

    socket.on("disconnect", () => {
      console.log("Socket disconnected");
      setIsConnected(false);
    });

    socket.on("log_stream", (msg) => {
      console.log("Received log_stream:", msg);
      console.log("msg.log:", msg.log);
      setLogs((prev) => {
        const newLogs = [...prev.slice(-299), msg.log ?? JSON.stringify(msg)];
        return newLogs;
      });
    });

    return () => {
      socket.off("log_stream");
      socket.off("connect");
      socket.off("disconnect");
      socket.disconnect();
      console.log("Socket disconnected and cleaned up");
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current && isExpanded) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isExpanded]);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-sm border-t border-stone-200 shadow-2xl">
      {/* Toggle Header */}
      <div 
        className="px-6 py-3 cursor-pointer hover:bg-stone-50/50 transition-all duration-200 select-none"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <Terminal className="h-4 w-4 text-stone-600" />
              <h3 className="text-stone-800 font-medium text-sm">Live Console</h3>
            </div>
            <div className="flex items-center space-x-2">
              <Circle 
                className={`h-2 w-2 ${isConnected ? 'text-emerald-500 fill-emerald-500' : 'text-red-400 fill-red-400'}`} 
              />
              <span className="text-xs text-stone-500">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-xs text-stone-500">
              <Zap className="h-3 w-3" />
              <span>{logs.length} events</span>
            </div>
            <div className="flex items-center space-x-1 text-stone-600">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronUp className="h-4 w-4" />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Expandable Console Content */}
      <div 
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="border-t border-stone-200">
          <div 
            ref={scrollRef}
            className="bg-stone-50/30 text-stone-700 font-mono text-xs p-4 h-80 overflow-y-auto"
            style={{
              scrollbarWidth: 'thin',
              scrollbarColor: '#d6d3d1 #f5f5f4'
            }}
          >
            {logs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-stone-400">
                <div className="text-center">
                  <Activity className="h-8 w-8 mx-auto mb-3 opacity-40" />
                  <p className="text-sm">Waiting for log stream...</p>
                </div>
              </div>
            ) : (
              logs.map((line, idx) => (
                <div 
                  key={idx} 
                  className="py-1 hover:bg-stone-100/50 transition-colors duration-150 rounded px-2 -mx-2 border-l-2 border-transparent hover:border-stone-300"
                >
                  <span className="text-stone-800 leading-relaxed">{line}</span>
                </div>
              ))
            )}
          </div>
        </div>
        
        {/* Mini Footer when expanded */}
        {isExpanded && (
          <div className="bg-stone-50/50 border-t border-stone-200 px-4 py-2">
            <div className="flex items-center justify-between text-xs text-stone-500">
              <span>Real-time log monitoring</span>
              <span>
                {logs.length > 0 ? `Last: ${new Date().toLocaleTimeString()}` : 'No activity'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}