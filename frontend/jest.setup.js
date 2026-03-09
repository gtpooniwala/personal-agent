import '@testing-library/jest-dom';

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

class MockEventSource {
  constructor(url) {
    this.url = url;
    this._listeners = {};
    this.readyState = 0;
    MockEventSource.instances.push(this);
  }

  addEventListener(type, fn) {
    (this._listeners[type] ??= []).push(fn);
  }

  close() {
    this.readyState = 2;
  }

  emit(type, data) {
    const event = { data: JSON.stringify(data) };
    (this._listeners[type] || []).forEach((fn) => fn(event));
  }

  triggerError() {
    if (typeof this.onerror === 'function') this.onerror(new Event('error'));
  }
}
MockEventSource.instances = [];
MockEventSource.CONNECTING = 0;
MockEventSource.OPEN = 1;
MockEventSource.CLOSED = 2;

global.MockEventSource = MockEventSource;

beforeEach(() => {
  MockEventSource.instances = [];
  global.EventSource = MockEventSource;
});
