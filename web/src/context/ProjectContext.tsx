'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api } from '@/lib/api';
import type { Project } from '@/types/api';

const STORAGE_KEY = 'aa-project';

interface ProjectContextValue {
  projects: Project[];
  selectedProjectId: string | null;
  setSelectedProjectId: (id: string | null) => void;
  currentProject: Project | null;
  project: Project | null;
  isLoading: boolean;
  isLoadingProject: boolean;
  error: string | null;
  refreshProjects: () => Promise<void>;
  refreshProject: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

/**
 * Load project summaries and the selected project's full detail.
 *
 * Selection is persisted in localStorage so a reload keeps the workspace. The
 * detail request also tells the backend which project is current, which is what
 * the chat and generation routes read.
 *
 * @param props - React children.
 * @returns Provider element.
 */
export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedId] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingProject, setIsLoadingProject] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setSelectedProjectId = useCallback((id: string | null) => {
    setSelectedId(id);
    if (id) window.localStorage.setItem(STORAGE_KEY, id);
    else window.localStorage.removeItem(STORAGE_KEY);
  }, []);

  const refreshProjects = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.get<Project[]>('/api/v1/projects');
      setProjects(data);
      setError(null);
      setSelectedId((previous) => {
        const stored = previous ?? window.localStorage.getItem(STORAGE_KEY);
        const keep = stored && data.some((item) => item.id === stored) ? stored : null;
        return keep ?? (data.length ? data[0].id : null);
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load projects');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshProject = useCallback(async () => {
    const id = selectedProjectId;
    if (!id) {
      setProject(null);
      return;
    }
    setIsLoadingProject(true);
    try {
      setProject(await api.get<Project>('/api/v1/projects/' + id));
      setError(null);
    } catch (reason) {
      setProject(null);
      setError(reason instanceof Error ? reason.message : 'Could not load project');
    } finally {
      setIsLoadingProject(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  // The provider remains mounted while LoginPage transitions into the workspace.
  // Reload project data after sign-in if its initial unauthenticated fetch failed.
  useEffect(() => {
    const onAuthenticated = () => { void refreshProjects(); };
    window.addEventListener('aa-authenticated', onAuthenticated);
    return () => window.removeEventListener('aa-authenticated', onAuthenticated);
  }, [refreshProjects]);

  useEffect(() => {
    if (selectedProjectId) window.localStorage.setItem(STORAGE_KEY, selectedProjectId);
    void refreshProject();
  }, [selectedProjectId, refreshProject]);

  const value = useMemo<ProjectContextValue>(() => ({
    projects,
    selectedProjectId,
    setSelectedProjectId,
    currentProject: project,
    project,
    isLoading,
    isLoadingProject,
    error,
    refreshProjects,
    refreshProject,
  }), [projects, selectedProjectId, setSelectedProjectId, project, isLoading, isLoadingProject, error, refreshProjects, refreshProject]);

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

/**
 * Read the active project and reload helpers.
 *
 * @returns Project context value.
 * @throws Error When called outside ProjectProvider.
 */
export function useProject(): ProjectContextValue {
  const context = useContext(ProjectContext);
  if (!context) throw new Error('useProject must be used within a ProjectProvider');
  return context;
}

