import { formatFileSize, formatRelativeTime, truncateText } from "@/lib/formatters";

export default function DocumentsPanel({
  documents,
  selectedDocuments,
  isLoading,
  error,
  isUploading,
  uploadProgress,
  isCollapsed,
  isDragActive,
  onToggleCollapse,
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
      <button
        className="collapse-button"
        type="button"
        onClick={onToggleCollapse}
        aria-label={isCollapsed ? "Expand documents" : "Collapse documents"}
      >
        {isCollapsed ? "⮜" : "⮞"}
      </button>

      {!isCollapsed && (
        <>
          <div className="panel-header">
            <p className="eyebrow">Knowledge</p>
            <h2>Documents</h2>
          </div>
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
              documents.map((document) => {
                const isSelected = selectedDocuments.has(document.id);
                return (
                  <article
                    key={document.id}
                    className={`document-card ${isSelected ? "selected" : ""}`}
                  >
                    <label className="doc-main-row" htmlFor={`doc-${document.id}`}>
                      <input
                        id={`doc-${document.id}`}
                        type="checkbox"
                        checked={isSelected}
                        onChange={(event) => onToggleDocument(document.id, event.target.checked)}
                      />
                      <span className="doc-text-wrap">
                        <span className="doc-name" title={document.filename}>
                          📄 {truncateText(document.filename, 28)}
                        </span>
                        <span className="doc-meta">
                          {formatFileSize(document.file_size)} • {formatRelativeTime(document.uploaded_at)}
                        </span>
                        <span className="doc-summary">
                          {document.summary || "No summary available."}
                        </span>
                      </span>
                    </label>
                    <button
                      type="button"
                      className="icon-danger"
                      aria-label={`Delete ${document.filename}`}
                      onClick={() => onDeleteDocument(document.id, document.filename)}
                    >
                      🗑️
                    </button>
                  </article>
                );
              })}
          </div>
        </>
      )}
    </aside>
  );
}
