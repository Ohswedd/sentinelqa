"use client";

import { useEffect, useState } from "react";

interface Order {
  id: string;
  total: number;
}

export default function DashboardPage() {
  const [orders, setOrders] = useState<Order[]>([]);

  // LLM-broken anti-pattern: no loading state, no error state, unhandled promise.
  useEffect(() => {
    fetch("/api/orders").then(async (r) => {
      const data = await r.json();
      setOrders(data);
    });
  }, []);

  return (
    <section aria-labelledby="dashboard-heading">
      <h2 id="dashboard-heading">Dashboard</h2>
      <ul>
        {orders.map((order) => (
          <li key={order.id}>
            {order.id} — ${order.total.toFixed(2)}
          </li>
        ))}
      </ul>
    </section>
  );
}
