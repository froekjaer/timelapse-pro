// ═══════════════════════════════════════════════════════════════════════════
// TimeLapse Pro — RedactionPage.tsx (Kundevendt UI)
// ───────────────────────────────────────────────────────────────────────────
// Version : 1.0.0
// Dato    : 2026-07-07
// ═══════════════════════════════════════════════════════════════════════════
/**
 * GDPR Redaction Workflow UI
 *
 * Muliggør:
 *  - Analyse af billeder for GDPR data (ansigter, nummerplader)
 *  - Redaction/sløring af detekterede områder
 *  - Review og approval af redacted billeder
 *
 * Krav: UI-010 (Sløring/redaction workflow)
 */

import { useState, useEffect } from "react";
import { InfoTooltip } from "../components/InfoTooltip";

interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
  confidence: number;
}

interface PIIDetections {
  faces: BoundingBox[];
  license_plates: BoundingBox[];
  has_pii: boolean;
}

interface RedactionStatus {
  capture_id: number;
  device_id: string;
  filename: string;
  redaction_status: string;
  has_gdpr_data: boolean | null;
  gdpr_detections: PIIDetections | null;
  redacted_at: string | null;
  redacted_by: string | null;
}

interface PendingListResponse {
  total: number;
  pending_analysis: number;
  detected_pii: number;
  items: RedactionStatus[];
}

