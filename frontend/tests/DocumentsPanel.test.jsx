import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DocumentsPanel from '@/components/DocumentsPanel';

const defaultProps = {
  documents: [],
  selectedDocuments: new Set(),
  documentsExpanded: true,
  isLoading: false,
  error: '',
  isUploading: false,
  uploadProgress: 0,
  isCollapsed: false,
  isDragActive: false,
  onToggleCollapse: jest.fn(),
  onToggleDocumentsExpanded: jest.fn(),
  onOpenFilePicker: jest.fn(),
  onFileSelect: jest.fn(),
  onDragEnter: jest.fn(),
  onDragOver: jest.fn(),
  onDragLeave: jest.fn(),
  onDrop: jest.fn(),
  onToggleDocument: jest.fn(),
  onSelectReadyDocuments: jest.fn(),
  onClearSelectedDocuments: jest.fn(),
  onDeleteDocument: jest.fn(),
  fileInputRef: { current: null },
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe('DocumentsPanel document workflow UX (issue #64)', () => {
  test('shows processing state clearly and disables non-ready selection', () => {
    render(
      <DocumentsPanel
        {...defaultProps}
        documents={[
          {
            id: 'doc-processing',
            filename: 'Contract Draft.pdf',
            file_size: 1024,
            uploaded_at: new Date().toISOString(),
            processed: 'processing',
            total_chunks: 0,
            summary: '',
          },
        ]}
      />,
    );

    expect(screen.getByText('Indexing')).toBeInTheDocument();
    expect(screen.getByText(/Not searchable yet/i)).toBeInTheDocument();
    expect(screen.getByRole('checkbox')).toBeDisabled();
  });

  test('offers quick selection controls for ready documents', async () => {
    const user = userEvent.setup();

    render(
      <DocumentsPanel
        {...defaultProps}
        documents={[
          {
            id: 'doc-ready',
            filename: 'MSA.pdf',
            file_size: 1024,
            uploaded_at: new Date().toISOString(),
            processed: 'completed',
            total_chunks: 4,
            summary: 'Master agreement covering pricing and renewal terms.',
          },
        ]}
      />,
    );

    await user.click(screen.getByRole('button', { name: /select ready/i }));
    expect(defaultProps.onSelectReadyDocuments).toHaveBeenCalledTimes(1);
  });

  test('distinguishes queued documents from indexing documents', () => {
    render(
      <DocumentsPanel
        {...defaultProps}
        documents={[
          {
            id: 'doc-pending',
            filename: 'Queued Upload.pdf',
            file_size: 1024,
            uploaded_at: new Date().toISOString(),
            processed: 'pending',
            total_chunks: 0,
            summary: '',
          },
          {
            id: 'doc-processing',
            filename: 'Indexing Upload.pdf',
            file_size: 1024,
            uploaded_at: new Date().toISOString(),
            processed: 'processing',
            total_chunks: 0,
            summary: '',
          },
        ]}
      />,
    );

    expect(screen.getByText('1 queued')).toBeInTheDocument();
    expect(screen.getByText('1 indexing')).toBeInTheDocument();
    expect(screen.getByText(/Queued for indexing/i)).toBeInTheDocument();
    expect(screen.getByText(/Indexing in progress/i)).toBeInTheDocument();
  });
});
