import { useState, useEffect } from 'react';
import {
  listAdminsApiV1SuperadminAdminsGet,
  listPendingAdminsApiV1SuperadminAdminsPendingGet,
  approveAdminApiV1SuperadminAdminsAdminIdApprovePatch,
  deactivateAdminApiV1SuperadminAdminsAdminIdDeactivatePatch,
  deleteAdminApiV1SuperadminAdminsAdminIdDelete,
} from '../../client/sdk.gen';
import type { AdminProfileResponse, PendingAdminResponse } from '../../client/types.gen';
import { Button, Badge, Alert, Card, Table, Td, Spinner, EmptyState } from '../shared/ui';

export function SuperadminAdminsPage() {
  const [admins, setAdmins] = useState<AdminProfileResponse[]>([]);
  const [pending, setPending] = useState<PendingAdminResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'pending'>('all');

  const load = async () => {
    setIsLoading(true);
    const [adminsResult, pendingResult] = await Promise.all([
      listAdminsApiV1SuperadminAdminsGet(),
      listPendingAdminsApiV1SuperadminAdminsPendingGet(),
    ]);
    if (adminsResult.data) setAdmins(adminsResult.data.admins ?? []);
    if (pendingResult.data) setPending(pendingResult.data ?? []);
    setIsLoading(false);
  };

  useEffect(() => { load(); }, []);

  const flash = (msg: string) => { setSuccessMsg(msg); setTimeout(() => setSuccessMsg(null), 4000); };

  const handleApprove = async (adminId: string, username: string) => {
    const result = await approveAdminApiV1SuperadminAdminsAdminIdApprovePatch({
      path: { admin_id: adminId },
    });
    if (result.data) { flash(`${username} approved`); await load(); }
    else setError('Failed to approve admin');
  };

  const handleDeactivate = async (adminId: string, username: string) => {
    if (!confirm(`Deactivate admin ${username}?`)) return;
    const result = await deactivateAdminApiV1SuperadminAdminsAdminIdDeactivatePatch({
      path: { admin_id: adminId },
    });
    if (result.data) { flash(result.data.message); await load(); }
    else setError('Failed to deactivate admin');
  };

  const handleDelete = async (adminId: string, username: string) => {
    if (!confirm(`Delete admin ${username}? This cannot be undone.`)) return;
    const result = await deleteAdminApiV1SuperadminAdminsAdminIdDelete({
      path: { admin_id: adminId },
    });
    if (result.data) { flash(result.data.message); await load(); }
    else setError('Failed to delete admin');
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Admin Management</h1>
        <p className="text-sm text-gray-500 mt-0.5">Approve and manage admin accounts</p>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {successMsg && <Alert variant="success" onDismiss={() => setSuccessMsg(null)}>{successMsg}</Alert>}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit mb-6 mt-4">
        {([['all', 'All admins'], ['pending', 'Pending approval']] as const).map(([tab, label]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors
              ${activeTab === tab
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'}`}
          >
            {label}
            {tab === 'pending' && pending.length > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs font-semibold">
                {pending.length}
              </span>
            )}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : activeTab === 'all' ? (
          admins.length === 0 ? (
            <EmptyState icon="🛡️" title="No admins" description="Admins will appear here after they register" />
          ) : (
            <Table headers={['Admin', 'Email', 'Status', 'Verified', 'Joined', 'Actions']}>
              {admins.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <Td>
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-purple-100 flex items-center justify-center text-purple-700 text-xs font-semibold">
                        {a.username[0].toUpperCase()}
                      </div>
                      <span className="font-medium text-gray-900">{a.username}</span>
                    </div>
                  </Td>
                  <Td className="text-gray-500">{a.email}</Td>
                  <Td>
                    <Badge variant={a.is_active ? 'green' : 'red'}>
                      {a.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </Td>
                  <Td>
                    <Badge variant={a.is_verified ? 'blue' : 'yellow'}>
                      {a.is_verified ? 'Verified' : 'Pending'}
                    </Badge>
                  </Td>
                  <Td className="text-gray-400 text-xs">
                    {new Date(a.created_at).toLocaleDateString()}
                  </Td>
                  <Td>
                    <div className="flex gap-2">
                      {a.is_active && (
                        <Button variant="secondary" size="sm" onClick={() => handleDeactivate(a.id, a.username)}>
                          Deactivate
                        </Button>
                      )}
                      <Button variant="danger" size="sm" onClick={() => handleDelete(a.id, a.username)}>
                        Delete
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </Table>
          )
        ) : (
          pending.length === 0 ? (
            <EmptyState icon="✅" title="No pending registrations" description="All admin registrations have been reviewed" />
          ) : (
            <Table headers={['Admin', 'Email', 'Registered', 'Action']}>
              {pending.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <Td>
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 text-xs font-semibold">
                        {p.username[0].toUpperCase()}
                      </div>
                      <span className="font-medium text-gray-900">{p.username}</span>
                    </div>
                  </Td>
                  <Td className="text-gray-500">{p.email}</Td>
                  <Td className="text-gray-400 text-xs">
                    {new Date(p.created_at).toLocaleDateString()}
                  </Td>
                  <Td>
                    <Button size="sm" onClick={() => handleApprove(p.id, p.username)}>
                      Approve
                    </Button>
                  </Td>
                </tr>
              ))}
            </Table>
          )
        )}
      </Card>
    </div>
  );
}