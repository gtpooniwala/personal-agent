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

    const runChip = screen.getByText(/Run totally-unknown-status/i);
    expect(runChip.className).toContain('idle');
    expect(runChip.className).not.toContain('totally-unknown-status');
  });
});
