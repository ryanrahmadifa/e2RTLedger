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


subscriber.connect().catch(console.error);
subscriber.subscribe("ledger_updates", (message) => {
  io.emit("ledger_update", JSON.parse(message));
});

subscriber.subscribe("log_stream", (message) => {
  io.emit("log_stream", JSON.parse(message));
});


io.on("connection", (socket) => {
  console.log("User connected to WebSocket");
});

server.listen(3001, () => {
  console.log("WebSocket server running on port 3001");
});
