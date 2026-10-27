"use client";

import { useEffect, useState } from "react";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";
import { Navigation } from "../../components/navigation";

type McpTool = {
  name: string;
  description: string;
  category: string;
  risk: string;
  required_permission: string;
};

export default function ModelContextProtocolPage() {
  const [tools, setTools] = useState<McpTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadTools() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/proxy/tools", {
          signal: controller.signal,
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        const data = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(
            typeof data?.detail === "string"
              ? data.detail
              : `Unable to load Model Context Protocol tools (${response.status}).`,
          );
        }
        setTools(data as McpTool[]);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Unable to load Model Context Protocol tools.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadTools();
    return () => controller.abort();
  }, []);

  return (
    <div className="shell" style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <div style={{ display: "flex", flex: 1, minWidth: 0 }}>
        <Navigation />
        <div className="main" style={{ flex: 1, minWidth: 0, background: "#060b14" }}>
          <main className="main-content" style={{ padding: "32px 40px", maxWidth: "1600px" }}>
            <ContextGuard featureName="Model Context Protocol tools" permission="tools:read">
              <GlobalContextSelector />
              <section className="page-heading">
                <div>
                  <h1>Model Context Protocol</h1>
                  <p className="lede">Available tool definitions and their access requirements.</p>
                </div>
              </section>

              {loading && <p className="data-note" role="status">Loading available tools…</p>}
              {error && (
                <section className="panel error-panel" role="alert">
                  <p>{error}</p>
                </section>
              )}
              {!loading && !error && tools.length === 0 && (
                <section className="panel">
                  <p>No tools are currently available in this workspace.</p>
                </section>
              )}
              {!loading && !error && tools.length > 0 && (
                <section className="mcp-tool-list" aria-label="Available MCP tools">
                  {tools.map((tool) => (
                    <article className="panel mcp-tool-card" key={tool.name}>
                      <div>
                        <h2>{tool.name}</h2>
                        <p>{tool.description}</p>
                      </div>
                      <dl>
                        <div><dt>Category</dt><dd>{tool.category}</dd></div>
                        <div><dt>Risk</dt><dd>{tool.risk.replaceAll("_", " ")}</dd></div>
                        <div><dt>Required permission</dt><dd>{tool.required_permission}</dd></div>
                      </dl>
                    </article>
                  ))}
                </section>
              )}
            </ContextGuard>
          </main>
        </div>
      </div>
    </div>
  );
}
