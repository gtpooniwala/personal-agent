import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatPanel from '@/components/ChatPanel';

const defaultProps = {
  tools: [],
  messages: [],
  isLoadingMessages: false,
  chatError: '',
  messageInput: 'hello',
  isSending: false,
  onChangeMessage: jest.fn(),
  onSendMessage: jest.fn(),
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
    fireEvent.keyDown(input, { key: 'Process', keyCode: 229 });
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
});
