import React, { useState, useEffect } from 'react';
import { fetchEmployees, addEmployee, deleteEmployee } from '../api';
import type { Employee } from '../types';
import { Users, UserPlus, Trash2, Briefcase } from 'lucide-react';

export const TeamSettings: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [newPosition, setNewPosition] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    loadEmployees();
  }, []);

  const loadEmployees = async () => {
    try {
      setLoading(true);
      const data = await fetchEmployees();
      setEmployees(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load team members');
    } finally {
      setLoading(false);
    }
  };

  const handleAddEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newPosition.trim()) return;

    try {
      const emp = await addEmployee(newName, newPosition);
      setEmployees(prev => [...prev, emp]);
      setNewName('');
      setNewPosition('');
    } catch (err: any) {
      setError(err.message || 'Failed to add employee');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Remove this team member?')) return;
    try {
      await deleteEmployee(id);
      setEmployees(prev => prev.filter(e => e.id !== id));
    } catch (err: any) {
      setError(err.message || 'Failed to remove employee');
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-stone-50 p-8 overflow-y-auto">
      <div className="max-w-4xl mx-auto w-full">
        <div className="flex items-center gap-5 mb-10">
          <div className="p-4 bg-white border border-stone-200 shadow-sm rounded-2xl">
            <Users size={32} className="text-accent-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold font-heading text-stone-900 tracking-tight">
              Team Management
            </h1>
            <p className="text-stone-500 mt-1 text-lg">Add team members to assign them compliance tasks.</p>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-8 text-red-600 font-medium">
            {error}
          </div>
        )}

        <div className="grid md:grid-cols-3 gap-8">
          <div className="md:col-span-1">
            <form onSubmit={handleAddEmployee} className="bg-white border border-stone-200 rounded-2xl p-6 shadow-soft">
              <h3 className="text-xl font-heading font-bold text-stone-900 mb-6 flex items-center gap-2">
                <UserPlus size={20} className="text-accent-600" />
                Add Member
              </h3>
              
              <div className="space-y-5">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Name</label>
                  <input 
                    type="text"
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    className="w-full bg-stone-50 border border-stone-200 rounded-xl p-3 text-stone-800 focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 outline-none transition-all shadow-inner"
                    placeholder="e.g. Jane Doe"
                  />
                </div>
                
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Position / Role</label>
                  <input 
                    type="text"
                    value={newPosition}
                    onChange={e => setNewPosition(e.target.value)}
                    className="w-full bg-stone-50 border border-stone-200 rounded-xl p-3 text-stone-800 focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 outline-none transition-all shadow-inner"
                    placeholder="e.g. CISO, Risk Officer"
                  />
                </div>
                
                <button 
                  type="submit"
                  disabled={!newName.trim() || !newPosition.trim()}
                  className="w-full bg-accent-600 hover:bg-accent-700 disabled:opacity-50 disabled:hover:bg-accent-600 text-white font-bold py-3 rounded-xl transition-colors shadow-sm mt-2"
                >
                  Add Team Member
                </button>
              </div>
            </form>
          </div>

          <div className="md:col-span-2">
            <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-soft h-full flex flex-col">
              <div className="bg-stone-50 p-5 border-b border-stone-200 flex items-center justify-between">
                <h3 className="font-bold text-stone-800 font-heading text-lg flex items-center gap-2">
                  <Briefcase size={20} className="text-stone-400" />
                  Current Roster
                </h3>
                <span className="text-xs font-bold uppercase tracking-wider bg-white border border-stone-200 text-stone-500 px-3 py-1 rounded-full shadow-sm">
                  {employees.length} Members
                </span>
              </div>
              
              {loading ? (
                <div className="p-12 text-center text-stone-400">Loading...</div>
              ) : employees.length === 0 ? (
                <div className="p-16 text-center text-stone-400 font-medium flex flex-col items-center flex-1 justify-center">
                  <Users size={64} className="mb-6 text-stone-200" />
                  No team members added yet.
                </div>
              ) : (
                <div className="divide-y divide-stone-100 flex-1 overflow-y-auto">
                  {employees.map(emp => (
                    <div key={emp.id} className="p-5 flex items-center justify-between hover:bg-stone-50 transition-colors">
                      <div className="flex flex-col gap-1">
                        <span className="text-stone-900 font-bold text-lg">{emp.name}</span>
                        <span className="text-sm text-accent-600 font-semibold">{emp.position}</span>
                      </div>
                      <button 
                        onClick={() => handleDelete(emp.id)}
                        className="p-2.5 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-colors border border-transparent hover:border-red-100 shadow-sm"
                        title="Remove Member"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
