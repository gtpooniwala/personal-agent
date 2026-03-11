import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HomePage from '@/app/page';
import { apiCall, runtimeApiCall } from '@/lib/api';
import { subscribeToRunStream } from '@/lib/runStream';

jest.mock('@/lib/runStream', () => ({
  subscribeToRunStream: jest.fn((_runId, { onFallback }) => {
    onFallback();
    return () => {};
  }),
}));

jest.mock('@/lib/api', () => ({
  apiCall: jest.fn(),
  runtimeApiCall: jest.fn(),
  uploadPdf: jest.fn(),
  API_BASE: '/api/agent',
  RUNTIME_API_BASE: '/api/agent',
}));

const CONVERSATIONS = [
  { id: 'conv-a', title: 'Conv A', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
  { id: 'conv-b', title: 'Conv B', created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
];
const RUN_TRANSPORT_TIMEOUT_MESSAGE =
  'Live updates timed out. The run may still be in progress. Refresh the conversation to check for the final response.';

function setupApiMocks({
  runtimeChatResponse = async () => ({ run_id: 'run-1' }),
  conversations = CONVERSATIONS,
  createdConversationId = 'conv-new',
  sseMode = 'complete', // 'complete' | 'fallback' | 'pending'
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

  subscribeToRunStream.mockImplementation((_runId, { onStateUpdate, onComplete, onFallback }) => {
    if (sseMode === 'complete') {
      onStateUpdate({ type: 'run_complete', status: 'succeeded', error: null });
      onComplete({ status: 'succeeded', error: null });
    } else if (sseMode === 'fallback') {
      onFallback();
    }
    // 'pending' — never resolves, simulates in-flight
    return () => {};
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

  test('does not steal printable keys from interactive controls', async () => {
    const user = userEvent.setup();
    setupApiMocks({ conversations: [] });

    await act(async () => {
      render(<HomePage />);
    });

    const focusComposerButton = await screen.findByRole('button', { name: /focus composer/i });
    focusComposerButton.focus();
    expect(focusComposerButton).toHaveFocus();

    await user.keyboard('a');

    expect(screen.getByRole('textbox')).toHaveValue('');
    expect(focusComposerButton).toHaveFocus();
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

    await waitFor(() => {
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
});

describe('sendMessage conversation scoping (issue #31)', () => {
  beforeEach(() => {
    jest.resetAllMocks();
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

    setupApiMocks({ runtimeChatResponse: async () => ({ run_id: 'run-1' }), sseMode: 'fallback' });
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

describe('sendMessage SSE vs fallback paths', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  test('SSE path: run completes via SSE without polling /status', async () => {
    const user = userEvent.setup();

    setupApiMocks({ sseMode: 'complete' });

    await act(async () => {
      render(<HomePage />);
    });

    await waitFor(() => screen.getByRole('button', { name: /Conv A/i }));

    const input = screen.getByRole('textbox');
    await user.type(input, 'hello via sse');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled();
    });

    const statusCalls = runtimeApiCall.mock.calls.filter(([path]) => path && path.includes('/status'));
    expect(statusCalls).toHaveLength(0);
  });

  test('fallback path: run completes via polling when SSE triggers onFallback', async () => {
    const user = userEvent.setup();

    setupApiMocks({ sseMode: 'fallback' });

    await act(async () => {
      render(<HomePage />);
    });

    await waitFor(() => screen.getByRole('button', { name: /Conv A/i }));

    const input = screen.getByRole('textbox');
    await user.type(input, 'hello via fallback');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^send$/i })).not.toBeDisabled();
    });

    const statusCalls = runtimeApiCall.mock.calls.filter(([path]) => path && path.includes('/status'));
    expect(statusCalls.length).toBeGreaterThan(0);
  });

  test('fallback polling timeout shows a soft warning without synthesizing a failed assistant message', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    setupApiMocks({ sseMode: 'fallback' });
    runtimeApiCall.mockImplementation(async (path) => {
      if (path === '/chat') return { run_id: 'run-1' };
      if (path.includes('/status')) return { status: 'running', error: null };
      if (path.includes('/events')) return { events: [], next_after: null };
      return {};
    });

    await act(async () => {
      render(<HomePage />);
    });

    await waitFor(() => screen.getByRole('button', { name: /Conv A/i }));

    await user.type(screen.getByRole('textbox'), 'hello via stalled transport');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    await act(async () => {
      await jest.advanceTimersByTimeAsync(60_000);
    });

    await waitFor(() => {
      expect(screen.getByText(RUN_TRANSPORT_TIMEOUT_MESSAGE)).toBeInTheDocument();
    });

    expect(screen.queryByText('[Error: Failed to send message]')).not.toBeInTheDocument();
    expect(screen.getByText(/Thinking/)).toBeInTheDocument();
    expect(screen.queryByText('Failed')).not.toBeInTheDocument();
    expect(screen.getAllByText('Running').length).toBeGreaterThan(0);
  });

  test('repeated polling failures still surface as a hard failure', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    setupApiMocks({ sseMode: 'fallback' });
    runtimeApiCall.mockImplementation(async (path) => {
      if (path === '/chat') return { run_id: 'run-1' };
      if (path.includes('/status')) throw new Error('status unavailable');
      if (path.includes('/events')) return { events: [], next_after: null };
      return {};
    });

    await act(async () => {
      render(<HomePage />);
    });

    await waitFor(() => screen.getByRole('button', { name: /Conv A/i }));

    await user.type(screen.getByRole('textbox'), 'hello via repeated failures');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    await act(async () => {
      await jest.advanceTimersByTimeAsync(60_000);
    });

    await waitFor(() => {
      expect(screen.getByText('Failed to send message.')).toBeInTheDocument();
    });

    expect(screen.getByText('[Error: Failed to send message]')).toBeInTheDocument();
    expect(screen.queryByText(RUN_TRANSPORT_TIMEOUT_MESSAGE)).not.toBeInTheDocument();
    expect(screen.queryByText(/Thinking/)).not.toBeInTheDocument();
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0);
  });
});
