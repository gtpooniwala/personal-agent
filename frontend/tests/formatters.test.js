import { formatFileSize, formatRelativeTime, truncateText } from '@/lib/formatters';

describe('formatFileSize', () => {
  test('formats zero/invalid bytes as 0 B', () => {
    expect(formatFileSize(0)).toBe('0 B');
    expect(formatFileSize(-1)).toBe('0 B');
    expect(formatFileSize(Number.NaN)).toBe('0 B');
  });

  test('formats larger byte values with units', () => {
    expect(formatFileSize(1024)).toBe('1.0 KB');
    expect(formatFileSize(1024 * 1024)).toBe('1.0 MB');
  });
});

describe('truncateText', () => {
  test('returns input when shorter than max length', () => {
    expect(truncateText('hello', 10)).toBe('hello');
  });

  test('truncates and appends ellipsis when exceeding max length', () => {
    expect(truncateText('hello world', 6)).toBe('hello…');
  });
});

describe('formatRelativeTime', () => {
  beforeEach(() => {
    jest.spyOn(Date, 'now').mockReturnValue(new Date('2026-03-06T11:00:00.000Z').getTime());
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('formats recent past timestamps', () => {
    expect(formatRelativeTime('2026-03-06T10:59:20Z')).toBe('40s ago');
  });

  test('formats future timestamps', () => {
    expect(formatRelativeTime('2026-03-06T11:05:00Z')).toBe('in 5m');
  });

  test('handles missing and invalid inputs', () => {
    expect(formatRelativeTime('')).toBe('Unknown time');
    expect(formatRelativeTime('not-a-date')).toBe('Invalid date');
  });
});
