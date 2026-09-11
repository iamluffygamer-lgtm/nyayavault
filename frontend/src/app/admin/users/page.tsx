"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { User, Role, Department } from "@/types";
import { 
  Select,
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardBody,
  Input
} from "@/components/ui";

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);

  const [newUsername, setNewUsername] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRoleId, setNewRoleId] = useState("");
  const [newDepartmentId, setNewDepartmentId] = useState("none");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const fetchData = async () => {
    try {
      const [u, r, d] = await Promise.all([
        api.listUsers(200),
        api.listRoles(),
        api.listDepartments()
      ]);
      setUsers(u.items);
      setRoles(r);
      setDepartments(d);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleUpdate = async (userId: string, data: any) => {
    try {
      await api.updateUser(userId, data);
      await fetchData(); // Refresh data to show changes
    } catch (e: any) {
      alert("Failed to update user: " + e.message);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRoleId) {
      setError("Please select a role.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      await api.createUser({
        username: newUsername,
        email: newEmail,
        password: newPassword,
        role_id: newRoleId,
        department_id: newDepartmentId === "none" ? null : newDepartmentId
      });
      setNewUsername("");
      setNewEmail("");
      setNewPassword("");
      setNewRoleId("");
      setNewDepartmentId("none");
      fetchData();
    } catch (e: any) {
      setError(e.message || "Failed to create user");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) return <div className="p-8">Loading users...</div>;

  return (
    <div className="p-8 max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
      <div className="md:col-span-2">
        <h1 className="text-2xl font-bold mb-6">User Management</h1>
        
        <div className="bg-white border rounded-lg overflow-hidden">

        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-700 uppercase">
            <tr>
              <th className="px-6 py-3">User</th>
              <th className="px-6 py-3">Role</th>
              <th className="px-6 py-3">Department</th>
              <th className="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b">
                <td className="px-6 py-4">
                  <p className="font-medium">{u.username}</p>
                  <p className="text-xs text-slate-500">{u.email}</p>
                </td>
                <td className="px-6 py-4">
                  <Select 
                    value={u.role.id} 
                    onChange={(e) => handleUpdate(u.id, { role_id: e.target.value })}
                  >
                    {roles.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </Select>
                </td>
                <td className="px-6 py-4">
                  <Select 
                    value={u.department?.id || "none"} 
                    onChange={(e) => handleUpdate(u.id, { department_id: e.target.value === "none" ? null : e.target.value })}
                  >
                    <option value="none">No Department</option>
                    {departments.map(d => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </Select>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center space-x-2">
                    <input 
                      type="checkbox"
                      className="h-4 w-4 rounded border-gray-300 text-brand focus:ring-brand"
                      checked={u.is_active} 
                      onChange={(e) => handleUpdate(u.id, { is_active: e.target.checked })}
                    />
                    <span className={u.is_active ? "text-green-600 font-medium" : "text-slate-400"}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      <div>
        <Card>
          <CardHeader>
            <CardTitle>New User</CardTitle>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleCreate} className="space-y-4">
              {error && <div className="p-2 text-sm text-red-600 bg-red-50 rounded">{error}</div>}
              
              <div>
                <label className="text-xs font-medium">Username</label>
                <Input required value={newUsername} onChange={e => setNewUsername(e.target.value)} />
              </div>

              <div>
                <label className="text-xs font-medium">Email</label>
                <Input type="email" required value={newEmail} onChange={e => setNewEmail(e.target.value)} />
              </div>

              <div>
                <label className="text-xs font-medium">Password</label>
                <Input type="password" required value={newPassword} onChange={e => setNewPassword(e.target.value)} />
              </div>

              <div>
                <label className="text-xs font-medium">Role</label>
                <Select value={newRoleId} onChange={e => setNewRoleId(e.target.value)} required>
                  <option value="" disabled>Select a role...</option>
                  {roles.map(r => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </Select>
              </div>

              <div>
                <label className="text-xs font-medium">Department</label>
                <Select value={newDepartmentId} onChange={e => setNewDepartmentId(e.target.value)}>
                  <option value="none">No Department</option>
                  {departments.map(d => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </Select>
              </div>

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                Create User
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
