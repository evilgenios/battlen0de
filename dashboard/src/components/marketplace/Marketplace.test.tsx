import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import {
  marketplaceApi,
  type MarketplaceConfig,
  type MarketplaceDashboard,
} from "@/lib/api/marketplace";
import { DEMO_LISTINGS } from "@/lib/marketplace/demo";
import { MarketplaceProvider } from "./MarketplaceProvider";
import { Storefront } from "./Storefront";
import { ComparisonView } from "./BuyerDashboard";
import { ListingWizard } from "./ListingWizard";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/marketplace",
}));
vi.mock("@/lib/hooks/useAuthSession", () => ({
  useAuthSession: () => ({ isAuthenticated: false, isLoading: false }),
}));
const config: MarketplaceConfig = {
  mode: "preview",
  public_listings_enabled: false,
  messaging_enabled: false,
  payments_enabled: false,
  transfers_enabled: false,
  offers_enabled: false,
  uploads_enabled: false,
};

beforeEach(() => {
  vi.restoreAllMocks();
  push.mockReset();
  localStorage.clear();
  vi.spyOn(marketplaceApi, "config").mockResolvedValue(config);
});

describe("marketplace discovery", () => {
  it("filters sample commanders by combined military attributes and resets them", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MarketplaceProvider>
        <Storefront />
      </MarketplaceProvider>,
    );
    expect(
      screen.getByText(/All statistics, sellers, and prices are illustrative/),
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Military focus"), "air");
    expect(
      screen.getByRole("link", {
        name: "Air Superiority Specialist",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", {
        name: "Elite Ground Commander",
      }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Advanced filters/ }));
    await user.type(screen.getByLabelText("Minimum airspace"), "2100");
    expect(await screen.findByText("No commanders found.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.getAllByRole("article")).toHaveLength(3);
  });

  it("saves demos separately and carries selected statistics into comparison", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MarketplaceProvider>
        <Storefront />
        <ComparisonView />
      </MarketplaceProvider>,
    );
    await user.click(
      screen.getByRole("button", {
        name: "Save Elite Ground Commander",
      }),
    );
    expect(
      screen.getByRole("button", {
        name: "Unsave Elite Ground Commander",
      }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      JSON.parse(localStorage.getItem("battlen0de-demo-favorites")!),
    ).toEqual(["demo-ground-commander"]);
    const cards = screen.getAllByRole("article");
    await user.click(
      within(cards[0]).getByRole("button", {
        name: "Add to comparison",
      }),
    );
    await user.click(
      within(cards[1]).getByRole("button", {
        name: "Add to comparison",
      }),
    );
    const table = screen.getByRole("table");
    expect(within(table).getByText("822M")).toBeInTheDocument();
    expect(within(table).getByText("758M")).toBeInTheDocument();
    expect(within(table).getByText("2,030")).toHaveClass("mp-best");
    await user.click(
      within(table).getByRole("button", {
        name: "Remove Elite Ground Commander from comparison",
      }),
    );
    expect(within(table).queryByText("822M")).not.toBeInTheDocument();
  });

  it("shows a live catalog failure instead of disguising it as sample inventory", async () => {
    vi.spyOn(marketplaceApi, "config").mockResolvedValue({
      ...config,
      mode: "live",
      public_listings_enabled: true,
    });
    vi.spyOn(marketplaceApi, "listings").mockRejectedValue(
      new Error("Live catalog unavailable"),
    );
    renderWithProviders(
      <MarketplaceProvider>
        <Storefront />
      </MarketplaceProvider>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live catalog unavailable",
    );
    expect(
      screen.queryByText("Elite Ground Commander"),
    ).not.toBeInTheDocument();
  });
});

it("creates a private draft through all wizard steps using a strict API payload", async () => {
  const user = userEvent.setup();
  const dashboard: MarketplaceDashboard = {
    profile: {
      display_name: "Tester",
      seller_enabled: true,
      restricted: false,
      staff_role: "user",
    },
    listings: [],
    counts: {
      active: 0,
      draft: 0,
      pending_review: 0,
      favorites: 0,
      conversations: 0,
    },
    notifications: [],
  };
  vi.spyOn(marketplaceApi, "dashboard").mockResolvedValue(dashboard);
  const save = vi.spyOn(marketplaceApi, "save").mockResolvedValue({
    ...DEMO_LISTINGS[0],
    id: "new-private-id",
    is_demo: false,
    status: "draft",
  });
  renderWithProviders(<ListingWizard />);
  await user.type(
    screen.getByLabelText("Listing title"),
    "QA Ground Commander",
  );
  await user.type(screen.getByLabelText("Commander name"), "QA Commander");
  await user.type(screen.getByLabelText(/Public commander ID/), "987654");
  await user.type(
    screen.getByLabelText("Commander overview"),
    "A synthetic commander with detailed ground development for QA.",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.clear(screen.getByLabelText("Total strength (full number)"));
  await user.type(
    screen.getByLabelText("Total strength (full number)"),
    "822000000",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.type(
    screen.getByLabelText("Supporting evidence notes"),
    "Synthetic evidence submitted for testing the listing flow.",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("button", { name: "Save draft" }));
  await waitFor(() =>
    expect(push).toHaveBeenCalledWith("/marketplace/dashboard/listings"),
  );
  expect(save).toHaveBeenCalledTimes(1);
  expect(save.mock.calls[0][0]).toMatchObject({
    title: "QA Ground Commander",
    commander_id: "987654",
    strength: 822000000,
    currency: "USD",
  });
  expect(save.mock.calls[0][0]).not.toHaveProperty("status");
  expect(save.mock.calls[0][0]).not.toHaveProperty("seller_id");
});
