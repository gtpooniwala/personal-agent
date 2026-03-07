import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatPanel from '@/components/ChatPanel';

const defaultProps = {
  currentView: 'chat',
  currentConversationId: 'conv-a',
  messages: [],
  currentConversationTitle: '',
  isLoadingMessages: false,
  chatError: '',
  messageInput: 'hello',
  isSending: false,
  onChangeMessage: jest.fn(),
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
