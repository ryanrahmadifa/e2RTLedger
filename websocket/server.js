const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const redis = require("redis");

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: "*" },
});

const subscriber = redis.createClient({
  socket: {
    host: 'redis',
    port: 6379,
  }
});

const seenFingerprints = new Set();

(async () => {
  await subscriber.connect();

  await subscriber.subscribe("ledger_updates", (message) => {
    try {
      const entry = JSON.parse(message);

      if (seenFingerprints.has(entry.fingerprint)) {
        return;
      }
      seenFingerprints.add(entry.fingerprint);

      io.emit("ledger_update", entry);

    } catch (e) {
      console.error("Failed to parse ledger_updates message", e);
    }
  });

  await subscriber.subscribe("log_stream", (message) => {
    try {
      io.emit("log_stream", JSON.parse(message));
    } catch (e) {
      console.error("Failed to parse log_stream message", e);
    }
  });
})();

io.on("connection", (socket) => {
  console.log("User connected to WebSocket");
});

server.listen(3001, () => {
  console.log("WebSocket server running on port 3001");
});