export default function RedactionPage() {
  const [pendingData, setPendingData] = useState<PendingListResponse | null>(null);
  const [selectedCapture, setSelectedCapture] = useState<RedactionStatus | null>(null);
  const [analysisResult, setAnalysisResult] = useState<PIIDetections | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("detected");

  useEffect(() => {
    loadPending();
  }, [statusFilter]);

  const loadPending = async () => {
    try {
      setLoading(true);
      const url = statusFilter
        ? `/api/redaction/pending?status_filter=${statusFilter}`
        : "/api/redaction/pending";
      const res = await fetch(url);
      if (!res.ok) throw new Error("Kunne ikke indlæse afventende billeder");
      const data = await res.json();
      setPendingData(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const analyzeCapture = async (captureId: number) => {
    try {
      setLoading(true);
      const res = await fetch(`/api/redaction/analyze/${captureId}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Analyse fejlede");
      const data = await res.json();
      setAnalysisResult(data.detections);
      setSelectedCapture((prev) => (prev ? { ...prev, redaction_status: data.redaction_status } : null));
      await loadPending(); // Refresh list
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const redactCapture = async (captureId: number) => {
    if (!confirm("Er du sikker på at du vil sløre dette billede? Handlingen kan ikke fortrydes.")) {
      return;
    }
    try {
      setLoading(true);
      const res = await fetch(`/api/redaction/redact/${captureId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blur_kernel: 51, blur_sigma: 30, auto_approve: false }),
      });
      if (!res.ok) throw new Error("Sløring fejlede");
      await loadPending();
      await loadCaptureStatus(captureId); // Refresh selected
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const approveCapture = async (captureId: number) => {
    try {
      setLoading(true);
      const res = await fetch(`/api/redaction/approve/${captureId}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Godkendelse fejlede");
      await loadPending();
      await loadCaptureStatus(captureId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadCaptureStatus = async (captureId: number) => {
    try {
      const res = await fetch(`/api/redaction/status/${captureId}`);
      if (!res.ok) return;
      const data = await res.json();
      setSelectedCapture(data);
    } catch (e) {
      console.error("Failed to load capture status", e);
    }
  };

  const selectCapture = (item: RedactionStatus) => {
    setSelectedCapture(item);
    setAnalysisResult(item.gdpr_detections);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending": return "bg-yellow-100 text-yellow-800";
      case "analyzed": return "bg-green-100 text-green-800";
      case "detected": return "bg-red-100 text-red-800";
      case "redacted": return "bg-blue-100 text-blue-800";
      case "skipped": return "bg-gray-100 text-gray-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "pending": return "Afventer";
      case "analyzed": return "Analyseret (OK)";
      case "detected": return "GDPR fundet";
      case "redacted": return "Sløret";
      case "skipped": return "Sprunget over";
      default: return status;
    }
  };

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          Fejl: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">GDPR Slørings-workflow</h1>
        <p className="text-gray-600">
          Analyser og slør ansigter og nummerplader i overensstemmelse med GDPR.
        </p>
      </div>

      {/* Stats */}
      {pendingData && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm text-gray-500">Total ikke-slørede</div>
            <div className="text-2xl font-bold">{pendingData.total}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm text-gray-500">Afventer analyse</div>
            <div className="text-2xl font-bold text-yellow-600">{pendingData.pending_analysis}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm text-gray-500">GDPR data fundet</div>
            <div className="text-2xl font-bold text-red-600">{pendingData.detected_pii}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm text-gray-500">Filtrer</div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
            >
              <option value="detected">Kun GDPR-detektioner</option>
              <option value="pending">Afventer analyse</option>
              <option value="">Alle ikke-slørede</option>
            </select>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        {/* List */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="text-lg font-medium">Billeder</h2>
          </div>
          <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
            {loading && !pendingData ? (
              <div className="p-4 text-center text-gray-500">Indlæser...</div>
            ) : pendingData?.items.length === 0 ? (
              <div className="p-4 text-center text-gray-500">Ingen billeder</div>
            ) : (
              pendingData?.items.map((item) => (
                <div
                  key={item.capture_id}
                  className={`p-4 hover:bg-gray-50 cursor-pointer ${
                    selectedCapture?.capture_id === item.capture_id ? "bg-blue-50" : ""
                  }`}
                  onClick={() => selectCapture(item)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-medium">{item.filename}</div>
                      <div className="text-sm text-gray-500">{item.device_id}</div>
                    </div>
                    <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(item.redaction_status)}`}>
                      {getStatusLabel(item.redaction_status)}
                    </span>
                  </div>
                  {item.has_gdpr_data && (
                    <div className="mt-2 text-sm text-red-600">
                      {item.gdpr_detections?.faces.length || 0} ansigter, {item.gdpr_detections?.license_plates.length || 0} nummerplader
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Detail */}
        <div className="bg-white rounded-lg shadow">
          {selectedCapture ? (
            <>
              <div className="px-4 py-3 border-b border-gray-200">
                <h2 className="text-lg font-medium">{selectedCapture.filename}</h2>
                <div className="text-sm text-gray-500">Billede ID: {selectedCapture.capture_id}</div>
              </div>
              <div className="p-4">
                {/* Actions */}
                <div className="flex gap-2 mb-4">
                  {selectedCapture.redaction_status === "pending" && (
                    <button
                      onClick={() => analyzeCapture(selectedCapture.capture_id)}
                      disabled={loading}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                      Analyser
                    </button>
                  )}
                  {selectedCapture.redaction_status === "detected" && (
                    <>
                      <button
                        onClick={() => redactCapture(selectedCapture.capture_id)}
                        disabled={loading}
                        className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                      >
                        Slør
                      </button>
                      <button
                        onClick={() => approveCapture(selectedCapture.capture_id)}
                        disabled={loading}
                        className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                      >
                        Godkend
                      </button>
                    </>
                  )}
                  {selectedCapture.redaction_status === "redacted" && (
                    <div className="text-green-600 font-medium">
                      ✓ Billedet er sløret og godkendt
                    </div>
                  )}
                </div>

                {/* Detections */}
                {analysisResult && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="font-medium mb-2">Status</h3>
                      <div className={`px-3 py-2 rounded ${getStatusColor(selectedCapture.redaction_status)}`}>
                        {getStatusLabel(selectedCapture.redaction_status)}
                      </div>
                    </div>

                    <div>
                      <h3 className="font-medium mb-2 flex items-center gap-1">Fundet GDPR data
                        <InfoTooltip label="Fundet GDPR data" text={'Antal ansigter og nummerplader AI-analysen har fundet i billedet.\nBounding boxes viser præcis hvor de ligger (x, y, bredde, højde).\nConf er AI\'ens sikkerhed (0–1) — lav sikkerhed bør kontrolleres manuelt før godkendelse.'} />
                      </h3>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-gray-50 p-3 rounded">
                          <div className="text-sm text-gray-500">Ansiger</div>
                          <div className="text-xl font-bold">{analysisResult.faces.length}</div>
                        </div>
                        <div className="bg-gray-50 p-3 rounded">
                          <div className="text-sm text-gray-500">Nummerplader</div>
                          <div className="text-xl font-bold">{analysisResult.license_plates.length}</div>
                        </div>
                      </div>
                    </div>

                    {analysisResult.faces.length > 0 && (
                      <div>
                        <h4 className="font-medium mb-2">Ansiger (bounding boxes)</h4>
                        <div className="bg-gray-50 p-2 rounded text-sm font-mono">
                          {analysisResult.faces.map((f, i) => (
                            <div key={i}>
                              [{i}] x={f.x}, y={f.y}, w={f.w}, h={f.h} (conf: {f.confidence.toFixed(2)})
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {analysisResult.license_plates.length > 0 && (
                      <div>
                        <h4 className="font-medium mb-2">Nummerplader (bounding boxes)</h4>
                        <div className="bg-gray-50 p-2 rounded text-sm font-mono">
                          {analysisResult.license_plates.map((p, i) => (
                            <div key={i}>
                              [{i}] x={p.x}, y={p.y}, w={p.w}, h={p.h} (conf: {p.confidence.toFixed(2)})
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="p-4 text-center text-gray-500">
              Vælg et billede fra listen til venstre
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
