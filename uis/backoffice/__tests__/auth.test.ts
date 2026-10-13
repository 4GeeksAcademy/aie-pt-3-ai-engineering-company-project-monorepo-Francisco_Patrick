import { setToken, getToken, removeToken, isAuthenticated } from '../lib/auth';

describe('Auth Storage Helpers (lib/auth.ts)', () => {
  beforeEach(() => {
    localStorage.clear();
    jest.clearAllMocks();
  });

  test('setToken stores JWT token in localStorage and updates isAuthenticated status', (): void => {
    const testToken = 'mock.jwt.access_token_string';
    setToken(testToken);

    expect(getToken()).toBe(testToken);
    expect(isAuthenticated()).toBe(true);
  });

  test('removeToken clears token from localStorage and resets isAuthenticated status', (): void => {
    const testToken = 'mock.jwt.access_token_string';
    setToken(testToken);
    expect(isAuthenticated()).toBe(true);

    removeToken();

    expect(getToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  test('getToken returns null when no token is stored', (): void => {
    expect(getToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });
});
