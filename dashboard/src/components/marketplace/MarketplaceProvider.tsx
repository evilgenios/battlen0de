"use client";

import { createContext, useContext, useEffect, useState } from "react";
import useSWR from "swr";
import { marketplaceApi, type Listing } from "@/lib/api/marketplace";
import { useAuthSession } from "@/lib/hooks/useAuthSession";

function useMarketplaceState() {
  const { isAuthenticated } = useAuthSession();
  const config = useSWR("marketplace-config", marketplaceApi.config, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  const favorites = useSWR(
    isAuthenticated ? "marketplace-favorites" : null,
    marketplaceApi.favorites,
  );
  const [demoSaved, setDemoSaved] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Listing[]>([]);
  useEffect(() => {
    try {
      const saved: unknown = JSON.parse(
        localStorage.getItem("battlen0de-demo-favorites") ?? "[]",
      );
      if (Array.isArray(saved))
        queueMicrotask(() =>
          setDemoSaved(
            saved.filter(
              (id): id is string =>
                typeof id === "string" && id.startsWith("demo-"),
            ),
          ),
        );
    } catch {
      /* Browser storage is optional for synthetic examples. */
    }
  }, []);
  async function toggleSaved(listing: Listing) {
    if (listing.is_demo) {
      setDemoSaved((current) => {
        const next = current.includes(listing.id)
          ? current.filter((id) => id !== listing.id)
          : [...current, listing.id];
        try {
          localStorage.setItem(
            "battlen0de-demo-favorites",
            JSON.stringify(next),
          );
        } catch {
          /* In-memory saving still works. */
        }
        return next;
      });
    } else {
      if (!isAuthenticated) throw new Error("Sign in to save this listing.");
      await marketplaceApi.favorite(listing.id);
      await favorites.mutate();
    }
  }
  function toggleCompare(listing: Listing) {
    setComparison((current) =>
      current.some((row) => row.id === listing.id)
        ? current.filter((row) => row.id !== listing.id)
        : current.length < 3
          ? [...current, listing]
          : current,
    );
  }
  return {
    config: config.data,
    configError: config.error as Error | undefined,
    comparison,
    toggleCompare,
    demoSaved,
    favorites: favorites.data ?? [],
    toggleSaved,
    isSaved: (listing: Listing) =>
      listing.is_demo
        ? demoSaved.includes(listing.id)
        : Boolean(favorites.data?.some((row) => row.id === listing.id)),
  };
}
const MarketplaceContext = createContext<ReturnType<
  typeof useMarketplaceState
> | null>(null);
export function MarketplaceProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const state = useMarketplaceState();
  return (
    <MarketplaceContext.Provider value={state}>
      {children}
    </MarketplaceContext.Provider>
  );
}
export function useMarketplace() {
  const value = useContext(MarketplaceContext);
  if (!value) throw new Error("MarketplaceProvider is required");
  return value;
}
