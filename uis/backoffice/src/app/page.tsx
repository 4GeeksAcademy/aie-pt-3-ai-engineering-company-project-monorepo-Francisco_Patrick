"use client";

import React, { useState, useRef } from "react";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const analyzeFile = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://localhost:8000/api/incidents/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const data = await response.json();
      setResults(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadCSV = () => {
    window.location.href = "http://localhost:8000/api/incidents/results/export";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-black text-white font-sans p-8 selection:bg-blue-500 selection:text-white">
      <div className="max-w-5xl mx-auto space-y-12">
        <header className="text-center space-y-4">
          <h1 className="text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
            TrackFlow Incident Analyzer
          </h1>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Upload your incident reports CSV to generate real-time metrics, detect anomalies, and track operational health securely.
          </p>
        </header>

        <main className="space-y-12">
          {/* Upload Section */}
          <section
            className={`border-2 border-dashed rounded-3xl p-12 text-center transition-all duration-300 ease-in-out backdrop-blur-md bg-white/5 
            ${file ? 'border-blue-500 bg-blue-500/10' : 'border-gray-700 hover:border-blue-400 hover:bg-white/10'}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
          >
            <input
              type="file"
              accept=".csv"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileChange}
            />
            <div className="space-y-6">
              <div className="w-20 h-20 mx-auto bg-blue-500/20 rounded-full flex items-center justify-center border border-blue-500/30">
                <svg className="w-10 h-10 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div>
                <h3 className="text-2xl font-semibold mb-2">
                  {file ? file.name : "Drag and drop your CSV here"}
                </h3>
                <p className="text-gray-400">or click to browse from your computer</p>
              </div>
              <button
                onClick={() => !file ? fileInputRef.current?.click() : analyzeFile()}
                disabled={loading}
                className={`px-8 py-3 rounded-full font-semibold transition-all duration-300 shadow-lg ${
                  loading
                    ? "bg-gray-600 cursor-not-allowed"
                    : "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 hover:shadow-blue-500/25 hover:scale-105 transform"
                }`}
              >
                {loading ? "Analyzing..." : file ? "Run Analysis" : "Browse Files"}
              </button>
            </div>
            {error && (
              <div className="mt-6 p-4 bg-red-500/20 border border-red-500/50 rounded-xl text-red-200">
                <span className="font-bold">Error:</span> {error}
              </div>
            )}
          </section>

          {/* Results Section */}
          {results && (
            <section className="animate-in slide-in-from-bottom-8 duration-700 fade-in space-y-8">
              <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                <h2 className="text-3xl font-bold">Analysis Results</h2>
                <button
                  onClick={downloadCSV}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-full bg-white/10 hover:bg-white/20 border border-white/10 transition-all shadow-lg backdrop-blur-sm"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export CSV
                </button>
              </div>

              {/* Top Metrics */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-xl shadow-2xl relative overflow-hidden group">
                  <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                  <p className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">Total Processed</p>
                  <p className="text-5xl font-bold text-white">{results.metrics.total_processed}</p>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-xl shadow-2xl relative overflow-hidden group">
                   <div className="absolute inset-0 bg-gradient-to-br from-green-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                  <p className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">Valid Records</p>
                  <p className="text-5xl font-bold text-green-400">{results.metrics.valid_records}</p>
                </div>
                <div className={`border rounded-3xl p-6 backdrop-blur-xl shadow-2xl relative overflow-hidden group ${results.metrics.invalid_records > 0 ? 'bg-red-500/10 border-red-500/30' : 'bg-white/5 border-white/10'}`}>
                  <p className="text-gray-400 text-sm font-medium uppercase tracking-wider mb-2">Invalid Records</p>
                  <p className={`text-5xl font-bold ${results.metrics.invalid_records > 0 ? 'text-red-400' : 'text-white'}`}>
                    {results.metrics.invalid_records}
                  </p>
                </div>
              </div>

              {/* Breakdowns */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-xl shadow-2xl">
                  <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
                    <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" /></svg>
                    By Category
                  </h3>
                  <div className="space-y-4">
                    {Object.entries(results.metrics.category_breakdown).map(([cat, count]: [string, any]) => (
                      <div key={cat} className="flex justify-between items-center group">
                        <span className="text-gray-300 capitalize">{cat.replace("_", " ")}</span>
                        <span className="bg-white/10 text-white px-3 py-1 rounded-full font-mono text-sm group-hover:bg-purple-500/20 group-hover:text-purple-300 transition-colors">
                          {count}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-xl shadow-2xl">
                  <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
                    <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    By Status
                  </h3>
                  <div className="space-y-4">
                    {Object.entries(results.metrics.status_breakdown).map(([status, count]: [string, any]) => (
                      <div key={status} className="flex justify-between items-center group">
                        <span className="text-gray-300 capitalize">{status}</span>
                        <span className="bg-white/10 text-white px-3 py-1 rounded-full font-mono text-sm group-hover:bg-blue-500/20 group-hover:text-blue-300 transition-colors">
                          {count}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Avg Satisfaction */}
              <div className="bg-gradient-to-r from-blue-900/40 to-purple-900/40 border border-white/10 rounded-3xl p-8 flex items-center justify-between backdrop-blur-xl">
                <div>
                  <h3 className="text-xl font-bold text-white mb-1">Average Satisfaction Index</h3>
                  <p className="text-gray-400 text-sm">Based on closed tickets with recorded scores</p>
                </div>
                <div className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
                  {results.metrics.average_satisfaction_index} <span className="text-2xl text-gray-500 font-medium">/ 5</span>
                </div>
              </div>

              {/* Diagnostics */}
              {results.metrics.invalid_records > 0 && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-3xl p-8 backdrop-blur-xl">
                  <h3 className="text-xl font-bold text-red-400 mb-4 flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                    Invalid Records Detected ({results.metrics.invalid_records})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-gray-300">
                      <thead className="bg-red-500/20 text-red-200">
                        <tr>
                          <th className="px-4 py-3 rounded-tl-lg">Row</th>
                          <th className="px-4 py-3">Record ID</th>
                          <th className="px-4 py-3 rounded-tr-lg">Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.diagnostics.invalid_sample.map((inv: any, idx: number) => (
                          <tr key={idx} className="border-b border-red-500/20 last:border-0 hover:bg-red-500/5 transition-colors">
                            <td className="px-4 py-3 font-mono">{inv.row}</td>
                            <td className="px-4 py-3 font-mono text-gray-400">{inv.id}</td>
                            <td className="px-4 py-3">{inv.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {results.metrics.invalid_records > results.diagnostics.invalid_sample.length && (
                    <p className="text-sm text-red-400/70 mt-4 text-center">Showing first {results.diagnostics.invalid_sample.length} invalid records.</p>
                  )}
                </div>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
