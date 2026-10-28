import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";
import { BarkSettings } from "./bark-settings";

describe("BarkSettings", () => {
  it("saves a device URL, clears the input, and disables notifications", async () => {
    const writes: unknown[] = [];
    server.use(
      http.get("/api/settings/notifications", () => HttpResponse.json({ configured: false })),
      http.put("/api/settings/notifications", async ({ request }) => {
        const body = await request.json() as { barkUrl: string | null };
        writes.push(body);
        return HttpResponse.json({ configured: body.barkUrl !== null });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BarkSettings disabled={false} />);
    await screen.findByText("Disabled");
    const input = screen.getByLabelText("Bark device URL");
    expect(input).toHaveAttribute("type", "password");
    await user.type(input, "https://bark.example/private-key");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Enabled");
    expect(input).toHaveValue("");
    expect(writes).toEqual([{ barkUrl: "https://bark.example/private-key" }]);
    await user.click(screen.getByRole("button", { name: "Disable" }));
    await screen.findByText("Disabled");
    expect(writes[1]).toEqual({ barkUrl: null });
  });

  it("preserves the unsaved URL when saving fails", async () => {
    server.use(
      http.get("/api/settings/notifications", () => HttpResponse.json({ configured: false })),
      http.put("/api/settings/notifications", () => HttpResponse.json({ error: { code: "failed", message: "Could not save" } }, { status: 500 })),
    );
    const user = userEvent.setup();
    renderWithProviders(<BarkSettings disabled={false} />);
    await screen.findByText("Disabled");
    const input = screen.getByLabelText("Bark device URL");
    await user.type(input, "https://bark.example/key");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getByText("Could not save")).toBeInTheDocument());
    expect(input).toHaveValue("https://bark.example/key");
  });
});
