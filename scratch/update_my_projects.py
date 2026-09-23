import os

content = '''import { Pagination } from '../common/Pagination';
import React, { useState } from 'react';
import { User, Project, Milestone } from '../../types';
import {
  FolderKanban,
  Users,
  Calendar,
  Clock,
  ExternalLink,
  X,
  Layers,
  Wrench,
  CheckCircle2,
  DollarSign,
  Briefcase,
  Paperclip,
  File,
  Download,
  Flag,
  Target,
  ChevronRight,
  Sparkles,
} from 'lucide-react';

interface MyProjectsProps {
  currentUser: User;
  projects: Project[];
  allUsers: User[];
}

export const MyProjects: React.FC<MyProjectsProps> = ({
  currentUser,
  projects = [],
  allUsers = [],
}) => {
  const [selectedProjectModal, setSelectedProjectModal] = useState<Project | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  const myProjects = (projects || []).filter((p) => p.assignedUserIds?.includes(currentUser.id));
  const paginatedProjects = myProjects.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const getMilestoneStatusBadge = (status?: string) => {
    const s = (status || 'planned').toLowerCase().trim();
    if (s === 'achieved' || s === 'completed') {
      return {
        label: 'Achieved',
        className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        dot: 'bg-emerald-500',
      };
    }
    if (s === 'in_progress') {
      return {
        label: 'In Progress',
        className: 'bg-blue-50 text-blue-700 border-blue-200',
        dot: 'bg-blue-500',
      };
    }
    return {
      label: 'Planned',
      className: 'bg-amber-50 text-amber-700 border-amber-200',
      dot: 'bg-amber-500',
    };
  };

  const getMilestoneProgress = (m: Milestone) => {
    if (m.status === 'achieved' || (m as any).status === 'completed') {
      return 100;
    }
    if (m.completion_percentage && m.completion_percentage > 0) {
      return Math.round(m.completion_percentage);
    }
    if (m.status === 'in_progress') {
      return 35; // Default 35% for In Progress milestones
    }
    return 0;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 shadow-md flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>My Assigned Projects</span>
          </h2>
          <p className="text-xs text-slate-300 mt-1">
            View project scopes, milestones & deliverables, allocated tools, and PM contacts.
          </p>
        </div>
        <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 text-xs font-bold">
          {myProjects.length} Active Assignments
        </span>
      </div>

      {/* Projects Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {paginatedProjects.map((project) => {
          const milestones = project.milestones || [];
          const achievedCount = milestones.filter(
            (m) => m.status === 'achieved' || (m as any).status === 'completed'
          ).length;

          // Calculate average milestone progress taking in-progress as 35% default
          const totalProgress = milestones.length > 0
            ? Math.round(
                milestones.reduce((acc, m) => acc + getMilestoneProgress(m), 0) / milestones.length
              )
            : 0;

          const overallProgress = project.completion_percentage && project.completion_percentage > 0
            ? Math.round(project.completion_percentage)
            : totalProgress;

          return (
            <div
              key={project.id}
              className="p-5 rounded-2xl bg-white border border-slate-200 shadow-lg hover:border-slate-300 transition-all flex flex-col justify-between space-y-4 group"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 uppercase">
                    {project.code}
                  </span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold capitalize ${
                      project.status === 'active'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : project.status === 'completed'
                        ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    }`}
                  >
                    {project.status}
                  </span>
                </div>

                <h3 className="text-base font-extrabold text-slate-900 group-hover:text-blue-600 transition-colors">
                  {project.name}
                </h3>
                <p className="text-xs text-slate-500 font-medium">Client: {project.client}</p>
                <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                  {project.description}
                </p>

                {/* Milestones Preview Bar */}
                {milestones.length > 0 && (
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-bold text-slate-700 flex items-center gap-1.5">
                        <Flag className="w-3 h-3 text-indigo-600" />
                        <span>Milestones</span>
                      </span>
                      <span className="text-indigo-600 font-semibold text-[10px]">
                        {achievedCount}/{milestones.length} Completed ({overallProgress}%)
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, Math.max(0, overallProgress))}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Stats */}
              <div className="space-y-3 pt-3 border-t border-slate-200 text-xs">
                <div className="flex justify-between items-center text-slate-600 text-[11px] font-bold">
                  <span>Logged Hours</span>
                  <span className="text-indigo-700 font-extrabold">
                    {project.loggedHours || 0} hrs
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] font-bold">
                  <div className="flex items-center gap-1.5 text-slate-700">
                    <span>PM: {project.pmName}</span>
                  </div>
                  {(project.documents || []).length > 0 ? (
                    <span className="flex items-center gap-1 text-slate-500 font-semibold">
                      <Paperclip className="w-3 h-3 text-indigo-600" />
                      {(project.documents || []).length} Docs
                    </span>
                  ) : (
                    <span className="text-slate-600">Ends {project.endDate}</span>
                  )}
                </div>

                <button
                  onClick={() => setSelectedProjectModal(project)}
                  className="w-full py-2 rounded-xl bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-800 text-xs font-bold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <Target className="w-3.5 h-3.5 text-indigo-600" />
                  <span>View Details, Milestones & Tools</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {myProjects.length > itemsPerPage && (
        <div className="mt-4 flex justify-end">
          <Pagination
            currentPage={currentPage}
            totalItems={myProjects.length}
            itemsPerPage={itemsPerPage}
            onPageChange={setCurrentPage}
            onItemsPerPageChange={(newVal) => {
              setItemsPerPage(newVal);
              setCurrentPage(1);
            }}
          />
        </div>
      )}

      {/* PROJECT DETAILS, MILESTONES, TOOLS & DOCUMENTS MODAL */}
      {selectedProjectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-white border border-slate-200 rounded-2xl shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 sticky top-0 bg-white z-10">
              <div>
                <span className="text-[10px] font-bold text-indigo-700 uppercase tracking-widest bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                  {selectedProjectModal.code}
                </span>
                <h3 className="text-xl font-extrabold text-slate-900 mt-1">
                  {selectedProjectModal.name}
                </h3>
                <p className="text-xs text-slate-500">Client: {selectedProjectModal.client}</p>
              </div>
              <button
                onClick={() => setSelectedProjectModal(null)}
                className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-800 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <h4 className="font-bold text-slate-600 uppercase tracking-wider text-[10px] mb-1">
                  Project Description & Objective
                </h4>
                <p className="text-slate-600 leading-relaxed bg-slate-50/40 p-3 rounded-xl border border-slate-200">
                  {selectedProjectModal.description || 'No description provided.'}
                </p>
              </div>

              {/* PROJECT MILESTONES & DELIVERABLES */}
              <div>
                <h4 className="font-bold text-slate-700 uppercase tracking-wider text-[10px] mb-2 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Flag className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Project Milestones & Deliverables ({(selectedProjectModal.milestones || []).length})</span>
                  </span>
                  {(selectedProjectModal.milestones || []).length > 0 && (
                    <span className="text-indigo-600 font-semibold lowercase tracking-normal">
                      {(selectedProjectModal.milestones || []).filter((m) => m.status === 'achieved').length} achieved
                    </span>
                  )}
                </h4>
                {(selectedProjectModal.milestones || []).length > 0 ? (
                  <div className="space-y-2.5">
                    {(selectedProjectModal.milestones || []).map((m, idx) => {
                      const badge = getMilestoneStatusBadge(m.status);
                      const completion = getMilestoneProgress(m);

                      return (
                        <div
                          key={m.id || idx}
                          className="p-3 rounded-xl bg-slate-50/80 border border-slate-200/80 hover:border-indigo-200 transition-all space-y-2"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="space-y-0.5 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                                  {idx + 1}
                                </span>
                                <h5 className="font-bold text-slate-800 text-xs truncate">
                                  {m.name}
                                </h5>
                              </div>
                              {m.description && (
                                <p className="text-[11px] text-slate-500 pl-7 leading-relaxed">
                                  {m.description}
                                </p>
                              )}
                            </div>

                            <span
                              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold border shrink-0 ${badge.className}`}
                            >
                              <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                              {badge.label}
                            </span>
                          </div>

                          {/* Progress & Target Dates */}
                          <div className="pl-7 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[10px] text-slate-500 pt-1 border-t border-slate-200/60">
                            <div className="flex items-center gap-1.5">
                              <Calendar className="w-3 h-3 text-slate-400" />
                              <span>
                                Target: <strong className="text-slate-700">{m.expected_completion_date || 'TBD'}</strong>
                              </span>
                            </div>

                            <div className="flex items-center justify-between sm:justify-end gap-2">
                              <span>Progress: <strong className="text-slate-700">{completion}%</strong></span>
                              <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${
                                    m.status === 'achieved' ? 'bg-emerald-500' : 'bg-indigo-600'
                                  }`}
                                  style={{ width: `${Math.min(100, Math.max(0, completion))}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-3 rounded-xl bg-slate-50/40 border border-slate-200 text-slate-400 text-xs italic">
                    No milestones defined for this project yet.
                  </div>
                )}
              </div>

              {/* Supporting Documents */}
              <div>
                <h4 className="font-bold text-slate-600 uppercase tracking-wider text-[10px] mb-2 flex items-center gap-1.5">
                  <Paperclip className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Supporting Documents ({(selectedProjectModal.documents || []).length})</span>
                </h4>
                {(selectedProjectModal.documents || []).length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {(selectedProjectModal.documents || []).map((doc) => (
                      <div
                        key={doc.id}
                        className="p-2.5 rounded-xl bg-slate-50/60 border border-slate-300/60 flex items-center justify-between gap-2 hover:border-blue-400 transition-all group"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                            <File className="w-4 h-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="font-bold text-slate-800 text-xs truncate group-hover:text-blue-600 transition-colors" title={doc.fileName}>
                              {doc.fileName}
                            </p>
                            <p className="text-[10px] text-slate-400 font-medium">
                              {formatFileSize(doc.fileSize)}
                              {doc.uploadedAt && ` • ${new Date(doc.uploadedAt).toLocaleDateString()}`}
                            </p>
                          </div>
                        </div>
                        <a
                          href={doc.filePath}
                          target="_blank"
                          rel="noopener noreferrer"
                          download={doc.fileName}
                          className="p-1.5 rounded-lg bg-white border border-slate-200 text-slate-600 hover:text-blue-600 hover:border-blue-300 transition-all shrink-0 cursor-pointer shadow-2xs"
                          title="Download document"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 rounded-xl bg-slate-50/40 border border-slate-200 text-slate-400 text-xs italic">
                    No supporting documents uploaded for this project.
                  </div>
                )}
              </div>

              {/* Tools Allocated */}
              <div>
                <h4 className="font-bold text-slate-600 uppercase tracking-wider text-[10px] mb-2">
                  Software Licenses & Cloud Tools Allocated ({selectedProjectModal.tools.length})
                </h4>
                {selectedProjectModal.tools.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {selectedProjectModal.tools.map((t) => (
                      <div
                        key={t.id}
                        className="p-2.5 rounded-xl bg-slate-50/60 border border-slate-300/60 flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <div className="p-1.5 rounded-lg bg-indigo-50 text-indigo-700 font-bold">
                            {t.category ? t.category[0] : 'T'}
                          </div>
                          <div>
                            <p className="font-bold text-slate-800">{t.name}</p>
                            <p className="text-[10px] text-slate-500">{t.category}</p>
                          </div>
                        </div>
                        <span className="font-bold text-emerald-600">${t.monthlyCost}/mo</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 rounded-xl bg-slate-50/40 border border-slate-200 text-slate-400 text-xs italic">
                    No software tools allocated to this project.
                  </div>
                )}
              </div>

              {/* Team Members */}
              <div>
                <h4 className="font-bold text-slate-600 uppercase tracking-wider text-[10px] mb-2">
                  Assigned Team Members
                </h4>
                <div className="flex flex-wrap gap-2">
                  {allUsers
                    .filter((u) => (selectedProjectModal.assignedUserIds || []).includes(u.id))
                    .map((u) => (
                      <div
                        key={u.id}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-300"
                      >
                        <img
                          src={u.avatar}
                          alt={u.name}
                          className="w-5 h-5 rounded-full object-cover"
                        />
                        <div>
                          <p className="font-semibold text-slate-800 text-[11px]">{u.name}</p>
                          <p className="text-[9px] text-slate-500">{u.title}</p>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-200 flex justify-end">
              <button
                onClick={() => setSelectedProjectModal(null)}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs cursor-pointer transition-colors"
              >
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
'''

target_path = r"C:\Users\disha\TimeSheet_Frontend\src\components\employee\MyProjects.tsx"
with open(target_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated MyProjects.tsx with 35% default for in_progress successfully.")
