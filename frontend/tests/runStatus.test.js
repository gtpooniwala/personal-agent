import { getRunPresentation, getRunStatusClassName } from '@/lib/runStatus';

describe('getRunPresentation', () => {
  test('returns null when there is no run state', () => {
    expect(getRunPresentation(null)).toBeNull();
  });

  test('describes in-progress work from run status and latest event', () => {
    expect(
      getRunPresentation({
        status: 'running',
        latestEvent: {
          type: 'started',
          message: 'Run started',
        },
      }),
    ).toMatchObject({
      label: 'Starting',
      shortLabel: 'Starting',
      tone: 'running',
      detail: 'Run started',
    });
  });

  test('describes degraded transport separately from run failure', () => {
    expect(
      getRunPresentation({
        status: 'running',
        transport: 'degraded',
        transportMessage: 'Live updates timed out.',
      }),
    ).toMatchObject({
      label: 'Live updates lost',
      shortLabel: 'Updates lost',
      tone: 'degraded',
      detail: 'Live updates timed out.',
    });
  });

  test('keeps terminal success readable', () => {
    expect(
      getRunPresentation({
        status: 'succeeded',
        latestEvent: {
          type: 'succeeded',
          message: 'Run completed successfully',
        },
      }),
    ).toMatchObject({
      label: 'Completed',
      shortLabel: 'Completed',
      tone: 'succeeded',
      detail: 'Run completed successfully',
    });
  });
});

describe('getRunStatusClassName', () => {
  test('maps degraded in-flight runs to the degraded class', () => {
    expect(getRunStatusClassName('running', 'degraded')).toBe('degraded');
  });

  test('falls back to status class names for normal runs', () => {
    expect(getRunStatusClassName('failed')).toBe('failed');
  });
});
