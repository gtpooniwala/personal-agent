import { formatFileSize, formatRelativeTime, truncateText } from "@/lib/formatters";

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
  onDeleteDocument,
  fileInputRef,
}) {
  const selectedCount = selectedDocuments.size;

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
            <p className="eyebrow">Context</p>
            <h2>Workspace Sidebar</h2>
          </div>
          <p className="panel-note context-panel-note">
            Keep chat context, uploaded files, and future sidebar tools together in one place.
          </p>

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
                    ? `${selectedCount} selected file${selectedCount > 1 ? "s" : ""} will be used for document search.`
                    : "Select files below to use document search in chat."}
                </p>

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
                      return (
                        <article
                          key={doc.id}
                          className={`document-card ${isSelected ? "selected" : ""}`}
                        >
                          <label className="doc-main-row" htmlFor={`doc-${doc.id}`}>
                            <input
                              id={`doc-${doc.id}`}
                              type="checkbox"
                              checked={isSelected}
                              onChange={(event) => onToggleDocument(doc.id, event.target.checked)}
                            />
                            <span className="doc-text-wrap">
                              <span className="doc-name" title={doc.filename}>
                                📄 {truncateText(doc.filename, 28)}
                              </span>
                              <span className="doc-meta">
                                {formatFileSize(doc.file_size)} • {formatRelativeTime(doc.uploaded_at)}
                              </span>
                              <span className="doc-summary">
                                {doc.summary || "No summary available."}
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
        </>
      )}
    </aside>
  );
}
