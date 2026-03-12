import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatPanel from '@/components/ChatPanel';

const defaultProps = {
  currentView: 'chat',
  currentConversationId: 'conv-a',
  messages: [],
  currentConversationTitle: '',
  activeRun: null,
  isLoadingMessages: false,
  chatError: '',
  messageInput: 'hello',
  isSending: false,
  selectedDocumentDetails: [],
  onChangeMessage: jest.fn(),
  onChoosePromptStarter: jest.fn(),
  onSendMessage: jest.fn(),
  onFocusComposer: jest.fn(),
  messageInputRef: { current: null },
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe('ChatPanel IME composition guard (issue #30)', () => {
  test('Enter with isComposing:true does not call onSendMessage', () => {
    render(<ChatPanel {...defaultProps} />);
    const input = screen.getByRole('textbox');
    fireEvent.keyDown(input, { key: 'Enter', keyCode: 13, isComposing: true });
    expect(defaultProps.onSendMessage).not.toHaveBeenCalled();
  });

  test('Enter with keyCode 229 (IME fallback) does not call onSendMessage', () => {
    render(<ChatPanel {...defaultProps} />);
    const input = screen.getByRole('textbox');
    fireEvent.keyDown(input, { key: 'Enter', keyCode: 229 });
    expect(defaultProps.onSendMessage).not.toHaveBeenCalled();
  });

  test('Plain Enter (no composition) calls onSendMessage once', async () => {
    render(<ChatPanel {...defaultProps} />);
    const input = screen.getByRole('textbox');
    await userEvent.click(input);
    await userEvent.keyboard('{Enter}');
    expect(defaultProps.onSendMessage).toHaveBeenCalledTimes(1);
  });

  test('Non-Enter key does not call onSendMessage', async () => {
    render(<ChatPanel {...defaultProps} />);
    const input = screen.getByRole('textbox');
    await userEvent.click(input);
    await userEvent.keyboard('a');
    expect(defaultProps.onSendMessage).not.toHaveBeenCalled();
  });

  test('Shift+Enter does not call onSendMessage', async () => {
    render(<ChatPanel {...defaultProps} />);
    const input = screen.getByRole('textbox');
    await userEvent.click(input);
    await userEvent.keyboard('{Shift>}{Enter}{/Shift}');
    expect(defaultProps.onSendMessage).not.toHaveBeenCalled();
  });
});

describe('ChatPanel tool activity disclosure', () => {
  test('tool details are collapsed by default and expand on demand', async () => {
    const user = userEvent.setup();

    render(
      <ChatPanel
        {...defaultProps}
        messages={[
          {
            id: 'assistant-1',
            role: 'assistant',
            content: 'Done',
            timestamp: new Date().toISOString(),
            agent_actions: [
              {
                tool: 'calculator',
                input: '2 + 2',
                output: '4',
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByText('Tool activity')).toBeInTheDocument();
    expect(screen.getByText(/Input:/i)).not.toBeVisible();

    await user.click(screen.getByText('Tool activity'));

    expect(screen.getByText(/Input:/i)).toBeVisible();
    expect(screen.getByText(/Output:/i)).toBeVisible();
  });
});

describe('ChatPanel document context UX (issue #64)', () => {
  test('shows selected document chips and prompt starters', async () => {
    const user = userEvent.setup();

    render(
      <ChatPanel
        {...defaultProps}
        selectedDocumentDetails={[
          { id: 'doc-1', filename: 'Master Services Agreement.pdf' },
          { id: 'doc-2', filename: 'Pricing Appendix.pdf' },
        ]}
      />,
    );

    expect(screen.getByText('Master Services Agreement.pdf')).toBeInTheDocument();
    expect(screen.getByText('Pricing Appendix.pdf')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /summarize selected docs/i }));

    expect(defaultProps.onChoosePromptStarter).toHaveBeenCalledWith(
      'Summarize the selected documents and highlight the main decisions, dates, and risks.',
    );
  });

  test('renders source cards when document search tool output includes citations', () => {
    render(
      <ChatPanel
        {...defaultProps}
        messages={[
          {
            id: 'assistant-1',
            role: 'assistant',
            content: 'Here is the answer.',
            timestamp: new Date().toISOString(),
            agent_actions: [
              {
                tool: 'search_documents',
                input: '{ "query": "termination" }',
                output:
                  "**1. From 'MSA.pdf' (section 2) - highly relevant:**\nTermination requires thirty days notice.\n\n*Found 1 relevant passages from 1 document(s).*",
              },
            ],
          },
        ]}
      />,
    );

    const sourceRegion = screen.getByLabelText('Document sources');
    expect(sourceRegion).toBeInTheDocument();
    expect(within(sourceRegion).getByText('MSA.pdf')).toBeInTheDocument();
    expect(within(sourceRegion).getByText(/Section 2/i)).toBeInTheDocument();
    expect(within(sourceRegion).getByText(/Termination requires thirty days notice/i)).toBeInTheDocument();
  });

  test('parses source cards when the document filename contains an apostrophe', () => {
    render(
      <ChatPanel
        {...defaultProps}
        messages={[
          {
            id: 'assistant-2',
            role: 'assistant',
            content: 'Found it.',
            timestamp: new Date().toISOString(),
            agent_actions: [
              {
                tool: 'search_documents',
                input: '{ "query": "renewal" }',
                output:
                  "**1. From 'Bob's Contract.pdf' (section 4) - moderately relevant:**\nRenewal is automatic unless cancelled.\n\n*Found 1 relevant passages from 1 document(s).*",
              },
            ],
          },
        ]}
      />,
    );

    const sourceRegion = screen.getByLabelText('Document sources');
    expect(within(sourceRegion).getByText("Bob's Contract.pdf")).toBeInTheDocument();
    expect(within(sourceRegion).getByText(/Section 4/i)).toBeInTheDocument();
  });

  test('falls back to a looser parser when source formatting is not bolded', () => {
    render(
      <ChatPanel
        {...defaultProps}
        messages={[
          {
            id: 'assistant-3',
            role: 'assistant',
            content: 'Found another source.',
            timestamp: new Date().toISOString(),
            agent_actions: [
              {
                tool: 'search_documents',
                input: '{ "query": "pricing" }',
                output:
                  "1. From 'Pricing Addendum.pdf' (section 7) - highly relevant:\nPricing updates require written approval.\n\n*Found 1 relevant passages from 1 document(s).*",
              },
            ],
          },
        ]}
      />,
    );

    const sourceRegion = screen.getByLabelText('Document sources');
    expect(within(sourceRegion).getByText('Pricing Addendum.pdf')).toBeInTheDocument();
    expect(within(sourceRegion).getByText(/Pricing updates require written approval/i)).toBeInTheDocument();
  });

  test('sanitizes unknown run status values before using them as CSS classes', () => {
    render(
      <ChatPanel
        {...defaultProps}
        activeRun={{ status: 'totally-unknown-status' }}
      />,
    );

    const [statusPill] = screen.getAllByText('Working');
    expect(statusPill.className).toContain('idle');
    expect(statusPill.className).not.toContain('totally-unknown-status');
  });
});

describe('ChatPanel run status layout', () => {
  test('does not render a run status row when there is no active run', () => {
    render(<ChatPanel {...defaultProps} messageInput="" />);

    expect(screen.queryByLabelText('Run status')).not.toBeInTheDocument();
  });

  test('renders run status outside the transcript for an empty conversation', () => {
    render(
      <ChatPanel
        {...defaultProps}
        messageInput=""
        activeRun={{
          status: 'running',
          latestEvent: { type: 'started', message: 'Run started' },
        }}
      />,
    );

    const transcript = screen.getByLabelText('Conversation transcript');
    const runStatus = screen.getByLabelText('Run status');

    expect(runStatus).toBeInTheDocument();
    expect(transcript).not.toContainElement(runStatus);
    expect(screen.getAllByText('Starting').length).toBeGreaterThan(0);
  });

  test('keeps run status separate from selected document chips and full transcripts', () => {
    render(
      <ChatPanel
        {...defaultProps}
        messageInput=""
        messages={[
          { id: 'm1', role: 'user', content: 'Hello', timestamp: '2026-03-11T10:00:00Z', agent_actions: [] },
          { id: 'm2', role: 'assistant', content: 'Hi there', timestamp: '2026-03-11T10:00:02Z', agent_actions: [] },
        ]}
        selectedDocumentDetails={[
          { id: 'doc-1', filename: 'Quarterly Report.pdf' },
        ]}
        activeRun={{
          status: 'running',
          transport: 'polling',
          transportMessage: 'Live stream unavailable. Checking status in the background.',
          latestEvent: { type: 'started', message: 'Run started' },
        }}
      />,
    );

    const transcript = screen.getByLabelText('Conversation transcript');
    const documentsStrip = screen.getByLabelText('Selected documents');
    const runStatus = screen.getByLabelText('Run status');

    expect(documentsStrip).toBeInTheDocument();
    expect(documentsStrip).not.toContainElement(runStatus);
    expect(transcript).not.toContainElement(runStatus);
    expect(screen.getAllByText('Starting').length).toBeGreaterThan(0);
    expect(screen.getByText('Live stream unavailable. Checking status in the background.')).toBeInTheDocument();
  });
});
