'use client';

import { useState } from 'react';
import Link from 'next/link';
import { changePassword } from '../../../lib/authApi';

/**
 * Change password page component allowing users to update their credentials.
 *
 * @returns JSX Element rendering the change password form.
 */
export default function ChangePasswordPage(): React.ReactElement {
  const [currentPassword, setCurrentPassword] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');

  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError('');
    setSuccessMessage('');

    if (newPassword !== confirmPassword) {
      setError('La nueva contraseña y su confirmación no coinciden.');
      return;
    }

    if (newPassword.length < 8) {
      setError('La nueva contraseña debe tener al menos 8 caracteres.');
      return;
    }

    setIsLoading(true);

    try {
      const res = await changePassword(currentPassword, newPassword);
      setSuccessMessage(res.message || 'Contraseña actualizada correctamente.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'La contraseña actual es incorrecta o la sesión no es válida.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md mx-auto bg-slate-900/90 p-8 rounded-2xl border border-slate-800 shadow-2xl backdrop-blur-xl space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-100 text-center">Cambiar Contraseña</h2>
          <p className="mt-2 text-sm text-slate-400 text-center">
            Actualiza la contraseña de tu cuenta de usuario.
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {successMessage && (
          <div className="bg-green-950/60 border-l-4 border-green-500 p-4 rounded-md">
            <p className="text-sm text-green-200">{successMessage}</p>
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="current-password" className="block text-sm font-medium text-slate-200">
              Contraseña Actual
            </label>
            <input
              id="current-password"
              name="current_password"
              type="password"
              required
              className="mt-1 block w-full px-3 py-2 border border-slate-700 bg-slate-800/80 text-slate-100 placeholder-slate-400 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="••••••••"
              value={currentPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCurrentPassword(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-slate-200">
              Nueva Contraseña
            </label>
            <input
              id="new-password"
              name="new_password"
              type="password"
              required
              className="mt-1 block w-full px-3 py-2 border border-slate-700 bg-slate-800/80 text-slate-100 placeholder-slate-400 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="••••••••"
              value={newPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewPassword(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium text-slate-200">
              Confirmar Nueva Contraseña
            </label>
            <input
              id="confirm-password"
              name="confirm_password"
              type="password"
              required
              className="mt-1 block w-full px-3 py-2 border border-slate-700 bg-slate-800/80 text-slate-100 placeholder-slate-400 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmPassword(e.target.value)}
            />
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className={`w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 ${
                isLoading ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {isLoading ? 'Actualizando...' : 'Cambiar Contraseña'}
            </button>
          </div>

          <div className="text-center pt-2">
            <Link href="/" className="text-sm font-medium text-indigo-400 hover:text-indigo-300">
              Volver al Panel Principal
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
