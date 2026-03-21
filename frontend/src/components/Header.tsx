"use client";

interface HeaderProps {
  showTrace: boolean;
  onToggleTrace: () => void;
  uploadedCount: number;
  onToggleUpload: () => void;
}

export function Header({ showTrace, onToggleTrace, uploadedCount, onToggleUpload }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-[#0a0a0a]">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
          <span className="text-white font-bold text-sm">DP</span>
        </div>
        <div>
          <h1 className="text-lg font-semibold text-white">DataPilot</h1>
          <p className="text-xs text-gray-500">
            Multi-Agent Business Intelligence
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-xs text-gray-400">4 Agents Online</span>
        </div>
        <button
          onClick={onToggleUpload}
          className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors bg-gray-800 text-gray-400 hover:text-white flex items-center gap-1.5"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Docs{uploadedCount > 0 && ` (${uploadedCount})`}
        </button>
        <button
          onClick={onToggleTrace}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            showTrace
              ? "bg-primary-600 text-white"
              : "bg-gray-800 text-gray-400 hover:text-white"
          }`}
        >
          Agent Trace
        </button>
      </div>
    </header>
  );
}
