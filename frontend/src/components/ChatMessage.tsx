"use client";

interface Source {
  source_type: string;
  source_name: string;
  details: string;
}

interface MessageProps {
  message: {
    role: "user" | "assistant";
    content: string;
    confidence?: number;
    sources?: Source[];
    duration_ms?: number;
    status?: string;
    trace?: unknown[];
  };
  onSelectTrace?: () => void;
}

function ConfidenceBadge({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  const color =
    percent >= 80
      ? "text-green-400 bg-green-400/10"
      : percent >= 50
      ? "text-yellow-400 bg-yellow-400/10"
      : "text-red-400 bg-red-400/10";

  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${color}`}>
      {percent}% confidence
    </span>
  );
}

export function ChatMessage({ message, onSelectTrace }: MessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-primary-600 text-white"
            : "bg-gray-900 border border-gray-800 text-gray-100"
        }`}
      >
        {/* Message content */}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content}
        </div>

        {/* Metadata bar for assistant messages */}
        {!isUser && (message.confidence || message.sources?.length || message.duration_ms) && (
          <div className="mt-3 pt-2 border-t border-gray-800 flex flex-wrap items-center gap-2">
            {message.confidence !== undefined && message.confidence > 0 && (
              <ConfidenceBadge value={message.confidence} />
            )}
            {message.duration_ms !== undefined && (
              <span className="text-xs text-gray-500">
                {message.duration_ms > 1000
                  ? `${(message.duration_ms / 1000).toFixed(1)}s`
                  : `${message.duration_ms}ms`}
              </span>
            )}
            {message.trace && message.trace.length > 0 && (
              <button
                onClick={onSelectTrace}
                className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
              >
                View trace ({message.trace.length} steps)
              </button>
            )}
          </div>
        )}

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.sources.map((source, i) => (
              <div
                key={i}
                className="text-xs text-gray-500 flex items-center gap-1"
              >
                <span className="text-primary-500">
                  {source.source_type === "sql_query" ? "DB" :
                   source.source_type === "document" ? "DOC" : "CALC"}
                </span>
                <span>{source.source_name}</span>
                {source.details && (
                  <span className="text-gray-600 truncate max-w-[200px]">
                    - {source.details}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
