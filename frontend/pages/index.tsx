import LedgerTable from "../components/LedgerTable";
import LiveConsole from "../components/LiveConsole";
import Image from "next/image";
import Head from "next/head";

export default function Home() {
  return (
    <>
      <Head>
        <link rel="icon" href="/favicon.ico"/>
        <title> Earlybird AI | Live Ledger </title>
      </Head>
      <div className="p-5">
        <section className="mt-10 bg-gray-50 p-6 rounded shadow-sm text-gray-700 text-sm">
        <Image src="/earlybirdai.png" alt="Earlybird AI" width={120} height={60} />
        <LedgerTable />
        <LiveConsole /> 
          <h2 className="text-lg font-semibold mb-3">Proof of Concept Explanation</h2>
          <p className="mb-2">
            This Live Ledger POC is built with a modern, full-stack architecture designed to process emails in real-time, classify expense data, and display it dynamically.
          </p>
          <ul className="list-disc list-inside space-y-1 mb-3">
            <li><strong>Backend:</strong> FastAPI (Python) handles email polling, NLP classification via OpenRouter, database operations (PostgreSQL), and publishes updates to Redis.</li>
            <li><strong>WebSocket Server:</strong> Node.js subscribes to Redis pub/sub to broadcast live ledger updates to connected clients.</li>
            <li><strong>Frontend:</strong> Next.js (React) displays ledger data with live updates, styled using Tailwind CSS for responsive UI.</li>
            <li><strong>Database:</strong> PostgreSQL stores structured ledger entries persistently.</li>
            <li><strong>Messaging & Caching:</strong> Redis enables fast pub/sub communication between backend and websocket server.</li>
            <li><strong>Deployment:</strong> Docker Compose orchestrates the multi-service app on your own premises, ensuring easy setup and scalability.</li>
          </ul>
          <p>
            The directory structure is organized for clarity and separation of concerns, with independent backend, websocket, and frontend services.
          </p>
          <p className="mt-6 italic text-xs text-gray-500">
            &mdash; Made with ⚡ by Muhammad Ryanrahmadifa
          </p>
        </section>
      </div>
    </>
  );
}
