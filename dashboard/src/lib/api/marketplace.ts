import { apiRequest } from "./client";

export interface MarketplaceConfig {
  mode: "preview" | "live";
  public_listings_enabled: boolean;
  messaging_enabled: boolean;
  offers_enabled: boolean;
  payments_enabled: boolean;
  uploads_enabled: boolean;
  transfers_enabled: boolean;
}
export type ListingStatus =
  | "draft"
  | "pending_review"
  | "active"
  | "paused"
  | "removed";
export interface ListingInput {
  title: string;
  description: string;
  commander_name: string;
  commander_id: string;
  server: number;
  strength: number;
  commander_level: number;
  collector_level: number;
  airspace: number;
  vip: number;
  composition: "ground" | "air" | "balanced";
  research: number;
  price_cents: number;
  currency: "USD";
  evidence: string;
}
export interface Listing
  extends Omit<ListingInput, "commander_id" | "evidence"> {
  id: string;
  seller_name: string;
  status: ListingStatus;
  version: number;
  is_demo: boolean;
  stats_reviewed: boolean;
  control_demonstrated: boolean;
  created_at: string;
  updated_at: string;
  commander_id?: string;
  evidence?: string;
  review_note?: string;
  seller_id?: string;
}
export interface MarketplaceDashboard {
  profile: {
    display_name: string;
    seller_enabled: boolean;
    restricted: boolean;
    staff_role: string;
  };
  listings: Listing[];
  counts: {
    active: number;
    pending_review: number;
    draft: number;
    favorites: number;
    conversations: number;
  };
  notifications: { id: string; text: string; created_at: string }[];
}
export interface Conversation {
  id: string;
  listing_id: string;
  title: string;
}
export interface Message {
  id: string;
  body: string;
  mine: boolean;
  created_at: string;
}
export interface ReviewQueue {
  listings: Listing[];
  reports: {
    id: string;
    listing_id: string;
    title: string;
    version: number;
    reason: string;
  }[];
  events: { id: string; action: string; created_at: string }[];
}
const root = "/marketplace";
export const marketplaceApi = {
  config: () => apiRequest<MarketplaceConfig>(`${root}/config`),
  listings: (query = "") =>
    apiRequest<{ items: Listing[]; total: number; mode: string }>(
      `${root}/listings${query ? `?${query}` : ""}`,
    ),
  listing: (id: string) =>
    apiRequest<Listing>(`${root}/listings/${encodeURIComponent(id)}`),
  ownListing: (id: string) =>
    apiRequest<Listing>(`${root}/me/listings/${encodeURIComponent(id)}`),
  dashboard: () => apiRequest<MarketplaceDashboard>(`${root}/me/dashboard`),
  profile: (display_name: string) =>
    apiRequest(`${root}/me/profile`, {
      method: "PATCH",
      body: { display_name },
    }),
  save: (body: ListingInput, id?: string, version?: number) =>
    apiRequest<Listing>(
      `${root}/listings${id ? `/${encodeURIComponent(id)}` : ""}`,
      { method: id ? "PATCH" : "POST", body: id ? { ...body, version } : body },
    ),
  transition: (listing: Listing, action: "submit" | "pause" | "withdraw") =>
    apiRequest<Listing>(`${root}/listings/${listing.id}/${action}`, {
      method: "POST",
      body: { version: listing.version },
    }),
  favorites: () => apiRequest<Listing[]>(`${root}/me/favorites`),
  favorite: (id: string) =>
    apiRequest<{ saved: boolean }>(`${root}/favorites/${id}`, {
      method: "POST",
    }),
  report: (id: string, reason: string) =>
    apiRequest(`${root}/reports/${id}`, { method: "POST", body: { reason } }),
  conversations: () => apiRequest<Conversation[]>(`${root}/conversations`),
  startConversation: (id: string, body: string) =>
    apiRequest<{ id: string }>(`${root}/conversations/${id}`, {
      method: "POST",
      body: { body },
    }),
  messages: (id: string) =>
    apiRequest<Message[]>(`${root}/conversations/${id}/messages`),
  send: (id: string, body: string) =>
    apiRequest(`${root}/conversations/${id}/messages`, {
      method: "POST",
      body: { body },
    }),
  reviews: () => apiRequest<ReviewQueue>(`${root}/admin/reviews`),
  decision: (
    listing: Listing,
    decision: "approve" | "reject" | "remove",
    note: string,
    stats_reviewed = false,
    control_demonstrated = false,
  ) =>
    apiRequest(`${root}/admin/listings/${listing.id}/decision`, {
      method: "POST",
      body: {
        decision,
        note,
        version: listing.version,
        stats_reviewed,
        control_demonstrated,
      },
    }),
  resolve: (id: string) =>
    apiRequest(`${root}/admin/reports/${id}/resolve`, { method: "POST" }),
  permissions: (
    id: string,
    seller_enabled: boolean,
    staff_role: string,
    restricted: boolean,
  ) =>
    apiRequest(`${root}/admin/profiles/${id}`, {
      method: "PATCH",
      body: { seller_enabled, staff_role, restricted },
    }),
};
