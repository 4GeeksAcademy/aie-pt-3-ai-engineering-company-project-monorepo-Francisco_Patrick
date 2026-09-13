'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { fetchWithAuth } from '../../../lib/api';

export interface ProfileState {
  readonly name: string;
  readonly phone: string;
  readonly address: string;
}

/**
 * Profile management page component allowing authenticated users to view and update contact details.
 *
 * @returns JSX Element rendering the profile settings form.
 */
export default function ProfilePage(): React.ReactElement {
  const [profile, setProfile] = useState<ProfileState>({ name: '', phone: '', address: '' });
  const [email, setEmail] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');

  const loadProfile = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError('');
    try {
      const userRes = await fetchWithAuth('/auth/me');
      if (userRes.ok) {
        const userData = await userRes.json();
        setEmail(userData?.email ?? '');
      }

      const profileRes = await fetchWithAuth('/profiles/me');
      if (profileRes.ok) {
        const profileData = await profileRes.json();
        setProfile({
          name: profileData?.name ?? '',
          phone: profileData?.phone ?? '',
          address: profileData?.address ?? '',
        });
      } else {
        throw new Error('Failed to load profile data.');
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load profile data.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    setProfile({ ...profile, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setIsSaving(true);

    try {
      const response = await fetchWithAuth('/profiles/me', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(profile),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message = errorData?.detail ?? errorData?.message ?? 'Failed to update profile';
        throw new Error(String(message));
      }

      setSuccess('Profile updated successfully!');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred while saving.';
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <div className="px-4 py-5 sm:px-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900">Personal Information</h3>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">Update your account details and contact information.</p>
        </div>
        <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 p-4 rounded-md flex items-center justify-between gap-4">
                <p className="text-sm text-red-700">{error}</p>
                <button
                  type="button"
                  onClick={() => loadProfile()}
                  className="px-3 py-1.5 text-xs font-semibold rounded bg-red-600 hover:bg-red-700 text-white transition-all shrink-0"
                >
                  🔄 Retry Loading Profile
                </button>
              </div>
            )}
            {success && (
              <div className="bg-green-50 p-4 rounded-md">
                <p className="text-sm text-green-700">{success}</p>
              </div>
            )}
            
            <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-6">
              <div className="sm:col-span-4">
                <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email address</label>
                <div className="mt-1">
                  <input type="email" name="email" id="email" disabled value={email} className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md bg-gray-100 cursor-not-allowed px-3 py-2 border" />
                </div>
                <p className="mt-2 text-sm text-gray-500">Email cannot be changed.</p>
              </div>

              <div className="sm:col-span-4">
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">Full name</label>
                <div className="mt-1">
                  <input type="text" name="name" id="name" required value={profile.name} onChange={handleChange} className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md px-3 py-2 border" />
                </div>
              </div>

              <div className="sm:col-span-4">
                <label htmlFor="phone" className="block text-sm font-medium text-gray-700">Phone number</label>
                <div className="mt-1">
                  <input type="tel" name="phone" id="phone" value={profile.phone} onChange={handleChange} className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md px-3 py-2 border" />
                </div>
              </div>

              <div className="sm:col-span-6">
                <label htmlFor="address" className="block text-sm font-medium text-gray-700">Address</label>
                <div className="mt-1">
                  <input type="text" name="address" id="address" value={profile.address} onChange={handleChange} className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md px-3 py-2 border" />
                </div>
              </div>
            </div>

            <div className="pt-5 flex justify-end">
              <button type="submit" disabled={isSaving} className={`ml-3 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}>
                {isSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

