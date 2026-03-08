import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import DashboardPage from "@/pages/dashboard-page";
import ProjectsPage from "@/pages/projects-page";
import ModelsPage from "@/pages/models-page";
import DatasetsPage from "@/pages/datasets-page";
import TrainingPage from "@/pages/training-page";
import AdaptersPage from "@/pages/adapters-page";
import WeightsPage from "@/pages/weights-page";
import RunsPage from "@/pages/runs-page";
import ComparePage from "@/pages/compare-page";
import SuggestionsPage from "@/pages/suggestions-page";
import ArtifactsPage from "@/pages/artifacts-page";
import SettingsPage from "@/pages/settings-page";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App(): React.JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/datasets" element={<DatasetsPage />} />
            <Route path="/training" element={<TrainingPage />} />
            <Route path="/adapters" element={<AdaptersPage />} />
            <Route path="/weights" element={<WeightsPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/suggestions" element={<SuggestionsPage />} />
            <Route path="/artifacts" element={<ArtifactsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
