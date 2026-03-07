import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HomePage from '@/app/page';
import { apiCall, runtimeApiCall } from '@/lib/api';

jest.mock('@/lib/api', () => ({
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

function setupApiMocks({
  runtimeChatResponse = async () => ({ run_id: 'run-1' }),
  conversations = CONVERSATIONS,
  createdConversationId = 'conv-new',
} = {}) {
  apiCall.mockImplementation(async (path, options = {}) => {
    if (path === '/tools') return [];
    if (path === '/conversations' && options.method === 'POST') return { id: createdConversationId };
    if (path === '/conversations') return conversations;
    if (path.includes('/messages')) return [];
    if (path === '/documents') return { documents: [] };
    return {};
  });

  runtimeApiCall.mockImplementation((path) => {
    if (path === '/chat') return runtimeChatResponse();
    if (path.includes('/status')) return Promise.resolve({ status: 'succeeded' });
    if (path.includes('/events')) return Promise.resolve({ events: [], next_after: null });
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

  test('focuses the composer after initial render', async () => {
    setupApiMocks();

    await act(async () => {
      render(<HomePage />);
    });

    await waitFor(() => {
      expect(screen.getByRole('textbox')).toHaveFocus();
    });
  });
});

describe('sendMessage first-message flow', () => {
  test('creates a conversation automatically when none exists', async () => {
    const user = userEvent.setup();
    let createdConversation = false;

    apiCall.mockImplementation(async (path, options = {}) => {
      if (path === '/tools') return [];
      if (path === '/conversations' && options.method === 'POST') {
        createdConversation = true;
        return { id: 'conv-new' };
      }
      if (path === '/conversations') {
        return createdConversation
          ? [{ id: 'conv-new', title: 'Conv New', updated_at: new Date().toISOString() }]
          : [];
      }
      if (path.includes('/messages')) return [];
      if (path === '/documents') return { documents: [] };
      return {};
    });
    runtimeApiCall.mockImplementation(async (path) => {
      if (path === '/chat') return { run_id: 'run-1' };
      if (path.includes('/status')) return { status: 'succeeded' };
      if (path.includes('/events')) return { events: [], next_after: null };
      return {};
    });

    await act(async () => {
      render(<HomePage />);
    });

    await waitFor(() => screen.getByText('No conversations yet.'));

    const input = screen.getByRole('textbox');
    await user.type(input, 'hello');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    await waitFor(() => {
      expect(apiCall).toHaveBeenCalledWith(
        '/conversations',
        expect.objectContaining({ method: 'POST' }),
      );
    });

    expect(runtimeApiCall).toHaveBeenCalledWith(
      '/chat',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          message: 'hello',
          conversation_id: 'conv-new',
          selected_documents: [],
        }),
      }),
    );
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
      expect(screen.getByRole('button', { name: /Conv A/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Conv B/i })).toBeInTheDocument();
    });

    // Type a message (conv-a is active by default)
    const input = screen.getByRole('textbox');
    await user.type(input, 'hello');

    // Click send — triggers the never-resolving in-flight request for conv-a
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    // Conv-a's send button should be disabled
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
    });

    // Switch to conv-b
    await user.click(screen.getByRole('button', { name: /Conv B/i }));

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

    await waitFor(() => screen.getByRole('button', { name: /Conv A/i }));

    const input = screen.getByRole('textbox');
    await user.type(input, 'hello');

    await user.click(screen.getByRole('button', { name: /^send$/i }));

    // After all promises resolve, the button should return to "Send" and be enabled
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled();
    });
  });

  test('maintains sending state for original conversation if user switches during status polling', async () => {
    const user = userEvent.setup();

    // /chat resolves immediately, but status polling is delayed
    let resolveStatus;
    const statusPromise = new Promise((resolve) => {
      resolveStatus = resolve;
    });

    setupApiMocks({ runtimeChatResponse: async () => ({ run_id: 'run-1' }) });
    runtimeApiCall.mockImplementation(async (path) => {
      if (path === '/chat') return { run_id: 'run-1' };
      if (path.includes('/status')) {
        await statusPromise;
        return { status: 'succeeded' };
      }
      if (path.includes('/events')) {
        return { events: [], next_after: null };
      }
      return {};
    });

    await act(async () => {
      render(<HomePage />);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Conv A/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Conv B/i })).toBeInTheDocument();
    });

    const input = screen.getByRole('textbox');
    await user.type(input, 'hello');

    await user.click(screen.getByRole('button', { name: /^send$/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
    });

    await user.click(screen.getByRole('button', { name: /Conv B/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled();
    });

    await user.click(screen.getByRole('button', { name: /Conv A/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
    });

    resolveStatus();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled();
    });
  });
});
