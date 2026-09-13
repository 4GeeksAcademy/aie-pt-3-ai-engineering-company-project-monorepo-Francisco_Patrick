import { requestPasswordReset, resetPassword, changePassword } from '../lib/authApi';

// Mock global fetch
const globalFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = globalFetch;

describe('Auth API Helpers (lib/authApi.ts)', (): void => {
  beforeEach((): void => {
    jest.clearAllMocks();
  });

  describe('requestPasswordReset', (): void => {
    test('Happy Path: returns success payload when API responds OK', async (): Promise<void> => {
      const successResponse = { message: 'If that email is registered, you will receive a reset link shortly.' };
      globalFetch.mockResolvedValueOnce({
        ok: true,
        json: async (): Promise<unknown> => successResponse,
      } as Response);

      const result = await requestPasswordReset('user@example.com');

      expect(result).toEqual(successResponse);
      expect(globalFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/forgot-password'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'user@example.com' }),
        })
      );
    });

    test('Failure Mode: throws Error with detail message when API returns error response', async (): Promise<void> => {
      globalFetch.mockResolvedValueOnce({
        ok: false,
        json: async (): Promise<unknown> => ({ detail: 'Invalid email address format' }),
      } as Response);

      await expect(requestPasswordReset('invalid-email')).rejects.toThrow('Invalid email address format');
    });
  });

  describe('resetPassword', (): void => {
    test('Happy Path: returns success payload when token is valid', async (): Promise<void> => {
      const successResponse = { message: 'Password successfully updated.' };
      globalFetch.mockResolvedValueOnce({
        ok: true,
        json: async (): Promise<unknown> => successResponse,
      } as Response);

      const result = await resetPassword('valid-token', 'NewPassword123!');

      expect(result).toEqual(successResponse);
      expect(globalFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/reset-password'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ token: 'valid-token', new_password: 'NewPassword123!' }),
        })
      );
    });

    test('Failure Mode: throws Error when token is invalid or expired', async (): Promise<void> => {
      globalFetch.mockResolvedValueOnce({
        ok: false,
        json: async (): Promise<unknown> => ({ detail: 'El token de restablecimiento es inválido o ha expirado.' }),
      } as Response);

      await expect(resetPassword('invalid-token', 'NewPassword123!')).rejects.toThrow('El token de restablecimiento es inválido o ha expirado.');
    });
  });

  describe('changePassword', (): void => {
    test('Happy Path: returns success payload when current password is correct', async (): Promise<void> => {
      const successResponse = { message: 'Password successfully changed.' };
      globalFetch.mockResolvedValueOnce({
        ok: true,
        json: async (): Promise<unknown> => successResponse,
      } as Response);

      const result = await changePassword('CurrentPassword123!', 'NewPassword123!');

      expect(result).toEqual(successResponse);
      expect(globalFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/change-password'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ current_password: 'CurrentPassword123!', new_password: 'NewPassword123!' }),
        })
      );
    });

    test('Failure Mode: throws Error when current password is wrong', async (): Promise<void> => {
      globalFetch.mockResolvedValueOnce({
        ok: false,
        json: async (): Promise<unknown> => ({ detail: 'Incorrect current password.' }),
      } as Response);

      await expect(changePassword('WrongPassword123!', 'NewPassword123!')).rejects.toThrow('Incorrect current password.');
    });
  });
});
