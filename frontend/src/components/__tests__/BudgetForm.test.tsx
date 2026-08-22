import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import BudgetForm from "../BudgetForm";
import { api } from "../../lib/api";

describe("BudgetForm", () => {
  it("refuses category allocations that exceed the monthly budget", async () => {
    const user = userEvent.setup();
    const save = vi.spyOn(api, "saveBudget");
    render(<BudgetForm existing={null} onSaved={vi.fn()} />);

    const income = screen.getByLabelText(/money available/i);
    await user.clear(income);
    await user.type(income, "5000");

    await user.click(screen.getByText(/add a category limit/i));
    const allocation = screen.getAllByRole("spinbutton").at(-1)!;
    await user.clear(allocation);
    await user.type(allocation, "9000");

    await user.click(screen.getByRole("button", { name: /save budget/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/exceeds|more than/i);
    // Caught client-side; the API is never called with an invalid budget.
    expect(save).not.toHaveBeenCalled();
  });

  it("refuses a savings target larger than income", async () => {
    const user = userEvent.setup();
    const save = vi.spyOn(api, "saveBudget");
    render(<BudgetForm existing={null} onSaved={vi.fn()} />);

    const savings = screen.getByLabelText(/savings goal/i);
    await user.clear(savings);
    await user.type(savings, "99999");
    await user.click(screen.getByRole("button", { name: /save budget/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/savings/i);
    expect(save).not.toHaveBeenCalled();
  });

  it("submits a valid budget and hands the result back", async () => {
    const user = userEvent.setup();
    const saved = {
      id: "1", month: 8, year: 2026, total_income: 15000, savings_target: 2000, rules: [],
    };
    vi.spyOn(api, "saveBudget").mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<BudgetForm existing={null} onSaved={onSaved} />);
    await user.click(screen.getByRole("button", { name: /save budget/i }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved));
    expect(api.saveBudget).toHaveBeenCalledWith(
      expect.objectContaining({ total_income: 15000, savings_target: 2000 }),
    );
  });

  it("surfaces a server-side rejection instead of failing silently", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "saveBudget").mockRejectedValue(
      Object.assign(new Error("Savings target cannot exceed total income for the month."), {
        name: "ApiError", status: 422,
      }),
    );
    render(<BudgetForm existing={null} onSaved={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /save budget/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
