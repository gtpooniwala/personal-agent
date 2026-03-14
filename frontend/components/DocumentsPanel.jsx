import { useState } from "react";
import {
  formatDocumentStatusLabel,
  formatFileSize,
  formatRelativeTime,
  truncateText,
} from "@/lib/formatters";
import ToolsDashboard from "@/components/ToolsDashboard";

const DOCUMENT_STATUS_CLASSNAMES = new Set(["completed", "processing", "pending", "failed"]);

function getDocumentStatusClassName(status) {
  return DOCUMENT_STATUS_CLASSNAMES.has(status) ? status : "pending";
}

export default function DocumentsPanel({
  documents,
  selectedDocuments,
  documentsExpanded,
  isLoading,
  error,
  isUploading,
  uploadProgress,
  isCollapsed,
  isDragActive,
  onToggleCollapse,
  onToggleDocumentsExpanded,
  onOpenFilePicker,
  onFileSelect,
  onDragEnter,
  onDragOver,
  onDragLeave,
  onDrop,
  onToggleDocument,
  onSelectReadyDocuments,
  onClearSelectedDocuments,
  onDeleteDocument,
  fileInputRef,
}) {
  const [activeTab, setActiveTab] = useState("context");
  const selectedCount = selectedDocuments.size;
  const readyDocuments = documents.filter((doc) => doc.processed === "completed");
  const readyCount = readyDocuments.length;
  const processingCount = documents.filter((doc) => doc.processed === "processing").length;
  const queuedCount = documents.filter((doc) => doc.processed === "pending").length;
  const failedCount = documents.filter((doc) => doc.processed === "failed").length;

  function buildDocumentSummary(doc) {
    if (doc.summary && doc.summary !== "Document content available for search") {
      return doc.summary;
    }

    if (doc.processed === "completed") {
      return `Ready for search across ${doc.total_chunks || 0} section${doc.total_chunks === 1 ? "" : "s"}.`;
    }

    if (doc.processed === "failed") {
      return "Processing failed. Re-upload the file to retry indexing.";
    }

    if (doc.processed === "pending") {
      return "Queued for indexing. Search will unlock when processing begins.";
    }

    return "Indexing in progress. Search will unlock when processing completes.";
  }

  return (
    <aside className={`panel panel-right ${isCollapsed ? "collapsed" : ""}`}>
      {!isCollapsed ? (
        <button
          className="collapse-button"
          type="button"
          onClick={onToggleCollapse}
          aria-label="Collapse sidebar"
        >
          ⮞
        </button>
      ) : null}

      {!isCollapsed && (
        <>
          <div className="panel-header">
            <div className="right-panel-tabs">
              <button
                type="button"
                className={`right-panel-tab ${activeTab === "context" ? "active" : ""}`}
                onClick={() => setActiveTab("context")}
              >
                Context
              </button>
              <button
                type="button"
                className={`right-panel-tab ${activeTab === "tools" ? "active" : ""}`}
                onClick={() => setActiveTab("tools")}
              >
                Tools
              </button>
            </div>
          </div>

          {activeTab === "context" && (
          <section className="context-section">
            <button
              type="button"
              className="section-toggle"
              onClick={onToggleDocumentsExpanded}
              aria-expanded={documentsExpanded}
            >
              <span>
                <span className="section-eyebrow">Knowledge</span>
                <strong>Documents</strong>
              </span>
              <span className="section-toggle-meta">
                {selectedCount} selected • {documentsExpanded ? "Hide" : "Show"}
              </span>
            </button>

            {documentsExpanded && (
              <>
                <p className="panel-note docs-selection-note">
                  {selectedCount > 0
                    ? `${selectedCount} ready document${selectedCount > 1 ? "s" : ""} will be used in chat search.`
                    : "Select ready documents below to use them in chat search."}
                </p>

                <div className="docs-overview">
                  <span className="context-chip">{documents.length} total</span>
                  <span className="context-chip">{readyCount} ready</span>
                  {queuedCount > 0 ? <span className="context-chip">{queuedCount} queued</span> : null}
                  {processingCount > 0 ? (
                    <span className="context-chip">{processingCount} indexing</span>
                  ) : null}
                  {failedCount > 0 ? <span className="context-chip failed">{failedCount} failed</span> : null}
                </div>

                <div className="docs-actions">
                  <button
                    type="button"
                    className="secondary-button docs-action-button"
                    onClick={onSelectReadyDocuments}
                    disabled={readyCount === 0}
                  >
                    Select ready
                  </button>
                  <button
                    type="button"
                    className="secondary-button docs-action-button"
                    onClick={onClearSelectedDocuments}
                    disabled={selectedCount === 0}
                  >
                    Clear
                  </button>
                </div>

                <button
                  type="button"
                  className={`upload-zone ${isDragActive ? "drag-active" : ""}`}
                  onClick={onOpenFilePicker}
                  onDrop={onDrop}
                  onDragEnter={onDragEnter}
                  onDragOver={onDragOver}
                  onDragLeave={onDragLeave}
                >
                  <span className="upload-title">Click or drag PDF files</span>
                  <span className="upload-caption">PDF only • Max 50MB each</span>
                </button>

                {isUploading && (
                  <div className="upload-progress-wrap" aria-live="polite">
                    <div className="upload-progress-bar" style={{ width: `${uploadProgress}%` }} />
                  </div>
                )}

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  multiple
                  className="hidden-file-input"
                  onChange={onFileSelect}
                />

                <div className="panel-body scrollable">
                  {isLoading && <p className="panel-note">Loading documents...</p>}
                  {!isLoading && error && <p className="panel-error">{error}</p>}
                  {!isLoading && !error && documents.length === 0 && (
                    <p className="panel-note">No documents uploaded.</p>
                  )}

                  {!isLoading &&
                    !error &&
                    documents.map((doc) => {
                      const isSelected = selectedDocuments.has(doc.id);
                      const isReady = doc.processed === "completed";
                      const statusClassName = getDocumentStatusClassName(doc.processed);
                      const statusLabel = formatDocumentStatusLabel(doc.processed);
                      return (
                        <article
                          key={doc.id}
                          className={`document-card ${isSelected ? "selected" : ""} ${isReady ? "" : "inactive"}`}
                        >
                          <label className="doc-main-row" htmlFor={`doc-${doc.id}`}>
                            <input
                              id={`doc-${doc.id}`}
                              type="checkbox"
                              checked={isSelected}
                              disabled={!isReady}
                              onChange={(event) => onToggleDocument(doc.id, event.target.checked)}
                            />
                            <span className="doc-text-wrap">
                              <span className="doc-header-row">
                                <span className="doc-name" title={doc.filename}>
                                  📄 {truncateText(doc.filename, 28)}
                                </span>
                                <span className={`doc-status-badge ${statusClassName}`}>
                                  {statusLabel}
                                </span>
                              </span>
                              <span className="doc-meta">
                                {formatFileSize(doc.file_size)} • {formatRelativeTime(doc.uploaded_at)}
                              </span>
                              <span className="doc-meta">
                                {isReady
                                  ? `${doc.total_chunks || 0} searchable section${doc.total_chunks === 1 ? "" : "s"}`
                                  : "Not searchable yet"}
                              </span>
                              <span className="doc-summary">
                                {buildDocumentSummary(doc)}
                              </span>
                            </span>
                          </label>
                          <button
                            type="button"
                            className="icon-danger"
                            aria-label={`Delete ${doc.filename}`}
                            onClick={() => onDeleteDocument(doc.id, doc.filename)}
                          >
                            🗑️
                          </button>
                        </article>
                      );
                    })}
                </div>
              </>
            )}
          </section>
          )}

          {activeTab === "tools" && <ToolsDashboard />}
        </>
      )}
    </aside>
  );
}
