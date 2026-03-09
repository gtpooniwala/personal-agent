import {
  DEFAULT_RUN_STREAM_INACTIVITY_TIMEOUT_MS,
  subscribeToRunStream,
} from '@/lib/runStream';

const RUNTIME_API_BASE = 'http://localhost:8000';

jest.mock('@/lib/api', () => ({
  RUNTIME_API_BASE: 'http://localhost:8000',
}));

function makeCallbacks(overrides = {}) {
  return {
    onStateUpdate: jest.fn(),
    onComplete: jest.fn(),
    onFallback: jest.fn(),
    ...overrides,
  };
}

describe('subscribeToRunStream', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  test('calls onFallback immediately when EventSource is undefined', () => {
    const savedEventSource = global.EventSource;
    delete global.EventSource;

    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    expect(callbacks.onFallback).toHaveBeenCalledTimes(1);
    expect(callbacks.onStateUpdate).not.toHaveBeenCalled();
    expect(callbacks.onComplete).not.toHaveBeenCalled();

    global.EventSource = savedEventSource;
  });

  test('calls onFallback when EventSource constructor throws', () => {
    const savedEventSource = global.EventSource;
    global.EventSource = class {
      constructor() {
        throw new Error('constructor error');
      }
    };

    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    expect(callbacks.onFallback).toHaveBeenCalledTimes(1);
    expect(callbacks.onStateUpdate).not.toHaveBeenCalled();
    expect(callbacks.onComplete).not.toHaveBeenCalled();

    global.EventSource = savedEventSource;
  });

  test('calls onFallback when run_event has malformed JSON', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    // Emit a raw event with invalid JSON data
    const listeners = es._listeners['run_event'] || [];
    listeners.forEach((fn) => fn({ data: 'not-valid-json' }));

    expect(callbacks.onFallback).toHaveBeenCalledTimes(1);
    expect(callbacks.onStateUpdate).not.toHaveBeenCalled();
  });

  test('opens EventSource at correct URL', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    expect(es).toBeDefined();
    expect(es.url).toBe(`${RUNTIME_API_BASE}/runs/run-xyz/stream`);
  });

  test('falls back when no event arrives before the inactivity timeout', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', {
      ...callbacks,
      inactivityTimeoutMs: 1_000,
    });

    const es = MockEventSource.instances[0];
    jest.advanceTimersByTime(1_000);

    expect(callbacks.onFallback).toHaveBeenCalledTimes(1);
    expect(es.readyState).toBe(2);
  });

  test('run_event fires onStateUpdate with normalized shape', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    es.emit('run_event', {
      event_id: 'evt-1',
      event_type: 'tool_call',
      status: 'running',
      payload: { message: 'hello', tool: 'search', metadata: { k: 'v' } },
      timestamp: '2024-01-01T00:00:00Z',
    });

    expect(callbacks.onStateUpdate).toHaveBeenCalledWith({
      type: 'run_event',
      event: {
        event_id: 'evt-1',
        type: 'tool_call',
        status: 'running',
        message: 'hello',
        tool: 'search',
        metadata: { k: 'v' },
        created_at: '2024-01-01T00:00:00Z',
      },
    });
    expect(callbacks.onComplete).not.toHaveBeenCalled();
    expect(callbacks.onFallback).not.toHaveBeenCalled();
  });

  test('heartbeat resets the inactivity watchdog', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', {
      ...callbacks,
      inactivityTimeoutMs: 1_000,
    });

    const es = MockEventSource.instances[0];
    jest.advanceTimersByTime(900);
    es.emit('heartbeat', {});
    jest.advanceTimersByTime(900);

    expect(callbacks.onFallback).not.toHaveBeenCalled();

    jest.advanceTimersByTime(101);

    expect(callbacks.onFallback).toHaveBeenCalledTimes(1);
  });

  test('run_event resets the inactivity watchdog', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', {
      ...callbacks,
      inactivityTimeoutMs: 1_000,
    });

    const es = MockEventSource.instances[0];
    jest.advanceTimersByTime(900);
    es.emit('run_event', {
      event_id: 'evt-1',
      event_type: 'tool_call',
      status: 'running',
      payload: {},
      timestamp: '2024-01-01T00:00:00Z',
    });
    jest.advanceTimersByTime(900);

    expect(callbacks.onFallback).not.toHaveBeenCalled();

    jest.advanceTimersByTime(101);

    expect(callbacks.onFallback).toHaveBeenCalledTimes(1);
  });

  test('run_complete fires onStateUpdate and onComplete, closes EventSource', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    es.emit('run_complete', { status: 'succeeded', error: null });

    expect(callbacks.onStateUpdate).toHaveBeenCalledWith({
      type: 'run_complete',
      status: 'succeeded',
      error: null,
    });
    expect(callbacks.onComplete).toHaveBeenCalledWith({ status: 'succeeded', error: null });
    expect(es.readyState).toBe(2);
    expect(callbacks.onFallback).not.toHaveBeenCalled();
  });

  test('onerror fires onFallback, not onStateUpdate', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    es.triggerError();

    expect(callbacks.onFallback).toHaveBeenCalledTimes(1);
    expect(callbacks.onStateUpdate).not.toHaveBeenCalled();
    expect(callbacks.onComplete).not.toHaveBeenCalled();
  });

  test('cleanup function closes EventSource and prevents subsequent callbacks', () => {
    const callbacks = makeCallbacks();
    const cleanup = subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    cleanup();

    expect(es.readyState).toBe(2);

    es.emit('run_event', {
      event_id: 'evt-1',
      event_type: 'tool_call',
      status: 'running',
      payload: {},
      timestamp: '2024-01-01T00:00:00Z',
    });

    expect(callbacks.onStateUpdate).not.toHaveBeenCalled();
  });

  test('cleanup clears the inactivity watchdog', () => {
    const callbacks = makeCallbacks();
    const cleanup = subscribeToRunStream('run-xyz', {
      ...callbacks,
      inactivityTimeoutMs: 1_000,
    });

    cleanup();
    jest.advanceTimersByTime(1_000);

    expect(callbacks.onFallback).not.toHaveBeenCalled();
  });

  test('heartbeat fires no callbacks', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    es.emit('heartbeat', {});

    expect(callbacks.onStateUpdate).not.toHaveBeenCalled();
    expect(callbacks.onComplete).not.toHaveBeenCalled();
    expect(callbacks.onFallback).not.toHaveBeenCalled();
  });

  test('multiple run_events then run_complete all delivered in order', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];

    es.emit('run_event', {
      event_id: 'evt-1',
      event_type: 'step',
      status: 'running',
      payload: {},
      timestamp: '2024-01-01T00:00:01Z',
    });
    es.emit('run_event', {
      event_id: 'evt-2',
      event_type: 'step',
      status: 'running',
      payload: {},
      timestamp: '2024-01-01T00:00:02Z',
    });
    es.emit('run_complete', { status: 'succeeded', error: null });

    expect(callbacks.onStateUpdate).toHaveBeenCalledTimes(3);
    expect(callbacks.onStateUpdate.mock.calls[0][0].type).toBe('run_event');
    expect(callbacks.onStateUpdate.mock.calls[0][0].event.event_id).toBe('evt-1');
    expect(callbacks.onStateUpdate.mock.calls[1][0].type).toBe('run_event');
    expect(callbacks.onStateUpdate.mock.calls[1][0].event.event_id).toBe('evt-2');
    expect(callbacks.onStateUpdate.mock.calls[2][0].type).toBe('run_complete');
    expect(callbacks.onComplete).toHaveBeenCalledTimes(1);
  });

  test('onerror after run_complete does not trigger onFallback', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    es.emit('run_complete', { status: 'succeeded', error: null });

    // Browser fires onerror after server closes the stream
    es.triggerError();

    expect(callbacks.onFallback).not.toHaveBeenCalled();
    expect(callbacks.onComplete).toHaveBeenCalledTimes(1);
  });

  test('run_complete clears the inactivity watchdog', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', {
      ...callbacks,
      inactivityTimeoutMs: DEFAULT_RUN_STREAM_INACTIVITY_TIMEOUT_MS,
    });

    const es = MockEventSource.instances[0];
    es.emit('run_complete', { status: 'succeeded', error: null });
    jest.advanceTimersByTime(DEFAULT_RUN_STREAM_INACTIVITY_TIMEOUT_MS);

    expect(callbacks.onFallback).not.toHaveBeenCalled();
    expect(callbacks.onComplete).toHaveBeenCalledTimes(1);
  });
});
