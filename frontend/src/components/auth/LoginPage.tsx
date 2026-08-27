import { useState, FormEvent } from 'react';
import { loginAuthLoginPost, registerAdminAuthRegisterAdminPost } from '../../client/sdk.gen';
import { useAuth } from '../../context/AuthContext';
import { Button, Input, Alert } from '../shared/ui';
import type { TokenResponse } from '../../client/types.gen';

type Mode = 'login' | 'register';

export function LoginPage() {
  const { login } = useAuth();
  const [mode, setMode] = useState<Mode>('login');

  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsLoading(true);

    try {
      if (mode === 'login') {
        const result = await loginAuthLoginPost({ body: { email, password } });
        if (result.error || !result.data) {
          setError(extractMsg(result.error) ?? 'Login failed');
          return;
        }
        await login(result.data as TokenResponse);
      } else {
        const result = await registerAdminAuthRegisterAdminPost({
          body: { email, username, password },
        });
        if (result.error) {
          setError(extractMsg(result.error) ?? 'Registration failed');
          return;
        }
        setSuccess('Registration submitted. A superadmin must approve your account before you can log in.');
        setMode('login');
        setEmail('');
        setUsername('');
        setPassword('');
      }
    } catch (err) {
      setError('Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo mark */}
        <div className="flex justify-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center text-white text-xl font-bold shadow-lg">
            A
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm px-8 py-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-1">
            {mode === 'login' ? 'Sign in' : 'Request admin access'}
          </h1>
          <p className="text-sm text-gray-500 mb-6">
            {mode === 'login'
              ? 'Enter your credentials to continue.'
              : 'Submit your details for superadmin approval.'}
          </p>

          {error && (
            <div className="mb-4">
              <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>
            </div>
          )}
          {success && (
            <div className="mb-4">
              <Alert variant="success">{success}</Alert>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />

            {mode === 'register' && (
              <Input
                label="Username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="your_username"
                required
                autoComplete="username"
              />
            )}

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />

            <Button type="submit" className="w-full mt-2" isLoading={isLoading} size="lg">
              {mode === 'login' ? 'Sign in' : 'Submit registration'}
            </Button>
          </form>
        </div>

        {/* Toggle */}
        <p className="text-center text-sm text-gray-500 mt-4">
          {mode === 'login' ? (
            <>
              Need admin access?{' '}
              <button
                onClick={() => { setMode('register'); setError(null); setSuccess(null); }}
                className="text-indigo-600 font-medium hover:underline"
              >
                Register
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button
                onClick={() => { setMode('login'); setError(null); setSuccess(null); }}
                className="text-indigo-600 font-medium hover:underline"
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}

function extractMsg(err: unknown): string | null {
  if (!err) return null;
  if (typeof err === 'string') return err;
  const e = err as Record<string, unknown>;
  if (typeof e.detail === 'string') return e.detail;
  if (Array.isArray(e.detail)) return (e.detail as { msg: string }[]).map((d) => d.msg).join(', ');
  return null;
}