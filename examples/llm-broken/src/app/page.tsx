"use client";

// LLM-broken anti-pattern: mock data shipped in production build.
const MOCK_ORDERS = [
  { id: "mock-1", customer: "Alice", total: 9.99, status: "pending" },
  { id: "mock-2", customer: "Bob", total: 42.0, status: "shipped" },
  { id: "mock-3", customer: "Carol", total: 17.5, status: "pending" },
];

export default function HomePage() {
  // LLM-broken anti-pattern: dead "Save" button — no onClick wiring.
  // LLM-broken anti-pattern: console error silently ignored.
  return (
    <section aria-labelledby="home-heading">
      <h2 id="home-heading">Recent orders</h2>
      <ul>
        {MOCK_ORDERS.map((order) => (
          <li key={order.id}>
            {order.customer} — ${order.total.toFixed(2)} ({order.status})
          </li>
        ))}
      </ul>
      <button type="button">Save</button>
      <noscript>
        <p>JavaScript is required to use this page.</p>
      </noscript>
      <script
        dangerouslySetInnerHTML={{
          __html: `
            try {
              window.dispatchEvent(new ErrorEvent('error', { message: 'demo glitch' }));
            } catch (e) {
              // LLM-broken: swallowed console error.
            }
          `,
        }}
      />
    </section>
  );
}
