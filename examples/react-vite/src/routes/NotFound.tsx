import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <section aria-labelledby="notfound-heading">
      <h2 id="notfound-heading">Page not found</h2>
      <p>
        Try <Link to="/">going home</Link>.
      </p>
    </section>
  );
}
