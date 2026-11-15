import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { ApiError, api, call, type Me, type Role } from "./api/client";

export const HOME: Record<Role, string> = {
  OWNER: "/recherche",
  YARD: "/demandes",
  ADMIN: "/admin",
};

/** Utilisateur de la session (null si non connecté). Le rôle vient de l'API, jamais du client. */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<Me | null> => {
      try {
        return await call(api.GET("/api/auth/me"));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: Infinity,
  });
}

/** À utiliser sous une route protégée : l'utilisateur est alors forcément chargé. */
export function useCurrentUser(): Me {
  const { data } = useMe();
  if (!data) throw new Error("Utilisateur non connecté");
  return data;
}

export function useLogin() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => call(api.POST("/api/auth/login", { body })),
    onSuccess: (me) => {
      queryClient.clear();
      queryClient.setQueryData(["me"], me);
      navigate(HOME[me.role], { replace: true });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: () => call(api.POST("/api/auth/logout")),
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(["me"], null);
      navigate("/login", { replace: true });
    },
  });
}
