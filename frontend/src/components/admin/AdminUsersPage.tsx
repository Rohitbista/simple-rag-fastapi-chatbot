import { useState, useEffect, FormEvent } from 'react';
import {
  listMyUsersApiV1AdminUsersGet,
  createUserApiV1AdminUsersPost,
  deactivateUserApiV1AdminUsersUserIdDeactivatePatch,
  deleteUserApiV1AdminUsersUserIdDelete,
} from '../../client/sdk.gen';
import type { UserProfileResponse } from '../../client/types.gen';
import {
  Button, Input, Badge, Modal, Alert, Card,
  Table, Td, Spinner, EmptyState,
} from '../shared/ui';

export function AdminUsersPage() {
  const [users, setUsers] = useState<UserProfileResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = async () => {
    setIsLoading(true);
    const result = await listMyUsersApiV1AdminUsersGet();
    if (result.data) {
      setUsers(result.data.users ?? []);
      setTotal(result.data.total ?? 0);
    }
    setIsLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleDeactivate = async (userId: string, username: string) => {
    if (!confirm(`Deactivate ${username}? They will no longer be able to log in.`)) return;
    const result = await deactivateUserApiV1AdminUsersUserIdDeactivatePatch({
      path: { user_id: userId },
    });
    if (result.data) {
      setSuccessMsg(result.data.message);
      await load();
    } else {
      setError('Failed to deactivate user');
    }
  };

  const handleDelete = async (userId: string, username: string) => {
    if (!confirm(`Permanently delete ${username}? This cannot be undone.`)) return;
    const result = await deleteUserApiV1AdminUsersUserIdDelete({
      path: { user_id: userId },
    });
    if (result.data) {
      setSuccessMsg(result.data.message);
      await load();
    } else {
      setError('Failed to delete user');
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">My Users</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} user{total !== 1 ? 's' : ''} under your account</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>+ Create user</Button>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)} classname="mb-4">{error}</Alert>}
      {successMsg && <Alert variant="success" onDismiss={() => setSuccessMsg(null)}>{successMsg}</Alert>}

      <Card className="mt-4 overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : users.length === 0 ? (
          <EmptyState
            icon="👥"
            title="No users yet"
            description="Create a user to get started"
            action={<Button onClick={() => setShowCreate(true)}>Create first user</Button>}
          />
        ) : (
          <Table headers={['User', 'Email', 'Status', 'Joined', 'Actions']}>
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <Td>
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 text-xs font-semibold">
                      {u.username[0].toUpperCase()}
                    </div>
                    <span className="font-medium text-gray-900">{u.username}</span>
                  </div>
                </Td>
                <Td className="text-gray-500">{u.email}</Td>
                <Td>
                  <Badge variant={u.is_active ? 'green' : 'red'}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </Td>
                <Td className="text-gray-400 text-xs">
                  {new Date(u.created_at).toLocaleDateString()}
                </Td>
                <Td>
                  <div className="flex gap-2">
                    {u.is_active && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeactivate(u.id, u.username)}
                      >
                        Deactivate
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => handleDelete(u.id, u.username)}
                    >
                      Delete
                    </Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <CreateUserModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={async (msg) => {
          setSuccessMsg(msg);
          setShowCreate(false);
          await load();
        }}
      />
    </div>
  );
}

function CreateUserModal({
  isOpen,
  onClose,
  onCreated,
}: {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (msg: string) => void;
}) {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setEmail(''); setUsername(''); setPassword(''); setError(null);
  };

  const handleClose = () => { reset(); onClose(); };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    const result = await createUserApiV1AdminUsersPost({
      body: { email, username, password },
    });
    setIsLoading(false);
    if (result.data) {
      reset();
      onCreated(`User "${result.data.username}" created successfully`);
    } else {
      setError(extractMsg(result.error) ?? 'Failed to create user');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Create new user">
      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
        <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" required />
        <Input label="Username" type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" required />
        <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
        <div className="flex gap-3 pt-2">
          <Button type="button" variant="secondary" className="flex-1" onClick={handleClose}>Cancel</Button>
          <Button type="submit" className="flex-1" isLoading={isLoading}>Create user</Button>
        </div>
      </form>
    </Modal>
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