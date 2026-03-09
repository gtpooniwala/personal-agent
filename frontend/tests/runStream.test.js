import { subscribeToRunStream } from '@/lib/runStream';

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

  test('opens EventSource at correct URL', () => {
    const callbacks = makeCallbacks();
    subscribeToRunStream('run-xyz', callbacks);

    const es = MockEventSource.instances[0];
    expect(es).toBeDefined();
    expect(es.url).toBe(`${RUNTIME_API_BASE}/runs/run-xyz/stream`);
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
        event_type: 'tool_call',
        status: 'running',
        message: 'hello',
        tool: 'search',
        metadata: { k: 'v' },
        timestamp: '2024-01-01T00:00:00Z',
      },
    });
    expect(callbacks.onComplete).not.toHaveBeenCalled();
    expect(callbacks.onFallback).not.toHaveBeenCalled();
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
});
