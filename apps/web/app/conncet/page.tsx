import { redirect } from "next/navigation"

// Catches the common "conncet" misspelling and sends it to the real page.
export default function ConnectTypoRedirect() {
  redirect("/connect")
}
