import { useAuth } from '../context/AuthContext';
import { Badge, Card } from '../components/shared/ui';

export function ProfilePage() {
  const { user, role } = useAuth();

  if (!user) return null;

  const roleBadgeVariant: Record<string, 'blue' | 'green' | 'gray'> = {
    superadmin: 'blue',
    admin: 'green',
    user: 'gray',
  };

  const fields = [
    { label: 'Username', value: user.username },
    { label: 'Email', value: user.email },
    { label: 'Role', value: <Badge variant={roleBadgeVariant[role ?? 'user']}>{user.role}</Badge> },
    {
      label: 'Account status',
      value: <Badge variant={user.is_active ? 'green' : 'red'}>{user.is_active ? 'Active' : 'Inactive'}</Badge>,
    },
    {
      label: 'Email verified',
      value: <Badge variant={user.is_verified ? 'blue' : 'yellow'}>{user.is_verified ? 'Yes' : 'Pending'}</Badge>,
    },
    { label: 'Joined', value: new Date(user.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) },
    {
      label: 'Last login',
      value: user.last_login_at
        ? new Date(user.last_login_at).toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
        : '—',
    },
    { label: 'User ID', value: <span className="font-mono text-xs text-gray-400">{user.id}</span> },
  ];

  return (
    <div className="p-6 max-w-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Profile</h1>
        <p className="text-sm text-gray-500 mt-0.5">Your account details</p>
      </div>

      {/* Avatar block */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-16 h-16 rounded-2xl bg-indigo-100 flex items-center justify-center text-indigo-700 text-2xl font-bold">
          {user.username[0].toUpperCase()}
        </div>
        <div>
          <p className="text-lg font-semibold text-gray-900">{user.username}</p>
          <p className="text-sm text-gray-500">{user.email}</p>
        </div>
      </div>

      <Card className="divide-y divide-gray-100">
        {fields.map(({ label, value }) => (
          <div key={label} className="flex items-center justify-between px-5 py-3.5">
            <span className="text-sm text-gray-500 w-36 shrink-0">{label}</span>
            <span className="text-sm text-gray-900 text-right">{value}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}