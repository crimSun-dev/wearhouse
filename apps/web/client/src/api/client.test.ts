import {describe, expect, it, vi} from 'vitest';
import {createApi, createIntent, mediaUrl} from './index';

const base = 'http://127.0.0.1:8100/api/v2';
const auth = {token: vi.fn(async () => 'first')};
describe('v2 client', () => {
  it('retains rate limits, field errors and support IDs', async () => {
    const field = {field: 'body.name', message: 'Required'};
    const response = Response.json({code: 'RATE_LIMITED', message: 'Wait', field_errors: [field], request_id: 'example'},
      {status: 429, headers: {'Retry-After': '30'}});
    const api = createApi(auth, base, async () => response);
    await expect(api.call('get', '/api/v2/me', {})).rejects.toMatchObject({
      code: 'RATE_LIMITED', retryAfter: 30, requestId: 'example', fieldErrors: [field],
    });
  });
  it('handles empty responses and obtains a fresh bearer each time', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response(null, {status: 204}));
    const broker = {token: vi.fn().mockResolvedValueOnce('a').mockResolvedValueOnce('b')};
    const api = createApi(broker, base, fetcher);
    for (const token of ['a', 'b']) {
      expect(await api.call('get', '/api/v2/me', {})).toBeUndefined();
      expect(new Headers(fetcher.mock.lastCall?.[1]?.headers).get('Authorization')).toBe('Bearer ' + token);
    }
  });
  it('reuses the intent on retry and rotates it when the submitted body changes', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => Response.json({}));
    const api = createApi(auth, base, fetcher);
    const intent = createIntent();
    const keys = [];
    for (const price of [100, 100, 200]) {
      await api.call('post', '/api/v2/me/checkout', {intent, body: {expected_total_idr: price}});
      keys.push(new Headers(fetcher.mock.lastCall?.[1]?.headers).get('Idempotency-Key'));
    }
    expect(keys[0]).toMatch(/^web-/);
    expect(keys[1]).toBe(keys[0]);
    expect(keys[2]).not.toBe(keys[1]);
  });
  it('rejects stale responses even when the transport ignores the signal', async () => {
    let release!: (response: Response) => void;
    const fetcher = vi.fn(() => new Promise<Response>(resolve => { release = resolve; }));
    const api = createApi(auth, base, fetcher);
    const controller = new AbortController();
    const result = api.call('get', '/api/v2/me', {signal: controller.signal});
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalled());
    controller.abort();
    release(Response.json({}));
    await expect(result).rejects.toMatchObject({name: 'AbortError'});
  });
  it('times out while waiting for the broker', async () => {
    const api = createApi({token: () => new Promise(() => {})}, base, fetch, 10);
    await expect(api.call('get', '/api/v2/me', {})).rejects.toMatchObject({name: 'TimeoutError'});
  });
  it('sends and receives image bytes without JSON encoding', async () => {
    const image = new Blob(['pixels'], {type: 'image/png'});
    const fetcher = vi.fn<typeof fetch>(async () => new Response(image));
    const api = createApi(auth, base, fetcher);
    const path = {item_id: 'my/photo'};
    expect(await (await api.blob('/api/v2/me/wardrobe/items/{item_id}/photo', {path})).text()).toBe('pixels');
    fetcher.mockResolvedValueOnce(Response.json({}));
    await api.call('put', '/api/v2/me/wardrobe/items/{item_id}/photo', {path, body: image});
    expect(fetcher.mock.lastCall?.[1]?.body).toBe(image);
    expect(String(fetcher.mock.lastCall?.[0])).toBe(base + '/me/wardrobe/items/my%2Fphoto/photo');
  });
  it('resolves media against the API origin', () => {
    expect(mediaUrl('/api/v2/media/example', base)).toBe(base + '/media/example');
  });
});
