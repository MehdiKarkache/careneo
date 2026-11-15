import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { Toaster } from "sonner";
import { ApiError } from "./api/client";
import { router } from "./App";
import "./index.css";

const queryClient: QueryClient = new QueryClient({
  // Session expirée pendant l'utilisation : on oublie l'utilisateur, la route protégée
  // redirige alors vers la connexion.
  queryCache: new QueryCache({
    onError: (error) => {
      if (error instanceof ApiError && error.status === 401) queryClient.setQueryData(["me"], null);
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 2,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  </StrictMode>,
);
