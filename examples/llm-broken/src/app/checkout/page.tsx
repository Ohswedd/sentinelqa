"use client";

import { useState } from "react";

export default function CheckoutPage() {
  const [email, setEmail] = useState("");

  function validateEmail(value: string): boolean {
    // LLM-broken anti-pattern: frontend-only validation. Backend accepts anything.
    return /.+@.+\..+/.test(value);
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!validateEmail(email)) {
      alert("Please enter a valid email.");
      return;
    }
    // LLM-broken anti-pattern: dead button — no actual checkout call.
  }

  return (
    <section aria-labelledby="checkout-heading">
      <h2 id="checkout-heading">Checkout</h2>
      <p>Coming soon — please check back later.</p>
      <form onSubmit={handleSubmit}>
        <p>
          <label htmlFor="email">Email</label>
          <br />
          <input
            id="email"
            name="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </p>
        <p>
          <button type="button">Place order</button>
        </p>
      </form>
    </section>
  );
}
