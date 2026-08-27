import { useState, useEffect } from 'react';
import {
  listAllUsersApiV1SuperadminUsersGet,
  ingestDataApiV1SuperadminIngestPost,
} from '../../client/sdk.gen';
import type { UserProfileResponse } from '../../client/types.gen';
import { Button, Badge, Alert, Card, Table, Td, Spinner, EmptyState } from '../shared/ui';

export function SuperadminUsersPage() {
  const [users, setUsers] = useState<UserProfileResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const load = async () => {
    setIsLoading(true);
    const result = await listAllUsersApiV1SuperadminUsersGet();
    if (result.data) {
      setUsers(result.data.users ?? []);
      setTotal(result.data.total ?? 0);
    }
    setIsLoading(false);
  };

  useEffect(() => { load(); }, []);

  const filtered = users.filter(
    (u) =>
      u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.role.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const roleBadge = (role: string) => {
    const map: Record<string, 'blue' | 'gray' | 'green'> = {
      superadmin: 'blue',
      admin: 'green',
      user: 'gray',
    };
    return map[role] ?? 'gray';
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">All Users</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} total across all admins</p>
        </div>
        <Button variant="secondary" onClick={load}>↺ Refresh</Button>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <div className="mb-4">
        <input
          type="text"
          className="w-full max-w-xs px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="Search by name, email or role…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : filtered.length === 0 ? (
          <EmptyState icon="🌐" title={searchQuery ? 'No matches' : 'No users'} />
        ) : (
          <Table headers={['User', 'Email', 'Role', 'Status', 'Joined', 'Last login']}>
            {filtered.map((u) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <Td>
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 text-xs font-semibold">
                      {u.username[0].toUpperCase()}
                    </div>
                    <span className="font-medium text-gray-900">{u.username}</span>
                  </div>
                </Td>
                <Td className="text-gray-500 text-xs">{u.email}</Td>
                <Td><Badge variant={roleBadge(u.role)}>{u.role}</Badge></Td>
                <Td><Badge variant={u.is_active ? 'green' : 'red'}>{u.is_active ? 'Active' : 'Inactive'}</Badge></Td>
                <Td className="text-gray-400 text-xs">{new Date(u.created_at).toLocaleDateString()}</Td>
                <Td className="text-gray-400 text-xs">
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : '—'}
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}