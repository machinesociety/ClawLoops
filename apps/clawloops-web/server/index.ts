import express from "express";
import { createServer } from "http";
import path from "path";
import { fileURLToPath } from "url";
import * as fs from "fs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const server = createServer(app);

  // Serve static files from dist/public in production
  const staticPath = path.resolve(__dirname, "public");
  // Check if static path exists
  if (!fs.existsSync(staticPath)) {
    throw new Error(`Static path does not exist: ${staticPath}`);
  }

  // Serve static files first
  app.use(express.static(staticPath));

  // Handle client-side routing - serve index.html for all routes except static assets
  app.get("/static-path", (_req, res) => {
    res.send(`Static path: ${staticPath}`);
  });
  
  // Only serve index.html for routes that don't match static files
  app.get("*", (_req, res) => {
    res.sendFile(path.join(staticPath, "index.html"));
  });

  const port = process.env.PORT || 3000;

  server.listen(port, () => {
    console.log(`Server running on http://localhost:${port}/`);
  });
}

startServer().catch(console.error);
