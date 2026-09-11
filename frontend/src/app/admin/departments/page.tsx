"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Department } from "@/types";
import { 
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Input,
  Select,
  Textarea
} from "@/components/ui";

const ORG_TYPES = [
  "NATIONAL", "STATE", "DISTRICT", "POLICE_UNIT", 
  "STATION", "FORENSIC_LAB", "COURT", "OTHER"
];

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [orgType, setOrgType] = useState("OTHER");
  const [parentId, setParentId] = useState<string>("none");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchDepartments = async () => {
    try {
      const data = await api.listDepartments();
      setDepartments(data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDepartments();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    
    try {
      await api.createDepartment({
        name,
        description: description || null,
        org_type: orgType,
        parent_id: parentId === "none" ? null : parentId
      });
      setName("");
      setDescription("");
      setOrgType("OTHER");
      setParentId("none");
      fetchDepartments();
    } catch (e: any) {
      setError(e.message || "Failed to create department");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) return <div className="p-8">Loading departments...</div>;

  return (
    <div className="p-8 max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
      <div className="md:col-span-2">
        <h1 className="text-2xl font-bold mb-6">Organization Hierarchy</h1>
        <div className="space-y-2">
          {departments.map(dept => {
            const depth = Math.max(0, dept.path.split("/").length - 3);
            return (
              <div 
                key={dept.id} 
                className="p-3 border rounded-md bg-white flex justify-between items-center"
                style={{ marginLeft: `${depth * 2}rem` }}
              >
                <div>
                  <p className="font-medium text-sm">{dept.name}</p>
                  <p className="text-xs text-slate-500">{dept.org_type}</p>
                </div>
              </div>
            );
          })}
          {departments.length === 0 && <p>No departments found.</p>}
        </div>
      </div>
      
      <div>
        <Card>
          <CardHeader>
            <CardTitle>New Department</CardTitle>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <div className="p-2 text-sm text-red-600 bg-red-50 rounded">{error}</div>}
              
              <div>
                <label className="text-xs font-medium">Name</label>
                <Input required value={name} onChange={e => setName(e.target.value)} />
              </div>
              
              <div>
                <label className="text-xs font-medium">Org Type</label>
                <Select value={orgType} onChange={e => setOrgType(e.target.value)}>
                  {ORG_TYPES.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </Select>
              </div>
              
              <div>
                <label className="text-xs font-medium">Parent Department</label>
                <Select value={parentId} onChange={e => setParentId(e.target.value)}>
                  <option value="none">None (Root)</option>
                  {departments.map(d => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </Select>
              </div>
              
              <div>
                <label className="text-xs font-medium">Description</label>
                <Textarea value={description} onChange={e => setDescription(e.target.value)} />
              </div>
              
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                Create Department
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
