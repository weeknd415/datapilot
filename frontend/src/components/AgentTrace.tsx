"use client";

interface TraceStep {
  agent: string;
  action: string;
  input_summary: string;
  output_summary: string;
  confidence: number;
  duration_ms: number;
}

interface AgentTraceProps {
  steps: TraceStep[];
}

const AGENT_COLORS: Record<string, string> = {
  supervisor: "border-purple-500 bg-purple-500/10",
  sql_agent: "border-blue-500 bg-blue-500/10",
  document_agent: "border-amber-500 bg-amber-500/10",
  analytics_agent: "border-green-500 bg-green-500/10",
};

const AGENT_LABELS: Record<string, string> = {
  supervisor: "Supervisor",
  sql_agent: "SQL Agent",
  document_agent: "Document Agent",
  analytics_agent: "Analytics Agent",
};

const ACTION_LABELS: Record<string, string> = {
  route_query: "Routing Query",
  generate_sql: "Generating SQL",
  execute_sql: "Executing Query",
  explain_results: "Explaining Results",
  search_documents: "Searching Documents",
  analyze_documents: "Analyzing Documents",
  extract_structured_data: "Extracting Data",
  analyze_data: "Analyzing Data",
  generate_chart: "Generating Chart",
  synthesize: "Synthesizing Answer",
};

export function AgentTrace({ steps }: AgentTraceProps) {
  if (steps.length === 0) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">
          Agent Trace
        </h3>
        <p className="text-xs text-gray-600">
          Ask a question to see the agent execution trace here. Each step
          shows which agent handled the query, what action it took, and
          its confidence level.
        </p>
      </div>
    );
  }

  const totalDuration = steps.reduce((sum, s) => sum + s.duration_ms, 0);

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-300">Agent Trace</h3>
        <span className="text-xs text-gray-500">
          {steps.length} steps |{" "}
          {totalDuration > 1000
            ? `${(totalDuration / 1000).toFixed(1)}s`
            : `${totalDuration}ms`}
        </span>
      </div>

      <div className="space-y-3">
        {steps.map((step, i) => (
          <div
            key={i}
            className={`step-animate border-l-2 pl-3 py-2 ${
              AGENT_COLORS[step.agent] || "border-gray-600 bg-gray-800/50"
            } rounded-r-lg`}
            style={{ animationDelay: `${i * 100}ms` }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-gray-200">
                {AGENT_LABELS[step.agent] || step.agent}
              </span>
              <span className="text-xs text-gray-500">
                {step.duration_ms}ms
              </span>
            </div>
            <div className="text-xs text-gray-400 mb-1">
              {ACTION_LABELS[step.action] || step.action}
            </div>
            {step.output_summary && (
              <div className="text-xs text-gray-500 truncate">
                {step.output_summary}
              </div>
            )}
            {step.confidence > 0 && (
              <div className="mt-1 flex items-center gap-1">
                <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      step.confidence >= 0.8
                        ? "bg-green-500"
                        : step.confidence >= 0.5
                        ? "bg-yellow-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${step.confidence * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-600">
                  {Math.round(step.confidence * 100)}%
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Agent legend */}
      <div className="mt-6 pt-4 border-t border-gray-800">
        <h4 className="text-xs font-medium text-gray-500 mb-2">Agents</h4>
        <div className="space-y-1">
          {Object.entries(AGENT_LABELS).map(([key, label]) => (
            <div key={key} className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  key === "supervisor"
                    ? "bg-purple-500"
                    : key === "sql_agent"
                    ? "bg-blue-500"
                    : key === "document_agent"
                    ? "bg-amber-500"
                    : "bg-green-500"
                }`}
              />
              <span className="text-xs text-gray-500">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
