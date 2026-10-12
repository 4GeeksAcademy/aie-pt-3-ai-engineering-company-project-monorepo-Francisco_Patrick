'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { resetPassword } from '../../lib/authApi';

function ResetPasswordForm(): React.ReactElement {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!token) {
      setError('No se ha proporcionado un token de restablecimiento válido en la URL.');
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden. Por favor, verifícalas.');
      return;
    }

    if (newPassword.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.');
      return;
    }

    setIsLoading(true);

    try {
      await resetPassword(token, newPassword);
      router.push('/login?reset=success');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Error al restablecer la contraseña. El token puede ser inválido o haber expirado.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-md w-full space-y-8 bg-slate-900/90 p-8 rounded-2xl border border-slate-800 shadow-2xl backdrop-blur-xl">
      <div>
        <h2 className="mt-2 text-center text-3xl font-extrabold text-slate-100">Restablecer Contraseña</h2>
        <p className="mt-2 text-center text-sm text-slate-400">
          Introduce tu nueva contraseña a continuación.
        </p>
      </div>

      <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3 flex-1">
                <p className="text-sm text-red-700">{error}</p>
                <div className="mt-2">
                  <Link href="/forgot-password" className="text-sm font-medium text-red-700 underline hover:text-red-600">
                    Solicitar un nuevo enlace de restablecimiento
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-slate-200">
              Nueva Contraseña
            </label>
            <input
              id="new-password"
              name="new_password"
              type="password"
              required
              className="mt-1 appearance-none block w-full px-3 py-2 border border-slate-700 bg-slate-800/80 rounded-md shadow-sm placeholder-slate-400 text-slate-100 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
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
              className="mt-1 appearance-none block w-full px-3 py-2 border border-slate-700 bg-slate-800/80 rounded-md shadow-sm placeholder-slate-400 text-slate-100 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmPassword(e.target.value)}
            />
          </div>
        </div>

        <div>
          <button
            type="submit"
            disabled={isLoading || !token}
            className={`w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 ${
              isLoading || !token ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {isLoading ? 'Actualizando...' : 'Guardar nueva contraseña'}
          </button>
        </div>

        <div className="text-sm text-center">
          <Link href="/login" className="font-medium text-indigo-400 hover:text-indigo-300">
            Volver al Inicio de Sesión
          </Link>
        </div>
      </form>
    </div>
  );
}

/**
 * Reset password page wrapper component.
 *
 * @returns JSX Element rendering the reset password form with Suspense boundary.
 */
export default function ResetPasswordPage(): React.ReactElement {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100 py-12 px-4 sm:px-6 lg:px-8">
      <Suspense fallback={<div className="text-slate-300">Cargando formulario...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
