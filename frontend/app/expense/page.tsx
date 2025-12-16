import { redirect } from "next/navigation";

export default function ExpenseRedirect() {
  // Fast server-side redirect to the canonical expenses workspace
  redirect("/expenses");
}
