import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HomePage from '@/app/page';
import { apiCall, runtimeApiCall } from '../lib/api';

jest.mock('../lib/api', () => ({
  apiCall: jest.fn(),
  runtimeApiCall: jest.fn(),
  uploadPdf: jest.fn(),
  API_BASE: 'http://localhost:8000/api/v1',
  RUNTIME_API_BASE: 'http://localhost:8000',
}));

const CONVERSATIONS = [
  { id: 'conv-a', title: 'Conv A', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
  { id: 'conv-b', title: 'Conv B', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
];

function setupApiMocks({ runtimeChatResponse = async () => ({ run_id: 'run-1' }) } = {}) {
  apiCall.mockImplementation(async (path) => {
    if (path === '/tools') return [];
    if (path === '/conversations') return CONVERSATIONS;
    if (path.includes('/messages')) return [];
    if (path === '/documents') return { documents: [] };
    return {};
  });

  runtimeApiCall.mockImplementation((path) => {
    if (path === '/chat') return runtimeChatResponse();
    if (path.includes('/status')) return Promise.resolve({ status: 'succeeded' });
    return Promise.resolve({});
  });
}

describe('initial render state', () => {
  test('send button is enabled before conversations load', async () => {
    // Delay conversations so the component renders with null currentConversationId first
    apiCall.mockImplementation(async (path) => {
      if (path === '/conversations') {
        await new Promise((resolve) => setTimeout(resolve, 50));
        return [];
      }
      if (path === '/tools') return [];
      if (path === '/documents') return { documents: [] };
      return {};
    });
    runtimeApiCall.mockResolvedValue({});

    await act(async () => {
      render(<HomePage />);
    });

    // On first render, both sendingConversationId and currentConversationId are null.
    // isSending must be false (not null === null).
    expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled();
  });
});

describe('sendMessage error path', () => {
  test('shows error when no conversation exists and user tries to send', async () => {
    const user = userEvent.setup();

    apiCall.mockImplementation(async (path) => {
      if (path === '/conversations') return [];  // no conversations
      if (path === '/tools') return [];
      if (path === '/documents') return { documents: [] };
      return {};
    });
    runtimeApiCall.mockResolvedValue({});

    await act(async () => {
      render(<HomePage />);
    });

    // Wait for load to settle (no conversations)
    await waitFor(() => screen.getByText('No conversations yet.'));

    const input = screen.getByRole('textbox');
    await user.type(input, 'hello');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    // Should show the "no conversation" error, not silently no-op
    await waitFor(() => {
      expect(screen.getByText('Create a conversation before sending a message.')).toBeInTheDocument();
    });
  });
});

describe('sendMessage conversation scoping (issue #31)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('isSending is false for the non-sending conversation while another is in-flight', async () => {
    const user = userEvent.setup();

    // /chat never resolves — conv-a stays in-flight indefinitely
    setupApiMocks({ runtimeChatResponse: () => new Promise(() => {}) });

    await act(async () => {
      render(<HomePage />);
    });

    // Wait for both conversations to appear
    await waitFor(() => {
      expect(screen.getByText('Conv A')).toBeInTheDocument();
      expect(screen.getByText('Conv B')).toBeInTheDocument();
    });

    // Type a message (conv-a is active by default)
    const input = screen.getByRole('textbox');
    await user.type(input, 'hello');

    // Click send — triggers the never-resolving in-flight request for conv-a
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    // Conv-a's send button should be disabled
    expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();

    // Switch to conv-b
    await act(async () => {
      await user.click(screen.getByText('Conv B'));
    });

    // Conv-b's send button must NOT be disabled
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled();
    });
  });

  test('isSending reverts to false after send completes', async () => {
    const user = userEvent.setup();

    setupApiMocks(); // fast-resolving by default

    await act(async () => {
      render(<HomePage />);
    });

    await waitFor(() => screen.getByText('Conv A'));

    const input = screen.getByRole('textbox');
    await user.type(input, 'hello');

    await user.click(screen.getByRole('button', { name: /^send$/i }));

    // After all promises resolve, the button should return to "Send" and be enabled
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled();
    });
  });
});
